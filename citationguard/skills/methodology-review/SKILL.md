---
name: methodology-review
description: Review the methodology of an academic paper or manuscript with evidence-linked findings. Use when CitationGuard needs to assess research questions, assumptions, design validity, methods, causal logic, or threats to validity.
---

# Methodology Review

Evaluate whether the research design is capable of answering the questions the paper claims to answer.

## Review dimensions

1. Problem formulation and hypothesis clarity.
2. Alignment between question, data, method, and claimed conclusion.
3. Assumptions, identification strategy, controls, and possible confounders.
4. Sampling, measurement, preprocessing, and leakage risks.
5. Whether the method is described precisely enough to reproduce or challenge.
6. Whether the limitations section honestly bounds the claims.

## Output contract

Return findings with:

- `category: methodology`
- `severity: major | moderate | minor`
- `finding`
- `evidence_refs[]`
- `why_it_matters`
- `recommended_fix`
- `confidence`

Separate an actual methodological flaw from a missing explanation. Never infer invalidity from unfamiliar terminology alone, and never issue an accept/reject decision without human review.
