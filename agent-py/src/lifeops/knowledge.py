from __future__ import annotations

from abc import ABC, abstractmethod

from lifeops.models import ContactIntelligence, Journey, Recommendation, TripItinerary, UseCase
from lifeops.moss import MossClient


class AgentKnowledgeRepository(ABC):
    """Durable semantic outputs produced by specialist agent runs."""

    @abstractmethod
    async def save_journey(self, user_id: str, journey: Journey, use_case: UseCase) -> None: ...

    @abstractmethod
    async def save_recommendations(
        self,
        user_id: str,
        journey_id: str,
        use_case: UseCase,
        recommendations: list[Recommendation],
    ) -> None: ...

    @abstractmethod
    async def save_contact_summary(
        self, user_id: str, session_id: str, intelligence: ContactIntelligence
    ) -> None: ...

    @abstractmethod
    async def save_trip_itinerary(self, user_id: str, itinerary: TripItinerary) -> None: ...


class MossAgentKnowledgeRepository(AgentKnowledgeRepository):
    """Moss-backed semantic repository shared by all specialist agents."""

    def __init__(self, moss: MossClient) -> None:
        self._moss = moss

    async def save_journey(self, user_id: str, journey: Journey, use_case: UseCase) -> None:
        await self._moss.journeys.save(
            {
                **journey.model_dump(mode="json"),
                "user_id": user_id,
                "use_case": use_case.value,
            }
        )

    async def save_recommendations(
        self,
        user_id: str,
        journey_id: str,
        use_case: UseCase,
        recommendations: list[Recommendation],
    ) -> None:
        for recommendation in recommendations:
            await self._moss.recommendations.save(
                {
                    **recommendation.model_dump(mode="json"),
                    "user_id": user_id,
                    "journey_id": journey_id,
                    "use_case": use_case.value,
                }
            )

    async def save_contact_summary(
        self, user_id: str, session_id: str, intelligence: ContactIntelligence
    ) -> None:
        document = {
            "user_id": user_id,
            "session_id": session_id,
            **intelligence.model_dump(mode="json"),
        }
        await self._moss.interactions.save(document)
        if intelligence.name or intelligence.email or intelligence.public_profile_url:
            await self._moss.contacts.save(document)

    async def save_trip_itinerary(self, user_id: str, itinerary: TripItinerary) -> None:
        await self._moss.trip_itineraries.save(
            {**itinerary.model_dump(mode="json"), "user_id": user_id}
        )
