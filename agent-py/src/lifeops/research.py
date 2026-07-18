import asyncio

from lifeops.brightdata import BrightDataError, BrightDataService
from lifeops.models import Journey, ResearchResult
from lifeops.moss import MossClient


class ResearchManager:
    def __init__(self, bright_data: BrightDataService, moss: MossClient) -> None:
        self._bright_data = bright_data
        self._moss = moss

    async def research_journey(
        self, user_id: str, journey: Journey, *, limit: int = 5
    ) -> list[ResearchResult]:
        queries = [f"{journey.goal} {journey.next_action}"]
        if journey.kind.value == "shopping":
            queries = [
                f"{journey.goal} buy price deals availability",
                f"{journey.goal} official specifications model comparison",
                f"{journey.goal} retailer price Amazon Best Buy Walmart Target Costco B&H",
            ]

        async def search(query: str):
            try:
                return await self._bright_data.search(query, limit=max(limit, 6))
            except BrightDataError:
                return []

        batches = await asyncio.gather(*(search(query) for query in queries))
        documents = []
        seen: set[str] = set()
        for batch in batches:
            for document in batch:
                if not document.url or document.url in seen:
                    continue
                seen.add(document.url)
                documents.append(document)
                if len(documents) >= 18:
                    break
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
