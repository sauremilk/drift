# ADR-002: AST Fingerprinting for Pattern Classification

**Status:** Accepted
**Date:** 2025-12-05
**Decision Makers:** @mick-gsk

## Context

Drift's Pattern Fragmentation Signal (PFS) needs to determine whether two code patterns (e.g. two `try/except` blocks) represent the "same approach" or "different approaches" to a cross-cutting concern. This is the core classification problem: given N error-handling blocks in a module, how many distinct *variants* exist?

We evaluated three approaches for pattern classification:

1. **Text similarity** (e.g. `difflib.SequenceMatcher` on raw source text)
2. **AST fingerprinting** (extract structural features into a JSON dict, group by fingerprint equality)
3. **Embedding similarity** (encode patterns with a code embedding model, cluster by cosine distance)

## Decision

**We chose option 2: AST fingerprinting.**

Each code pattern (error handling, API endpoint, etc.) is reduced to a structural fingerprint — a JSON dictionary capturing the decisions the developer made, not the specific variable names or formatting.

Example fingerprint for a `try/except` block:

```json
{
  "handler_count": 1,
  "handlers": [
    {
      "exception_type": "ValueError",
      "actions": ["raise"]
    }
  ],
  "has_finally": false,
  "has_else": false
}
```

Two patterns with identical fingerprints are the "same variant." Different fingerprints = different variants. Variant counting per module per category produces the fragmentation score.

## Trade-offs

### Fingerprinting vs. Text Similarity

| Criterion | Text Similarity | AST Fingerprinting |
|-----------|-----------------|---------------------|
| **Rename robustness** | Fails: `except ValueError` ≠ `except ValueError as err` scores < 1.0 even though the *approach* is identical | Succeeds: both produce `{"exception_type": "ValueError", "actions": ["raise"]}` |
| **Formatting independence** | Fails: different indentation or line breaks reduce similarity | Succeeds: AST is format-agnostic |
| **Semantic granularity** | Too fine: detects cosmetic differences as "different patterns" | Right level: captures *what decisions were made* (which exception? raise or log? finally block?) |
| **False positives** | High: reports formatting differences as fragmentation | Low: only structural differences count |
| **Implementation complexity** | Trivial (one-liner) | Medium (per-pattern fingerprint extractor needed) |
| **Extensibility** | Generic but undiscriminating | Each pattern category gets a domain-specific extractor |

**Concrete example where text similarity fails:**

```python
# Variant A
try:
    result = process(data)
except ValueError as e:
    raise ProcessingError(str(e)) from e

# Variant B (same approach, different variable names)
try:
    output = process(input_data)
except ValueError as err:
    raise ProcessingError(str(err)) from err
```

Text similarity: ~70% (below typical 80% threshold). AST fingerprint: identical `{"exception_type": "ValueError", "actions": ["raise"]}`.

### Fingerprinting vs. Embeddings

| Criterion | AST Fingerprinting | Embedding Similarity |
|-----------|---------------------|----------------------|
| **Dependencies** | Zero (built-in `ast` module) | Heavy (`sentence-transformers`, `faiss-cpu`, `numpy`) |
| **Determinism** | Fully deterministic | Model-dependent (different model versions → different clusters) |
| **Interpretability** | Fingerprint diffs are human-readable | Cosine distances are opaque |
| **Clustering quality** | Binary (same/different) — misses "almost same" | Continuous similarity — captures gradients |
| **Runtime** | O(n) per file (single AST walk) | O(n) embedding + O(n²) similarity matrix |

Embeddings are strictly more powerful for fuzzy matching, but they violate ADR-001's determinism requirement and add ~200MB of model dependencies. We defer embedding-based similarity to an optional `[embeddings]` extra install for Phase 2.

## Implementation

Each pattern category has a dedicated fingerprint extractor:

- **Error handling** (`_fingerprint_try_block`): Captures exception types, handler action taxonomy (`raise`/`log`/`print`/`pass`/`return`/`call`), `finally`/`else` presence.
- **API endpoints** (`_fingerprint_endpoint`): Captures error handling presence, auth checks, return patterns, async/sync.

The action taxonomy is the key design choice. We classify handler body statements into 6 categories rather than comparing raw AST nodes:

```
raise     → re-raises or wraps the exception
return    → swallows the exception with a return value
log       → calls logging/error/warning methods
print     → stdout/stderr output (common anti-pattern)
pass      → silently swallows (anti-pattern)
call      → delegates to another function
```

This taxonomy is what makes two "log-and-continue" handlers fingerprint-identical even if one uses `logger.error()` and the other uses `logging.warning()`.

## Consequences

- Adding a new pattern category requires writing a dedicated `_fingerprint_*` function.
- The fingerprint schema is not versioned — changes to fingerprint structure invalidate the parse cache (acceptable since cache is keyed by file content hash, not fingerprint schema).
- Patterns that differ only in variable names, formatting, or comment content are correctly grouped as the same variant.
- Patterns that differ in *structural decisions* (raise vs. log, sync vs. async) are correctly split into different variants.

## Limitations

- Two structurally identical `try/except` blocks using `raise` are considered the same variant even if they raise *different* custom exception types. We could add exception type specificity to the fingerprint, but this increases fragmentation noise for codebases with rich exception hierarchies.
- The action taxonomy requires maintenance as new patterns emerge (e.g. `match/case` error handling in Python 3.10+).
