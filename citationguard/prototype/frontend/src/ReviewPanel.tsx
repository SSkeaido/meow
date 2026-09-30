import type { PreSubmissionReviewResponse, ReviewFinding } from './types'

type ReviewPanelProps = {
  result: PreSubmissionReviewResponse
}

function severityLabel(value: ReviewFinding['severity']) {
  if (value === 'major') return '高优先级'
  if (value === 'moderate') return '建议处理'
  return '轻量提醒'
}

export default function ReviewPanel({ result }: ReviewPanelProps) {
  const { paper_card: card, summary } = result
  return (
    <section className="review-panel">
      <div className="results__head">
        <div>
          <p className="step">04</p>
          <h2>投稿前审查 Skill</h2>
          <p className="results__sub">目标：{result.target_venue || '通用投稿'} · {result.findings.length} 条结构化发现</p>
        </div>
        <div className="review-score">
          <strong>{summary.readiness_score}</strong>
          <span>准备度</span>
        </div>
      </div>

      <div className="review-skill-row">
        {result.skill_ids.map((skill) => <span key={skill}>{skill}</span>)}
      </div>

      <div className="review-grid">
        <article className="review-card review-card--distill">
          <p className="review-card__eyebrow">PAPER CARD</p>
          <h3>{card.title}</h3>
          <p>{card.problem_and_gap || '暂未提取到明确的问题定义。'}</p>
          {card.contributions.length ? (
            <ul>{card.contributions.slice(0, 3).map((item) => <li key={item}>{item}</li>)}</ul>
          ) : <p className="muted">暂未识别到明确贡献。</p>}
        </article>

        <article className="review-card">
          <p className="review-card__eyebrow">PRIORITY ACTIONS</p>
          {summary.priority_actions.length ? (
            <ol>{summary.priority_actions.map((item) => <li key={item}>{item}</li>)}</ol>
          ) : <p className="muted">当前没有需要优先处理的发现。</p>}
        </article>
      </div>

      <div className="review-findings">
        {result.findings.length ? result.findings.map((finding) => (
          <article key={`${finding.skill_id}-${finding.title}`} className={`review-finding review-finding--${finding.severity}`}>
            <div className="review-finding__head">
              <span className="review-finding__severity">{severityLabel(finding.severity)}</span>
              <span>{finding.category}</span>
              <span>{Math.round(finding.confidence * 100)}% 置信度</span>
            </div>
            <h3>{finding.title}</h3>
            <p>{finding.summary}</p>
            <div className="review-finding__fix"><strong>建议：</strong>{finding.recommended_fix}</div>
            {finding.evidence_refs.length ? (
              <div className="review-finding__evidence">
                {finding.evidence_refs.map((ref, index) => (
                  <span key={`${ref.paper_id ?? ref.source}-${ref.page ?? index}`}>
                    {ref.source === 'reference' ? `证据 · p.${ref.page ?? '?'} · ` : '稿件 · '}{ref.quote}
                  </span>
                ))}
              </div>
            ) : null}
          </article>
        )) : <div className="review-empty">没有生成审查发现。可以先增加目标期刊、研究问题或实验信息。</div>}
      </div>
    </section>
  )
}
