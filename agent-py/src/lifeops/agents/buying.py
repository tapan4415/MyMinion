from __future__ import annotations

import httpx

from lifeops.buywise import BuywiseClient
from lifeops.models import Journey, MemoryRecord, Recommendation, ResearchResult


class BuyingAdvisor:
    """Turns researched evidence into explainable, non-sponsored recommendations."""

    def __init__(self, buywise: BuywiseClient | None = None) -> None:
        self._buywise = buywise

    async def recommend(
        self,
        journey: Journey,
        evidence: list[ResearchResult],
        memories: list[MemoryRecord] | None = None,
    ) -> list[Recommendation]:
        if self._buywise:
            try:
                memory_context = "; ".join(memory.content for memory in (memories or [])[:8])
                query = journey.goal
                if memory_context:
                    query = f"{query}. Personalize using recalled preferences: {memory_context}"
                result = await self._buywise.investigate(
                    query,
                    [item.source for item in evidence if item.source.startswith("http")],
                )
                offers = result.get("offers") or []
                return [
                    Recommendation(
                        title=str(offer.get("title") or offer.get("retailer") or "Option"),
                        rationale=str(
                            result.get("recommendation", {}).get("reasoning")
                            or "Ranked by Buywise"
                        ),
                        score=min(
                            1, float(offer.get("scores", {}).get("overall", 0)) / 100
                        ),
                        tradeoffs=[str(item) for item in offer.get("warnings", [])],
                        evidence_ids=[item.id for item in evidence],
                        attributes={
                            "rank": index + 1,
                            "provider": "buywise",
                            "research_source": "bright_data_browser_api",
                            "retailer": offer.get("retailer"),
                            "price": offer.get("total"),
                            "currency": offer.get("currency"),
                            "url": offer.get("url"),
                            "availability": offer.get("availability"),
                            "delivery": offer.get("delivery"),
                            "return_days": offer.get("returnDays"),
                            "warranty": offer.get("warranty"),
                            "match": offer.get("match"),
                            "condition": offer.get("condition"),
                            "seller_type": offer.get("sellerType"),
                            "evidence": offer.get("evidence", []),
                            "coverage": result.get("coverage"),
                            "activities": result.get("activities", []),
                            "customer_themes": result.get("customerThemes", []),
                            "buying_checklist": result.get("buyingChecklist", []),
                            "search_mode": result.get("mode"),
                            "shopping_mode": result.get("shoppingMode"),
                            "recommendation_confidence": result.get(
                                "recommendation", {}
                            ).get("confidence"),
                            "recommendation_headline": result.get(
                                "recommendation", {}
                            ).get("headline"),
                        },
                    )
                    for index, offer in enumerate(offers[:5])
                ]
            except (httpx.HTTPError, RuntimeError, ValueError):
                pass
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
