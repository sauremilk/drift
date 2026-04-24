# Drift vs Architecture Conformance Tools

Drift and architecture conformance tools are related, but they are not the same category.

Architecture conformance tools verify whether code obeys explicit architectural rules. Drift detects emergent architectural erosion and cross-file coherence loss, including cases where no formal rule was written down.

## Short answer

Use architecture conformance tools when you already know the intended boundaries and want executable enforcement.

Use drift when the repository is drifting structurally and you need a deterministic way to surface the patterns before or alongside formal rules.

## Comparison

| Question | Architecture conformance tools | Drift |
|---|---|---|
| Enforce predefined layer rules | Yes | Partially, when `layer_boundaries` are configured |
| Detect emergent structural drift without explicit rules | Limited | Yes |
| Cross-file pattern fragmentation | No | Yes |
| Near-duplicate architectural patterns | No | Yes |
| Boundary erosion as a scored signal | Usually binary rule results | Yes |
| Composite orientation score | Usually no | Yes |
| Deterministic CI rollout with SARIF/JSON | Depends on tool | Yes |

## Where they fit together

The useful sequence is often:

1. use drift to identify where the architecture is already fragmenting
2. convert the clearest recurring boundaries into explicit conformance rules
3. keep drift in place to catch structural patterns that formal rules still do not model

This matters because many repositories do not start with complete architecture rules. Drift helps teams see where explicit enforcement would be worth adding.

## Example difference in practice

If a repository has three competing error-handling shapes in the same module, a conformance tool may stay silent unless a specific rule exists for that pattern.

Drift can still flag the fragmentation because the issue is architectural inconsistency, not only rule violation.

If a repository already defines layer boundaries explicitly, drift and a conformance tool can reinforce each other rather than compete.

## Related pages

- [Architecture Drift Detection for Python](../use-cases/architecture-drift-python.md)
- [Trust and Evidence](../trust-evidence.md)
- [Signal Reference](../algorithms/signals.md)
