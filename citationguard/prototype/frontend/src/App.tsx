import { useEffect, useRef, useState } from 'react'
import {
  auditBatch,
  ACCESS_KEY_STORAGE_KEY,
  ApiError,
  createProject,
  downloadExport,
  getAccessKeySession,
  listPapers,
  listProjects,
  privacyModeLabels,
  removeAccessKey,
  runPreSubmissionReview,
  saveAccessKey,
  reviewCitationBinding,
  suggestCitationBindings,
  uploadPaper,
} from './api'
import './App.css'
import HistoryPanel from './HistoryPanel'
import ReviewPanel from './ReviewPanel'
import { extractTextFromFile } from './fileParsers'
import type { AccessKeySession, AuditResult, BatchAuditResponse, CitationBindingRecord, PaperIngestResult, PreSubmissionReviewResponse, PrivacyMode, Project } from './types'

type ManuscriptMode = 'text' | 'file'

type ReferenceUploadState = {
  name: string
  status: 'uploading' | 'done' | 'error'
  detail: string
}

const WORKSPACE_STORAGE_KEY = 'citation-audit-single-page-project-id'
const MAX_REFERENCE_FILES_PER_BATCH = 20

function supportTone(level?: string) {
  const value = (level ?? '').toUpperCase()
  if (value.includes('PASS')) return 'pass'
  if (value.includes('CHECK')) return 'check'
  if (value.includes('RISK')) return 'risk'
  if (value.includes('FAIL')) return 'fail'
  return 'check'
}

function resultLabel(total: number) {
  if (!total) return '还没有检查结果'
  if (total === 1) return '1 条 claim 已完成检查'
  return `${total} 条 claim 已完成检查`
}

function formatFileSize(file: File) {
  const mb = file.size / 1024 / 1024
  if (mb >= 1) return `${mb.toFixed(1)} MB`
  return `${Math.max(1, Math.round(file.size / 1024))} KB`
}

