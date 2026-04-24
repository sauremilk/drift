# ADR-006: Context-Tagging for Intentional Variance

**Status:** Accepted
**Date:** 2026-03-24
**Relates to:** EPISTEMICS.md Problem 1, ADR-001 (determinism), ADR-003 (scoring)

## Context

Drift assumes that structural variance is an indicator of erosion. This is
generally true, but breaks down in two well-documented scenarios
(EPISTEMICS.md §1):

1. **Architecture transitions** — A migration from monolith to services
   necessarily co-locates old and new patterns. The temporary variance *is* the
   migration; penalizing it discourages progress.

2. **Deliberate polymorphism** — Strategy patterns, codec hierarchies, and
   plugin systems produce structural similarity that drift interprets as
   duplication, even when it is the intended architecture.

The existing `drift:ignore` pragma fully suppresses findings. This is too
blunt: it hides the signal entirely and removes all tracking. Teams need a
mechanism that says *"I see this variance and it is intentional"* without
losing coverage.

## Decision

Introduce **`drift:context <tag>`** inline pragmas that annotate code regions
with intentional-variance context. Findings that overlap a context-tagged
region are **dampened, not suppressed**: their score is reduced by a
configurable factor, and the context tags are recorded in finding metadata
for full traceability.

### Pragma Syntax

```python
# drift:context migration
class NewPaymentService:
    ...

# drift:context deliberate,strategy-pattern
def process_card(self): ...
```

```typescript
// drift:context refactoring
export function legacyHandler() { ... }
```

### Supported Formats

| Language   | Comment style                        |
|------------|--------------------------------------|
| Python     | `# drift:context <tag>[,<tag>]`      |
| TypeScript | `// drift:context <tag>[,<tag>]`     |
| JavaScript | `// drift:context <tag>[,<tag>]`     |

### Semantics

- Tags are **free-form** strings (lowercase, hyphens, underscores allowed).
- Multiple tags are comma-separated.
- A context comment applies to the **line it appears on** and the finding whose
  range includes that line. This matches the `drift:ignore` line-match contract.
- Context tags do **not** suppress findings. Findings remain visible in all
  output formats with their original signal type and description.

### Score Dampening

Tagged findings receive: `score = original_score × context_dampening`

- `context_dampening` is configurable (default: **0.5**, range 0.0–1.0).
- Setting `context_dampening: 1.0` disables dampening (tags are metadata-only).
- Setting `context_dampening: 0.0` is equivalent to suppression (discouraged).
- Impact is recomputed after dampening.

### Output

- **Rich terminal:** Summary line shows context-tagged count alongside
  suppressed count. Findings show `[ctx: migration]` tag annotation.
- **JSON:** Each finding's `metadata` includes `"context_tags": ["migration"]`.
- **SARIF:** Context tags appear in finding `properties`.

### Configuration

```yaml
# drift.yaml
context_dampening: 0.5  # Score reduction factor for context-tagged findings
```

## Consequences

### Positive

- False positives from intentional variance are reduced without hiding the signal.
- Context tags create an audit trail of *acknowledged* architectural decisions.
- `transition_ratio` (reserved in ADR-005's TrendContext) can be populated with
  the ratio of context-tagged to total findings.
- CI gates can be tuned: a team in migration can set `context_dampening: 0.3`
  to account for expected variance.

### Negative

- Developers must add pragmas manually (though this is also true for
  `drift:ignore`).
- The dampening factor is a heuristic — there is no principled way to derive
  the "correct" reduction for a given tag.

### Neutral

- The feature is strictly additive; codebases without `drift:context` comments
  behave identically.
- ADR-001 (determinism) is preserved: same input → same output.
