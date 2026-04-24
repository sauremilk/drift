# Architectural Technical Debt in AI-Assisted Codebases

Drift is useful when a team already knows that AI-assisted delivery is increasing output, but cannot yet see where structural technical debt is accumulating.

This page focuses on one narrow question: how do you detect technical debt that is architectural rather than merely stylistic?

## What kind of technical debt drift is good at

Drift is strongest when technical debt shows up as cross-file coherence loss:

- duplicated implementation shapes that should have stayed shared
- mixed architectural patterns inside one module
- import boundaries that erode over time
- modules whose change behavior suggests structural instability

That is a different problem from formatting debt, typing debt, or security debt.

## Why AI-assisted teams feel this early

AI coding tools make local task completion faster. They do not automatically preserve the repository's shared implementation habits.

The result is often technical debt with a structural signature:

- more local variants of the same concern
- more copy-modify helpers
- more exceptions to boundaries that used to be clean
- more review effort spent explaining why code technically works but does not fit

## What drift gives you

- deterministic detection of architectural debt patterns
- file-level findings that teams can inspect directly
- JSON and SARIF outputs for automated workflows
- a rollout path that starts with observation instead of hard gating

## What drift does not claim

Drift does not claim to detect every form of technical debt.

It is intentionally narrower: it helps when debt becomes visible as architectural erosion in real code structure.

## Recommended first step

1. Run [Quick Start](../getting-started/quickstart.md).
2. Look at the highest-scored findings in modules that already feel expensive.
3. Use those findings to decide whether the debt is local cleanup or a structural pattern worth standardizing.

## Related pages

- [Architecture Drift Detection for Python](architecture-drift-python.md)
- [Architectural Linter for AI Coding Teams](architectural-linter-ai-teams.md)
- [Trust and Evidence](../trust-evidence.md)
- [API and Outputs](../reference/api-outputs.md)
