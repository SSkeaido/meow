from app.models.schemas import Paper
from app.services.citation_suggester import suggest_citation_bindings


def test_numbered_reference_entry_matches_a_pdf_title() -> None:
    paper = Paper(
        id="paper-1",
        project_id="project-1",
        title="Citation Grounded Auditing for Academic Claims",
        original_filename="citation-grounded-auditing.pdf",
        file_hash="hash",
        page_count=10,
        metadata={"authors": "Wang Li", "year": "2024"},
    )
    text = "The proposed workflow improves traceability [1].\n\nReferences\n[1] Wang Li. Citation Grounded Auditing for Academic Claims. 2024."

    suggestions = suggest_citation_bindings(text, [paper])

    assert suggestions[0].marker == "[1]"
    assert suggestions[0].paper_id == paper.id
    assert suggestions[0].confidence >= 0.9


def test_unmatched_marker_remains_visible_for_user_confirmation() -> None:
    paper = Paper(
        id="paper-1",
        project_id="project-1",
        title="Unrelated Paper",
        original_filename="unrelated.pdf",
        file_hash="hash",
        page_count=1,
    )

    suggestions = suggest_citation_bindings("This claim cites [2].", [paper])

    assert suggestions[0].marker == "[2]"
    assert suggestions[0].paper_id is None
