# MyMinion

MyMinion is a voice-first personal operations agent. A user states an outcome; the system turns it into a durable journey, retrieves useful context, researches changing facts, and advances the next action across web and iOS sessions. It is intentionally modeled as an agent—not a chat transcript with extra UI.

The scaffold runs end to end with deterministic in-memory Moss and Bright Data adapters. No API keys are required for local development, and provider code is kept behind typed interfaces so production adapters can replace mocks without changing business logic.

## Architecture

```text
Next.js web ─┐
             ├── FastAPI delivery layer ── LifeOpsAgent use case
Expo iOS  ───┤                              ├── Planner
             │                              ├── MemoryManager ── Moss repositories
LiveKit voice┘                              ├── ResearchManager ── Bright Data service
                                            └── Session repository
```

- `frontend/` — Next.js 15, React 19, Tailwind, and shadcn-style Radix primitives. The desktop dashboard has Conversation, Journey Board, Research, and Memory Timeline surfaces.
- `mobile/` — Expo/React Native iOS client using the same API and shared contracts. It includes goal entry, a microphone interaction seam, journey progress, and evidence cards.
- `agent-py/` — FastAPI delivery, application orchestration, domain models, provider abstractions, sample journeys, and independent agent tools.
- `shared/` — portable JSON schema, TypeScript API contracts, and orchestration prompts.

Session state and long-term memory are deliberately separate. `SessionState` holds the current task, conversation, and temporary variables. Moss holds selected durable facts and journey continuity.

## Request sequence

```mermaid
sequenceDiagram
    actor User
    participant LiveKit
    participant Planner
    participant Memory as Memory Retrieval
    participant BrightData as Bright Data Research
    participant Moss as Moss Update
    participant Agent as LLM Response
    participant UI as Frontend Update
    User->>LiveKit: Speak a goal
    LiveKit->>Planner: Transcribed goal
    Planner->>Memory: Retrieve relevant durable context
    Memory-->>Planner: Preferences, constraints, decisions
    Planner->>BrightData: Research current facts and options
    BrightData-->>Planner: Evidence with sources
    Planner->>Moss: Save useful findings and journey state
    Planner->>Agent: Plan + memory + evidence
    Agent-->>UI: Response and structured journey update
    UI-->>User: Voice response + visual progress
```

## Provider integration points

### Moss

`MossClient` exposes five repositories: `user_profile`, `preferences`, `journeys`, `research`, and `decisions`. Every index implements async `save`, `search`, `update`, and `delete`. `InMemoryMossIndex` is the development adapter. A real adapter should implement `MossIndex` and be injected from `dependencies.py`.

`MemoryManager` does not save every message. It only accepts preferences, constraints, decisions, rejection reasons, ongoing journeys, and stable profile information that pass a confidence policy.

### Bright Data

`BrightDataService` defines async `search`, `extract`, and `crawl`. `MockBrightDataService` returns clearly marked deterministic evidence and never performs an API call. Implement the same interface with the Bright Data SDK/API, then swap the dependency provider.

### LiveKit

`LiveKitVoiceBridge` turns a final transcript into the exact same `LifeOpsAgent.respond()` use case used by HTTP. `livekit_entrypoint()` is the seam for room connection, STT, TTS, interruptions, and streaming. Install the `livekit` Python extra and provide credentials only when adding the real worker.

### OpenAI Agents SDK

`LifeOpsAgent` owns the deterministic orchestration order: retrieve memory, plan, research, selectively store, update session state, respond. `OpenAIAgentsAdapter` is an optional lazy-loaded SDK boundary using `Agent` and async `Runner.run`. Mock mode does not import the SDK or require credentials. In production, wrap independent functions in `tools/` as SDK function tools and inject them into the adapter.

## Run locally

Requirements: Python 3.11+, Node.js 20+, npm, Xcode with an iOS Simulator for the native client.

```bash
cp .env.example .env
python3 -m venv .venv
.venv/bin/pip install -e './agent-py[dev]'
npm install
```

Start the API:

```bash
.venv/bin/uvicorn lifeops.api.app:app --app-dir agent-py/src --reload
```

Then start either client:

```bash
npm run dev       # web: http://localhost:3000
npm run dev:ios   # Expo + iOS Simulator
```

For a physical iPhone, set `EXPO_PUBLIC_AGENT_API_URL` to the computer's LAN address (for example `http://192.168.1.20:8000`); `localhost` inside the device points to the phone. The iOS microphone purpose string is already configured. A real LiveKit room token endpoint is still required before voice streaming is enabled.

Run all checks:

```bash
make verify
```

Docker runs the web/API pair with `docker compose up --build`. Expo remains a host-native workflow because it needs the simulator or a device.

## API

- `GET /health` — liveness and adapter mode.
- `POST /v1/agent/respond` — accepts `{ user_id, session_id, message }` and returns the response, structured journey, evidence, memories used, and memories saved.
- FastAPI docs are available at `http://localhost:8000/docs`.

## Replacing mocks safely

1. Implement the existing provider interface; keep SDK types inside the adapter.
2. Add provider settings to environment configuration—never source files.
3. Replace only the dependency factory in `dependencies.py`.
4. Add contract tests using recorded/sandbox responses.
5. Keep mock mode for local development, CI, and offline demos.

External actions such as purchases, bookings, applications, or policy changes should require explicit user confirmation, be idempotent where possible, and write an audit event. Research confidence is not permission to act.
