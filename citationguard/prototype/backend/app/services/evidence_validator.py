from app.models.schemas import EvidenceCard, SourceChunk


def validate_evidence_cards(cards: list[EvidenceCard], chunks: list[SourceChunk]) -> list[EvidenceCard]:
    """Retain cards for inspection, but clearly mark quotes that cannot be traced to source text."""
    chunks_by_id = {chunk.id: chunk for chunk in chunks}
    validated: list[EvidenceCard] = []
    for card in cards:
        chunk = chunks_by_id.get(card.source_chunk_id)
        flags = [flag for flag in card.validation_flags if flag != "quote_not_found"]
        if not chunk or not _quote_exists(card.source_quote, chunk):
            flags.append("quote_not_found")
        validated.append(card.model_copy(update={"validation_flags": flags}))
    return validated


def is_source_verified(card: EvidenceCard) -> bool:
    return "quote_not_found" not in card.validation_flags


def _quote_exists(quote: str, chunk: SourceChunk) -> bool:
    normalized_quote = " ".join(quote.split())
    if not normalized_quote:
        return False
    return normalized_quote in " ".join(chunk.text.split()) or normalized_quote in " ".join(chunk.cleaned_text.split())