function formatExpiry(value?: string) {
  if (!value) return ''
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

function App() {
  const [accessKeyInput, setAccessKeyInput] = useState(
    () => window.localStorage.getItem(ACCESS_KEY_STORAGE_KEY) ?? '',
  )
  const [accessKeyVersion, setAccessKeyVersion] = useState(0)
  const [session, setSession] = useState<AccessKeySession | null>(null)
  const [activeView, setActiveView] = useState<'audit' | 'history'>('audit')
  const [historyRefreshToken, setHistoryRefreshToken] = useState(0)
  const [needsAccessKey, setNeedsAccessKey] = useState(false)
  const [project, setProject] = useState<Project | null>(null)
  const [papers, setPapers] = useState<PaperIngestResult[]>([])
  const [manuscriptMode, setManuscriptMode] = useState<ManuscriptMode>('text')
  const [manuscriptText, setManuscriptText] = useState('')
  const [manuscriptFile, setManuscriptFile] = useState<File | null>(null)
  const [manuscriptExtractedText, setManuscriptExtractedText] = useState('')
  const [manuscriptMeta, setManuscriptMeta] = useState('')
  const [referenceUploads, setReferenceUploads] = useState<ReferenceUploadState[]>([])
  const [bindingNotice, setBindingNotice] = useState('')
  const [bindingRecords, setBindingRecords] = useState<CitationBindingRecord[]>([])
  const [isSuggestingBindings, setIsSuggestingBindings] = useState(false)
  const folderInputRef = useRef<HTMLInputElement>(null)
  const [statusMessage, setStatusMessage] = useState('正在准备工作区')
  const [errorMessage, setErrorMessage] = useState('')
  const [isBootstrapping, setIsBootstrapping] = useState(true)
  const [isParsingManuscript, setIsParsingManuscript] = useState(false)
  const [isUploadingReferences, setIsUploadingReferences] = useState(false)
  const [isAuditing, setIsAuditing] = useState(false)
  const [batchResult, setBatchResult] = useState<BatchAuditResponse | null>(null)
  const [isReviewing, setIsReviewing] = useState(false)
  const [reviewVenue, setReviewVenue] = useState('generic')
  const [reviewResult, setReviewResult] = useState<PreSubmissionReviewResponse | null>(null)

  const auditResults: AuditResult[] = batchResult?.results ?? []
  const exportBase = batchResult && project ? `/projects/${project.id}/exports/audits/${batchResult.batch.id}` : ''

  const stats = (() => {
    const counts = { pass: 0, check: 0, risk: 0, fail: 0 }
    for (const result of auditResults) {
      const tone = supportTone(result.support_level)
      counts[tone as keyof typeof counts] += 1
    }
    return counts
  })()

  const activeManuscriptText =
    manuscriptMode === 'text' ? manuscriptText.trim() : manuscriptExtractedText.trim()

  useEffect(() => {
    let active = true

    async function bootstrapWorkspace() {
      try {
        const projects = await listProjects()
        if (!active) return

        const savedId = window.localStorage.getItem(WORKSPACE_STORAGE_KEY)
        const savedProject = savedId ? projects.find((item) => item.id === savedId) ?? null : null

        if (savedProject) {
          setProject(savedProject)
          setStatusMessage('工作区已就绪')
          return
        }

        const created = await createProject({
          name: 'Citation Quick Audit',
          description: 'Single-page citation checker workspace',
          privacy_mode: 'privacy_enhanced',
        })
        if (!active) return
        window.localStorage.setItem(WORKSPACE_STORAGE_KEY, created.id)
        setProject(created)
        setStatusMessage('已创建默认工作区')
      } catch (error) {
        if (!active) return
        if (error instanceof ApiError && error.status === 401) {
          setNeedsAccessKey(true)
          setErrorMessage(error.message)
          setStatusMessage('请输入有效邀请码')
          return
        }
        setErrorMessage(error instanceof Error ? error.message : '工作区初始化失败')
        setStatusMessage('后端连接失败')
      } finally {
        if (active) setIsBootstrapping(false)
      }
    }

    void bootstrapWorkspace()

    return () => {
      active = false
    }
  }, [accessKeyVersion])

  useEffect(() => {
    if (!window.localStorage.getItem(ACCESS_KEY_STORAGE_KEY)) {
      setSession(null)
      return
    }
    getAccessKeySession()
      .then(setSession)
      .catch((error: unknown) => {
        if (error instanceof ApiError && error.status === 401) setNeedsAccessKey(true)
      })
  }, [accessKeyVersion])

  function handleAccessKeySubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!accessKeyInput.trim()) {
      setErrorMessage('请输入邀请码')
      return
    }
    saveAccessKey(accessKeyInput)
    setNeedsAccessKey(false)
    setErrorMessage('')
    setIsBootstrapping(true)
    setAccessKeyVersion((value) => value + 1)
  }

  function handleSignOut() {
    removeAccessKey()
    window.localStorage.removeItem(WORKSPACE_STORAGE_KEY)
    setAccessKeyInput('')
    setProject(null)
    setPapers([])
    setSession(null)
    setActiveView('audit')
    setNeedsAccessKey(true)
    setStatusMessage('已退出邀请码工作区')
  }

  async function handleExport(path: string, filename: string) {
    try {
      await downloadExport(path, filename)
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) setNeedsAccessKey(true)
      setErrorMessage(error instanceof Error ? error.message : '导出失败')
    }
  }

  useEffect(() => {
    const folderInput = folderInputRef.current
    folderInput?.setAttribute('webkitdirectory', '')
    folderInput?.setAttribute('directory', '')
  }, [])

  useEffect(() => {
    const projectId = project?.id ?? ''
    if (!projectId) {
      setPapers([])
      return
    }

    let active = true

    async function loadPapers() {
      try {
        const nextPapers = await listPapers(projectId)
        if (!active) return
        setPapers(nextPapers)
      } catch (error) {
        if (!active) return
        setErrorMessage(error instanceof Error ? error.message : '文献列表加载失败')
      }
    }

    void loadPapers()

    return () => {
      active = false
    }
  }, [project])

  async function refreshPapers() {
    const projectId = project?.id ?? ''
    if (!projectId) return
    const nextPapers = await listPapers(projectId)
    setPapers(nextPapers)
  }

  async function handleManuscriptFile(file: File | null) {
    if (!file) return

    setManuscriptMode('file')
    setManuscriptFile(file)
    setIsParsingManuscript(true)
    setErrorMessage('')
    setManuscriptMeta('')
    setStatusMessage('正在解析待审文件')

    try {
      const extracted = await extractTextFromFile(file)
      setManuscriptExtractedText(extracted)
      setManuscriptMeta(`${file.name} · ${formatFileSize(file)} · ${extracted.length.toLocaleString()} chars`)
      setStatusMessage('待审文件已解析')
    } catch (error) {
      setManuscriptExtractedText('')
      setManuscriptMeta('')
      setErrorMessage(error instanceof Error ? error.message : '待审文件解析失败')
      setStatusMessage('待审文件解析失败')
    } finally {
      setIsParsingManuscript(false)
    }
  }

  async function handleReferenceFiles(fileList: FileList | null) {
    if (!project || !fileList?.length) return

    const selectedFiles = Array.from(fileList)
    const files = selectedFiles.slice(0, MAX_REFERENCE_FILES_PER_BATCH)
    setIsUploadingReferences(true)
    setErrorMessage('')
    if (selectedFiles.length > MAX_REFERENCE_FILES_PER_BATCH) {
      setErrorMessage(
        `为保护服务器，每次最多上传 ${MAX_REFERENCE_FILES_PER_BATCH} 篇。访问密钥一周内有效，请分批上传剩余文献。`,
      )
    }
    setStatusMessage('正在上传引用文献')

    for (const file of files) {
      if (!file.name.toLowerCase().endsWith('.pdf')) {
        setReferenceUploads((current) => [
          { name: file.name, status: 'error', detail: '当前引用文献区只接收 PDF。' },
          ...current,
        ])
        continue
      }

      setReferenceUploads((current) => [{ name: file.name, status: 'uploading', detail: '上传中' }, ...current])

      try {
        const result = await uploadPaper(project.id, file)
        setReferenceUploads((current) =>
          current.map((item) =>
            item.name === file.name
              ? {
                  ...item,
                  status: 'done',
                  detail: `${result.paper.page_count} 页 · ${result.chunk_count} chunks`,
                }
              : item,
          ),
        )
      } catch (error) {
        setReferenceUploads((current) =>
          current.map((item) =>
            item.name === file.name
              ? {
                  ...item,
                  status: 'error',
                  detail: error instanceof Error ? error.message : '上传失败',
                }
              : item,
          ),
        )
      }
    }

    try {
      await refreshPapers()
      setStatusMessage('引用文献已更新')
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : '文献刷新失败')
    } finally {
      setIsUploadingReferences(false)
    }
  }

  async function handleAudit() {
    if (!project) return
    if (!activeManuscriptText) {
      setErrorMessage('请先输入论文引用片段，或者上传待审文件。')
      return
    }
    if (!papers.length) {
      setErrorMessage('请先上传至少一篇引用文献 PDF。')
      return
    }

    setIsAuditing(true)
    setErrorMessage('')
    setStatusMessage('正在执行引用准确性检查')

    try {
      const confirmedBindings = bindingRecords
        .filter((record) => record.status === 'confirmed' && record.paper_id)
        .map((record) => ({ marker: record.marker, paper_id: record.paper_id as string }))
      const result = await auditBatch(project.id, {
        text: activeManuscriptText,
        source_label: manuscriptFile?.name || 'pasted-excerpt',
        language: 'auto',
        source: manuscriptMode === 'text' ? 'pasted' : 'uploaded_file',
        cited_paper_ids: papers.map((item) => item.paper.id),
        citation_bindings: confirmedBindings,
        enforce_citation_bindings: bindingRecords.length > 0,
        top_k: 8,
      })
      setBatchResult(result)
      setHistoryRefreshToken((value) => value + 1)
      setStatusMessage('检查完成')
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : '检查失败')
      setStatusMessage('检查失败')
    } finally {
      setIsAuditing(false)
    }
  }

  async function handleSuggestBindings() {
    if (!project || !activeManuscriptText || !papers.length) return
    setIsSuggestingBindings(true)
    setErrorMessage('')
    try {
      const records = await suggestCitationBindings(project.id, {
        text: activeManuscriptText,
        paper_ids: papers.map((item) => item.paper.id),
      })
      setBindingRecords(records)
      setBindingNotice(records.length ? '请确认下方引用映射后再开始审计。' : '未在待审内容中识别到引用标识。')
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : '引用匹配建议失败')
    } finally {
      setIsSuggestingBindings(false)
    }
  }

  async function handlePreSubmissionReview() {
    if (!project || !activeManuscriptText) {
      setErrorMessage('请先输入或上传待审论文内容。')
      return
    }
    setIsReviewing(true)
    setErrorMessage('')
    setStatusMessage('正在运行投稿前审查 Skill')
    try {
      const result = await runPreSubmissionReview(project.id, {
        manuscript_text: activeManuscriptText,
        cited_paper_ids: papers.map((item) => item.paper.id),
        target_venue: reviewVenue,
      })
      setReviewResult(result)
      setStatusMessage('投稿前审查完成')
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : '投稿前审查失败')
      setStatusMessage('投稿前审查失败')
    } finally {
      setIsReviewing(false)
    }
  }

  async function handleReviewBinding(record: CitationBindingRecord, status: string, paperId = record.paper_id) {
    if (!project) return
    try {
      const updated = await reviewCitationBinding(project.id, record.id, { paper_id: paperId, status })
      setBindingRecords((current) => current.map((item) => (item.id === updated.id ? updated : item)))
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : '保存引用映射失败')
    }
  }

  if (needsAccessKey) {
    return (
      <main className="access-gate">
        <form className="access-gate__card" onSubmit={handleAccessKeySubmit}>
          <p className="hero__eyebrow">INVITE-ONLY ACCESS</p>
          <h1>进入引用准确性检查</h1>
          <p>输入管理员发放的邀请码。邀请码只保存在当前浏览器中，并通过加密连接发送。</p>
          <label htmlFor="access-key">邀请码</label>
          <input
            id="access-key"
            type="password"
            autoComplete="off"
            value={accessKeyInput}
            onChange={(event) => setAccessKeyInput(event.target.value)}
            placeholder="cak_..."
            autoFocus
          />
          {errorMessage ? <div className="feedback feedback--error">{errorMessage}</div> : null}
          <button type="submit" className="launch" disabled={isBootstrapping}>
            {isBootstrapping ? '正在验证...' : '进入工作区'}
          </button>
        </form>
      </main>
    )
  }

  if (activeView === 'history') {
    return (
      <div className="page">
        <header className="hero hero--compact">
          <div className="hero__copy">
            <p className="hero__eyebrow">Citation Accuracy Checker</p>
            <h1>我的文献与论文检查历史</h1>
            <p className="hero__sub">
              同一个访问密钥在一周有效期内可分多次上传和检查，无需一次提交全部资料。
            </p>
          </div>
          <div className="hero__meta">
            {session ? <span className="hero__pill">有效至 {formatExpiry(session.expires_at)}</span> : null}
            <button type="button" className="launch launch--small" onClick={() => setActiveView('audit')}>
              返回检查
            </button>
            <button type="button" className="sign-out" onClick={handleSignOut}>退出访问密钥</button>
          </div>
        </header>
        <main className="canvas">
          <HistoryPanel refreshToken={historyRefreshToken} />
        </main>
      </div>
    )
  }

  return (
    <div className="page">
      <header className="hero">
        <div className="hero__copy">
          <p className="hero__eyebrow">Citation Accuracy Checker</p>
          <h1>把你的正文和引用文献丢进来，我们只做一件事：检查引用有没有说成你想表达的意思。</h1>
          <p className="hero__sub">
            首屏只保留两个入口。左边放你的论文正文、PDF 或 DOCX；右边放你真正引用过的文献 PDF。其他内容等用户提交后再展开。
          </p>
        </div>

          <div className="hero__meta">
          <span className="hero__pill">
            {project ? privacyModeLabels[project.privacy_mode as PrivacyMode] : '工作区初始化中'}
          </span>
            <span className="hero__status">{statusMessage}</span>
            {session ? <span className="hero__status">密钥有效至 {formatExpiry(session.expires_at)}</span> : null}
            <button type="button" className="sign-out" onClick={() => setActiveView('history')}>我的历史</button>
            {window.localStorage.getItem(ACCESS_KEY_STORAGE_KEY) ? (
              <button type="button" className="sign-out" onClick={handleSignOut}>退出邀请码</button>
            ) : null}
        </div>
      </header>

      <main className="canvas">
        <section className="stage">
          <article className="input-card">
            <div className="input-card__head">
              <div>
                <p className="step">01</p>
                <h2>待审内容</h2>
              </div>
              <div className="segmented">
                <button
                  type="button"
                  className={manuscriptMode === 'text' ? 'is-active' : ''}
                  onClick={() => setManuscriptMode('text')}
                >
                  粘贴片段
                </button>
                <button
                  type="button"
                  className={manuscriptMode === 'file' ? 'is-active' : ''}
                  onClick={() => setManuscriptMode('file')}
                >
                  上传文件
                </button>
              </div>
            </div>

            {manuscriptMode === 'text' ? (
              <div className="composer">
                <textarea
                  value={manuscriptText}
                  onChange={(event) => setManuscriptText(event.target.value)}
                  placeholder="粘贴你自己的论文段落、related work、discussion 或者任何你担心被润色后发生语义漂移的引用片段。"
                  rows={14}
                />
                <div className="composer__foot">
                  <span>{manuscriptText.trim().length.toLocaleString()} chars</span>
                  <span>适合快速检查单段或多段文本</span>
                </div>
              </div>
            ) : (
              <label className="dropzone dropzone--manuscript">
                <input
                  type="file"
                  accept=".pdf,.docx,.txt,.md,.markdown"
                  onChange={(event) => void handleManuscriptFile(event.target.files?.[0] ?? null)}
                />
                <div className="dropzone__inner">
                  <strong>{isParsingManuscript ? '正在解析文件...' : '上传待审文件'}</strong>
                  <p>支持 PDF、DOCX、TXT、MD。当前前端会先在本地抽文本，再送去做引用检查。</p>
                  {manuscriptMeta ? <span className="dropzone__meta">{manuscriptMeta}</span> : null}
                </div>
              </label>
            )}
          </article>

          <article className="input-card">
            <div className="input-card__head">
              <div>
                <p className="step">02</p>
                <h2>引用文献 PDF</h2>
              </div>
              <span className="counter">{papers.length} 篇</span>
            </div>

            <p className="upload-advice">
              建议每次上传不超过 {MAX_REFERENCE_FILES_PER_BATCH} 篇。访问密钥从首次使用起有效7天，
              可稍后回来继续上传，历史文献不会丢失。
            </p>
            <label className="dropzone">
              <input type="file" accept=".pdf" multiple onChange={(event) => void handleReferenceFiles(event.target.files)} />
              <div className="dropzone__inner">
                <strong>{isUploadingReferences ? '正在上传文献...' : '上传引用文献'}</strong>
                <p>这里专门放你准备用来支撑 claim 的原始文献 PDF。可以一次多选批量上传。</p>
              </div>
            </label>
            <input
              ref={folderInputRef}
              className="visually-hidden"
              type="file"
              accept=".pdf"
              multiple
              onChange={(event) => void handleReferenceFiles(event.target.files)}
            />
            <button type="button" className="folder-upload" onClick={() => folderInputRef.current?.click()}>
              选择引用文献文件夹
            </button>

            <div className="reference-list">
              {referenceUploads.length ? (
                referenceUploads.map((item) => (
                  <div key={`${item.name}-${item.detail}`} className={`reference-item reference-item--${item.status}`}>
                    <strong>{item.name}</strong>
                    <span>{item.detail}</span>
                  </div>
                ))
              ) : (
                <div className="reference-empty">还没有上传引用文献。</div>
              )}
            </div>

            {papers.length ? (
              <div className="citation-bindings">
                <p>文中引用标识</p>
                <span>先识别论文中的引用标识，再确认每个标识实际对应的 PDF。</span>
                <button type="button" className="folder-upload" onClick={handleSuggestBindings} disabled={isSuggestingBindings}>
                  {isSuggestingBindings ? '正在识别引用...' : '识别并确认引用映射'}
                </button>
                {bindingRecords.map((record) => (
                  <div key={record.id} className={`citation-binding citation-binding--${record.status}`}>
                    <strong>{record.marker}</strong>
                    <select
                      value={record.paper_id ?? ''}
                      onChange={(event) => void handleReviewBinding(record, 'suggested', event.target.value || null)}
                    >
                      <option value="">未匹配 PDF</option>
                      {papers.map((item) => <option key={item.paper.id} value={item.paper.id}>{item.paper.title}</option>)}
                    </select>
                    <small>{Math.round(record.confidence * 100)}% · {record.reason}</small>
                    <div className="binding-actions">
                      <button type="button" onClick={() => void handleReviewBinding(record, 'confirmed')} disabled={!record.paper_id}>确认</button>
                      <button type="button" onClick={() => void handleReviewBinding(record, 'rejected')}>拒绝</button>
                    </div>
                  </div>
                ))}
              </div>
            ) : null}
            {bindingNotice ? <p className="binding-notice">{bindingNotice}</p> : null}
          </article>
        </section>

        <section className="action-bar">
          <div className="action-bar__copy">
            <strong>检查前提</strong>
            <span>左边有正文，右边有引用文献，系统才知道“你说了什么”和“你拿什么来支撑它”。</span>
          </div>
          <div className="action-bar__actions">
            <button
              type="button"
              className="launch"
              onClick={handleAudit}
              disabled={isBootstrapping || isParsingManuscript || isUploadingReferences || isAuditing}
            >
              {isAuditing ? '检查中...' : '开始引用准确性检查'}
            </button>
            <div className="review-launch">
              <select value={reviewVenue} onChange={(event) => setReviewVenue(event.target.value)} aria-label="目标投稿类型">
                <option value="generic">通用投稿</option>
                <option value="neurips">NeurIPS / ML 会议</option>
                <option value="acl">ACL / NLP 会议</option>
                <option value="journal">中文期刊 / 学术期刊</option>
              </select>
              <button type="button" className="secondary-launch" onClick={handlePreSubmissionReview} disabled={isReviewing || isParsingManuscript}>
                {isReviewing ? '审查中...' : '运行投稿前审查'}
              </button>
            </div>
          </div>
        </section>

        {errorMessage ? <div className="feedback feedback--error">{errorMessage}</div> : null}

        {batchResult ? (
          <section className="results">
            <div className="results__head">
              <div>
                <p className="step">03</p>
                <h2>检查结果</h2>
                <p className="results__sub">{resultLabel(auditResults.length)}</p>
              </div>

              <div className="scoreboard">
                <span className="scoreboard__pill scoreboard__pill--pass">PASS {stats.pass}</span>
                <span className="scoreboard__pill scoreboard__pill--check">CHECK {stats.check}</span>
                <span className="scoreboard__pill scoreboard__pill--risk">RISK {stats.risk}</span>
                <span className="scoreboard__pill scoreboard__pill--fail">FAIL {stats.fail}</span>
              </div>
            </div>

            <div className="export-actions">
              <button type="button" onClick={() => void handleExport(`${exportBase}.md`, `citation-audit-${batchResult.batch.id}.md`)}>导出 Markdown</button>
              <button type="button" onClick={() => void handleExport(`${exportBase}.csv`, `claim-audit-${batchResult.batch.id}.csv`)}>导出 claim CSV</button>
              <button type="button" onClick={() => void handleExport(`${exportBase}/ledger.csv`, `citation-ledger-${batchResult.batch.id}.csv`)}>导出引用台账</button>
              <button type="button" onClick={() => void handleExport(`/projects/${project?.id}/exports/evidence.csv`, `evidence-${project?.id}.csv`)}>导出证据卡</button>
            </div>

            <div className="result-list">
              {auditResults.map((result) => {
                const tone = supportTone(result.support_level)
                return (
                  <article key={`${result.claim_text}-${result.explanation}`} className={`result-card result-card--${tone}`}>
                    <div className="result-card__head">
                      <span className={`verdict verdict--${tone}`}>{result.support_level}</span>
                      <span className="flags">{result.risk_flags.join(' · ') || 'no flags'}</span>
                    </div>
                    <h3>{result.claim_text}</h3>
                    <p>{result.explanation}</p>
                    <div className="result-card__fix">{result.suggested_fix}</div>
                  </article>
                )
              })}
            </div>
          </section>
        ) : null}

        {reviewResult ? <ReviewPanel result={reviewResult} /> : null}
      </main>
    </div>
  )
}

export default App
