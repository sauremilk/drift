---
title: What is Architectural Drift in AI Codebases?
description: Architectural drift is the silent structural erosion that happens when AI coding tools generate code that works but makes your codebase progressively harder to change. Learn what causes it, why tests don't catch it, and how to detect it.
---

# What is Architectural Drift in AI Codebases?

**Architectural drift** is the gradual erosion of structural consistency in a codebase — the slow accumulation of inconsistencies that individually pass all tests but collectively make the code harder to understand, change, and maintain.

AI coding tools **accelerate** this problem dramatically.

## The Problem: Code That Works But Drifts

When you use Copilot, Cursor, Claude, or other AI assistants, each code generation is locally correct. It works. Tests pass. The linter is happy.

But across files, something breaks silently:

- **The same error handling pattern gets implemented four different ways** — each AI session picks a slightly different approach
- **Database logic leaks into the API layer** — the AI doesn't know your architecture conventions
- **Near-duplicate helper functions accumulate** — copy-paste scaffolding with minor variations across modules
- **Import boundaries erode** — the AI takes the shortest path, not the architecturally correct one

This is architectural drift. Your codebase compiles, tests pass, but the structural coherence degrades with every session.

## Why Tests Don't Catch It

Tests verify **behavior**: does this function return the right value? Does this endpoint respond correctly?

Architectural drift isn't a behavior problem — it's a **structural** problem:

| What tests catch | What drift catches |
|---|---|
| Wrong return values | Same concern solved 4 different ways |
| Missing error handling | Inconsistent error handling across modules |
| Broken API contracts | Layer boundaries violated through imports |
| Regression bugs | Near-duplicate code accumulating silently |

You can have 100% test coverage and still have severe architectural drift. The code works today — but every change tomorrow requires understanding four different patterns instead of one.

## Symptoms You Already Know

If you've worked on an AI-assisted codebase for more than a few sprints, you've seen these:

1. **"Why is this done differently here?"** — Pattern fragmentation across modules
2. **"I fixed this, but the same bug exists in three other places"** — Mutant duplicates that diverged
3. **"This import shouldn't be here"** — Architecture violations from AI taking shortcuts
4. **"Nobody knows which approach is canonical"** — No single source of truth for common patterns
5. **"The PR is green, but I don't trust it"** — Structural complexity that static analysis misses

## How Drift Detects It

[Drift](https://github.com/mick-gsk/drift) is a quality control layer for AI-generated Python code. It operates across file boundaries — analyzing AST structure and git history to surface structural degradation that single-file tools miss.

```bash
pip install drift-analyzer
drift analyze --repo .
```

24 signals detect specific structural problems:

- **Pattern Fragmentation (PFS)** — the same concern handled inconsistently across modules
- **Architecture Violations (AVS)** — layer boundaries eroded through forbidden imports
- **Mutant Duplicates (MDS)** — AST-level near-clones that diverged across files
- **Explainability Deficit (EDS)** — complex code without proportional documentation
- **Temporal Volatility (TVS)** — files that change together but aren't co-located
- And 19 more signals covering structural debt, naming, testing, security patterns

Each finding includes a file location, severity score, and a **concrete next step** — not just "there's a problem" but "here's what to do about it."

## No LLM in the Pipeline

Drift is **deterministic**. Same repository, same commit, same results — every time. No cloud calls, no API keys, no probabilistic output. This is critical for CI gates and team trust.

## How Teams Use It

**In CI** — Block PRs that introduce new structural problems:
```yaml
- uses: mick-gsk/drift@main
  with:
    fail-on: high
    comment: true
```

**In your editor** — MCP integration for Copilot, Cursor, and Claude:
```bash
drift init --mcp
```

**For trend tracking** — Monitor structural health over time:
```bash
drift trend --repo .
```

## Get Started

- [Install drift](getting-started/quickstart.md) — first findings in 2 minutes
- [Example findings](product/example-findings.md) — see what drift detects, with code
- [Trust & evidence](trust-evidence.md) — precision benchmarks, methodology, limitations
- [Case studies](case-studies/index.md) — FastAPI, Pydantic, Django, Paramiko
