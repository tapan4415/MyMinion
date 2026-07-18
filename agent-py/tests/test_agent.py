import pytest

from lifeops.dependencies import get_agent, get_contact_agent, get_moss
from lifeops.models import AgentRequest, InteractionRequest, JourneyKind, UseCase


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
async def test_buying_flow_returns_ranked_recommendations() -> None:
    response = await get_agent().respond(
        AgentRequest(user_id="u1", session_id="buy", message="Recommend a couch under $1500")
    )
    assert response.use_case == UseCase.BUYING
    assert len(response.recommendations) == 3
    assert response.recommendations[0].score > response.recommendations[1].score
    stored = await get_moss().recommendations.search("Best overall", filters={"user_id": "u1"})
    assert stored


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
async def test_trip_flow_returns_itinerary_strategy() -> None:
    response = await get_agent().respond(
        AgentRequest(user_id="u1", session_id="trip", message="Plan a trip to Japan")
    )
    assert response.use_case == UseCase.TRIP_PLANNING
    assert response.recommendations[0].attributes["pace"] == "balanced"
    stored = await get_moss().research.search("Japan", filters={"user_id": "u1"})
    assert stored


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
