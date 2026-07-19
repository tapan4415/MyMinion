from __future__ import annotations

import asyncio
import json

from livekit import agents
from livekit.agents import Agent, AgentServer, AgentSession, JobContext, RunContext, function_tool
from livekit.plugins import openai
from livekit.plugins.openai.realtime.realtime_model import TurnDetection

from lifeops.agent import LifeOpsAgent
from lifeops.config import get_settings
from lifeops.dependencies import get_agent, get_moss
from lifeops.memory import MemoryManager
from lifeops.models import AgentRequest, UseCase


class LiveKitVoiceBridge:
    def __init__(self, agent: LifeOpsAgent) -> None:
        self._agent = agent

    async def handle_transcript(self, *, user_id: str, session_id: str, transcript: str) -> str:
        response = await self._agent.respond(
            AgentRequest(user_id=user_id, session_id=session_id, message=transcript)
        )
        return response.message


@function_tool
async def run_lifeops_agent(context: RunContext, request: str) -> str:
    """Plan and research a real-world request using MyMinion's memory and specialist agents."""
    room_name = context.session.room_io.room.name if context.session.room_io else "voice"

    async def publish(topic: str, payload: str) -> None:
        if not context.session.room_io:
            return
        try:
            await context.session.room_io.room.local_participant.publish_data(
                payload,
                reliable=True,
                topic=topic,
            )
        except Exception:
            pass

    recalled = None
    moss_error = ""
    for attempt in range(1, 3):
        try:
            recalled = await MemoryManager(get_moss()).retrieve("demo-user", request)
            break
        except Exception as error:
            detail = str(error)
            moss_error = (
                "Moss usage limit exceeded (monthly allowance reached)"
                if "USAGE_LIMIT_EXCEEDED" in detail or "429 Too Many Requests" in detail
                else f"Moss retrieval failed ({type(error).__name__})"
            )
            await publish(
                "myminion.error",
                json.dumps(
                    {
                        "stage": (
                            "Retrying the complete mission from Moss retrieval (2/2)"
                            if attempt == 1
                            else "Mission stopped after Moss retry failed"
                        ),
                        "error": moss_error,
                        "retrying": attempt == 1,
                    }
                ),
            )
            if attempt == 1:
                await asyncio.sleep(1)
    if recalled is None:
        return f"I couldn’t continue because {moss_error}."

    recalled_details = [
        f"{memory.kind.value.replace('_', ' ')}: {memory.content}" for memory in recalled[:5]
    ]
    if context.session.room_io:
        try:
            await context.session.room_io.room.local_participant.publish_data(
                json.dumps(
                    {
                        "stage": (
                            f"Moss recalled {len(recalled_details)} memories; "
                            "researching approved retailers"
                            if recalled_details
                            else "No matching Moss memory; researching approved retailers"
                        ),
                        "memories": recalled_details,
                    }
                ),
                reliable=True,
                topic="myminion.progress",
            )
        except Exception:
            pass
    await context.update(
        "I found your saved preferences and I’m checking Amazon, Walmart, Best Buy, "
        "and Target for first-generation Apple AirPods."
        if recalled_details
        else "I’m checking Amazon, Walmart, Best Buy, and Target for verified offers."
    )

    async def complete_mission() -> str:
        last_error = "No verified priced offers were returned"
        for attempt in range(1, 3):
            if attempt > 1:
                await publish(
                    "myminion.error",
                    json.dumps(
                        {
                            "stage": f"Retrying the complete mission ({attempt}/2)",
                            "error": last_error,
                            "retrying": True,
                        }
                    ),
                )
            try:
                response = await get_agent().respond(
                    AgentRequest(
                        user_id="demo-user",
                        session_id=f"voice-{room_name}-attempt-{attempt}",
                        message=request,
                    )
                )
                incomplete_buying = (
                    response.use_case == UseCase.BUYING and not response.recommendations
                )
                if incomplete_buying and attempt < 2:
                    last_error = "Approved retailers returned no verified dollar-priced offers"
                    continue
                await publish("myminion.agent_result", response.model_dump_json())
                return response.message
            except Exception as error:
                last_error = f"{type(error).__name__}: provider mission failed"
                if attempt < 2:
                    continue

        await publish(
            "myminion.error",
            json.dumps(
                {
                    "stage": "Mission failed after automatic retry",
                    "error": last_error,
                    "retrying": False,
                }
            ),
        )
        return f"I couldn’t complete the mission after retrying. {last_error}."

    # The mission is intentionally independent of the current speech turn. A user can
    # interrupt the voice response without cancelling research or Moss persistence.
    mission = asyncio.create_task(complete_mission())
    try:
        async with context.with_filler(
            lambda step: (
                "I’m still working through the live sources."
                if step % 2 == 0
                else "I’m comparing the evidence now; the mission will keep running."
            ),
            delay=6,
            interval=10,
            max_steps=6,
        ):
            return await asyncio.shield(mission)
    except asyncio.CancelledError:
        # asyncio.shield keeps complete_mission running and it will publish the result.
        return "I heard you. The mission is still running in the background."


