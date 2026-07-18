from __future__ import annotations

from lifeops.agent import LifeOpsAgent
from lifeops.models import AgentRequest


class LiveKitVoiceBridge:
    """Provider-neutral voice bridge used by a LiveKit job entrypoint."""

    def __init__(self, agent: LifeOpsAgent) -> None:
        self._agent = agent

    async def handle_transcript(self, *, user_id: str, session_id: str, transcript: str) -> str:
        response = await self._agent.respond(
            AgentRequest(user_id=user_id, session_id=session_id, message=transcript)
        )
        return response.message


async def livekit_entrypoint(job_context: object) -> None:
    """Integration seam for livekit-agents.

    A production adapter connects the room, transcribes speech, passes transcripts to
    LiveKitVoiceBridge, and streams the returned response to TTS. No credentials or
    network calls are embedded in this scaffold.
    """
    _ = job_context
