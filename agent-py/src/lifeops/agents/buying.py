from __future__ import annotations

from lifeops.models import Journey, Recommendation, ResearchResult


class BuyingAdvisor:
    """Turns researched evidence into explainable, non-sponsored recommendations."""

    async def recommend(
        self, journey: Journey, evidence: list[ResearchResult]
    ) -> list[Recommendation]:
        labels = ("Best overall match", "Best value", "Best low-risk choice")
        recommendations: list[Recommendation] = []
        for index, label in enumerate(labels):
            related = evidence[index : index + 1] or evidence[:1]
            recommendations.append(
                Recommendation(
                    title=label,
                    rationale=(
                        f"Matches the stated goal: {journey.goal}. This scaffold ranks fit, "
                        "total cost, reliability, and return flexibility."
                    ),
                    score=round(0.88 - index * 0.07, 2),
                    tradeoffs=[
                        "Live pricing and availability must be refreshed before purchase",
                        "Final fit depends on unresolved constraints",
                    ],
                    evidence_ids=[item.id for item in related],
                    attributes={"rank": index + 1, "mock": True},
                )
            )
        return recommendations
