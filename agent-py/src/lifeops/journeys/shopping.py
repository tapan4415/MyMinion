from lifeops.journeys.base import JourneyTemplate
from lifeops.models import JourneyKind

SHOPPING = JourneyTemplate(
    kind=JourneyKind.SHOPPING,
    triggers=("buy", "couch", "furniture", "purchase"),
    tasks=(
        ("Capture requirements", "Record dimensions, style, budget, and delivery constraints."),
        ("Research options", "Find products matching hard requirements."),
        ("Compare finalists", "Rank total cost, quality, fit, and return policy."),
        ("Choose and track", "Record the decision and delivery follow-up."),
    ),
    missing_information=("budget", "dimensions", "delivery location"),
    research_queries=("best matching products", "retailer delivery return policy"),
    memory_hooks=(
        "style preferences",
        "dimensions",
        "budget",
        "rejection reasons",
        "purchase decision",
    ),
    ui_card="Buying Furniture",
)
