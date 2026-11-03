export type PrivacyMode =
  | 'cloud_standard'
  | 'privacy_enhanced'
  | 'bring_your_own_key'
  | 'local_private'

export type ProjectCreate = {
  name: string
  description?: string
  privacy_mode?: PrivacyMode
}

export type Project = ProjectCreate & {
  id: string
  access_key_id: string
  created_at: string
}

export type Paper = {
  id: string
  project_id: string
  title: string
  original_filename: string
  file_hash: string
  page_count: number
  metadata: Record<string, unknown>
  created_at: string
}

export type PaperIngestResult = {
  paper: Paper
  chunk_count: number
  indexed_chunk_count: number
  evidence_count: number
}

export type PaperContent = {
  paper: Paper
  text: string
  chunk_count: number
}

export type EvidenceCard = {
  id: string
  project_id: string
  paper_id: string
  source_chunk_id: string
  claim_type: string
  summary: string
  source_quote: string
  page: number
  section: string
  support_scope: string
  limitations: string
  confidence: number
}

export type ClaimBatchCreate = {
  text: string
  source_label?: string
  language?: string
  source?: string
  cited_paper_ids?: string[]
  citation_bindings?: CitationBinding[]
  enforce_citation_bindings?: boolean
  top_k?: number
}

export type CitationBinding = {
  marker: string
  paper_id: string
}

export type CitationBindingSuggestion = {
  marker: string
  paper_id: string | null
  confidence: number
  reason: string
}

export type CitationBindingRecord = CitationBindingSuggestion & {
  id: string
  project_id: string
  source: string
  status: string
  created_at: string
  updated_at: string
}

export type AuditResult = {
  claim_text: string
  cited_paper_ids: string[]
  supporting_evidence_ids: string[]
  supporting_source_chunk_ids: string[]
  support_level: string
  risk_flags: string[]
  explanation: string
  suggested_fix: string
}

export type AuditRun = {
  id: string
  project_id: string
  claim_batch_id: string
  run_type: string
  status: string
  model_provider: string
  model_name: string
  started_at: string
  finished_at: string
  error_message: string
}

export type ClaimBatch = {
  id: string
  project_id: string
  source_label: string
  language: string
  source: string
  status: string
  created_at: string
  updated_at: string
}

export type BatchAuditResponse = {
  batch: ClaimBatch
  audit_run: AuditRun
  paragraph_count: number
  claim_count: number
  results: AuditResult[]
}

export type AuditBatchDetail = {
  batch: ClaimBatch
  audit_run: AuditRun
  results: AuditResult[]
  manuscript_text: string
  papers: Paper[]
}

export type AccessKeySession = {
  key_prefix: string
  first_used_at: string
  expires_at: string
  completed_audits: number
}

export type AuditHistoryItem = {
  batch: ClaimBatch
  audit_run: AuditRun
  manuscript_preview: string
  manuscript_characters: number
  result_count: number
  papers: Paper[]
}

export type UserHistory = {
  projects: Project[]
  papers: Paper[]
  audits: AuditHistoryItem[]
}

export type RetrieveChunksRequest = {
  query: string
  paper_ids?: string[]
  top_k?: number
}

export type RetrievedChunk = {
  source_chunk_id: string
  paper_id: string
  project_id: string
  page_start: number
  page_end: number
  section_type: string
  text: string
  metadata: Record<string, unknown>
}

export type ReviewEvidenceRef = {
  source: string
  paper_id: string | null
  page: number | null
  section: string
  quote: string
}

export type PaperCard = {
  title: string
  paper_type: string
  problem_and_gap: string
  contributions: string[]
  method_summary: string
  data_and_experiments: string
  key_claims: string[]
  limitations: string[]
  open_questions: string[]
}

export type ReviewFinding = {
  skill_id: string
  category: string
  severity: 'major' | 'moderate' | 'minor'
  title: string
  summary: string
  evidence_refs: ReviewEvidenceRef[]
  recommended_fix: string
  confidence: number
}

export type ReviewSummary = {
  readiness_score: number
  major_count: number
  moderate_count: number
  minor_count: number
  strengths: string[]
  priority_actions: string[]
}

export type PreSubmissionReviewResponse = {
  review_id: string
  project_id: string
  target_venue: string
  skill_ids: string[]
  paper_card: PaperCard
  findings: ReviewFinding[]
  summary: ReviewSummary
}

export type ReviewSkillRequest = {
  manuscript_text: string
  cited_paper_ids?: string[]
  target_venue?: string
  skill_ids?: string[]
}
