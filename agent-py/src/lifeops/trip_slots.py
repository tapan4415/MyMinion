from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from lifeops.memory import MemoryManager
from lifeops.models import (
    MemoryCandidate,
    MemoryKind,
    SessionState,
    TripAccommodationType,
    TripSlots,
    TripTransportMode,
)
from lifeops.moss import MossClient

FOOD_VOCAB: dict[str, tuple[str, ...]] = {
    "vegetarian": ("vegetarian",),
    "vegan": ("vegan",),
    "seafood": ("seafood",),
    "halal": ("halal",),
    "kosher": ("kosher",),
    "gluten-free": ("gluten-free", "gluten free"),
    "street food": ("street food",),
    "local cuisine": ("local cuisine", "local food"),
    "fine dining": ("fine dining",),
    "spicy food": ("spicy",),
    "desserts": ("dessert", "desserts", "sweets"),
    "foodie": ("foodie",),
}

PACE_VOCAB: dict[str, tuple[str, ...]] = {
    "hiking": ("hiking", "hike", "trekking", "trek"),
    "adventure": ("adventure", "adventurous"),
    "relaxing": ("relaxing", "relax", "chill", "laid-back", "laid back"),
    "balanced": ("balanced",),
}

_FLIGHT_WORDS = ("fly", "flight", "flights", "flying", "plane", "airplane")
_ROAD_WORDS = ("drive", "driving", "road trip", "roadtrip", "by road", "by car")
_AIRBNB_WORDS = ("airbnb", "air bnb")
_HOTEL_WORDS = ("hotel", "hotels")

_DURATION_RE = re.compile(r"(\d+)\s*[- ]?(?:day|days|night|nights)\b", re.I)
_BUDGET_RE = re.compile(r"\$\s?([\d,]+(?:\.\d+)?)|budget[^\d]{0,20}?([\d,]+(?:\.\d+)?)", re.I)
_TRAVELERS_RE = re.compile(
    r"(\d+)\s*(?:people|travelers|travellers|adults|guests|of us)\b", re.I
)
_CAP_WORDS = r"[A-Z][\w]*(?:\s+[A-Z][\w]*){0,3}"
_FROM_TO_RE = re.compile(rf"\bfrom\s+({_CAP_WORDS})\s+to\s+({_CAP_WORDS})")
_DESTINATION_RE = re.compile(
    rf"\b(?:trip to|travel(?:ing|ling)? to|vacation to|holiday to|going to|go to|visit)"
    rf"\s+({_CAP_WORDS})"
)
_NON_ANSWER_FILLERS = frozenset(
    {
        "yes", "no", "yeah", "nah", "yep", "nope", "ok", "okay", "sure",
        "maybe", "um", "uh", "hmm", "i don't know", "not sure", "idk",
    }
)
_ORIGIN_RE = re.compile(rf"\bfrom\s+({_CAP_WORDS})")

QUESTION_BANK: tuple[tuple[str, str], ...] = (
    ("destination", "Where would you like to go?"),
    ("duration_days", "How many days are you planning for the trip?"),
    ("transport_mode", "Would you like to travel by flight or by road?"),
    ("accommodation_type", "Do you prefer booking a hotel or an Airbnb?"),
    ("budget", "What's your budget for the trip?"),
    ("food_preferences", "Any restaurant or food preferences I should keep in mind?"),
    (
        "pace_preferences",
        "Are you looking for something adventurous, relaxing, or more hiking-focused?",
    ),
)

_REUSABLE_FROM_MOSS = (
    "transport_mode",
    "accommodation_type",
    "food_preferences",
    "pace_preferences",
)

_PREFERENCE_LABELS: dict[str, Callable[[Any], str]] = {
    "transport_mode": lambda v: f"prefers traveling by {v.value}",
    "accommodation_type": lambda v: f"prefers {v.value} accommodations",
    "food_preferences": lambda v: f"food preferences: {', '.join(v)}",
    "pace_preferences": lambda v: f"trip pace preferences: {', '.join(v)}",
}

_PROBE_TERMS: dict[str, str] = {
    "transport_mode": "fly flight plane drive driving road trip car transport",
    "accommodation_type": "airbnb hotel accommodation lodging stay",
    "food_preferences": (
        "vegetarian vegan foodie seafood halal kosher gluten-free street food "
        "local cuisine fine dining spicy dessert restaurant food"
    ),
    "pace_preferences": (
        "hiking hike trekking adventure adventurous relaxing relax chill balanced pace"
    ),
}


