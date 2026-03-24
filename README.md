# Drift — Find the architecture damage AI coding tools leave behind

[![CI](https://github.com/sauremilk/drift/actions/workflows/ci.yml/badge.svg)](https://github.com/sauremilk/drift/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/sauremilk/drift/graph/badge.svg)](https://codecov.io/gh/sauremilk/drift)
[![PyPI version](https://img.shields.io/pypi/v/drift-analyzer.svg)](https://pypi.org/project/drift-analyzer/)
[![Downloads](https://img.shields.io/pypi/dm/drift-analyzer)](https://pypi.org/project/drift-analyzer/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://pre-commit.com)
[![SARIF](https://img.shields.io/badge/output-SARIF-blueviolet)](https://docs.github.com/en/code-security/code-scanning)
[![TypeScript](https://img.shields.io/badge/TypeScript-optional-blue?logo=typescript)](https://www.typescriptlang.org/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Stars](https://img.shields.io/github/stars/sauremilk/drift?style=social)](https://github.com/sauremilk/drift)
[![Documentation](https://img.shields.io/badge/docs-mkdocs-blue)](https://sauremilk.github.io/drift/)

> **Repo:** `sauremilk/drift` · **Package:** `drift-analyzer` · **Command:** `drift` · **Requires:** Python 3.11+

**Drift is the deterministic coherence check for AI-assisted Python teams. Ruff finds local rule violations. Semgrep and CodeQL find security and policy issues. Drift finds the cross-file architectural erosion those tools do not model.**

### What drift catches that other checks usually don't

- **Ruff / formatters / type checkers:** local correctness and style signals, not cross-module coherence.
- **Semgrep / CodeQL / security scanners:** risky flows and policy violations, not whether patterns fragment across a codebase.
- **Sonar / maintainability dashboards:** broad quality heuristics, not a drift-specific score grounded in reproducible signal families.

Current public evidence: 15 real-world repositories in the study corpus, 6 scoring signals, and 1 report-only signal kept out of the composite score until its precision improves. [Full study →](STUDY.md) · [Trust & limitations](docs-site/benchmarking.md)

## Try it now

```bash
pip install drift-analyzer   # requires Python 3.11+
drift analyze --repo .
```

That's it — you'll see a drift score, module ranking, and actionable findings in seconds.

Before you try it on a work repo:

- Run `python --version` first. Drift currently requires Python 3.11+.
- If you only have Python 3.10 in CI today, wait to roll it out there until the runtime is available.

![drift CLI demo](demos/demo.gif)

### Try on a demo project (2 minutes)

```bash
git clone https://github.com/sauremilk/drift.git
cd drift/examples/demo-project
pip install drift-analyzer
drift analyze --repo .
```

The [demo project](examples/demo-project/) contains intentional drift patterns — you'll see pattern fragmentation, architecture violations, and duplicated logic in the output.

## Why drift

When your team uses Copilot, Cursor, or other AI coding tools, code passes CI — but the architecture quietly degrades:

- **Pattern fragmentation:** error handling is implemented 4 different ways across the same service
- **Boundary violations:** the API layer imports directly from the database layer
- **Silent duplication:** AI generates a new validator instead of finding the existing one
- **Churn hotspots:** the same files change every sprint because the structure is unclear

Your linter, type checker, and test suite won't catch this. Drift does — deterministically, without any LLM in the pipeline.

## Setup

### GitHub Action (recommended: start report-only)

```yaml
name: Drift

on: [push, pull_request]

jobs:
  drift:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write

    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: sauremilk/drift@v1
        with:
          fail-on: none           # report findings without blocking CI
          upload-sarif: "true"    # findings appear as PR annotations
```

Once the team has reviewed findings for a few sprints, tighten the gate:

```yaml
      - uses: sauremilk/drift@v1
        with:
          fail-on: high           # block only high-severity findings
          upload-sarif: "true"
```

### CI gate (local)

```bash
drift check --fail-on none    # report-only
drift check --fail-on high    # block on high-severity findings
```

### pre-commit hook

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: drift
        name: drift
        entry: drift check --fail-on high
        language: system
        pass_filenames: false
        always_run: true
```

More setup paths:

- [Quick Start](docs-site/getting-started/quickstart.md)
- [Configuration](docs-site/getting-started/configuration.md)
- [Team Rollout](docs-site/getting-started/team-rollout.md)

## What you get

```text
╭─ drift analyze  myproject/ ──────────────────────────────────────────────────╮
│  DRIFT SCORE  0.52  │  87 files  │  412 functions  │  AI: 34%  │  2.1s      │
╰──────────────────────────────────────────────────────────────────────────────╯

                        Module Drift Ranking
  Module                           Score  Findings  Top Signal
  ─────────────────────────────────────────────────────────────
  src/api/routes/                   0.71       12   PFS 0.85
  src/services/auth/                0.58        7   AVS 0.72
  src/db/models/                    0.41        4   MDS 0.61

┌──┬────────┬───────┬──────────────────────────────────────┬──────────────────────┐
│  │ Signal │ Score │ Title                                │ Location             │
├──┼────────┼───────┼──────────────────────────────────────┼──────────────────────┤
│◉ │ PFS    │  0.85 │ Error handling split 4 ways          │ src/api/routes.py:42 │
│◉ │ AVS    │  0.72 │ DB import in API layer               │ src/api/auth.py:18   │
│○ │ MDS    │  0.61 │ 3 near-identical validators          │ src/utils/valid.py   │
└──┴────────┴───────┴──────────────────────────────────────┴──────────────────────┘
```

Drift currently scores six signal families and reports one additional report-only signal:

- `PFS` Pattern Fragmentation
- `AVS` Architecture Violations
- `MDS` Mutant Duplicates
- `EDS` Explainability Deficit
- `TVS` Temporal Volatility
- `SMS` System Misalignment
- `DIA` Doc-Implementation Drift (reported, weight `0.00` in the composite score)

Signal details and scoring model:

- [Signal Reference](docs-site/algorithms/signals.md)
- [Algorithm Deep Dive](docs-site/algorithms/deep-dive.md)
- [Scoring Model](docs-site/algorithms/scoring.md)

## Ideal for

- **Python teams using AI coding tools** (Copilot, Cursor, Cody) in existing codebases
- **Tech leads** who want to catch structural erosion before it becomes team habit
- **CI pipelines** that need a deterministic architecture check without LLM infrastructure

## Who should adopt now

- teams with Python 3.11+ already available locally and in CI
- repositories with 20+ files and recurring refactors across modules
- teams using AI assistance enough that copy-modify drift and boundary erosion are real review problems

## Who should wait

- tiny repos where a few findings would dominate the score
- teams looking for bug finding, security review, or strict pass/fail quality gates on day one
- teams without Python 3.11+ in their execution path yet

## Best first target

Drift works best on Python repositories with 20+ files and some history. If you see too many findings on the first run:

1. Start with `drift check --fail-on none` to just observe.
2. Focus on findings with score ≥ 0.7 — those have the strongest signal.
3. Ignore generated code or vendor directories (configure exclusions in `drift.yaml`).

## Don't use drift if...

- you expect bug finding, security scanning, or type safety enforcement
- you need zero false positives on a tiny repository from day one
- you want one absolute score to replace code review judgment

Drift is most useful when teams treat the score as orientation and the findings as investigation prompts.

## Small-team rollout

The safest adoption path is progressive:

1. Start with `drift analyze` locally and review the top findings.
2. Add `drift check` in CI as report-only discipline for a short period.
3. Gate only on `high` findings once the team understands the output.
4. Tune config and policies only after reviewing real findings in your repo.

Recommended guides:

- [Team Rollout](docs-site/getting-started/team-rollout.md)
- [Finding Triage](docs-site/getting-started/finding-triage.md)
- [Benchmarking and Trust](docs-site/benchmarking.md)

## Trust and limitations

> **Public claims safe to repeat for v0.5.0:** Drift is deterministic, benchmarked on 15 real-world repositories in the current study corpus, and uses 6 scoring signals plus DIA as a report-only signal with weight `0.00` until precision improves.
>
> **What's limited:** Benchmark validation is single-rater; not yet independently replicated. Small repos can be noisy. Temporal signals depend on clone depth. The composite score is orientation, not a verdict.
>
> **What's next:** Independent external validation, multi-rater ground truth, signal-specific confidence intervals.

Drift is designed to earn trust through determinism and reproducibility:

- no LLMs in the detection pipeline
- reproducible CLI and CI output
- signal-specific interpretation instead of score-only messaging
- explicit benchmarking and known-limitations documentation

> **Drift vs. erosion:** Without `layer_boundaries` in `drift.yaml`, drift detects *emergent drift* — structural patterns that diverge without explicit prohibition. With configured `layer_boundaries`, drift additionally performs *conformance checking* against a defined architecture. Both modes are complementary: drift does not replace dedicated architecture conformance frameworks (e.g. [PyTestArch](https://github.com/zyskarch/pytestarch) for executable layer rules in pytest), but catches cross-file coherence issues those tools do not model.

Start with the strongest, most actionable findings first. If a signal is noisy for your repository shape, tune or de-emphasize it instead of forcing an early hard gate.

Further reading:

- [Benchmarking and Trust](docs-site/benchmarking.md)
- [Full Study](STUDY.md)
- [Case Studies](docs-site/case-studies/index.md)

## Contributing

We welcome bug reports, signal improvements, and documentation fixes.
If you run drift on your codebase and get surprising results — good or bad — please [open an issue](https://github.com/sauremilk/drift/issues) or start a [discussion](https://github.com/sauremilk/drift/discussions).

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup instructions and good first issues.

## Documentation map

- [Getting Started](docs-site/getting-started/quickstart.md)
- [How It Works](docs-site/algorithms/deep-dive.md)
- [Benchmarking and Trust](docs-site/benchmarking.md)
- [Product Strategy](docs-site/product-strategy.md)
- [Contributor Guide](CONTRIBUTING.md)
- [Developer Guide](DEVELOPER.md)

## Status

drift has working CLI, GitHub Action, configuration, JSON/SARIF output, benchmark material, and active tests.

Feature maturity should still be read pragmatically:

- core Python analysis: stable
- CI and SARIF workflow: stable
- benchmark claims: documented, but should be interpreted per signal and methodology
- TypeScript support and selected advanced signals: evolving

## License

MIT. See [LICENSE](LICENSE).
