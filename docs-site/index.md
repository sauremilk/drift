---
template: home.html
title: Drift — Architecture Erosion Detection for AI-Assisted Python Development
description: Deterministic static analyzer that detects cross-file coherence problems in AI-assisted Python codebases — pattern fragmentation, architecture violations, and near-duplicate code. Agent-native (MCP), 23 signals, 97% precision, no LLM.
---

<!-- Primary content is rendered by overrides/home.html template. -->
<!-- Below: supplementary text for search engines and MkDocs site search. -->

Drift is a deterministic static analyzer for **architectural erosion** in AI-assisted Python codebases. AI code generation creates structural drift — identical helpers across files, broken layer boundaries, inconsistent error handling. Drift detects it deterministically: cross-file coherence problems that pass tests but make code progressively harder to change.

Unlike linters (Ruff, pylint) which check single files, or security scanners (Semgrep, CodeQL) which trace data flows, Drift operates **across module boundaries** — analyzing AST structure and git history to surface structural degradation. No LLM, no cloud calls: same repo, same commit, same results.

## What Drift Detects

- **Pattern Fragmentation (PFS)** — the same concern handled inconsistently across modules
- **Architecture Violations (AVS)** — layer boundaries eroded through forbidden imports
- **Mutant Duplicates (MDS)** — AST-level near-clones that diverged across files
- **Temporal Volatility (TVS)** — files that change together but aren't co-located
- **Explainability Deficit (EDS)** — complex code without proportional documentation

24 signals total — 18 scoring-active, 6 report-only. Each finding includes file location, cause, severity score, and a concrete next step.

## Get Started

```bash
# Human dev
pip install drift-analyzer
drift analyze --repo .

# Agent setup (MCP)
pip install drift-analyzer[mcp]
drift init --mcp
```

- [Quick Start](getting-started/quickstart.md) — install to first findings in 2 minutes
- [Example Findings](product/example-findings.md) — 5 concrete findings with code and fix paths
- [Evaluate Drift](start-here.md) — evidence, comparisons, and rollout guidance

## How It Works

Drift parses Python via AST, analyzes git history, runs 23 detection signals, and produces scored, actionable findings — deterministically, with zero external dependencies at runtime.

- [Algorithm Deep Dive](algorithms/deep-dive.md) — signal mechanics under the hood
- [Signal Reference](algorithms/signals.md) — all 23 signals explained
- [Scoring Model](algorithms/scoring.md) — composite scoring methodology

## Trust and Evidence

- [Trust and Evidence](trust-evidence.md) — precision claims, methodology, limitations
- [Benchmarking](benchmarking.md) — 15 real-world repos, reproducible results
- [Comparisons](comparisons/index.md) — how Drift complements Ruff, Semgrep, SonarQube

## Integrate

- [Integrations](integrations.md) — GitHub Action, pre-commit, MCP for Copilot/Cursor/Claude, SARIF
- [Agent Integration](integrations.md) — MCP server, session baselines, structured fix plans
- [Team Rollout](getting-started/team-rollout.md) — start report-only, tighten over time
- [Case Studies](case-studies/index.md) — FastAPI, Pydantic, Django, Paramiko
- [Contributing](contributing.md) — the fastest way to help is reporting a false positive

## Agent-Native Features

Drift is built for AI-assisted development workflows. Agent-native commands provide structured output that coding agents can parse and act on:

- **MCP Server** — `drift mcp --serve` — Model Context Protocol integration for VS Code Copilot, Cursor, Claude Desktop, and Windsurf
- **Session Baseline** — `drift scan --max-findings 5` — top 5 critical findings as focused agent context
- **Structured Fix Plan** — `drift fix-plan --repo .` — prioritized repair tasks as machine-readable output
- **Pre-Commit Gate** — `drift diff --staged-only` — structural regression check for staged changes

Deterministic — no LLM in the pipeline. Agents can trust the output because the same repo and commit always produce the same results.
