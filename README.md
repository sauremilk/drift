<div align="center">

# Drift

**Deterministic architecture erosion detection for AI-accelerated codebases**

[![CI](https://github.com/mick-gsk/drift/actions/workflows/ci.yml/badge.svg)](https://github.com/mick-gsk/drift/actions/workflows/ci.yml)
[![Precision (lenient)](https://img.shields.io/badge/dynamic/json?url=https://raw.githubusercontent.com/mick-gsk/drift/main/benchmark_results/ground_truth_analysis.json&query=%24.total.precision_lenient&label=precision%20lenient&color=yellow)](benchmark_results/ground_truth_analysis.json)
[![Signals](https://img.shields.io/badge/dynamic/json?url=https://raw.githubusercontent.com/mick-gsk/drift/main/benchmark_results/signal_coverage_matrix.json&query=%24.current_total&label=signals&color=blue)](benchmark_results/signal_coverage_matrix.json)
[![codecov](https://codecov.io/gh/mick-gsk/drift/branch/main/graph/badge.svg)](https://codecov.io/gh/mick-gsk/drift)
[![SARIF](https://img.shields.io/badge/output-SARIF-blueviolet)](https://docs.github.com/en/code-security/code-scanning)
[![Agent API](https://img.shields.io/badge/API-MCP%20agent--native-green)](docs/STUDY.md#15-agent-loop-efficiency)
<br>
[![PyPI](https://img.shields.io/pypi/v/drift-analyzer?cacheSeconds=300)](https://pypi.org/project/drift-analyzer/)
[![Python versions](https://img.shields.io/pypi/pyversions/drift-analyzer)](https://pypi.org/project/drift-analyzer/)
[![License](https://img.shields.io/github/license/mick-gsk/drift)](LICENSE)
[![Stars](https://img.shields.io/github/stars/mick-gsk/drift?style=social)](https://github.com/mick-gsk/drift)

97.3% precision (single-rater) · 23 signals · deterministic · no LLM in pipeline · [full study](docs/STUDY.md) · [docs](https://mick-gsk.github.io/drift/)

</div>

AI coding tools write code that works — but doesn't fit. Error handling fragments across 4 patterns, layer boundaries erode, near-identical utilities accumulate silently. **Drift finds exactly that:** deterministic structural analysis in seconds, no LLM required.

<div align="center">
  <img src="demos/demo.gif" alt="drift analyze demo" width="720">
</div>

---

```bash
pip install drift-analyzer
drift analyze --repo .
```

```text
╭─ drift analyze  myproject/ ──────────────────────────────────────────────────╮
│  DRIFT SCORE  0.52  Δ -0.031 ↓ improving  │  87 files  │  AI: 34%  │  2.1s │
╰──────────────────────────────────────────────────────────────────────────────╯

  Module                  Score  Bar                   Findings  Top Signal
  src/api/routes/          0.71  ██████████████░░░░░░       12   PFS 0.85
  src/services/auth/       0.58  ███████████░░░░░░░░░        7   AVS 0.72
  src/db/models/           0.41  ████████░░░░░░░░░░░░        4   MDS 0.61

  ◉ PFS  0.85  Error handling split 4 ways
               → src/api/routes.py:42
               → Next: consolidate into shared error handler

  ◉ AVS  0.72  DB import in API layer
               → src/api/auth.py:18
               → Next: move DB access behind service interface
```

## What drift catches

Drift finds the structural problems AI-generated code introduces quietly: the same error handling done 4 different ways, database imports leaking into the API layer, near-identical helper functions across 6 files. Problems that pass every test but make the codebase harder to change.

### Try it now

```bash
drift analyze --repo .          # see your top findings
drift explain PFS               # learn what a signal means
drift fix-plan --repo .         # get actionable repair tasks
```

### Add to CI (start report-only)

```yaml
- uses: mick-gsk/drift@v1
  with:
    fail-on: none               # report findings without blocking
    upload-sarif: "true"        # findings appear as PR annotations
```

Once the team trusts the output, tighten: `fail-on: high`.

More: [Quick Start](docs-site/getting-started/quickstart.md) · [Example Findings](docs-site/product/example-findings.md) · [Team Rollout](docs-site/getting-started/team-rollout.md)

## AI-assisted workflows

Drift integrates with AI coding sessions (Copilot, Cursor, Claude) and MCP-capable editors:

```bash
drift scan --repo . --max-findings 5   # session baseline for agents
drift diff --staged-only               # pre-commit check
drift mcp --serve                      # MCP server for IDE integration
drift fix-plan --repo .                # agent-friendly repair tasks
```

Full setup: [Integrations](docs-site/integrations.md) · [MCP](docs-site/integrations.md) · [Vibe-Coding Guide](examples/vibe-coding/README.md)

## Why teams use drift

Your linter, type checker, and test suite can tell you whether code is valid. They do not tell you whether the repository is quietly splitting into incompatible patterns across modules.

Drift focuses on that gap:

- **Ruff / formatters / type checkers:** local correctness and style, not cross-module coherence.
- **Semgrep / CodeQL / security scanners:** risky flows and policy violations, not architectural consistency.
- **Maintainability dashboards:** broad quality heuristics, not a drift-specific score with reproducible signal families.

Current public evidence: 15 real-world repositories in the study corpus, 22 signal families (15 scoring-active, 7 report-only), and auto-calibration that rebalances weights at runtime. [Full study →](docs/STUDY.md) · [Trust & limitations](docs-site/benchmarking.md)

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

## Setup and rollout options

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

      - uses: mick-gsk/drift@v1
        with:
          fail-on: none           # report findings without blocking CI
          upload-sarif: "true"    # findings appear as PR annotations
```

Once the team has reviewed findings for a few sprints, tighten the gate:

```yaml
      - uses: mick-gsk/drift@v1
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
  - repo: https://github.com/mick-gsk/drift
    rev: v1.4.2
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

Project operations:

- [Contributor Guide](CONTRIBUTING.md)
- [Developer Guide](DEVELOPER.md)
- [Maintainer Runbook](docs/MAINTAINER_RUNBOOK.md)
- [Repository Governance](docs/REPOSITORY_GOVERNANCE.md)

If you want example findings before integrating, start with [docs-site/product/example-findings.md](docs-site/product/example-findings.md).

## All 22 signals

Drift scores 22 signal families (15 scoring-active, 7 report-only) — from pattern fragmentation and architecture violations to temporal volatility, security-by-default checks, and co-change coupling. Each finding includes a severity, file location, and concrete next action.

`drift explain <SIGNAL>` shows what any signal detects and how to fix it.

[Signal Reference](docs-site/algorithms/signals.md) · [Algorithm Deep Dive](docs-site/algorithms/deep-dive.md) · [Scoring Model](docs-site/algorithms/scoring.md)

Agent output reference: [Negative Context](docs-site/reference/negative-context.md)

## How drift compares

Data sourced from [STUDY.md](docs/STUDY.md) §9 and [benchmark_results/](benchmark_results/).

| Capability | drift | SonarQube | pylint / mypy | jscpd / CPD |
|---|:---:|:---:|:---:|:---:|
| Pattern Fragmentation across modules | Yes | No | No | No |
| Near-Duplicate Detection | Yes | Partial (text) | No | Yes (text) |
| Architecture Violation signals | Yes | Partial | No | No |
| Temporal / change-history signals | Yes | No | No | No |
| GitHub Code Scanning via SARIF | Yes | Yes | No | No |
| Zero server setup | Yes | No | Partial | Yes |
| TypeScript Support | Optional ¹ | Yes | No | Yes |

¹ Experimental via `drift-analyzer[typescript]`. Python is the primary target.

Drift is designed to **complement** linters and security scanners, not replace them. Recommended stack: linter (style) + type checker (types) + drift (coherence) + security scanner (SAST).

Full comparison: [STUDY.md §9 — Tool Landscape Comparison](docs/STUDY.md)

## Is drift a good fit?

Drift is a strong fit for:

- Python teams using AI coding tools in repositories where architecture matters
- repositories with 20+ files and recurring refactors across modules
- teams that want deterministic architectural feedback in local runs and CI

Wait or start more cautiously if:

- the repository is tiny and a few findings would dominate the score
- you need bug finding, security review, or type-safety enforcement rather than structural analysis
- Python 3.11+ is not available in your local and CI execution path yet

The safest rollout path is progressive:

1. Start with `drift analyze` locally and review the top findings.
2. Add `drift check --fail-on none` in CI as report-only discipline.
3. Gate only on `high` findings once the team understands the output.
4. Ignore generated or vendor code and tune config only after reviewing real findings in your repo.

Recommended guides:

- [Team Rollout](docs-site/getting-started/team-rollout.md)
- [Finding Triage](docs-site/getting-started/finding-triage.md)
- [Benchmarking and Trust](docs-site/benchmarking.md)

## Trust and limitations

> **Public claims safe to repeat today:** Drift is deterministic, benchmarked on 15 real-world repositories in the current study corpus, and uses 22 signal families (15 scoring-active, 7 report-only) with auto-calibration for runtime weight rebalancing and small-repo noise suppression.
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

## Test quality

- **1 645+ tests**, 0 regressions
- **Mutation kill rate: 100 %** (23/23 mutants killed)
  - All 5 core signals (PFS, AVS, MDS, EDS, GCD) at 100 %
- Baseline: [`benchmark_results/mutation_baseline.json`](benchmark_results/mutation_baseline.json)

## Release status

The PyPI classifier is `Development Status :: 4 - Beta`.

Core analysis and CI workflow are stable; some adjacent surfaces remain intentionally marked as experimental.

Current release posture:

- core Python analysis: stable
- CI and SARIF workflow: stable
- TypeScript support: experimental
- embeddings-based parts: optional / experimental
- benchmark methodology: evolving

Full rationale and matrix: [Stability and Release Status](docs-site/stability.md)

## Contributing

Drift's biggest blind spots are found by people running it on codebases the maintainers have never seen. **Your real-world experience is a direct contribution to signal quality** — whether you write code or not.

If Drift surprised you with an unexpected result, that's valuable feedback: [open an issue](https://github.com/mick-gsk/drift/issues) or start a [discussion](https://github.com/mick-gsk/drift/discussions). A well-documented false positive can be more valuable than a new feature.

| I want to… | Go here |
|---|---|
| Ask a usage question | [Discussions](https://github.com/mick-gsk/drift/discussions) |
| Report a false positive / false negative | [FP/FN template](https://github.com/mick-gsk/drift/issues/new?template=false_positive.md) |
| Report a bug | [Bug report](https://github.com/mick-gsk/drift/issues/new?template=bug_report.md) |
| Suggest a feature | [Feature request](https://github.com/mick-gsk/drift/issues/new?template=feature_request.md) |
| Propose a contribution before coding | [Contribution proposal](https://github.com/mick-gsk/drift/issues/new?template=contribution_proposal.md) |
| Report a security vulnerability | [SECURITY.md](SECURITY.md) — not a public issue |

### New here? Start contributing

You don't need to understand the whole analyzer to help. Start at the level that fits your time:

1. **15 min:** Fix a typo or clarify a docs example → open a PR directly
2. **30 min:** Report an unexpected finding with reproduction steps → [FP/FN template](https://github.com/mick-gsk/drift/issues/new?template=false_positive.md)
3. **1 hour:** Add an edge-case test → pick a [`good first issue`](https://github.com/mick-gsk/drift/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)
4. **2+ hours:** Improve signal logic or finding explanations → see [CONTRIBUTING.md](CONTRIBUTING.md)

```bash
git clone https://github.com/mick-gsk/drift.git && cd drift && make install
make test-fast    # confirm everything passes, then start
```

**First contribution? We'll help you scope it.** Open a [contribution proposal](https://github.com/mick-gsk/drift/issues/new?template=contribution_proposal.md) or ask in [Discussions](https://github.com/mick-gsk/drift/discussions) if you're unsure where to start.

**Typical first contributions:**

- Report a false positive or false negative with reproduction steps
- Add a ground-truth fixture for a signal edge case
- Improve a finding's explanation text to be more actionable
- Write a test for an untested edge case
- Clarify docs or add a configuration example

**What we value most:** reproducibility, explainability, false-alarm reduction.
**What we deprioritize:** new output formats without insight value, comfort features, complexity without analysis improvement.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide, contributor types, and the contribution ladder. See [ROADMAP.md](ROADMAP.md) for current priorities.

## Documentation map

- [Getting Started](docs-site/getting-started/quickstart.md)
- [How It Works](docs-site/algorithms/deep-dive.md)
- [Benchmarking and Trust](docs-site/benchmarking.md)
- [Product Strategy](docs-site/product-strategy.md)
- [Contributor Guide](CONTRIBUTING.md)
- [Developer Guide](DEVELOPER.md)

## License

MIT. See [LICENSE](LICENSE).
