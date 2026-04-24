# Drift vs Ruff

Drift and Ruff solve different problems.

Ruff is a local correctness, style, and linting tool. Drift is a deterministic architectural linter for cross-file coherence problems.

## Short answer

Use Ruff to keep individual files clean.

Use drift when the missing question is whether the repository is fragmenting structurally across modules and over time.

## Comparison

| Question | Ruff | Drift |
|---|---|---|
| Local linting and style | Yes | No |
| Fast feedback in a single file | Yes | No |
| Cross-file coherence | No | Yes |
| Pattern fragmentation across one module | No | Yes |
| Layer and import boundary drift | No | Yes |
| Near-duplicate structural patterns | No | Yes |
| Architectural findings in SARIF/JSON | Indirectly, depending on rule set | Yes |

## When teams use both

The normal path is not Ruff or drift.

The useful path is Ruff and drift:

- Ruff keeps local code quality consistent.
- drift highlights architectural erosion that local rules do not model.

## Example difference in practice

If a service has four incompatible error-handling shapes inside one module, Ruff may consider all four variants syntactically fine.

Drift can still report the fragmentation as a structural finding because the issue is inconsistency, not syntax.

## Where to go next

- [Architecture Drift Detection for Python](../use-cases/architecture-drift-python.md)
- [Architectural Linter for AI Coding Teams](../use-cases/architectural-linter-ai-teams.md)
- [Signal Reference](../algorithms/signals.md)
