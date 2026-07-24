import pytest


@pytest.fixture(autouse=True)
def isolate_tests_from_external_models(monkeypatch):
    """Unit tests must never spend API credits because a developer has a local .env."""
    monkeypatch.setenv("EMBEDDING_PROVIDER", "hash")
    monkeypatch.setenv("RERANK_PROVIDER", "disabled")
    monkeypatch.setenv("CLAIM_EXTRACTION_PROVIDER", "heuristic")
    monkeypatch.setenv("LLM_PROVIDER", "heuristic")
    monkeypatch.setenv("OCR_PROVIDER", "disabled")
    monkeypatch.setenv("ACCESS_KEY_REQUIRED", "false")
