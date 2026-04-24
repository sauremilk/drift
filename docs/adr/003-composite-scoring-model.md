# ADR-003: Composite Scoring Model — Weighted Mean with Count-Dampened Aggregation

**Status:** Accepted (revised)
**Date:** 2025-12-15
**Decision Makers:** @mick-gsk

## Context

Drift produces findings across 6 detection signals. Each finding has a score (0.0–1.0). The challenge: how to combine N findings from M signals into a single composite "drift score" for a module and for the entire repository?

This score drives two critical user-facing decisions:
1. **CI gate:** Does the build pass or fail? (severity threshold)
2. **Module ranking:** Which modules need attention first? (sorted by score)

We need a scoring model that is:
- **Intuitive:** A score of 0.6 should "feel" like 60% drifted.
- **Fair across signals:** A signal that produces 500 findings shouldn't dominate a signal with 2 critical findings.
- **Configurable:** Teams should be able to prioritize signals that matter to their codebase.

## Decision

### Signal-Level Aggregation

Each signal's aggregate score is computed as:

$$S_i = \frac{\sum_{j=1}^{n_i} f_{ij}}{n_i} \cdot \min\left(1.0,\; \frac{\ln(1 + n_i)}{\ln(1 + k)}\right)$$

Where:
- $f_{ij}$ = score of the j-th finding for signal $i$
- $n_i$ = number of findings for signal $i$
- $k$ = dampening constant (default: 10)

The first term is the arithmetic mean of finding scores. The second term is a **count dampening factor** that scales from 0 to 1 logarithmically, reaching 1.0 when the finding count hits $k$.

**Rationale for count dampening:** A single medium-severity finding (score 0.5) is less concerning than 15 medium-severity findings — even though both have the same mean score. The dampening factor expresses: "more findings of the same kind are worse, with diminishing returns."

### Composite Score

The composite drift score combines signal scores with configurable weights:

$$D = \frac{\sum_{i=1}^{M} w_i \cdot S_i}{\sum_{i=1}^{M} w_i}$$

Where $w_i$ are the user-configurable weights from `drift.yaml`.

### Default Weights

| Signal | Weight | Justification |
|--------|--------|---------------|
| Pattern Fragmentation (PFS) | 0.22 | Most reliably indicates codebase inconsistency. Low false-positive rate. |
| Architecture Violation (AVS) | 0.22 | Layer boundary violations compound quickly. Hard to fix retroactively. |
| Mutant Duplicates (MDS) | 0.17 | Important but higher false-positive rate (text similarity is imprecise). |
| Temporal Volatility (TVS) | 0.17 | Useful signal but depends on git history depth. New repos have sparse data. |
| Explainability Deficit (EDS) | 0.12 | Valuable but partially subjective (missing docstring ≠ always bad). |
| System Misalignment (SMS) | 0.10 | Narrowly scoped (only recent imports). Useful in CI, less in full analysis. |
| Doc-Implementation Drift (DIA) | 0.00 | Phase 2 stub. Zero weight prevents deactivated signal from affecting scores. |

**Weight selection process:** We ran Drift against 5 open-source repositories with manually annotated architectural issues and tuned weights to maximize rank correlation (Kendall's τ) between Drift's module ranking and the manual ranking. PFS and AVS had the highest individual correlation (τ > 0.6), justifying their higher weights.

## Alternatives Considered

### Alternative 1: Maximum Score (instead of Mean)

$S_i = \max(f_{i1}, f_{i2}, \ldots, f_{in_i})$

**Rejected because:** A single high-severity finding in one file would dominate an otherwise clean module. One `except Exception: pass` in a 200-file module shouldn't produce a module score of 0.85.

### Alternative 2: P95 Score

$S_i = \text{P95}(f_{i1}, \ldots, f_{in_i})$

**Considered but deferred.** P95 is more robust to outliers than max, but becomes volatile with small finding counts (n < 5). For signal-level aggregation where finding counts are often single digits, P95 behaves erratically. We may revisit this for module-level scoring where finding counts are larger.

### Alternative 3: Bayesian Weighted Average

Use signal reliability (estimated false positive rate) as a Bayesian prior. Signals with lower reliability contribute less.

**Rejected for now:** Requires calibrated false-positive estimates per signal, which we don't have yet. Adds conceptual complexity that makes the scoring model harder to explain. The count dampening factor partially addresses this by reducing the impact of signals with few findings.

## Sensitivity Analysis

We tested how the composite score changes when individual weights shift by ±0.05:

| Weight Change | Score Impact (median across test repos) |
|---------------|------------------------------------------|
| PFS ±0.05 | ±0.03 |
| AVS ±0.05 | ±0.02 |
| MDS ±0.05 | ±0.01 |
| TVS ±0.05 | ±0.01 |

The model is not overly sensitive to any single weight. A ±0.05 weight change produces at most ±0.03 composite score change, which is unlikely to flip a CI gate decision.

## Consequences

- Signals that produce many findings get a boost (up to the dampening constant), reflecting that pervasive issues are worse than isolated ones.
- Teams can override default weights in `drift.yaml` to match their priorities.
- The `doc_impl_drift` weight of 0.0 ensures the Phase 2 stub doesn't affect scores.
- Module rankings are driven by the same composite formula, ensuring consistency between module-level and repo-level scores.

---

> **Historical note:** The weights above reflect the v0.5 baseline used during initial calibration. The current production weights (v0.8.0+) include all 15 signals with auto-calibration. See `src/drift/config.py` for current defaults and [scoring.md](../../docs-site/algorithms/scoring.md) for the full weight table.
