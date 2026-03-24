# Drift — Codebase Coherence Analyzer

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

**Detect architectural erosion from AI-generated code.**

Drift is a static analysis tool that measures how well a codebase maintains its architectural coherence over time — particularly as AI code-generation tools (Copilot, Cursor, ChatGPT) introduce code that solves local tasks correctly but weakens global design consistency.

![drift CLI demo](demos/demo.gif)

_Reproducible terminal recording via [demos/demo.tape](demos/demo.tape)._

---

## Contents

- [The Problem](#the-problem)
- [Measured Results](#measured-results)
- [Quick Start](#-quick-start)
- [Demo](#-demo)
- [What Drift Detects](#-what-drift-detects)
- [Output Formats](#-output-formats)
- [Configuration](#configuration)
- [pre-commit Hook](#pre-commit-hook)
- [GitHub Action](#github-action)
- [CLI Commands](#cli-commands)
- [Architecture](#architecture)
- [How It Works: Algorithm Deep Dive](#how-it-works-algorithm-deep-dive)
- [Design Decisions](#design-decisions)
- [Case Studies](#case-studies)
- [Development](#development)
- [Benchmark Study](STUDY.md)
- [Roadmap](#roadmap)

---

## The Problem

AI coding assistants optimize for the _prompt context_, not the _codebase context_. The result: code that works but doesn't fit. Error handling fragments across 4 different patterns. Import boundaries erode. Near-duplicate functions accumulate. The codebase gradually loses the implicit contracts that made it maintainable.

SonarSource [reports](https://www.sonarsource.com/blog/the-inevitable-rise-of-poor-code-quality-in-ai-accelerated-codebases/) an 8× increase in code duplicates and declining code reuse in AI-accelerated codebases. Linters catch syntax issues. SonarQube catches security issues. **Nothing catches the loss of architectural coherence — until drift.**

**Drift doesn't detect bugs. It detects the loss of design intent.**

### Why Not Existing Tools?

<details>
<summary>Why not SonarQube and classic linters?</summary>


| Tool                 | What it catches                  | What it misses                                           |
| -------------------- | -------------------------------- | -------------------------------------------------------- |
| **SonarQube**        | Duplicates, complexity, security | No pattern fragmentation; no AI-specific erosion signals |
| **pylint / mypy**    | Syntax, types, style             | No architecture or coherence signals                     |
| **jscpd / CPD**      | Text-level duplicates            | No AST-structural near-duplicates; no fragmentation      |
| **Sourcegraph Cody** | AI-powered search                | Non-deterministic; requires cloud; no composite scoring  |

**drift is the first tool that combines structural, temporal, and pattern-coherence signals into a deterministic Codebase Health Score — specifically designed for AI-accelerated development.**

</details>

## Measured Results

Benchmarked on 5 real-world Python repositories (default config, no tuning):

| Repository                                       | Files | Functions | Drift Score | Severity | Findings |   Time |
| ------------------------------------------------ | ----: | --------: | ----------: | -------- | -------- | -----: |
| [FastAPI](https://github.com/fastapi/fastapi)    | 1,118 |     4,554 |       0.690 | HIGH     | 661      |  2.3 s |
| [Pydantic](https://github.com/pydantic/pydantic) |   403 |     8,384 |       0.577 | MEDIUM   | 283      | 57.9 s |
| PWBS (490-file backend)                          |   490 |     5,073 |       0.520 | MEDIUM   | 146      |  6.2 s |
| [httpx](https://github.com/encode/httpx)         |    60 |     1,134 |       0.472 | MEDIUM   | 46       |  3.3 s |
| drift (self-analysis)                            |    45 |       263 |       0.442 | MEDIUM   | 69       |  0.3 s |

Top finding for each repo: FastAPI → 499 near-duplicate test functions (MDS), Pydantic → 117 underdocumented internal functions (EDS), PWBS → 114 API endpoint variants (PFS), httpx → 31 error-handling variants (PFS), drift → doc-implementation gaps (DIA).

**Evaluation:** 80% precision on 291 classified findings, 86% recall on 14 controlled mutations. Full methodology, ground-truth analysis, and raw data: **[STUDY.md](STUDY.md)**

## Quick Start

```bash
# Install from PyPI
pip install drift-analyzer

# Or install from source (development)
pip install -e ".[dev]"

# Analyze a repository
drift analyze --repo /path/to/your/project

# CI check (exit code 1 if findings exceed threshold)
drift check --fail-on high

# Show pattern catalog
drift patterns

# JSON output for downstream tooling
drift analyze --format json

# Self-analysis — drift analyzes its own codebase
drift self

# Generate a shields.io badge for your README
drift badge --repo .
```

## Demo

Generate/update the GIF with [Vhs](https://github.com/charmbracelet/vhs):

```bash
vhs demos/demo.tape
```

Windows helper:

```powershell
./scripts/render_demo.ps1
```

Reference output (text fallback):

```
╭─ drift analyze  myproject/ ──────────────────────────────────────────────────╮
│  DRIFT SCORE  0.52  │  87 files  │  412 functions  │  AI: 34%  │  2.1s      │
╰──────────────────────────────────────────────────────────────────────────────╯

                        Module Drift Ranking
  Module                           Score  Bar                    Findings  Top Signal
  ────────────────────────────────────────────────────────────────────────────────────
  src/api/routes/                   0.71  ████████████████░░░░ 0.71   12  PFS 0.85
  src/services/auth/                0.58  ███████████░░░░░░░░░ 0.58    7  AVS 0.72
  src/db/models/                    0.41  ████████░░░░░░░░░░░░ 0.41    4  MDS 0.61
  src/utils/                        0.23  ████░░░░░░░░░░░░░░░░ 0.23    2  EDS 0.44

┌──┬────────┬───────┬──────────────────────────────────────┬──────────────────────┐
│  │ Signal │ Score │ Title                                 │ Location             │
├──┼────────┼───────┼──────────────────────────────────────┼──────────────────────┤
│◉ │ PFS    │  0.85 │ Error handling split 4 ways           │ src/api/routes.py:42 │
│◉ │ AVS    │  0.72 │ DB import in API layer                │ src/api/auth.py:18   │
│○ │ MDS    │  0.61 │ 3 near-identical validators           │ src/utils/valid.py   │
│◌ │ EDS    │  0.44 │ Complex fn without docstring or tests │ src/db/models.py:91  │
└──┴────────┴───────┴──────────────────────────────────────┴──────────────────────┘
```

## pre-commit Hook

Add drift as a [pre-commit](https://pre-commit.com) hook so it runs before every commit:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/sauremilk/drift
    rev: v1
    hooks:
      - id: drift-check
        args: [--fail-on, high]
```

## GitHub Action

Add drift to any repository's CI pipeline in seconds:

```yaml
# .github/workflows/drift.yml
name: Drift

on: [push, pull_request]

jobs:
  drift:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write # required for upload-sarif

    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0 # full git history for temporal signals

      - uses: sauremilk/drift@v1
        with:
          fail-on: high # exit 1 on high/critical findings
          upload-sarif: "true" # inline annotations in GitHub Code Scanning
```

| Input           | Default | Description                                                                      |
| --------------- | ------- | -------------------------------------------------------------------------------- |
| `fail-on`       | `high`  | Minimum severity that fails the build: `critical` \| `high` \| `medium` \| `low` |
| `upload-sarif`  | `false` | Upload SARIF to GitHub Code Scanning (requires `security-events: write`)         |
| `since`         | `90`    | Days of git history for temporal signals                                         |
| `format`        | `rich`  | Terminal output: `rich` \| `json` \| `sarif`                                     |
| `config`        | —       | Path to `drift.yaml` config file                                                 |
| `drift-version` | latest  | pip version spec, e.g. `drift-analyzer==0.2.0`                                   |

A full example workflow is available at [`examples/drift-check.yml`](examples/drift-check.yml).

## What Drift Detects

Drift measures 6 active detection signals, each targeting a different dimension of architectural erosion:

| Signal                      | Code | What it detects                                                                                  |
| --------------------------- | ---- | ------------------------------------------------------------------------------------------------ |
| **Pattern Fragmentation**   | PFS  | Same category of pattern (e.g. error handling) implemented N different ways within one module    |
| **Architecture Violations** | AVS  | Imports that cross layer boundaries (DB → API) or create circular dependencies                   |
| **Mutant Duplicates**       | MDS  | Near-identical functions that diverge in subtle ways (copy-paste-then-modify)                    |
| **Explainability Deficit**  | EDS  | Complex functions lacking docstrings, tests, or type annotations — especially when AI-attributed |
| **Temporal Volatility**     | TVS  | Files with anomalous change frequency, author diversity, or defect correlation                   |
| **System Misalignment**     | SMS  | Recently introduced imports/patterns foreign to their target module                              |

> **Phase 2 (not active):** Doc-Implementation Drift (DIA) — documented architecture that no longer matches actual code. Included in the codebase but excluded from the default pipeline (weight 0.0).

### Composite Drift Score

Individual signal scores (0.0–1.0) are combined into a weighted **composite drift score**:

```
Score = Σ (signal_weight × signal_score) / Σ weights
```

Default weights:

```yaml
weights:
  pattern_fragmentation: 0.22
  architecture_violation: 0.22
  mutant_duplicate: 0.17
  temporal_volatility: 0.17
  explainability_deficit: 0.12
  system_misalignment: 0.10
  doc_impl_drift: 0.00 # Phase 2 — not active
```

### Observed Score Ranges

Empirical ranges observed across 8 well-known open-source Python repositories (see [STUDY.md](STUDY.md) §11.5 for methodology):

| Range         | Interpretation                        | Observed Examples                           |
| ------------- | ------------------------------------- | ------------------------------------------- |
| **< 0.40**    | Focused / hand-crafted                | requests (0.376)                            |
| **0.40–0.50** | Normal / moderately complex           | flask (0.413), drift (0.450), httpx (0.486) |
| **0.50–0.55** | Complex / framework-typical           | sqlmodel (0.504), pydantic (0.531)          |
| **> 0.55**    | Large-scale / high structural inertia | fastapi (0.582), django (0.546)             |

> **Note:** These ranges are hypotheses derived from observed data, not validated thresholds/SLOs.
> The score reflects structural complexity — a high score is not inherently "bad" (django is well-maintained at 0.54).
> Track _trends_ over time, not absolute values. See `drift trend` for built-in tracking.

**Temporal stability:** Scores are highly stable across consecutive commits:

- drift: σ=0.012 over 10 commits (range 0.439–0.475)
- django: σ=0.004 over 20 commits (range 0.535–0.546)

**Major-version correlation:** Across 17 django releases (1.8→6.0, 10 years), the score plateaus at 0.553–0.563 (σ=0.004) — then drops -0.016 at 6.0 when 116 deprecation-removal commits cleaned up legacy debt. This confirms that drift tracks structural coherence, not codebase size. See [STUDY.md](STUDY.md) §11.7 for the full analysis.

Use `scripts/temporal_drift.py` to generate temporal score curves for any repository (`--commits N` for recent history, `--tags PATTERN` for release milestones).

## Configuration

> **Quick start:** Copy [`drift.example.yaml`](drift.example.yaml) to `drift.yaml` and adapt to your project — that's the fastest path to a working configuration.

Create a `drift.yaml` in your project root:

```yaml
# File patterns
include:
  - "**/*.py"
exclude:
  - "**/node_modules/**"
  - "**/__pycache__/**"
  - "**/venv/**"

# Signal weights (normalised internally — don't need to sum to 1.0)
weights:
  pattern_fragmentation: 0.22
  architecture_violation: 0.22
  mutant_duplicate: 0.17
  temporal_volatility: 0.17
  explainability_deficit: 0.12
  system_misalignment: 0.10
  doc_impl_drift: 0.00

# Detection thresholds
thresholds:
  high_complexity: 10
  medium_complexity: 5
  min_function_loc: 10
  similarity_threshold: 0.80
  recency_days: 14
  volatility_z_threshold: 1.5

# Architecture boundaries
policies:
  layer_boundaries:
    - name: "No DB imports in API layer"
      from: "api/**"
      deny_import: ["db.*", "models.*"]
    - name: "No API imports in DB layer"
      from: "db/**"
      deny_import: ["api.*", "routes.*"]

# CI severity gate
fail_on: high # critical | high | medium | low
```

## CLI Commands

### `drift analyze`

Full repository analysis with Rich terminal output. Includes **actionable recommendations** — concrete, rule-based suggestions for fixing detected drift (no LLM required).

```bash
drift analyze --repo . --since 90 --format rich
```

| Flag           | Default | Description                     |
| -------------- | ------- | ------------------------------- |
| `--repo, -r`   | `.`     | Repository path                 |
| `--path, -p`   | —       | Restrict to subdirectory        |
| `--since, -s`  | `90`    | Days of git history             |
| `--format, -f` | `rich`  | Output: `rich`, `json`, `sarif` |
| `--config, -c` | —       | Config file path                |

### `drift check`

CI-optimized: analyze changed files, exit code 1 if severity threshold exceeded.

```bash
drift check --diff HEAD~1 --fail-on high --format sarif
```

### `drift patterns`

Display the pattern catalog — all discovered code patterns grouped by category.

```bash
drift patterns --category error_handling
```

### `drift trend`

Show drift score evolution over time with an **ASCII trend chart** when ≥3 snapshots exist.

```bash
drift trend --last 90
```

### `drift timeline`

**Root-cause analysis** — identifies _when_ drift began per module and correlates it with AI-attributed commits. Shows clean periods, drift onset dates, trigger commits, and AI burst detection.

```bash
drift timeline --repo . --since 90
```

| Flag           | Default | Description      |
| -------------- | ------- | ---------------- |
| `--repo, -r`   | `.`     | Repository path  |
| `--since, -s`  | `90`    | Days of history  |
| `--config, -c` | —       | Config file path |

### `drift self`

**Proof-of-concept demo** — drift analyzes its own codebase. Useful for showcasing drift to new users or verifying installation.

```bash
drift self
drift self --format json
```

### `drift badge`

Generate a [shields.io](https://shields.io) badge URL for the repository’s drift score. Useful for embedding in your README.

```bash
# Print badge URL and Markdown snippet
drift badge --repo .

# Write badge URL to file (for CI artifacts)
drift badge --repo . --output badge-url.txt

# Custom badge style
drift badge --style for-the-badge
```

| Flag           | Default | Description                                                    |
| -------------- | ------- | -------------------------------------------------------------- |
| `--repo, -r`   | `.`     | Repository path                                                |
| `--since, -s`  | `90`    | Days of history                                                |
| `--config, -c` | —       | Config file path                                               |
| `--style`      | `flat`  | Badge style: `flat`, `flat-square`, `for-the-badge`, `plastic` |
| `--output, -o` | —       | Write badge URL to file                                        |

## Output Formats

**Rich (default):** Color-coded terminal dashboard with score bars, module rankings, and finding details.

**JSON:** Machine-readable output for dashboards and downstream tools.

**SARIF:** GitHub Code Scanning integration — findings appear as code annotations in PRs.

## Architecture

```
drift/
├── cli.py              # Click CLI entry point
├── analyzer.py         # Orchestrator: discovery → parse → signals → score
├── cache.py            # Parse result caching (SHA-256 keyed)
├── config.py           # drift.yaml configuration loading
├── models.py           # Core data models (dataclasses)
├── timeline.py         # Root-cause analysis: when & why drift began
├── recommendations.py  # Rule-based actionable fix suggestions
├── ingestion/
│   ├── ast_parser.py   # Python AST parsing (built-in ast module)
│   ├── ts_parser.py    # TypeScript/TSX parsing (tree-sitter, optional)
│   ├── file_discovery.py
│   └── git_history.py  # Git log parsing + AI attribution heuristics
├── signals/
│   ├── base.py         # BaseSignal ABC
│   ├── pattern_fragmentation.py
│   ├── architecture_violation.py
│   ├── mutant_duplicates.py
│   ├── explainability_deficit.py
│   ├── temporal_volatility.py
│   ├── system_misalignment.py
│   └── doc_impl_drift.py  # Phase 2 stub
├── scoring/
│   └── engine.py       # Weighted composite scoring
└── output/
    ├── rich_output.py  # Terminal dashboard + timeline + trend chart
    └── json_output.py  # JSON + SARIF
```

### Design Decisions

1. **Deterministic core — no LLM in detection.** All signals use AST analysis, graph algorithms, and statistical methods. Reproducible, fast, auditable. ([ADR-001](docs/adr/001-deterministic-analysis-pipeline.md))

2. **AST fingerprinting for pattern matching.** Error handling, API endpoints, and other patterns are reduced to structural fingerprints (JSON dicts). Grouping and variant counting happens on these fingerprints, not source text. ([ADR-002](docs/adr/002-ast-fingerprinting-for-patterns.md))

3. **Count-dampened composite scoring.** Logarithmic dampening prevents signals with many findings from dominating. A single critical architecture violation outweighs 50 low-severity doc gaps. ([ADR-003](docs/adr/003-composite-scoring-model.md))

4. **Subprocess-based git parsing.** Decoupled from libgit2 — works on any system with `git` installed. Parallel history processing via `ThreadPoolExecutor`. ([ADR-004](docs/adr/004-subprocess-git-parsing.md))

5. **Signal architecture.** Each signal is an independent analyzer implementing `BaseSignal`. Signals are composed, not chained — they run on the same parsed data. Adding a new signal requires one file and one decorator.

---

## How It Works: Algorithm Deep Dive

This section explains the core algorithms that power drift's analysis pipeline. These are the techniques a static analysis tool needs to detect architectural erosion without relying on LLMs.

### AST Fingerprinting (O(n) per file)

Instead of comparing source text, drift reduces code patterns to **structural fingerprints** — normalized JSON representations of AST subtrees. This makes detection invariant to variable names, formatting, and comments.

```
Source Code                          AST Fingerprint
──────────────────────────────────   ──────────────────────────────────
try:                                 {"handler_types": ["ValueError"],
    result = parse(data)              "body_actions":   ["return"],
    return result                     "has_bare_except": false,
except ValueError:                    "reraises":        false}
    return None
```

**AST n-grams** (3-grams of node type names) capture structural shape while normalizing away identifiers and literals. Two functions with identical n-gram multisets but different variable names are structurally identical — exactly what copy-paste-then-modify patterns produce.

**Implementation:** `src/drift/ingestion/ast_parser.py` — Python's `ast` module with a custom `NodeVisitor` for cyclomatic complexity, fingerprint extraction, and n-gram computation in a single O(n) traversal.

### Near-Duplicate Detection via Multiset Jaccard (O(k²) per bucket)

The Mutant Duplicate Signal (MDS) finds functions that are structurally almost identical — the "copy-paste-then-modify" pattern common in AI-generated code.

**Three-phase approach:**

1. **Exact duplicates** — Group by `body_hash` (SHA-256 of normalized AST). O(n).
2. **Structural near-duplicates** — Bucket functions by LOC (±10%), then compare AST n-gram multisets using **Jaccard similarity**:

$$J(A, B) = \frac{\sum \min(A_i, B_i)}{\sum \max(A_i, B_i)}$$

   Pairs above 0.80 similarity are flagged. Bucketing reduces the naive O(n²) to O(k²) per bucket with a hard cap of 500 comparisons per bucket.

3. **Semantic near-duplicates** (optional) — When `sentence-transformers` is installed, a FAISS index enables k-NN search across all functions. Hybrid scoring blends structural and semantic similarity: `0.6 × jaccard + 0.4 × cosine_embedding` with a 0.75 threshold.

**Implementation:** `src/drift/signals/mutant_duplicates.py`

### Import Graph Analysis via NetworkX (O(n + m))

The Architecture Violation Signal (AVS) builds a **directed import graph** (nodes = files, edges = imports) and detects boundary violations using layer inference.

**Key techniques:**

- **Layer inference** — Each file is assigned to an architectural layer (API=0, Services=1, DB=2) based on directory conventions. An "omnilayer" concept exempts cross-cutting modules (`utils/`, `config/`, `types/`) from violations.
- **Upward import detection** — Edges where `source_layer > destination_layer` (e.g., DB module importing from API layer) are flagged as violations.
- **Hub-module dampening** — Files with in-degree centrality above the 90th percentile are classified as hubs. Findings against hubs receive a 0.5× score multiplier to reduce false positives from legitimate architectural hubs.
- **Circular dependency detection** — Strongly connected components (Tarjan's algorithm, O(n + m)) identify circular import chains.

**Implementation:** `src/drift/signals/architecture_violation.py` — powered by `networkx.DiGraph`.

### Count-Dampened Composite Scoring

Individual signal scores are combined into a single drift score using **logarithmic count dampening** — preventing signals with many low-confidence findings from dominating:

$$\text{signal\_score} = \overline{s} \times \min\!\left(1,\; \frac{\ln(1 + n)}{\ln(1 + k)}\right)$$

where $\overline{s}$ = mean finding score, $n$ = finding count, $k$ = dampening constant (10).

The composite score is a weighted average across all signals. Weights are calibrated via **ablation study**: each signal is removed, the F1-score delta is measured, and higher-impact signals receive proportionally higher weights.

**Implementation:** `src/drift/scoring/engine.py`

### Complexity Summary

| Component | Algorithm | Complexity | Key Technique |
|---|---|---|---|
| AST Parsing | Visitor pattern | O(n) per file | Fingerprinting + n-gram extraction |
| Near-Duplicates (MDS) | Multiset Jaccard + FAISS | O(k²) per bucket | LOC-bucketing + hybrid similarity |
| Architecture (AVS) | Graph analysis | O(n + m) | Tarjan SCC + hub dampening |
| Pattern Fragmentation (PFS) | Fingerprint grouping | O(n) | Variant counting + normalization |
| Composite Scoring | Weighted aggregation | O(n) | Logarithmic count dampening |

## Development

```bash
# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Run with verbose output
pytest -v

# Analyze drift's own codebase
drift analyze --repo .
```

## Requirements

- Python 3.11+
- Git repository (for history analysis)

### Core Dependencies

- `click` — CLI framework
- `rich` — Terminal output
- `pyyaml` — Configuration
- `pydantic` — Config validation
- `gitpython` — Git history
- `networkx` — Import graph analysis

### Optional

- `tree-sitter` + `tree-sitter-typescript` — TypeScript/TSX support
- `sentence-transformers` + `faiss-cpu` — Embedding-based similarity (Phase 2)

### TypeScript Support

TypeScript and TSX support is available via the optional `tree-sitter` dependency:

```bash
# Install with TypeScript support
pip install -e ".[typescript]"

# Or install all extras
pip install -e ".[all]"
```

When tree-sitter is installed, drift automatically:

- Detects `.ts` and `.tsx` files during discovery
- Extracts functions, classes, imports, and error-handling patterns
- Applies all 6 active signals to TypeScript code
- Includes TypeScript files in the default `include` patterns

Without tree-sitter, TypeScript files are skipped during analysis.

## Case Studies

### FastAPI — Pattern Fragmentation in a Growing Framework

**Repository:** [fastapi/fastapi](https://github.com/fastapi/fastapi) (1,118 files, 4,554 functions)
**Drift Score:** 0.690 (HIGH) | **Time:** 2.3s

FastAPI's top signal: **499 near-duplicate test functions** (MDS score 0.85). Test helper patterns diverged across endpoint modules — `test_read_items()`, `test_read_users()`, `test_read_events()` share identical assertion structures with only the model name changed.

The PFS signal found **4 distinct error-handling patterns** across route modules — a classic sign of framework growth where new contributors implement patterns differently than core maintainers.

**Takeaway:** Even well-maintained frameworks accumulate structural debt at scale. Drift quantifies what code reviewers notice intuitively: "this feels inconsistent."

### Pydantic — Explainability Deficit in Complex Internals

**Repository:** [pydantic/pydantic](https://github.com/pydantic/pydantic) (403 files, 8,384 functions)
**Drift Score:** 0.577 (MEDIUM) | **Time:** 57.9s

Pydantic's dominant signal: **117 underdocumented internal functions** (EDS). The `_internal/` package contains highly complex validation logic (cyclomatic complexity >15) with minimal docstrings — understandable for internal code, but a maintenance risk when contributors need to modify it.

**Takeaway:** High complexity without documentation creates a "bus factor" problem. Drift flags the riskiest functions, not all functions.

### Django — Structural Stability Across 10 Years of Releases

**Repository:** [django/django](https://github.com/django/django) (17 releases, 1.8→6.0)
**Drift Score Range:** 0.535–0.563 (σ=0.004)

django's drift score plateaued at 0.553–0.563 across Django 2.0→5.2 — then **dropped by 0.016 at Django 6.0** when 116 deprecation-removal commits cleaned up legacy debt.

This confirms drift measures structural coherence, not codebase size. The score correlates with intentional cleanup, not arbitrary growth.

**Takeaway:** Track trends, not absolute numbers. A stable score means consistent architecture. A sudden drop after cleanup means the tool is calibrated correctly. Full analysis: [STUDY.md §11.7](STUDY.md).

---

## Roadmap

- **v0.1 (current):** 6 active detection signals, Python support, CLI + CI integration, parse caching, trend history with ASCII charts, timeline root-cause analysis, actionable recommendations, `drift self` demo command, `drift badge` generator
- **v0.2:** PyPI release, performance optimization (<5s for 500-file repos), TypeScript support (tree-sitter — parser ready, optional install), Doc-Impl Drift signal improvements
- **v0.3:** VS Code extension with inline annotations, embedding-based duplicate detection, ADR-to-code alignment
- **v0.4:** GitHub App for automated PR comments, auto-fix suggestions for MDS/PFS findings (AST-based refactoring), team dashboards, historical drift tracking

### Vision: AI Codebase Health Monitor

drift aims to become the daily health check for AI-accelerated codebases — a deterministic, fast, zero-infrastructure tool that gives teams a single KPI for codebase coherence. Track it weekly. Gate PRs on it. Watch the trend, not the absolute score.

## Benchmark Study

Full evaluation methodology, ground-truth precision analysis (291 classified findings), controlled mutation benchmark (14 patterns, 86% recall), and a [tool landscape comparison](STUDY.md#9-tool-landscape-comparison) against SonarQube, pylint, and CPD: **[STUDY.md](STUDY.md)**

## License

MIT
