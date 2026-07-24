from app.models.schemas import EvidenceCard, SourceChunk
from app.services.evidence_validator import is_source_verified, validate_evidence_cards


def _chunk() -> SourceChunk:
    return SourceChunk(
        id="chunk-1",
        project_id="project-1",
        paper_id="paper-1",
        chunk_index=0,
        page_start=4,
        page_end=4,
        text="The method improves retrieval performance on the benchmark dataset.",
        cleaned_text="The method improves retrieval performance on the benchmark dataset.",
        token_estimate=16,
    )


def _card(quote: str) -> EvidenceCard:
    return EvidenceCard(
        id="card-1",
        project_id="project-1",
        paper_id="paper-1",
        source_chunk_id="chunk-1",
        claim_type="result",
        summary="Benchmark result",
        source_quote=quote,
        page=4,
        section="result",
        support_scope="benchmark dataset",
        limitations="fixture",
    )


def test_quote_validation_accepts_a_traceable_quote() -> None:
    card = validate_evidence_cards([_card("The method improves retrieval performance on the benchmark dataset.")], [_chunk()])[0]

    assert card.validation_flags == []
    assert is_source_verified(card)


def test_quote_validation_flags_untraceable_quote() -> None:
    card = validate_evidence_cards([_card("The method improves all clinical outcomes.")], [_chunk()])[0]

    assert card.validation_flags == ["quote_not_found"]
    assert not is_source_verified(card)
