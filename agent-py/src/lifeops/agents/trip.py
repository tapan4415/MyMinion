from __future__ import annotations

from lifeops.models import Journey, Recommendation, ResearchResult


class TripPlannerAgent:
    """Builds an itinerary strategy while keeping bookable facts tied to evidence."""

    async def recommend(
        self, journey: Journey, evidence: list[ResearchResult]
    ) -> list[Recommendation]:
        return [
            Recommendation(
                title="Balanced itinerary",
                rationale=(
                    "Uses a hub-based route with recovery time and defers booking until dates, "
                    "budget, and departure airport are confirmed."
                ),
                score=0.9,
                tradeoffs=["Fewer destinations", "Lower transfer overhead"],
                evidence_ids=[item.id for item in evidence],
                attributes={"pace": "balanced", "booking_status": "not_booked"},
            )
        ]
