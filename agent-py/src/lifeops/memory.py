from __future__ import annotations

import re
from datetime import UTC, datetime

from pydantic import ValidationError

from lifeops.models import MemoryCandidate, MemoryKind, MemoryRecord
from lifeops.moss import MossClient


class MemoryManager:
    """Selective long-term memory policy, deliberately separate from session state."""

    _patterns = (
        (
            MemoryKind.PREFERENCE,
            re.compile(r"\b(?:i prefer|i like|my preference is)\s+(.+)", re.I),
            True,
        ),
        (
            MemoryKind.PREFERENCE,
            re.compile(r"\b(?:i prioritize|most important is|with strong)\s+(.+)", re.I),
            True,
        ),
        (
            MemoryKind.CONSTRAINT,
            re.compile(
                r"\b(?:my budget is|i cannot|i can't|must be|need to stay under)\s+(.+)", re.I
            ),
            True,
        ),
        (
            MemoryKind.CONSTRAINT,
            re.compile(r"\bunder\s+(\$?\d[\d,]*(?:\.\d{1,2})?)", re.I),
            True,
        ),
        (
            MemoryKind.DECISION,
            re.compile(r"\b(?:i decided|i chose|let's go with|i booked)\s+(.+)", re.I),
            True,
        ),
        (
            MemoryKind.REJECTION_REASON,
            re.compile(r"\b(?:i rejected|i don't want|not that one because)\s+(.+)", re.I),
            False,
        ),
        (
            MemoryKind.PROFILE,
            re.compile(r"\b(?:i live in|i work as|my home is)\s+(.+)", re.I),
            True,
        ),
    )

    def __init__(self, moss: MossClient) -> None:
        self._moss = moss

    async def extract_candidate_memory(self, message: str) -> list[MemoryCandidate]:
        candidates: list[MemoryCandidate] = []
        for kind, pattern, stable in self._patterns:
            if match := pattern.search(message):
                candidates.append(
                    MemoryCandidate(
                        kind=kind,
                        content=match.group(1).strip().rstrip("."),
                        confidence=0.9,
                        stable=stable,
                        source_message=message,
                    )
                )
        return candidates

    def should_store(self, candidate: MemoryCandidate) -> bool:
        return (
            candidate.confidence >= 0.75
            and len(candidate.content) >= 3
            and candidate.kind in set(MemoryKind)
        )

    async def retrieve(self, user_id: str, query: str, *, limit: int = 10) -> list[MemoryRecord]:
        records: list[MemoryRecord] = []
        for index in (
            self._moss.user_profile,
            self._moss.preferences,
            self._moss.journeys,
            self._moss.decisions,
        ):
            documents = await index.search(query, limit=limit, filters={"user_id": user_id})
            for document in documents:
                try:
                    records.append(MemoryRecord.model_validate(document))
                except ValidationError:
                    # Journey state shares the semantic index but is not a memory record.
                    continue
        return records[:limit]

    async def save(self, user_id: str, candidate: MemoryCandidate) -> MemoryRecord:
        record = MemoryRecord(
            user_id=user_id,
            kind=candidate.kind,
            content=candidate.content,
            metadata={"confidence": candidate.confidence, "stable": candidate.stable},
        )
        await self._moss.index_for_kind(candidate.kind.value).save(record.model_dump(mode="json"))
        return record

    async def update(self, record: MemoryRecord, content: str) -> MemoryRecord:
        changes = {"content": content, "updated_at": datetime.now(UTC).isoformat()}
        updated = await self._moss.index_for_kind(record.kind.value).update(record.id, changes)
        return (
            MemoryRecord.model_validate(updated) if updated else record.model_copy(update=changes)
        )
