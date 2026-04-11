# Signal Reference

Drift tracks 24 total signals across architectural erosion and security-by-default patterns. 14 signals are currently scoring-active and 10 are report-only until precision/recall validation is complete or re-validation is finished. Signals are grouped by origin: 6 core signals from the historical v0.5 baseline (with TVS currently held report-only in the composite score), 4 consistency proxy signals (promoted from report-only in v0.7.0 via [ADR-007](https://github.com/mick-gsk/drift/blob/main/docs/adr/007-consistency-proxy-signals.md)), 3 contract signals (added in v0.7.0/v0.7.1 via [ADR-008](https://github.com/mick-gsk/drift/blob/main/docs/adr/008-adr-008-signal-promotion.md)), 1 cohesion signal (COD), 1 co-change coupling signal (CCC), 1 TypeScript architecture signal (TSA), 4 structural report-only signals, 3 security report-only signals, and 1 AI-hallucination report-only signal (PHR).

## Signal Table (All 24)

| Abbrev | Signal | Mode | What it detects |
|---|---|---|---|
| PFS | Pattern Fragmentation | Scoring | Multiple incompatible implementation patterns in the same module. |
| AVS | Architecture Violations | Scoring | Imports crossing intended layer boundaries or structural boundaries. |
| MDS | Mutant Duplicates | Scoring | Near-duplicate functions/classes diverging in subtle ways. |
| EDS | Explainability Deficit | Scoring | Complex code lacking tests, docs, or type/context signals. |
| TVS | Temporal Volatility | Report-only | Files with anomalous churn and instability over git history. |
| SMS | System Misalignment | Scoring | Imports or patterns that are foreign to the target module context. |
| DIA | Doc-Implementation Drift | Scoring | Documented architecture that no longer matches actual code. |
| BEM | Broad Exception Monoculture | Scoring | Overuse of broad exception handling and swallowed failures. |
| TPD | Test Polarity Deficit | Scoring | Tests with insufficient negative/failure-path assertions. |
| GCD | Guard Clause Deficit | Scoring | Public functions lacking early input/precondition guards. |
| COD | Cohesion Deficit | Scoring | Modules/classes mixing unrelated responsibilities and dependencies. |
| NBV | Naming Contract Violation | Scoring | Naming patterns that diverge from dominant project conventions. |
| BAT | Bypass Accumulation | Scoring | Accumulation of TODO/FIXME/HACK and disabled-check bypasses. |
| ECM | Exception Contract Drift | Scoring | Inconsistent exception taxonomies and handling contracts. |
| CCC | Co-Change Coupling | Scoring | Files that repeatedly change together without explicit dependency. |
| TSA | TypeScript Architecture | Report-only | TS/JS architecture violations (layer leaks, cycles, cross-package imports, UI-to-infra imports). |
| CXS | Cognitive Complexity | Report-only | Functions with deeply nested, hard-to-follow control flow. |
| FOE | Fan-Out Explosion | Report-only | Modules/functions with unusually high dependency fan-out. |
| CIR | Circular Import | Report-only | Circular dependency chains in the module import graph. |
| DCA | Dead Code Accumulation | Report-only | Unreferenced functions/classes/symbols accumulating over time. |
| MAZ | Missing Authorization | Report-only | API endpoints lacking auth/authz checks (CWE-862). |
| ISD | Insecure Default | Report-only | Unsafe default config patterns (CWE-1188). |
| HSC | Hardcoded Secret | Report-only | Embedded secrets/tokens/credentials in source (CWE-798). |
| PHR | Phantom Reference | Report-only | Unresolvable function/class references — AI hallucination indicator. |

## Signal-derived negative context

Some signals additionally emit agent-facing anti-pattern warnings via
`negative_context` (JSON output and agent task output).

Contributor rule:

When introducing or promoting a signal, explicitly decide whether it should
produce negative context. If it should, update both in
`src/drift/negative_context.py`:

1. `_SIGNAL_CATEGORY` mapping
2. `@_register(SignalType.XXX)` generator

Reference: [Negative Context](../reference/negative-context.md)

## Core Signals

### Pattern Fragmentation (PFS)

**What it detects:** Same category of pattern implemented N different ways within one module.

**Example:** Error handling split across try/except, bare except, logging-only, and re-raise patterns in the same API module.

**Score:** `1 - (1 / num_variants)` — 4 variants → 0.75 (HIGH)

### Architecture Violations (AVS)

**What it detects:** Imports that cross layer boundaries or create circular dependencies.

**Example:** A database model importing from an API route handler.

**Techniques:** Import graph analysis, layer inference, hub dampening, Tarjan SCC.

### Mutant Duplicates (MDS)

**What it detects:** Near-identical functions that diverge in subtle ways.

**Example:** `validate_user()` and `validate_admin()` sharing 90% identical AST structure.

**Techniques:** AST n-gram Jaccard similarity, LOC bucketing, optional FAISS embeddings.

### Explainability Deficit (EDS)

**What it detects:** Complex functions lacking docstrings, tests, or type annotations.

**Focus:** Especially flags AI-attributed functions (from git blame heuristics).

### Temporal Volatility (TVS)

**What it detects:** Files with anomalous change frequency, author diversity, or defect correlation.

**Techniques:** Statistical z-score on commit frequency, author entropy.

### System Misalignment (SMS)

**What it detects:** Recently introduced imports or patterns foreign to their target module.

**Example:** A utility module suddenly importing from an HTTP client library.

## Consistency Proxy Signals

Promoted from report-only to scoring-active in v0.7.0 with conservative initial weights. See [ADR-007](https://github.com/mick-gsk/drift/blob/main/docs/adr/007-consistency-proxy-signals.md) for the original rationale.

### Doc-Implementation Drift (DIA)

**What it detects:** Documented architecture that no longer matches actual code.

**Weight:** 0.04. Known precision limitations from URL/directory-name heuristics (63% strict precision in v0.5 baseline).

### Broad Exception Monoculture (BEM)

**What it detects:** Modules where exception handling is uniformly broad (bare except, catch-all Exception) with high swallowing ratios.

**Weight:** 0.04.

### Test Polarity Deficit (TPD)

**What it detects:** Test suites with near-zero negative assertions — only happy-path testing, no failure-path coverage.

**Weight:** 0.04.

### Guard Clause Deficit (GCD)

**What it detects:** Modules where public functions uniformly lack early guard clauses (parameter validation, precondition checks).

**Weight:** 0.03.

## Contract Signals

Added in v0.7.0/v0.7.1 via [ADR-008](https://github.com/mick-gsk/drift/blob/main/docs/adr/008-adr-008-signal-promotion.md).

### Naming Contract Violation (NBV)

**What it detects:** Modules where naming conventions diverge from the established codebase patterns (e.g., inconsistent casing, prefix/suffix drift).

**Weight:** 0.04.

### Bypass Accumulation (BAT)

**What it detects:** Modules accumulating bypass patterns (TODO/FIXME/HACK markers, disabled checks, hardcoded overrides) beyond a statistical threshold.

**Weight:** 0.03.

### Exception Contract Drift (ECM)

**What it detects:** Modules where exception hierarchies or error-handling contracts diverge from the dominant codebase pattern.

**Weight:** 0.03.

## Coupling Signal

### Co-Change Coupling (CCC)

**What it detects:** File pairs that repeatedly change together in git history without explicit import dependency.

**Example:** `order_service.py` and `payment_rules.py` are changed together across many commits, but neither imports the other.

**Techniques:** Deterministic commit co-change aggregation with merge/bot down-weighting and static import-edge exclusion.

**Weight:** 0.005.
