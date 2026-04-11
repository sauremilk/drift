---
name: fix-failing-actions
description: "Diagnose and fix failing GitHub Actions workflows in the drift repository. Use when a CI run, security hygiene check, release workflow, or any other GitHub Actions job is red. Keywords: GitHub Actions, workflow failure, CI failure, failed run, failing check, red CI, workflow fix, gh run, action logs, pipeline error, failing job."
argument-hint: "Paste the failing run URL or run ID, or describe which workflow is failing."
---

# Fix Failing GitHub Actions

## When to Use

- A CI run on `main` or a PR is red
- The release workflow failed
- A security hygiene, repo-guard, or labeler job failed
- You see a failed status check in a pull request
- `gh run list` shows failed runs

## Drift-Specific Context

All workflows in this repo run on **Windows runners** (`windows-latest`) with PowerShell.
Python is resolved dynamically via `$env:PYTHON_BIN` (set by a resolver step).
CI steps use `make check` equivalents split into:
`ruff` → `mypy` → `pytest` → `drift analyze`.

Key workflows and their failure modes:

| Workflow | File | Common Failures |
|----------|------|-----------------|
| CI | `ci.yml` | pytest, mypy, ruff, `check_version.py`, `check_model_consistency.py` |
| Security Hygiene | `security-hygiene.yml` | detect-secrets, actionlint, zizmor, pip-audit |
| Release | `release.yml` | PSR version bump, PyPI publish, tag conflicts |
| Validate Release | `validate-release.yml` | SemVer format, CHANGELOG missing entry |
| Docs | `docs.yml` | mkdocs build error, broken links |
| Docker | `docker.yml` | build error, push credentials |
| Repo Guard | `repo-guard.yml` | `check_repo_hygiene.py` blocklist violation |
| Install Smoke | `install-smoke.yml` | pip install failure, CLI entry point missing |
| Doc Consistency | `doc-consistency.yml` | version mismatch in docs |

---

## Step 1: Identify the Failing Run

```bash
# List recent failed runs
gh run list --repo mick-gsk/drift --status failure --limit 10

# Or watch a specific run
gh run view <run-id> --repo mick-gsk/drift
```

If you have a URL like `https://github.com/mick-gsk/drift/actions/runs/12345678`,
extract the run ID (`12345678`) and use it below.

---

## Step 2: Fetch the Failure Logs

```bash
# Show only the failing steps
gh run view <run-id> --repo mick-gsk/drift --log-failed

# Or full log for a specific job
gh run view <run-id> --repo mick-gsk/drift --log
```

**Parse the log output:** Look for the first `##[error]` or `FAILED` line — that is the root cause.
Ignore everything after the first failure unless it looks like a separate independent failure.

---

## Step 3: Classify the Failure

Match the error to one of these categories, then jump to the fix section:

| Pattern in Log | Category | Fix Section |
|----------------|----------|-------------|
| `ruff check` / `E501`, `F401`, `F811` | Lint | §A |
| `mypy` / `error:` / `Incompatible types` | Type error | §B |
| `FAILED tests/` / `AssertionError` | Test failure | §C |
| `detect-secrets` / `Potential secret` | Secret scan | §D |
| `actionlint` / `yaml:` | Workflow lint | §E |
| `check_version.py` / `SemVer` | Version format | §F |
| `check_model_consistency.py` | Model mismatch | §G |
| `check_repo_hygiene.py` / `blocklist` | Repo hygiene | §H |
| `mkdocs` / `WARNING` / `404` | Docs build | §I |
| `semantic-release` / `tag` / `PyPI` | Release pipeline | §J |
| `pip install` / `No module named` | Dependency | §K |

---

## §A — Lint Failure (ruff)

```bash
# Reproduce locally
.venv\Scripts\ruff check src/ tests/

# Auto-fix safe issues
.venv\Scripts\ruff check src/ tests/ --fix
```

If auto-fix is not enough, inspect the flagged file and fix manually.
Do **not** add `# noqa` without a comment explaining why the rule is suppressed.

---

## §B — Type Error (mypy)

```bash
# Reproduce locally
.venv\Scripts\python -m mypy src/drift
```

Typical fixes:
- Missing return type annotation → add return type
- `None` not handled → add `if x is None: return` guard
- Import not found → add to `mypy` `ignore_missing_imports` or install the stub package (`types-*`)
- `# type: ignore` is acceptable only when the upstream stub is missing and documented in a comment

---

## §C — Test Failure (pytest)

```bash
# Reproduce the failing test locally
.venv\Scripts\python -m pytest tests/<failing_test_file>.py::test_name -v --tb=long
```

Checklist:
- [ ] Is the failure a genuine regression introduced by the last commit?
- [ ] Is it a flaky test (timing, randomness, git state dependency)?
- [ ] Is a fixture broken? Run `tests/fixtures/` inspection.
- [ ] Did a signal or scoring change invalidate expected values?

For **signal/scoring regressions**: update the expected values in the fixture file or ground-truth fixture (`tests/fixtures/ground_truth.py`) if the change is intentional, and document in `CHANGELOG.md`.

For **flaky tests**: add `@pytest.mark.flaky(reruns=2)` only as a last resort; prefer fixing the root cause.

---

## §D — Secret Scan Failure (detect-secrets)

