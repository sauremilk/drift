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
│ ts_parser    │    │ DIA  BEM  TPD│    │ impact      │    │ sarif       │
│ git_history  │───▶│ GCD  NBV  BAT│    │ module      │    │             │
│              │    │ ECM COD CCC  │    │             │    │             │
└──────────────┘    └──────────────┘    └─────────────┘    └─────────────┘
     Parse              Detect              Score              Format
```

**Data flow:** File Discovery → AST Parsing (parallel, cached) + Git History (concurrent) → 15 Signals (all scoring) → Auto-Calibration → Composite Scoring → Output Rendering

### Incremental Analysis (Temporal Model)

Full analysis runs all signals on every file. The **incremental path** (`drift_nudge`) re-runs
only the signals affected by changed files:

```
BaselineManager.get()  ──┐
                         ├──▶ IncrementalSignalRunner.run(changed_files)
changed files            │       │
 ├─ file-local signals ──┘       ├──▶ exact confidence
 └─ cross-file / git ───────────▶ estimated (baseline carried)
```

Each signal declares an `incremental_scope` class variable:

| Scope | Meaning | Re-run on file change? |
|-------|---------|----------------------|
| `file_local` | Depends only on a single file's AST | Yes — exact |
| `cross_file` | Depends on imports / relations across files | No — estimated |
| `git_dependent` | Depends on git history | No — estimated |

**Convention:** Every new signal **MUST** declare `incremental_scope` on the class.
Omitting it defaults to `file_local`.

**Baseline management:** `BaselineManager` (singleton in `incremental.py`) caches
baselines per repository and automatically invalidates them when:

- HEAD commit changes (branch switch, new commit)
- Stash list changes
- More than 10 files changed since baseline creation
- TTL expires (default 15 min)

**Key directories:**

| Directory | Purpose |
|---|---|
| `src/drift/ingestion/` | File discovery, AST parsing (Python + TypeScript), git log parsing |
| `src/drift/signals/` | 15 detection signals, each implementing `BaseSignal` |
| `src/drift/scoring/` | Weighted composite score, severity gating, module scores |
| `src/drift/output/` | Rich terminal dashboard, JSON, SARIF formatters |
| `src/drift/commands/` | Click CLI subcommands |
| `src/drift/config.py` | Pydantic-based configuration with defaults |
| `src/drift/models.py` | Core data models: `Finding`, `ParseResult`, `RepoAnalysis` |

---

## Signals (15 detectors)

| Abbrev | Signal | Detects |
|--------|--------|---------|
| **PFS** | Pattern Fragmentation | Same concern solved N different ways |
| **AVS** | Architecture Violation | Imports crossing layer boundaries |
| **MDS** | Mutant Duplicates | Near-duplicate functions (AST fingerprint) |
| **EDS** | Explainability Deficit | Complex functions lacking documentation |
| **TVS** | Temporal Volatility | Unusually high churn in recent commits |
| **SMS** | System Misalignment | Module-level structural inconsistencies |
| **DIA** | Doc-Implementation Drift | Documentation claims that diverge from code |
| **BEM** | Broad Exception Monoculture | Uniform broad exception handling across a module |
| **TPD** | Test Polarity Deficit | Test suites lacking negative / failure path tests |
| **GCD** | Guard Clause Deficit | Public functions uniformly missing early guards |
| **NBV** | Naming Contract Violation | Functions whose names imply a contract the body doesn't fulfil |
| **BAT** | Bypass Accumulation | Files with high density of suppression markers (type: ignore, noqa, TODO/FIXME/HACK) |
| **ECM** | Exception Contract Drift | Public functions whose exception profile changed across recent commits (git-based, MVP) |
| **COD** | Cohesion Deficit | Modules that mix weakly related semantic responsibilities |
| **CCC** | Co-Change Coupling | Files that repeatedly co-change without explicit import dependency |

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
- **Root discipline:** new tracked top-level entries must satisfy [docs/ROOT_POLICY.md](docs/ROOT_POLICY.md) and `.github/repo-root-allowlist`
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
| Property-based | Fuzzing of config/path boundaries | `pytest tests/test_property_based.py` |

**Shared fixture:** `conftest.py` → `tmp_repo` creates a complete 3-layer mini-project (services/api/db).

---

## Bug-Hunting Tools

Three tools supplement the standard test suite. They are not required for every commit but should be run when changing parsing, config, or signal-scoring logic.

### Vulture — Dead Code Detection

Finds unerreichbaren Code, der durch Tests nicht erreichbar ist. Läuft automatisch im CI (test-Job, nach mypy).

```bash
python -m vulture src/drift --min-confidence 80
```

Expected output on a clean codebase: no findings. Every finding should either be fixed or added to `[tool.vulture] ignore_names` in `pyproject.toml` with a comment explaining why.

### Hypothesis — Property-Based Fuzzing

Tests in `tests/test_property_based.py` fuzz the system-boundary functions (config parsing, path matching, file discovery) with thousands of generated inputs. Run alongside the standard suite:

```bash
pytest tests/test_property_based.py -v
```

To extend coverage, add `@given`-decorated tests to the file. Follow the existing pattern: assert only safety properties (no unexpected exceptions), keep `max_examples ≤ 50` for CI budget.

### Mutmut — Testsuite Quality Check (local only)

Mutmut mutates `scoring/` and `signals/` source code and checks whether the test suite catches each mutation. It is **not run in CI** (typical runtime: 10–30 min). Run manually to evaluate test coverage quality:

```bash
python -m mutmut run
python -m mutmut results
```

Target: mutation score ≥ 60% for `scoring/`. Results below 50% indicate tests that run but verify nothing — fix the tests, not the mutations.

Configuration is in `pyproject.toml` `[tool.mutmut]`.

---

## Common Issues

| Problem | Fix |
|---------|-----|
| Windows UTF-8 crashes in Rich output | Handled automatically in `commands/__init__.py` |
| Tests fail with `exit 128` (not a git repository) | pre-push hook unsets `GIT_DIR` — ensure hooks are active: `git config core.hooksPath .githooks` |
| `sentence-transformers` not found | Install with `pip install -e ".[embeddings]"` or use `--no-embeddings` flag |
| mypy failures | Run `python -m mypy src/drift` locally; CI and pre-push enforce a clean type check |

---

## Release Process

**Automated (recommended):**

```bash
python scripts/release_automation.py --full-release
```

This single command: runs quick tests → calculates next version → updates CHANGELOG → commits → tags → pushes → triggers PyPI publication.

**Manual steps (if needed):**

1. Bump version in `pyproject.toml`
2. Update `CHANGELOG.md`
3. Commit: `chore: bump version to vX.Y.Z`
4. Tag: `git tag vX.Y.Z && git push origin vX.Y.Z`
5. Create GitHub Release → CI publishes to PyPI and updates the `v1` major tag

**Helpers:**

| Command | Purpose |
|---------|---------|
| `python scripts/release_automation.py --calc-version` | Calculate next version only |
| `python scripts/release_automation.py --update-changelog` | Update CHANGELOG only |

### PyPI token for agents and CI

- Preferred setup: add repository secret `PYPI_API_TOKEN` with your PyPI API token.
- Never store token values in tracked files, workflow YAML, docs examples with real values, or commits.
- `publish.yml` will use token-based upload automatically when `PYPI_API_TOKEN` is set.
- If `PYPI_API_TOKEN` is not set, workflow falls back to Trusted Publishing (OIDC).
- For local/manual agent upload, export `TWINE_USERNAME=__token__` and `TWINE_PASSWORD=<your-token>` before `python -m twine upload dist/*`.

See [CONTRIBUTING.md → Versioning](CONTRIBUTING.md#versioning) for details.

---

## GitHub Actions Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `ci.yml` | Push/PR to main | Lint, typecheck, tests, coverage, self-analysis, score gate |
| `publish.yml` | GitHub Release / manual | Build + publish to PyPI (token or trusted publishing) |
| `auto-release-on-push.yml` | Push to main | Auto-create GitHub Release from pyproject.toml version |
| `validate-release.yml` | Tag push `v*` | Pre-publish version validation |
| `docs.yml` | Push to main (docs changes) | Build + deploy MkDocs to GitHub Pages |
| `repo-guard.yml` | Push/PR to main | Repository hygiene checks (blocklist, root allowlist) |
| `package-kpis.yml` | Monthly cron / manual | Collect PyPI downloads + GitHub dependency usage |
| `welcome.yml` | First issue/PR | Automated welcome message for new contributors |
| `stale.yml` | Weekly cron | Mark and close inactive issues/PRs |

---

## Pre-Push Gates (for contributors)

The `.githooks/pre-push` hook enforces 6 gates before code reaches the remote. These run automatically after `make install`.

| Gate | When triggered | What it checks |
|------|---------------|----------------|
| **Feature Evidence** | `feat:` commits | Tests in `tests/`, benchmark artifact, STUDY.md update |
| **Changelog** | `feat:` or `fix:` commits | `CHANGELOG.md` must be updated |
| **Version Bump** | `pyproject.toml` changed | Version must be valid SemVer and > last remote tag |
| **Lockfile Sync** | `pyproject.toml` changed | `uv.lock` must exist and be synchronized |
| **Public API Docstrings** | `src/drift/` changes | New public functions must have docstrings |
| **Risk Audit (§18)** | `src/drift/signals/`, `ingestion/`, `output/` changes | At least one audit artifact under `audit_results/` must be updated |

**Skip flags** (use sparingly, e.g. for docs-only changes):

```bash
DRIFT_SKIP_CHANGELOG=1 git push      # Skip changelog gate
DRIFT_SKIP_VERSION_BUMP=1 git push   # Skip version gate
DRIFT_SKIP_RISK_AUDIT=1 git push     # Skip risk audit gate
DRIFT_SKIP_HOOKS=1 git push          # Skip ALL gates (emergency only)
```

After the gates pass, the hook also runs lint, typecheck, tests, and self-analysis locally before pushing.
