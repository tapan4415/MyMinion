from __future__ import annotations

import re
from collections import defaultdict

from lifeops.models import (
    Journey,
    Recommendation,
    ResearchResult,
    TripItinerary,
    TripItineraryDay,
    TripSlots,
)


def _parse_price(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = re.sub(r"[^\d.]", "", value)
        if cleaned:
            try:
                return float(cleaned)
            except ValueError:
                return None
    return None


def _bucket_evidence(evidence: list[ResearchResult]) -> dict[str, list[ResearchResult]]:
    buckets: dict[str, list[ResearchResult]] = defaultdict(list)
    for item in evidence:
        buckets[str(item.raw.get("category", "other"))].append(item)
    return buckets


class TripPlannerAgent:
    """Builds an itinerary strategy while keeping bookable facts tied to evidence."""

    def _build_days(
        self, slots: TripSlots, evidence: list[ResearchResult]
    ) -> list[TripItineraryDay]:
        buckets = _bucket_evidence(evidence)
        transport = buckets.get("transport", [])
        lodging = buckets.get("lodging", [])
        food = buckets.get("food", [])
        activities = buckets.get("activities", [])
        duration = slots.duration_days or 1
        pace_label = ", ".join(slots.pace_preferences) or "balanced"

        days: list[TripItineraryDay] = []
        for day_number in range(1, duration + 1):
            is_edge_day = day_number in (1, duration)
            if day_number == 1:
                focus = f"Arrival in {slots.destination}"
            elif day_number == duration:
                focus = "Departure"
            else:
                focus = f"{pace_label.title()} day"

            transport_item = transport[0] if transport and is_edge_day else None
            lodging_item = lodging[0] if lodging else None
            food_item = food[(day_number - 1) % len(food)] if food else None
            activity_item = (
                activities[(day_number - 1) % len(activities)]
                if activities and not is_edge_day
                else None
            )

            evidence_ids = [
                item.id
                for item in (transport_item, lodging_item, food_item, activity_item)
                if item is not None
            ]
            days.append(
                TripItineraryDay(
                    day_number=day_number,
                    focus=focus,
                    transport=transport_item.title if transport_item else None,
                    lodging=lodging_item.title if lodging_item else None,
                    meals=[food_item.title] if food_item else [],
                    activities=[activity_item.title] if activity_item else [],
                    evidence_ids=evidence_ids,
                )
            )
        return days

    def _estimate_budget(
        self, evidence: list[ResearchResult], slots: TripSlots
    ) -> tuple[float | None, str]:
        prices_by_category: dict[str, float] = {}
        for item in evidence:
            category = str(item.raw.get("category", "other"))
            if category in prices_by_category:
                continue
            price = _parse_price(item.raw.get("price"))
            if price is not None:
                prices_by_category[category] = price

        if not prices_by_category:
            return None, "unknown"
        total = sum(prices_by_category.values())
        if slots.budget is None:
            return total, "unknown"
        if total <= slots.budget * 0.95:
            return total, "under"
        if total <= slots.budget * 1.05:
            return total, "near"
        return total, "over"

    async def recommend(
        self, journey: Journey, evidence: list[ResearchResult], slots: TripSlots
    ) -> list[Recommendation]:
        days = self._build_days(slots, evidence)
        _, budget_status = self._estimate_budget(evidence, slots)
        pace_label = ", ".join(slots.pace_preferences) or "balanced"
        food_label = ", ".join(slots.food_preferences) or "local favorites"
        transport_label = (
            slots.transport_mode.value if slots.transport_mode else "the confirmed mode"
        )
        stay_label = slots.accommodation_type.value if slots.accommodation_type else "lodging"
        rationale = (
            f"Builds a {len(days)}-day {slots.destination} itinerary around {pace_label} "
            f"activities and {food_label} dining, staying at a {stay_label} and traveling by "
            f"{transport_label}."
        )
        return [
            Recommendation(
                title=f"{len(days)}-day {slots.destination} itinerary",
                rationale=rationale,
                score=0.9,
                tradeoffs=[
                    "Itinerary is grounded in current research; recheck prices before booking."
                ],
                evidence_ids=[item.id for item in evidence],
                attributes={
                    "pace": pace_label,
                    "booking_status": "not_booked",
                    "budget_status": budget_status,
                    "days": len(days),
                },
            )
        ]

    async def build_itinerary(
        self, journey: Journey, evidence: list[ResearchResult], slots: TripSlots
    ) -> TripItinerary:
        days = self._build_days(slots, evidence)
        total_cost, budget_status = self._estimate_budget(evidence, slots)
        return TripItinerary(
            journey_id=journey.id,
            slots=slots,
            days=days,
            estimated_total_cost=total_cost,
            budget_status=budget_status,
            evidence_ids=[item.id for item in evidence],
        )