@function_tool
async def recall_memory(context: RunContext, query: str) -> str:
    """Look up what MyMinion remembers about the user, a person, a preference, a plan, or an
    earlier topic. Call this whenever the user asks what you know, who someone is, about their
    preferences or plans, or anything from the past."""
    from lifeops.dependencies import get_moss
    from lifeops.memory import MemoryManager

    moss = get_moss()
    # Force a fresh cloud read so recall sees facts the Scribe wrote from another process.
    for name in ("user_profile", "preferences", "journeys", "decisions", "contacts"):
        index = getattr(moss, name, None)
        loaded = getattr(index, "_loaded_indexes", None)
        remote = getattr(index, "remote_name", None)
        if loaded is not None and remote is not None:
            loaded.discard(remote)

    lines: list[str] = []
    for record in await MemoryManager(moss).retrieve("demo-user", query, limit=8):
        lines.append(f"- {record.content}")
    try:
        for contact in await moss.contacts.search(query, limit=4, filters={"user_id": "demo-user"}):
            identity = contact.get("identity") or contact.get("content")
            if identity:
                lines.append(f"- {contact.get('name')}: {identity}")
    except Exception:
        pass

    seen: set[str] = set()
    unique: list[str] = []
    for line in lines:
        key = line.lower()
        if key not in seen:
            seen.add(key)
            unique.append(line)
    if not unique:
        return f"I don't have anything saved about '{query}' yet."
    return "Here is what I remember:\n" + "\n".join(unique[:12])


class MyMinionVoiceAgent(Agent):
    def __init__(self, memory_context: str = "") -> None:
        remembered_context = (
            "\n\nMoss context loaded before this voice session:\n"
            f"{memory_context}\n"
            "Treat this as authoritative user context. If the user asks vaguely what they "
            "wanted to buy, where they wanted to travel, or to continue a plan, use the "
            "matching section and most relevant active journey instead of claiming you have "
            "no information. Do not mix a shopping budget into a trip or a trip budget into "
            "shopping. Ask only for trip fields that are genuinely absent from Trip planning "
            "memory."
            if memory_context
            else ""
        )
        super().__init__(
            instructions=(
                "You are MyMinion, a warm, smart, voice-first personal agent. Perform with an "
                "original tiny-helper voice: bright, playful, enthusiastic, and slightly higher "
                "in register, with a quick musical cadence and occasional delighted reactions. "
                "Stay clearly understandable, never become shrill, never use gibberish, and do "
                "not imitate any existing movie character or actor. Match the moment: curious "
                "while listening, focused during research, reassuring on retries, and excited "
                "when a mission succeeds. Talk naturally and keep answers concise enough to "
                "hear. For buying, travel, relationship "
                "intelligence, or other real-world tasks, always call run_lifeops_agent so you "
                "use current research and long-term memory. Whenever the user asks what you "
                "know, who a person is, or about their preferences, plans, family, or anything "
                "from earlier, ALWAYS call recall_memory first and answer from what it returns; "
                "never say you do not know without calling recall_memory. Call run_lifeops_agent "
                "before asking a buying or travel follow-up because Moss may already contain the "
                "answer. If the user names a specific product, immediately research current offers "
                "instead of asking generic category, feature, or budget questions. Ask only one "
                "genuinely unresolved question at a time. Trip planning in particular may take "
                "several short back-and-forth "
                "questions — dates, flight or road, restaurants, hotel or Airbnb, budget, and "
                "pace — before an itinerary is ready; that is expected, so keep asking one at a "
                "time rather than guessing. Speak in English unless the user explicitly requests "
                "another language. Never say you are a chatbot or scaffold."
                f"{remembered_context}"
            ),
            tools=[run_lifeops_agent, recall_memory],
            allow_interruptions=True,
        )


settings = get_settings()
server = AgentServer(
    ws_url=settings.livekit_url,
    api_key=settings.livekit_api_key,
    api_secret=settings.livekit_api_secret,
)


@server.rtc_session(agent_name=settings.livekit_agent_name)
async def livekit_entrypoint(ctx: JobContext) -> None:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required for the voice worker")
    # Do not rely on the realtime model choosing a memory tool before its first answer.
    # Preload a small, domain-oriented Moss persona so vague continuation questions work.
    memory_context = ""
    try:
        manager = MemoryManager(get_moss())
        sections: list[str] = []
        domains = (
            (
                "Shopping memory",
                (
                    "active shopping journey what product the user wants to buy",
                    "product brand model form factor preference earbuds headphones shopping budget",
                ),
                False,
            ),
            (
                "Trip planning memory",
                (
                    "active travel trip journey destination dates departure lodging food "
                    "pace budget",
                    "travel preferences dietary lodging transportation home location companions",
                ),
                True,
            ),
        )
        for label, queries, journeys_only in domains:
            recalled = []
            seen: set[str] = set()
            for query in queries:
                # Take a balanced sample from both intent and preference queries instead of
                # allowing repeated journeys from the first query to crowd preferences out.
                for record in await manager.retrieve("demo-user", query, limit=6):
                    if journeys_only and record.kind.value != "journey":
                        continue
                    if record.id not in seen:
                        seen.add(record.id)
                        recalled.append(record)
            if recalled:
                lines = "\n".join(
                    f"- {record.kind.value}: {record.content}" for record in recalled[:10]
                )
                sections.append(f"{label}:\n{lines}")
        memory_context = "\n\n".join(sections)
    except Exception:
        # The recall_memory tool remains available if startup preloading is unavailable.
        memory_context = ""
    session = AgentSession(
        llm=openai.realtime.RealtimeModel(
            model="gpt-realtime",
            voice="marin",
            api_key=settings.openai_api_key,
            turn_detection=TurnDetection(
                type="semantic_vad",
                eagerness="medium",
                create_response=True,
                interrupt_response=False,
            ),
        )
    )
    await session.start(room=ctx.room, agent=MyMinionVoiceAgent(memory_context))
    await session.generate_reply(
        instructions=(
            "In the bright, playful, slightly high-register MyMinion voice, greet the user "
            "briefly with cheerful tiny-helper energy and ask what mission you can take care of. "
            "Keep every word clear and do not imitate an existing character."
        )
    )


if __name__ == "__main__":
    agents.cli.run_app(server)
