# ADR-066 — Adaptive Recommendation Engine (ARE)

**Status:** proposed
**Deciders:** Mick Gottschalk
**Date:** 2025-07-26
**Related:** ADR-035 (per-repo calibration)

---

## Context

Drift generates actionable recommendations alongside findings.  These recommendations use
static effort labels and generic descriptions that do not adapt to the project's actual
fix patterns.  Specifically:

1. Effort labels ("low"/"medium"/"high") are hardcoded per signal type and may not match
   observed fix times in a given codebase.
2. Recommendation text uses generic verbs ("consider reviewing") that score poorly on
   user-reported actionability.
3. There is no feedback loop: recommendations that lead to fast fixes are treated the same
   as those that are ignored.

Three design decisions were required:

1. **Storage**: Where to persist outcome data across analysis runs?
2. **Scoring**: How to quantify recommendation quality without LLM calls?
3. **Refinement**: How to improve recommendation text deterministically?

---

## Decision

### D1 — Repo-local JSONL outcome tracking

Outcomes are stored in `.drift/outcomes.jsonl` (one JSON object per line).  Each entry
records a finding fingerprint (SHA-256 of signal_type + fully_qualified_name/path), the
timestamp when the finding was first reported, and when it disappeared (resolved).

The fingerprint is stable across minor code changes because it uses the fully qualified
name when available, falling back to file_path + start_line.

**Rationale:** JSONL is append-friendly, human-inspectable, and consistent with the
existing `.drift/feedback.jsonl` pattern.  No database dependency.

### D2 — Deterministic four-subscore reward chain

Recommendation quality is scored via `compute_reward()` returning a `RewardScore` with:

| Subscore          | Weight | Source                                    |
|--------------------|--------|------------------------------------------|
| fix_speed          | 0.40   | Days-to-fix (linear decay 1–14 days)     |
| specificity        | 0.30   | File/symbol mention + generic verb ratio  |
| effort_accuracy    | 0.20   | Estimated vs. actual effort class match   |
| no_regression      | 0.10   | Finding did not reappear within 30 days   |

When no outcome data exists, `confidence < 0.5` and fix_speed/no_regression default to 0.0.

**Rationale:** No LLM required, fully deterministic, weights chosen by signal-quality
relevance.  The confidence cap ensures new findings degrade gracefully.

### D3 — Rule-based recommendation refinement

`refine()` applies at most 2 iterative passes based on reward subscores:

1. **Low fix_speed** → prepend concrete file path, symbol name, and line number.
2. **Low specificity** → replace generic verbs ("consider" → "extract") with
   concrete imperatives.

A context suffix is appended once for test/generated/fixture code.  Recommendations with
`reward.total >= 0.7` skip refinement entirely.

**Rationale:** Deterministic, auditable, no hallucination risk.  Max-iteration cap (2)
ensures bounded latency.

### D4 — Effort calibration from outcome history

`calibrate_efforts()` computes median days-to-fix per signal type from resolved,
non-suppressed outcomes.  Mapping: ≤1d → "low", ≤5d → "medium", >5d → "high".

Only signal types with ≥ `min_calibration_samples` (default 10) qualify.
Suppressed outcomes are excluded entirely.

**Rationale:** Median is robust to outliers.  Minimum sample threshold prevents
noisy calibration from sparse data.

---

## Consequences

### Positive

- Recommendations improve over time as outcome data accumulates → self-correcting loop.
- Effort labels become project-specific rather than one-size-fits-all.
- Fully opt-in (`recommendations.enabled: true`) — zero behavioral change by default.
- No PII stored (no author names, emails, or commit hashes in outcome data).
- All logic deterministic — no LLM calls, no network requests.

### Negative

- New JSONL file (`.drift/outcomes.jsonl`) should be gitignored by users.
- Meaningful calibration requires ~10+ resolved findings per signal type.
- Reward weights (0.4/0.3/0.2/0.1) are hardcoded; tuning requires code changes.

### Risks

- **Fingerprint drift**: FQN changes (renames) may create new fingerprints,
  fragmenting outcome history.  Mitigation: archive rotation (180 days default).
- **Cold start**: New repos have no outcome data → reward confidence capped at 0.3–0.4,
  refinement still runs on specificity but not fix_speed.

---

## Module Map

| File | Purpose |
|------|---------|
| `src/drift/outcome_tracker.py` | Outcome dataclass, fingerprinting, JSONL persistence |
| `src/drift/reward_chain.py` | RewardScore, four-subscore computation |
| `src/drift/calibration/recommendation_calibrator.py` | Effort calibration from outcomes |
| `src/drift/recommendation_refiner.py` | Rule-based text refinement |
| `src/drift/config.py` | `RecommendationsConfig` Pydantic model |
| `src/drift/commands/calibrate.py` | CLI: `effort-run`, `effort-report`, `effort-reset` |
| `src/drift/commands/analyze.py` | ARE integration hook (post-recommendation) |
