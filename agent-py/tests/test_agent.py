import pytest

from lifeops.agents.buying import BuyingAdvisor
from lifeops.dependencies import get_agent, get_contact_agent, get_moss
from lifeops.models import (
    AgentRequest,
    InteractionRequest,
    Journey,
    JourneyKind,
    JourneyTask,
    ResearchResult,
    UseCase,
)


@pytest.fixture(autouse=True)
def reset_dependencies() -> None:
    get_agent.cache_clear()
    get_contact_agent.cache_clear()
    get_moss.cache_clear()


@pytest.mark.asyncio
async def test_agent_creates_moving_journey_and_mock_research() -> None:
    response = await get_agent().respond(
        AgentRequest(
            user_id="u1", session_id="s1", message="I am moving to Seattle and my budget is $4,000"
        )
    )
    assert response.journey.kind == JourneyKind.MOVING
    assert len(response.journey.tasks) == 6
    assert response.research
    assert response.research[0].raw["mock"] is True
    assert any(memory.kind.value == "constraint" for memory in response.memories_saved)


@pytest.mark.asyncio
async def test_memory_is_available_on_later_session() -> None:
    agent = get_agent()
    await agent.respond(
        AgentRequest(user_id="u1", session_id="first", message="I prefer boutique hotels")
    )
    response = await agent.respond(
        AgentRequest(user_id="u1", session_id="second", message="Plan a trip with hotels")
    )
    assert any("boutique hotels" in memory.content for memory in response.memories_used)


@pytest.mark.asyncio
async def test_buying_flow_does_not_fabricate_unpriced_recommendations() -> None:
    response = await get_agent().respond(
        AgentRequest(user_id="u1", session_id="buy", message="Recommend a couch under $1500")
    )
    assert response.use_case == UseCase.BUYING
    assert response.recommendations == []


@pytest.mark.asyncio
async def test_verified_retailer_offers_are_ranked_by_dollar_price() -> None:
    journey = Journey(
        goal="Find Apple AirPods under $400",
        kind=JourneyKind.SHOPPING,
        tasks=[JourneyTask(title="Compare offers", description="Compare verified prices")],
        next_action="Compare approved retailers",
    )
    evidence = [
        ResearchResult(
            source="https://www.bestbuy.com/site/airpods/123.p",
            title="Apple AirPods",
            summary="Verified page",
            confidence=0.9,
            raw={
                "price": "$179.99",
                "serp_title": "AirPods at Best Buy",
                "verified_product_page": True,
            },
        ),
        ResearchResult(
            source="https://www.apple.com/shop/buy-airpods/airpods-pro-2",
            title="AirPods Pro",
            summary="Verified page",
            confidence=0.9,
            raw={
                "price": "$249.00",
                "serp_title": "AirPods Pro at Apple",
                "verified_product_page": True,
            },
        ),
        ResearchResult(
            source="https://www.amazon.com/airpods/dp/example",
            title="AirPods accessory price",
            summary="Navigation price incorrectly exposed as a product offer",
            confidence=0.9,
            raw={
                "price": "$10.00",
                "serp_title": "AirPods at Amazon",
                "verified_product_page": True,
            },
        ),
    ]
    recommendations = await BuyingAdvisor().recommend(journey, evidence)
    assert [item.attributes["price"] for item in recommendations] == [179.99, 249.0]
    assert [item.attributes["retailer"] for item in recommendations] == ["Best Buy", "Apple"]
    assert recommendations[0].score > recommendations[1].score


@pytest.mark.asyncio
async def test_buying_phrase_builds_budget_and_call_quality_persona() -> None:
    response = await get_agent().respond(
        AgentRequest(
            user_id="persona-user",
            session_id="persona-buy",
            message=(
                "Find the best noise-cancelling headphones under $400 "
                "with strong call quality."
            ),
        )
    )
    contents = [memory.content.lower() for memory in response.memories_saved]
    assert any("400" in content for content in contents)
    assert any("call quality" in content for content in contents)


@pytest.mark.asyncio
async def test_natural_priority_language_is_recalled_for_later_shopping() -> None:
    agent = get_agent()
    first = await agent.respond(
        AgentRequest(
            user_id="priority-user",
            session_id="persona",
            message=(
                "I care about excellent microphone quality. "
                "Comfort matters more than heavy bass."
            ),
        )
    )
    saved_preferences = [
        memory for memory in first.memories_saved if memory.kind.value == "preference"
    ]
    assert len(saved_preferences) == 2

    second = await agent.respond(
        AgentRequest(
            user_id="priority-user",
            session_id="airpods",
            message="Find the best Apple AirPods deal for me",
        )
    )
    recalled = " ".join(memory.content.lower() for memory in second.memories_used)
    assert "microphone quality" in recalled
    assert "comfort matters more than heavy bass" in recalled


@pytest.mark.asyncio
async def test_trip_flow_asks_for_missing_slots_before_building_itinerary() -> None:
    response = await get_agent().respond(
        AgentRequest(user_id="u1", session_id="trip", message="Plan a trip to Japan")
    )
    assert response.use_case == UseCase.TRIP_PLANNING
    assert response.itinerary is None
    assert not response.recommendations
    assert response.pending_questions
    assert response.message == response.pending_questions[0]


@pytest.mark.asyncio
async def test_contact_enrichment_requires_consent() -> None:
    intelligence = await get_contact_agent().analyze(
        InteractionRequest(
            user_id="u1",
            session_id="contact",
            transcript="I spoke with Sarah Chen at Acme. She will send the proposal.",
            public_profile_url="https://www.linkedin.com/in/sarah-chen",
        )
    )
    assert intelligence.name == "Sarah Chen"
    assert intelligence.enrichment_status == "consent_required"
    assert intelligence.commitments == ["She will send the proposal"]
    assert len(intelligence.provenance) == 4


@pytest.mark.asyncio
async def test_contact_flow_uses_bright_data_and_persists_summary_to_moss() -> None:
    response = await get_agent().respond(
        AgentRequest(
            user_id="u1",
            session_id="relationship",
            message="I spoke with Sarah Chen at Acme. She will send the proposal.",
        )
    )
    assert response.use_case == UseCase.CONTACT_INTELLIGENCE
    assert response.contact_intelligence is not None
    assert len(response.contact_intelligence.provenance) == 4
    contacts = await get_moss().contacts.search("Sarah", filters={"user_id": "u1"})
    assert contacts
