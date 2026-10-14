from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def new_id() -> str:
    return str(uuid4())


class PrivacyMode(StrEnum):
    CLOUD_STANDARD = "cloud_standard"
    PRIVACY_ENHANCED = "privacy_enhanced"
    BRING_YOUR_OWN_KEY = "bring_your_own_key"
    LOCAL_PRIVATE = "local_private"


class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    privacy_mode: PrivacyMode = PrivacyMode.PRIVACY_ENHANCED


class Project(ProjectCreate):
    id: str = Field(default_factory=new_id)
    access_key_id: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AccessKeyRecord(BaseModel):
    id: str = Field(default_factory=new_id)
    key_hash: str
    key_prefix: str
    max_completed_audits: int = 0
    completed_audits: int = 0
    reserved_audits: int = 0
    active: bool = True
    valid_days: int = 7
    first_used_at: datetime | None = None
    expires_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AccessKeySession(BaseModel):
    key_prefix: str
    first_used_at: datetime
    expires_at: datetime
    completed_audits: int = 0


class Paper(BaseModel):
    id: str = Field(default_factory=new_id)
    project_id: str
    title: str
    original_filename: str
    file_hash: str
    page_count: int
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SourceChunk(BaseModel):
    id: str = Field(default_factory=new_id)
    paper_id: str
    project_id: str
    chunk_index: int
    page_start: int
    page_end: int
    section: str = "unknown"
    section_type: str = "unknown"
    text: str
    cleaned_text: str
    token_estimate: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceCard(BaseModel):
    id: str = Field(default_factory=new_id)
    project_id: str
    paper_id: str
    source_chunk_id: str
    claim_type: str
    summary: str
    source_quote: str
    page: int
    section: str
    support_scope: str
    limitations: str
    confidence: float = 0.5
    validation_flags: list[str] = Field(default_factory=list)


class PaperIngestResult(BaseModel):
    paper: Paper
    chunk_count: int
    indexed_chunk_count: int = 0
    evidence_count: int = 0


class PaperContent(BaseModel):
    paper: Paper
    text: str = ""
    chunk_count: int = 0


class AuditRequest(BaseModel):
    claim_text: str
    cited_paper_ids: list[str] = Field(default_factory=list)
    top_k: int = 8


class AuditResult(BaseModel):
    claim_text: str
    cited_paper_ids: list[str]
    supporting_evidence_ids: list[str]
    supporting_source_chunk_ids: list[str] = Field(default_factory=list)
    support_level: str
    risk_flags: list[str]
    explanation: str
    suggested_fix: str


class CitationBinding(BaseModel):
    marker: str = Field(min_length=1, max_length=200)
    paper_id: str


class CitationBindingSuggestionRequest(BaseModel):
    text: str = Field(min_length=1)
    paper_ids: list[str] = Field(default_factory=list)


class CitationBindingSuggestion(BaseModel):
    marker: str
    paper_id: str | None = None
    confidence: float
    reason: str


class CitationBindingRecord(BaseModel):
    id: str = Field(default_factory=new_id)
    project_id: str
    marker: str
    paper_id: str | None = None
    confidence: float = 0.0
    reason: str = ""
    source: str = "auto"
    status: str = "suggested"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CitationBindingReviewUpdate(BaseModel):
    paper_id: str | None = None
    status: str = "confirmed"


class ClaimBatchCreate(BaseModel):
    text: str = Field(min_length=1)
    source_label: str = ""
    language: str = "auto"
    source: str = "pasted"
    cited_paper_ids: list[str] = Field(default_factory=list)
    citation_bindings: list[CitationBinding] = Field(default_factory=list)
    enforce_citation_bindings: bool = False
    top_k: int = Field(default=8, ge=1, le=20)


