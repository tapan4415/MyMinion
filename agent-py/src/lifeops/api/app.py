from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from lifeops.agent import LifeOpsAgent
from lifeops.agents.contact import ContactIntelligenceAgent
from lifeops.config import get_settings
from lifeops.dependencies import get_agent, get_contact_agent, get_moss
from lifeops.knowledge import MossAgentKnowledgeRepository
from lifeops.livekit import LiveKitTokenService
from lifeops.models import (
    AgentRequest,
    AgentResponse,
    ContactIntelligence,
    InteractionRequest,
    LiveKitTokenRequest,
    LiveKitTokenResponse,
)
from lifeops.moss import MossClient, ensure_cloud_moss_indexes


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    if (
        not settings.mock_moss
        and settings.moss_auto_create_indexes
        and settings.moss_project_id
        and settings.moss_project_key
    ):
        await ensure_cloud_moss_indexes(settings.moss_project_id, settings.moss_project_key)
    yield


app = FastAPI(title="MyMinion Agent API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "ok",
        "mode": "hybrid"
        if settings.mock_bright_data != settings.mock_moss
        else ("mock" if settings.mock_bright_data else "live"),
        "bright_data": (
            "mock"
            if settings.mock_bright_data
            else "configured"
            if settings.bright_data_browser_ws
            or (
                settings.bright_data_api_key
                and settings.bright_data_serp_zone
                and settings.bright_data_unlocker_zone
            )
            else "incomplete"
        ),
        "moss": (
            "mock"
            if settings.mock_moss
            else "configured"
            if settings.moss_project_id and settings.moss_project_key
            else "incomplete"
        ),
        "livekit": (
            "configured"
            if settings.livekit_url and settings.livekit_api_key and settings.livekit_api_secret
            else "incomplete"
        ),
    }


@app.post("/v1/livekit/token", response_model=LiveKitTokenResponse)
async def create_livekit_token(request: LiveKitTokenRequest) -> LiveKitTokenResponse:
    return LiveKitTokenService(get_settings()).issue(request)


@app.post("/v1/agent/respond", response_model=AgentResponse)
async def respond(request: AgentRequest, agent: LifeOpsAgent = Depends(get_agent)) -> AgentResponse:
    return await agent.respond(request)


@app.post("/v1/interactions/analyze", response_model=ContactIntelligence)
async def analyze_interaction(
    request: InteractionRequest,
    agent: ContactIntelligenceAgent = Depends(get_contact_agent),
    moss: MossClient = Depends(get_moss),
) -> ContactIntelligence:
    intelligence = await agent.analyze(request)
    await MossAgentKnowledgeRepository(moss).save_contact_summary(
        request.user_id, request.session_id, intelligence
    )
    return intelligence
