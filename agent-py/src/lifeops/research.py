import asyncio
import re
from urllib.parse import urlparse

from lifeops.brightdata import BrightDataError, BrightDataService
from lifeops.models import Journey, ResearchResult
from lifeops.moss import MossClient


class ResearchManager:
    SHOPPING_RETAILERS = {
        "apple.com": "Apple",
        "amazon.com": "Amazon",
        "bestbuy.com": "Best Buy",
        "walmart.com": "Walmart",
        "target.com": "Target",
    }

    def __init__(self, bright_data: BrightDataService, moss: MossClient) -> None:
        self._bright_data = bright_data
        self._moss = moss

    async def research_journey(
        self, user_id: str, journey: Journey, *, limit: int = 5
    ) -> list[ResearchResult]:
        queries = [f"{journey.goal} {journey.next_action}"]
        if journey.kind.value == "shopping":
            product = self._shopping_terms(journey.goal)
            queries = [
                f'"{product}" price site:{domain}'
                for domain in self.SHOPPING_RETAILERS
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
            retailer_matches = 0
            ordered = sorted(
                batch, key=lambda item: self._product_url_score(item.url), reverse=True
            )
            for document in ordered:
                if not document.url or document.url in seen:
                    continue
                if journey.kind.value == "shopping" and not self._retailer(document.url):
                    continue
                if journey.kind.value == "shopping" and not self._matches_product(
                    journey.goal, document.title, document.text, document.url
                ):
                    continue
                seen.add(document.url)
                documents.append(document)
                retailer_matches += 1
                if retailer_matches >= 2 or len(documents) >= 10:
                    break

        if journey.kind.value == "shopping":
            async def verify(document):
                try:
                    extracted = await self._bright_data.extract(document.url)
                    extracted.metadata = {
                        **document.metadata,
                        **extracted.metadata,
                        "serp_title": document.title,
                        "serp_text": document.text,
                        "retailer": self._retailer(document.url),
                        "verified_product_page": bool(
                            extracted.metadata.get("verified_product_page")
                        ),
                    }
                    return extracted
                except BrightDataError:
                    return None

            verified = await asyncio.gather(*(verify(document) for document in documents))
            documents = [document for document in verified if document is not None]
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

    @classmethod
    def _retailer(cls, url: str) -> str | None:
        host = urlparse(url).hostname or ""
        host = host.lower().removeprefix("www.")
        for domain, retailer in cls.SHOPPING_RETAILERS.items():
            if host == domain or host.endswith(f".{domain}"):
                return retailer
        return None

    @staticmethod
    def _matches_product(goal: str, *values: str) -> bool:
        stopwords = {
            "best",
            "current",
            "offers",
            "offer",
            "find",
            "only",
            "saved",
            "budget",
            "price",
            "under",
            "apple",
        }
        tokens = {
            token
            for token in re.findall(r"[a-z0-9]+", goal.lower())
            if len(token) >= 4 and token not in stopwords
        }
        haystack = " ".join(values).lower()
        return not tokens or any(token in haystack for token in tokens)

    @staticmethod
    def _shopping_terms(goal: str) -> str:
        phrase = re.split(
            r"\b(?:under|within|only use|considering|based on|for me)\b",
            goal,
            maxsplit=1,
            flags=re.I,
        )[0]
        phrase = re.sub(
            r"\b(?:find|show|get|the|best|current|offers?|deals?|prices?|for)\b",
            " ",
            phrase,
            flags=re.I,
        )
        return " ".join(phrase.split()) or goal

    @staticmethod
    def _product_url_score(url: str) -> int:
        lowered = url.lower()
        product_markers = ("/dp/", "/ip/", "/product/", "/p/", "/shop/buy-")
        category_markers = ("/browse/", "/search", "/s?", "/c/")
        if any(marker in lowered for marker in product_markers):
            return 2
        if any(marker in lowered for marker in category_markers):
            return 0
        return 1
