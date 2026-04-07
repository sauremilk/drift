<div align="center">

# Drift

**Deterministic cross-file coherence analysis for Python codebases**

[![CI](https://github.com/mick-gsk/drift/actions/workflows/ci.yml/badge.svg)](https://github.com/mick-gsk/drift/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/drift-analyzer?cacheSeconds=300)](https://pypi.org/project/drift-analyzer/)
[![Python versions](https://img.shields.io/pypi/pyversions/drift-analyzer)](https://pypi.org/project/drift-analyzer/)
[![codecov](https://codecov.io/gh/mick-gsk/drift/branch/main/graph/badge.svg)](https://codecov.io/gh/mick-gsk/drift)
[![License](https://img.shields.io/github/license/mick-gsk/drift)](LICENSE)

[docs](https://mick-gsk.github.io/drift/) · [full study](docs/STUDY.md) · [trust & limitations](docs-site/trust-evidence.md) · [FAQ](docs-site/faq.md)

</div>

Drift detects structural erosion that accumulates across files: the same error handling done four different ways, database imports leaking into the API layer, AST-level near-duplicate helpers across modules. These problems pass existing tests but make the codebase progressively harder to change.

The analysis is deterministic (no LLM in the pipeline) and produces findings with file locations, severity, and a suggested next step. Precision upper-bound estimate: [77 % strict / 95 % lenient on a v0.5 ground-truth corpus](docs/STUDY.md) (score-weighted sample of 286 findings, 5 repos, single-rater — not yet independently replicated). See [Trust and limitations](#trust-and-limitations) for full caveats.

```bash
pip install drift-analyzer        # requires Python 3.11+
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

<sup>Example output — actual findings depend on repository structure.</sup>

<div align="center">
  <img src="demos/demo.gif" alt="drift analyze terminal demo" width="720">
</div>

---

## How drift differs from adjacent tools

Linters, type checkers, and security scanners operate on individual files or single-flow paths. Drift operates across files: it detects when the same concern is solved inconsistently across modules, when layer boundaries erode through imports, and when near-duplicate code accumulates structurally.

| Category | Primary analysis target | Drift's additional scope |
|---|---|---|
| **Linters / formatters** (Ruff, Black) | Style, single-file correctness | Cross-module coherence |
| **Type checkers** (mypy, Pyright) | Type safety per expression | Architectural consistency across modules |
| **Security scanners** (Semgrep, CodeQL) | Risky flows, policy violations | Structural fragmentation patterns |
| **Maintainability dashboards** (SonarQube) | Broad quality heuristics | Per-signal drift scores, deterministic and reproducible |
| **Clone detectors** (jscpd, CPD) | Text-level duplication | AST-level near-duplicates across modules |

Drift is designed to run alongside linters and security scanners, not replace them. Recommended stack: linter (style) + type checker (types) + drift (coherence) + security scanner (SAST).

<details>
<summary><b>Capability comparison table</b></summary>

| Capability | drift | SonarQube | pylint / mypy | jscpd / CPD |
|---|:---:|:---:|:---:|:---:|
| Pattern Fragmentation across modules | ✔ | — | — | — |
| Near-Duplicate Detection (AST-level) | ✔ | Partial (text) | — | ✔ (text) |
| Architecture Violation signals | ✔ | Partial | — | — |
| Temporal / change-history signals | ✔ | — | — | — |
| GitHub Code Scanning via SARIF | ✔ | ✔ | — | — |
| Zero server setup | ✔ | — | Partial | ✔ |
| TypeScript support | Experimental ¹ | ✔ | — | ✔ |

✔ = within primary design scope · — = not a primary design target (may be partially available via configuration or plugins) · Partial = limited coverage

¹ Via `drift-analyzer[typescript]`. Python is the primary analysis target.

Comparison reflects primary design scope per [STUDY.md §9](docs/STUDY.md).
</details>

## Quickstart

```bash
drift analyze --repo .          # see your top findings
drift explain PFS               # learn what a signal means
drift fix-plan --repo .         # get actionable repair tasks
```

Add to CI (start report-only):

```yaml
- uses: mick-gsk/drift@v1
  with:
    fail-on: none               # report findings without blocking
    upload-sarif: "true"        # findings appear as PR annotations
```

Once the team trusts the output, tighten: `fail-on: high`.

More: [Quick Start](docs-site/getting-started/quickstart.md) · [Example Findings](docs-site/product/example-findings.md) · [Team Rollout](docs-site/getting-started/team-rollout.md)

## Installation

| Path | Command / Config | Best for |
|---|---|---|
| **PyPI** | `pip install drift-analyzer` | Local use, scripts, CI |
| **pipx / uvx** | `pipx install drift-analyzer` | Isolated CLI (no venv) |
| **Install script** | `curl -fsSL .../install.sh \| sh` | One-liner (auto-detects pipx, uv, pip) |
| **Homebrew** | `brew tap mick-gsk/drift && brew install drift-analyzer` | macOS / Linux devs |
| **Docker** | `docker run -v .:/src ghcr.io/mick-gsk/drift analyze --repo /src` | Container-based CI |
| **GitHub Action** | `uses: mick-gsk/drift@v1` | GitHub CI/CD pipelines |
| **pre-commit** | `repo: https://github.com/mick-gsk/drift` | Git hooks |

Full installation guide: [Installation](docs-site/getting-started/installation.md)

## AI-assisted workflows

Drift provides an MCP server and agent-native commands for use inside AI coding sessions (Copilot, Cursor, Claude):

```bash
pip install drift-analyzer[mcp]
drift init --mcp --claude         # scaffold MCP configs for your editor
drift scan --repo . --max-findings 5   # session baseline for agents
drift diff --staged-only               # pre-commit structural check
drift fix-plan --repo .                # agent-friendly repair tasks
```

Full setup: [Integrations](docs-site/integrations.md) · [Vibe-Coding Guide](examples/vibe-coding/README.md) · [Demo walkthroughs](demos/README.md)

## Signals

Drift runs multiple signal families against the codebase. Each signal detects a specific cross-file coherence problem. Findings include severity, file location, and a suggested next step.

`drift explain <SIGNAL>` shows what any signal detects and how to address it.

[Signal Reference](docs-site/algorithms/signals.md) · [Algorithm Deep Dive](docs-site/algorithms/deep-dive.md) · [Scoring Model](docs-site/algorithms/scoring.md)

## Use cases

<details>
<summary><b>Pattern fragmentation in a connector layer</b></summary>

**Problem:** A FastAPI service has 4 connectors, each implementing error handling differently — bare `except`, custom exceptions, retry decorators, and silent fallbacks.

```bash
drift analyze --repo . --sort-by impact --max-findings 5
```

**Output:** PFS finding (high score) — "26 error_handling variants in connectors/" — shows exactly which files diverge and suggests consolidation.
</details>

<details>
<summary><b>Architecture boundary violation in a monorepo</b></summary>

**Problem:** A database model file imports directly from the API layer, creating a circular dependency that breaks test isolation.

```bash
drift check --fail-on high
```

**Output:** AVS finding — "DB import in API layer at src/api/auth.py:18" — blocks the CI pipeline until the import direction is fixed.
</details>

<details>
<summary><b>Duplicate utility code from AI-generated scaffolding</b></summary>

**Problem:** AI code generation created 6 identical `_run_async()` helper functions across separate task files instead of finding the existing shared utility.

```bash
drift analyze --repo . --format json | jq '.findings[] | select(.signal=="MDS")'
```

**Output:** MDS findings listing all 6 locations with high similarity scores, enabling a single extract-to-shared-module refactoring.
</details>

## Setup and CI integration

<details>
<summary><b>Full GitHub Action example (recommended: start report-only)</b></summary>

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
</details>

<details>
<summary><b>pre-commit hook configuration</b></summary>

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/mick-gsk/drift
    rev: vX.Y.Z                  # replace with the latest tag from https://github.com/mick-gsk/drift/releases
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
</details>

CI gate (local):

```bash
drift check --fail-on none    # report-only
drift check --fail-on high    # block on high-severity findings
```

More: [Configuration](docs-site/getting-started/configuration.md) · [Team Rollout](docs-site/getting-started/team-rollout.md)

<details>
<summary><b>Is drift a good fit?</b></summary>

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
</details>

## Trust and limitations

Drift's analysis pipeline is deterministic and its benchmark artifacts are published in the repository, so claims can be inspected rather than trusted on assertion.

- **Deterministic pipeline:** no LLMs in detection — same input produces the same output.
- **Benchmarked:** precision upper-bound estimate on a [v0.5 ground-truth corpus](docs/STUDY.md) (77 % strict / 95 % lenient, score-weighted sample of 286 findings, 5 repos). 88 % mutation recall on a [controlled benchmark](benchmark_results/mutation_benchmark.json) (15/17 patterns, 10 signal types). These numbers apply to the historical benchmark models and have not been revalidated for the current signal set.
- **Single-rater caveat:** ground-truth classification is not yet independently replicated.
- **Small-repo noise:** repositories with few files can produce noisy scores. Auto-calibration mitigates but does not eliminate this.
- **Temporal signals** depend on clone depth and git history quality.
- **The composite score is orientation, not a verdict.** Interpret deltas via `drift trend`, not isolated snapshots.

<details>
<summary><b>Interpreting the score</b></summary>

The drift score measures **loss of structural coherence**, not code quality.

- **Interpret deltas, not snapshots.** Use `drift trend` to track changes over time. A single score in isolation has limited meaning.
- **Temporary increases are expected during migrations.** Two coexisting patterns (old and new) will raise PFS/MDS signals. This is the migration happening, not a problem.
- **Deliberate polymorphism is not erosion.** Strategy, Adapter, and Plugin patterns produce structural similarity that MDS flags as duplication. Findings include a `deliberate_pattern_risk` hint — verify intent before acting.
- **The score rewards reduction, not correctness.** Deleting code lowers the score just like refactoring does. Do not optimize for a low score — optimize for understood, intentional structure.

Without `layer_boundaries` in `drift.yaml`, drift detects *emergent drift* — structural patterns that diverge without explicit prohibition. With configured `layer_boundaries`, drift additionally performs *conformance checking* against a defined architecture. Both modes are complementary.

See [STUDY.md §14](docs/STUDY.md) for epistemological boundaries.
</details>

<details>
<summary><b>Release status</b></summary>

The PyPI classifier is `Development Status :: 4 - Beta`.

- core Python analysis: stable
- CI and SARIF workflow: stable
- TypeScript support: experimental
- embeddings-based parts: optional / experimental
- benchmark methodology: evolving

Full rationale: [Stability and Release Status](docs-site/stability.md)
</details>

Further reading: [Benchmarking and Trust](docs-site/benchmarking.md) · [Full Study](docs/STUDY.md) · [Case Studies](docs-site/case-studies/index.md)

## Contributing

Drift's biggest blind spots are found by people running it on codebases the maintainers have never seen. A well-documented false positive can be more valuable than a new feature.

| I want to… | Go here |
|---|---|
| Ask a usage question | [Discussions](https://github.com/mick-gsk/drift/discussions) |
| Report a false positive / false negative | [FP/FN template](https://github.com/mick-gsk/drift/issues/new?template=false_positive.md) |
| Report a bug | [Bug report](https://github.com/mick-gsk/drift/issues/new?template=bug_report.md) |
| Suggest a feature | [Feature request](https://github.com/mick-gsk/drift/issues/new?template=feature_request.md) |
| Propose a contribution before coding | [Contribution proposal](https://github.com/mick-gsk/drift/issues/new?template=contribution_proposal.md) |
| Report a security vulnerability | [SECURITY.md](SECURITY.md) — not a public issue |

```bash
git clone https://github.com/mick-gsk/drift.git && cd drift && make install
make test-fast    # confirm everything passes, then start
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide and [ROADMAP.md](ROADMAP.md) for current priorities.

## Documentation

| Topic | Link |
|---|---|
| Getting Started | [Quick Start](docs-site/getting-started/quickstart.md) |
| Algorithms | [How It Works](docs-site/algorithms/deep-dive.md) |
| Evidence | [Benchmarking and Trust](docs-site/benchmarking.md) |
| Strategy | [Product Strategy](docs-site/product-strategy.md) |
| Contributing | [Contributor Guide](CONTRIBUTING.md) |
| Development | [Developer Guide](DEVELOPER.md) |

## License

MIT. See [LICENSE](LICENSE).
