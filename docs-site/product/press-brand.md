# Press and Brand

This page collects reusable project descriptions for listings, directories, newsletter blurbs, and external references.

It is intentionally compact so that third parties can describe drift consistently without inventing their own wording.

## Messaging hierarchy

- Primary: deterministic architectural drift detection for AI-accelerated Python codebases
- Secondary: architecture erosion analysis
- Secondary: cross-file coherence detection
- Secondary: structural code quality for fast-growing repositories

## One-sentence description

Drift provides deterministic architectural drift detection for AI-accelerated Python codebases.

## Short description

Drift is an open-source static analyzer for Python repositories. It surfaces architectural drift through architecture erosion analysis and cross-file coherence detection: pattern fragmentation, architecture violations, mutant duplicates, explainability gaps, temporal volatility, and system misalignment. It complements linters, type checkers, and security tools with deterministic findings about structural coherence, plus JSON and SARIF output for automation.

## Extended boilerplate

Drift helps teams inspect architectural drift before it becomes normalized. The tool is designed for repositories where local code quality checks still pass, but structural consistency is slipping across modules over time. It is especially useful in fast-growing, AI-accelerated Python repositories. Drift is deterministic, benchmarked on a public study corpus, and intended for gradual rollout in CI rather than immediate hard gating.

## Safe factual points

- package name: `drift-analyzer`
- repository: `mick-gsk/drift`
- command: `drift`
- runtime: Python 3.11+
- outputs: rich terminal, JSON, SARIF
- GitHub Action support: yes
- analysis style: deterministic, no LLM in the detector pipeline
- scoring model: 18 scoring signals in the current composite model; 6 additional signals are report-only, with TVS at weight 0.0 pending re-validation

## Suggested directory blurb

Drift detects architectural drift in Python codebases. It complements local linting and security checks by surfacing architecture erosion and cross-file coherence problems such as pattern fragmentation, layer boundary violations, mutant duplicates, and structural hotspots.

## Suggested comparison framing

Use drift when the missing question is not whether code is syntactically correct or policy-compliant, but whether the repository is getting harder to reason about structurally.

## Source pages for deeper verification

- [Trust and Evidence](../trust-evidence.md)
- [Integrations](../integrations.md)
- [API and Outputs](../reference/api-outputs.md)
- [Case Studies](../case-studies/index.md)