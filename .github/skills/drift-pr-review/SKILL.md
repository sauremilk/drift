---
name: drift-pr-review
description: "Systematic PR review workflow aligned with Drift Policy. Use when reviewing pull requests that touch src/drift/, tests/, or scoring logic."
---

# Drift PR Review Skill

## Purpose

Guide Copilot agents through a policy-conformant, evidence-based pull request review for the drift repository.

## When to Use

- Reviewing PRs that change `src/drift/`, `tests/`, or `docs-site/`
- Evaluating signal quality, scoring changes, or output format changes
- Checking benchmark evidence for new features

## Strukturierte Review-Checkliste

**Pflicht-Referenz:** Die vollständige Review-Checkliste liegt unter `.github/prompts/_partials/review-checkliste.md`.
Bei jedem adversarialen Review wird diese Checkliste Punkt für Punkt abgearbeitet.
Der Reviewer dokumentiert pro Punkt **Ja / Nein / N/A** mit Kurzbegründung.

## Review Workflow

### Step 1: Policy Gate

Before reviewing code, verify the PR passes the Policy Gate:

```
### Drift Policy Gate
- Aufgabe: [PR title / description]
- Zulassungskriterium erfüllt: [JA / NEIN] → [which criterion]
- Ausschlusskriterium ausgelöst: [JA / NEIN] → [if YES: which]
- Roadmap-Phase: [1 / 2 / 3 / 4] — blockiert durch höhere Phase: [JA / NEIN]
- Entscheidung: [ZULÄSSIG / ABBRUCH]
- Begründung: [one sentence]
```

If the gate fails, comment with the reason and suggest what should be prioritized instead.

### Step 2: Signal Quality Checklist

For every new or modified finding/signal, verify all 5 mandatory elements:

- [ ] **Technical traceability** — finding points to specific code location
- [ ] **Reproducibility** — finding can be reproduced from the same input
- [ ] **Unique cause attribution** — finding maps to exactly one root cause
- [ ] **Clear justification** — rationale is documented and understandable
- [ ] **Actionable next step** — a concrete remediation or investigation step exists

A finding missing any element is **non-compliant** with Policy §13.

### Step 3: Benchmark Evidence

For feature PRs (`feat:` commits), verify:

- [ ] `benchmark_results/v*_feature_evidence.json` artifact exists
- [ ] Self-analysis score is equal or better than baseline
- [ ] No regression in precision/recall on known test repos

### Step 4: Self-Score Delta

If `src/drift/` is modified:

```bash
drift analyze --repo . --format json
```

Compare the composite score against the CI threshold (currently 0.47).
A score drop below threshold **blocks** the PR.

### Step 5: Test Coverage

- [ ] New behavior has corresponding test(s) in `tests/`
- [ ] `make check` passes (lint + typecheck + tests + self-analysis)
- [ ] No new `# type: ignore` or `# noqa` without justification

### Step 6: Priority Compliance

Verify the change respects the priority hierarchy:

```
Glaubwürdigkeit > Signalpräzision > Verständlichkeit > FP/FN-Reduktion > Einführbarkeit > Trend > Features
```

A lower-priority change must not compromise a higher-priority property.

## Review Comment Template

```markdown
### PR Review — Drift Policy

**Policy Gate:** ✅ ZULÄSSIG / ❌ ABBRUCH
**Signal Quality (§13):** ✅ All 5 elements / ❌ Missing: [list]
**Benchmark Evidence:** ✅ Present / ⚠️ Missing / N/A
**Self-Score Delta:** ✅ ≥ 0.47 / ❌ Below threshold
**Test Coverage:** ✅ Covered / ❌ Missing tests for: [list]
**Priority Compliance:** ✅ OK / ❌ Violates: [explanation]

**Summary:** [1-2 sentences]
```
