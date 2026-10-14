import re

from app.models.schemas import (
    AuditRequest,
    AuditRun,
    BatchAuditResponse,
    CitationLedgerEntry,
    ClaimBatch,
    ClaimBatchCreate,
    PersistedAuditResult,
    ReviewClaim,
    ReviewParagraph,
)
from app.rag.retriever import chunk_retriever
from app.services.audit_engine import get_citation_auditor
from app.services.citation_matcher import resolve_claim_citations
from app.services.claim_extractor import get_claim_extractor
from app.services.store import store


_PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n+")
_CLAIM_SPLIT_RE = re.compile(r"(?<=[.!?。！？])\s+")


class AuditWorkflow:
    def audit_batch(self, project_id: str, payload: ClaimBatchCreate) -> BatchAuditResponse:
        store.get_project(project_id)
        batch = ClaimBatch(
            project_id=project_id,
            source_label=payload.source_label,
            language=payload.language,
            source=payload.source,
            status="audited",
        )
        paragraphs = self._build_paragraphs(batch=batch, text=payload.text, source=payload.source)
        claim_extractor = get_claim_extractor()
        claims = self._build_claims(
            paragraphs=paragraphs,
            cited_paper_ids=payload.cited_paper_ids,
            claim_extractor=claim_extractor,
        )
        citation_auditor = get_citation_auditor()
        audit_run = AuditRun(
            project_id=project_id,
            claim_batch_id=batch.id,
            model_provider=citation_auditor.provider,
            model_name=f"claim={claim_extractor.model_name}; audit={citation_auditor.model_name}",
        )
        evidence_cards = store.list_project_evidence_cards(project_id=project_id)
        project_paper_ids = {paper.id for paper in store.list_project_papers(project_id)}

        results: list[PersistedAuditResult] = []
        ledger_entries: list[CitationLedgerEntry] = []
        for claim in claims:
            cited_paper_ids, unmapped_markers = resolve_claim_citations(
                claim_text=claim.claim_text,
                citation_bindings=payload.citation_bindings,
                fallback_paper_ids=payload.cited_paper_ids,
                enforce_bindings=payload.enforce_citation_bindings,
            )
            claim.cited_paper_ids = cited_paper_ids
            retrieved_chunks = chunk_retriever.retrieve(
                query=claim.claim_text,
                project_id=project_id,
                paper_ids=cited_paper_ids,
                k=payload.top_k,
            )
            audit_result = citation_auditor.audit_claim(
                project_id=project_id,
                payload=AuditRequest(
                    claim_text=claim.claim_text,
                    cited_paper_ids=cited_paper_ids,
                    top_k=payload.top_k,
                ),
                evidence_cards=evidence_cards,
                retrieved_chunks=retrieved_chunks,
                invalid_cited_paper_ids=set(cited_paper_ids) - project_paper_ids,
                unmapped_citation_markers=unmapped_markers,
            )
            claim.evidence_card_ids = audit_result.supporting_evidence_ids
            result = PersistedAuditResult(
                **audit_result.model_dump(),
                audit_run_id=audit_run.id,
                project_id=project_id,
                review_claim_id=claim.id,
                sent_payload_summary=citation_auditor.sent_payload_summary,
            )
            results.append(result)
            for paper_id in claim.cited_paper_ids:
                ledger_entries.append(
                    CitationLedgerEntry(
                        project_id=project_id,
                        claim_batch_id=batch.id,
                        review_paragraph_id=claim.review_paragraph_id,
                        review_claim_id=claim.id,
                        paper_id=paper_id,
                        evidence_card_id=result.supporting_evidence_ids[0] if result.supporting_evidence_ids else None,
                        last_audit_status=result.support_level,
                    )
                )

        store.save_audit_batch(
            batch=batch,
            paragraphs=paragraphs,
            claims=claims,
            audit_run=audit_run,
            results=results,
            ledger_entries=ledger_entries,
        )
        return BatchAuditResponse(
            batch=batch,
            audit_run=audit_run,
            paragraph_count=len(paragraphs),
            claim_count=len(claims),
            results=results,
        )

    @staticmethod
    def _build_paragraphs(batch: ClaimBatch, text: str, source: str) -> list[ReviewParagraph]:
        raw_paragraphs = [item.strip() for item in _PARAGRAPH_SPLIT_RE.split(text) if item.strip()]
        return [
            ReviewParagraph(
                claim_batch_id=batch.id,
                project_id=batch.project_id,
                paragraph_index=index,
                text=paragraph,
                source=source,
            )
            for index, paragraph in enumerate(raw_paragraphs)
        ]

    @staticmethod
    def _build_claims(paragraphs: list[ReviewParagraph], cited_paper_ids: list[str], claim_extractor) -> list[ReviewClaim]:
        claims: list[ReviewClaim] = []
        for paragraph in paragraphs:
            extracted_claims = claim_extractor.extract(paragraph.text)
            for claim_index, extracted_claim in enumerate(extracted_claims):
                claims.append(
                    ReviewClaim(
                        review_paragraph_id=paragraph.id,
                        project_id=paragraph.project_id,
                        claim_index=claim_index,
                        claim_text=extracted_claim.claim_text,
                        normalized_claim=" ".join(extracted_claim.claim_text.lower().split()),
                        claim_type=extracted_claim.claim_type,
                        strength=extracted_claim.strength,
                        cited_paper_ids=cited_paper_ids,
                    )
                )
        return claims


audit_workflow = AuditWorkflow()
