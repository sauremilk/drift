# Maintainer Runbook

Operational reference for drift maintainers. For contributor guidance see [CONTRIBUTING.md](../CONTRIBUTING.md).

---

## Release workflow

Releases are fully automated via `python-semantic-release` (PSR) in CI.

1. **Use conventional commits** — PSR derives the version bump from commit prefixes:
   - `feat:` → MINOR
   - `fix:` → PATCH
   - `BREAKING CHANGE:` → MAJOR
2. **Push to `main`** — CI runs PSR, which updates `pyproject.toml`, `CHANGELOG.md`, creates a tag, GitHub Release, and publishes to PyPI.
3. **Local fallback** (CI failure only): `python scripts/release_automation.py --full-release`

## Pre-push gates

All pushes are gated by `.githooks/pre-push`. See [drift-push-gates.instructions.md](../.github/instructions/drift-push-gates.instructions.md) for the full checklist.

Quick reference:

| Trigger | Gate |
|---------|------|
| `feat:` commit | Tests + feature evidence + STUDY.md update |
| `feat:` or `fix:` commit | CHANGELOG.md updated |
| `pyproject.toml` changed | Version > last tag + `uv.lock` synced |
| `src/drift/**` new public function | Docstring present |
| `src/drift/signals/`, `ingestion/`, `output/` | Audit artifact updated |
| Every push | `make check` passes |

## Triage workflow

1. **Issues:** Respond within 72 hours. Label with appropriate category.
   Claim coordination for contributor-facing issues can be assisted by the issue-claim workflows and the playbook in [docs/issue-claim-playbook.md](issue-claim-playbook.md).
2. **PRs:** Run `make check` locally. Review against [POLICY.md](../POLICY.md) and the quality workflow in [drift-quality-workflow.instructions.md](../.github/instructions/drift-quality-workflow.instructions.md).
3. **Security reports:** Follow [SECURITY.md](../SECURITY.md) — private advisory, 72h acknowledgment, 7-day resolution timeline.

## Signal changes

Any change to signals, scoring weights, or output formats requires:

1. An ADR under `decisions/` (status `proposed`)
2. Audit artifact updates under `audit_results/` (FMEA, STRIDE, fault trees, risk register as applicable)
3. Feature evidence under `benchmark_results/`

See [POLICY.md §18](../POLICY.md) for the full risk-audit matrix.

## Key commands

| Task | Command |
|------|---------|
| Full local CI | `make check` |
| Fast tests | `make test-fast` |
| Self-analysis | `make self` |
| Lint + fix | `make lint-fix` |

## CITATION.cff sync

`CITATION.cff` version and date are updated automatically by the release workflow. If a manual release is performed, update `CITATION.cff` to match.
