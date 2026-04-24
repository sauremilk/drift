# ADR-008: Intention & Contract Proxy Signals (NBV, BAT, ECM)

**Status:** Accepted
**Date:** 2026-03-26
**Relates to:** ADR-007 (Consistency Proxy Signals), EPISTEMICS.md §2–§4

## Context

ADR-007 introduced three proxy signals (BEM, TPD, GCD) that detect
*conditions for consistent wrongness* — structural uniformity as a risk
factor.  EPISTEMICS §2–§4 identifies three additional blind spots that
remain unaddressed:

1. **Intention Drift:** Code artefacts (name, type, docstring, test)
   contradict each other about what a function is supposed to do.
2. **Implicit Contract Drift:** A function's observable behaviour
   envelope (exception profile, guard clauses, side effects) changes
   while its signature stays the same.
3. **Process Erosion:** Quality-bypass markers (`# type: ignore`,
   `# noqa`, `TODO`) accumulate monotonically, indicating declining
   development discipline.

These problems share a trait: they are *not directly measurable* in
full generality (§4 proves this requires formal specification or
runtime observation), but each has **statically observable surrogates**
that satisfy Drift's determinism and reproducibility requirements.

## Decision

Introduce three new deterministic proxy signals that detect structural
conditions indicative of intention drift, contract drift, and process
erosion:

| Signal | Abbrev | What it detects |
|--------|--------|----------------|
| Naming Contract Violation | NBV | Functions whose name implies a behaviour (validate → raise, is → bool) that the AST does not contain |
| Bypass Accumulation | BAT | Modules with anomalous density of quality-bypass markers (type: ignore, noqa, pragma, TODO, cast) |
| Exception Contract Drift | ECM | Public functions whose exception profile changed across commits while their signature remained stable |

**Report-only start:** All three signals launch with weight `0.00`,
identical to the ADR-007 precedent.  They generate findings visible in
all output formats but do not affect the composite drift score.

**Promotion criteria:** Identical to ADR-007 — a signal is promoted to
active weight when an ablation study shows ΔF1 > 0.02 on the
ground-truth sample, with FP rate ≤ 20% and overlap with existing
signals ≤ 30%.

**Implementation sequence:**
- Phase 1: NBV (low effort, pure AST, no git dependency)
- Phase 2: BAT (low effort, regex + optional git trend)
- Phase 3: ECM (medium effort, requires AST-diff infrastructure)

## Consequences

### Positive
- Drift can surface intention-level and contract-level drift that was
  previously declared out of scope
- All three signals are fully deterministic (AST + regex + git)
- Report-only mode preserves Phase 1 trust
- NBV and BAT require zero new infrastructure — they consume existing
  `ParseResult` and source text
- ECM builds reusable AST-diff infrastructure for future signals

### Negative
- ECM requires reading historical source from git (`git show`), which
  adds subprocess calls and is unavailable in shallow clones
- NBV naming rules are Python-convention-specific; TypeScript mapping
  is deferred to V2
- BAT bypass markers may be legitimate at library boundaries

### Epistemological Limits
- NBV detects *declared* intention (via naming) not *actual* intention.
  Functions without naming markers are invisible.
- BAT measures *suppression density* not *suppression justification*.
  A high density may be legitimate for files wrapping poorly-typed
  external libraries.
- ECM detects *structural* contract change (exception types, guards)
  not *semantic* contract change (altered return values, changed
  timing).  Transitive changes (callee behaviour changes) are not
  captured.

## Alternatives Considered

1. **Cross-Artifact Coherence (full):** Systematically compare types,
   docstrings, tests, and naming for contradictions.  Deferred — NBV
   captures the highest-signal subset (naming) at lowest effort.  Full
   cross-artifact coherence is a V2 candidate.

2. **Behavioural Signature Drift (full CFG skeleton):** Track
   control-flow-graph hash over commits.  Deferred — ECM captures the
   most actionable subset (exception profile) at lower effort.

3. **LLM-based intention analysis:** Rejected — violates ADR-001
   determinism requirement.

4. **Stale temporal artefact detector (TODO age):** Rejected for V1 —
   low architectural impact, closer to linting than drift detection.
