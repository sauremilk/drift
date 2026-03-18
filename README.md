# Drift — Codebase Coherence Analyzer

**Detect architectural erosion from AI-generated code.**

Drift is a static analysis tool that measures how well a codebase maintains its architectural coherence over time — particularly as AI code-generation tools (Copilot, Cursor, ChatGPT) introduce code that solves local tasks correctly but weakens global design consistency.

## The Problem

AI coding assistants optimize for the _prompt context_, not the _codebase context_. The result: code that works but doesn't fit. Error handling fragments across 4 different patterns. Import boundaries erode. Near-duplicate functions accumulate. The codebase gradually loses the implicit contracts that made it maintainable.

**Drift doesn't detect bugs. It detects the loss of design intent.**

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Analyze a repository
drift analyze --repo /path/to/your/project

# CI check (exit code 1 if findings exceed threshold)
drift check --fail-on high

# Show pattern catalog
drift patterns

# JSON output for downstream tooling
drift analyze --format json
```

## What Drift Detects

Drift measures 7 detection signals, each targeting a different dimension of architectural erosion:

| Signal                      | Code | What it detects                                                                                  |
| --------------------------- | ---- | ------------------------------------------------------------------------------------------------ |
| **Pattern Fragmentation**   | PFS  | Same category of pattern (e.g. error handling) implemented N different ways within one module    |
| **Architecture Violations** | AVS  | Imports that cross layer boundaries (DB → API) or create circular dependencies                   |
| **Mutant Duplicates**       | MDS  | Near-identical functions that diverge in subtle ways (copy-paste-then-modify)                    |
| **Explainability Deficit**  | EDS  | Complex functions lacking docstrings, tests, or type annotations — especially when AI-attributed |
| **Doc-Impl Drift**          | DIA  | Documented architecture that no longer matches actual code _(Phase 2)_                           |
| **Temporal Volatility**     | TVS  | Files with anomalous change frequency, author diversity, or defect correlation                   |
| **System Misalignment**     | SMS  | Recently introduced imports/patterns foreign to their target module                              |

### Composite Drift Score

Individual signal scores (0.0–1.0) are combined into a weighted **composite drift score**:

```
Score = Σ (signal_weight × signal_score) / Σ weights
```

Default weights:

```yaml
weights:
  pattern_fragmentation: 0.20
  architecture_violation: 0.20
  mutant_duplicate: 0.15
  temporal_volatility: 0.15
  explainability_deficit: 0.10
  doc_impl_drift: 0.10
  system_misalignment: 0.10
```

## Configuration

Create a `drift.yaml` in your project root:

```yaml
# File patterns
include:
  - "**/*.py"
  - "**/*.ts"
exclude:
  - "**/node_modules/**"
  - "**/__pycache__/**"
  - "**/venv/**"

# Signal weights (must sum to ~1.0)
weights:
  pattern_fragmentation: 0.20
  architecture_violation: 0.20
  mutant_duplicate: 0.15
  temporal_volatility: 0.15
  explainability_deficit: 0.10
  doc_impl_drift: 0.10
  system_misalignment: 0.10

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

Full repository analysis with Rich terminal output.

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

Show drift score evolution over time.

```bash
drift trend --last 90
```

## Output Formats

**Rich (default):** Color-coded terminal dashboard with score bars, module rankings, and finding details.

**JSON:** Machine-readable output for dashboards and downstream tools.

**SARIF:** GitHub Code Scanning integration — findings appear as code annotations in PRs.

## Architecture

```
drift/
├── cli.py              # Click CLI entry point
├── analyzer.py         # Orchestrator: discovery → parse → signals → score
├── config.py           # drift.yaml configuration loading
├── models.py           # Core data models (dataclasses)
├── ingestion/
│   ├── ast_parser.py   # Python AST parsing (built-in ast module)
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
│   └── doc_impl_drift.py
├── scoring/
│   └── engine.py       # Weighted composite scoring
└── output/
    ├── rich_output.py  # Terminal dashboard
    └── json_output.py  # JSON + SARIF
```

### Key Design Decisions

1. **Deterministic core.** No LLM in the detection pipeline. All signals use AST analysis, graph algorithms, and statistical methods. Reproducible, fast, auditable.

2. **Python `ast` module for Python files.** Zero-dependency parsing, always available, simpler than tree-sitter for Python-only analysis. TypeScript support via optional tree-sitter dependency.

3. **Signal architecture.** Each signal is an independent analyzer implementing `BaseSignal`. Signals are composed, not chained — they run on the same parsed data.

4. **Fingerprint-based pattern matching.** Error handling, API endpoints, and other patterns are reduced to structural fingerprints (JSON dicts). Grouping and variant counting happens on these fingerprints, not source text.

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

- `tree-sitter` + `tree-sitter-typescript` — TypeScript/JSX support
- `sentence-transformers` + `faiss-cpu` — Embedding-based similarity (Phase 2)

## Roadmap

- **v0.1 (current):** 7 detection signals, Python support, CLI + CI integration
- **v0.2:** TypeScript support, embedding-based duplicate detection, temporal trend charts
- **v0.3:** IDE plugin (VS Code), ADR-to-code alignment (Doc-Impl Drift), team dashboards
- **v0.4:** PR bot, auto-fix suggestions, historical drift tracking

## License

MIT
