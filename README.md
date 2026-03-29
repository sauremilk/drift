# Drift — Finds the architecture erosion that AI-generated code silently introduces

[![CI](https://github.com/sauremilk/drift/actions/workflows/ci.yml/badge.svg)](https://github.com/sauremilk/drift/actions/workflows/ci.yml)
[![Precision](https://img.shields.io/badge/precision-97.3%25-brightgreen)](docs/STUDY.md)
[![Coverage](https://img.shields.io/badge/coverage-78%25-brightgreen)](https://github.com/sauremilk/drift/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/drift-analyzer?cacheSeconds=300)](https://pypi.org/project/drift-analyzer/)
[![Downloads/month](https://static.pepy.tech/badge/drift-analyzer/month)](https://pepy.tech/project/drift-analyzer)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://pre-commit.com)
[![SARIF](https://img.shields.io/badge/output-SARIF-blueviolet)](https://docs.github.com/en/code-security/code-scanning)
[![TypeScript](https://img.shields.io/badge/TypeScript-optional-blue?logo=typescript)](https://www.typescriptlang.org/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Stars](https://img.shields.io/github/stars/sauremilk/drift?style=social)](https://github.com/sauremilk/drift)
[![Documentation](https://img.shields.io/badge/docs-mkdocs-blue)](https://sauremilk.github.io/drift/)

> **Repo:** `sauremilk/drift` · **Package:** `drift-analyzer` · **Command:** `drift` · **Requires:** Python 3.11+
>
> **97.3% precision** on 263 ground-truth findings across 15 repositories · deterministic · no LLM in pipeline · [full study →](docs/STUDY.md)

## Start here

**What is drift?**

Drift is a deterministic static analyzer that finds the architecture erosion AI-generated code silently introduces — pattern fragmentation, boundary violations, and structural hotspots — before they become normal team habits. In seconds, without any LLM in the pipeline.

**Who is it for?**

- Python teams with fast-growing codebases where architecture matters
- Tech leads who want fast structural feedback, not just style or type checks
- Teams using AI coding tools and seeing more cross-file drift across modules

### 1-minute quickstart

```bash
pip install -q drift-analyzer
drift analyze --repo .
```

That gives you a drift score, the hottest modules, and actionable findings in one run.

## Choose your path

- **Not sure where to start?** Use the central docs routing page: [Start Here](docs-site/start-here.md).
- **Casual user:** install drift, run `drift analyze --repo .`, and start with [Quick Start](docs-site/getting-started/quickstart.md) and [Configuration](docs-site/getting-started/configuration.md).
- **Evaluator:** review [Example Findings](docs-site/product/example-findings.md), [Trust and Evidence](docs-site/trust-evidence.md), and [Stability and Release Status](docs-site/stability.md) before deciding on rollout.
- **Contributor:** use [CONTRIBUTING.md](CONTRIBUTING.md) once you are ready to submit a fix, improve docs, or work on signal quality.
- **Core maintainer:** use [CONTRIBUTING.md](CONTRIBUTING.md), [DEVELOPER.md](DEVELOPER.md), and [POLICY.md](POLICY.md) for the full quality, architecture, and release guardrails.

## Release status

The PyPI classifier remains `Development Status :: 3 - Alpha` intentionally.

That is not a claim that the whole tool is immature. It is a conservative release signal for a product whose core Python analysis is already usable, while some adjacent surfaces still have mixed maturity.

| Area | Status | What that means today |
|---|---|---|
| Core Python analysis | Stable | Primary analysis path, CLI usage, and main signal set are the most production-ready parts of drift. |
| CI and SARIF workflow | Stable | Suitable for report-only rollout now, then selective gating once teams calibrate findings locally. |
| TypeScript support | Experimental | Optional support exists, but Python remains the primary target and the more validated path. |
| Embeddings-based parts | Optional / experimental | Not required for the core detector path and should be treated as exploratory add-ons. |
| Benchmark methodology | Evolving | Public and reproducible, but still conservative in its claims and not the final word on every repository shape. |

Why keep Alpha for now: release signaling should reflect the least mature user-facing surfaces, not only the strongest path. Drift already has stable core workflows, but the overall product story still includes experimental and evolving areas.

See [Stability and Release Status](docs-site/stability.md) for the explicit matrix and the criteria for a future move toward Beta.

### Example output

```text
DRIFT SCORE  0.52
Top finding: PFS 0.85  Error handling split 4 ways  at src/api/routes.py:42
Next action: consolidate variants into one shared pattern
```

### If you want CI, use this

```yaml
- uses: sauremilk/drift@v1
  with:
    fail-on: none
    upload-sarif: "true"
```

Start report-only first. Tighten to `fail-on: high` once the team understands the signal quality in its own repo.

### Try it on a demo project

```bash
git clone https://github.com/sauremilk/drift.git
cd drift/examples/demo-project
pip install -q drift-analyzer
drift analyze --repo .
```

The [demo project](examples/demo-project/) contains intentional drift patterns, so you get useful findings immediately.

![drift CLI demo](https://raw.githubusercontent.com/sauremilk/drift/master/demos/demo.gif)

## Why drift

When your team uses GitHub Copilot, Cursor, or other AI coding tools, code passes CI while the repository quietly accumulates architectural drift:

- **Pattern fragmentation:** error handling is implemented 4 different ways across the same service
- **Boundary violations:** the API layer imports directly from the database layer
- **Silent duplication:** AI generates a new validator instead of finding the existing one
- **Churn hotspots:** the same files change every sprint because the structure is unclear

Your linter, type checker, and test suite won't catch this. Drift does — deterministically, without any LLM in the pipeline. That makes drift useful for architectural drift detection in AI-accelerated Python codebases, with architecture erosion analysis and cross-file coherence findings that teams can act on.

## What drift catches that other checks usually don't

- **Ruff / formatters / type checkers:** local correctness and style signals, not cross-module coherence.
- **Semgrep / CodeQL / security scanners:** risky flows and policy violations, not whether patterns fragment across a codebase.
- **Sonar / maintainability dashboards:** broad quality heuristics, not a drift-specific score grounded in reproducible signal families.

Current public evidence: 15 real-world repositories in the study corpus, 15 scoring signals (all contributing to the composite score), and auto-calibration that rebalances weights at runtime. [Full study →](docs/STUDY.md) · [Trust & limitations](docs-site/benchmarking.md)

## Use cases

### Pattern fragmentation in a connector layer

**Problem:** A FastAPI service has 4 connectors, each implementing error handling differently — bare `except`, custom exceptions, retry decorators, and silent fallbacks.

**Solution:**
```bash
drift analyze --repo . --sort-by impact --max-findings 5
```

**Output:** PFS finding with score 0.96 — "26 error_handling variants in connectors/" — shows exactly which files diverge and suggests consolidation.

### Architecture boundary violation in a monorepo

**Problem:** A database model file imports directly from the API layer, creating a circular dependency that breaks test isolation.

**Solution:**
```bash
drift check --fail-on high
```

**Output:** AVS finding — "DB import in API layer at src/api/auth.py:18" — blocks the CI pipeline until the import direction is fixed.

### Duplicate utility code from AI-generated scaffolding

**Problem:** AI code generation created 6 identical `_run_async()` helper functions across separate task files instead of finding the existing shared utility.

**Solution:**
```bash
drift analyze --repo . --format json | jq '.findings[] | select(.signal=="MDS")'
```

**Output:** MDS findings listing all 6 locations with similarity scores ≥ 0.95, enabling a single extract-to-shared-module refactoring.

## Concrete example findings

If you are evaluating drift, the fastest way to understand the value is to look at concrete findings rather than abstract signal names.

See [docs-site/product/example-findings.md](docs-site/product/example-findings.md) for 5 short examples with code, the likely finding, why it matters, and how to fix it:

- Pattern fragmentation: three incompatible error-handling patterns in one module
- Mutant duplicate: two copied formatter functions that will drift apart later
- Architecture violation: a `db/` module importing from `api/`
- Doc-implementation drift: README structure that no longer matches the repo
- Temporal volatility: a small file that became a churn hotspot in git history

## More setup options

### Full GitHub Action (recommended: start report-only)

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

The fastest way to add drift to your workflow:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/sauremilk/drift
    rev: v0.9.0
    hooks:
      - id: drift-check          # blocks on high-severity findings
      # - id: drift-report        # report-only alternative (start here)
```

Or use a local hook if you already have drift installed:

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

Drift scores all 15 signal families:

- `PFS` Pattern Fragmentation (0.16)
- `AVS` Architecture Violations (0.16)
- `MDS` Mutant Duplicates (0.13)
- `TVS` Temporal Volatility (0.13)
- `EDS` Explainability Deficit (0.09)
- `SMS` System Misalignment (0.08)
- `DIA` Doc-Implementation Drift (0.04)
- `BEM` Broad Exception Monoculture (0.04)
- `TPD` Test Polarity Deficit (0.04)
- `NBV` Naming Contract Violation (0.04)
- `GCD` Guard Clause Deficit (0.03)
- `BAT` Bypass Accumulation (0.03)
- `ECM` Exception Contract Drift (0.03)
- `COD` Cohesion Deficit (0.01)
- `CCC` Co-Change Coupling (0.005)

Signal details and scoring model:

- [Signal Reference](docs-site/algorithms/signals.md)
- [Algorithm Deep Dive](docs-site/algorithms/deep-dive.md)
- [Scoring Model](docs-site/algorithms/scoring.md)

## How drift compares

Data sourced from [STUDY.md](docs/STUDY.md) §9 and [benchmark_results/](benchmark_results/).

| Capability | drift | SonarQube | pylint / mypy | jscpd / CPD |
|---|:---:|:---:|:---:|:---:|
| Pattern Fragmentation (N variants per module) | Yes | No | No | No |
| Near-Duplicate Detection (AST structural) | Yes | Partial (text) | No | Yes (text) |
| Architecture Violation (layer + circular deps) | Yes | Partial | No | No |
| Temporal Volatility (churn anomalies) | Yes | No | No | No |
| System Misalignment (novel imports) | Yes | No | No | No |
| Composite Health Score | Yes | Yes (different) | No | No |
| Zero Config (no server needed) | Yes | No (server) | Partial | Yes |
| SARIF Output (GitHub Code Scanning) | Yes | Yes | No | No |
| TypeScript Support | Optional ¹ | Yes | No | Yes |

¹ Experimental via `drift-analyzer[typescript]`. Python is the primary target.

Drift is designed to **complement** linters and security scanners, not replace them. Recommended stack: linter (style) + type checker (types) + drift (coherence) + security scanner (SAST).

Full comparison: [STUDY.md §9 — Tool Landscape Comparison](docs/STUDY.md)

## Ideal for

- **Python teams using AI coding tools** (Copilot, Cursor, Cody) in existing codebases
- **Tech leads** who want to catch structural erosion before it becomes team habit
- **CI pipelines** that need a deterministic architecture check without LLM infrastructure

Teams often describe drift as an architectural linter for repositories where GitHub Copilot and similar assistants accelerate local delivery faster than shared design conventions can keep up.

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

> **Public claims safe to repeat for v0.8.2:** Drift is deterministic, benchmarked on 15 real-world repositories in the current study corpus, and uses 15 scoring signals with auto-calibration for runtime weight rebalancing and small-repo noise suppression.
>
> **What's limited:** Benchmark validation is single-rater; not yet independently replicated. Small repos can be noisy. Temporal signals depend on clone depth. The composite score is orientation, not a verdict.
>
> **What's next:** Independent external validation, multi-rater ground truth, signal-specific confidence intervals.

Drift is designed to earn trust through determinism and reproducibility:

- no LLMs in the detection pipeline
- reproducible CLI and CI output
- signal-specific interpretation instead of score-only messaging
- explicit benchmarking and known-limitations documentation

### Interpreting the score

The drift score measures **structural entropy**, not code quality. Keep these principles in mind:

- **Interpret deltas, not snapshots.** Use `drift trend` to track changes over time. A single score in isolation has limited meaning.
- **Temporary increases are expected during migrations.** Two coexisting patterns (old and new) will raise PFS/MDS signals. This is the migration happening, not a problem.
- **Deliberate polymorphism is not erosion.** Strategy, Adapter, and Plugin patterns produce structural similarity that MDS flags as duplication. Findings include a `deliberate_pattern_risk` hint — verify intent before acting.
- **The score rewards reduction, not correctness.** Deleting code lowers the score just like refactoring does. Do not optimize for a low score — optimize for understood, intentional structure.

For a detailed discussion of epistemological boundaries (what drift can and cannot see), see [STUDY.md §14](docs/STUDY.md).

> **Drift vs. erosion:** Without `layer_boundaries` in `drift.yaml`, drift detects *emergent drift* — structural patterns that diverge without explicit prohibition. With configured `layer_boundaries`, drift additionally performs *conformance checking* against a defined architecture. Both modes are complementary: drift does not replace dedicated architecture conformance frameworks (e.g. [PyTestArch](https://github.com/zyskarch/pytestarch) for executable layer rules in pytest), but catches cross-file coherence issues those tools do not model.

Start with the strongest, most actionable findings first. If a signal is noisy for your repository shape, tune or de-emphasize it instead of forcing an early hard gate.

Further reading:

- [Benchmarking and Trust](docs-site/benchmarking.md)
- [Full Study](docs/STUDY.md)
- [Case Studies](docs-site/case-studies/index.md)

## Contributing

Drift seeks contributions that increase the credibility of static architecture findings: reproducible cases, better explainability, fewer false alarms, and clearer next actions.

If you run drift on your codebase and get surprising results — good or bad — please [open an issue](https://github.com/sauremilk/drift/issues) or start a [discussion](https://github.com/sauremilk/drift/discussions).

### New here? Start contributing

1. Pick an issue labelled [`good first issue`](https://github.com/sauremilk/drift/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)
2. `git clone https://github.com/sauremilk/drift.git && cd drift && make install`
3. `make test-fast` — confirm everything passes
4. Make your change, then open a PR

**Typical first contributions:**

- Add a ground-truth fixture for a false positive or false negative
- Improve a finding's explanation text to be more actionable
- Write a test for an untested edge case
- Fix or extend signal documentation with a concrete example

**What we value most:** reproducibility, explainability, false-alarm reduction.\
**What we deprioritize:** new output formats without insight value, comfort features, complexity without analysis improvement.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide and [ROADMAP.md](ROADMAP.md) for current priorities.

## Documentation map

- [Getting Started](docs-site/getting-started/quickstart.md)
- [How It Works](docs-site/algorithms/deep-dive.md)
- [Benchmarking and Trust](docs-site/benchmarking.md)
- [Product Strategy](docs-site/product-strategy.md)
- [Contributor Guide](CONTRIBUTING.md)
- [Developer Guide](DEVELOPER.md)

## Status

drift has working CLI, GitHub Action, configuration, JSON/SARIF output, benchmark material, and active tests.

Current release posture:

- PyPI classifier remains Alpha intentionally
- core Python analysis: stable
- CI and SARIF workflow: stable
- TypeScript support: experimental
- embeddings-based parts: optional / experimental
- benchmark methodology: evolving

Rationale and matrix: [Stability and Release Status](docs-site/stability.md)

## License

MIT. See [LICENSE](LICENSE).
