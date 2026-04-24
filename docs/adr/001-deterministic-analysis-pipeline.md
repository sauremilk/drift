# ADR-001: Deterministic Analysis Pipeline (No LLM in Detection Core)

**Status:** Accepted
**Date:** 2025-12-01
**Decision Makers:** @mick-gsk

## Context

Drift aims to detect architectural erosion in codebases — particularly erosion caused by AI-generated code. A natural question is whether to use an LLM (e.g. GPT-4, Claude) to power the detection pipeline itself, since LLMs excel at understanding code semantics.

We evaluated three approaches:

1. **LLM-powered detection:** Send code snippets to an LLM and ask it to identify drift patterns (e.g. "Are these two error handling approaches inconsistent?").
2. **Hybrid:** Use deterministic parsing with LLM-based semantic post-processing for ambiguous cases.
3. **Fully deterministic:** AST analysis, graph algorithms, and statistical methods only.

## Decision

**We chose option 3: fully deterministic pipeline.**

The detection core uses only:
- Python's `ast` module for structural parsing
- `networkx` for import graph analysis and cycle detection
- Statistical z-scores for temporal anomaly detection
- `difflib.SequenceMatcher` and AST-based structural comparison for duplicate detection
- Structural fingerprinting (JSON dicts) for pattern variant grouping

No LLM call exists anywhere in the analysis pipeline.

## Trade-offs

### What we gain

| Property | Why it matters |
|----------|----------------|
| **Reproducibility** | Same input → same output. Critical for CI gates: a build that passes today must pass tomorrow with the same code. LLM outputs are non-deterministic (temperature > 0), and even at temperature 0, API behavior can change between model versions. |
| **Speed** | Full analysis of a 500-file repo completes in ~2 seconds. LLM-based analysis would require hundreds of API calls, adding 30-60s minimum. This latency kills pre-commit hook adoption. |
| **Cost** | Zero marginal cost per analysis run. LLM APIs charge per token; analyzing a medium codebase would cost $0.50-2.00 per run. In CI (every push), this becomes $100+/month for active teams. |
| **Auditability** | Every finding traces to a specific algorithm with inspectable inputs. "Why did Drift flag this?" has a concrete answer involving fingerprints, z-scores, or graph edges — not "the model thought so." |
| **Offline operation** | Works without network access. Important for air-gapped environments and for developers with intermittent connectivity. |

### What we lose

| Limitation | Severity | Mitigation |
|------------|----------|------------|
| **Semantic understanding** | Medium | We can't detect that two functions "do the same thing" if they use completely different control flow. Our duplicate detection catches structural similarity (80%+ match), not semantic equivalence. |
| **Natural language reasoning** | Low | We can't parse README claims like "we use the repository pattern" and verify them against code. The `doc_impl_drift` signal is deferred to Phase 2 for this reason. |
| **Context-aware severity** | Low | A human reviewer might say "this violation is fine because it's a migration script." Our signals treat all code equally. We mitigate this with configurable weights and exclude patterns. |

### Why not hybrid?

We prototyped a hybrid approach where the deterministic pipeline pre-filters candidates and an LLM post-processes ambiguous cases. Problems:

1. **Dependency creep:** Adding an LLM dependency (API keys, network, model selection) to a CI tool contradicts the "zero config" goal.
2. **Testing complexity:** How do you write deterministic tests for a non-deterministic component? Mock the LLM? Then you're testing the mock, not the detection.
3. **Diminishing returns:** The cases where deterministic detection is insufficient (semantic equivalence of structurally different code) are also cases where LLMs produce unreliable results.

## Consequences

- All detection signals must be implementable with deterministic algorithms.
- Pattern matching relies on structural fingerprints, not semantic similarity.
- The `doc_impl_drift` signal (documentation vs. code alignment) remains a stub until we find a deterministic approach or explicitly add an optional LLM mode.
- Users who want LLM-enhanced analysis can post-process Drift's JSON/SARIF output with their own tooling.

## Validation

To confirm this decision remains sound, we measured detection quality on three open-source repositories with known architectural issues:

- **False negative rate:** ~15% of manually identified drift patterns are not detected (primarily semantic-only duplicates).
- **False positive rate:** ~8% of findings are debatable (context-dependent, would benefit from semantic understanding).
- **Runtime:** P95 < 3 seconds for repos under 1000 files.

These numbers are acceptable for a CI tool where speed and reliability outweigh exhaustive detection.
