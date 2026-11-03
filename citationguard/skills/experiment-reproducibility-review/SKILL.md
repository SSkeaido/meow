---
name: experiment-reproducibility-review
description: Audit experiments, statistics, baselines, and reproducibility signals in academic papers. Use when CitationGuard needs to check whether reported results are supported, comparable, and realistically reproducible.
---

# Experiment and Reproducibility Review

Check whether the empirical evidence is sufficient for the paper's claims and whether another researcher could reproduce the result.

## Review dimensions

1. Dataset source, size, inclusion criteria, splits, and contamination.
2. Baselines, comparison fairness, hyperparameters, and ablations.
3. Metric definitions, statistical tests, uncertainty, repeated runs, and sample sizes.
4. Consistency between text, tables, figures, captions, and reported numbers.
5. Code, data, model, environment, compute budget, and random-seed availability.
6. Unsupported extrapolation from benchmark results to real-world performance.

## Output contract

Return findings with:

- `category: experiment | statistics | reproducibility | consistency`
- `severity: major | moderate | minor`
- `finding`
- `evidence_refs[]`
- `missing_information[]`
- `recommended_fix`
- `confidence`

Treat omitted information as an uncertainty or reproducibility gap, not proof of fraud. Quote exact values and locations when flagging a contradiction.
