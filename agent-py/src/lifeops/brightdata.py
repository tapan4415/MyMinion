from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class BrightDataDocument(BaseModel):
    url: str
    title: str
    text: str
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class BrightDataService(ABC):
    @abstractmethod
    async def search(self, query: str, *, limit: int = 5) -> list[BrightDataDocument]: ...

    @abstractmethod
    async def extract(self, url: str) -> BrightDataDocument: ...

    @abstractmethod
    async def crawl(self, url: str, *, max_pages: int = 10) -> list[BrightDataDocument]: ...


class MockBrightDataService(BrightDataService):
    """Deterministic development adapter; performs no network calls."""

    async def search(self, query: str, *, limit: int = 5) -> list[BrightDataDocument]:
        topics = ["official requirements", "local providers", "cost comparison"]
        return [
            BrightDataDocument(
                url=f"https://example.com/research/{index + 1}",
                title=f"{topic.title()} for {query}",
                text=(
                    f"Mock research result covering {topic} related to {query}. "
                    "Verify with a live Bright Data adapter before acting."
                ),
                metadata={"mock": True, "query": query},
            )
            for index, topic in enumerate(topics[:limit])
        ]

    async def extract(self, url: str) -> BrightDataDocument:
        return BrightDataDocument(
            url=url,
            title="Extracted page",
            text=f"Mock extraction for {url}.",
            metadata={"mock": True},
        )

    async def crawl(self, url: str, *, max_pages: int = 10) -> list[BrightDataDocument]:
        return [
            await self.extract(f"{url.rstrip('/')}/page-{index + 1}")
            for index in range(min(max_pages, 3))
        ]
