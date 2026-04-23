# Scoring Model

## Composite Drift Score

Individual signal scores are combined into a weighted composite:

$$\text{Score} = \frac{\sum (\text{signal\_weight} \times \text{signal\_score})}{\sum \text{weights}}$$

## Count Dampening

Logarithmic dampening prevents signals with many low-confidence findings from dominating:

$$\text{signal\_score} = \overline{s} \times \min\!\left(1,\; \frac{\ln(1 + n)}{\ln(1 + k)}\right)$$

- $\overline{s}$ = mean finding score
- $n$ = finding count
- $k$ = dampening constant (default: 10)

**Effect:** 1 finding at 0.5 → dampened to 0.27. 15 findings at 0.5 → full 0.5.

## Default Weights

19 signals are currently scoring-active. Weights are normalised at runtime; `auto_calibrate` (default: on) rebalances based on signal variance.

| Signal | Weight | Rationale |
|---|---|---|
| Pattern Fragmentation (PFS) | 0.16 | Highest ablation-study impact on F1 |
| Architecture Violation (AVS) | 0.16 | Critical for maintainability |
| Mutant Duplicate (MDS) | 0.13 | Common AI pattern |
| Explainability Deficit (EDS) | 0.09 | Important but noisy |
| System Misalignment (SMS) | 0.08 | Cross-module novelty detection |
| Doc-Implementation Drift (DIA) | 0.04 | Promoted from report-only (v0.7.0) |
| Broad Exception Monoculture (BEM) | 0.04 | Promoted from report-only (v0.7.0) |
| Test Polarity Deficit (TPD) | 0.04 | Promoted from report-only (v0.7.0) |
| Naming Contract Violation (NBV) | 0.04 | Added in v0.7.0 ([ADR-008](https://github.com/mick-gsk/drift/blob/main/docs/adr/008-adr-008-signal-promotion.md)) |
| Guard Clause Deficit (GCD) | 0.03 | Promoted from report-only (v0.7.0) |
| Bypass Accumulation (BAT) | 0.03 | Added in v0.7.0 ([ADR-008](https://github.com/mick-gsk/drift/blob/main/docs/adr/008-adr-008-signal-promotion.md)) |
| Exception Contract Drift (ECM) | 0.03 | Added in v0.7.1 ([ADR-008](https://github.com/mick-gsk/drift/blob/main/docs/adr/008-adr-008-signal-promotion.md)) |
| Phantom Reference (PHR) | 0.02 | Promoted for scoring in [ADR-039](https://github.com/mick-gsk/drift/blob/main/docs/decisions/ADR-039-activate-agent-safety-signals.md) |
| Missing Authorization (MAZ) | 0.02 | Promoted for scoring in [ADR-039](https://github.com/mick-gsk/drift/blob/main/docs/decisions/ADR-039-activate-agent-safety-signals.md) |
| Cohesion Deficit (COD) | 0.01 | Added in v0.7.3 as cohesion-focused coherence detector |
| Hardcoded Secret (HSC) | 0.01 | Promoted for scoring in [ADR-039](https://github.com/mick-gsk/drift/blob/main/docs/decisions/ADR-039-activate-agent-safety-signals.md) |
| Insecure Default (ISD) | 0.01 | Promoted for scoring in [ADR-039](https://github.com/mick-gsk/drift/blob/main/docs/decisions/ADR-039-activate-agent-safety-signals.md) |
| Co-Change Coupling (CCC) | 0.005 | Added in v0.8.0 for hidden git-history coupling without explicit imports |
| Fan-Out Explosion (FOE) | 0.005 | Promoted for scoring in [ADR-039](https://github.com/mick-gsk/drift/blob/main/docs/decisions/ADR-039-activate-agent-safety-signals.md) |

### Report-only Signals (`weight=0.0`)

The following signals are intentionally report-only in the default model and do not contribute to the composite score:

| Signal | Weight | Status |
|---|---|---|
| Temporal Volatility (TVS) | 0.0 | Report-only pending re-validation |
| TS Architecture (TSA) | 0.0 | Report-only |
| Circular Import (CIR) | 0.0 | Report-only |
| Dead Code Accumulation (DCA) | 0.0 | Report-only |
| Cognitive Complexity (CXS) | 0.0 | Report-only |

Core weights were originally calibrated via ablation study (remove each signal, measure F1 delta, assign proportional weight). Promoted signals received conservative initial weights. See [ADR-003](https://github.com/mick-gsk/drift/blob/main/docs/adr/003-composite-scoring-model.md).

### Historical note

Current default model snapshot: 24 total signals (19 scoring-active, 5 report-only).

The v0.5 benchmark study used 6 core signals at higher weights (PFS=0.22, AVS=0.22, MDS=0.17, TVS=0.17, EDS=0.12, SMS=0.10) with 4 report-only signals at weight 0.00. Precision claims in the study apply to that model. See [ADR-007](https://github.com/mick-gsk/drift/blob/main/docs/adr/007-consistency-proxy-signals.md) for the original report-only rationale.

## Severity Mapping

| Score Range | Severity |
|---|---|
| ≥ 0.80 | CRITICAL |
| ≥ 0.60 and < 0.80 | HIGH |
| ≥ 0.40 and < 0.60 | MEDIUM |
| ≥ 0.20 and < 0.40 | LOW |
| < 0.20 | INFO |

## Module-Level Scoring

Findings are grouped by module path. Each module receives:

- Per-signal scores
- Composite score
- AI attribution ratio (% findings from AI-generated code)
- Top signal identifier
