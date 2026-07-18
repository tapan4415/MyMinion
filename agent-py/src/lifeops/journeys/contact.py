from lifeops.journeys.base import JourneyTemplate
from lifeops.models import JourneyKind

CONTACT = JourneyTemplate(
    kind=JourneyKind.CONTACT,
    triggers=("conversation with", "meeting with", "spoke with", "spoke to", "call with"),
    tasks=(
        ("Extract interaction", "Identify people, context, topics, and explicit facts."),
        ("Resolve identity", "Match existing contacts before creating a new relationship record."),
        ("Research public context", "Discover consent-safe public professional sources."),
        ("Capture commitments", "Separate their commitments, your commitments, and deadlines."),
        ("Recommend follow-up", "Propose the next useful relationship action for approval."),
    ),
    missing_information=("interaction context", "desired relationship outcome"),
    research_queries=("public professional profile", "company background"),
    memory_hooks=("relationship context", "commitments", "follow-up preferences"),
    ui_card="Relationship Intelligence",
)
