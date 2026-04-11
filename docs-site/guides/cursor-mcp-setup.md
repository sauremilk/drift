# Drift in Cursor — MCP Setup Guide

Drift provides a Model Context Protocol (MCP) server that gives Cursor's AI agent direct access to architectural analysis tools. Instead of copy-pasting CLI output, the agent can scan your repository, plan fixes, and verify changes — all within a single chat session.

## Prerequisites

Install drift with MCP extras:

```bash
pip install drift-analyzer[mcp]
```

Verify the server starts:

```bash
drift mcp --serve
```

Press ++ctrl+c++ to stop.

## Quick setup

### Option A: Auto-generate config

Run from your project root:

```bash
drift init --mcp
```

This creates `.cursor/mcp.json` (or `.vscode/mcp.json`) with the correct launcher path. Drift auto-detects whether the `drift` console script is on PATH and falls back to `python -m drift` if needed.

!!! tip "Cursor reads `.vscode/mcp.json` too"
    Cursor supports both `.cursor/mcp.json` and `.vscode/mcp.json`. If your team also uses VS Code, a single `.vscode/mcp.json` works for both editors.

### Option B: Manual config

Create `.cursor/mcp.json` in your project root:

```json
{
  "mcpServers": {
    "drift": {
      "type": "stdio",
      "command": "drift",
      "args": ["mcp", "--serve"]
    }
  }
}
```

Or for global availability across all projects, create `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "drift": {
      "type": "stdio",
      "command": "drift",
      "args": ["mcp", "--serve"]
    }
  }
}
```

!!! note "Virtual environments"
    If drift is installed in a virtual environment, use the full path to the Python interpreter:

    ```json
    {
      "mcpServers": {
        "drift": {
          "type": "stdio",
          "command": "${workspaceFolder}/.venv/bin/python",
          "args": ["-m", "drift", "mcp", "--serve"]
        }
      }
    }
    ```

    On Windows, use `.venv/Scripts/python.exe` instead.

## Verify the connection

1. Open Cursor and load your project
2. Open the Agent chat (++cmd+i++ / ++ctrl+i++)
3. Check that **drift** appears under "Available Tools" in Cursor Settings → MCP
4. Ask: *"Scan this repository for architectural drift"*

The agent should call `drift_scan` and return findings directly in the chat.

## Available MCP tools

Drift exposes 12 tools through MCP. Cursor's agent discovers and uses them automatically.

### Analysis tools

| Tool | Description |
|------|-------------|
| `drift_scan` | Full repository architectural analysis — returns findings, scores, and severity |
| `drift_diff` | Incremental analysis of changed files — ideal for pre-commit checks |
| `drift_validate` | Verify config and environment readiness before running analysis |
| `drift_brief` | Get a structural briefing with scope-aware guardrails before starting work |
| `drift_explain` | Explain unfamiliar findings or signals in detail |
| `drift_negative_context` | Get anti-patterns to avoid when writing new code |

### Repair tools

| Tool | Description |
|------|-------------|
| `drift_fix_plan` | Get prioritized, actionable repair tasks with constraints |
| `drift_nudge` | Fast directional feedback after a file edit (~0.2 s response) |

### Session management

| Tool | Description |
|------|-------------|
| `drift_session_start` | Start a tracked session — with `autopilot=true`, runs validate → brief → scan → fix_plan in one call |
| `drift_session_status` | Check current session state, progress, and KPIs |
| `drift_session_update` | Update session scope or configuration mid-flight |
| `drift_session_end` | End session with summary and cleanup |

## Workflow examples

### Quick scan

Ask the agent:

> "Scan this repo for architectural drift and summarize the top issues."

The agent calls `drift_scan` and presents findings grouped by severity.

### Fix loop

For iterative repair, tell the agent:

> "Start a drift session, fix the highest-priority finding, and verify the fix."

The agent will:

1. Call `drift_session_start(autopilot=true)` — runs full analysis and returns a fix plan
2. Edit the file to fix the top finding
3. Call `drift_nudge` for instant feedback on whether the fix improved or degraded coherence
4. Repeat until findings are resolved

### Pre-commit check

> "Check if my staged changes introduce architectural drift."

The agent calls `drift_diff` targeting only changed files.

### Negative context for new code

> "I'm about to add a new service module. What anti-patterns should I avoid?"

The agent calls `drift_negative_context` to get patterns that would trigger drift findings in your specific codebase.

## Configuration

Drift reads `drift.yaml` from your project root for analysis configuration (signals, thresholds, scope). The MCP server inherits this config automatically.

See [Configuration](../getting-started/configuration.md) for all options.

## Troubleshooting

### Server not appearing in Cursor

- Verify `drift mcp --serve` works in your terminal
- Check that the `command` path in `mcp.json` is correct — use full paths for virtual environments
- Restart Cursor after adding or changing `mcp.json`

### Tools not showing up

- Ensure `drift-analyzer[mcp]` is installed (not just `drift-analyzer`)
- Run `drift mcp --list` to verify the tool catalog loads correctly

### Slow responses

- First scan of a large repo may take a few seconds due to AST parsing and git history analysis
- Subsequent calls within the same session are faster
- Use `drift_nudge` instead of `drift_scan` for quick feedback during iterative fixes

### Windows path issues

- Use forward slashes or escaped backslashes in `mcp.json`
- Cursor supports `${workspaceFolder}` interpolation for portable configs

## Next steps

- [Integrations overview](../integrations.md) — all integration surfaces
- [Agent Workflow](../getting-started/prompts.md) — prompt templates for AI assistants
- [Negative Context for Agents](negative-context-agents.md) — teach your agent what to avoid
- [Feedback & Calibration](feedback-calibration.md) — tune drift to your codebase
