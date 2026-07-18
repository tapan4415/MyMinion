from lifeops.models import UseCase


class UseCaseRouter:
    """Deterministic routing fallback; production can replace classification with an SDK agent."""

    _contact_terms = (
        "conversation with",
        "meeting with",
        "spoke with",
        "spoke to",
        "call with",
        "interaction",
    )
    _travel_terms = ("trip", "travel", "vacation", "itinerary", "flight", "hotel", "japan")
    _buying_terms = ("buy", "recommend", "shopping", "purchase", "couch", "laptop", "best")

    async def route(self, message: str) -> UseCase:
        normalized = message.lower()
        if any(term in normalized for term in self._contact_terms):
            return UseCase.CONTACT_INTELLIGENCE
        if any(term in normalized for term in self._travel_terms):
            return UseCase.TRIP_PLANNING
        if any(term in normalized for term in self._buying_terms):
            return UseCase.BUYING
        return UseCase.GENERAL
