import json

import httpx
import pytest

from lifeops.brightdata import BrightDataError, LiveBrightDataService


@pytest.mark.asyncio
async def test_live_search_parses_bright_data_serp_response() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"].startswith("Bearer ")
        body = json.loads(request.content)
        assert body["zone"] == "serp-test"
        return httpx.Response(
            200,
            json={
                "shopping": [
                    {
                        "title": "Test product",
                        "link": "https://retailer.example/product",
                        "price": "$99.00",
                        "source": "Retailer",
                    }
                ]
            },
        )

    service = LiveBrightDataService(
        "test-key",
        serp_zone="serp-test",
        unlocker_zone="unlocker-test",
        transport=httpx.MockTransport(handler),
    )
    results = await service.search("test product")
    await service.close()
    assert results[0].title == "Test product"
    assert results[0].metadata["price"] == "$99.00"


@pytest.mark.asyncio
async def test_live_search_requires_serp_zone() -> None:
    service = LiveBrightDataService("test-key", serp_zone=None, unlocker_zone=None)
    with pytest.raises(BrightDataError, match="SERP_ZONE"):
        await service.search("test")
    await service.close()
