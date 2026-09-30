import os
from functools import lru_cache

from app.integrations.siliconflow import SiliconFlowSettings
from app.llm.citation_audit import LangChainCitationAuditor
from app.services.auditor import HeuristicCitationAuditor


class HighRiskReviewingAuditor:
    """Escalate only primary RISK verdicts to the stronger reviewer model."""

    provider = "siliconflow"
    sent_payload_summary = "claim plus up to five retrieved evidence snippets; high-risk claims receive one reviewer pass"

    def __init__(self, primary: LangChainCitationAuditor, reviewer: LangChainCitationAuditor) -> None:
        self.primary = primary
        self.reviewer = reviewer
        self.model_name = f"{primary.model_name}; reviewer={reviewer.model_name}"

    def audit_claim(self, **kwargs):
        primary_result = self.primary.audit_claim(**kwargs)
        if primary_result.support_level != "RISK":
            return primary_result
        reviewer_result = self.reviewer.audit_claim(**kwargs)
        # A reviewer can reduce a risk only to CHECK. A PASS after a disagreement is not sufficiently conservative.
        support_level = "CHECK" if reviewer_result.support_level == "PASS" else reviewer_result.support_level
        return reviewer_result.model_copy(
            update={
                "support_level": support_level,
                "risk_flags": list(dict.fromkeys(primary_result.risk_flags + reviewer_result.risk_flags)),
                "explanation": f"Primary audit: {primary_result.explanation}\nHigh-risk review: {reviewer_result.explanation}",
            }
        )


@lru_cache(maxsize=1)
def get_citation_auditor() -> HeuristicCitationAuditor | LangChainCitationAuditor:
    provider = os.getenv("LLM_PROVIDER", "heuristic").lower()
    if provider == "heuristic":
        return HeuristicCitationAuditor()
    if provider == "openai_compatible":
        return LangChainCitationAuditor()
    if provider == "siliconflow":
        settings = SiliconFlowSettings.from_env()
        primary = LangChainCitationAuditor(
            provider="siliconflow",
            model_name=settings.audit_model,
            api_key=settings.api_key,
            base_url=settings.base_url,
        )
        if os.getenv("SILICONFLOW_ENABLE_RISK_REVIEW", "true").lower() != "true":
            return primary
        reviewer = LangChainCitationAuditor(
            provider="siliconflow",
            model_name=settings.reviewer_model,
            api_key=settings.api_key,
            base_url=settings.base_url,
        )
        return HighRiskReviewingAuditor(primary=primary, reviewer=reviewer)
    raise ValueError("LLM_PROVIDER must be 'heuristic', 'openai_compatible', or 'siliconflow'")
