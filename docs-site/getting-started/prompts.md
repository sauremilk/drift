# Prompts to Try

These prompts work with GitHub Copilot, Cursor, Claude, or any AI coding assistant.
Copy one, paste it into your editor's chat, and see what drift finds in your codebase — no config, no setup beyond `pip install drift-analyzer`.

Not sure what drift even looks for? Check out [Problems Every Vibe-Coder Recognizes](vibe-coding-problems.md) first — real code examples you'll probably recognize from your own projects.

---

## First Look

Start here. One prompt, instant results.

```text
Install drift-analyzer and run `drift analyze --repo .` on this project.
Show me the top 5 findings and explain what each one means for this codebase.
```

```text
Run `drift analyze --repo .` and give me a plain-language summary:
What's the overall drift score? Which areas of the code have the most structural problems?
```

```text
Run `drift brief --repo .` and explain the output.
What should I focus on first?
```

---

## Find Specific Problems

Target a specific signal. Each prompt focuses on one type of structural issue.

### Duplicate code from AI generation

```text
Run `drift analyze --repo . --format json` and look at MDS findings (Mutant Duplicates).
Which functions are near-copies of each other? Show me the pairs and suggest which ones to consolidate.
```

### Architecture boundary violations

```text
Run `drift analyze --repo .` and explain all AVS findings (Architecture Violations).
Which imports cross layer boundaries? Draw a simple diagram of the intended layers vs. what drift found.
```

### Pattern fragmentation

```text
Run `drift analyze --repo .` and focus on PFS findings (Pattern Fragmentation).
Where is the same concern handled in multiple different ways? Which pattern should be the canonical one?
```

### Complex undocumented code

```text
Run `drift analyze --repo .` and check for EDS findings (Explainability Deficit).
Which functions are complex but lack documentation? Prioritize by complexity score.
```

---

## Fix Workflows

Go from findings to fixes. These prompts drive a complete repair loop.

```text
Run `drift fix-plan --repo . --max-tasks 3` and implement the first task from the plan.
Explain what you changed and why. Then re-run `drift analyze --repo .` to confirm the score improved.
```

```text
Run `drift scan --max-findings 5` and pick the highest-impact finding.
Refactor the code to fix it. Show me a before/after diff and explain the structural improvement.
```

```text
Run `drift diff --staged-only` on my staged changes.
Are there any new structural problems? If yes, suggest fixes before I commit.
```

```text
Create a fix plan with `drift fix-plan --repo .` and work through the tasks one by one.
Commit each fix separately with a clear commit message explaining the structural improvement.
```

---

## CI and Workflow Setup

Set up drift in your development workflow — pre-commit, CI, or editor integration.

### Pre-commit hook

```text
Set up drift as a pre-commit hook in this repo using the report-only mode.
Add the config to .pre-commit-config.yaml and test it with a dry run.
```

### GitHub Actions

```text
Create a GitHub Actions workflow file (.github/workflows/drift.yml) that:
1. Runs drift on every pull request
2. Uploads findings as SARIF to GitHub Code Scanning
3. Uses report-only mode (fail-on: none) for now

Use the official drift GitHub Action (mick-gsk/drift@v2).
```

### MCP integration

```text
Run `drift init --mcp` to set up MCP integration for this editor.
Then use the drift tools directly — no more copy-pasting prompts needed.
```

### GitLab CI

```text
Create a .gitlab-ci.yml job that runs drift in report-only mode on merge requests.
Archive the JSON report as a CI artifact.
```

---

## Trend and Baseline

Track architecture health over time.

```text
Run `drift analyze --repo . --format json -o drift-baseline.json` to create a baseline snapshot.
What's the current drift score? Which signals contribute most?
```

```text
Run `drift trend --last 30` and explain the trend.
Is the architecture getting better or worse? Which signals are driving the change?
```

```text
Compare the current drift score against the last baseline.
Run `drift analyze --repo .` and tell me which findings are new since the last snapshot.
```

---

## Vibe-Coding Survival Kit

If your team uses AI assistants heavily, start here for the full workflow.

```text
Copy the vibe-coding config from https://github.com/mick-gsk/drift/tree/main/examples/vibe-coding
into this project's root as drift.yaml. Then:
1. Run `drift validate` to check the config
2. Run `drift analyze --repo .` to get a Day 0 baseline
3. Run `drift fix-plan --repo . --max-tasks 5` and fix the top items
```

```text
Run `drift analyze --repo .` with a focus on AI-specific patterns:
- MDS: Are there duplicate helpers that an AI assistant generated in multiple places?
- PFS: Is the same concern solved differently across files?
- BAT: Are there `# type: ignore` or broad `except Exception` accumulations?
Show me the findings sorted by impact.
```

---

## Copy-Ready Workflow Files

Complete files you can drop into your project. Copy the content, save at the indicated path, done.

### `.github/workflows/drift.yml`

```yaml title=".github/workflows/drift.yml"
name: Drift
on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read
  security-events: write   # only needed if upload-sarif: true

jobs:
  drift:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 50

      - uses: mick-gsk/drift@v2
        with:
          fail-on: none          # report-only — change to 'high' when ready
          upload-sarif: true     # findings appear as PR annotations
```

### `.pre-commit-config.yaml` (add drift hook)

```yaml title=".pre-commit-config.yaml"
repos:
  - repo: https://github.com/mick-gsk/drift
    rev: v2.9.15
    hooks:
      - id: drift-report        # report-only — switch to drift-check later
```

### `.vscode/mcp.json` (MCP for Copilot / Cursor / Windsurf)

```json title=".vscode/mcp.json"
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

> **Shortcut:** `drift init --mcp` generates this file for you.

---

!!! tip "Pro tip: Use MCP instead of prompts"
    If your editor supports [MCP](../integrations.md#mcp-server) (VS Code Copilot, Cursor, Claude Desktop, Windsurf), run `drift init --mcp` once. After that, your AI assistant can call drift tools directly — no prompt copying needed. The prompts above are most useful for quick one-off checks or editors without MCP support.

!!! info "Vibe-coding optimized config"
    The [`examples/vibe-coding/`](https://github.com/mick-gsk/drift/tree/main/examples/vibe-coding) directory contains a pre-tuned `drift.yaml` with signal weights and thresholds optimized for AI-heavy codebases, plus a GitHub Actions workflow, pre-push hook, and MCP config — ready to copy into your project.
