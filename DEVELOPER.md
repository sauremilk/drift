# Drift — Developer Guide

Quick-reference for contributors and agents. For detailed contribution rules see [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Setup (3 commands)

```bash
git clone https://github.com/sauremilk/drift.git && cd drift
make install          # pip install -e ".[dev]" + git hooks
make check            # lint + typecheck + test + self-analysis
```

> **Requirements:** Python 3.11+, Git, GNU Make (on Windows: Git Bash / WSL / `choco install make`).

---

## Architecture

```
ingestion/          signals/            scoring/           output/
┌──────────────┐    ┌──────────────┐    ┌─────────────┐    ┌─────────────┐
│ file_discovery│───▶│ PFS  AVS  MDS│───▶│ composite   │───▶│ rich (CLI)  │
│ ast_parser   │    │ EDS  TVS  SMS│    │ score       │    │ json        │
│ ts_parser    │    │ DIA          │    │ impact      │    │ sarif       │
│ git_history  │───▶│              │    │ module      │    │             │
└──────────────┘    └──────────────┘    └─────────────┘    └─────────────┘
     Parse              Detect              Score              Format
```

**Data flow:** File Discovery → AST Parsing (parallel, cached) + Git History (concurrent) → 7 Signals → Composite Scoring → Output Rendering

**Key directories:**

| Directory | Purpose |
|---|---|
| `src/drift/ingestion/` | File discovery, AST parsing (Python + TypeScript), git log parsing |
| `src/drift/signals/` | 7 detection signals, each implementing `BaseSignal` |
| `src/drift/scoring/` | Weighted composite score, severity gating, module scores |
| `src/drift/output/` | Rich terminal dashboard, JSON, SARIF formatters |
| `src/drift/commands/` | Click CLI subcommands |
| `src/drift/config.py` | Pydantic-based configuration with defaults |
| `src/drift/models.py` | Core data models: `Finding`, `ParseResult`, `RepoAnalysis` |

---

## Signals (7 detectors)

| Abbrev | Signal | Detects |
|--------|--------|---------|
| **PFS** | Pattern Fragmentation | Same concern solved N different ways |
| **AVS** | Architecture Violation | Imports crossing layer boundaries |
| **MDS** | Mutant Duplicates | Near-duplicate functions (AST fingerprint) |
| **EDS** | Explainability Deficit | Complex functions lacking documentation |
| **TVS** | Temporal Volatility | Unusually high churn in recent commits |
| **SMS** | System Misalignment | Module-level structural inconsistencies |
| **DIA** | Doc-Implementation Drift | Documentation claims that diverge from code |

Adding a new signal: see [CONTRIBUTING.md → Adding a new signal](CONTRIBUTING.md#adding-a-new-signal).

---

## Commands

### Make targets (developer workflow)

```
make help        Show all targets
make install     Dev install + git hooks
make lint        Ruff check
make lint-fix    Ruff check + auto-fix
make typecheck   Mypy
make test        Tests (skip slow)
make test-fast   Unit tests, stop on first failure
make test-all    All tests incl. smoke
make coverage    Tests with coverage report
make check       Full check pipeline (lint+type+test+self)
make ci          Full CI replica (version-check + check)
make self        Drift self-analysis
make clean       Remove caches
```

### CLI subcommands

```
drift analyze    Full repo analysis (--format rich|json|sarif)
drift check      CI diff-mode (--fail-on high, --diff HEAD~1)
drift self       Analyze drift's own codebase
drift patterns   Code pattern catalog
drift timeline   Root-cause timeline per module
drift trend      Score trend over time
drift badge      Generate shields.io badge URL
```

---

## Conventions

- **Python 3.11+**, type annotations on all public APIs
- **Ruff** for linting (`ruff check src/ tests/`), **mypy** for type checking
- **Conventional Commits** enforced by commit-msg hook: `feat|fix|docs|refactor|test|chore(scope): msg`
- **Coverage gate:** 65% minimum (ratchet — only increase)
- **Self-analysis gate:** `drift self` score must stay ≤ previous + 0.010
- Signals must be **deterministic**, **LLM-free**, and **fast** (< 500ms / 1k functions)
- Git imports only in `ingestion/` — never in signals or scoring
- Private paths (`tagesplanung/`) are blocked by git hooks

---

## Test Strategy

| Layer | What | Command |
|-------|------|---------|
| Unit tests | Signal logic, scoring, parsing | `make test-fast` |
| Integration | Full pipeline on `tmp_repo` fixture | `make test` |
| Ground truth | Precision/recall on labeled findings | `pytest tests/test_precision_recall.py` |
| Smoke (slow) | Real open-source repos | `make test-all` (marker: `slow`) |
| Mutation | Synthetic injections for recall | `python scripts/mutation_benchmark.py` |

**Shared fixture:** `conftest.py` → `tmp_repo` creates a complete 3-layer mini-project (services/api/db).

---

## Common Issues

| Problem | Fix |
|---------|-----|
| Windows UTF-8 crashes in Rich output | Handled automatically in `commands/__init__.py` |
| Tests fail with `exit 128` (not a git repository) | pre-push hook unsets `GIT_DIR` — ensure hooks are active: `git config core.hooksPath .githooks` |
| `sentence-transformers` not found | Install with `pip install -e ".[embeddings]"` or use `--no-embeddings` flag |
| mypy baseline errors | Known errors in `mypy_baseline.txt` — new code must be clean |

---

## Release Process

1. Bump version in `pyproject.toml`
2. Update `CHANGELOG.md`
3. Commit: `chore: bump version to vX.Y.Z`
4. Tag: `git tag vX.Y.Z && git push origin vX.Y.Z`
5. Create GitHub Release → CI publishes to PyPI and updates the `v1` major tag

See [CONTRIBUTING.md → Versioning](CONTRIBUTING.md#versioning) for details.
