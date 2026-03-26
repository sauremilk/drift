# Drift — Architectural Drift Detection for Python

**Deterministic architectural drift detection for AI-accelerated Python codebases.**

Drift is a deterministic static analyzer for teams that want to catch architectural drift before it becomes normal: fragmented patterns, boundary violations, near-duplicates, and unstable hotspots that accumulate when code is optimized for local delivery but not for global coherence. It is especially useful in fast-moving, AI-accelerated repositories.

> Repo: `sauremilk/drift` · Package: `drift-analyzer` · Command: `drift` · Requires: Python 3.11+

## Why teams add drift next to existing checks

- Ruff, formatting, and typing keep local code clean.
- Semgrep, CodeQL, and security tooling catch risky flows.
- Drift adds a deterministic view of architecture erosion analysis and cross-file coherence detection: pattern fragmentation, boundary erosion, and drift hotspots.

## Start Here

```bash
pip install drift-analyzer
drift analyze --repo .
```

## Choose Your Path

Use the central [Start Here](start-here.md) page if you want the documentation segmented by goal instead of by section.

- I want to **use** drift
- I want to **evaluate** drift
- I want to **contribute**
- I want to understand the **research and methodology**

Direct shortcuts:

- [Quick Start](getting-started/quickstart.md)
- [Trust and Evidence](trust-evidence.md)
- [Contributing](contributing.md)
- [Algorithm Deep Dive](algorithms/deep-dive.md)

Current public evidence: 15 real-world repositories in the study corpus, 6 scoring signals, and 4 report-only signals (DIA, BEM, TPD, GCD) with weight 0.00 until extraction precision improves.

Release posture is intentionally conservative: the PyPI classifier remains Alpha, while the core Python analysis and CI-facing workflows are already the most stable parts of the product. See [Stability and Release Status](stability.md) for the explicit maturity matrix.

## Example Findings

If you are evaluating drift, concrete findings are usually more persuasive than methodology alone.

- [Example Findings](product/example-findings.md) shows 5 short, reproducible findings with code, the likely drift result, why it matters, and the fix path.
- The examples cover pattern fragmentation, mutant duplicates, architecture violations, doc-implementation drift, and temporal volatility.

## What Drift Is Good At

- surfacing architecture and coherence issues that linters do not model
- complementing fast-moving development, including AI-assisted workflows, with deterministic checks
- helping teams review hotspots, modules, and trends instead of isolated style violations

## What Drift Is Not

- not a bug finder
- not a security scanner
- not a type checker
- not a zero-false-positive oracle

## Trust Model

Drift earns trust through reproducible analysis, explicit methodology, and signal-by-signal interpretation.

- deterministic pipeline with no LLM in the core analysis path
- benchmark material and study artifacts kept in the repository
- guidance for gradual rollout instead of immediate hard gating
- clear limitations and interpretation notes in the docs

See [Benchmarking and Trust](benchmarking.md) for methodology, known limitations, and how to read findings conservatively.

If you need a compact evidence summary first, read [Trust and Evidence](trust-evidence.md).

If you need the release-maturity breakdown first, read [Stability and Release Status](stability.md).

## Compare Drift to Adjacent Tools

- [Drift vs Ruff](comparisons/drift-vs-ruff.md)
- [Drift vs Semgrep and CodeQL](comparisons/drift-vs-semgrep-codeql.md)
- [Drift vs Architecture Conformance Tools](comparisons/drift-vs-architecture-conformance.md)

These pages are intentionally narrow: they explain where drift fits, where it does not, and how teams combine it with existing checks.

## Integration Paths

- [Integrations](integrations.md)
- [API and Outputs](reference/api-outputs.md)

## Reusable Project Summary

- [Press and Brand](product/press-brand.md)

## Quick Reference

- [FAQ](faq.md)
- [Glossary](glossary.md)

## Documentation Map

- [Getting Started](getting-started/quickstart.md)
- [How It Works](algorithms/deep-dive.md)
- [Benchmarking and Trust](benchmarking.md)
- [Product Strategy](product-strategy.md)
- [Case Studies](case-studies/index.md)
