import os
import re
from typing import Literal

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.integrations.siliconflow import SiliconFlowSettings


class ExtractedClaim(BaseModel):
    claim_text: str
    claim_type: Literal["background", "comparison", "causal", "result", "limitation", "future_work", "recommendation"] = "background"
    strength: Literal["weak", "moderate", "strong"] = "moderate"


class ClaimExtractionDecision(BaseModel):
    claims: list[ExtractedClaim] = Field(default_factory=list)


_CLAIM_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """Extract only independently auditable academic claims from the submitted paragraph.
Do not rewrite the text. Do not add facts. Exclude transitions and the author's personal intentions.
For every claim, return its exact source wording, a claim type, and its strength.""",
        ),
        ("human", "Paragraph:\n{paragraph}"),
    ]
)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?。！？])\s+")


class HeuristicClaimExtractor:
    provider = "heuristic"
    model_name = "sentence-splitter-placeholder"

    def extract(self, paragraph: str) -> list[ExtractedClaim]:
        sentences = [item.strip() for item in _SENTENCE_SPLIT_RE.split(paragraph) if len(item.strip()) >= 8]
        return [ExtractedClaim(claim_text=sentence) for sentence in sentences] or [ExtractedClaim(claim_text=paragraph)]


class SiliconFlowClaimExtractor:
    provider = "siliconflow"

    def __init__(self, settings: SiliconFlowSettings | None = None) -> None:
        self.settings = settings or SiliconFlowSettings.from_env()
        self.model_name = self.settings.claim_model
        from langchain_openai import ChatOpenAI

        model = ChatOpenAI(
            model=self.model_name,
            api_key=self.settings.api_key,
            base_url=self.settings.base_url,
            temperature=0,
        )
        self.chain = _CLAIM_PROMPT | model.with_structured_output(ClaimExtractionDecision)
        self.fallback = HeuristicClaimExtractor()

    def extract(self, paragraph: str) -> list[ExtractedClaim]:
        try:
            decision = self.chain.invoke({"paragraph": paragraph})
        except Exception:
            return self.fallback.extract(paragraph)
        valid = [item for item in decision.claims if item.claim_text and item.claim_text in paragraph]
        return valid or self.fallback.extract(paragraph)


def get_claim_extractor() -> HeuristicClaimExtractor | SiliconFlowClaimExtractor:
    provider = os.getenv("CLAIM_EXTRACTION_PROVIDER", "heuristic").lower()
    if provider == "heuristic":
        return HeuristicClaimExtractor()
    if provider == "siliconflow":
        return SiliconFlowClaimExtractor()
    raise ValueError("CLAIM_EXTRACTION_PROVIDER must be 'heuristic' or 'siliconflow'")
