from __future__ import annotations

import re
from urllib.parse import urlparse

import httpx

from lifeops.buywise import BuywiseClient
from lifeops.models import Journey, MemoryRecord, Recommendation, ResearchResult


class BuyingAdvisor:
    """Turns researched evidence into explainable, non-sponsored recommendations."""

    def __init__(self, buywise: BuywiseClient | None = None) -> None:
        self._buywise = buywise

    ALLOWED_RETAILERS = {
        "apple.com": "Apple",
        "amazon.com": "Amazon",
        "bestbuy.com": "Best Buy",
        "walmart.com": "Walmart",
        "target.com": "Target",
    }
    REQUIRED_RETAILERS = {"Amazon", "Walmart", "Best Buy", "Target"}

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
                offers = [
                    offer
                    for offer in (result.get("offers") or [])
                    if self._valid_offer(offer)
                ]
                recommendations = [
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
                covered = {
                    str(item.attributes.get("retailer")) for item in recommendations
                }
                if recommendations and self.REQUIRED_RETAILERS.issubset(covered):
                    return recommendations
            except (httpx.HTTPError, RuntimeError, ValueError):
                pass

        budget = self._budget(memories or [])
        minimum_price = self._minimum_product_price(journey.goal)
        best_by_retailer: dict[str, tuple[float, ResearchResult]] = {}
        for item in evidence:
            price = self._price(item.raw.get("price") or item.raw.get("serp_text") or item.summary)
            retailer = self._retailer(item.source)
            verified = item.raw.get("verified_product_page") is True
            if price is None or retailer is None or not verified:
                continue
            if price < minimum_price:
                continue
            if budget is not None and price > budget:
                continue
            current = best_by_retailer.get(retailer)
            if current is None or price < current[0]:
                best_by_retailer[retailer] = (price, item)
        priced = [
            (price, retailer, item)
            for retailer, (price, item) in best_by_retailer.items()
        ]
        priced.sort(key=lambda row: row[0])
        if not priced:
            return []
        lowest = priced[0][0]
        highest = max(row[0] for row in priced)
        spread = max(highest - lowest, 1)
        return [
                Recommendation(
                    title=item.raw.get("serp_title") or item.title,
                    rationale=(
                        f"Verified on {retailer}. Ranked using the live price and the user's "
                        "recalled Moss constraints."
                    ),
                    score=round(0.95 - ((price - lowest) / spread) * 0.15, 2),
                    tradeoffs=["Price and stock can change after the recorded retrieval time"],
                    evidence_ids=[item.id],
                    attributes={
                        "rank": index + 1,
                        "provider": "bright_data",
                        "research_source": "bright_data_serp_then_browser_verify",
                        "retailer": retailer,
                        "price": price,
                        "currency": "USD",
                        "url": item.source,
                        "availability": "Verified product page",
                        "match": "priced_offer",
                        "condition": "new",
                    },
                )
                for index, (price, retailer, item) in enumerate(priced[:5])
            ]

    @classmethod
    def _retailer(cls, url: str) -> str | None:
        host = (urlparse(url).hostname or "").lower().removeprefix("www.")
        for domain, retailer in cls.ALLOWED_RETAILERS.items():
            if host == domain or host.endswith(f".{domain}"):
                return retailer
        return None

    @classmethod
    def _valid_offer(cls, offer: dict) -> bool:
        price = offer.get("total")
        retailer = cls._retailer(str(offer.get("url") or ""))
        return isinstance(price, (int, float)) and price > 0 and retailer is not None

    @staticmethod
    def _price(value: object) -> float | None:
        if isinstance(value, (int, float)):
            return float(value) if value > 0 else None
        match = re.search(r"\$\s*([0-9][0-9,]*(?:\.\d{1,2})?)", str(value))
        return float(match.group(1).replace(",", "")) if match else None

    @staticmethod
    def _budget(memories: list[MemoryRecord]) -> float | None:
        for memory in memories:
            if memory.kind.value != "constraint":
                continue
            match = re.search(r"\$\s*([0-9][0-9,]*(?:\.\d{1,2})?)", memory.content)
            if match:
                return float(match.group(1).replace(",", ""))
        return None

    @staticmethod
    def _minimum_product_price(goal: str) -> float:
        # Reject accessory, installment, and navigation-filter values masquerading as
        # full-product prices. Expand this catalog as specialist schemas are added.
        if "airpods" in goal.lower():
            return 40.0
        return 1.0
