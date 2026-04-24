# Drift vs Semgrep and CodeQL

Semgrep, CodeQL, and drift are complementary.

Semgrep and CodeQL are strong at policy, security, and risky-flow detection. Drift is focused on deterministic architectural erosion and cross-file coherence.

## Short answer

Use Semgrep and CodeQL when you need to know whether code introduces a known bad pattern, vulnerability shape, or policy violation.

Use drift when you need to know whether the repository is slowly diverging from its own architectural patterns.

## Semgrep Pro Engine and cross-file analysis

Semgrep's Pro Engine (2024+) adds interprocedural, cross-file dataflow analysis. This is a meaningful capability — taint flows that cross function and file boundaries are now trackable.

The scope of this cross-file analysis is **security and compliance**: tracking how untrusted data reaches a sensitive sink across module boundaries, finding authorization bypasses, detecting insecure data flows.

Drift's cross-file analysis is **structural coherence**: detecting that the same problem is being solved four different ways across modules (Pattern Fragmentation), that near-identical functions have silently accumulated (Mutant Duplicates), or that a module is importing from a layer it should not depend on (Architecture Violation).

These are different questions. Semgrep Pro answers: "Is this code dangerous?" Drift answers: "Is this codebase becoming harder to reason about structurally?"

A concrete example: drift's Mutant Duplicate signal (MDS) detects this:

```python
# api/handlers/users.py
def _parse_response(data):
    return {k: v for k, v in data.items() if v is not None}

# api/handlers/orders.py
def _clean_response(data):              # different name
    return {k: v for k, v in data.items() if v is not None}  # same body

# api/handlers/products.py
def _filter_nulls(response):            # third variant
    return {k: v for k, v in response.items() if v}  # subtly different
```

Semgrep Pro would not flag this — there is no security issue, no taint flow, no policy violation. Drift reports three mutant duplicates and recommends extraction to a shared utility. This pattern is the primary cause of architectural fragmentation in AI-assisted codebases.

## Comparison

| Question | Semgrep / CodeQL | Drift |
|---|---|---|
| Security and risky flows | Yes | No |
| Policy violations | Yes | No |
| Cross-file taint analysis | Semgrep Pro: Yes | No |
| Cross-file architectural coherence | Limited, depending on rule design | Yes |
| Pattern fragmentation | No | Yes |
| Mutant duplicates | No | Yes |
| Layer-boundary erosion | Sometimes via custom rules | Yes, as a first-class signal |
| Temporal / change-history signals | No | Yes |
| Deterministic (no LLM) | Yes | Yes |
| Composite architectural orientation score | No | Yes |
| Bayesian per-repo calibration | No | Yes |

## Why teams combine them

These tools fail in different directions:

- Semgrep and CodeQL tell you whether code is dangerous or non-compliant.
- drift tells you whether the codebase is becoming harder to reason about structurally.

That makes them additive, not interchangeable.

## Good adoption sequence

1. Keep your existing security and policy checks.
2. Add drift in report-only mode.
3. Use drift findings to review hotspots that are not visible in security tooling.

## Where to go next

- [CI Architecture Checks with SARIF](../use-cases/ci-architecture-checks-sarif.md)
- [Trust and Evidence](../trust-evidence.md)
- [Case Studies](../case-studies/index.md)
