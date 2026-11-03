from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.models.schemas import SourceChunk
from app.pdf.cleaner import clean_page_text, estimate_tokens


SECTION_KEYWORDS = {
    "abstract": "abstract",
    "introduction": "introduction",
    "method": "method",
    "methods": "method",
    "materials and methods": "method",
    "result": "result",
    "results": "result",
    "discussion": "discussion",
    "conclusion": "conclusion",
    "conclusions": "conclusion",
    "limitation": "limitation",
    "limitations": "limitation",
    "references": "reference",
}


def infer_section_type(text: str) -> str:
    for line in text.splitlines()[:8]:
        section_type = _heading_section_type(line)
        if section_type:
            return section_type
    return "unknown"


def split_page_sections(text: str, initial_section_type: str) -> tuple[list[tuple[str, str]], str]:
    """Split a page at recognizable headings while carrying the active section across pages."""
    current_section_type = initial_section_type
    segments: list[tuple[str, list[str]]] = []
    for line in text.splitlines():
        heading_section_type = _heading_section_type(line)
        if heading_section_type:
            current_section_type = heading_section_type
        if not segments or segments[-1][0] != current_section_type:
            segments.append((current_section_type, []))
        segments[-1][1].append(line)
    return [(section_type, "\n".join(lines)) for section_type, lines in segments if "\n".join(lines).strip()], current_section_type


def _heading_section_type(line: str) -> str | None:
    candidate = line.strip().lower().rstrip(":.")
    candidate = candidate.lstrip("0123456789. ")
    if len(candidate) > 48:
        return None
    for keyword, section_type in SECTION_KEYWORDS.items():
        if candidate == keyword:
            return section_type
    return None


def split_pages_to_chunks(project_id: str, paper_id: str, pages: list) -> list[SourceChunk]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=3500,
        chunk_overlap=400,
        separators=["\n\n", "\n", ". ", "; ", " "],
    )
    chunks: list[SourceChunk] = []
    current_section_type = "unknown"

    for page_doc in pages:
        page_number = int(page_doc.metadata.get("page", 0)) + 1
        page_sections, current_section_type = split_page_sections(page_doc.page_content, current_section_type)
        for section_type, section_text in page_sections:
            cleaned = clean_page_text(section_text)
            if len(cleaned) < 80:
                continue

            for text in splitter.split_text(cleaned):
                chunks.append(
                    SourceChunk(
                        project_id=project_id,
                        paper_id=paper_id,
                        chunk_index=len(chunks),
                        page_start=page_number,
                        page_end=page_number,
                        section=section_type,
                        section_type=section_type,
                        text=text,
                        cleaned_text=text,
                        token_estimate=estimate_tokens(text),
                        metadata={"source": page_doc.metadata.get("source", "")},
                    )
                )

    return chunks
