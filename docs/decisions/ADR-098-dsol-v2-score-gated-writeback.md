# ADR-098 — DSOL v2: Score-Gated Write-Back, Convergence-Check, FP-Oracle-Integration

- Status: proposed
- Date: 2025-01-01
- Supersedes: —
- Supplements: [ADR-097](ADR-097-self-improvement-loop.md)
- Related: ADR-096 (KPI Trend), ADR-091 (Drift-Retrieval-RAG)

## Context

ADR-097 defines the Drift Self-Improvement Loop (DSOL) as a read-only analysis cycle that
produces human-reviewed proposals but never mutates the repository autonomously. A review of
the original implementation identified seven concrete gaps:

1. **CP1 — Scan-Staleness Blind Spot**: DSOL ran on cached scan data without detecting when the
   self-scan step had failed or the report was too old (>7 days).
2. **CP2 — Score-Gate missing**: No gate validated that proposals actually improved drift score
   before write-back was invoked.
3. **CP3 — Convergence-Blind Loop**: DSOL could repeat identical proposals across cycles
   indefinitely with no stagnation detection.
4. **CP4 — DRIFT_SELF_SCAN_FAILED not propagated**: Workflow YAML did not propagate the
   self-scan failure status into the engine via env var.
5. **CP5 — FP-Oracle report never persisted**: `fp-oracle-audit.yml` had `contents: read`, so
   `oracle_fp_report.json` was never committed and could not feed DSOL proposals.
6. **CP6 — Quality threshold absent**: No minimum proposal score filtered low-confidence
   proposals from the cycle.
7. **CP7 — Artefact retention over-long**: `retention-days: 365` exceeded the 90-day cycle
   visibility window needed.

This ADR documents the design decisions for addressing all seven gaps.

## Decision

### 1. Staleness Detection (CP1 + CP4)

`_check_scan_staleness(path, max_age_days=7)` is added to `engine.py`. It:
- Returns a warning string if `DRIFT_SELF_SCAN_FAILED=1` (env var set by workflow when
  `self_scan.outcome == 'failure'`).
- Returns a warning string if the self-report file is older than `max_age_days`.
- Returns `None` if the scan is fresh.

The workflow sets `DRIFT_SELF_SCAN_FAILED=1` via
`${{ steps.self_scan.outcome == 'failure' && '1' || '' }}`.

`ImprovementReport.scan_stale: bool` records whether any staleness warning was emitted.

### 2. Score-Gate (CP2)

`scripts/validate_proposals.py` is a standalone Click script (not imported at runtime) that:
- Verifies at least one proposal exists.
- Verifies all proposals meet `--min-score`.
- Verifies `current_score >= baseline - 5.0` (5-point regression tolerance).
- Exits 0 (PASS) or 1 (FAIL).

The `writeback` job calls this script before applying any artefacts. The gate is only active
when `enable-writeback: true` — the default cron run is never affected.

### 3. Convergence-Check (CP3)

`_convergence_check(ledger_rows, window=4)` returns `ConvergenceStatus`:
- `stagnating: bool` — True when >50% of the last cycle's proposal IDs appeared in all
  previous `window` cycles.
- `overlap_ratio: float` — fraction of repeated IDs.
- `repeated_ids: tuple[str, ...]` — which IDs are stagnant.

`scripts/check_dsol_convergence.py` wraps this as a CLI gate (exit 0/1). The `writeback`
job calls it with `--fail-on-stagnation` before applying artefacts.

`ImprovementReport.convergence_status: ConvergenceStatus | None` records the result.

### 4. FP-Oracle Integration (CP5)

`fp-oracle-audit.yml` gains `contents: write` and a new step that commits
`benchmark_results/oracle_fp_report.json` when `save_history: true`.

`_fp_oracle_proposals(oracle_report, previous_ids, max_items)` in `engine.py` reads
`budget_violations` from the oracle report and emits `kind="fp_rate_exceeded"` proposals.
Recurrence is boosted when the same signal appeared in the previous cycle's ledger.

### 5. Quality Threshold (CP6)

`SelfImprovementEngine.__init__` gains `min_proposal_score: float = 0.0`.
After generating proposals, any proposal with `score < min_proposal_score` is dropped.
The CLI `drift self-improve run` gains `--min-score FLOAT`.
The workflow passes `${{ inputs.min-proposal-score }}` to the engine.

### 6. Artefact Retention (CP7)

`retention-days: 365` → `retention-days: 90`. Ninety days covers four weekly cycles plus
a two-week review margin. Beyond that, the ledger JSONL on `drift-history` branch serves as
the persistent record.

### 7. Write-Back Design (opt-in, artefact-only)

The new `writeback` job:
- Is conditional on `inputs.enable-writeback == true` (never runs on cron schedule).
- Has `permissions: contents: write` (isolated from the `cycle` job's `contents: read`).
- Only writes human-reviewable Markdown action artefacts to `work_artifacts/dsol_actions/`.
- Never modifies source code, scoring weights, or configuration.
- Commits with `[skip ci]` to prevent loop re-entry.

`drift self-improve apply` (new Click subcommand) reads a `proposals.json` and writes:
- `stale_audit_action_<ts>.md` for `kind="stale_audit"`
- `adr_stub_<signal>.md` for `kind="regressive_signal"`
- `fp_triage_<signal>.md` for `kind="fp_rate_exceeded"`
- `hotspot_<id>.md` for `kind="hotspot_finding"`

## Consequences

### Positive
- Stale-data proposals are flagged rather than silently included.
- Score regression is caught before write-back occurs.
- Stagnating loops self-terminate rather than producing noise indefinitely.
- FP oracle findings feed proposals automatically once the oracle report is persisted.
- Low-quality proposals are filtered at the source.
- Artefact storage is bounded to a meaningful window.

### Negative / Trade-offs
- `writeback` is strictly opt-in — cron runs produce no repo mutations. Teams that want
  automated write-back must explicitly trigger `workflow_dispatch`.
- Convergence detection requires at least 2 ledger rows; the first two cycles always pass.
- Score-Gate requires `benchmark_results/kpi_snapshot.json` to exist; if missing, the gate
  falls back to score 0.0 (conservative).

## Out of scope

- Automated code patch generation (remains forbidden — ADR-097 §Out-of-scope).
- Signal scoring weight adjustment.
- Cross-repo DSOL execution.
- ADR auto-acceptance (status stays `proposed` until maintainer reviews).
