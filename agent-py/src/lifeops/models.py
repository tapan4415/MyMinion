from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, ClassVar, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class JourneyKind(StrEnum):
    MOVING = "moving"
    SHOPPING = "shopping"
    TRAVEL = "travel"
    INSURANCE = "insurance"
    JOB_SEARCH = "job_search"
    CONTACT = "contact"
    GENERAL = "general"


class TaskStatus(StrEnum):
    TODO = "todo"
    RESEARCHING = "researching"
    WAITING = "waiting"
    COMPLETED = "completed"


class JourneyStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class MemoryKind(StrEnum):
    PREFERENCE = "preference"
    CONSTRAINT = "constraint"
    DECISION = "decision"
    REJECTION_REASON = "rejection_reason"
    JOURNEY = "journey"
    PROFILE = "profile"


class UseCase(StrEnum):
    BUYING = "buying"
    CONTACT_INTELLIGENCE = "contact_intelligence"
    TRIP_PLANNING = "trip_planning"
    GENERAL = "general"


class TripTransportMode(StrEnum):
    FLIGHT = "flight"
    ROAD = "road"
    EITHER = "either"


class TripAccommodationType(StrEnum):
    HOTEL = "hotel"
    AIRBNB = "airbnb"
    EITHER = "either"


class JourneyTask(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    title: str
    description: str
    status: TaskStatus = TaskStatus.TODO
    metadata: dict[str, Any] = Field(default_factory=dict)


class Journey(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    goal: str
    kind: JourneyKind = JourneyKind.GENERAL
    tasks: list[JourneyTask]
    dependencies: dict[str, list[str]] = Field(default_factory=dict)
    missing_information: list[str] = Field(default_factory=list)
    next_action: str
    status: JourneyStatus = JourneyStatus.ACTIVE


class MemoryCandidate(BaseModel):
    kind: MemoryKind
    content: str
    confidence: float = Field(ge=0, le=1)
    stable: bool = False
    source_message: str


class MemoryRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    user_id: str
    kind: MemoryKind
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ResearchResult(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    source: str
    title: str
    summary: str
    confidence: float = Field(ge=0, le=1)
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    raw: dict[str, Any] = Field(default_factory=dict)


class Recommendation(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    title: str
    rationale: str
    score: float = Field(ge=0, le=1)
    tradeoffs: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)


class TripSlots(BaseModel):
    """Facts the trip planner needs before it can build an itinerary."""

    REQUIRED_FIELDS: ClassVar[tuple[str, ...]] = (
        "destination",
        "duration_days",
        "transport_mode",
        "accommodation_type",
        "budget",
        "food_preferences",
        "pace_preferences",
    )

    destination: str | None = None
    origin: str | None = None
    travelers: int | None = None
    duration_days: int | None = None
    start_date: str | None = None
    transport_mode: TripTransportMode | None = None
    accommodation_type: TripAccommodationType | None = None
    budget: float | None = None
    budget_currency: str = "USD"
    food_preferences: list[str] = Field(default_factory=list)
    pace_preferences: list[str] = Field(default_factory=list)

    def missing_fields(self) -> list[str]:
        missing = []
        for field in self.REQUIRED_FIELDS:
            value = getattr(self, field)
            if value in (None, "", []):
                missing.append(field)
        return missing


class TripItineraryDay(BaseModel):
    day_number: int
    focus: str
    transport: str | None = None
    lodging: str | None = None
    meals: list[str] = Field(default_factory=list)
    activities: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class TripItinerary(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    journey_id: str
    slots: TripSlots
    days: list[TripItineraryDay]
    estimated_total_cost: float | None = None
    budget_status: str = "unknown"
    evidence_ids: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ContactIntelligence(BaseModel):
    name: str | None = None
    company: str | None = None
    role: str | None = None
    email: str | None = None
    public_profile_url: str | None = None
    topics: list[str] = Field(default_factory=list)
    commitments: list[str] = Field(default_factory=list)
    follow_ups: list[str] = Field(default_factory=list)
    relationship_notes: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    provenance: list[str] = Field(default_factory=list)
    enrichment_status: str = "not_requested"


class InteractionRequest(BaseModel):
    user_id: str
    session_id: str
    transcript: str = Field(min_length=1)
    consent_to_enrich: bool = False
    public_profile_url: str | None = None


class SessionState(BaseModel):
    session_id: str
    user_id: str
    current_task_id: str | None = None
    conversation: list[dict[str, str]] = Field(default_factory=list)
    temporary_variables: dict[str, Any] = Field(default_factory=dict)


class AgentRequest(BaseModel):
    user_id: str
    session_id: str
    message: str = Field(min_length=1)


class AgentResponse(BaseModel):
    message: str
    journey: Journey
    research: list[ResearchResult]
    memories_used: list[MemoryRecord]
    memories_saved: list[MemoryRecord]
    use_case: UseCase = UseCase.GENERAL
    recommendations: list[Recommendation] = Field(default_factory=list)
    contact_intelligence: ContactIntelligence | None = None
    itinerary: TripItinerary | None = None
    pending_questions: list[str] = Field(default_factory=list)


class LiveKitTokenRequest(BaseModel):
    room_name: str | None = Field(default=None, min_length=1, max_length=128)
    participant_name: str | None = Field(default=None, min_length=1, max_length=128)
    # "ambient" = Scribe only (silent listening); "ask" = Companion + Scribe together.
    mode: Literal["ambient", "ask"] = "ambient"


class LiveKitTokenResponse(BaseModel):
    server_url: str
    participant_token: str
    room_name: str
    participant_identity: str
