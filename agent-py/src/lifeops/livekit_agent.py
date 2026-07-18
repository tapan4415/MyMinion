from __future__ import annotations

from livekit import agents
from livekit.agents import Agent, AgentServer, AgentSession, JobContext, RunContext, function_tool
from livekit.plugins import openai

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
        await context.session.room_io.room.local_participant.publish_data(
            '{"stage":"Retrieving memory and researching current sources"}',
            reliable=True,
            topic="myminion.progress",
        )
    await context.update("I’m checking your preferences and researching the best next step.")
    response = await get_agent().respond(
        AgentRequest(
            user_id="voice-user",
            session_id=f"voice-{room_name}",
            message=request,
        )
    )
    if context.session.room_io:
        await context.session.room_io.room.local_participant.publish_data(
            response.model_dump_json(),
            reliable=True,
            topic="myminion.agent_result",
        )
    return response.message


class MyMinionVoiceAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are MyMinion, a warm, smart, voice-first personal agent. Talk naturally "
                "and keep answers concise enough to hear. For buying, travel, relationship "
                "intelligence, or other real-world tasks, always call run_lifeops_agent so you "
                "use current research and long-term memory. Ask only one missing question at a "
                "time. Speak in English unless the user explicitly requests another language. "
                "Never say you are a chatbot or scaffold."
            ),
            tools=[run_lifeops_agent],
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
        )
    )
    await session.start(room=ctx.room, agent=MyMinionVoiceAgent())
    await session.generate_reply(
        instructions="Greet the user briefly and ask what you can take care of."
    )


if __name__ == "__main__":
    agents.cli.run_app(server)
