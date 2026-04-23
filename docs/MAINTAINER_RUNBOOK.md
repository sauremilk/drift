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

1. An ADR under `docs/decisions/` (status `proposed`)
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

## Succession & delegation

Drift is currently maintained by a single maintainer. To mitigate single-point-of-failure risk:

- **Trusted contributor role:** Any contributor with ≥3 merged PRs and demonstrated familiarity with POLICY.md may be nominated as a trusted reviewer. Open a discussion to propose.
- **Minimum response level:** Issues and PRs must receive a first response within 72 hours. If the maintainer is unavailable for >7 days, a pinned notice should be posted in Discussions.
- **PyPI publish rights:** The primary maintainer holds publish rights. A second trusted committer with upload access is needed before drift reaches CI-critical adoption (>10 teams). This is tracked as a distribution milestone.
- **Continuity documents:** All signal logic, benchmark artifacts, and release automation are self-contained and reproducible. A successor maintainer can operate the project using this runbook, [DEVELOPER.md](../DEVELOPER.md), and [POLICY.md](../POLICY.md) without access to any external service.
- **Sponsorship:** See [SUPPORT.md](../SUPPORT.md) and [GitHub Sponsors](https://github.com/sponsors/mick-gsk).
