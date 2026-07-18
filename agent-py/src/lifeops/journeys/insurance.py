from lifeops.journeys.base import JourneyTemplate
from lifeops.models import JourneyKind

INSURANCE = JourneyTemplate(
    kind=JourneyKind.INSURANCE,
    triggers=("insurance", "coverage", "policy", "quote"),
    tasks=(
        ("Define coverage", "Capture assets, risk tolerance, and required limits."),
        ("Research carriers", "Find eligible, reputable providers."),
        ("Compare quotes", "Normalize premiums, deductibles, exclusions, and limits."),
        ("Review decision", "Record rationale and renewal follow-up."),
    ),
    missing_information=("insurance type", "location", "coverage needs"),
    research_queries=(
        "licensed insurance carriers",
        "coverage requirements",
        "consumer complaint data",
    ),
    memory_hooks=(
        "risk tolerance",
        "coverage constraints",
        "rejected exclusions",
        "selected policy",
    ),
    ui_card="Insurance Shopping",
)
