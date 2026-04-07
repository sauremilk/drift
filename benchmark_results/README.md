# Benchmark Results

Last verified: 2026-04-07

This directory contains checked-in evidence artifacts referenced by the public docs, study notes, and release history.

Use it as an index, not as a single headline metric.

## What lives here

- `mutation_benchmark.json`: controlled mutation-benchmark output.
- `vX.Y.Z*_feature_evidence.json`: versioned feature-evidence artifacts for specific releases or improvement waves.
- `ground_truth_analysis.json`: precision-study support artifact.
- `all_results.json`: aggregated benchmark summaries.
- `signal_coverage_matrix.json`: signal-to-evidence coverage overview.
- `archive/`, `mutations/`, `package_kpis/`, `repair/`: supporting raw or derived benchmark material.

## Recommended reading order

1. Start with `../docs-site/benchmarking.md` for the conservative public interpretation.
2. Continue with `../docs/STUDY.md` for methodology, caveats, and historical baselines.
3. Open the raw JSON artifacts here only when you want to inspect the underlying evidence directly.

## Interpretation notes

- Some benchmark claims are historical baselines and do not automatically apply to the current live signal model.
- Feature-evidence files document narrow changes; they are not a substitute for the full study.
- Raw artifacts are intentionally preserved for auditability, which means this directory contains both current and historical material.