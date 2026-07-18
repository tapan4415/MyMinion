from __future__ import annotations

import asyncio

from lifeops.brightdata import BrightDataService
from lifeops.models import (
    Journey,
    ResearchResult,
    TripAccommodationType,
    TripSlots,
    TripTransportMode,
)
from lifeops.moss import MossClient

_MAX_CONCURRENT_SEARCHES = 3


class TripResearchService:
    """Issues Bright Data queries targeted at the confirmed trip slots."""

    def __init__(self, bright_data: BrightDataService, moss: MossClient) -> None:
        self._bright_data = bright_data
        self._moss = moss

    def _queries(self, slots: TripSlots) -> list[tuple[str, str]]:
        destination = slots.destination or "the destination"
        travelers = slots.travelers or 2

        origin = slots.origin
        if slots.transport_mode == TripTransportMode.FLIGHT:
            transport_query = f"flights from {origin or 'nearest major airport'} to {destination}"
        elif slots.transport_mode == TripTransportMode.ROAD:
            transport_query = f"driving route from {origin or 'nearby cities'} to {destination}"
        else:
            transport_query = f"flights and driving routes to {destination}"

        accommodation = (
            "hotels"
            if slots.accommodation_type == TripAccommodationType.HOTEL
            else "airbnb"
            if slots.accommodation_type == TripAccommodationType.AIRBNB
            else "hotels and airbnb options"
        )
        lodging_query = f"{destination} {accommodation} for {travelers} travelers"

        food_terms = ", ".join(slots.food_preferences) or "popular local food"
        food_query = f"{destination} restaurants {food_terms}"

        pace_terms = ", ".join(slots.pace_preferences) or "balanced"
        activities_query = f"{destination} {pace_terms} activities"

        requirements_query = f"{destination} entry requirements"

        return [
            ("transport", transport_query),
            ("lodging", lodging_query),
            ("food", food_query),
            ("activities", activities_query),
            ("requirements", requirements_query),
        ]

    async def _search_category(
        self,
        user_id: str,
        journey: Journey,
        category: str,
        query: str,
        semaphore: asyncio.Semaphore,
    ) -> list[ResearchResult]:
        async with semaphore:
            documents = await self._bright_data.search(query, limit=3)
        results = [
            ResearchResult(
                source=doc.url,
                title=doc.title,
                summary=doc.text,
                confidence=0.55 if doc.metadata.get("mock") else 0.82,
                retrieved_at=doc.retrieved_at,
                raw={**doc.metadata, "category": category},
            )
            for doc in documents
        ]
        await asyncio.gather(
            *(
                self._moss.research.save(
                    {
                        **result.model_dump(mode="json"),
                        "user_id": user_id,
                        "journey_id": journey.id,
                        "category": category,
                    }
                )
                for result in results
            )
        )
        return results

    async def research(
        self, user_id: str, journey: Journey, slots: TripSlots
    ) -> list[ResearchResult]:
        # Each category is an independent Bright Data call - the live browser-automation
        # path can take 10-20s per call, so running all 5 sequentially was the dominant
        # source of latency. A small semaphore keeps this from overwhelming the remote
        # scraping browser's concurrent-session limit.
        semaphore = asyncio.Semaphore(_MAX_CONCURRENT_SEARCHES)
        per_category = await asyncio.gather(
            *(
                self._search_category(user_id, journey, category, query, semaphore)
                for category, query in self._queries(slots)
            )
        )
        return [result for results in per_category for result in results]
