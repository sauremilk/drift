---
name: drift-effective-usage
description: "Minimal workflow for effective use of drift-analyzer. Use when users ask how to run drift, scope scans, interpret findings, reduce noise, track trends, use feedback-based calibration, use the MCP server, or add drift to CI."
---

# Drift Effective Usage

Use this skill to help users adopt drift-analyzer with the smallest reliable workflow.
Prefer reproducible commands, clear scope, and actionable findings over exhaustive output.

## Use When

- User asks how to run drift for the first time
- User wants less noise or fewer false positives
- User asks how to interpret or prioritize findings
- User wants a guided first-run path or score trend over time
- User wants project-specific tuning from TP/FP/FN feedback
- User wants to use direct drift MCP tools in chat or agent workflows
- User wants to add drift to CI without blocking adoption too early

## Default Workflow

### 1. Establish a Baseline

For a guided first run, start with:

```bash
drift start
```

For reproducible automation or onboarding baselines, use:

```bash
drift analyze --repo . --format json --exit-zero
```

Use this first because it is reproducible, machine-readable, and safe for onboarding.
`--exit-zero` keeps the first run non-blocking even when findings exist.

### 2. Clean Up Scope

Exclude non-operational paths such as generated output, docs, build artifacts, and fixtures.
Put those excludes in drift config so local and CI runs behave the same.
If results look noisy, narrow the scan scope before discussing fixes.

### 3. Read Findings for Actionability

Prioritize findings that have:

- a clear file or module anchor
- an understandable cause
- a concrete next step
- repeated or high-confidence occurrence

Treat low-confidence or poorly explained findings as scope or calibration work first.

### 4. Roll Out Gradually

Start with local review, then add report-only CI with `drift analyze --repo . --format json --exit-zero`, then enforce stricter checks once findings are stable.

Use `drift trend --repo .` when the team wants to compare score movement over time instead of treating each scan as isolated.

### 5. Use Feedback When Noise Persists

If the same findings repeatedly turn out to be true positives or false positives, record that evidence and review calibration before changing broad scope rules.

```bash
drift feedback mark --mark fp --signal PFS --file src/example.py --reason "generated code"
drift calibrate run --dry-run
```

Use calibration only after collecting real TP/FP/FN evidence. Start with `--dry-run`.

## Core Commands

```bash
# Guided first-use path
drift start

# Baseline for automation or onboarding
drift analyze --repo . --format json --exit-zero

# Turn findings into concrete next tasks
drift fix-plan --repo . --max-tasks 5

# Human-readable local review
drift analyze --repo .

# Report-only CI rollout
drift check --fail-on none

# Stricter CI once the output is trusted
drift check --fail-on high

# Trend view across multiple snapshots
drift trend --repo .
```

## Optional Features

If users want commit and author provenance on findings, enable attribution in config:

```yaml
attribution:
  enabled: true
```

Use this only when provenance helps triage. It is optional.

## MCP Usage

If the current chat or agent environment already exposes drift MCP tools, use them directly.
Do not start `drift mcp --serve` in a terminal just to call drift tools from the same chat session.

Prefer direct tool calls in chat in this order:

1. `drift_validate`
2. `drift_brief`
3. `drift_scan`
4. `drift_negative_context`
5. `drift_fix_plan`
6. `drift_nudge`
7. `drift_diff`
8. `drift_explain`
9. `drift_feedback`
10. `drift_calibrate`

This order keeps the workflow predictable: validate first, gather context before changes, scan the baseline, use nudge for fast iteration, use diff for verification, and use feedback plus calibration only when signal quality needs tuning.

For repeated remediation work, prefer `drift_session_start` before repeated `drift_nudge` checks.

Only use terminal-based MCP setup when an editor or external MCP client still needs manual server registration.

```bash
pip install drift-analyzer[mcp]
```

Useful inspection commands:

```bash
drift mcp --list
drift mcp --schema
drift mcp --serve
```

If using VS Code:

```json
{
  "servers": {
    "drift": {
      "type": "stdio",
      "command": "drift",
      "args": ["mcp", "--serve"]
    }
  }
}
```

## Response Pattern

When helping a user, answer in this order:

1. State the usage problem in one sentence
2. Give the smallest next command
3. Explain what to look for in the output
4. Give one follow-up action

## Guardrails

- Do not recommend more output unless it improves decisions
- Do not jump to broad refactors before scope is clean
- Do not present low-confidence findings as hard facts
- Keep examples portable and repo-agnostic
