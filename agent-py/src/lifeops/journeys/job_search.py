from lifeops.journeys.base import JourneyTemplate
from lifeops.models import JourneyKind

JOB_SEARCH = JourneyTemplate(
    kind=JourneyKind.JOB_SEARCH,
    triggers=("job", "changing jobs", "career", "interview"),
    tasks=(
        ("Define the target", "Clarify roles, industries, compensation, and constraints."),
        ("Prepare materials", "Tailor resume, portfolio, and positioning."),
        ("Build pipeline", "Research companies and track applications."),
        ("Interview and decide", "Prepare, compare offers, and record tradeoffs."),
    ),
    missing_information=("target role", "location preference", "compensation range"),
    research_queries=("target companies hiring", "role compensation benchmarks"),
    memory_hooks=(
        "career goals",
        "location preference",
        "compensation constraint",
        "company rejection reasons",
        "offer decisions",
    ),
    ui_card="Job Search",
)
