from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

from livekit import api

from lifeops.config import Settings
from lifeops.models import LiveKitTokenRequest, LiveKitTokenResponse


class LiveKitTokenService:
    """Issue narrowly scoped, short-lived participant tokens."""

    def __init__(self, settings: Settings) -> None:
        if not (
            settings.livekit_url
            and settings.livekit_api_key
            and settings.livekit_api_secret
        ):
            raise RuntimeError("LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET are required")
        self._url = settings.livekit_url
        self._key = settings.livekit_api_key
        self._secret = settings.livekit_api_secret
        self._agent_name = settings.livekit_agent_name

    def issue(self, request: LiveKitTokenRequest) -> LiveKitTokenResponse:
        room_name = request.room_name or f"myminion-{uuid4().hex[:12]}"
        identity = f"web-{uuid4().hex}"
        room_config = api.RoomConfiguration(
            agents=[api.RoomAgentDispatch(agent_name=self._agent_name)]
        )
        token = (
            api.AccessToken(self._key, self._secret)
            .with_identity(identity)
            .with_name(request.participant_name or "MyMinion user")
            .with_ttl(timedelta(minutes=15))
            .with_grants(api.VideoGrants(room_join=True, room=room_name))
            .with_room_config(room_config)
            .to_jwt()
        )
        return LiveKitTokenResponse(
            server_url=self._url,
            participant_token=token,
            room_name=room_name,
            participant_identity=identity,
        )
