from __future__ import annotations

import asyncio

from livekit import agents
from livekit.agents import Agent, AgentServer, AgentSession, JobContext, RunContext, function_tool
from livekit.plugins import openai
from livekit.plugins.openai.realtime.realtime_model import TurnDetection

from lifeops.agent import LifeOpsAgent
from lifeops.config import get_settings
from lifeops.dependencies import get_agent
from lifeops.models import AgentRequest


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
    if context.session.room_io:
        try:
            await context.session.room_io.room.local_participant.publish_data(
                '{"stage":"Retrieving memory and researching current sources"}',
                reliable=True,
                topic="myminion.progress",
            )
        except Exception:
            pass
    await context.update("I’m checking your preferences and researching the best next step.")

    async def complete_mission() -> str:
        response = await get_agent().respond(
            AgentRequest(
                user_id="demo-user",
                session_id=f"voice-{room_name}",
                message=request,
            )
        )
        if context.session.room_io:
            try:
                await context.session.room_io.room.local_participant.publish_data(
                    response.model_dump_json(),
                    reliable=True,
                    topic="myminion.agent_result",
                )
            except Exception:
                # Moss persistence has already completed; a closed room must not undo the work.
                pass
        return response.message

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


class MyMinionVoiceAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are MyMinion, a warm, smart, voice-first personal agent. Talk naturally "
                "and keep answers concise enough to hear. For buying, travel, relationship "
                "intelligence, or other real-world tasks, always call run_lifeops_agent so you "
                "use current research and long-term memory. Call the tool before asking a buying "
                "or travel follow-up because Moss may already contain the answer. If the user "
                "names a specific product, immediately research current offers instead of asking "
                "generic category, feature, or budget questions. Ask only one genuinely unresolved "
                "question at a time. Trip planning in particular may take several short back-and-forth "
                "questions — dates, flight or road, restaurants, hotel or Airbnb, budget, and "
                "pace — before an itinerary is ready; that is expected, so keep asking one at a "
                "time rather than guessing. Speak in English unless the user explicitly requests "
                "another language. Never say you are a chatbot or scaffold."
            ),
            tools=[run_lifeops_agent],
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
    await session.start(room=ctx.room, agent=MyMinionVoiceAgent())
    await session.generate_reply(
        instructions="Greet the user briefly and ask what you can take care of."
    )


if __name__ == "__main__":
    agents.cli.run_app(server)
