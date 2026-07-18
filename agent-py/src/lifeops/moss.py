from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict
from copy import deepcopy
from typing import Any, Generic, TypeVar
from uuid import uuid4

T = TypeVar("T", bound=dict[str, Any])


class MossIndex(ABC, Generic[T]):
    """Repository contract for one semantic Moss index."""

    name: str

    @abstractmethod
    async def save(self, document: T) -> T: ...

    @abstractmethod
    async def search(
        self, query: str, *, limit: int = 10, filters: dict[str, Any] | None = None
    ) -> list[T]: ...

    @abstractmethod
    async def update(self, document_id: str, changes: dict[str, Any]) -> T | None: ...

    @abstractmethod
    async def delete(self, document_id: str) -> bool: ...


class InMemoryMossIndex(MossIndex[T]):
    def __init__(self, name: str) -> None:
        self.name = name
        self._documents: dict[str, T] = {}

    async def save(self, document: T) -> T:
        stored = deepcopy(document)
        stored.setdefault("id", uuid4().hex)
        self._documents[str(stored["id"])] = stored
        return deepcopy(stored)

    async def search(
        self, query: str, *, limit: int = 10, filters: dict[str, Any] | None = None
    ) -> list[T]:
        terms = query.lower().split()
        matches: list[T] = []
        for document in self._documents.values():
            if filters and any(document.get(key) != value for key, value in filters.items()):
                continue
            haystack = " ".join(str(value) for value in document.values()).lower()
            if not terms or any(term in haystack for term in terms):
                matches.append(deepcopy(document))
        return matches[:limit]

    async def update(self, document_id: str, changes: dict[str, Any]) -> T | None:
        if document_id not in self._documents:
            return None
        self._documents[document_id].update(changes)
        return deepcopy(self._documents[document_id])

    async def delete(self, document_id: str) -> bool:
        return self._documents.pop(document_id, None) is not None


class MossClient:
    """Typed index registry. Replace construction with the Moss SDK adapter later."""

    INDEX_NAMES = (
        "user_profile",
        "preferences",
        "journeys",
        "research",
        "decisions",
        "contacts",
        "interactions",
        "recommendations",
    )

    def __init__(self, indexes: dict[str, MossIndex[dict[str, Any]]] | None = None) -> None:
        self._indexes = indexes or {name: InMemoryMossIndex(name) for name in self.INDEX_NAMES}

    @property
    def user_profile(self) -> MossIndex[dict[str, Any]]:
        return self._indexes["user_profile"]

    @property
    def preferences(self) -> MossIndex[dict[str, Any]]:
        return self._indexes["preferences"]

    @property
    def journeys(self) -> MossIndex[dict[str, Any]]:
        return self._indexes["journeys"]

    @property
    def research(self) -> MossIndex[dict[str, Any]]:
        return self._indexes["research"]

    @property
    def decisions(self) -> MossIndex[dict[str, Any]]:
        return self._indexes["decisions"]

    @property
    def contacts(self) -> MossIndex[dict[str, Any]]:
        return self._indexes["contacts"]

    @property
    def interactions(self) -> MossIndex[dict[str, Any]]:
        return self._indexes["interactions"]

    @property
    def recommendations(self) -> MossIndex[dict[str, Any]]:
        return self._indexes["recommendations"]

    def index_for_kind(self, kind: str) -> MossIndex[dict[str, Any]]:
        mapping = defaultdict(
            lambda: self.user_profile,
            {
                "preference": self.preferences,
                "constraint": self.preferences,
                "decision": self.decisions,
                "rejection_reason": self.decisions,
                "journey": self.journeys,
                "profile": self.user_profile,
            },
        )
        return mapping[kind]
