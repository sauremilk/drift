# ADR-086: Trend Gate Enforcement

**Status:** proposed
**Date:** 2025-07-21
**Authors:** Mick Gottschalk

## Context

Drift tracks composite-score history per repository in `.drift-cache/history.json`. Until now, this history was used only for trend visualization — no enforcement gate existed for CI pipelines. As a result, steadily degrading codebases could pass CI indefinitely as long as individual scan thresholds were met.

Feature 06 introduces a configurable trend gate: if the composite score degrades by more than `delta_threshold` points over `window_commits` recent commits, the gate blocks the pipeline — unless remediation activity (resolved findings) is detected in the same window.

## Decision

Add a first-class trend gate to `drift check` and `drift ci` with:

1. **Config model** (`TrendGateConfig` in `GateConfig`): `enabled`, `window_commits`, `delta_threshold`, `require_remediation_activity`.
2. **Gate evaluation logic** (`evaluate_trend_gate` in `quality_gate.py`): compares composite scores across the deduplicated commit window and returns a `TrendGateDecision`.
3. **Remediation detection** (`remediation_activity.py`): detects resolved fingerprints between consecutive distinct commits in the window.
4. **Snapshot enrichment** (`trend_history.py`): each persisted snapshot now includes `commit_hash` and `finding_fingerprints` to enable remediation detection.
5. **CLI flags** `--trend-gate / --no-trend-gate` on both `drift check` and `drift ci` to override config at runtime.

Default: `enabled = False` — no behavioral change for existing users unless they opt in.

## Consequences

**Positive:**
- Teams can catch architectural degradation trends, not just point-in-time threshold violations.
- Remediation bypass prevents false-positive blocks when active fixes are in progress.
- Fully configurable — users control window size, threshold, and remediation policy.
- Additive to existing severity gate; can be combined.

**Negative:**
- Requires at least `window_commits` distinct history entries before the gate activates (safe fallback: `insufficient_history` → not blocked).
- Snapshot enrichment adds minor overhead (git `rev-parse HEAD` subprocess + fingerprint computation).

## Alternatives Considered

- **Fixed global threshold** (no per-repo config): rejected — thresholds vary too much across codebase sizes.
- **Trend-only enforcement without remediation bypass**: too aggressive for active-fix workflows.
- **Separate `drift trend-gate` subcommand**: rejected — adds CLI surface without reducing check/ci composability.

## References

- `src/drift/quality_gate.py` — `TrendGateDecision`, `evaluate_trend_gate`
- `src/drift/remediation_activity.py` — new module
- `src/drift/trend_history.py` — snapshot enrichment
- `src/drift/commands/check.py`, `src/drift/commands/ci.py` — CLI integration
- `src/drift/config/_schema.py` — `TrendGateConfig`, `GateConfig`
- POLICY.md §18 — risk audit obligation
