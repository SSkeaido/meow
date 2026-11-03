import re

from app.models.schemas import CitationBindingSuggestion, Paper
from app.services.citation_matcher import extract_citation_markers


_NUMBERED_REFERENCE_RE = re.compile(r"(?ms)^\s*\[(\d+)\]\s*(.+?)(?=^\s*\[\d+\]|\Z)")
_TOKEN_RE = re.compile(r"[a-z0-9]{2,}", re.IGNORECASE)


def suggest_citation_bindings(text: str, papers: list[Paper]) -> list[CitationBindingSuggestion]:
    references = {f"[{number}]": entry for number, entry in _NUMBERED_REFERENCE_RE.findall(text)}
    suggestions: list[CitationBindingSuggestion] = []
    for marker in sorted(extract_citation_markers(text)):
        reference_text = references.get(marker, marker)
        paper, confidence = _best_paper(reference_text, papers)
        if paper and confidence >= 0.32:
            source = "numbered reference entry" if marker in references else "author-year marker"
            suggestions.append(
                CitationBindingSuggestion(
                    marker=marker,
                    paper_id=paper.id,
                    confidence=round(confidence, 3),
                    reason=f"Matched {source} against PDF title, filename, authors, and year.",
                )
            )
        else:
            suggestions.append(
                CitationBindingSuggestion(
                    marker=marker,
                    confidence=round(confidence, 3),
                    reason="No uploaded PDF had sufficient metadata or filename overlap.",
                )
            )
    return suggestions


def _best_paper(reference_text: str, papers: list[Paper]) -> tuple[Paper | None, float]:
    reference_tokens = _tokens(reference_text)
    if not reference_tokens:
        return None, 0.0
    best_paper: Paper | None = None
    best_score = 0.0
    for paper in papers:
        metadata = paper.metadata
        candidate = " ".join(
            [
                paper.title,
                paper.original_filename.rsplit(".", 1)[0],
                str(metadata.get("authors", "")),
                str(metadata.get("year", "")),
            ]
        )
        candidate_tokens = _tokens(candidate)
        overlap = len(reference_tokens & candidate_tokens)
        if not overlap:
            continue
        score = overlap / max(1, min(len(reference_tokens), len(candidate_tokens)))
        if paper.title and paper.title.casefold() in reference_text.casefold():
            score = max(score, 0.95)
        if score > best_score:
            best_paper, best_score = paper, score
    return best_paper, best_score


def _tokens(value: str) -> set[str]:
    return {token.casefold() for token in _TOKEN_RE.findall(value)}
