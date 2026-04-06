# Week 1 Rollout Runbook

Execution runbook for immediate distribution work.

## Objective

Increase discovery and drive measurable PyPI download growth within 7 days.

## Day-by-Day Plan

### Day 1

- Finalize one canonical positioning line for all channels.
- Audit PyPI metadata in `pyproject.toml` for keywords, classifiers, and project URLs.
- Validate README discovery surfaces: PyPI install, GitHub Action, pre-commit hook, Discussions.
- Validate awesome list phrasing and shorten if maintainers prefer minimal wording.
- Prepare branch-ready PR text from `awesome-submissions.md`.

### Day 2

- Set GitHub Topics: `linting`, `architecture`, `python`, `ai-assisted-development`, `code-quality`, `developer-tools`, `static-analysis`.
- Enable or verify GitHub Discussions and pin one showcase or FAQ thread.
- Verify `good first issue` labels and contribution entry points.

### Day 3

- Verify the GitHub Action listing and example remain marketplace-ready.
- pre-commit discoverability: `.pre-commit-hooks.yaml` is already indexed automatically via
  GitHub search (`path:.pre-commit-hooks.yaml`) and Sourcegraph — no explicit submission required.
- **Awesome-list PRs blocked (Gate nicht erfüllt):** Mindestanforderungen für
  awesome-python (≥100 Stars, ≥3 Monate alt) und awesome-static-analysis (>20 Stars, ≥3 Monate,
  >1 Kontributor) sind am 06.04.2026 nicht erfüllt (7 Stars, 19 Tage alt, 1 Kontributor).
  Frühester Einreichungszeitpunkt: ~18.06.2026. Readiness-Gate und korrektes YAML-Format
  sind in `docs/distribution/awesome-submissions.md` dokumentiert.
- Bis zum Gate: Andere Discovery-Hebel priorisieren (Show HN, Reddit, dev.to).

### Day 4

- Finalize and publish the dev.to article using `devto-hashnode-5-repos.md`.
- Re-publish the adjusted version on Hashnode.
- Add canonical repo and PyPI links near top and end of both posts.

### Day 5

- Publish Show HN with hard proof points: deterministic, 23 signals, 97.3% precision, 15 real repositories.
- Keep copy value-oriented and non-promotional.

### Day 6

- Cross-post to Reddit with channel-specific framing:
  - r/Python
  - r/programming
  - r/softwarearchitecture
- Review referral traffic and initial PyPI movement.
- Identify the best-performing headline and lead paragraph.

### Day 7

- Convert `ide-discovery-mvp-spec.md` into actionable tickets (docs, UX, engineering).
- Decide whether to schedule implementation in next sprint.
- Write a short retro:
  - What produced qualified traffic
  - What produced low-value traffic
  - What to repeat in week 2

## Platform Setup Checklist

- PyPI metadata current in `pyproject.toml`
- README points clearly to PyPI, GitHub Action, pre-commit, and Discussions
- GitHub Topics set on the repository
- GitHub Discussions enabled with one pinned showcase or FAQ thread
- GitHub Action usage example verified against `action.yml`
- pre-commit hooks index submission prepared from `.pre-commit-hooks.yaml`

## KPI Template

| Metric | Baseline | Day 7 | Delta |
|---|---:|---:|---:|
| PyPI downloads |  |  |  |
| GitHub stars |  |  |  |
| Referral clicks to repo |  |  |  |
| Referral clicks to PyPI |  |  |  |
| Awesome PR status (count merged) |  |  |  |

## Notes

- Keep messaging consistent across channels.
- Prefer reproducible examples over broad claims.
- If discussion volume spikes, prioritize high-signal questions and publish one FAQ follow-up.
