export type TaskStatus = "todo" | "researching" | "waiting" | "completed";
export type JourneyKind = "moving" | "shopping" | "travel" | "contact" | "insurance" | "job_search" | "general";
export type UseCase = "buying" | "contact_intelligence" | "trip_planning" | "general";

export interface JourneyTask {
  id: string;
  title: string;
  description: string;
  status: TaskStatus;
}

export interface Journey {
  id: string;
  goal: string;
  kind: JourneyKind;
  tasks: JourneyTask[];
  dependencies: Record<string, string[]>;
  missing_information: string[];
  next_action: string;
  status: "active" | "paused" | "completed";
}

export interface ResearchResult {
  id: string;
  source: string;
  title: string;
  summary: string;
  confidence: number;
  retrieved_at: string;
}

export interface MemoryRecord {
  id: string;
  user_id: string;
  kind: "preference" | "constraint" | "decision" | "rejection_reason" | "journey" | "profile";
  content: string;
  created_at: string;
  updated_at: string;
}

export interface Recommendation {
  id: string;
  title: string;
  rationale: string;
  score: number;
  tradeoffs: string[];
  evidence_ids: string[];
  attributes: Record<string, unknown>;
}

export interface ContactIntelligence {
  name: string | null;
  company: string | null;
  role: string | null;
  email: string | null;
  public_profile_url: string | null;
  topics: string[];
  commitments: string[];
  follow_ups: string[];
  relationship_notes: string[];
  recommendations: string[];
  provenance: string[];
  enrichment_status: string;
}

export type TripTransportMode = "flight" | "road" | "either";
export type TripAccommodationType = "hotel" | "airbnb" | "either";

export interface TripSlots {
  destination: string | null;
  origin: string | null;
  travelers: number | null;
  duration_days: number | null;
  start_date: string | null;
  transport_mode: TripTransportMode | null;
  accommodation_type: TripAccommodationType | null;
  budget: number | null;
  budget_currency: string;
  food_preferences: string[];
  pace_preferences: string[];
}

export interface TripItineraryDay {
  day_number: number;
  focus: string;
  transport: string | null;
  lodging: string | null;
  meals: string[];
  activities: string[];
  evidence_ids: string[];
}

export interface TripItinerary {
  id: string;
  journey_id: string;
  slots: TripSlots;
  days: TripItineraryDay[];
  estimated_total_cost: number | null;
  budget_status: "under" | "near" | "over" | "unknown";
  evidence_ids: string[];
  generated_at: string;
}

export interface AgentResponse {
  message: string;
  journey: Journey;
  research: ResearchResult[];
  memories_used: MemoryRecord[];
  memories_saved: MemoryRecord[];
  use_case: UseCase;
  recommendations: Recommendation[];
  contact_intelligence: ContactIntelligence | null;
  itinerary: TripItinerary | null;
  pending_questions: string[];
}