class ClaimBatch(BaseModel):
    id: str = Field(default_factory=new_id)
    project_id: str
    source_label: str = ""
    language: str = "auto"
    source: str = "pasted"
    status: str = "pending"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ReviewParagraph(BaseModel):
    id: str = Field(default_factory=new_id)
    claim_batch_id: str
    project_id: str
    paragraph_index: int
    text: str
    polished_text: str | None = None
    source: str = "pasted"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ReviewClaim(BaseModel):
    id: str = Field(default_factory=new_id)
    review_paragraph_id: str
    project_id: str
    claim_index: int
    claim_text: str
    normalized_claim: str
    claim_type: str = "unknown"
    strength: str = "unknown"
    cited_paper_ids: list[str] = Field(default_factory=list)
    evidence_card_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AuditRun(BaseModel):
    id: str = Field(default_factory=new_id)
    project_id: str
    claim_batch_id: str
    run_type: str = "user_text_audit"
    status: str = "completed"
    model_provider: str = "heuristic"
    model_name: str = "keyword-overlap-placeholder"
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    error_message: str = ""


class PersistedAuditResult(AuditResult):
    id: str = Field(default_factory=new_id)
    audit_run_id: str
    project_id: str
    review_claim_id: str
    sent_payload_summary: str = "heuristic-only; no external model call"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CitationLedgerEntry(BaseModel):
    id: str = Field(default_factory=new_id)
    project_id: str
    claim_batch_id: str
    review_paragraph_id: str
    review_claim_id: str
    paper_id: str
    evidence_card_id: str | None = None
    citation_key: str = ""
    usage_type: str = "claim_support"
    last_audit_status: str
    last_audited_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class BatchAuditResponse(BaseModel):
    batch: ClaimBatch
    audit_run: AuditRun
    paragraph_count: int
    claim_count: int
    results: list[PersistedAuditResult]


class AuditBatchDetail(BaseModel):
    batch: ClaimBatch
    audit_run: AuditRun
    results: list[PersistedAuditResult]
    manuscript_text: str = ""
    papers: list[Paper] = Field(default_factory=list)


class AuditHistoryItem(BaseModel):
    batch: ClaimBatch
    audit_run: AuditRun
    manuscript_preview: str = ""
    manuscript_characters: int = 0
    result_count: int = 0
    papers: list[Paper] = Field(default_factory=list)


class UserHistory(BaseModel):
    projects: list[Project] = Field(default_factory=list)
    papers: list[Paper] = Field(default_factory=list)
    audits: list[AuditHistoryItem] = Field(default_factory=list)


class RetrieveChunksRequest(BaseModel):
    query: str
    paper_ids: list[str] = Field(default_factory=list)
    top_k: int = 8


class RetrievedChunk(BaseModel):
    source_chunk_id: str
    paper_id: str
    project_id: str
    page_start: int
    page_end: int
    section_type: str
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


DEFAULT_REVIEW_SKILLS = [
    "paper-distillation",
    "methodology-review",
    "experiment-reproducibility-review",
    "adversarial-review",
]


class ReviewSkillRequest(BaseModel):
    manuscript_text: str = Field(min_length=1, max_length=200_000)
    cited_paper_ids: list[str] = Field(default_factory=list)
    target_venue: str = "generic"
    skill_ids: list[str] = Field(default_factory=lambda: list(DEFAULT_REVIEW_SKILLS))


class ReviewEvidenceRef(BaseModel):
    source: str = "manuscript"
    paper_id: str | None = None
    page: int | None = None
    section: str = ""
    quote: str = ""


class PaperCard(BaseModel):
    title: str = ""
    paper_type: str = "unknown"
    problem_and_gap: str = ""
    contributions: list[str] = Field(default_factory=list)
    method_summary: str = ""
    data_and_experiments: str = ""
    key_claims: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)


class ReviewFinding(BaseModel):
    skill_id: str
    category: str
    severity: str
    title: str
    summary: str
    evidence_refs: list[ReviewEvidenceRef] = Field(default_factory=list)
    recommended_fix: str = ""
    confidence: float = Field(default=0.5, ge=0, le=1)


class ReviewSummary(BaseModel):
    readiness_score: int = Field(default=50, ge=0, le=100)
    major_count: int = 0
    moderate_count: int = 0
    minor_count: int = 0
    strengths: list[str] = Field(default_factory=list)
    priority_actions: list[str] = Field(default_factory=list)


class PreSubmissionReviewResponse(BaseModel):
    review_id: str = Field(default_factory=new_id)
    project_id: str
    target_venue: str
    skill_ids: list[str]
    paper_card: PaperCard
    findings: list[ReviewFinding] = Field(default_factory=list)
    summary: ReviewSummary
