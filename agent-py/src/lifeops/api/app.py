from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from lifeops.agent import LifeOpsAgent
from lifeops.agents.contact import ContactIntelligenceAgent
from lifeops.dependencies import get_agent, get_contact_agent, get_moss
from lifeops.models import AgentRequest, AgentResponse, ContactIntelligence, InteractionRequest
from lifeops.moss import MossClient

app = FastAPI(title="LifeOps AI Agent API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "mode": "mock"}


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
    await moss.interactions.save(
        {
            "user_id": request.user_id,
            "session_id": request.session_id,
            "transcript": request.transcript,
            "intelligence": intelligence.model_dump(mode="json"),
        }
    )
    if intelligence.name or intelligence.email or intelligence.public_profile_url:
        await moss.contacts.save(
            {"user_id": request.user_id, **intelligence.model_dump(mode="json")}
        )
    return intelligence
