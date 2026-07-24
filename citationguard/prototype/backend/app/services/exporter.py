import csv
from io import StringIO

from app.models.schemas import AuditRun, CitationLedgerEntry, ClaimBatch, EvidenceCard, PersistedAuditResult


def audit_report_markdown(batch: ClaimBatch, audit_run: AuditRun, results: list[PersistedAuditResult]) -> str:
    lines = [
        "# Citation Audit Report",
        "",
        f"- Batch: `{batch.id}`",
        f"- Source: {batch.source_label or 'unspecified'}",
        f"- Model: {audit_run.model_provider} / {audit_run.model_name}",
        f"- Status: {audit_run.status}",
        "",
        "## Claim Results",
        "",
    ]
    for index, result in enumerate(results, start=1):
        lines.extend(
            [
                f"### {index}. {result.support_level}",
                "",
                result.claim_text,
                "",
                f"- Risk flags: {', '.join(result.risk_flags) or 'none'}",
                f"- Evidence cards: {', '.join(result.supporting_evidence_ids) or 'none'}",
                f"- Source chunks: {', '.join(result.supporting_source_chunk_ids) or 'none'}",
                f"- Explanation: {result.explanation}",
                f"- Suggested fix: {result.suggested_fix}",
                "",
            ]
        )
    return "\n".join(lines)


def audit_results_csv(results: list[PersistedAuditResult]) -> str:
    rows = [
        {
            "claim_text": result.claim_text,
            "support_level": result.support_level,
            "risk_flags": "; ".join(result.risk_flags),
            "cited_paper_ids": "; ".join(result.cited_paper_ids),
            "supporting_evidence_ids": "; ".join(result.supporting_evidence_ids),
            "supporting_source_chunk_ids": "; ".join(result.supporting_source_chunk_ids),
            "explanation": result.explanation,
            "suggested_fix": result.suggested_fix,
        }
        for result in results
    ]
    return _to_csv(rows)


def evidence_cards_csv(cards: list[EvidenceCard]) -> str:
    rows = [
        {
            "paper_id": card.paper_id,
            "claim_type": card.claim_type,
            "summary": card.summary,
            "source_quote": card.source_quote,
            "section": card.section,
            "page": card.page,
            "confidence": card.confidence,
            "validation_flags": "; ".join(card.validation_flags),
        }
        for card in cards
    ]
    return _to_csv(rows)


def citation_ledger_csv(entries: list[CitationLedgerEntry]) -> str:
    rows = [
        {
            "review_claim_id": entry.review_claim_id,
            "paper_id": entry.paper_id,
            "evidence_card_id": entry.evidence_card_id or "",
            "citation_key": entry.citation_key,
            "usage_type": entry.usage_type,
            "last_audit_status": entry.last_audit_status,
            "last_audited_at": entry.last_audited_at.isoformat(),
        }
        for entry in entries
    ]
    return _to_csv(rows)


def _to_csv(rows: list[dict[str, object]]) -> str:
    if not rows:
        return ""
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()
