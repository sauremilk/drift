# ADR-005: Delta-First Score Interpretation — Preventing Goodhart Optimization

**Status:** Accepted  
**Date:** 2026-03-24  
**Decision Makers:** @mick-gsk

## Context

### The Problem

Drift produces a composite score (0.0–1.0) that represents structural coherence of a codebase. STUDY.md §11.7 demonstrates that this score is temporally stable (σ < 0.005 for mature repos) and correlates with structural changes (not noise). The tool's own documentation states: *"The value of drift is delta, not absolute."*

However, the current output architecture contradicts this principle:

1. **`drift analyze` emits an absolute score without trend context.** A team seeing `Score: 0.512 (MEDIUM)` has no frame of reference — is this good? Bad? Improving? Degrading?

2. **The CI gate (`fail_on`) operates on absolute severity.** Teams set `fail_on: high` and optimize toward keeping findings below that threshold — creating Goodhart dynamics where the score becomes the target.

3. **`drift trend` is a separate, opt-in command.** The delta interpretation — which is the *only* valid interpretation per drift's own design — requires a deliberate extra step that most CI pipelines skip.

4. **JSON/SARIF outputs contain no historical context.** Downstream consumers (dashboards, PR bots) receive a point-in-time number without the temporal frame needed to interpret it.

### Empirical Evidence (STUDY.md)

- **Django 6.0 score drop (Δ = -0.016):** The largest delta in 10 years was caused by removing legacy code — *improving* the codebase. A team targeting "score < 0.55" would have been at 0.553–0.563 for a decade and might have deleted productive code to reach 0.55. The delta tells the real story: -0.016 after a cleanup is a positive signal.

- **Refactoring paradox:** Unifying error-handling patterns across a module temporarily *increases* PFS (two patterns coexist mid-refactoring). A delta-aware system shows "+0.02 this sprint, -0.04 next sprint" — which is the expected trajectory. An absolute-score gate would block the PR that introduces the temporary regression.

- **Migration transitions:** PWBS (a known AI-assisted codebase) has AVS findings because it uses two data-access patterns simultaneously. These findings are structurally correct but contextually expected. Without delta context, the score misleads.

### Threats from Goodhart Optimization

In AI-assisted teams that track the composite score as a KPI:

| Perverse Incentive | Mechanism | Consequence |
|--------------------|-----------|-------------|
| **Deletion bias** | Deleting high-PFS modules is faster than refactoring them | Productive code removed to lower score |
| **Uniformity bias** | Copying the most common pattern (even if wrong) avoids PFS increase | Monoculture; reduced adaptability |
| **Refactoring avoidance** | Mid-refactoring score spikes trigger CI failures | Refactorings abandoned before completion |
| **Sophistication ceiling** | Complex architectures (CQRS, event sourcing) produce more signals than simple MVC | Teams choose simpler (worse) architecture to minimize score |

## Decision

### Principle: No Absolute Score Without Temporal Context

Every drift output that includes a composite score MUST also include:
1. The previous score (if history exists)
2. The delta (current − previous)
3. The delta direction (improving / stable / degrading)
4. The history depth (number of prior snapshots)

When no history exists, the output MUST explicitly state that no trend interpretation is possible.

### Change 1: Inline Trend Context in `drift analyze`

`analyze_repo()` reads the history file (`.drift-cache/history.json`) after computing the current score and attaches a `TrendContext` to `RepoAnalysis`.

```python
@dataclass
class TrendContext:
    previous_score: float | None     # Last snapshot score
    delta: float | None              # current - previous
    direction: str                   # "improving" | "stable" | "degrading"
    recent_scores: list[float]       # Last 5 scores
    history_depth: int               # Total snapshots available
    transition_ratio: float          # % of findings with drift:context tags
```

**Direction logic:**
- `|Δ| < 0.005` → `"stable"` (below noise floor per STUDY.md §11.6)
- `Δ < -0.005` → `"improving"`
- `Δ > +0.005` → `"degrading"`

**Rich output with trend:**
```
Drift Score: 0.442 (MEDIUM)  Δ −0.015 ↓ improving
  Trend: 0.472 → 0.457 → 0.442 (3 snapshots)
```

**Rich output without history:**
```
Drift Score: 0.442 (MEDIUM)  — baseline (no prior snapshots)
  ⚠ Run drift analyze again after structural changes to establish trend.
```

**JSON output enrichment:**
```json
{
  "drift_score": 0.442,
  "severity": "medium",
  "trend": {
    "previous_score": 0.457,
    "delta": -0.015,
    "direction": "improving",
    "recent_scores": [0.472, 0.457, 0.442],
    "history_depth": 3,
    "transition_ratio": 0.0
  }
}
```

When no history exists: `"trend": null`.

### Change 2: Delta-Based CI Gate (opt-in)

New configuration options in `drift.yaml`:

```yaml
fail_on: high                # Existing: severity-based gate (unchanged)
fail_on_delta: 0.05          # New: fail if Δ > +0.05 (score increased)
fail_on_delta_window: 5      # Compare against mean of last N snapshots
```

**Semantics:**
- `fail_on_delta` compares the current score against the mean of the last `fail_on_delta_window` snapshots.
- If `current_score - mean(recent_N) > fail_on_delta`, the gate fails.
- If no history exists, the delta gate passes (first run cannot fail on delta).

**Why mean-of-N instead of last-1:** A single outlier snapshot (e.g., mid-refactoring) shouldn't anchor the delta gate. Mean-of-5 smooths transient spikes while still catching sustained degradation.

**Interaction with `fail_on`:** Both gates are independent. A run can fail on severity *or* delta *or* both. `fail_on: none` + `fail_on_delta: 0.05` is a valid configuration that ignores absolute severity and only gates on trend.

