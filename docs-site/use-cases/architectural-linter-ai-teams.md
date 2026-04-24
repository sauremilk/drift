# Architectural Linter for AI Coding Teams

Drift is positioned for teams using GitHub Copilot, Cursor, or similar AI coding tools where code is delivered faster than shared architectural conventions can be reinforced.

The relevant question is not whether the generated code runs. The relevant question is whether it still fits the repository.

## Why AI-assisted teams need a different check

AI coding tools are good at local task completion. They are weaker at preserving cross-file consistency across an evolving codebase.

That usually shows up as:

- the same concern implemented several different ways in one module
- boundary leaks between API, domain, and persistence layers
- copy-modify helpers that look new but duplicate existing logic
- modules importing patterns that do not belong to their local design

## What drift adds next to normal code quality tooling

Drift gives AI-assisted teams a deterministic architectural linter that asks:

- does the new code follow the same implementation shape as related code
- are architectural boundaries staying stable
- is the repository accumulating structural debt faster than review catches it

For a narrower comparison, see [Drift vs Ruff](../comparisons/drift-vs-ruff.md) and [Drift vs Semgrep and CodeQL](../comparisons/drift-vs-semgrep-codeql.md).

## Recommended rollout for AI-heavy teams

1. Start locally with `drift analyze --repo .`.
2. Add report-only CI visibility.
3. Review whether the top findings correspond to places where AI-assisted changes already felt costly.
4. Gate only on `high` findings after a few real pull requests.

The detailed rollout path is in [Team Rollout](../getting-started/team-rollout.md).

## What makes this approach credible

- deterministic pipeline
- no LLM in the detector path
- benchmark material and raw artifacts in the repository
- explicit limitations instead of single-number marketing

See [Trust and Evidence](../trust-evidence.md) for the short evidence summary.

## Best fit

Drift is most useful for:

- Python teams with recurring copy-modify drift
- services where architectural review is becoming slower than code generation
- repositories large enough that cross-file patterns matter

Drift is a weak fit for tiny repos or teams that expect a bug finder.

## Next pages

- [Architecture Drift Detection for Python](architecture-drift-python.md)
- [CI Architecture Checks with SARIF](ci-architecture-checks-sarif.md)
- [FAQ](../faq.md)
