"""Scribe enrichment loop.

Turns a snippet of conversation transcript into durable Moss knowledge:
  1. extract important facts (LLM for arbitrary facts + regex baseline),
  2. attribute each fact to the right person (the user vs another named speaker),
  3. gate them through the existing MemoryManager.should_store policy,
  4. persist to Moss via MemoryManager.save (user facts as the user's; other people's
     facts are stored but clearly attributed),
  5. optionally research the user's fact live with Bright Data,
  6. when a NEW person is detected, gather their public info via Bright Data, summarize
     it, and store a contact record + a concise profile memory so the Companion can
     later answer "tell me about <person>".

Public data only (search results + public pages) and best-effort — never breaks the
listening loop. No LiveKit import, so it can be unit-tested with plain text.

NOTE: transcripts are currently untagged, so attribution is best-effort guesswork by
the LLM. When speaker-tagged audio is available this becomes exact.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime

from lifeops.memory import MemoryManager
from lifeops.models import MemoryCandidate, MemoryKind, MemoryRecord, ResearchResult
from lifeops.moss import MossClient
from lifeops.research import ResearchManager

_VALID_KINDS = {kind.value for kind in MemoryKind}
_NON_PERSON = {"user", "someone", "everyone", "they", "them", "people", "friend", "team"}


def _extraction_system(user_name: str) -> str:
    return (
        "You extract durable, important facts from a snippet of a real, possibly "
        "multi-person conversation, so a personal assistant can remember them.\n"
        f"The primary user is {user_name}. Attribute every fact to who it is ABOUT:\n"
        f'- If {user_name} states something about themselves or their own plans, set '
        '"subject" to "user".\n'
        '- If a DIFFERENT named speaker states something about themselves (e.g. "my name '
        'is Varuni and I work at Microsoft"), set "subject" to that person\'s name and do '
        f"NOT attribute it to {user_name}.\n"
        "- If the user states a fact about another person, set subject to that person's name.\n"
        "Keep only facts worth remembering: preferences, constraints (budgets, dates, "
        "requirements), decisions, commitments, rejection reasons, stable profile facts "
        "(names, places, roles, relationships), and plans. Ignore small talk and filler.\n"
        'Respond with a compact JSON object: {"facts": [{"subject": "user" or a person\'s '
        'name, "kind": one of [preference, constraint, decision, rejection_reason, journey, '
        'profile], "content": "<short self-contained fact>", "confidence": <0-1>, '
        '"research": <true if fresh web info (products, prices, places, events) would help>}], '
        '"people": ["<full names of OTHER real people (never the user) who were mentioned or '
        'talked to and are worth looking up>"]}. '
        'If nothing is worth saving, return {"facts": [], "people": []}.'
    )


@dataclass
class ScribeEnrichment:
    heard: str
    memories: list[MemoryRecord] = field(default_factory=list)
    research: list[ResearchResult] = field(default_factory=list)
    people: list[dict] = field(default_factory=list)


class ScribeEnricher:
    """Reuse-heavy orchestrator for the always-on Scribe."""

    def __init__(
        self,
        memory: MemoryManager,
        research: ResearchManager,
        *,
        moss: MossClient | None = None,
        user_id: str = "demo-user",
        user_name: str = "Shobhit",
        openai_api_key: str | None = None,
        model: str = "gpt-4.1-mini",
        use_llm: bool = True,
        max_research_per_flush: int = 1,
        enable_people: bool = True,
        max_people_per_flush: int = 1,
    ) -> None:
        self._memory = memory
        self._research = research
        self._moss = moss if moss is not None else getattr(memory, "_moss", None)
        self._user_id = user_id
        self._user_name = user_name
        self._api_key = openai_api_key
        self._model = model
        self._use_llm = use_llm and bool(openai_api_key)
        self._max_research = max_research_per_flush
        self._enable_people = enable_people
        self._max_people = max_people_per_flush
        self._people_seen: set[str] = set()

    def _is_user(self, subject: str) -> bool:
        subject = subject.strip().lower()
        return subject in {"user", "", self._user_name.lower(), self._user_name.split()[0].lower()}

    @staticmethod
    def _looks_like_person(subject: str) -> bool:
        parts = subject.strip().split()
        return (
            1 <= len(parts) <= 4
            and subject.strip().lower() not in _NON_PERSON
            and all(part[:1].isalpha() for part in parts if part)
        )

    async def enrich(self, text: str) -> ScribeEnrichment:
        text = text.strip()
        if not text:
            return ScribeEnrichment(heard=text)
        candidates, llm_people = await self._collect_candidates(text)
        saved: list[MemoryRecord] = []
        research: list[ResearchResult] = []
        researched = 0
        people_ctx: dict[str, str] = {}
        for candidate, wants_research, subject in candidates:
            if not self._memory.should_store(candidate):
                continue
            if self._is_user(subject):
                record = await self._memory.save(self._user_id, candidate, source="scribe")
                if wants_research and researched < self._max_research:
                    research += await self._research.research_topic(self._user_id, record.content)
                    researched += 1
            else:
                attributed = candidate.model_copy(
                    update={"content": f"{subject}: {candidate.content}"}
                )
                record = await self._memory.save(
                    self._user_id, attributed, source=f"scribe:about:{subject}"
                )
                if self._looks_like_person(subject):
                    people_ctx.setdefault(subject, candidate.content)
            saved.append(record)

        for person in llm_people:
            if not self._is_user(person) and self._looks_like_person(person):
                people_ctx.setdefault(person, "")

        people: list[dict] = []
        if self._enable_people:
            count = 0
            for name, context in people_ctx.items():
                if count >= self._max_people:
                    break
                if name.strip().lower() in self._people_seen:
                    continue
                self._people_seen.add(name.strip().lower())
                try:
                    profile = await self._research_person(name, context)
                except Exception:
                    profile = None
                if profile:
                    people.append(profile)
                    count += 1
        return ScribeEnrichment(heard=text, memories=saved, research=research, people=people)

    async def _research_person(self, name: str, context: str) -> dict | None:
        sources = await self._research.gather_person_sources(name, context)
        if not sources:
            return None
        summary = await self._summarize_person(name, context, sources)
        identity = (summary.get("identity") or "").strip()
        bio = (summary.get("bio") or "").strip()
        now = datetime.now(UTC).isoformat()
        contact_doc = {
            "user_id": self._user_id,
            "name": name,
            "content": bio or identity or name,
            "identity": identity,
            "role": summary.get("role"),
            "company": summary.get("company"),
            "sources": [{"title": doc.title, "url": doc.url} for doc in sources],
            "source": "scribe:person",
            "kind": "contact",
            "observed_at": now,
            "created_at": now,
        }
        if self._moss is not None:
            try:
                await self._moss.contacts.save(contact_doc)
            except Exception:
                pass
        if identity:
            candidate = MemoryCandidate(
                kind=MemoryKind.PROFILE,
                content=f"{name}: {identity}"[:230],
                confidence=0.85,
                stable=True,
                source_message=context or name,
            )
            try:
                await self._memory.save(self._user_id, candidate, source="scribe:person")
            except Exception:
                pass
        return {"name": name, "identity": identity, "sources": len(sources)}

    async def _summarize_person(
        self, name: str, context: str, sources: list
    ) -> dict:
        snippets = "\n".join(
            f"- {doc.title} | {doc.url}\n  {(doc.text or '')[:200]}" for doc in sources[:6]
        )
        fallback = {
            "identity": (sources[0].title or name)[:180],
            "bio": (sources[0].text or "")[:300],
            "role": None,
            "company": None,
        }
        if not self._api_key:
            return fallback
        try:
            from openai import AsyncOpenAI
        except ImportError:
            return fallback
        prompt = (
            f"Summarize public identity information about a person named '{name}'."
            + (f" Conversation context: {context}." if context else "")
            + " Use ONLY the public search snippets below. Do not invent details; if a field "
            "is unknown use null.\n\n"
            + snippets
            + '\n\nReturn JSON: {"identity": "<one line: name, role, company, location if '
            'known>", "bio": "<2-3 sentence summary>", "role": "<role or null>", '
            '"company": "<company or null>"}'
        )
        try:
            client = AsyncOpenAI(api_key=self._api_key)
            response = await client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0,
                max_tokens=400,
            )
            return json.loads(response.choices[0].message.content or "{}") or fallback
        except Exception:
            return fallback

    async def _collect_candidates(
        self, text: str
    ) -> tuple[list[tuple[MemoryCandidate, bool, str]], list[str]]:
        merged: list[tuple[MemoryCandidate, bool, str]] = [
            (candidate, False, "user")
            for candidate in await self._memory.extract_candidate_memory(text)
        ]
        people: list[str] = []
        if self._use_llm:
            llm_candidates, people = await self._llm_extract(text)
            merged = llm_candidates + merged
        seen: set[str] = set()
        deduped: list[tuple[MemoryCandidate, bool, str]] = []
        for candidate, wants_research, subject in merged:
            key = f"{subject.strip().lower()}|{candidate.content.strip().lower()}"
            if key in seen:
                continue
            seen.add(key)
            deduped.append((candidate, wants_research, subject))
        return deduped, people

    async def _llm_extract(
        self, text: str
    ) -> tuple[list[tuple[MemoryCandidate, bool, str]], list[str]]:
        try:
            from openai import AsyncOpenAI
        except ImportError:
            return [], []
        client = AsyncOpenAI(api_key=self._api_key)
        try:
            response = await client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": _extraction_system(self._user_name)},
                    {"role": "user", "content": text},
                ],
                response_format={"type": "json_object"},
                temperature=0,
                max_tokens=700,
            )
            payload = json.loads(response.choices[0].message.content or "{}")
        except Exception:
            return [], []
        candidates: list[tuple[MemoryCandidate, bool, str]] = []
        for fact in payload.get("facts", []):
            kind = str(fact.get("kind", "")).lower()
            content = str(fact.get("content", "")).strip().rstrip(".")
            subject = str(fact.get("subject", "user")).strip() or "user"
            if kind not in _VALID_KINDS or len(content) < 3:
                continue
            try:
                confidence = float(fact.get("confidence", 0.8))
            except (TypeError, ValueError):
                confidence = 0.8
            candidates.append(
                (
                    MemoryCandidate(
                        kind=MemoryKind(kind),
                        content=content,
                        confidence=max(0.0, min(1.0, confidence)),
                        stable=kind in {"preference", "constraint", "profile"},
                        source_message=text,
                    ),
                    bool(fact.get("research", False)),
                    subject,
                )
            )
        people = [str(p).strip() for p in payload.get("people", []) if str(p).strip()]
        return candidates, people
