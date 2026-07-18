from __future__ import annotations

from abc import ABC, abstractmethod

from lifeops.models import SessionState


class SessionRepository(ABC):
    @abstractmethod
    async def get(self, session_id: str) -> SessionState | None: ...
    @abstractmethod
    async def save(self, state: SessionState) -> SessionState: ...


class InMemorySessionRepository(SessionRepository):
    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}

    async def get(self, session_id: str) -> SessionState | None:
        return self._sessions.get(session_id)

    async def save(self, state: SessionState) -> SessionState:
        self._sessions[state.session_id] = state
        return state
