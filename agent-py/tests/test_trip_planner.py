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
async def test_bare_destination_reply_is_accepted() -> None:
    """Regression test: a bare place name answering "Where would you like to go?"
    (e.g. voice STT transcribing "Lake Tahoe") must not be asked again forever —
    it doesn't match any trigger-phrase pattern, so it needs the fallback path."""
    agent = get_agent()
    first = await agent.respond(
        AgentRequest(user_id="u-trip-bare", session_id="trip-bare", message="Plan a weekend trip")
    )
    assert first.pending_questions == ["Where would you like to go?"]

    second = await agent.respond(
        AgentRequest(user_id="u-trip-bare", session_id="trip-bare", message="Lake Tahoe")
    )
    assert second.pending_questions != ["Where would you like to go?"]


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


@pytest.mark.asyncio
async def test_trip_specific_facts_do_not_leak_from_a_matched_preference_document() -> None:
    """Regression test: probing Moss for a reusable field (e.g. pace) can match a document
    that also happens to mention a dollar figure or place name. Only the field actually
    being probed for may be pulled from that document - budget/destination must not leak."""
    agent = get_agent()
    user_id = "u-trip-5"

    await get_moss().preferences.save(
        {
            "user_id": user_id,
            "kind": "preference",
            "content": (
                "I love hiking any day. I prefer to have less than $600 budget for a "
                "weekend getaway to Paris."
            ),
        }
    )

    response = None
    for message in ["Plan a trip to Portland", "5 days", "driving", "airbnb", "vegetarian"]:
        response = await agent.respond(
            AgentRequest(user_id=user_id, session_id="trip-5", message=message)
        )

    assert response is not None
    # budget is trip-specific and must still be asked, not silently backfilled to 600.
    assert response.itinerary is None
    assert response.pending_questions == ["What's your budget for the trip?"]

    final = await agent.respond(
        AgentRequest(user_id=user_id, session_id="trip-5", message="$200")
    )
    assert final.itinerary is not None
    # budget came from this conversation, not leaked from the unrelated $600 mention.
    assert final.itinerary.slots.budget == 200.0
    # pace_preferences legitimately reused hiking from the matched document.
    assert "hiking" in final.itinerary.slots.pace_preferences


@pytest.mark.asyncio
async def test_bare_answers_are_persisted_even_when_memory_manager_would_miss_them() -> None:
    """Regression test: a bare one-word answer like "vegetarian" or "airbnb" doesn't match
    any of MemoryManager's "I prefer/I live in/..." phrase patterns, so TripSlotService must
    persist the resolved slot itself rather than depending on that regex to catch it too."""
    agent = get_agent()
    user_id = "u-trip-4"

    turns = [
        "Plan a trip to Portland",
        "5 days",
        "driving",
        "airbnb",
        "$500",
        "vegetarian",
        "hiking",
    ]
    for message in turns:
        await agent.respond(AgentRequest(user_id=user_id, session_id="trip-4", message=message))

    stored_preferences = await get_moss().preferences.search("", filters={"user_id": user_id})
    saved_content = " ".join(str(doc.get("content", "")) for doc in stored_preferences).lower()
    assert "driving" in saved_content or "road" in saved_content
    assert "airbnb" in saved_content
    assert "vegetarian" in saved_content
    assert "hiking" in saved_content

    response = None
    for message in ["Plan a trip to Seattle", "3 days", "$400"]:
        response = await agent.respond(
            AgentRequest(user_id=user_id, session_id="trip-4-new", message=message)
        )

    assert response is not None
    assert response.itinerary is not None
    assert response.itinerary.slots.transport_mode == TripTransportMode.ROAD
    assert response.itinerary.slots.accommodation_type == TripAccommodationType.AIRBNB
    assert "vegetarian" in response.itinerary.slots.food_preferences
    assert "hiking" in response.itinerary.slots.pace_preferences
