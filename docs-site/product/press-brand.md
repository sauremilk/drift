# Press and Brand

This page collects reusable project descriptions for listings, directories, newsletter blurbs, and external references.

It is intentionally compact so that third parties can describe drift consistently without inventing their own wording.

## Messaging hierarchy

- Hero: Drift catches what AI coding tools break silently — structural erosion across files that passes all your tests.
- Primary: quality control layer for AI-generated Python code
- Secondary: AI code coherence monitor — deterministic architecture erosion detection
- Secondary: structural rot from vibe-coding, caught before it compounds
- Tertiary: cross-file coherence analysis for fast-growing repositories

## One-sentence description

Drift catches what AI coding tools break silently — structural erosion across files that passes all your tests.

## Short description

Drift is a quality control layer for AI-generated Python code. It detects structural erosion that passes linters, type checkers, and tests: the same problem solved four different ways, database logic leaking into the API layer, near-duplicate scaffolding accumulating across modules. No LLM in the pipeline — deterministic, reproducible, built for CI and agent workflows.

## Extended boilerplate

AI coding tools generate code that works — but silently erodes structural consistency. Drift catches this before it compounds. It operates across file boundaries to detect pattern fragmentation, architecture violations, mutant duplicates, and 21 more structural signals. Designed for repositories where tests stay green while the codebase gets progressively harder to change. Deterministic, benchmarked on a public study corpus, and intended for gradual rollout in CI rather than immediate hard gating.

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

Drift is a quality control layer for AI-generated Python code. It catches structural erosion that passes tests — pattern fragmentation, architecture violations, mutant duplicates, and structural hotspots across modules. Deterministic, no LLM, works in CI and inside coding agents (MCP).

## Suggested comparison framing

Use drift when the missing question is not whether code is syntactically correct or policy-compliant, but whether AI-generated code is silently making your repository harder to reason about.

## Source pages for deeper verification

- [Trust and Evidence](../trust-evidence.md)
- [Integrations](../integrations.md)
- [API and Outputs](../reference/api-outputs.md)
- [Case Studies](../case-studies/index.md)