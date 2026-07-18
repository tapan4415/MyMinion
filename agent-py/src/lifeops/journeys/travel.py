from lifeops.journeys.base import JourneyTemplate
from lifeops.models import JourneyKind

TRAVEL = JourneyTemplate(
    kind=JourneyKind.TRAVEL,
    triggers=("trip", "travel", "japan", "vacation", "flight"),
    tasks=(
        ("Shape the trip", "Confirm dates, travelers, pace, and budget."),
        ("Research routes", "Compare flights and ground transportation."),
        ("Build itinerary", "Balance stays, activities, and recovery time."),
        ("Check requirements", "Review entry, insurance, connectivity, and bookings."),
    ),
    missing_information=("dates", "departure airport", "budget"),
    research_queries=(
        "flight routes",
        "entry requirements",
        "neighborhood guide",
        "rail transportation",
    ),
    memory_hooks=(
        "travel pace",
        "seat preference",
        "hotel preferences",
        "dietary constraints",
        "booked decisions",
    ),
    ui_card="Trip Planning",
)
