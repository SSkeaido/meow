import type {
  AuditBatchDetail,
  AccessKeySession,
  BatchAuditResponse,
  ClaimBatchCreate,
  CitationBindingRecord,
  EvidenceCard,
  PaperIngestResult,
  PaperContent,
  PrivacyMode,
  Project,
  ProjectCreate,
  RetrievedChunk,
  RetrieveChunksRequest,
  PreSubmissionReviewResponse,
  ReviewSkillRequest,
  UserHistory,
} from './types'

const API_BASE = ((import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '/api').replace(/\/$/, '')
export const ACCESS_KEY_STORAGE_KEY = 'citation-audit-access-key'

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

export function saveAccessKey(value: string) {
  window.localStorage.setItem(ACCESS_KEY_STORAGE_KEY, value.trim())
}

export function removeAccessKey() {
  window.localStorage.removeItem(ACCESS_KEY_STORAGE_KEY)
}

function buildUrl(path: string) {
  const relativePath = path.replace(/^\//, '')
  if (API_BASE.startsWith('http://') || API_BASE.startsWith('https://')) {
    return new URL(relativePath, `${API_BASE}/`).toString()
  }
  return `${API_BASE}/${relativePath}`
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const accessKey = window.localStorage.getItem(ACCESS_KEY_STORAGE_KEY)
  const response = await fetch(buildUrl(path), {
    headers: {
      ...(init?.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...(accessKey ? { 'X-Access-Key': accessKey } : {}),
      ...(init?.headers ?? {}),
    },
    ...init,
  })

  if (!response.ok) {
    const raw = await response.text()
    let detail = raw
    try {
      detail = (JSON.parse(raw) as { detail?: string }).detail ?? raw
    } catch {
      // Keep a non-JSON response as-is.
    }
    throw new ApiError(detail || `Request failed with status ${response.status}`, response.status)
  }

  return (await response.json()) as T
}

export async function downloadExport(path: string, filename: string) {
  const accessKey = window.localStorage.getItem(ACCESS_KEY_STORAGE_KEY)
  const response = await fetch(buildUrl(path), {
    headers: accessKey ? { 'X-Access-Key': accessKey } : {},
  })
  if (!response.ok) {
    throw new ApiError((await response.text()) || '导出失败', response.status)
  }
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

export function listProjects() {
  return request<Project[]>('/projects')
}

export function createProject(payload: ProjectCreate) {
  return request<Project>('/projects', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function listPapers(projectId: string) {
  return request<PaperIngestResult[]>(`/projects/${projectId}/papers`)
}

export function getPaperContent(projectId: string, paperId: string) {
  return request<PaperContent>(`/projects/${projectId}/papers/${paperId}`)
}

export function uploadPaper(projectId: string, file: File) {
  const formData = new FormData()
  formData.append('file', file)

  return request<PaperIngestResult>(`/projects/${projectId}/papers/upload`, {
    method: 'POST',
    body: formData,
  })
}

export function listEvidence(paperId: string) {
  return request<EvidenceCard[]>(`/papers/${paperId}/evidence`)
}

export function generateEvidence(paperId: string) {
  return request<EvidenceCard[]>(`/papers/${paperId}/evidence/generate`, {
    method: 'POST',
  })
}

export function auditBatch(projectId: string, payload: ClaimBatchCreate) {
  return request<BatchAuditResponse>(`/projects/${projectId}/audits/batches`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function suggestCitationBindings(projectId: string, payload: { text: string; paper_ids: string[] }) {
  return request<CitationBindingRecord[]>(`/projects/${projectId}/citation-bindings/suggest`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function listCitationBindings(projectId: string) {
  return request<CitationBindingRecord[]>(`/projects/${projectId}/citation-bindings`)
}

export function reviewCitationBinding(projectId: string, bindingId: string, payload: { paper_id: string | null; status: string }) {
  return request<CitationBindingRecord>(`/projects/${projectId}/citation-bindings/${bindingId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function getBatchDetail(projectId: string, batchId: string) {
  return request<AuditBatchDetail>(`/projects/${projectId}/audits/batches/${batchId}`)
}

export function getAccessKeySession() {
  return request<AccessKeySession>('/account/session')
}

export function getUserHistory() {
  return request<UserHistory>('/account/history')
}

export function retrieveChunks(projectId: string, payload: RetrieveChunksRequest) {
  return request<RetrievedChunk[]>(`/projects/${projectId}/retrieval/chunks`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function runPreSubmissionReview(projectId: string, payload: ReviewSkillRequest) {
  return request<PreSubmissionReviewResponse>(`/projects/${projectId}/reviews/pre-submission`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export const privacyModeLabels: Record<PrivacyMode, string> = {
  cloud_standard: '云端标准',
  privacy_enhanced: '隐私增强',
  bring_your_own_key: 'BYOK',
  local_private: '本地私有',
}

export const privacyModeDescriptions: Record<PrivacyMode, string> = {
  cloud_standard: '快速上线，适合公开资料和轻量试用。',
  privacy_enhanced: '只发送最小必要片段，适合敏感科研文本。',
  bring_your_own_key: '用户自带 API Key，平台不承担 token 成本。',
  local_private: '本地或内网部署，适合严格隔离场景。',
}
