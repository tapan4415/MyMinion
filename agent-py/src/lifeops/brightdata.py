from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

import httpx
from pydantic import BaseModel, Field


class BrightDataDocument(BaseModel):
    url: str
    title: str
    text: str
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class BrightDataService(ABC):
    @abstractmethod
    async def search(self, query: str, *, limit: int = 5) -> list[BrightDataDocument]: ...

    @abstractmethod
    async def extract(self, url: str) -> BrightDataDocument: ...

    @abstractmethod
    async def crawl(self, url: str, *, max_pages: int = 10) -> list[BrightDataDocument]: ...


class MockBrightDataService(BrightDataService):
    """Deterministic development adapter; performs no network calls."""

    async def search(self, query: str, *, limit: int = 5) -> list[BrightDataDocument]:
        topics = ["official requirements", "local providers", "cost comparison"]
        return [
            BrightDataDocument(
                url=f"https://example.com/research/{index + 1}",
                title=f"{topic.title()} for {query}",
                text=(
                    f"Mock research result covering {topic} related to {query}. "
                    "Verify with a live Bright Data adapter before acting."
                ),
                metadata={"mock": True, "query": query},
            )
            for index, topic in enumerate(topics[:limit])
        ]

    async def extract(self, url: str) -> BrightDataDocument:
        return BrightDataDocument(
            url=url,
            title="Extracted page",
            text=f"Mock extraction for {url}.",
            metadata={"mock": True},
        )

    async def crawl(self, url: str, *, max_pages: int = 10) -> list[BrightDataDocument]:
        return [
            await self.extract(f"{url.rstrip('/')}/page-{index + 1}")
            for index in range(min(max_pages, 3))
        ]


class BrightDataError(RuntimeError):
    """Safe provider error that never includes credentials."""


