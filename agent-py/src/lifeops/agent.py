from __future__ import annotations

import json
from typing import Any, Protocol

from lifeops.agents.buying import BuyingAdvisor
from lifeops.agents.contact import ContactIntelligenceAgent
from lifeops.agents.trip import TripPlannerAgent
from lifeops.knowledge import AgentKnowledgeRepository
from lifeops.memory import MemoryManager
from lifeops.models import (
    AgentRequest,
    AgentResponse,
    InteractionRequest,
    MemoryCandidate,
    MemoryKind,
    ResearchResult,
    SessionState,
    TripItinerary,
    UseCase,
)
from lifeops.planner import Planner
from lifeops.research import ResearchManager
from lifeops.sessions import SessionRepository
from lifeops.trip_research import TripResearchService
from lifeops.trip_slots import TripSlotService
from lifeops.use_cases.router import UseCaseRouter


class ConversationRuntime(Protocol):
    async def run(self, prompt: str, tools: list[Any]) -> str: ...


class LifeOpsAgent:
    """Main orchestration use case shared by HTTP, voice, and future workers."""

    def __init__(
        self,
        planner: Planner,
        memory: MemoryManager,
        research: ResearchManager,
        sessions: SessionRepository,
        trip_slots: TripSlotService,
        trip_research: TripResearchService,
        router: UseCaseRouter | None = None,
        buying: BuyingAdvisor | None = None,
        trip: TripPlannerAgent | None = None,
        contact: ContactIntelligenceAgent | None = None,
        knowledge: AgentKnowledgeRepository | None = None,
        conversation: ConversationRuntime | None = None,
    ) -> None:
        self._planner = planner
        self._memory = memory
        self._research = research
        self._sessions = sessions
        self._trip_slots = trip_slots
        self._trip_research = trip_research
        self._router = router or UseCaseRouter()
        self._buying = buying or BuyingAdvisor()
        self._trip = trip or TripPlannerAgent()
        self._contact = contact
        self._knowledge = knowledge
        self._conversation = conversation

    async def respond(self, request: AgentRequest) -> AgentResponse:
        session = await self._sessions.get(request.session_id) or SessionState(
            session_id=request.session_id, user_id=request.user_id
        )
        session.conversation.append({"role": "user", "content": request.message})

        memories_used = await self._memory.retrieve(request.user_id, request.message)
        use_case = await self._router.route(request.message)
        if use_case == UseCase.GENERAL and self._trip_slots.has_pending(session):
            use_case = UseCase.TRIP_PLANNING
        journey = await self._planner.create_journey(request.message)
        # Trip planning does its own targeted research once slots are complete, and needs
        # none while still gathering answers - skip the generic call so answering a simple
        # question ("5 days", "vegetarian") doesn't pay for an unused Bright Data search.
        research: list[ResearchResult] = (
            []
            if use_case == UseCase.TRIP_PLANNING
            else await self._research.research_journey(request.user_id, journey)
        )
        recommendations = []
        contact_intelligence = None
        itinerary: TripItinerary | None = None
        pending_questions: list[str] = []
        if use_case == UseCase.BUYING:
            recommendations = await self._buying.recommend(journey, research, memories_used)
        elif use_case == UseCase.TRIP_PLANNING:
            slots = await self._trip_slots.resolve(request.user_id, session, request.message)
            missing = self._trip_slots.missing_fields(slots)
            if missing:
                question = self._trip_slots.next_question(missing)
                pending_questions = [question] if question else []
            else:
                research = await self._trip_research.research(request.user_id, journey, slots)
                recommendations = await self._trip.recommend(journey, research, slots)
                itinerary = await self._trip.build_itinerary(journey, research, slots)
        elif use_case == UseCase.CONTACT_INTELLIGENCE and self._contact:
            contact_intelligence = await self._contact.analyze(
                InteractionRequest(
                    user_id=request.user_id,
                    session_id=request.session_id,
                    transcript=request.message,
                )
            )

        if self._knowledge:
            await self._knowledge.save_journey(request.user_id, journey, use_case)
            await self._knowledge.save_recommendations(
                request.user_id, journey.id, use_case, recommendations
            )
            if contact_intelligence:
                await self._knowledge.save_contact_summary(
                    request.user_id, request.session_id, contact_intelligence
                )
            if itinerary:
                await self._knowledge.save_trip_itinerary(request.user_id, itinerary)

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

        if self._conversation:
            context = {
                "use_case": use_case.value,
                "journey": journey.model_dump(mode="json"),
                "research": [item.model_dump(mode="json") for item in research],
                "recommendations": [item.model_dump(mode="json") for item in recommendations],
                "contact_intelligence": contact_intelligence.model_dump(mode="json")
                if contact_intelligence
                else None,
                "memories": [item.model_dump(mode="json") for item in memories_used],
                "pending_questions": pending_questions,
                "itinerary": itinerary.model_dump(mode="json") if itinerary else None,
            }
            history = session.conversation[-12:]
            message = await self._conversation.run(
                "Conversation history:\n"
                f"{json.dumps(history, default=str)}\n\n"
                "Completed agent work:\n"
                f"{json.dumps(context, default=str)}\n\n"
                "Respond naturally to the user's latest message. Do not describe yourself as "
                "a scaffold. If pending_questions is non-empty, ask exactly that one question "
                "conversationally and do not invent an itinerary yet. If itinerary is present, "
                "briefly summarize the day-by-day plan and mention the budget status. Otherwise "
                "ask at most one necessary follow-up question. If enough information exists, "
                "give the useful answer now and briefly explain the next action. For a buying "
                "mission, only call something an offer or quote a price when it appears in the "
                "recommendations list. If recommendations is empty, say that no verified priced "
                "offers were found; never turn raw research text into recommendations.",
                [],
            )
        elif pending_questions:
            message = pending_questions[0]
        elif itinerary:
            message = self._compose_itinerary_message(itinerary)
        else:
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
            itinerary=itinerary,
            pending_questions=pending_questions,
        )

    @staticmethod
    def _compose_itinerary_message(itinerary: TripItinerary) -> str:
        budget_note = {
            "under": "within your budget",
            "near": "close to your budget",
            "over": "above your budget",
            "unknown": "with pricing still to confirm",
        }[itinerary.budget_status]
        return (
            f"Here's a {len(itinerary.days)}-day itinerary for {itinerary.slots.destination}, "
            f"{budget_note}. I'll refine it further as we lock in bookings."
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

    def __init__(self, model: str, api_key: str) -> None:
        self.model = model
        self._api_key = api_key

    async def run(self, prompt: str, tools: list[Any]) -> str:
        try:
            from agents import Agent, Runner, set_default_openai_key
        except ImportError as error:
            raise RuntimeError("Install the 'openai' extra to enable OpenAI Agents SDK") from error
        set_default_openai_key(self._api_key, use_for_tracing=False)
        agent = Agent(
            name="LifeOps Orchestrator",
            instructions=(
                "You are MyMinion, a warm, concise, voice-first personal agent. Converse "
                "naturally while helping the user complete real-world work. Use the supplied "
                "journey, memory, research, and specialist output as facts. Never claim you "
                "researched something when no evidence was supplied."
            ),
            model=self.model,
            tools=tools,
        )
        result = await Runner.run(agent, prompt)
        return str(result.final_output)
