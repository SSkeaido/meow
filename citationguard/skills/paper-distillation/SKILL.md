---
name: paper-distillation
description: Distill an academic PDF or manuscript into a structured, evidence-linked paper card. Use when CitationGuard needs a reusable representation of a paper before citation auditing, peer review, literature synthesis, or revision comparison.
---

# Paper Distillation

Turn a paper into a compact structured representation before asking another reviewer to judge it.

## Workflow

1. Extract metadata: title, authors, venue, year, domain, paper type, and submission status.
2. Map the paper structure: problem, research gap, hypotheses, method, data, experiments, results, limitations, and claimed contributions.
3. Split broad claims into atomic claims that can be checked independently.
4. Attach every important claim to a page, section, figure, table, equation, or reference location.
5. Separate author-stated facts from reviewer inferences. Mark missing or ambiguous evidence instead of filling it in.
6. Record terminology, datasets, baselines, metrics, and key numbers consistently for later version comparison.

## Output contract

Return a `PaperCard` with:

- `metadata`
- `problem_and_gap`
- `contributions[]`
- `method_summary`
- `data_and_experiments`
- `key_claims[]` with `claim`, `evidence_refs[]`, `confidence`, and `scope`
- `limitations[]`
- `reproducibility_signals`
- `open_questions[]`

Use page-aware evidence references whenever the source is a PDF. Do not produce a generic abstract-only summary and do not claim that a paper is correct merely because its own text says so.
