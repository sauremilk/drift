# Drift — Contribution Roadmap

This roadmap communicates what the project needs most right now,
what is accessible for new contributors, and what is explicitly
deprioritized. It is updated with each release.

Last updated: v0.7.1 (2026-03-27)

---

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