class TripSlotExtractor:
    """Deterministic regex/keyword extraction, mirroring MemoryManager's pattern style."""

    @staticmethod
    def extract(text: str) -> dict[str, Any]:
        if not text:
            return {}
        lowered = text.lower()
        found: dict[str, Any] = {}

        if match := _DURATION_RE.search(lowered):
            found["duration_days"] = int(match.group(1))

        if match := _BUDGET_RE.search(lowered):
            raw = match.group(1) or match.group(2)
            found["budget"] = float(raw.replace(",", ""))

        if match := _TRAVELERS_RE.search(lowered):
            found["travelers"] = int(match.group(1))

        has_flight = any(word in lowered for word in _FLIGHT_WORDS)
        has_road = any(word in lowered for word in _ROAD_WORDS)
        if has_flight and has_road:
            found["transport_mode"] = TripTransportMode.EITHER
        elif has_flight:
            found["transport_mode"] = TripTransportMode.FLIGHT
        elif has_road:
            found["transport_mode"] = TripTransportMode.ROAD

        has_airbnb = any(word in lowered for word in _AIRBNB_WORDS)
        has_hotel = any(word in lowered for word in _HOTEL_WORDS)
        if has_airbnb and has_hotel:
            found["accommodation_type"] = TripAccommodationType.EITHER
        elif has_airbnb:
            found["accommodation_type"] = TripAccommodationType.AIRBNB
        elif has_hotel:
            found["accommodation_type"] = TripAccommodationType.HOTEL

        food = [tag for tag, triggers in FOOD_VOCAB.items() if any(t in lowered for t in triggers)]
        if food:
            found["food_preferences"] = food

        pace = [tag for tag, triggers in PACE_VOCAB.items() if any(t in lowered for t in triggers)]
        if pace:
            found["pace_preferences"] = pace

        if match := _FROM_TO_RE.search(text):
            found["origin"] = match.group(1).strip()
            found["destination"] = match.group(2).strip()
        else:
            if match := _DESTINATION_RE.search(text):
                found["destination"] = match.group(1).strip()
            if match := _ORIGIN_RE.search(text):
                found["origin"] = match.group(1).strip()

        return found

    @staticmethod
    def merge(slots: TripSlots, extracted: dict[str, Any]) -> TripSlots:
        if not extracted:
            return slots
        data = slots.model_dump(mode="json")
        for key, value in extracted.items():
            if key in ("food_preferences", "pace_preferences"):
                existing = list(data.get(key) or [])
                for tag in value:
                    if tag not in existing:
                        existing.append(tag)
                data[key] = existing
            elif data.get(key) in (None, "", []):
                data[key] = value
        return TripSlots(**data)


class TripSlotService:
    """Resolves what's already known about a trip and asks for the rest."""

    def __init__(self, moss: MossClient, memory: MemoryManager) -> None:
        self._moss = moss
        self._memory = memory

    async def resolve(self, user_id: str, session: SessionState, message: str) -> TripSlots:
        raw_stored = session.temporary_variables.get("trip_slots")
        has_prior_turn = raw_stored is not None
        before = TripSlots(**(raw_stored or {}))
        extracted = TripSlotExtractor.extract(message)
        slots = TripSlotExtractor.merge(before, extracted)

        # A bare reply to "Where would you like to go?" (e.g. "Lake Tahoe") won't match
        # any trigger phrase or other field, so treat it as the destination itself. Only
        # applies from the second turn onward - on the very first message, "destination"
        # being unset doesn't mean we just asked about it.
        if (
            has_prior_turn
            and not extracted
            and slots.destination is None
            and "destination" in before.missing_fields()
        ):
            candidate = message.strip().rstrip(".!?")
            is_filler = candidate.lower() in _NON_ANSWER_FILLERS
            if candidate and not is_filler and len(candidate.split()) <= 6:
                slots = TripSlotExtractor.merge(slots, {"destination": candidate.title()})

        await self._persist_new_preferences(user_id, before, slots, message)

        missing = slots.missing_fields()
        reusable_missing = [field for field in missing if field in _REUSABLE_FROM_MOSS]
        if reusable_missing:
            probe = " ".join(_PROBE_TERMS[field] for field in reusable_missing)
            for index in (self._moss.preferences, self._moss.decisions, self._moss.journeys):
                hits = await index.search(probe, limit=5, filters={"user_id": user_id})
                for hit in hits:
                    content = str(hit.get("content") or hit.get("goal") or "")
                    # Only pull the specific reusable fields being probed for out of a
                    # matched document - it may also mention trip-specific facts (budget,
                    # destination, dates) that must never leak in from an unrelated trip.
                    found = TripSlotExtractor.extract(content)
                    reusable_found = {k: v for k, v in found.items() if k in _REUSABLE_FROM_MOSS}
                    slots = TripSlotExtractor.merge(slots, reusable_found)

        session.temporary_variables["trip_slots"] = slots.model_dump(mode="json")
        return slots

    async def _persist_new_preferences(
        self, user_id: str, before: TripSlots, after: TripSlots, source_message: str
    ) -> None:
        """Save durable preferences the moment they're stated, instead of relying on
        MemoryManager's generic phrase-trigger patterns to catch the same fact by luck."""
        for field in _REUSABLE_FROM_MOSS:
            before_value = getattr(before, field)
            after_value = getattr(after, field)
            if after_value in (None, "", []) or before_value == after_value:
                continue
            candidate = MemoryCandidate(
                kind=MemoryKind.PREFERENCE,
                content=_PREFERENCE_LABELS[field](after_value),
                confidence=1.0,
                stable=True,
                source_message=source_message,
            )
            if self._memory.should_store(candidate):
                await self._memory.save(user_id, candidate, source="trip_slots")

    @staticmethod
    def missing_fields(slots: TripSlots) -> list[str]:
        return slots.missing_fields()

    @staticmethod
    def has_pending(session: SessionState) -> bool:
        stored = session.temporary_variables.get("trip_slots")
        if not stored:
            return False
        return bool(TripSlots(**stored).missing_fields())

    @staticmethod
    def next_question(missing: list[str]) -> str | None:
        if not missing:
            return None
        missing_set = set(missing)
        for field, question in QUESTION_BANK:
            if field in missing_set:
                return question
        return None
