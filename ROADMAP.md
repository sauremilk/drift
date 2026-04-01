# Drift — Contribution Roadmap

This roadmap communicates what the project needs most right now,
what is accessible for new contributors, and what is explicitly
deprioritized. It is updated with each release.

Last updated: v1.3.0 (2026-04-01)

---

## Current phase: Distribution (Q2 2026)

**Engineering moratorium in effect.** No new signals, no new features, no refactoring.
Goal for this quarter: validate demand, reach ≥10 external users.

Exceptions: bugfixes that block installation or first-run experience.

## Go support MVP (post-moratorium track)

Go support is a plausible future direction, but it is not scheduled during the
current distribution moratorium. The milestones below are intentionally phrased
as date-free MVP steps so contributors can prepare bounded work once this track
is opened.

### Phase 1 — Parser baseline

- **Measurable outcome:** Drift can discover `.go` files, parse package/import/
  function structure for a minimal fixture corpus, and complete analysis on
  those fixtures without parser crashes.
- **Owner-neutral entry point:** Add or extend isolated fixtures for
  single-package and multi-package Go repos, then harden ingestion until the
  fixtures parse deterministically.

### Phase 2 — Signal coverage subset

- **Measurable outcome:** A first subset of structurally compatible signals runs
  on Go fixtures with deterministic tests and documented scope limitations.
  Initial candidates: Pattern Fragmentation, Mutant Duplicates,
  Explainability Deficit, and Guard Clause Deficit.
- **Owner-neutral entry point:** Port one signal at a time behind fixture-based
  tests, starting with file-local heuristics before attempting cross-package or
  git-dependent behavior.

### Phase 3 — Validation matrix

- **Measurable outcome:** Enabled Go signals have a small validation matrix with
  labeled examples from fixtures plus at least one real-world Go repository,
  including explicit TP/FP/FN notes.
- **Owner-neutral entry point:** Contribute labeled findings, false-positive
  reports, and repo-level validation notes even if you are not changing parser
  or signal code.

No dates are committed for this track. It should only move forward once the
current demand-validation goals are satisfied or maintainers explicitly lift the
moratorium for language expansion.

---

## Completed since v0.7.1

- **v0.7.3:** Cohesion Deficit signal (COD) added — detects semantically incoherent modules
- **v0.8.0:** Co-Change Coupling signal (CCC) added — detects hidden file coupling from co-change patterns; all 15 signals now scoring-active with auto-calibration
- **v0.8.1:** Language consistency — all user-facing finding text switched to English
- **v0.8.2:** `drift config validate` / `drift config show` commands; stable `rule_id` for deduplication

---

## Design Dimensions

Drift serves two complementary purposes. Contributions should be aware
of which dimension they target:

| Dimension | Purpose | Primary tools |
|-----------|---------|---------------|
| **Diagnosis** | Comprehensive health assessment at a point in time | `drift_scan`, `drift_diff` |
| **Navigation** | Real-time directional feedback during editing | `drift_nudge` |

Diagnosis runs all signals on the full codebase (exact). Navigation runs
only file-local signals on changed files (exact for those, estimated for
cross-file / git-dependent signals). Both share the same signal
implementations — navigation is a subset view with faster feedback.

## Currently important

These areas have the highest impact on drift's credibility and signal quality.
Contributions here are reviewed with priority.

- **Reproduce and harden existing findings** — add minimal fixtures that
  trigger (or should trigger) specific signals, so each finding has a
  deterministic reproduction case.
- **Reduce false positives** — identify cases where drift flags something
  incorrectly and contribute a fixture + expected-result pair.
- **Sharpen finding explanations** — improve the `reason` and `next_action`
  text in signal output so findings are immediately actionable.
- **Edge-case fixtures** — add ground-truth fixtures for boundary conditions
  (empty repos, single-file projects, deeply nested modules).
- **Signal documentation** — write or improve per-signal docs with concrete
  code examples showing what triggers the signal and why.
- **Community validation studies** — independent precision validation,
  actionability assessment, and erosion-pattern research
  ([STUDY.md §15–§17](docs/STUDY.md)).

## Good for new contributors

These tasks are small, isolated, and have clear acceptance criteria.
Look for the [`good first issue`](https://github.com/sauremilk/drift/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) label on GitHub.

- **Add a ground-truth fixture** — create a minimal code sample in
  `tests/fixtures/` that should (or should not) trigger a specific signal.
  See the existing `GroundTruthFixture` class for the pattern.
- **Improve a finding message** — pick a signal, find a vague `reason` or
  `next_action` string, and make it more specific and actionable.
- **Write a test for an untested edge case** — empty input, zero-score
  scenarios, single-function modules.
- **Fix a documentation gap** — add a missing example to a signal reference
  page or correct outdated configuration guidance.
- **Report a false positive or false negative** — even without a code fix,
  a well-documented FP/FN report with a minimal reproduction is a valuable
  contribution. Use the [FP/FN issue template](https://github.com/sauremilk/drift/issues/new?template=false_positive.md).
- **Participate in a self-analysis study** — run `drift analyze` on your own
  repo and share what you found (~15 min).
  Use the [self-analysis template](https://github.com/sauremilk/drift/issues/new?template=study_self_analysis.md).
- **Rate drift findings** — classify findings as TP/FP for inter-rater
  validation (~30 min).
  Use the [finding rating template](https://github.com/sauremilk/drift/issues/new?template=study_finding_rating.md).

## Not currently prioritized

The following areas are acknowledged but will not be actively reviewed
until higher-priority work is complete. PRs in these areas are likely
to wait or be closed with an explanation.

- New output formats without clear additional insight value
- Dashboard or visualization UIs
- Complexity increases without measurable analysis improvement
- Broad refactors that touch many files without a concrete signal-quality gain
- New signals without a precision/recall evaluation against the ground-truth corpus

This is not a permanent rejection — it reflects current phase priorities
([POLICY.md §14](POLICY.md)). If you believe a deprioritized item has
become urgent, open a [contribution proposal](https://github.com/sauremilk/drift/issues/new?template=contribution_proposal.md) with your rationale.
