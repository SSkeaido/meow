from app.models.schemas import AuditRequest, EvidenceCard
from app.services.audit_engine import HighRiskReviewingAuditor
from app.services.auditor import citation_auditor


def test_auditor_flags_missing_evidence() -> None:
    result = citation_auditor.audit_claim(
        project_id="p1",
        payload=AuditRequest(claim_text="This claim has no support."),
        evidence_cards=[],
    )
    assert result.support_level == "FAIL"
    assert "unsupported_claim" in result.risk_flags


def test_auditor_returns_candidate_evidence() -> None:
    card = EvidenceCard(
        project_id="p1",
        paper_id="paper1",
        source_chunk_id="chunk1",
        claim_type="method",
        summary="Transformer models improve retrieval performance.",
        source_quote="Transformer models improve retrieval performance in benchmark experiments.",
        page=1,
        section="result",
        support_scope="benchmark experiments",
        limitations="single benchmark",
    )
    result = citation_auditor.audit_claim(
        project_id="p1",
        payload=AuditRequest(claim_text="Transformer models improve retrieval performance.", cited_paper_ids=["paper1"]),
        evidence_cards=[card],
    )
    assert result.supporting_evidence_ids == [card.id]
    assert result.support_level == "CHECK"


def test_auditor_flags_a_claim_without_a_citation() -> None:
    card = EvidenceCard(
        project_id="p1",
        paper_id="paper1",
        source_chunk_id="chunk1",
        claim_type="result",
        summary="Transformer retrieval models improve benchmark performance.",
        source_quote="Transformer retrieval models improve benchmark performance.",
        page=1,
        section="result",
        support_scope="benchmark",
        limitations="test fixture",
    )
    result = citation_auditor.audit_claim(
        project_id="p1",
        payload=AuditRequest(claim_text="Transformer retrieval models improve benchmark performance."),
        evidence_cards=[card],
    )
    assert result.support_level == "RISK"
    assert "missing_citation" in result.risk_flags


def test_high_risk_review_never_upgrades_a_disputed_claim_to_pass() -> None:
    class Primary:
        model_name = "primary"

        @staticmethod
        def audit_claim(**kwargs):
            return citation_auditor.audit_claim(
                project_id="p1",
                payload=AuditRequest(claim_text="No support."),
                evidence_cards=[],
            ).model_copy(update={"support_level": "RISK", "risk_flags": ["causal_overclaim"]})

    class Reviewer:
        model_name = "reviewer"

        @staticmethod
        def audit_claim(**kwargs):
            return citation_auditor.audit_claim(
                project_id="p1",
                payload=AuditRequest(claim_text="No support."),
                evidence_cards=[],
            ).model_copy(update={"support_level": "PASS", "risk_flags": []})

    result = HighRiskReviewingAuditor(Primary(), Reviewer()).audit_claim()

    assert result.support_level == "CHECK"
    assert "causal_overclaim" in result.risk_flags


def test_auditor_flags_an_unbound_citation_marker() -> None:
    result = citation_auditor.audit_claim(
        project_id="p1",
        payload=AuditRequest(claim_text="A claim [4].", cited_paper_ids=[]),
        evidence_cards=[],
        unmapped_citation_markers=["[4]"],
    )

    assert result.support_level == "RISK"
    assert result.risk_flags == ["citation_marker_unmapped"]


def test_auditor_excludes_evidence_with_an_untraceable_quote() -> None:
    card = EvidenceCard(
        project_id="p1",
        paper_id="paper1",
        source_chunk_id="chunk1",
        claim_type="result",
        summary="Transformer models improve retrieval performance.",
        source_quote="Transformer models improve retrieval performance in benchmark experiments.",
        page=1,
        section="result",
        support_scope="benchmark experiments",
        limitations="single benchmark",
        validation_flags=["quote_not_found"],
    )
    result = citation_auditor.audit_claim(
        project_id="p1",
        payload=AuditRequest(claim_text="Transformer models improve retrieval performance.", cited_paper_ids=["paper1"]),
        evidence_cards=[card],
    )

    assert result.supporting_evidence_ids == []
