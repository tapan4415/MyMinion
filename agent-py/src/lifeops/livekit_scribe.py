"""Always-on Scribe worker.

A second LiveKit agent that joins the SAME room as the conversational Companion but
is STT-only: no LLM, no TTS -> it physically cannot speak. It transcribes the room
audio, debounces the transcript, and hands each chunk to ScribeEnricher, which decides
what is important, stores it in Moss, and researches it with Bright Data.

Run: python -m lifeops.livekit_scribe start   (registers as settings.livekit_scribe_agent_name)
"""

from __future__ import annotations

import asyncio
import json

from livekit import agents
from livekit.agents import Agent, AgentServer, AgentSession, JobContext
from livekit.plugins import openai, silero

from lifeops.config import get_settings
from lifeops.dependencies import get_bright_data, get_moss
from lifeops.memory import MemoryManager
from lifeops.research import ResearchManager
from lifeops.scribe import ScribeEnricher

settings = get_settings()
server = AgentServer(
    ws_url=settings.livekit_url,
    api_key=settings.livekit_api_key,
    api_secret=settings.livekit_api_secret,
    # The Companion worker already binds the default health port (8081); give the
    # Scribe its own so both workers can run on the same machine.
    port=8082,
)

_FLUSH_SILENCE_SECONDS = 4.0


@server.rtc_session(agent_name=settings.livekit_scribe_agent_name)
async def scribe_entrypoint(ctx: JobContext) -> None:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required for the scribe worker")

    moss = get_moss()
    enricher = ScribeEnricher(
        MemoryManager(moss),
        ResearchManager(get_bright_data(), moss),
        moss=moss,
        openai_api_key=settings.openai_api_key,
        model=settings.scribe_model,
    )

    # STT-only session: omitting llm and tts means the Scribe never generates or
    # speaks a reply. It only listens.
    session = AgentSession(
        stt=openai.STT(api_key=settings.openai_api_key),
        vad=silero.VAD.load(),
    )

    buffer: list[str] = []
    lock = asyncio.Lock()
    flush_handle: dict[str, asyncio.Task | None] = {"task": None}

    async def flush() -> None:
        async with lock:
            if not buffer:
                return
            text = " ".join(buffer).strip()
            buffer.clear()
        if not text:
            return
        try:
            result = await enricher.enrich(text)
        except Exception:
            return
        try:
            await ctx.room.local_participant.publish_data(
                json.dumps(
                    {
                        "heard": result.heard[:280],
                        "saved": len(result.memories),
                        "researched": len(result.research),
                        "people": len(result.people),
                    }
                ),
                reliable=True,
                topic="myminion.scribe",
            )
        except Exception:
            # A closed room must not undo the Moss writes that already succeeded.
            pass

    async def debounce() -> None:
        try:
            await asyncio.sleep(_FLUSH_SILENCE_SECONDS)
            await flush()
        except asyncio.CancelledError:
            pass

    def on_transcribed(event: object) -> None:
        if not getattr(event, "is_final", False):
            return
        transcript = (getattr(event, "transcript", "") or "").strip()
        if not transcript:
            return
        buffer.append(transcript)
        pending = flush_handle["task"]
        if pending and not pending.done():
            pending.cancel()
        flush_handle["task"] = asyncio.create_task(debounce())

    session.on("user_input_transcribed", on_transcribed)

    await session.start(
        room=ctx.room,
        agent=Agent(instructions="You are a silent transcriber. You never speak."),
    )


if __name__ == "__main__":
    agents.cli.run_app(server)
