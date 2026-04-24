# Trust and Evidence

This page is the shortest path to the evidence behind drift.

It is designed for teams that need to answer a practical question before rollout: what can we trust today, what should we verify locally, and where is the raw material?

## Public claims safe to repeat

- drift uses 19 scoring signals in the composite score (5 additional signals are report-only)
- the conservative public benchmark claim is 77% strict precision / 95% lenient on the historical v0.5 six-signal baseline
- the current study corpus covers 15 real-world repositories
- all analysis is deterministic and does not use an LLM in the detector pipeline
- package metadata currently uses the PyPI Beta classifier, while rollout guidance remains conservative because maturity still varies across the broader product surface

## Security boundary evidence

For repository-analyzer deployments, the most relevant security question is how
drift behaves on untrusted file trees and git metadata.

Current security controls are documented in `SECURITY.md`, including path
normalization, symlink skipping, a 5 MB per-file guardrail, hardened git
subprocess usage, and parser non-execution behavior.

Supporting regression tests include:

- `tests/test_git_history_safety.py`
- `tests/test_file_discovery.py`
- `tests/test_cache_resilience.py`

## Benchmark evidence

- **Conservative public benchmark claim:** 77% strict precision / 95% lenient on a score-weighted sample of 286 findings across 5 repositories in the historical v0.5 six-signal baseline (non-circular heuristic classification; 51 Disputed findings where only score evidence was available — independent multi-rater validation pending)
- precision has not been revalidated for the current 15-signal model; treat the v0.5 number as a historical reference point, not as a blanket claim for the current composite model
- **v0.7.1 (2026-03-27):** 88% detection recall on a controlled mutation benchmark of 17 injected patterns across 10 signal types (synthetic repo with git history; 2 patterns undetected: 1 return-pattern fragmentation variant, 1 system-misalignment below threshold)
- **v0.5 baseline (historical):** 86% detection rate on a 14-pattern benchmark
- self-analysis of drift reports a score of 0.442 (MEDIUM)

These numbers are summarized from [Benchmark Study](study.md) and should be interpreted together with the limitations below.

## What the evidence means

The strongest current claim is not that every finding is equally reliable.

The strongest current claim is that drift provides a deterministic and inspectable process, with benchmarked evidence, for surfacing structural drift patterns that teams can calibrate against their own repository.

## Known limitations to keep visible

- classification uses non-circular structural heuristics; 51 of 286 findings are Disputed (score-only evidence, no structural confirmation)
- the labeled precision sample is score-weighted and over-represents higher-confidence findings
- TVS shows 0% strict precision because titles lack structural keywords — this reflects a classification-method limitation, not necessarily signal quality
- AVS sample size (n=20) remains below the n≥30 threshold for reliable per-signal precision
- recall was measured on a synthetic mutation benchmark, not on every naturally evolving repository shape
- DIA has known precision limitations and received a conservative weight (0.04) when promoted to scoring in v0.7.0
- temporal signals depend on repository history quality and clone depth
- the composite score is orientation, not a verdict

## Recommended evaluation posture

1. start with report-only usage
2. inspect findings per signal
3. gate only on high-confidence cases
4. tune based on recurring evidence in your own repo

## How to talk about release maturity

Use a split message instead of a single blanket adjective:

- package classifier: Beta
- core Python analysis: stable
- CI and SARIF workflow: stable
- TypeScript support: experimental
- embeddings-based parts: optional / experimental
- benchmark methodology: evolving

This keeps external communication honest without turning the Beta classifier into a blanket production guarantee for every surface.

See [Stability and Release Status](stability.md).

## Where the detailed material lives

- [Benchmarking and Trust](benchmarking.md)
- [Benchmark Study](study.md)
- [Case Studies](case-studies/index.md)
- [Signal Reference](algorithms/signals.md)

## Repository artifacts

The raw benchmark and audit artifacts live in the repository alongside the docs. That matters because teams can inspect the material instead of relying on a black-box headline metric.

Useful starting points:

- `benchmark_results/all_results.json` — aggregate scores, file counts, and finding totals for every corpus repository in a single file
- `benchmark_results/ground_truth_analysis.json` — the labeled precision-analysis matrix (TP / FP / Disputed per signal)
- `benchmark_results/archive/validation/ground_truth_labels.json` — underlying per-finding ground-truth labels used by the precision analysis
- `benchmark_results/mutation_benchmark.json` — controlled recall benchmark (17 injected mutation patterns, detection rate per signal)
- `benchmark_results/archive/validation/holdout_validation.json` — leave-one-out cross-validation snapshots kept apart from the main analysis narrative
- `benchmark_results/archive/single_repo/fastapi.json`, `benchmark_results/archive/single_repo/pydantic.json`, and `benchmark_results/archive/single_repo/django.json` — full per-repository analysis output used by the case studies

These artifacts are most useful when read together with [Benchmarking and Trust](benchmarking.md) and [Benchmark Study](study.md), because the methodology and the limits determine how the numbers should be interpreted.

## What to verify locally before making policy decisions

- whether your strongest findings line up with places the team already finds expensive to change
- whether generated or exceptional directories should be excluded
- whether boundary violations reflect real architecture intent or acceptable convenience imports
- whether temporal signals have enough git history to be meaningful in your clone

## Next pages

- [Architecture Drift Detection for Python](use-cases/architecture-drift-python.md)
- [CI Architecture Checks with SARIF](use-cases/ci-architecture-checks-sarif.md)
- [FAQ](faq.md)
