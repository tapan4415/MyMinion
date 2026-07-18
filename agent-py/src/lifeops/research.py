import asyncio

import httpx

from lifeops.brightdata import BrightDataDocument, BrightDataError, BrightDataService
from lifeops.models import Journey, ResearchResult
from lifeops.moss import MossClient


class ResearchManager:
    def __init__(self, bright_data: BrightDataService, moss: MossClient) -> None:
        self._bright_data = bright_data
        self._moss = moss

    async def research_journey(
        self, user_id: str, journey: Journey, *, limit: int = 3
    ) -> list[ResearchResult]:
        query = f"{journey.goal} {journey.next_action}"
        if journey.kind.value == "shopping":
            query = (
                f"{journey.goal} buy price "
                "site:bestbuy.com OR site:amazon.com OR site:walmart.com OR site:target.com"
            )
        try:
            documents = await self._bright_data.search(query, limit=max(limit, 5))
        except (BrightDataError, httpx.HTTPError):
            documents = []
        results = [
            ResearchResult(
                source=doc.url,
                title=doc.title,
                summary=doc.text,
                confidence=0.55 if doc.metadata.get("mock") else 0.82,
                retrieved_at=doc.retrieved_at,
                raw=doc.metadata,
            )
            for doc in documents
        ]
        for result in results:
            await self._moss.research.save(
                {**result.model_dump(mode="json"), "user_id": user_id, "journey_id": journey.id}
            )
        return results

    async def research_topic(
        self, user_id: str, topic: str, *, limit: int = 3
    ) -> list[ResearchResult]:
        """Research a free-text topic (no Journey) and persist findings to Moss.

        Used by the always-on Scribe to enrich the knowledge base from conversation.
        Reuses the same Bright Data search + ResearchResult mapping as research_journey.
        """
        try:
            documents = await self._bright_data.search(topic, limit=max(limit, 5))
        except (BrightDataError, httpx.HTTPError):
            # The always-on Scribe must degrade gracefully: a slow/failed Bright Data
            # call still leaves the extracted memory saved to Moss.
            documents = []
        results = [
            ResearchResult(
                source=doc.url,
                title=doc.title,
                summary=doc.text,
                confidence=0.55 if doc.metadata.get("mock") else 0.82,
                retrieved_at=doc.retrieved_at,
                raw=doc.metadata,
            )
            for doc in documents
        ]
        for result in results:
            await self._moss.research.save(
                {**result.model_dump(mode="json"), "user_id": user_id, "topic": topic}
            )
        return results

    async def gather_person_sources(
        self, name: str, context: str = "", *, max_sources: int = 6
    ) -> list[BrightDataDocument]:
        """Collect public web results about a person (best-effort, never raises).

        Runs a few SERP queries concurrently (LinkedIn / Instagram / general) and
        returns de-duplicated documents. Used by the Scribe to enrich a detected person.
        """
        ctx = context.strip()
        queries = [
            f"{name} {ctx} linkedin".strip(),
            f"{name} {ctx} instagram".strip(),
            f"{name} {ctx}".strip(),
        ]

        async def _one(query: str) -> list[BrightDataDocument]:
            try:
                return await self._bright_data.search(query, limit=4)
            except (BrightDataError, httpx.HTTPError):
                return []

        groups = await asyncio.gather(*[_one(query) for query in queries])
        seen: set[str] = set()
        docs: list[BrightDataDocument] = []
        for group in groups:
            for doc in group:
                if doc.url and doc.url not in seen:
                    seen.add(doc.url)
                    docs.append(doc)
        return docs[:max_sources]
