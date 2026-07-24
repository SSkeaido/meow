import os
from pathlib import Path

from langchain_community.document_loaders import PyMuPDFLoader
from langchain_core.documents import Document


def load_pdf_pages(path: Path) -> list[Document]:
    loader = PyMuPDFLoader(str(path))
    pages = loader.load()
    if os.getenv("OCR_PROVIDER", "disabled").lower() != "siliconflow":
        return pages

    from app.integrations.siliconflow import SiliconFlowOcr

    minimum_characters = int(os.getenv("OCR_MIN_TEXT_CHARACTERS", "80"))
    max_pages = int(os.getenv("OCR_MAX_PAGES", "10"))
    sparse_pages = [
        (page_index, page)
        for page_index, page in enumerate(pages)
        if len(page.page_content.strip()) < minimum_characters
    ][:max_pages]
    if not sparse_pages:
        return pages

    ocr = SiliconFlowOcr()
    for page_index, page in sparse_pages:
        try:
            extracted_text = ocr.extract_page(str(path), page_index)
        except Exception:
            # Preserve the original page so deterministic parsing remains usable if OCR is unavailable.
            continue
        if extracted_text:
            page.page_content = extracted_text
            page.metadata["ocr_provider"] = "siliconflow"
            page.metadata["ocr_model"] = ocr.model_name
    return pages