This repo carries **intentional test-fixture secrets** (non-real values used in tests).
Each such literal must have `# pragma: allowlist secret` on the **same line**.

```bash
# Reproduce locally
pre-commit run --all-files detect-secrets
```

Fix:
1. Open the flagged file and line
2. If the value is a real credential → **remove it immediately**, rotate the credential, and treat this as a security incident
3. If the value is a test fixture → add `# pragma: allowlist secret` on that exact line
4. If it was already annotated but the baseline is stale → update baseline: `detect-secrets scan > .secrets.baseline`

See [SECURITY.md](../../SECURITY.md) for incident escalation steps.

---

## §E — Workflow Lint Failure (actionlint/zizmor)

```bash
# Reproduce locally (requires actionlint in PATH or pre-commit)
pre-commit run --all-files actionlint
pre-commit run --all-files zizmor
```

Common issues:
- Unquoted expression `${{ env.VAR }}` without quotes in shell run step → wrap in `"${{ env.VAR }}"`
- Using `set-output` (deprecated) → replace with `echo "name=value" >> $GITHUB_OUTPUT`
- Missing `permissions:` block → add least-privilege permissions
- `continue-on-error` masking real failures → evaluate whether the step should actually fail

---

## §F — Version Format Failure

The version in `pyproject.toml` must be valid SemVer (`MAJOR.MINOR.PATCH`).
**Do not manually edit** `pyproject.toml` version — it is managed by PSR (python-semantic-release) in CI.

If the check fails on a branch:
1. Verify the version is a clean SemVer string (no `.dev`, no extra suffixes unless intentional)
2. If `pyproject.toml` was manually edited → revert the version field
3. If PSR left a malformed version → check the release workflow logs for the error

```bash
.venv\Scripts\python scripts/check_version.py --check-semver
```

---

## §G — Model Consistency Failure

```bash
.venv\Scripts\python scripts/check_model_consistency.py
```

This script checks that Pydantic models and CLI/output schemas are in sync.
Fix: update the model, schema, or the consistency script to reflect intentional changes.
If a field was added to a model, ensure it is present in `drift.output.schema.json` or `drift.schema.json`.

---

## §H — Repo Hygiene Failure

```bash
.venv\Scripts\python scripts/check_repo_hygiene.py --config .github/repo-guard.blocklist --root-allowlist .github/repo-root-allowlist
```

Common causes:
- A blocked file path was accidentally committed (e.g., `tagesplanung/`, temp files)
- A new root-level file was added that is not in the allowlist → add to `.github/repo-root-allowlist`
- A blocklist pattern now matches a legitimate file → review the blocklist before removing the entry

---

## §I — Docs Build Failure (mkdocs)

```bash
.venv\Scripts\python -m mkdocs build --strict 2>&1
```

Common issues:
- Broken internal link → fix the `[text](path)` reference
- Missing nav entry in `mkdocs.yml` → add the page
- Jinja2 template error in `overrides/` → check the template syntax
- `mkdocs-material` version incompatibility → check `pyproject.toml` constraint

---

## §J — Release Pipeline Failure

**Do not run PSR manually** unless CI is unavailable and the maintainer requests it.
CI release is triggered on `push` to `main` via `.github/workflows/release.yml`.

Diagnostic steps:
```bash
gh run view <release-run-id> --repo mick-gsk/drift --log-failed
```

Common issues:
- No releasable commits since last tag → PSR skips without error; verify with `semantic-release version --print`
- PyPI token expired or missing → secret `PYPI_API_TOKEN` must be rotated in repo Settings → Secrets
- Tag conflict → a tag already exists for the computed version; check with `git tag -l | sort -V | tail -5`
- Merge conflict in PSR's own release commit → rebase and retry the push

Local fallback (only on maintainer request):
```bash
python scripts/release_automation.py --full-release
```

---

## §K — Dependency / Install Failure

```bash
# Reproduce locally
pip install -e ".[dev]"
```

Common issues:
- New dependency added to `pyproject.toml` but not yet in `uv.lock` → run `uv lock` and commit the lockfile
- Transitive dependency yanked on PyPI → pin to last working version + add comment
- `No module named 'X'` during tests → add `X` to `[project.optional-dependencies.dev]`

---

## Step 4: Verify the Fix Locally

Before committing, run the equivalent of the failing CI step locally:

```bash
# For most CI failures
make check

# Or targeted:
.venv\Scripts\ruff check src/ tests/           # lint
.venv\Scripts\python -m mypy src/drift         # types
make test-fast                                  # tests (schnell, ohne @pytest.mark.slow)
```

---

## Step 5: Commit and Report

Use the appropriate conventional commit type:

- `fix: resolve <failing-workflow> failure: <root cause summary>`

Update `CHANGELOG.md` under `### Fixed` if this was a user-visible or CI-blocking bug.

**Do not push autonomously.** Present the fix and wait for maintainer approval. See the `drift-commit-push` skill for the full push gate checklist.

---

## Quick Triage Cheat Sheet

```
gh run list --status failure --limit 5         → find the run
gh run view <id> --log-failed                  → read the error
                                               → classify (§A–§K)
make check                                     → verify fix locally
git add + git commit -m "fix: ..."            → stage fix
```
