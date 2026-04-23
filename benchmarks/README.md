# Benchmarks

This directory contains the benchmark infrastructure for drift. It is designed to be
reproducible by anyone with a working Python environment and a `pip install -e '.[dev]'`
install of drift.

## Directory Structure

```
benchmarks/
├── corpus/              # Reference codebase (MyApp) with golden signal cache
├── defect_corpus/       # Curated real-world defect samples for recall measurement
├── gauntlet/            # Scenario suite for precision/recall signal testing
│   ├── scenarios/       # Scenario sub-directories (adversarial, fp_traps, …)
│   ├── evaluator/       # Evaluation harness
│   └── runners/         # Runner scripts
├── brief_study_corpus.json   # Corpus for drift_brief A/B study
├── oracle_repos.json         # Curated external repos for FP rate measurement
└── perf_budget.json          # Wall-clock performance budget (fail-gate for CI)
```

## Running Benchmarks

### Performance budget check
```bash
pytest tests/test_perf_budget.py -v
```
Fails if drift exceeds `perf_budget.json` wall-clock thresholds on the corpus.

### Precision / Recall gate
```bash
pytest tests/test_precision_recall.py -v --tb=short
```
Measures signal precision/recall against `benchmarks/gauntlet/scenarios/`.

### Defect corpus recall
```bash
pytest tests/test_defect_corpus.py -v
```
Measures recall against the external-ground-truth defect corpus.
See [`defect_corpus/README.md`](defect_corpus/README.md) for methodology.

### Mutation benchmark
```bash
python scripts/_mutation_benchmark.py
```
Generates `benchmark_results/mutation_benchmark.json`. Requires the dev install.

### Full benchmark suite
```bash
make check   # lint + typecheck + quick tests (includes perf gate)
```

## Gauntlet Scenario Categories

| Directory | Purpose |
|---|---|
| `adversarial/` | Patterns designed to trigger false positives |
| `ambivalent/` | Borderline cases — expected output may vary by config |
| `fn_traps/` | False-negative traps (drift must not miss these) |
| `fp_traps/` | False-positive traps (drift must not flag these) |
| `graduated/` | Progressive severity scenarios |
| `real_world/` | Scenarios derived from real-world codebases |

## Oracle Repos (FP Rate)

`oracle_repos.json` lists professionally maintained Python projects (requests, httpx, …)
used to measure the false-positive rate on clean, idiomatic code.
Reproduce with:
```bash
pytest tests/test_smoke_real_repos.py -v   # slow, clones repos
```

## Benchmark Results

Results from CI runs are stored in `benchmark_results/`. See
[`benchmark_results/README.md`](../benchmark_results/README.md) for a description of
each JSON file and how to reproduce it.
