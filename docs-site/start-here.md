# Start Here

This page is the canonical entry point when you are not sure where to begin.

Choose the path that matches your job-to-be-done instead of scanning the whole documentation tree.

## I want to use drift

Start here if you want a first useful run, a safe rollout path, or a practical setup in CI.

- [Installation](getting-started/installation.md)
- [Quick Start](getting-started/quickstart.md)
- [Configuration](getting-started/configuration.md)
- [Team Rollout](getting-started/team-rollout.md)
- [Finding Triage](getting-started/finding-triage.md)
- [Integrations](integrations.md)
- [API and Outputs](reference/api-outputs.md)

Recommended order:

1. install drift
2. run `drift analyze --repo .`
3. review the first 3 to 5 findings
4. move to report-only CI

## I want to evaluate drift

Start here if you need to decide whether drift is credible, useful, and mature enough for your team.

- [Example Findings](product/example-findings.md)
- [Trust and Evidence](trust-evidence.md)
- [Stability and Release Status](stability.md)
- [Benchmarking and Trust](benchmarking.md)
- [Case Studies](case-studies/index.md)
- [Drift vs Ruff](comparisons/drift-vs-ruff.md)
- [Drift vs Semgrep and CodeQL](comparisons/drift-vs-semgrep-codeql.md)
- [Drift vs Architecture Conformance Tools](comparisons/drift-vs-architecture-conformance.md)

Recommended order:

1. inspect concrete findings
2. read the trust posture and limits
3. compare drift to the tools you already use
4. validate on one representative repository

## I want to contribute

Start here if you want to fix code, improve documentation, reduce false positives, or work on signal quality.

- [Contributing](contributing.md)
- [Product Strategy](product-strategy.md)
- [Changelog](changelog.md)
- Repository guides: [README](https://github.com/sauremilk/drift/blob/main/README.md), [CONTRIBUTING.md](https://github.com/sauremilk/drift/blob/main/CONTRIBUTING.md), [DEVELOPER.md](https://github.com/sauremilk/drift/blob/main/DEVELOPER.md), [POLICY.md](https://github.com/sauremilk/drift/blob/main/POLICY.md)

Recommended order:

1. read the contribution and policy constraints
2. verify what already exists in product strategy and docs
3. make the smallest credible change
4. attach evidence for any feature or signal change

## I want to understand the research and methodology

Start here if you need the detector model, benchmark framing, study material, or the meaning of specific signals.

- [Algorithm Deep Dive](algorithms/deep-dive.md)
- [Signal Reference](algorithms/signals.md)
- [Scoring Model](algorithms/scoring.md)
- [Benchmarking and Trust](benchmarking.md)
- [Benchmark Study](study.md)
- [Glossary](glossary.md)

Recommended order:

1. understand the signal families
2. read how scoring and severity are constructed
3. review the benchmark methodology and limitations
4. use the study for deeper evidence or citation needs

## If you still are not sure

Use this shortcut:

- Want output fast: [Quick Start](getting-started/quickstart.md)
- Want evidence first: [Trust and Evidence](trust-evidence.md)
- Want implementation details: [Algorithm Deep Dive](algorithms/deep-dive.md)
- Want to submit changes: [Contributing](contributing.md)