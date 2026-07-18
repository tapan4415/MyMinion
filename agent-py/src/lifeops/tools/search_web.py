from lifeops.brightdata import BrightDataService
from lifeops.models import ResearchResult


async def search_web(
    query: str, service: BrightDataService, *, limit: int = 5
) -> list[ResearchResult]:
    documents = await service.search(query, limit=limit)
    return [
        ResearchResult(
            source=item.url,
            title=item.title,
            summary=item.text,
            confidence=0.55,
            retrieved_at=item.retrieved_at,
            raw=item.metadata,
        )
        for item in documents
    ]
