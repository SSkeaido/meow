from app.pdf.metadata import _title_from_first_page


def test_title_falls_back_to_the_first_substantial_page_line() -> None:
    text = "\nA Citation-Grounded Workflow for Auditing Academic Claims\nJane Example\nAbstract\nThis study evaluates citation checking."

    assert _title_from_first_page(text) == "A Citation-Grounded Workflow for Auditing Academic Claims"
