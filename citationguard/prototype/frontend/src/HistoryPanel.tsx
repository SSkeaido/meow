import { useEffect, useState } from 'react'
import { getBatchDetail, getPaperContent, getUserHistory } from './api'
import type { AuditBatchDetail, PaperContent, UserHistory } from './types'

type Props = {
  refreshToken: number
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

export default function HistoryPanel({ refreshToken }: Props) {
  const [history, setHistory] = useState<UserHistory | null>(null)
  const [detail, setDetail] = useState<AuditBatchDetail | null>(null)
  const [paperDetail, setPaperDetail] = useState<PaperContent | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    setLoading(true)
    getUserHistory()
      .then((value) => {
        if (active) setHistory(value)
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : '历史记录加载失败')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [refreshToken])

  async function openAudit(projectId: string, batchId: string) {
    setError('')
    try {
      setDetail(await getBatchDetail(projectId, batchId))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '记录详情加载失败')
    }
  }

  async function openPaper(projectId: string, paperId: string) {
    setError('')
    try {
      setDetail(null)
      setPaperDetail(await getPaperContent(projectId, paperId))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '文献内容加载失败')
    }
  }

  if (loading) return <section className="history-panel"><p>正在加载历史记录…</p></section>

  return (
    <section className="history-panel">
      <div className="history-panel__head">
        <div>
          <p className="step">HISTORY</p>
          <h2>我的历史</h2>
          <p>这里保存当前访问密钥在有效期内上传的文献和检查过的论文内容。</p>
        </div>
        <div className="history-summary">
          <span><strong>{history?.papers.length ?? 0}</strong> 篇参考文献</span>
          <span><strong>{history?.audits.length ?? 0}</strong> 次论文检查</span>
        </div>
      </div>

      {error ? <div className="feedback feedback--error">{error}</div> : null}

      <div className="history-grid">
        <article className="history-column">
          <h3>上传过的参考文献</h3>
          {history?.papers.length ? history.papers.map((paper) => (
            <button
              type="button"
              className="history-card history-card--button"
              key={paper.id}
              onClick={() => void openPaper(paper.project_id, paper.id)}
            >
              <strong>{paper.title}</strong>
              <span>{paper.original_filename}</span>
              <small>{paper.page_count} 页 · {formatDate(paper.created_at)}</small>
            </button>
          )) : <p className="history-empty">还没有上传过参考文献。</p>}
        </article>

        <article className="history-column">
          <h3>检查过的论文内容</h3>
          {history?.audits.length ? history.audits.map((item) => (
            <button
              type="button"
              className="history-card history-card--button"
              key={item.batch.id}
              onClick={() => void openAudit(item.batch.project_id, item.batch.id)}
            >
              <strong>{item.batch.source_label || '未命名论文内容'}</strong>
              <span>{item.manuscript_preview || '无文本预览'}</span>
              <small>
                {formatDate(item.batch.created_at)} · {item.manuscript_characters} 字符 · {item.result_count} 条结果
              </small>
            </button>
          )) : <p className="history-empty">还没有完成论文检查。</p>}
        </article>
      </div>

      {detail ? (
        <div className="history-detail">
          <div className="history-detail__head">
            <div>
              <p className="step">DETAIL</p>
              <h3>{detail.batch.source_label || '论文检查详情'}</h3>
              <small>{formatDate(detail.batch.created_at)}</small>
            </div>
            <button type="button" className="sign-out" onClick={() => setDetail(null)}>关闭详情</button>
          </div>
          <h4>当时提交的论文内容</h4>
          <pre>{detail.manuscript_text}</pre>
          <h4>检查结果</h4>
          <div className="result-list">
            {detail.results.map((result, index) => (
              <article className="result-card" key={`${result.claim_text}-${index}`}>
                <strong>{result.support_level}</strong>
                <h3>{result.claim_text}</h3>
                <p>{result.explanation}</p>
                <div className="result-card__fix">{result.suggested_fix}</div>
              </article>
            ))}
          </div>
        </div>
      ) : null}

      {paperDetail ? (
        <div className="history-detail">
          <div className="history-detail__head">
            <div>
              <p className="step">PAPER</p>
              <h3>{paperDetail.paper.title}</h3>
              <small>
                {paperDetail.paper.original_filename} · {paperDetail.paper.page_count} 页 · {paperDetail.chunk_count} 个文本片段
              </small>
            </div>
            <button type="button" className="sign-out" onClick={() => setPaperDetail(null)}>关闭详情</button>
          </div>
          <h4>解析出的文献内容</h4>
          <pre>{paperDetail.text || '这篇PDF没有提取到可显示的文本。'}</pre>
        </div>
      ) : null}
    </section>
  )
}
