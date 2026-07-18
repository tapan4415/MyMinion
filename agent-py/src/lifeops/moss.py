from __future__ import annotations

import asyncio
import json
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


class MossCloudIndex(MossIndex[dict[str, Any]]):
    """Repository adapter backed by one Moss cloud semantic index."""

    def __init__(
        self, client: Any, name: str, remote_name: str, loaded_indexes: set[str] | None = None
    ) -> None:
        self._client = client
        self.name = name
        self.remote_name = remote_name
        self._loaded_indexes = loaded_indexes if loaded_indexes is not None else set()

    async def save(self, document: dict[str, Any]) -> dict[str, Any]:
        from moss import DocumentInfo, MutationOptions

        stored = deepcopy(document)
        stored.setdefault("id", uuid4().hex)
        stored["_moss_index"] = self.name
        await self._client.add_docs(
            self.remote_name,
            [
                DocumentInfo(
                    id=str(stored["id"]),
                    text=self._searchable_text(stored),
                    metadata=self._metadata(stored),
                    payload=json.dumps(stored, sort_keys=True, default=str),
                )
            ],
            MutationOptions(upsert=True),
        )
        self._loaded_indexes.discard(self.remote_name)
        return stored

    async def search(
        self,
        query: str,
        *,
        limit: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        from moss import QueryOptions

        if self.remote_name not in self._loaded_indexes:
            await self._client.load_index(self.remote_name)
            self._loaded_indexes.add(self.remote_name)
        result = None
        for attempt in range(3):
            try:
                result = await self._client.query(
                    self.remote_name,
                    query or "*",
                    QueryOptions(top_k=max(limit * 3, limit)),
                )
                break
            except Exception:
                if attempt == 2:
                    raise
                await asyncio.sleep(0.5 * (2**attempt))
        if result is None:
            return []
        matches: list[dict[str, Any]] = []
        for doc in result.docs:
            payload = self._payload(doc.payload)
            if payload.get("_system_seed"):
                continue
            if payload.get("_moss_index") != self.name:
                continue
            if filters and any(payload.get(key) != value for key, value in filters.items()):
                continue
            matches.append(deepcopy(payload))
        return matches[:limit]

    async def update(self, document_id: str, changes: dict[str, Any]) -> dict[str, Any] | None:
        from moss import GetDocumentsOptions

        docs = await self._client.get_docs(
            self.remote_name, GetDocumentsOptions(doc_ids=[document_id])
        )
        if not docs:
            return None
        payload = self._payload(docs[0].payload)
        return await self.save({**payload, **changes, "id": document_id})

    async def delete(self, document_id: str) -> bool:
        await self._client.delete_docs(self.remote_name, [document_id])
        self._loaded_indexes.discard(self.remote_name)
        return True

    @staticmethod
    def _searchable_text(document: dict[str, Any]) -> str:
        preferred = [
            document.get("content"),
            document.get("goal"),
            document.get("title"),
            document.get("summary"),
            document.get("name"),
            document.get("company"),
        ]
        text = " ".join(str(value) for value in preferred if value)
        return text or json.dumps(document, sort_keys=True, default=str)

    @staticmethod
    def _metadata(document: dict[str, Any]) -> dict[str, str]:
        keys = (
            "user_id",
            "kind",
            "use_case",
            "journey_id",
            "session_id",
            "_moss_index",
        )
        return {key: str(document[key]) for key in keys if document.get(key) is not None}

    @staticmethod
    def _payload(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                return {}
        return {}


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
        "trip_itineraries",
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

    @property
    def trip_itineraries(self) -> MossIndex[dict[str, Any]]:
        return self._indexes["trip_itineraries"]

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


def create_cloud_moss_client(
    project_id: str,
    project_key: str,
    *,
    remote_name: str = "myminion-memory",
) -> MossClient:
    """Create a live Moss registry without performing network I/O."""
    from moss import MossClient as SDKMossClient

    sdk = SDKMossClient(project_id, project_key)
    loaded_indexes: set[str] = set()
    indexes = {
        name: MossCloudIndex(sdk, name, remote_name, loaded_indexes)
        for name in MossClient.INDEX_NAMES
    }
    return MossClient(indexes)


async def ensure_cloud_moss_indexes(
    project_id: str, project_key: str, *, remote_name: str = "myminion-memory"
) -> list[str]:
    """Idempotently initialize MyMinion's consolidated cloud memory index."""
    from moss import DocumentInfo
    from moss import MossClient as SDKMossClient

    sdk = SDKMossClient(project_id, project_key)
    existing = {info.name for info in await sdk.list_indexes()}
    if remote_name in existing:
        return []
    await sdk.create_index(
        remote_name,
        [
            DocumentInfo(
                id="__myminion_system_seed__",
                text="MyMinion semantic memory index",
                metadata={"record_type": "system_seed"},
                payload=json.dumps({"id": "__myminion_system_seed__", "_system_seed": True}),
            )
        ],
        model_id="moss-minilm",
    )
    return [remote_name]
