from app.models.schemas import CitationBinding
from app.services.citation_matcher import resolve_claim_citations


def test_numeric_citations_resolve_only_the_bound_papers() -> None:
    paper_ids, unmapped = resolve_claim_citations(
        claim_text="The method improves retrieval accuracy [1, 2].",
        citation_bindings=[
            CitationBinding(marker="[1]", paper_id="paper-one"),
            CitationBinding(marker="[2]", paper_id="paper-two"),
        ],
        fallback_paper_ids=["paper-one", "paper-two", "paper-three"],
    )

    assert paper_ids == ["paper-one", "paper-two"]
    assert unmapped == []


def test_unmapped_citation_marker_is_reported() -> None:
    paper_ids, unmapped = resolve_claim_citations(
        claim_text="The method improves retrieval accuracy [3].",
        citation_bindings=[CitationBinding(marker="[1]", paper_id="paper-one")],
        fallback_paper_ids=["paper-one"],
    )

    assert paper_ids == []
    assert unmapped == ["[3]"]


def test_author_year_citation_resolves_a_manual_binding() -> None:
    paper_ids, unmapped = resolve_claim_citations(
        claim_text="The method is effective (Wang, 2024).",
        citation_bindings=[CitationBinding(marker="(Wang, 2024)", paper_id="wang-2024")],
        fallback_paper_ids=[],
    )

    assert paper_ids == ["wang-2024"]
    assert unmapped == []


def test_enforced_bindings_do_not_fall_back_to_every_uploaded_paper() -> None:
    paper_ids, unmapped = resolve_claim_citations(
        claim_text="The method improves retrieval accuracy [3].",
        citation_bindings=[],
        fallback_paper_ids=["paper-one", "paper-two"],
        enforce_bindings=True,
    )

    assert paper_ids == []
    assert unmapped == ["[3]"]
