# Drift — Developer Guide

Quick-reference for contributors and agents. For detailed contribution rules see [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Setup (3 commands)

```bash
git clone https://github.com/mick-gsk/drift.git && cd drift
make install          # pip install -e ".[dev]" + git hooks
make check            # lint + typecheck + test + self-analysis
```

> **Requirements:** Python 3.11+, Git, GNU Make (on Windows: use `.\scripts\check.ps1` as a drop-in for `make check`, or run via Git Bash / WSL).

Maintainer operations: [docs/MAINTAINER_RUNBOOK.md](docs/MAINTAINER_RUNBOOK.md) and
[docs/REPOSITORY_GOVERNANCE.md](docs/REPOSITORY_GOVERNANCE.md).

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
│              │    │ PHR MAZ HSC  │    │             │    │             │
│              │    │ ISD FOE      │    │             │    │             │
└──────────────┘    └──────────────┘    └─────────────┘    └─────────────┘
     Parse              Detect              Score              Format
```

**Data flow:** File Discovery → AST Parsing (parallel, cached) + Git History (concurrent) → 24 Signals (19 scoring-active, 5 report-only) → Auto-Calibration → Composite Scoring → Output Rendering

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
| `src/drift/signals/` | 24 detection signals (19 scoring-active, 5 report-only), each implementing `BaseSignal` |
| `src/drift/scoring/` | Weighted composite score, severity gating, module scores |
| `src/drift/output/` | Rich terminal dashboard, JSON, SARIF formatters |
| `src/drift/commands/` | Click CLI subcommands |
| `src/drift/config.py` | Pydantic-based configuration with defaults |
| `src/drift/models.py` | Core data models: `Finding`, `ParseResult`, `RepoAnalysis` |

---

## Signals (24 total — 19 scoring-active, 5 report-only)

### Scoring-active signals

| Abbrev | Signal | Detects |
|--------|--------|---------|
| **PFS** | Pattern Fragmentation | Same concern solved N different ways |
| **AVS** | Architecture Violation | Imports crossing layer boundaries |
| **MDS** | Mutant Duplicates | Near-duplicate functions (AST fingerprint) |
| **EDS** | Explainability Deficit | Complex functions lacking documentation |
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
| **FOE** | Fan-Out Explosion | Modules/functions with unusually high dependency fan-out |
| **MAZ** | Missing Authorization | API endpoints lacking auth/authz checks (CWE-862) |
| **ISD** | Insecure Default | Unsafe default config patterns (CWE-1188) |
| **HSC** | Hardcoded Secret | Embedded secrets/tokens/credentials in source (CWE-798) |
| **PHR** | Phantom Reference | Unresolvable function/class references (AI hallucination indicator) |

### Report-only signals (weight 0.0, pending validation)

| Abbrev | Signal | Detects |
|--------|--------|---------|
| **TVS** | Temporal Volatility | Unusually high churn in recent commits |
| **TSA** | TypeScript Architecture | TS/JS layer leaks, cycles, cross-package imports |
| **CXS** | Cognitive Complexity | Functions with deeply nested, hard-to-follow control flow |
| **CIR** | Circular Import | Circular dependency chains in the module import graph |
| **DCA** | Dead Code Accumulation | Unreferenced functions/classes/symbols accumulating over time |

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

#### Agent Workflow Shortcuts

Zusaetzliche Targets speziell fuer Agenten und Automatisierung:

```
make feat-start                             Vor dem ersten Edit bei feat: (Policy-Gate + Baseline)
make fix-start                              Vor dem ersten Edit bei fix: (Baseline + Test-Run)
make gate-check COMMIT_TYPE=feat            Gates proaktiv pruefen (vor Push)
make audit-diff                             Zeigt Audit-Pflichten bei signals/ingestion/output
make changelog-entry COMMIT_TYPE=feat MSG=  Formatgerechten CHANGELOG-Snippet ausgeben
make handover TASK='beschreibung'           Session-Uebergabe-Artefakt anlegen
make catalog                                Alle scripts/ mit Kurzbeschreibung anzeigen
make catalog ARGS='--search evidence'       Skript-Katalog nach Stichwort filtern
```



### CLI subcommands

```
drift analyze          Full repo analysis (--format rich|json|sarif)
drift check            CI diff-mode (--fail-on high, --diff HEAD~1)
drift scan             Agent-native repository scan
drift diff             Change-focused drift analysis for agent workflows
drift fix-plan         Prioritized repair plan for agents
drift copilot-context  Generate Copilot instructions from analysis
drift export-context   Export negative context for agent consumption
drift explain          Describe a signal in the terminal
drift init             Scaffold drift.yaml config and CI integration
drift mcp              Start drift as an MCP server (VS Code / Copilot)
drift validate         Preflight config and environment validation
drift config           Configuration inspection and schema export
drift baseline         Save and compare finding baselines
drift brief            Pre-task structural briefing for agent delegation
drift self             Analyze drift's own codebase
drift patterns         Code pattern catalog
drift timeline         Root-cause timeline per module
drift trend            Score trend over time
drift badge            Generate shields.io badge URL
```

---

## Conventions

- **Python 3.11+**, type annotations on all public APIs
- **Ruff** for linting (`ruff check src/ tests/`), **mypy** for type checking
- **Conventional Commits** enforced by commit-msg hook: `feat|fix|docs|refactor|test|chore(scope): msg`
- **Decision Trailer:** commits implementing an ADR carry `Decision: ADR-NNN` in the commit body
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
| Mutation | Synthetic injections for recall | `python scripts/_mutation_benchmark.py` |
| Property-based | Fuzzing of config/path boundaries | `pytest tests/test_property_based.py` |

**Shared fixture:** `conftest.py` → `tmp_repo` creates a complete 3-layer mini-project (services/api/db).

### Quelldatei → Empfohlene Tests (Agents / Fix-Loop)

Bei Drift-Fix-Loops gezielte Tests unmittelbar nach jeder Dateiänderung ausführen — **nicht** die volle Suite pro Iteration. Kürzeste Match-Regel (oben zuerst):

| Geänderte Datei | Empfohlene Tests |
|---|---|
| `src/drift/signals/architecture_violation*` | `pytest tests/test_avs_*.py -q --tb=short` |
| `src/drift/signals/doc_impl_drift*` | `pytest tests/test_dia_*.py -q --tb=short` |
| `src/drift/signals/explainability_deficit*` | `pytest tests/test_eds_*.py -q --tb=short` |
| `src/drift/signals/mutant_duplicates*` | `pytest tests/test_mutant_duplicates*.py -q --tb=short` |
| `src/drift/signals/dead_code_accumulation*` | `pytest tests/test_dead_code*.py -q --tb=short` |
| `src/drift/signals/pattern_fragmentation*` | `pytest tests/test_pattern_fragmentation*.py -q --tb=short` |
| `src/drift/signals/naming_contract*` | `pytest tests/test_naming_contract*.py -q --tb=short` |
| `src/drift/signals/test_polarity_deficit*` | `pytest tests/test_test_polarity_deficit*.py -q --tb=short` |
| `src/drift/signals/cognitive_complexity*` | `pytest tests/test_cognitive_complexity*.py -q --tb=short` |
| `src/drift/signals/circular_import*` | `pytest tests/test_circular_import*.py -q --tb=short` |
| `src/drift/signals/guard_clause*` | `pytest tests/test_guard_clause*.py -q --tb=short` |
| `src/drift/signals/insecure_default*` | `pytest tests/test_insecure_default*.py -q --tb=short` |
| `src/drift/signals/missing_authorization*` | `pytest tests/test_missing_authorization*.py -q --tb=short` |
| `src/drift/signals/hardcoded_secret*` | `pytest tests/test_hardcoded_secret*.py -q --tb=short` |
| `src/drift/signals/exception_contract*` | `pytest tests/test_exception_contract*.py -q --tb=short` |
| `src/drift/signals/fan_out_explosion*` | `pytest tests/test_fan_out_explosion*.py -q --tb=short` |
| `src/drift/signals/cohesion_deficit*` | `pytest tests/test_cohesion_deficit*.py -q --tb=short` |
| `src/drift/signals/bypass_accumulation*` | `pytest tests/test_bypass_accumulation*.py -q --tb=short` |
| `src/drift/signals/*` (andere) | `pytest tests/test_precision_recall.py tests/test_mirofish_signal_improvements.py -q --tb=short` |
| `src/drift/api.py` | `pytest tests/test_brief.py tests/test_integration.py tests/test_incremental.py tests/test_fix_actionability.py tests/test_nudge.py -q --tb=short` |
| `src/drift/mcp_server.py` | `pytest tests/test_mcp_copilot.py tests/test_mcp_hardening.py tests/test_tool_metadata.py tests/test_negative_context_export.py -q --tb=short` |
| `src/drift/output/*` | `pytest tests/test_json_output.py tests/test_csv_output.py tests/test_sarif_contract.py tests/test_output_golden.py tests/test_agent_tasks.py -q --tb=short` |
| `src/drift/ingestion/*` | `pytest tests/test_ast_parser.py tests/test_file_discovery.py tests/test_scope_resolver.py tests/test_typescript_parser.py -q --tb=short` |
| `src/drift/config.py` | `pytest tests/test_config.py tests/test_config_validate.py tests/test_model_consistency.py -q --tb=short` |
| `src/drift/commands/*` | `pytest tests/test_self_command.py tests/test_patterns_command.py tests/test_ci_reality.py -q --tb=short` |
| `src/drift/session.py` | `pytest tests/test_session.py -q --tb=short` |
| `src/drift/incremental.py` | `pytest tests/test_incremental.py tests/test_nudge.py -q --tb=short` |
| Fallback | `pytest tests/ -q --tb=short --ignore=tests/test_smoke_real_repos.py --maxfail=5` |

Bei Testfehlschlag gilt: `AttributeError`/`TypeError` auf Interna → Test anpassen; `AssertionError` auf Public-API-Vertrag → Production-Fix überdenken. Vollständiger Entscheidungsbaum: `.github/prompts/drift-fix-loop.prompt.md` (Schritt 3b).

---

## Bug-Hunting Tools

Three tools supplement the standard test suite. They are not required for every commit but should be run when changing parsing, config, or signal-scoring logic.

### Vulture — Dead Code Detection

Finds unreachable code that tests do not exercise. Runs automatically in CI (test job, after mypy).

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

**Normal path:** merge a pull request to `main` with a valid conventional-commit title.

That merge triggers [release.yml](.github/workflows/release.yml), which runs
`python-semantic-release` in CI to calculate the version, update release metadata,
create the tag, and publish the GitHub release.

After a user-visible merge, verify:

- the release workflow succeeded
- the new tag and GitHub release exist
- PyPI shows the expected version

**Local fallback (CI failure only):**

```bash
python scripts/release_automation.py --full-release
```

Use the fallback only when the automated release path is unavailable and a maintainer
has decided manual intervention is warranted.

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
| `release.yml` | Push to main / manual | Run python-semantic-release |
| `publish.yml` | GitHub Release / manual | Build + publish to PyPI (token or trusted publishing) |
| `validate-release.yml` | Release-related changes / manual | Release metadata and process validation |
| `docs.yml` | Docs updates | Build + deploy MkDocs to GitHub Pages |
| `repo-guard.yml` | Push/PR to main | Repository hygiene checks (blocklist, root allowlist) |
| `dependency-review.yml` | Pull requests | Dependency risk review |
| `workflow-sanity.yml` | Workflow file changes | Workflow consistency checks |
| `install-smoke.yml` | Scheduled / manual | Installability smoke test |
| `security-hygiene.yml` | Scheduled / manual | Security hygiene verification |
| `codeql.yml` | Scheduled / push / pull_request | Code scanning |
| `package-kpis.yml` | Monthly cron / manual | Collect PyPI downloads + GitHub dependency usage |
| `welcome.yml` | First issue/PR | Automated welcome message for new contributors |
| `stale.yml` | Weekly cron | Mark and close inactive issues/PRs |

For the full workflow matrix and consolidation notes, see [.github/workflows/README.md](.github/workflows/README.md).

### Temporary Cirrus CI fallback

While GitHub-hosted runners are blocked at account level, this repository can run a parallel fallback via `.cirrus.yml`.

1. Install the Cirrus CI GitHub App for the repository.
2. Keep `.cirrus.yml` in the repository root (already present).
3. Open a small PR and verify Cirrus checks appear for Python 3.11, 3.12, and 3.13.
4. Treat Cirrus as temporary fallback only; migration back to GitHub-hosted runners is tracked in issue `#90`.

Operational notes:

- Cirrus runs Linux containers (`python:3.11`, `python:3.12`, `python:3.13`) and executes the same quick pytest gate used in local/CI fallback checks.
- Keep required checks conservative while fallback is active (do not remove existing GitHub Actions checks unless explicitly replaced by governance decision).
- After billing is resolved and `ubuntu-latest` is stable again, remove `.cirrus.yml` in the same change that closes issue `#90`.

## Branch Governance (Main-Only)

This repository uses `main` as the single integration branch.

### 1) Verify branch state

```bash
gh api repos/mick-gsk/drift/branches --paginate --jq ".[] | {name: .name, protected: .protected}"
```

### 2) Configure branch protection for `main`

Requires repository admin permissions. This setup enforces pull requests, at least one review, and status checks.

```bash
gh api -X PUT repos/mick-gsk/drift/branches/main/protection \
     -H "Accept: application/vnd.github+json" \
     --input - <<'JSON'
{
     "required_status_checks": {
          "strict": true,
          "contexts": [
               "Version format check",
               "Test (Python 3.12)"
          ]
     },
     "enforce_admins": true,
     "required_pull_request_reviews": {
          "dismiss_stale_reviews": true,
          "required_approving_review_count": 1,
          "require_code_owner_reviews": true
     },
     "restrictions": null,
     "allow_force_pushes": false,
     "allow_deletions": false,
     "required_linear_history": true
}
JSON
```

### 3) Deprecate and remove `master`

After confirming no active work depends on it:

```bash
git push origin --delete master
```

If deletion is temporarily not possible, keep `master` read-only and open an issue to track final removal.

---

## Pre-Push Gates (for contributors)

The `.githooks/pre-push` hook enforces 6 gates before code reaches the remote. These run automatically after `make install`.

| Gate | When triggered | What it checks |
|------|---------------|----------------|
| **Feature Evidence** | `feat:` commits | Tests in `tests/`, benchmark artifact, STUDY.md update |
| **Feature Evidence Content** | `feat:` commits | Evidence file must carry a `generated_by` block from the authorised generator script |
| **Changelog** | `feat:` or `fix:` commits | `CHANGELOG.md` must be updated |
| **Version Bump** | `pyproject.toml` changed | Version must be valid SemVer and > last remote tag |
| **Lockfile Sync** | `pyproject.toml` changed | `uv.lock` must exist and be synchronized |
| **Public API Docstrings** | `src/drift/` changes | New public functions must have docstrings |
| **Risk Audit (§18)** | `src/drift/signals/`, `ingestion/`, `output/` changes | At least one audit artifact under `audit_results/` must be updated |

### Generating Feature Evidence before a feat: commit

Evidence files for `feat:` commits must be generated by the authorised script — hand-crafted
or agent-authored JSON is rejected by the pre-push gate (Gate 2b).

```bash
# Generate evidence (runs self-analysis + test suite + precision-recall):
python scripts/generate_feature_evidence.py --version X.Y.Z --slug my-feature

# Verify locally before committing:
python scripts/validate_feature_evidence.py \
    benchmark_results/vX.Y.Z_my-feature_feature_evidence.json \
    --require-generated-by --push-head $(git rev-parse HEAD)
```

Flags:
- `--skip-tests` — skip pytest (only self-analysis)
- `--skip-precision-recall` — skip the precision-recall test suite
- `--feature "description"` — human-readable description (default: derived from slug)

**Recommended push workflow (avoids running the full CI suite twice):**

```bash
python scripts/generate_feature_evidence.py --version X.Y.Z --slug my-feature
make check       # Runs full CI locally AND writes the SHA cache
git push         # Hook detects cached SHA → skips expensive pytest/mypy/self-analysis
```

The hook caches the HEAD SHA after a successful run. If you run `make check` first, the hook
reuses that result and only re-evaluates the lightweight policy gates (blocked paths, changelog, etc.).
This prevents the expensive test suite from running a second time inside VS Code's terminal.

**Skip flags** (use sparingly, e.g. for docs-only changes):

```bash
DRIFT_SKIP_CHANGELOG=1 git push              # Skip changelog gate
DRIFT_SKIP_VERSION_BUMP=1 git push           # Skip version gate
DRIFT_SKIP_RISK_AUDIT=1 git push             # Skip risk audit gate
DRIFT_SKIP_EVIDENCE_VALIDATION=1 git push    # Skip evidence content validation (emergency only)
DRIFT_SKIP_HOOKS=1 git push                  # Skip ALL gates (emergency only)
```

After the gates pass, the hook also runs lint, typecheck, tests, and self-analysis locally before pushing.
