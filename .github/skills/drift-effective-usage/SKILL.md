---
name: drift-effective-usage
description: "Practical workflow for effective use of the drift analyzer. Use when users ask how to run drift, configure scope, interpret findings, reduce false positives, use the drift MCP server, or integrate drift into CI and daily dev workflows."
---

# Drift Effective Usage Skill

## Purpose

Help users get high-value, reproducible, and actionable results from drift quickly.
Focus on trust first: traceable findings, reproducibility, and clear next actions.

## When to Use

- User asks how to use drift effectively
- User wants a reliable first run on a new repository
- User asks how to interpret findings and prioritize fixes
- User wants fewer false positives or clearer output
- User wants to use drift via MCP in VS Code or Copilot agent workflows
- User wants to add drift to CI or team workflows

## Core Principles

Apply this priority order when giving guidance:

1. Credibility of findings
2. Signal precision
3. Clarity of explanation
4. FP/FN reduction
5. Adoption friction
6. Trend tracking
7. Extra features

Never optimize for more output if it does not improve decisions.

## Effective Workflow

### Step 1: Fast and Clean First Run

Use a minimal command that is easy to reproduce:

```bash
drift analyze --repo . --format json --exit-zero
```

Goal:
- confirm the tool runs
- capture machine-readable baseline output
- avoid failing pipelines during initial onboarding

### Step 2: Scope Hygiene

Avoid noisy non-operational paths where possible (for example docs, generated files, fixtures, site outputs).
Recommend using config-based excludes so runs stay deterministic across environments.

### Step 3: Read Findings for Actionability

For each important finding, verify:

- technical traceability (file/line or equivalent anchor)
- reproducibility (same input -> same finding)
- clear cause attribution
- understandable rationale
- concrete next action

If one element is missing, treat the finding as incomplete before prioritizing implementation work.

### Step 4: Prioritize Fixes

Start with findings that combine:

- high confidence
- clear architectural impact
- low-to-medium remediation cost

Defer low-confidence noise until scope/config issues are cleaned up.

### Step 5: Iterate With Evidence

After changes, rerun drift and compare:

- total finding count
- severity distribution
- module-level patterns
- recurring categories over time

Prefer small, measurable loops over broad refactors.

## Command Patterns

Use these patterns in recommendations:

```bash
# Baseline scan for automation
drift analyze --repo . --format json --exit-zero

# Human-readable local review
drift analyze --repo .

# CI-friendly gate (project decides strictness)
drift check --repo .
```

If strict CI gating causes rollout friction, start in report-only mode and tighten later.

## MCP Server Usage (VS Code / Copilot)

Use this when users want agent-native drift analysis in editor workflows.

### Install MCP Extras

```bash
pip install drift-analyzer[mcp]
```

### Start or Inspect MCP Modes

```bash
# Start MCP stdio server
drift mcp --serve

# List available tools without starting server
drift mcp --list

# Print MCP parameter schema as JSON
drift mcp --schema
```

Notes:
- `--serve` uses stdio transport (no network listener)
- interactive terminal start can be blocked; use `--allow-tty` only for manual debugging
- use exactly one mode at a time (`--serve` or `--list` or `--schema`)

### VS Code Registration Example

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

### Recommended MCP Tool Order

1. `drift_validate` before first analysis (preflight)
2. `drift_brief` before implementation tasks
3. `drift_scan` for repository baseline
4. `drift_diff` after changes for regression checks
5. `drift_fix_plan` for prioritized remediation steps
6. `drift_explain` for unfamiliar signal interpretation

This sequence improves reliability and keeps agent actions policy-aligned.

### Optimized Fix-Loop (Session-Based)

For multi-finding fix workflows, use sessions to eliminate redundant scans:

```
# 1. Single call replaces validate + brief + scan + fix_plan
drift_session_start(path=".", autopilot=true)

# 2. Fix first task, then check with nudge (fast, ~0.2s)
drift_nudge(session_id="<sid>", changed_files="src/foo.py")

# 3. Get next task (always max_tasks=1 to keep responses small)
drift_fix_plan(session_id="<sid>", max_tasks=1)

# 4. After all tasks: verify once
drift_diff(session_id="<sid>", uncommitted=true)
```

Key rules:
- Always pass `session_id` to every subsequent tool call
- Use `nudge` (not `scan`) as inner-loop feedback after each edit
- Use `max_tasks=1` in fix_plan to reduce response size
- Follow `agent_instruction` and `next_tool_call` fields in responses
- Run `drift_diff` only as final verification, not after every edit

See `.github/prompts/drift-fix-loop.prompt.md` for the detailed workflow.

## False Positive Reduction Playbook

1. Confirm repository scope and excludes
2. Re-run on a narrowed target path when debugging
3. Check whether the same finding recurs consistently
4. Validate against real architecture intent, not naming alone
5. Encode stable conventions in config/tests where possible

## Recommended Response Pattern

When assisting users, structure answers in this order:

1. Short diagnosis of current usage problem
2. Smallest next command to run
3. How to interpret expected output
4. One concrete follow-up action
5. Optional hardening step for CI/trend tracking

## Guardrails

- Do not suggest cosmetic output changes as primary solution
- Do not recommend broad feature work before trust/reproducibility is stable
- Do not claim precision improvements without empirical evidence
- Keep advice reproducible with explicit commands and expected outcomes

## Ready-to-Use Mini Template

```markdown
Current issue: [one sentence]
Run now: `drift analyze --repo . --format json --exit-zero`
Check in output: [2-3 concrete fields/findings]
Next action: [single highest-value change]
Then verify with: [exact rerun command]
```
