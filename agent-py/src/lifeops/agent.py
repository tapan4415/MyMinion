from __future__ import annotations

from typing import Any

from lifeops.agents.buying import BuyingAdvisor
from lifeops.agents.contact import ContactIntelligenceAgent
from lifeops.agents.trip import TripPlannerAgent
from lifeops.memory import MemoryManager
from lifeops.models import (
    AgentRequest,
    AgentResponse,
    InteractionRequest,
    MemoryCandidate,
    MemoryKind,
    SessionState,
    UseCase,
)
from lifeops.planner import Planner
from lifeops.research import ResearchManager
from lifeops.sessions import SessionRepository
from lifeops.use_cases.router import UseCaseRouter


class LifeOpsAgent:
    """Main orchestration use case shared by HTTP, voice, and future workers."""

    def __init__(
        self,
        planner: Planner,
        memory: MemoryManager,
        research: ResearchManager,
        sessions: SessionRepository,
        router: UseCaseRouter | None = None,
        buying: BuyingAdvisor | None = None,
        trip: TripPlannerAgent | None = None,
        contact: ContactIntelligenceAgent | None = None,
    ) -> None:
        self._planner = planner
        self._memory = memory
        self._research = research
        self._sessions = sessions
        self._router = router or UseCaseRouter()
        self._buying = buying or BuyingAdvisor()
        self._trip = trip or TripPlannerAgent()
        self._contact = contact

    async def respond(self, request: AgentRequest) -> AgentResponse:
        session = await self._sessions.get(request.session_id) or SessionState(
            session_id=request.session_id, user_id=request.user_id
        )
        session.conversation.append({"role": "user", "content": request.message})

        memories_used = await self._memory.retrieve(request.user_id, request.message)
        use_case = await self._router.route(request.message)
        journey = await self._planner.create_journey(request.message)
        research = await self._research.research_journey(request.user_id, journey)
        recommendations = []
        contact_intelligence = None
        if use_case == UseCase.BUYING:
            recommendations = await self._buying.recommend(journey, research)
        elif use_case == UseCase.TRIP_PLANNING:
            recommendations = await self._trip.recommend(journey, research)
        elif use_case == UseCase.CONTACT_INTELLIGENCE and self._contact:
            contact_intelligence = await self._contact.analyze(
                InteractionRequest(
                    user_id=request.user_id,
                    session_id=request.session_id,
                    transcript=request.message,
                )
            )

        candidates = await self._memory.extract_candidate_memory(request.message)
        candidates.append(
            MemoryCandidate(
                kind=MemoryKind.JOURNEY,
                content=f"Active {journey.kind.value} journey: {journey.goal}",
                confidence=1,
                stable=False,
                source_message=request.message,
            )
        )
        memories_saved = [
            await self._memory.save(request.user_id, candidate)
            for candidate in candidates
            if self._memory.should_store(candidate)
        ]

        message = self._compose_response(
            journey.goal, journey.next_action, journey.missing_information, len(memories_used)
        )
        session.current_task_id = journey.tasks[0].id
        session.temporary_variables["journey_id"] = journey.id
        session.conversation.append({"role": "assistant", "content": message})
        await self._sessions.save(session)
        return AgentResponse(
            message=message,
            journey=journey,
            research=research,
            memories_used=memories_used,
            memories_saved=memories_saved,
            use_case=use_case,
            recommendations=recommendations,
            contact_intelligence=contact_intelligence,
        )

    @staticmethod
    def _compose_response(
        goal: str, next_action: str, missing: list[str], memory_count: int
    ) -> str:
        context = f" I found {memory_count} relevant saved memories." if memory_count else ""
        needed = f" I’ll need {', '.join(missing[:3])} as we go." if missing else ""
        return (
            f"I’ve turned “{goal}” into a working journey. "
            f"We’ll start with {next_action.lower()}.{context}{needed}"
        )


class OpenAIAgentsAdapter:
    """Optional SDK boundary. Imports lazily so mock mode has no credential requirement."""

    def __init__(self, model: str) -> None:
        self.model = model

    async def run(self, prompt: str, tools: list[Any]) -> str:
        try:
            from agents import Agent, Runner
        except ImportError as error:
            raise RuntimeError("Install the 'openai' extra to enable OpenAI Agents SDK") from error
        agent = Agent(
            name="LifeOps Orchestrator",
            instructions=(
                "Plan real-world work, retrieve durable memory, research changing facts, "
                "and return the next concrete action."
            ),
            model=self.model,
            tools=tools,
        )
        result = await Runner.run(agent, prompt)
        return str(result.final_output)
