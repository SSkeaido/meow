"""Deterministic first-pass reviewer skills for the CitationGuard prototype.

The service deliberately keeps orchestration outside the model. Each skill emits
the same evidence-linked finding shape, so an LLM reviewer can be plugged in later
without changing the frontend contract.
"""

import re
from collections.abc import Iterable

from app.models.schemas import (
    DEFAULT_REVIEW_SKILLS,
    EvidenceCard,
    Paper,
    PaperCard,
    PreSubmissionReviewResponse,
    ReviewEvidenceRef,
    ReviewFinding,
    ReviewSkillRequest,
    ReviewSummary,
)
from app.services.store import store


_SUPPORTED_SKILLS = set(DEFAULT_REVIEW_SKILLS)
_SENTENCE_RE = re.compile(r"(?<=[.!?。！？])\s+|\n+")
_TOKEN_RE = re.compile(r"[A-Za-z0-9_]{3,}|[\u4e00-\u9fff]{2,4}")


class ReviewerSkillRunner:
    def run(self, project_id: str, payload: ReviewSkillRequest) -> PreSubmissionReviewResponse:
        papers = store.list_project_papers(project_id)
        allowed_paper_ids = set(payload.cited_paper_ids) or {paper.id for paper in papers}
        evidence_cards = [
            card
            for card in store.list_project_evidence_cards(project_id)
            if card.paper_id in allowed_paper_ids
        ]
        paper_card = self._distill(payload.manuscript_text, papers, evidence_cards)
        skill_ids = [skill_id for skill_id in payload.skill_ids if skill_id in _SUPPORTED_SKILLS]
        if not skill_ids:
            skill_ids = list(DEFAULT_REVIEW_SKILLS)

        findings: list[ReviewFinding] = []
        if "methodology-review" in skill_ids:
            findings.extend(self._review_methodology(payload.manuscript_text, paper_card, evidence_cards))
        if "experiment-reproducibility-review" in skill_ids:
            findings.extend(self._review_experiments(payload.manuscript_text, paper_card, evidence_cards))
        if "adversarial-review" in skill_ids:
            findings.extend(self._review_adversarial(payload.manuscript_text, paper_card, evidence_cards))

        summary = self._summarize(paper_card, findings, evidence_cards)
        return PreSubmissionReviewResponse(
            project_id=project_id,
            target_venue=payload.target_venue or "generic",
            skill_ids=skill_ids,
            paper_card=paper_card,
            findings=findings,
            summary=summary,
        )

    def _distill(self, text: str, papers: list[Paper], evidence_cards: list[EvidenceCard]) -> PaperCard:
        sentences = self._sentences(text)
        title = next((line.strip() for line in text.splitlines() if line.strip()), "未命名论文")[:160]
        lowered = text.lower()
        if any(term in lowered for term in ("survey", "review paper", "综述", "系统综述")):
            paper_type = "survey"
        elif any(term in lowered for term in ("framework", "system", "pipeline", "框架", "系统")):
            paper_type = "systems"
        elif any(term in lowered for term in ("theorem", "proof", "定理", "证明")):
            paper_type = "theoretical"
        else:
            paper_type = "empirical"

        contributions = self._matching_sentences(
            sentences,
            ("contribution", "we propose", "we present", "our method", "本文提出", "本文贡献", "我们提出"),
            limit=4,
        )
        method = self._matching_sentences(
            sentences,
            ("method", "approach", "model", "algorithm", "methodology", "方法", "模型", "算法", "实验设计"),
            limit=3,
        )
        experiments = self._matching_sentences(
            sentences,
            ("dataset", "baseline", "experiment", "metric", "ablation", "数据集", "基线", "实验", "指标", "消融"),
            limit=4,
        )
        limitations = self._matching_sentences(
            sentences,
            ("limitation", "future work", "threat", "局限", "未来工作", "不足"),
            limit=4,
        )
        key_claims = self._strong_claims(sentences)[:8]
        problem = " ".join(sentences[:2])[:600]
        open_questions: list[str] = []
        if not limitations:
            open_questions.append("论文尚未明确说明主要局限性、适用边界或失败案例。")
        if not evidence_cards:
            open_questions.append("当前工作区没有可关联的参考文献证据卡，审查结果只能先基于稿件文本。")

        return PaperCard(
            title=title,
            paper_type=paper_type,
            problem_and_gap=problem,
            contributions=contributions,
            method_summary=" ".join(method)[:900],
            data_and_experiments=" ".join(experiments)[:900],
            key_claims=key_claims,
            limitations=limitations,
            open_questions=open_questions,
        )

    def _review_methodology(
        self,
        text: str,
        paper_card: PaperCard,
        evidence_cards: list[EvidenceCard],
    ) -> list[ReviewFinding]:
        findings: list[ReviewFinding] = []
        lowered = text.lower()
        missing: list[str] = []
        if not paper_card.method_summary:
            missing.append("方法或研究设计")
        if not any(term in lowered for term in ("question", "hypothesis", "研究问题", "假设", "目标")):
            missing.append("研究问题/假设")
        if missing:
            findings.append(
                self._finding(
                    skill_id="methodology-review",
                    category="methodology",
                    severity="moderate",
                    title="研究设计信息仍不完整",
                    summary=f"当前文本未明确呈现：{'、'.join(missing)}。这会降低读者判断方法是否真正回答研究问题的能力。",
                    fix="补充研究问题或假设、方法步骤、关键假设及其与结论之间的对应关系。",
                    target=" ".join(paper_card.key_claims[:1]) or paper_card.problem_and_gap,
                    evidence_cards=evidence_cards,
                )
            )
        if not paper_card.limitations:
            findings.append(
                self._finding(
                    skill_id="methodology-review",
                    category="methodology",
                    severity="minor",
                    title="局限性与适用边界未被明确标出",
                    summary="稿件中没有识别到局限性或未来工作段落，容易让结论显得比证据更确定。",
                    fix="增加局限性、适用范围、失败案例和可能影响结论的替代解释。",
                    target=paper_card.problem_and_gap,
                    evidence_cards=evidence_cards,
                )
            )
        return findings

    def _review_experiments(
        self,
        text: str,
        paper_card: PaperCard,
        evidence_cards: list[EvidenceCard],
    ) -> list[ReviewFinding]:
        lowered = text.lower()
        required_groups = {
            "数据集与样本": ("dataset", "data", "sample", "数据集", "样本"),
            "评价指标": ("metric", "evaluation", "指标", "评估"),
            "基线或对照": ("baseline", "control", "comparison", "基线", "对照", "比较"),
            "消融或敏感性": ("ablation", "sensitivity", "消融", "敏感性"),
            "复现实验信息": ("seed", "code", "repository", "environment", "随机种子", "代码", "环境"),
        }
        missing = [label for label, terms in required_groups.items() if not any(term in lowered for term in terms)]
        if not missing:
            return []
        return [
            self._finding(
                skill_id="experiment-reproducibility-review",
                category="experiment",
                severity="moderate" if len(missing) >= 3 else "minor",
                title="实验与复现信号不足",
                summary=f"尚未识别到以下信息：{'、'.join(missing)}。这不等于实验错误，但会阻碍结果复核和公平比较。",
                fix="补充数据来源与划分、指标定义、基线/消融、重复运行与代码环境信息；对关键结果报告不确定性。",
                target=" ".join(paper_card.data_and_experiments.split()[:50]) or paper_card.problem_and_gap,
                evidence_cards=evidence_cards,
            )
        ]

    def _review_adversarial(
        self,
        text: str,
        paper_card: PaperCard,
        evidence_cards: list[EvidenceCard],
    ) -> list[ReviewFinding]:
        targets = self._strong_claims(self._sentences(text))
        if not targets:
            return [
                self._finding(
                    skill_id="adversarial-review",
                    category="adversarial",
                    severity="minor",
                    title="暂未识别到可压力测试的核心结论",
                    summary="稿件缺少明显的结论性或比较性表述，建议先明确论文希望读者相信的核心结论。",
                    fix="在摘要和结论中明确 1-3 个可验证的核心主张，并为每个主张绑定证据。",
                    target=paper_card.problem_and_gap,
                    evidence_cards=evidence_cards,
                )
            ]
        target = targets[0]
        return [
            self._finding(
                skill_id="adversarial-review",
                category="adversarial",
                severity="moderate",
                title="核心结论需要反方验证",
                summary=f"核心主张“{target[:180]}”可能受到替代解释、边界条件或样本外场景影响，当前第一版审查尚未看到明确的反例检验。",
                fix="增加边界样本、替代模型/解释、敏感性分析或更谨慎的表述，并把结论范围限制到实际证据覆盖的场景。",
                target=target,
                evidence_cards=evidence_cards,
            )
        ]

    def _finding(
        self,
        *,
        skill_id: str,
        category: str,
        severity: str,
        title: str,
        summary: str,
        fix: str,
        target: str,
        evidence_cards: list[EvidenceCard],
    ) -> ReviewFinding:
        return ReviewFinding(
            skill_id=skill_id,
            category=category,
            severity=severity,
            title=title,
            summary=summary,
            evidence_refs=self._evidence_refs(target, evidence_cards),
            recommended_fix=fix,
            confidence=0.62 if evidence_cards else 0.42,
        )

    def _summarize(
        self,
        paper_card: PaperCard,
        findings: list[ReviewFinding],
        evidence_cards: list[EvidenceCard],
    ) -> ReviewSummary:
        major_count = sum(item.severity == "major" for item in findings)
        moderate_count = sum(item.severity == "moderate" for item in findings)
        minor_count = sum(item.severity == "minor" for item in findings)
        score = max(0, min(100, 100 - major_count * 25 - moderate_count * 12 - minor_count * 4))
        strengths = []
        if paper_card.contributions:
            strengths.append("已识别出论文的主要贡献或核心主张。")
        if paper_card.method_summary:
            strengths.append("稿件包含可供方法审查使用的研究设计信息。")
        if evidence_cards:
            strengths.append(f"当前工作区已有 {len(evidence_cards)} 张证据卡，可继续做页码级复核。")
        priority_actions = [item.recommended_fix for item in findings if item.severity in {"major", "moderate"}][:4]
        return ReviewSummary(
            readiness_score=score,
            major_count=major_count,
            moderate_count=moderate_count,
            minor_count=minor_count,
            strengths=strengths,
            priority_actions=priority_actions,
        )

    @staticmethod
    def _sentences(text: str) -> list[str]:
        return [item.strip() for item in _SENTENCE_RE.split(text) if item.strip()]

    @staticmethod
    def _matching_sentences(sentences: Iterable[str], terms: tuple[str, ...], limit: int) -> list[str]:
        matches = [sentence for sentence in sentences if any(term in sentence.lower() for term in terms)]
        return matches[:limit]

    @staticmethod
    def _strong_claims(sentences: Iterable[str]) -> list[str]:
        terms = ("significant", "state-of-the-art", "best", "novel", "prove", "显著", "首次", "证明", "最优", "提升", "优于")
        return [sentence for sentence in sentences if any(term in sentence.lower() for term in terms)]

    @staticmethod
    def _evidence_refs(target: str, evidence_cards: list[EvidenceCard]) -> list[ReviewEvidenceRef]:
        if not evidence_cards:
            return [ReviewEvidenceRef(source="manuscript", section="manuscript", quote=target[:240])]
        target_tokens = set(_TOKEN_RE.findall(target.lower()))
        scored = []
        for card in evidence_cards:
            card_tokens = set(_TOKEN_RE.findall(f"{card.summary} {card.source_quote}".lower()))
            score = len(target_tokens & card_tokens)
            scored.append((score, card))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            ReviewEvidenceRef(
                source="reference",
                paper_id=card.paper_id,
                page=card.page,
                section=card.section,
                quote=card.source_quote[:240],
            )
            for score, card in scored[:2]
            if score > 0
        ] or [
            ReviewEvidenceRef(
                source="reference",
                paper_id=evidence_cards[0].paper_id,
                page=evidence_cards[0].page,
                section=evidence_cards[0].section,
                quote=evidence_cards[0].source_quote[:240],
            )
        ]


reviewer_skill_runner = ReviewerSkillRunner()
