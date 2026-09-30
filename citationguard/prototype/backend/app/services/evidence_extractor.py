from app.models.schemas import EvidenceCard, Paper, SourceChunk


CORE_SECTIONS = {
    "abstract",
    "introduction",
    "method",
    "result",
    "discussion",
    "conclusion",
    "limitation",
}


class HeuristicEvidenceExtractor:
    """Placeholder extractor until the LangChain structured-output chain is wired."""

    def generate(self, paper: Paper, chunks: list[SourceChunk]) -> list[EvidenceCard]:
        selected = [chunk for chunk in chunks if chunk.section_type in CORE_SECTIONS]
        if not selected:
            selected = chunks[:8]

        cards: list[EvidenceCard] = []
        for chunk in selected[:12]:
            quote = _first_sentence(chunk.cleaned_text)
            if len(quote) < 40:
                quote = chunk.cleaned_text[:280].strip()
            cards.append(
                EvidenceCard(
                    project_id=paper.project_id,
                    paper_id=paper.id,
                    source_chunk_id=chunk.id,
                    claim_type=_claim_type_from_section(chunk.section_type),
                    summary=_summarize_heuristic(quote),
                    source_quote=quote,
                    page=chunk.page_start,
                    section=chunk.section_type,
                    support_scope="This evidence may support a narrow claim grounded in the quoted source text.",
                    limitations="Heuristic extraction only; requires LLM verification before scholarly use.",
                    confidence=0.35,
                )
            )
        return cards


def _first_sentence(text: str) -> str:
    for sep in [". ", "? ", "! "]:
        if sep in text:
            return text.split(sep, 1)[0].strip() + sep.strip()
    return text[:320].strip()


def _summarize_heuristic(quote: str) -> str:
    return quote[:240].strip()


def _claim_type_from_section(section_type: str) -> str:
    return {
        "method": "method",
        "result": "result",
        "discussion": "result",
        "limitation": "limitation",
        "introduction": "background",
        "abstract": "background",
        "conclusion": "future_work",
    }.get(section_type, "background")


evidence_extractor = HeuristicEvidenceExtractor()

