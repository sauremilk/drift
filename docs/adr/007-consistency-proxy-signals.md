# ADR-007: Consistency Proxy Signals (BEM, TPD, GCD)

**Status:** Accepted
**Date:** 2026-03-25
**Relates to:** EPISTEMICS.md §2 ("konsistente Falschheit")

## Context

EPISTEMICS §2 identifies *consistent wrongness* as a structural risk
that Drift cannot detect with its existing signals: when every module
follows the same pattern, all metrics are green, yet the shared
assumption is wrong.  Examples include uniform broad exception handling
that swallows real error classes, test suites with only happy-path
coverage, and public APIs that uniformly skip input validation.

These patterns share a common trait: **uniformity without
differentiation**. The absence of variation is itself a signal.

## Decision

Introduce three deterministic proxy signals that detect structural
conditions under which consistent wrongness thrives.  Each signal
measures *uniformity of a defensive practice* across a module:

| Signal | Abbrev | What it detects |
|--------|--------|----------------|
| Broad Exception Monoculture | BEM | ≥80% broad catch + ≥60% swallowing per module |
| Test Polarity Deficit | TPD | <10% negative assertions in test suites with ≥5 functions |
| Guard Clause Deficit | GCD | <15% guarded public functions (≥2 params, complexity ≥5) |

**Report-only start:** All three signals launch with weight `0.00`.
They generate findings visible in reports but do not affect composite
scores.

**Promotion criteria:** A signal is promoted to active weight when an
ablation study shows ΔF1 > 0.02 on the ground-truth sample, with
FP rate ≤ 20% and overlap with existing signals ≤ 30%.

## Consequences

### Positive
- Drift can surface a previously invisible class of architectural risk
- Precision-gates (minimum handler/function counts) limit false positives
- Report-only mode preserves trust (Phase 1 priority)
- Each signal is independently promotable/disableable

### Negative
- Three new signal files increase maintenance surface
- GCD is Python-only (TypeScript guard idioms differ)
- TPD requires in-signal AST walking (not reusable by ingestion layer)

### Epistemological Limits
These signals detect *conditions* for consistent wrongness, not the
wrongness itself.  A module with diverse exception handling may still
be wrong; a module with only positive tests may be correct.  The
signals flag *structural uniformity* as a risk factor.

## Alternatives Considered

1. **Single meta-signal (SMA):** Combine all three into one score.
   Rejected — each proxy has independent precision characteristics and
   should be tuned separately.

2. **LLM-based semantic analysis:** Use embeddings to detect "same
   pattern everywhere." Rejected — violates determinism requirement
   and Phase 1 trust priority.

3. **Extend existing signals:** Add BEM logic to PFS, TPD to EDS.
   Rejected — would conflate different measurement dimensions and
   complicate ablation.
