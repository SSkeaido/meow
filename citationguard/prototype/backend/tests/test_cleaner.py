from app.pdf.cleaner import clean_page_text, estimate_tokens
from app.pdf.loader import load_pdf_pages
from app.pdf.splitter import split_page_sections


def test_clean_page_text_merges_broken_hyphen() -> None:
    text = "citation-\ngrounded review"
    assert clean_page_text(text) == "citationgrounded review"


def test_estimate_tokens_returns_positive_value() -> None:
    assert estimate_tokens("short") >= 1


def test_pdf_loader_keeps_deterministic_parsing_when_ocr_is_disabled(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OCR_PROVIDER", "disabled")
    expected_pages = [object()]

    class FakeLoader:
        def __init__(self, path: str) -> None:
            self.path = path

        def load(self):
            return expected_pages

    monkeypatch.setattr("app.pdf.loader.PyMuPDFLoader", FakeLoader)

    assert load_pdf_pages(tmp_path / "not-used.pdf") is expected_pages


def test_section_detection_carries_a_heading_to_the_next_page() -> None:
    first_page, section_type = split_page_sections("Results\n" + "result text " * 20, "unknown")
    second_page, next_section_type = split_page_sections("continued result text " * 20, section_type)

    assert first_page[0][0] == "result"
    assert second_page[0][0] == "result"
    assert next_section_type == "result"
