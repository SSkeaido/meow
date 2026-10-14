import re
from pathlib import Path

import fitz
from langchain_core.documents import Document


_GENERIC_TITLES = {"", "untitled", "unknown", "microsoft word", "latex"}
_ABSTRACT_RE = re.compile(
    r"(?is)\babstract\b\s*[:.-]?\s*(.{80,2500}?)(?=\b(?:keywords?|introduction|1[.\s]+introduction)\b|$)"
)
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


def extract_paper_metadata(path: Path, pages: list[Document]) -> dict[str, str]:
    """Extract conservative metadata without relying on an LLM or an external service."""
    with fitz.open(str(path)) as document:
        raw_metadata = document.metadata or {}
    first_page = pages[0].page_content if pages else ""
    title = _usable(raw_metadata.get("title", "")) or _title_from_first_page(first_page)
    author = _usable(raw_metadata.get("author", ""))
    creation_date = _usable(raw_metadata.get("creationDate", ""))
    year_match = _YEAR_RE.search(creation_date or first_page[:2000])
    abstract_match = _ABSTRACT_RE.search(first_page)

    metadata = {
        "title": title,
        "authors": author,
        "year": year_match.group(0) if year_match else "",
        "abstract": " ".join(abstract_match.group(1).split()) if abstract_match else "",
        "pdf_title": _usable(raw_metadata.get("title", "")),
        "pdf_author": author,
    }
    return {key: value for key, value in metadata.items() if value}


def _title_from_first_page(text: str) -> str:
    lines = [" ".join(line.split()) for line in text.splitlines() if line.strip()]
    candidates = [line for line in lines[:12] if 12 <= len(line) <= 240]
    if not candidates:
        return ""
    # Academic titles are usually the first substantial non-boilerplate line on page one.
    return max(candidates[:5], key=lambda line: (sum(char.isalpha() for char in line), len(line)))


def _usable(value: str) -> str:
    normalized = " ".join(value.split())
    return "" if normalized.casefold() in _GENERIC_TITLES else normalized
