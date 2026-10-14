from app.models.schemas import EvidenceCard, Paper, ReviewSkillRequest
from app.services.reviewer_skills import ReviewerSkillRunner


def test_reviewer_runner_returns_card_findings_and_score(monkeypatch) -> None:
    paper = Paper(
        id="paper-1",
        project_id="project-1",
        title="Evidence paper",
        original_filename="evidence.pdf",
        file_hash="hash",
        page_count=4,
    )
    card = EvidenceCard(
        project_id="project-1",
        paper_id="paper-1",
        source_chunk_id="chunk-1",
        claim_type="result",
        summary="The proposed method improves accuracy on the dataset.",
        source_quote="Our method improves accuracy over the baseline.",
        page=2,
        section="Results",
        support_scope="accuracy result",
        limitations="small sample",
    )
    monkeypatch.setattr("app.services.reviewer_skills.store.list_project_papers", lambda _: [paper])
    monkeypatch.setattr(
        "app.services.reviewer_skills.store.list_project_evidence_cards",
        lambda _: [card],
    )

    result = ReviewerSkillRunner().run(
        "project-1",
        ReviewSkillRequest(
            manuscript_text=(
                "A novel method improves accuracy. We propose a framework. "
                "The method uses a dataset and reports a metric against a baseline."
            ),
            cited_paper_ids=["paper-1"],
        ),
    )

    assert result.project_id == "project-1"
    assert result.paper_card.title.startswith("A novel method")
    assert set(result.skill_ids) == {
        "paper-distillation",
        "methodology-review",
        "experiment-reproducibility-review",
        "adversarial-review",
    }
    assert result.findings
    assert 0 <= result.summary.readiness_score <= 100


def test_reviewer_runner_links_findings_to_reference_evidence(monkeypatch) -> None:
    card = EvidenceCard(
        project_id="project-1",
        paper_id="paper-1",
        source_chunk_id="chunk-1",
        claim_type="result",
        summary="A novel method improves accuracy.",
        source_quote="A novel method improves accuracy over the baseline.",
        page=3,
        section="Results",
        support_scope="accuracy",
        limitations="",
    )
    monkeypatch.setattr("app.services.reviewer_skills.store.list_project_papers", lambda _: [])
    monkeypatch.setattr(
        "app.services.reviewer_skills.store.list_project_evidence_cards",
        lambda _: [card],
    )

    result = ReviewerSkillRunner().run(
        "project-1",
        ReviewSkillRequest(
            manuscript_text="A novel method improves accuracy.",
            cited_paper_ids=["paper-1"],
            skill_ids=["adversarial-review"],
        ),
    )

    assert result.findings
    refs = result.findings[0].evidence_refs
    assert refs and refs[0].source == "reference"
    assert refs[0].paper_id == "paper-1"
    assert refs[0].page == 3
