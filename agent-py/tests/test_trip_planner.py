import pytest

from lifeops.dependencies import get_agent, get_contact_agent, get_moss
from lifeops.models import AgentRequest, TripAccommodationType, TripTransportMode, UseCase


@pytest.fixture(autouse=True)
def reset_dependencies() -> None:
    get_agent.cache_clear()
    get_contact_agent.cache_clear()
    get_moss.cache_clear()


@pytest.mark.asyncio
async def test_trip_planning_asks_one_question_at_a_time() -> None:
    response = await get_agent().respond(
        AgentRequest(user_id="u-trip-1", session_id="trip-1", message="Plan a 5 day trip to Kyoto")
    )
    assert response.use_case == UseCase.TRIP_PLANNING
    assert response.itinerary is None
    assert not response.recommendations
    assert len(response.pending_questions) == 1
    # destination and duration were both stated up front, so they shouldn't be re-asked.
    assert "kyoto" not in response.pending_questions[0].lower()
    assert "day" not in response.pending_questions[0].lower()


@pytest.mark.asyncio
async def test_trip_planning_builds_itinerary_once_all_slots_are_answered() -> None:
    agent = get_agent()
    user_id, session_id = "u-trip-2", "trip-2"
    turns = [
        "Plan a 5 day trip to Kyoto",
        "I'll fly there",
        "Let's book a hotel",
        "My budget is $3000",
        "I love street food and local cuisine",
        "I'm looking for something adventurous and relaxing",
    ]
    response = None
    for message in turns:
        response = await agent.respond(
            AgentRequest(user_id=user_id, session_id=session_id, message=message)
        )

    assert response is not None
    assert response.use_case == UseCase.TRIP_PLANNING
    assert not response.pending_questions
    assert response.recommendations
    assert response.itinerary is not None
    assert response.itinerary.slots.destination == "Kyoto"
    assert response.itinerary.slots.duration_days == 5
    assert response.itinerary.slots.transport_mode == TripTransportMode.FLIGHT
    assert response.itinerary.slots.accommodation_type == TripAccommodationType.HOTEL
    assert len(response.itinerary.days) == 5

    stored = await get_moss().trip_itineraries.search("Kyoto", filters={"user_id": user_id})
    assert stored


@pytest.mark.asyncio
async def test_durable_preference_is_reused_without_being_asked_again() -> None:
    agent = get_agent()
    user_id = "u-trip-3"

    # A pace preference stated in an earlier, unrelated conversation.
    await agent.respond(
        AgentRequest(
            user_id=user_id, session_id="pref-session", message="I prefer hiking and relaxing"
        )
    )

    turns = [
        "Plan a 4 day trip to Denver",
        "I'll drive there",
        "I'll book an airbnb",
        "My budget is $1200",
        "I enjoy vegetarian food",
    ]
    response = None
    for message in turns:
        response = await agent.respond(
            AgentRequest(user_id=user_id, session_id="trip-3", message=message)
        )

    assert response is not None
    assert response.itinerary is not None
    assert "hiking" in response.itinerary.slots.pace_preferences
    assert "relaxing" in response.itinerary.slots.pace_preferences
    # The pace question was answered from memory, so it was never asked directly.
    assert response.itinerary.slots.transport_mode == TripTransportMode.ROAD
    assert response.itinerary.slots.accommodation_type == TripAccommodationType.AIRBNB
