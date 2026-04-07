---
template: home.html
title: Drift — Architecture Erosion Detection
---

Drift is a deterministic analyzer for structural erosion in Python repositories.

It surfaces the cross-file problems that usually pass tests but still make a codebase harder to change: fragmented patterns, layer leaks, near-duplicate helpers, and inconsistent architecture decisions.

## See Drift First

```bash
pip install -q drift-analyzer
drift analyze --repo .
```

<div align="center">
	<img src="https://raw.githubusercontent.com/mick-gsk/drift/main/demos/demo.gif" alt="drift analyze terminal demo" width="900">
</div>

## What Drift Adds

- Ruff, formatting, and typing keep local code clean.
- Semgrep, CodeQL, and security tooling catch risky flows.
- Drift adds a deterministic view of architecture erosion analysis and cross-file coherence detection: pattern fragmentation, boundary erosion, and drift hotspots.

## Evaluate Drift

**[Start here](start-here.md)** — choose your path: try it, check the evidence, or plan a rollout.

Or jump directly: [Example Findings](product/example-findings.md) · [Trust and Evidence](trust-evidence.md) · [Stability](stability.md) · [Comparisons](comparisons/index.md)

## Use Drift

- [Quick Start](getting-started/quickstart.md)
- [Team Rollout](getting-started/team-rollout.md)
- [Integrations](integrations.md)
- [API and Outputs](reference/api-outputs.md)

## Public Evidence and Release Posture

Current public benchmark claim: 77% strict precision / 95% lenient on the historical v0.5 six-signal baseline (286 findings, 5 repositories, score-weighted sample, single-rater classification with 51 disputed cases).

The drift score reported per repository is a composite coherence metric (higher = more erosion). Individual finding scores measure detection confidence. The precision claim describes historical accuracy across the benchmark corpus — it is not a per-repo guarantee.

The current study corpus covers 15 real-world repositories and the current composite model uses 15 scoring signals, with TVS at weight 0.0 pending re-validation. The broader corpus supports case studies and ongoing validation, but it is not a revalidated headline precision claim for the current model.

Package metadata currently uses the Beta classifier. Rollout guidance is still conservative because the core Python path is stronger than optional or experimental surfaces such as TypeScript support and embeddings-based features.

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

## Contribute or Go Deeper

- [Contributing](contributing.md)
- [Algorithm Deep Dive](algorithms/deep-dive.md)
- [Signal Reference](algorithms/signals.md)
- [Benchmark Study](study.md)

## Compare Drift to Adjacent Tools

- [Drift vs Ruff](comparisons/drift-vs-ruff.md)
- [Drift vs Semgrep and CodeQL](comparisons/drift-vs-semgrep-codeql.md)
- [Drift vs Architecture Conformance Tools](comparisons/drift-vs-architecture-conformance.md)

These pages are intentionally narrow: they explain where drift fits, where it does not, and how teams combine it with existing checks.

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
