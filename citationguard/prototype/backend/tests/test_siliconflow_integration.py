import pytest

from app.integrations.siliconflow import SiliconFlowSettings
from app.services.claim_extractor import get_claim_extractor


def test_siliconflow_settings_require_an_api_key(monkeypatch) -> None:
    monkeypatch.delenv("SILICONFLOW_API_KEY", raising=False)

    with pytest.raises(ValueError, match="SILICONFLOW_API_KEY"):
        SiliconFlowSettings.from_env()


def test_claim_extractor_defaults_to_local_mode(monkeypatch) -> None:
    monkeypatch.setenv("CLAIM_EXTRACTION_PROVIDER", "heuristic")

    extractor = get_claim_extractor()

    assert extractor.provider == "heuristic"
    assert len(extractor.extract("This result improves the benchmark metric.")) == 1
