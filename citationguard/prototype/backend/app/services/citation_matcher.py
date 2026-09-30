import re

from app.models.schemas import CitationBinding


_NUMERIC_CITATION_RE = re.compile(r"\[([^\]]+)\]")
_AUTHOR_YEAR_CITATION_RE = re.compile(r"\(([^)]*\d{4}[a-z]?[^)]*)\)", re.IGNORECASE)


def resolve_claim_citations(
    claim_text: str,
    citation_bindings: list[CitationBinding],
    fallback_paper_ids: list[str],
    enforce_bindings: bool = False,
) -> tuple[list[str], list[str]]:
    """Return paper IDs explicitly tied to a claim and any unbound citation markers."""
    if not citation_bindings and not enforce_bindings:
        return list(dict.fromkeys(fallback_paper_ids)), []

    normalized_claim = _normalize(claim_text)
    marker_to_paper = {_normalize(binding.marker): binding.paper_id for binding in citation_bindings}
    markers = extract_citation_markers(claim_text)
    for marker in marker_to_paper:
        if marker and marker in normalized_claim:
            markers.add(marker)

    cited_paper_ids: list[str] = []
    unmapped_markers: list[str] = []
    for marker in sorted(markers):
        paper_id = marker_to_paper.get(_normalize(marker))
        if paper_id:
            cited_paper_ids.append(paper_id)
        else:
            unmapped_markers.append(marker)
    return list(dict.fromkeys(cited_paper_ids)), unmapped_markers


def extract_citation_markers(text: str) -> set[str]:
    markers: set[str] = set()
    for match in _NUMERIC_CITATION_RE.finditer(text):
        for token in re.split(r"[,;，；]", match.group(1)):
            token = token.strip()
            range_match = re.fullmatch(r"(\d+)\s*[-–]\s*(\d+)", token)
            if range_match:
                start, end = (int(value) for value in range_match.groups())
                if end - start <= 20:
                    markers.update(f"[{index}]" for index in range(start, end + 1))
                continue
            if token.isdigit():
                markers.add(f"[{token}]")
    for match in _AUTHOR_YEAR_CITATION_RE.finditer(text):
        markers.add(match.group(0))
    return markers


def _normalize(value: str) -> str:
    return re.sub(r"\s+", "", value).casefold()
