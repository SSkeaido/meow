---
name: adversarial-review
description: Stress-test the strongest claims in an academic paper with constructive counterarguments. Use when CitationGuard needs a red-team pass for alternative explanations, boundary cases, citation gaps, or overclaiming.
---

# Adversarial Review

Try to falsify the paper's highest-impact claims using only the paper and its approved evidence set.

## Workflow

1. Identify the strongest conclusion and the minimum evidence needed to support it.
2. Generate plausible alternative explanations, counterexamples, boundary cases, and failure modes.
3. Check whether the paper tested those alternatives or limited the claim appropriately.
4. Check for causal language, generalization, novelty, and certainty that exceed the evidence.
5. Prioritize issues that could change the conclusion; keep stylistic issues separate.

## Output contract

Return findings with:

- `category: adversarial`
- `severity: major | moderate | minor`
- `target_claim`
- `challenge`
- `evidence_refs[]`
- `what_would_resolve_it`
- `recommended_fix`
- `confidence`

Be specific and constructive. Do not invent external facts, do not accuse authors of misconduct without evidence, and do not convert a plausible challenge into a definitive rejection.