class LiveBrightDataService(BrightDataService):
    """Bright Data Direct API adapter for live SERP and Web Unlocker research."""

    endpoint = "https://api.brightdata.com/request"

    def __init__(
        self,
        api_key: str,
        *,
        serp_zone: str | None,
        unlocker_zone: str | None,
        browser_ws: str | None = None,
        timeout_seconds: float = 30,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("A Bright Data API key is required")
        self._api_key = api_key
        self._serp_zone = serp_zone
        self._unlocker_zone = unlocker_zone
        self._browser_ws = browser_ws
        self._client = httpx.AsyncClient(
            timeout=timeout_seconds,
            transport=transport,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

    async def search(self, query: str, *, limit: int = 5) -> list[BrightDataDocument]:
        if not self._serp_zone and self._browser_ws:
            return await self._search_with_browser(query, limit=limit)
        if not self._serp_zone:
            raise BrightDataError(
                "BRIGHT_DATA_SERP_ZONE or BRIGHT_DATA_BROWSER_WS is required for live search"
            )
        params = {"q": query, "hl": "en", "gl": "us", "brd_json": "1"}
        if "price" in query.lower() or "buy" in query.lower():
            params["tbm"] = "shop"
        target = "https://www.google.com/search?" + urlencode(params)
        try:
            payload = await self._request(
                {"zone": self._serp_zone, "url": target, "format": "json", "method": "GET"}
            )
        except BrightDataError:
            if self._browser_ws:
                return await self._search_with_browser(query, limit=limit)
            raise
        rows = payload.get("shopping") or payload.get("organic") or []
        return [
            BrightDataDocument(
                url=str(row.get("link") or ""),
                title=str(row.get("title") or query),
                text=str(row.get("description") or row.get("price") or ""),
                metadata={
                    "provider": "bright_data",
                    "source": row.get("source"),
                    "price": self._normalized_price(row.get("price")),
                    "delivery": row.get("delivery"),
                    "query": query,
                },
            )
            for row in rows
            if row.get("link")
        ][:limit]

    @staticmethod
    def _normalized_price(value: Any) -> Any:
        if isinstance(value, dict):
            return value.get("value") or value.get("price") or value.get("display")
        return value

    async def _search_with_browser(self, query: str, *, limit: int) -> list[BrightDataDocument]:
        try:
            from playwright.async_api import async_playwright
        except ImportError as error:
            raise BrightDataError(
                "Install the 'brightdata' extra to enable Browser API search"
            ) from error
        target = "https://www.google.com/search?" + urlencode({"q": query, "hl": "en", "gl": "us"})
        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.connect_over_cdp(self._browser_ws)
                context = browser.contexts[0] if browser.contexts else await browser.new_context()
                page = await context.new_page()
                await page.goto(target, wait_until="domcontentloaded", timeout=60_000)
                rows = []
                for attempt in range(3):
                    try:
                        await page.wait_for_load_state("domcontentloaded", timeout=15_000)
                        await page.wait_for_timeout(750)
                        rows = await page.locator("a:has(h3)").evaluate_all(
                            """links => links.map(link => ({
                                title: link.innerText,
                                url: link.href,
                                summary: link.parentElement?.parentElement?.innerText || ''
                            }))"""
                        )
                        break
                    except Exception:
                        if attempt == 2:
                            raise
                        await page.wait_for_timeout(1_000)
                await page.close()
                await browser.close()
            results: list[BrightDataDocument] = []
            seen: set[str] = set()
            for row in rows:
                url = str(row.get("url") or "")
                if not url.startswith("http") or "google.com" in url or url in seen:
                    continue
                seen.add(url)
                results.append(
                    BrightDataDocument(
                        url=url,
                        title=str(row.get("title") or query),
                        text=str(row.get("summary") or ""),
                        metadata={
                            "provider": "bright_data",
                            "zone": "browser_api",
                            "query": query,
                        },
                    )
                )
                if len(results) >= limit:
                    break
            return results
        except Exception as error:
            detail = str(error)
            if self._browser_ws:
                detail = detail.replace(self._browser_ws, "[redacted]")
            raise BrightDataError(f"Bright Data Browser API failed: {detail[:300]}") from error

    async def extract(self, url: str) -> BrightDataDocument:
        if not self._unlocker_zone and self._browser_ws:
            return await self._extract_with_browser(url)
        if not self._unlocker_zone:
            raise BrightDataError(
                "BRIGHT_DATA_UNLOCKER_ZONE or BRIGHT_DATA_BROWSER_WS is required for extraction"
            )
        payload = await self._request(
            {
                "zone": self._unlocker_zone,
                "url": url,
                "format": "raw",
                "method": "GET",
                "data_format": "markdown",
            },
            expect_json=False,
        )
        text = payload if isinstance(payload, str) else str(payload)
        title = next(
            (
                line.removeprefix("# ").strip()
                for line in text.splitlines()
                if line.startswith("# ")
            ),
            url,
        )
        return BrightDataDocument(
            url=url,
            title=title,
            text=text,
            metadata={"provider": "bright_data", "zone": self._unlocker_zone},
        )

    async def _extract_with_browser(self, url: str) -> BrightDataDocument:
        try:
            from playwright.async_api import async_playwright
        except ImportError as error:
            raise BrightDataError(
                "Install the 'brightdata' extra to enable Browser API extraction"
            ) from error
        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.connect_over_cdp(self._browser_ws)
                context = browser.contexts[0] if browser.contexts else await browser.new_context()
                page = await context.new_page()
                await page.goto(url, wait_until="commit", timeout=60_000)
                await page.wait_for_timeout(2_000)
                title = await page.title()
                text = await page.locator("body").inner_text(timeout=30_000)
                price_candidates = await page.locator(
                    '[itemprop="price"], meta[property="product:price:amount"]'
                ).evaluate_all(
                    """elements => elements.map(element =>
                        element.getAttribute('content') || element.textContent || '')"""
                )
                json_ld = await page.locator(
                    'script[type="application/ld+json"]'
                ).all_text_contents()
                await page.close()
                await browser.close()
            commerce_signals = (
                "add to cart",
                "buy now",
                "in stock",
                "shipping",
                "pickup",
            )
            has_offer_controls = len(text) >= 500 and any(
                signal in text.lower() for signal in commerce_signals
            )
            price = (
                self._page_price(price_candidates, json_ld, text)
                if has_offer_controls
                else None
            )
            return BrightDataDocument(
                url=url,
                title=title or url,
                text=text,
                metadata={
                    "provider": "bright_data",
                    "zone": "browser_api",
                    "price": price,
                    "verified_product_page": bool(price and has_offer_controls),
                },
            )
        except Exception as error:
            detail = str(error)
            if self._browser_ws:
                detail = detail.replace(self._browser_ws, "[redacted]")
            raise BrightDataError(f"Bright Data Browser API failed: {detail[:300]}") from error

    @classmethod
    def _page_price(
        cls, candidates: list[str], json_ld_documents: list[str], text: str
    ) -> str | None:
        for candidate in candidates:
            normalized = cls._price_string(candidate)
            if normalized:
                return normalized
        for raw in json_ld_documents:
            try:
                parsed = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                continue
            for value in cls._walk_prices(parsed):
                normalized = cls._price_string(value)
                if normalized:
                    return normalized
        match = re.search(r"\$\s*([0-9][0-9,]*(?:\.\d{1,2})?)", text)
        if not match:
            return None
        price = float(match.group(1).replace(",", ""))
        return f"${price:.2f}" if price > 0 else None

    @classmethod
    def _walk_prices(cls, value: Any) -> list[Any]:
        prices: list[Any] = []
        if isinstance(value, dict):
            for key, child in value.items():
                if key.lower() in {"price", "lowprice"}:
                    prices.append(child)
                else:
                    prices.extend(cls._walk_prices(child))
        elif isinstance(value, list):
            for child in value:
                prices.extend(cls._walk_prices(child))
        return prices

    @staticmethod
    def _price_string(value: Any) -> str | None:
        match = re.search(r"\$?\s*([0-9][0-9,]*(?:\.\d{1,2})?)", str(value))
        if not match:
            return None
        price = float(match.group(1).replace(",", ""))
        return f"${price:.2f}" if price > 0 else None

    async def crawl(self, url: str, *, max_pages: int = 10) -> list[BrightDataDocument]:
        # The generic interface returns documents synchronously. Production domain crawls
        # should use Bright Data Crawl API jobs and persist their snapshot IDs in the queue.
        return [await self.extract(url)] if max_pages > 0 else []

    async def _request(
        self, body: dict[str, Any], *, expect_json: bool = True
    ) -> dict[str, Any] | str:
        response = await self._client.post(self.endpoint, json=body)
        if response.status_code >= 400:
            detail = response.text[:300].replace(self._api_key, "[redacted]")
            raise BrightDataError(f"Bright Data returned {response.status_code}: {detail}")
        if not expect_json:
            return response.text
        try:
            payload = response.json()
        except ValueError as error:
            raise BrightDataError("Bright Data returned invalid JSON") from error
        if not isinstance(payload, dict):
            raise BrightDataError("Bright Data returned an unexpected response shape")
        return payload

    async def close(self) -> None:
        await self._client.aclose()
