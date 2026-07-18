from __future__ import annotations

import json
from typing import Any

import httpx


class BuywiseClient:
    """Adapter for the Buywise streaming investigation agent."""

    def __init__(self, base_url: str, *, timeout_seconds: float = 120) -> None:
        self._url = f"{base_url.rstrip('/')}/api/investigate"
        self._timeout = timeout_seconds

    async def investigate(self, query: str, candidate_urls: list[str]) -> dict[str, Any]:
        payload = {
            "query": query,
            "candidateUrls": list(dict.fromkeys(candidate_urls))[:20],
            "visibleOffers": [],
            "preferences": {
                "priority": "best_overall",
                "condition": "new",
                "country": "US",
            },
        }
        result: dict[str, Any] | None = None
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            async with client.stream("POST", self._url, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    event = json.loads(line)
                    if event.get("type") == "error":
                        raise RuntimeError(str(event.get("message") or "Buywise failed"))
                    if event.get("type") == "complete":
                        result = event.get("result")
        if not result:
            raise RuntimeError("Buywise completed without a result")
        return result
