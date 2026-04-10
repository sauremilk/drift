# Architecture Drift Detection for Python

Drift is useful when a Python repository still passes tests and linters, but the codebase is getting harder to change because structural patterns no longer line up.

This page is for teams asking a specific question: how do we detect architecture drift in Python before it becomes normal?

## When this problem is real

Architecture drift is usually visible before it is formalized.

Typical signals:

- one module implements the same pattern multiple different ways
- imports start crossing layer boundaries that used to be stable
- near-duplicate functions accumulate through copy-modify work
- the same files keep changing because the ownership and structure are unclear

These are cross-file coherence problems. They are not the same as syntax errors, type errors, or security findings.

## What drift detects

Drift currently uses 18 scoring signals in the composite model and keeps 6 additional signals report-only while validation and re-validation continue. The most visible categories for architecture-drift work are:

- pattern fragmentation
- architecture violations
- mutant duplicates
- explainability deficit
- system misalignment
- doc-implementation drift
- temporal volatility as report-only until re-validation

See [Signal Reference](../algorithms/signals.md) for the signal model.

## Why a Python team would use drift

Use drift when you need a deterministic architectural linter for Python that can:

- find coherence problems across files and modules
- produce machine-readable output for CI and triage
- show concrete locations to inspect next
- remain reproducible without an LLM in the detection path

## What drift does not replace

Drift does not replace existing local checks.

Use Ruff, typing, tests, Semgrep, and CodeQL for the problems they already solve well. Use drift when the missing question is whether the repository is fragmenting structurally.

## Concrete evaluation path

1. Run [Quick Start](../getting-started/quickstart.md).
2. Review the strongest findings first.
3. Check whether repeated patterns or boundary violations match your own understanding of the codebase.
4. Keep rollout report-only until the strongest findings prove useful.

## Evidence you can review

- [Trust and Evidence](../trust-evidence.md)
- [Benchmarking and Trust](../benchmarking.md)
- [Case Studies](../case-studies/index.md)
- [Benchmark Study](../study.md)

## Next pages

- [Architectural Linter for AI Coding Teams](architectural-linter-ai-teams.md)
- [CI Architecture Checks with SARIF](ci-architecture-checks-sarif.md)
- [Drift vs Ruff](../comparisons/drift-vs-ruff.md)