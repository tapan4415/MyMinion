from __future__ import annotations

import re

from lifeops.brightdata import BrightDataService
from lifeops.models import ContactIntelligence, InteractionRequest


class ContactIntelligenceAgent:
    """Extracts interaction context and enriches only an explicitly supplied public URL."""

    _name = re.compile(
        r"\b(?:with|met|called|spoke to|spoke with)\s+"
        r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)"
    )
    _company = re.compile(r"\b(?:at|from|works at)\s+([A-Z][\w&.-]+(?:\s+[A-Z][\w&.-]+)*)")
    _email = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")

    def __init__(self, bright_data: BrightDataService) -> None:
        self._bright_data = bright_data

    async def analyze(self, request: InteractionRequest) -> ContactIntelligence:
        transcript = request.transcript
        name_match = self._name.search(transcript)
        company_match = self._company.search(transcript)
        email_match = self._email.search(transcript)
        commitments = self._sentences_containing(transcript, ("will", "send", "share", "follow up"))
        follow_ups = self._sentences_containing(
            transcript, ("need to", "next", "follow up", "remind")
        )
        result = ContactIntelligence(
            name=name_match.group(1) if name_match else None,
            company=company_match.group(1) if company_match else None,
            email=email_match.group(0) if email_match else None,
            public_profile_url=request.public_profile_url,
            topics=self._keywords(transcript),
            commitments=commitments,
            follow_ups=follow_ups,
            relationship_notes=["Extracted from a user-provided interaction"],
            recommendations=self._recommend(commitments, follow_ups),
            provenance=["interaction transcript"],
        )
        identity_query = " ".join(
            part for part in (result.name, result.company, "professional profile") if part
        )
        discovery = await self._bright_data.search(
            identity_query or f"professional context {' '.join(result.topics[:3])}", limit=3
        )
        result.provenance.extend(document.url for document in discovery)
        result.relationship_notes.extend(
            f"Public-web candidate: {document.title}" for document in discovery
        )
        if request.public_profile_url and request.consent_to_enrich:
            document = await self._bright_data.extract(request.public_profile_url)
            result.provenance.append(document.url)
            result.relationship_notes.append(document.text)
            result.enrichment_status = (
                "mock_enriched" if document.metadata.get("mock") else "enriched"
            )
        elif request.public_profile_url:
            result.enrichment_status = "consent_required"
        return result

    @staticmethod
    def _recommend(commitments: list[str], follow_ups: list[str]) -> list[str]:
        recommendations = [f"Track commitment: {item}" for item in commitments]
        recommendations.extend(f"Create follow-up: {item}" for item in follow_ups)
        if not recommendations:
            recommendations.append("Confirm the desired next step before contacting this person")
        return recommendations

    @staticmethod
    def _sentences_containing(text: str, terms: tuple[str, ...]) -> list[str]:
        sentences = [sentence.strip() for sentence in re.split(r"[.!?]+", text) if sentence.strip()]
        return [
            sentence for sentence in sentences if any(term in sentence.lower() for term in terms)
        ]

    @staticmethod
    def _keywords(text: str) -> list[str]:
        stop = {
            "about",
            "after",
            "again",
            "could",
            "from",
            "have",
            "their",
            "there",
            "they",
            "this",
            "with",
            "would",
        }
        words = re.findall(r"[A-Za-z]{5,}", text.lower())
        counts = {word: words.count(word) for word in set(words) if word not in stop}
        return [
            word for word, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:8]
        ]
