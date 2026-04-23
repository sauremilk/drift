# Drift — Contribution Roadmap

This roadmap communicates what the project needs most right now,
what is accessible for new contributors, and what is explicitly
deprioritized. It is updated with each release.

Last updated: v2.9.14 (2026-04-13)

---

## Current phase: Distribution (Q2 2026)

**Current focus: Distribution & demand validation (Q2 2026).** No new signals, no new features, no refactoring.
Goal: validate demand, reach ≥10 external users. Engineering is stable — this phase is about building adoption.

Exceptions: bugfixes that block installation or first-run experience.

### Distribution Milestones

| Milestone | Condition | Earliest date | Status |
|---|---|---|---|
| **pre-commit Discoverability** | `.pre-commit-hooks.yaml` in repo | ✅ done | Indexed via GitHub search + Sourcegraph |
| **awesome-static-analysis PR** | >20 Stars, ≥3 months old, >1 contributor | ~18.06.2026 | ⏳ Gate not met (7 Stars, 19 days) |
| **awesome-python PR** | ≥100 Stars, ≥3 months old | ~18.06.2026 + star growth | ⏳ Gate not met (hard auto-reject before) |
| **pre-commit.com Featured** | >500 Stars | open | ⏳ long-term |

Vollständige Gate-Kriterien und vorbereitete PR-Texte: [`docs/distribution/awesome-submissions.md`](docs/distribution/awesome-submissions.md)

## Strategische Epochen (additiv zu POLICY §14-Phasen)

> **Status:** ADR-084 Option C akzeptiert (2026-04-21, Maintainer-Freigabe) —
> [`docs/decisions/ADR-084-positionierung-vibe-coding-tool.md`](docs/decisions/ADR-084-positionierung-vibe-coding-tool.md).
> Diese Sektion ergänzt die bestehende Distribution-Sektion und bricht
> nichts. Die "Currently important"-Liste und der Distribution-Track
> bleiben unverändert maßgeblich für laufende Arbeit.

### Begriffsabgrenzung

Drift verwendet zwei orthogonale Phasen-Begriffe. Sie dürfen nicht
miteinander verwechselt werden:

| Begriff | Bedeutung | Quelle |
|---------|-----------|--------|
| POLICY §14 Phase 1–4 | Qualitätsreifegrad: Trust → Relevance → Adoptability → Scaling | [`POLICY.md`](POLICY.md) §14 |
| Strategische Epoche A/B/C | Go-to-Market-Epoche: Adoption → Agenten-First → Universal | diese Sektion |

POLICY §14 ist dominante Begriffsachse für interne Qualitätsreife und
hat Vorrang. Strategische Epochen beschreiben die Außenpositionierung
und sind auf POLICY §14 abgebildet, ohne sie zu verdrängen.

### Epoche A — Adoption (laufend)

Identisch mit der oben dokumentierten Distribution-Phase. Ziel: ≥ 10
externe Nutzer, messbare Retention, klares ICP. Keine neuen
Meilensteine über das hinaus, was im Distribution-Track oben steht.

Validiert wird Epoche A durch das Experiment in
[`master-backlog/04-audience-validation-experiment.md`](master-backlog/04-audience-validation-experiment.md).

### Epoche B — Agenten-First (active)

**Aktiv per ADR-084 Option C (Maintainer-Freigabe 2026-04-21). Sub-ADRs
pro Item sind weiterhin erforderlich vor Code-Änderungen.**

Kandidaten-Items (alle `proposed`, jeweils mit Gate-Verweis):

- [Item 06 — Trend-Gate Enforcement](master-backlog/06-trend-gate-enforcement.md)
- [Item 07 — `drift patch --auto` Apply-and-Verify Loop](master-backlog/07-patch-auto-verify-loop.md)
- [Item 08 — VS Code Extension (Beta)](master-backlog/08-vscode-extension-beta.md)

Ergänzend:
[Item 05 — drift_nudge Cold-Start Latenz](master-backlog/05-drift-nudge-cold-start.md)
ist Voraussetzung, falls Z3 (Agent-Framework-Entwickler) als Zielgruppe
adoptiert.

### Epoche C — Universelle Plattform (Platzhalter)

**Erfordert Epoche-B-Abschluss.** Reine Stubs, kein Commitment:

- [Item 09 — Cross-Language IR](master-backlog/09-cross-language-ir.md)
- [Item 10 — Agent-Framework SDK Bindings](master-backlog/10-agent-framework-sdk.md)
- [Item 11 — Cloud Trend-Storage](master-backlog/11-cloud-trend-storage.md)

### Verhältnis zu Go-Support-MVP

Der unten stehende Go-Support-MVP-Track ist **unabhängig** von den
strategischen Epochen. Er bleibt im Post-Moratorium-Status und wird
nicht durch Epoche B vorgezogen. Eine Epoche-C-Entscheidung kann ihn
priorisieren, muss aber nicht.

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

## Completed since v0.8.2

- **v1.1.x:** Navigation track introduced — `drift_nudge` (directional feedback + safe-to-commit guard), incremental baseline/cache model, and diagnosis-vs-navigation framing documented.
- **v1.3.x -> v1.4.x:** Machine-readable reliability hardened — consistent JSON error envelopes across CLI and MCP flows, plus deterministic baseline refresh reasoning.
- **v1.5.0 -> v2.1.x:** Agent UX and release operations matured — agent-focused command/output improvements, PSR-based automated release pipeline, and improved governance/maintainer workflows.
- **v2.4.x:** Context and export surfaces expanded — finding-context triage policy, CSV output for `analyze`/`check`, `diff` score-basis clarity, and stronger MCP robustness (schema typing, structured error envelopes, Windows stdio stability).

- **v2.5.0:** Schema-based config validation, mutation testing infrastructure, per-signal cap for scan, signal abbreviation map, CITATION.cff automation, and diverse-strategy scan improvements.
- **v2.7.0:** Signal filtering for scan — `--exclude-signals` and `--max-per-signal`; harmonized scan finding fields (`signal_abbrev`, `signal_id`, `severity_rank`, `fingerprint`, `cross_validation`); false-positive reductions for DIA, AVS, MAZ, BEM, NBV, ECM, and HSC.
- **v2.9.8:** Calibration hardening — AVS, DIA, and MDS quality improvements, updated thresholds, extended feedback tooling, and refreshed golden snapshots.
- **v2.9.13:** Six new output formats: `pr-comment`, `junit`, `llm`, `ci`, and `gate`; shell tab-completion via `drift completions`; signal clarity hardening (EDS, PFS, AVS, CCC); actionability improvements across CXS, TVS, DCA, MAZ, TSB, and PHR.
- **v2.9.15:** Fix-intent contracts and shadow-verify for risky cross-file edits (ADR-063/064); repair-template registry and coverage matrix (ADR-065).

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
Look for the [`good first issue`](https://github.com/mick-gsk/drift/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) label on GitHub.

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
  contribution. Use the [FP/FN issue template](https://github.com/mick-gsk/drift/issues/new?template=false_positive.md).
- **Participate in a self-analysis study** — run `drift analyze` on your own
  repo and share what you found (~15 min).
  Use the [self-analysis template](https://github.com/mick-gsk/drift/issues/new?template=study_self_analysis.md).
- **Rate drift findings** — classify findings as TP/FP for inter-rater
  validation (~30 min).
  Use the [finding rating template](https://github.com/mick-gsk/drift/issues/new?template=study_finding_rating.md).

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
become urgent, open a [contribution proposal](https://github.com/mick-gsk/drift/issues/new?template=contribution_proposal.md) with your rationale.
