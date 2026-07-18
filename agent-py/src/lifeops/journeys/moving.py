from lifeops.journeys.base import JourneyTemplate
from lifeops.models import JourneyKind

MOVING = JourneyTemplate(
    kind=JourneyKind.MOVING,
    triggers=("moving", "move", "relocating"),
    tasks=(
        ("Define the move", "Confirm locations, dates, household size, and budget."),
        ("Research movers", "Compare licensed movers, quotes, and service levels."),
        ("Set up utilities", "Identify power, water, gas, and transfer dates."),
        ("Handle DMV", "Check license and vehicle registration requirements."),
        ("Connect internet", "Compare available plans at the new address."),
        ("Run the checklist", "Track packing, address changes, and handoffs."),
    ),
    missing_information=("destination", "target move date", "budget range"),
    research_queries=(
        "licensed movers",
        "utility providers",
        "DMV moving requirements",
        "home internet providers",
    ),
    memory_hooks=("budget", "preferred providers", "move date", "rejected quotes"),
    ui_card="Moving command center",
)
