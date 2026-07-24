import json
import os
from typing import Literal

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.models.schemas import AuditRequest, AuditResult, EvidenceCard, RetrievedChunk
from app.services.auditor import HeuristicCitationAuditor
from app.services.evidence_validator import is_source_verified


class CitationAuditDecision(BaseModel):
    """The only decision shape accepted from an LLM citation auditor."""

    support_level: Literal["PASS", "CHECK", "RISK", "FAIL"]
    risk_flags: list[str] = Field(default_factory=list)
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    supporting_source_chunk_ids: list[str] = Field(default_factory=list)
    explanation: str
    suggested_fix: str


AUDIT_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are a strict academic citation auditor. Decide only whether the provided evidence packet supports the claim.
Do not use outside knowledge. Do not infer facts missing from the packet. Do not invent IDs.
PASS requires direct, sufficiently scoped support. CHECK means partial or uncertain support. RISK means an identifiable citation risk. FAIL means no support.
Use risk flags when applicable: overgeneralization, causal_overclaim, population_mismatch, method_mismatch, unsupported_claim, semantic_drift_after_polish.
Your supporting IDs must exactly match IDs from the evidence packet.""",
        ),
        (
            "human",
            """Claim:
{claim_text}

Cited paper IDs:
{cited_paper_ids}

Evidence packet (the complete set of evidence available to you):
{evidence_packet}""",
        ),
    ]
)


class LangChainCitationAuditor:
    """Minimal-payload LLM auditor with deterministic safety fallbacks."""

    sent_payload_summary = "claim plus up to five retrieved evidence snippets; no full PDF"

    def __init__(
        self,
        provider: str = "openai_compatible",
        model_name: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.provider = provider
        self.model_name = model_name or os.getenv("LLM_MODEL", "")
        api_key = api_key or os.getenv("LLM_API_KEY", "")
        base_url = base_url or os.getenv("LLM_BASE_URL", "")
        if not self.model_name or not api_key:
            raise ValueError("LLM_MODEL and LLM_API_KEY are required for LLM_PROVIDER=openai_compatible")

        # Import only when an LLM is explicitly enabled, so local mode needs no model package or key.
        from langchain_openai import ChatOpenAI

        model_args = {"model": self.model_name, "api_key": api_key, "temperature": 0}
        if base_url:
            model_args["base_url"] = base_url
        model = ChatOpenAI(**model_args)
        self.chain = AUDIT_PROMPT | model.with_structured_output(CitationAuditDecision)
        self.fallback = HeuristicCitationAuditor()

    def audit_claim(
        self,
        project_id: str,
        payload: AuditRequest,
        evidence_cards: list[EvidenceCard],
        retrieved_chunks: list[RetrievedChunk] | None = None,
        invalid_cited_paper_ids: set[str] | None = None,
        unmapped_citation_markers: list[str] | None = None,
    ) -> AuditResult:
        invalid_cited_paper_ids = invalid_cited_paper_ids or set()
        if not payload.cited_paper_ids or invalid_cited_paper_ids or unmapped_citation_markers:
            return self.fallback.audit_claim(
                project_id=project_id,
                payload=payload,
                evidence_cards=evidence_cards,
                retrieved_chunks=retrieved_chunks,
                invalid_cited_paper_ids=invalid_cited_paper_ids,
                unmapped_citation_markers=unmapped_citation_markers,
            )

        evidence_packet = _build_evidence_packet(payload, evidence_cards, retrieved_chunks or [])
        if not evidence_packet:
            return self.fallback.audit_claim(
                project_id=project_id,
                payload=payload,
                evidence_cards=evidence_cards,
                retrieved_chunks=retrieved_chunks,
                invalid_cited_paper_ids=invalid_cited_paper_ids,
                unmapped_citation_markers=unmapped_citation_markers,
            )

        try:
            decision = self.chain.invoke(
                {
                    "claim_text": payload.claim_text,
                    "cited_paper_ids": ", ".join(payload.cited_paper_ids),
                    "evidence_packet": json.dumps(evidence_packet, ensure_ascii=False),
                }
            )
        except Exception:
            # A model failure must not become a misleading scholarly verdict.
            return self.fallback.audit_claim(
                project_id=project_id,
                payload=payload,
                evidence_cards=evidence_cards,
                retrieved_chunks=retrieved_chunks,
                invalid_cited_paper_ids=invalid_cited_paper_ids,
                unmapped_citation_markers=unmapped_citation_markers,
            )

        valid_evidence_ids = {item["evidence_card_id"] for item in evidence_packet if item["evidence_card_id"]}
        valid_chunk_ids = {item["source_chunk_id"] for item in evidence_packet}
        evidence_ids = [item for item in decision.supporting_evidence_ids if item in valid_evidence_ids]
        chunk_ids = [item for item in decision.supporting_source_chunk_ids if item in valid_chunk_ids]
        support_level = decision.support_level
        risk_flags = list(dict.fromkeys(decision.risk_flags))
        if support_level == "PASS" and not (evidence_ids or chunk_ids):
            support_level = "CHECK"
            risk_flags.append("unsupported_claim")

        return AuditResult(
            claim_text=payload.claim_text,
            cited_paper_ids=payload.cited_paper_ids,
            supporting_evidence_ids=evidence_ids,
            supporting_source_chunk_ids=chunk_ids,
            support_level=support_level,
            risk_flags=list(dict.fromkeys(risk_flags)),
            explanation=decision.explanation,
            suggested_fix=decision.suggested_fix,
        )


def _build_evidence_packet(
    payload: AuditRequest,
    evidence_cards: list[EvidenceCard],
    retrieved_chunks: list[RetrievedChunk],
) -> list[dict[str, str | None]]:
    cited_paper_ids = set(payload.cited_paper_ids)
    packet: list[dict[str, str | None]] = []
    seen_chunk_ids: set[str] = set()
    for card in evidence_cards:
        if card.paper_id not in cited_paper_ids or not is_source_verified(card) or len(packet) >= 5:
            continue
        packet.append(
            {
                "evidence_card_id": card.id,
                "source_chunk_id": card.source_chunk_id,
                "paper_id": card.paper_id,
                "page": str(card.page),
                "section": card.section,
                "quote": card.source_quote,
            }
        )
        seen_chunk_ids.add(card.source_chunk_id)
    for chunk in retrieved_chunks:
        if len(packet) >= 5 or chunk.source_chunk_id in seen_chunk_ids:
            continue
        packet.append(
            {
                "evidence_card_id": None,
                "source_chunk_id": chunk.source_chunk_id,
                "paper_id": chunk.paper_id,
                "page": str(chunk.page_start),
                "section": chunk.section_type,
                "quote": chunk.text[:1800],
            }
        )
    return packet
