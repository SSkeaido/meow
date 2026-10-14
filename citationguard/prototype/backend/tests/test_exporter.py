from app.models.schemas import AuditRun, ClaimBatch, PersistedAuditResult
from app.services.exporter import audit_report_markdown, audit_results_csv


def _result() -> PersistedAuditResult:
    return PersistedAuditResult(
        audit_run_id="run-1",
        project_id="project-1",
        review_claim_id="claim-1",
        claim_text="A supported claim.",
        cited_paper_ids=["paper-1"],
        supporting_evidence_ids=["evidence-1"],
        support_level="CHECK",
        risk_flags=[],
        explanation="Evidence is narrow.",
        suggested_fix="Keep the scope narrow.",
    )


def test_audit_exports_include_claim_content() -> None:
    batch = ClaimBatch(id="batch-1", project_id="project-1", status="audited")
    audit_run = AuditRun(id="run-1", project_id="project-1", claim_batch_id=batch.id)
    result = _result()

    markdown = audit_report_markdown(batch, audit_run, [result])
    csv_output = audit_results_csv([result])

    assert "A supported claim." in markdown
    assert "claim_text" in csv_output
    assert "A supported claim." in csv_output
