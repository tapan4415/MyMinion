from functools import lru_cache

from lifeops.agent import LifeOpsAgent
from lifeops.agents.contact import ContactIntelligenceAgent
from lifeops.brightdata import MockBrightDataService
from lifeops.memory import MemoryManager
from lifeops.moss import MossClient
from lifeops.planner import RuleBasedPlanner
from lifeops.research import ResearchManager
from lifeops.sessions import InMemorySessionRepository


@lru_cache
def get_moss() -> MossClient:
    return MossClient()


@lru_cache
def get_agent() -> LifeOpsAgent:
    moss = get_moss()
    bright_data = MockBrightDataService()
    return LifeOpsAgent(
        planner=RuleBasedPlanner(),
        memory=MemoryManager(moss),
        research=ResearchManager(bright_data, moss),
        sessions=InMemorySessionRepository(),
        contact=ContactIntelligenceAgent(bright_data),
    )


@lru_cache
def get_contact_agent() -> ContactIntelligenceAgent:
    return ContactIntelligenceAgent(MockBrightDataService())
