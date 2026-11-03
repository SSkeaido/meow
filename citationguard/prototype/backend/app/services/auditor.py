from app.models.schemas import AuditRequest, AuditResult, EvidenceCard, RetrievedChunk
from app.services.evidence_validator import is_source_verified


class HeuristicCitationAuditor:
    """Placeholder auditor for validating the API shape before LLM integration."""

    provider = "heuristic"
    model_name = "keyword-overlap-placeholder"
    sent_payload_summary = "heuristic-only; no external model call"

    def audit_claim(
        self,
        project_id: str,
        payload: AuditRequest,
        evidence_cards: list[EvidenceCard],
        retrieved_chunks: list[RetrievedChunk] | None = None,
        invalid_cited_paper_ids: set[str] | None = None,
        unmapped_citation_markers: list[str] | None = None,
    ) -> AuditResult:
        del project_id
        invalid_cited_paper_ids = invalid_cited_paper_ids or set()
        unmapped_citation_markers = unmapped_citation_markers or []
        if unmapped_citation_markers:
            return AuditResult(
                claim_text=payload.claim_text,
                cited_paper_ids=payload.cited_paper_ids,
                supporting_evidence_ids=[],
                supporting_source_chunk_ids=[],
                support_level="RISK",
                risk_flags=["citation_marker_unmapped"],
                explanation=f"The claim contains citation markers without bound source PDFs: {', '.join(unmapped_citation_markers)}.",
                suggested_fix="Bind each citation marker to an uploaded paper before running the audit again.",
            )
        candidates = [
            card
            for card in evidence_cards
            if (not payload.cited_paper_ids or card.paper_id in payload.cited_paper_ids) and is_source_verified(card)
        ]
        best = _best_keyword_match(payload.claim_text, candidates)
        if best:
            overlap = _keyword_overlap(payload.claim_text, best.source_quote)
            if not payload.cited_paper_ids:
                support_level = "RISK"
                risk_flags = ["missing_citation"]
                explanation = "Related evidence was found, but this claim has no cited paper in the allow-list."
            elif invalid_cited_paper_ids:
                support_level = "RISK"
                risk_flags = ["citation_not_in_allow_list"]
                explanation = "One or more cited papers are not available in this project."
            elif overlap >= 4:
                support_level = "CHECK"
                risk_flags = []
                explanation = "A candidate evidence card has overlapping terminology, but heuristic audit cannot verify support."
            else:
                support_level = "RISK"
                risk_flags = ["unsupported_claim"]
                explanation = "Only weak lexical overlap was found between the claim and candidate evidence card."

            return AuditResult(
                claim_text=payload.claim_text,
                cited_paper_ids=payload.cited_paper_ids,
                supporting_evidence_ids=[best.id],
                supporting_source_chunk_ids=[best.source_chunk_id],
                support_level=support_level,
                risk_flags=risk_flags,
                explanation=explanation,
                suggested_fix="Run the LLM citation-audit chain before using this claim in a manuscript.",
            )

        retrieved_chunks = retrieved_chunks or []
        best_chunk = _best_chunk_match(payload.claim_text, retrieved_chunks)
        if not best_chunk:
            risk_flags = ["unsupported_claim"]
            if not payload.cited_paper_ids:
                risk_flags.insert(0, "missing_citation")
            if invalid_cited_paper_ids:
                risk_flags.insert(0, "citation_not_in_allow_list")
            return AuditResult(
                claim_text=payload.claim_text,
                cited_paper_ids=payload.cited_paper_ids,
                supporting_evidence_ids=[],
                supporting_source_chunk_ids=[],
                support_level="FAIL",
                risk_flags=risk_flags,
                explanation="No candidate evidence was found for this claim.",
                suggested_fix="Add a citation or narrow the claim to evidence already in the project.",
            )

        overlap = _keyword_overlap(payload.claim_text, best_chunk.text)
        if not payload.cited_paper_ids:
            support_level = "RISK"
            risk_flags = ["missing_citation"]
            explanation = "Related evidence was found, but this claim has no cited paper in the allow-list."
        elif invalid_cited_paper_ids:
            support_level = "RISK"
            risk_flags = ["citation_not_in_allow_list"]
            explanation = "One or more cited papers are not available in this project."
        elif overlap >= 4:
            support_level = "CHECK"
            risk_flags = []
            explanation = "A retrieved source chunk has overlapping terminology, but heuristic audit cannot verify support."
        else:
            support_level = "RISK"
            risk_flags = ["unsupported_claim"]
            explanation = "Only weak lexical overlap was found between the claim and retrieved source chunk."

        return AuditResult(
            claim_text=payload.claim_text,
            cited_paper_ids=payload.cited_paper_ids,
            supporting_evidence_ids=[],
            supporting_source_chunk_ids=[best_chunk.source_chunk_id],
            support_level=support_level,
            risk_flags=risk_flags,
            explanation=explanation,
            suggested_fix="Run the LLM citation-audit chain before using this claim in a manuscript.",
        )


def _best_keyword_match(claim: str, cards: list[EvidenceCard]) -> EvidenceCard | None:
    if not cards:
        return None
    return max(cards, key=lambda card: _keyword_overlap(claim, card.source_quote))


def _best_chunk_match(claim: str, chunks: list[RetrievedChunk]) -> RetrievedChunk | None:
    if not chunks:
        return None
    return max(chunks, key=lambda chunk: _keyword_overlap(claim, chunk.text))


def _keyword_overlap(left: str, right: str) -> int:
    left_words = _keywords(left)
    right_words = _keywords(right)
    return len(left_words & right_words)


def _keywords(text: str) -> set[str]:
    return {word.lower().strip(".,;:()[]{}") for word in text.split() if len(word) >= 5}


citation_auditor = HeuristicCitationAuditor()
