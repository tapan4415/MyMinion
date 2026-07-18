from functools import lru_cache

from lifeops.agent import LifeOpsAgent, OpenAIAgentsAdapter
from lifeops.agents.contact import ContactIntelligenceAgent
from lifeops.brightdata import BrightDataService, LiveBrightDataService, MockBrightDataService
from lifeops.config import get_settings
from lifeops.knowledge import MossAgentKnowledgeRepository
from lifeops.memory import MemoryManager
from lifeops.moss import MossClient, create_cloud_moss_client
from lifeops.planner import RuleBasedPlanner
from lifeops.research import ResearchManager
from lifeops.sessions import InMemorySessionRepository


@lru_cache
def get_moss() -> MossClient:
    settings = get_settings()
    if settings.mock_moss:
        return MossClient()
    if not settings.moss_project_id or not settings.moss_project_key:
        raise RuntimeError("MOSS_PROJECT_ID and MOSS_PROJECT_KEY are required")
    return create_cloud_moss_client(settings.moss_project_id, settings.moss_project_key)


@lru_cache
def get_bright_data() -> BrightDataService:
    settings = get_settings()
    if settings.mock_bright_data:
        return MockBrightDataService()
    if not settings.bright_data_api_key:
        raise RuntimeError("BRIGHT_DATA_API_KEY is required when mocks are disabled")
    return LiveBrightDataService(
        settings.bright_data_api_key,
        serp_zone=settings.bright_data_serp_zone,
        unlocker_zone=settings.bright_data_unlocker_zone,
        browser_ws=settings.bright_data_browser_ws,
        timeout_seconds=settings.bright_data_timeout_seconds,
    )


@lru_cache
def get_agent() -> LifeOpsAgent:
    settings = get_settings()
    moss = get_moss()
    bright_data = get_bright_data()
    return LifeOpsAgent(
        planner=RuleBasedPlanner(),
        memory=MemoryManager(moss),
        research=ResearchManager(bright_data, moss),
        sessions=InMemorySessionRepository(),
        contact=ContactIntelligenceAgent(bright_data),
        knowledge=MossAgentKnowledgeRepository(moss),
        conversation=OpenAIAgentsAdapter(settings.openai_model, settings.openai_api_key)
        if settings.openai_api_key
        else None,
    )


@lru_cache
def get_contact_agent() -> ContactIntelligenceAgent:
    return ContactIntelligenceAgent(get_bright_data())
