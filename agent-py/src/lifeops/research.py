from lifeops.brightdata import BrightDataError, BrightDataService
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
        except BrightDataError:
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