### Change 3: History Auto-Persistence

Currently, only `drift trend` writes to the history file. After this ADR:

- `drift analyze` writes a snapshot to `.drift-cache/history.json` after every run.
- `drift trend` reads and displays the history (no change to trend behavior).
- History retention: 100 snapshots (unchanged).

This ensures that delta context accumulates even for teams that only use `drift analyze` in CI.

### Change 4: SARIF Trend Properties

SARIF output gains custom properties on the `run` object:

```json
{
  "runs": [{
    "properties": {
      "drift:trend": {
        "previousScore": 0.457,
        "delta": -0.015,
        "direction": "improving"
      }
    }
  }]
}
```

GitHub Code Scanning surfaces custom properties in the UI, making delta visible in PR annotations.

## Consequences

### Positive

1. **Goodhart resistance:** Teams cannot optimize on the absolute score without seeing the delta. The delta *is* the primary signal in every output format.
2. **Refactoring support:** Mid-refactoring score spikes are visible as transient deltas, not permanent failures. `fail_on_delta_window: 5` absorbs spikes up to 5 runs.
3. **First-run honesty:** New users see "baseline — no trend yet" instead of a decontextualized number.
4. **CI flexibility:** `fail_on_delta` allows teams to gate on *degradation rate* instead of *absolute level* — which is the correct operational interpretation per drift's design.
5. **Backward compatible:** All changes are additive. Existing `fail_on` behavior is unchanged. Delta gate is opt-in. JSON consumers that don't read `trend` are unaffected.

### Negative

1. **History file dependency:** Delta context requires `.drift-cache/history.json` to persist across CI runs. Ephemeral CI environments (fresh container per run) need artifact caching or a shared volume. Mitigation: document caching patterns for GitHub Actions, GitLab CI, Jenkins.
2. **Noise at low history depth:** With only 2 snapshots, the delta is noisy. Mitigation: `fail_on_delta_window` defaults to 5 — the gate is lenient until sufficient data exists.
3. **Disk I/O in analyze:** `analyze_repo()` now reads and writes the history file. Impact: <1ms for 100 JSON snapshots — negligible relative to analysis time.

### Neutral

- The composite scoring model (ADR-003) is entirely unchanged. Weights, dampening, signal aggregation — all untouched.
- The deterministic pipeline (ADR-001) is preserved. Trend context is a post-computation read from a local file, not a non-deterministic input to the analysis.

## Alternatives Considered

### Alternative 1: Remove the Composite Score Entirely

Replace the single number with a signal-level dashboard (7 individual scores). Force users to interpret each signal independently.

**Rejected:** The composite score exists (ADR-003) because it serves a real need — quick triage. A 7-dimensional signal space is not actionable in a CI gate. The problem is not the existence of the score but the absence of interpretation context.

### Alternative 2: Score Bands Instead of Numbers

Replace `0.442` with `HEALTHY / CONCERNING / DEGRADED` bands. Remove numeric precision entirely.

**Rejected:** Bands hide information. A team at 0.449 and a team at 0.550 would both be "CONCERNING" — but their trajectories may be opposite. The numeric score with delta is more informative than categorical bands.

### Alternative 3: Mandatory `drift trend` Before `drift analyze`

Require teams to run `drift trend` first, which establishes baseline. `drift analyze` without prior `drift trend` emits a warning.

**Rejected:** Adds friction. Splits a natural workflow into two commands. The better design is to make `drift analyze` self-contextualizing by auto-reading history.

### Alternative 4: Server-Side Score Storage

Store scores in a central drift server / SaaS backend for cross-team comparison and normalization.

**Rejected:** Contradicts ADR-001's zero-infrastructure principle. Drift runs locally — no server, no cloud, no account. History persistence is a local file problem, solvable with CI artifact caching.

## Implementation Notes

### Data Model Changes

```python
# models.py — new dataclass
@dataclass
class TrendContext:
    previous_score: float | None
    delta: float | None
    direction: str        # "improving" | "stable" | "degrading" | "baseline"
    recent_scores: list[float]
    history_depth: int
    transition_ratio: float

# models.py — extend RepoAnalysis
@dataclass
class RepoAnalysis:
    # ... existing fields ...
    trend: TrendContext | None = None
```

### Config Changes

```python
# config.py — extend DriftConfig
class DriftConfig(BaseModel):
    # ... existing fields ...
    fail_on_delta: float | None = None          # e.g. 0.05
    fail_on_delta_window: int = 5
```

### Scoring Engine Changes

```python
# scoring/engine.py — new function
def delta_gate_pass(
    current_score: float,
    history: list[dict],
    fail_on_delta: float,
    window: int = 5,
) -> bool:
    """Check if score degradation exceeds the delta threshold."""
    recent = [s["drift_score"] for s in history[-window:]]
    if not recent:
        return True  # No history → gate passes
    baseline = sum(recent) / len(recent)
    return (current_score - baseline) <= fail_on_delta
```

### Output Changes

All three renderers (Rich, JSON, SARIF) read `RepoAnalysis.trend` and render context. No change to the rendering interface — only additional data in the existing dataclass.

## References

- [ADR-001: Deterministic Analysis Pipeline](001-deterministic-analysis-pipeline.md) — zero-infrastructure constraint
- [ADR-003: Composite Scoring Model](003-composite-scoring-model.md) — scoring model preserved
- [STUDY.md §11.6](../STUDY.md) — temporal stability evidence (σ < 0.005)
- [STUDY.md §11.7](../STUDY.md) — major-version correlation (django 1.8→6.0)
- [POLICY.md §7](../../POLICY.md) — priority hierarchy (Glaubwürdigkeit > Signalpräzision > ...)
