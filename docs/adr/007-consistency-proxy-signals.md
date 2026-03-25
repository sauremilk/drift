# ADR-007: Consistency Proxy Signals (BEM, TPD, GCD)

**Status:** Accepted  
**Date:** 2026-03-25  
**Relates to:** EPISTEMICS.md §2 ("Konsistente Falschheit")

## Context

EPISTEMICS Problem 2 describes a fundamental blind spot: when an entire codebase *uniformly* does something wrong, standard drift detection sees consistency — not error. Semantic correctness is unobservable from syntax alone (the "syntax–semantics gap").

Direct detection of semantic wrongness would require domain models, LLMs, or specification oracles — none of which are deterministic or reproducible, violating ADR-001.

## Decision

We introduce **three deterministic proxy signals** that detect *structural conditions under which consistent wrongness thrives* — specifically, **uniformity without differentiation**:

### Signal 8: Broad Exception Monoculture (BEM)
- **Detects:** Modules where ≥80% of exception handlers catch broadly (bare/Exception/BaseException) AND ≥60% swallow errors (pass/log/print only)
- **Proxy for:** Error-handling monoculture that masks distinct failure modes
- **Data source:** Existing `PatternInstance.fingerprint["handlers"]` — no new parsing needed

### Signal 9: Test Polarity Deficit (TPD)
- **Detects:** Test suites with ≥5 test functions where <10% of assertions are negative (pytest.raises, assertRaises, assertFalse, etc.)
- **Proxy for:** Happy-path-only testing that leaves error paths unexercised
- **Data source:** In-signal AST walking of test files

### Signal 10: Guard Clause Deficit (GCD)
- **Detects:** Modules where <15% of public, complex (≥5 CC) functions with ≥2 parameters have guard clauses (isinstance, assert, if-raise)
- **Proxy for:** Blind-trust data flow where inputs are consumed without validation
- **Data source:** In-signal AST walking of function bodies (Python only)

All three signals launch as **report-only (weight 0.00)** per Phase 1 (Trust) requirements.

## Consequences

### Positive
- Addresses an epistemically fundamental gap without violating determinism
- Each signal has independent precision characteristics and can be promoted/demoted individually
- BEM reuses existing pattern data; no ingestion pipeline changes needed
- Explicitly documented epistemics: each signal states what it CAN and CANNOT detect

### Negative
- In-signal AST walking (TPD, GCD) re-parses source files — minor performance cost
- GCD is Python-only initially (TypeScript has different validation idioms)
- Proxy signals have inherent precision ceiling: they detect *conditions*, not *faults*

### Promotion Criteria
A signal is promoted from 0.00 to active weight when:
1. Ablation study shows ΔF1 > 0.02 on the ground truth sample
2. False positive rate ≤ 20% on at least 5 real-world repositories
3. No overlap with existing active signals exceeds 30% of findings

## Alternatives Considered

1. **LLM-based semantic analysis:** Rejected — violates ADR-001 (determinism), not reproducible
2. **Single combined "consistency flaw" signal:** Rejected — each proxy has independent precision and should be tunable/disablable independently
3. **Extending the AST parser:** Rejected for now — in-signal walking avoids breaking changes to shared ingestion pipeline; can be upstreamed later if performance requires it
