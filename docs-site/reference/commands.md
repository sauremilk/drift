# CLI Command Reference

Complete reference for all `drift` CLI commands. Install with `pip install drift-analyzer`.

---

## Core Analysis

### `drift analyze`

Full repository analysis — the primary entry point.

```bash
drift analyze --repo . --format json --fail-on high
drift analyze --select PFS,AVS --max-findings 10 --since 180
```

| Option | Default | Description |
|--------|---------|-------------|
| `--repo, -r` | `.` | Repository root path |
| `--path, -p` | — | Restrict to subdirectory |
| `--since, -s` | `90` | Days of git history |
| `--format, -f` | `rich` | `rich`, `json`, `sarif`, `csv`, `markdown`, `agent-tasks`, `github`, `pr-comment`, `junit`, `llm` |
| `--fail-on` | `none` | Exit 1 if findings exceed: `critical`, `high`, `medium`, `low` |
| `--exit-zero` | — | Always exit 0 |
| `--select` | — | Comma-separated signal IDs (e.g. `PFS,AVS,MDS`) |
| `--ignore` | — | Signal IDs to exclude |
| `--config, -c` | — | Config file path |
| `--workers, -w` | — | Parallel workers for file parsing |
| `--no-embeddings` | — | Disable embedding-based analysis |
| `--sort-by` | `impact` | Sort by `impact` or `score` |
| `--max-findings` | `20` | Maximum findings to display |
| `--show-suppressed` | — | Show `drift:ignore`-suppressed findings |
| `--quiet, -q` | — | Minimal output: score, severity, count only |
| `--no-code` | — | Suppress inline code snippets |
| `--baseline` | — | Filter out known findings from baseline file |
| `--save-baseline` | — | Save current findings as baseline |
| `--output, -o` | — | Write output to file |
| `--json` | — | Shortcut for `--format json` |
| `--compact` | — | Compact JSON for agents/CI |
| `--no-color` | — | Disable colored output |

`--format junit` and `--format llm` are currently supported for compatibility and emit a deprecation warning at runtime.

### `drift status`

Traffic-light health indicator with everyday language. Ideal for non-technical stakeholders and vibe-coders.

```bash
drift status                           # GREEN / YELLOW / RED status
drift status --profile strict --top 5
drift status --json
```

| Option | Default | Description |
|--------|---------|-------------|
| `--repo, -r` | `.` | Repository root |
| `--path, -p` | — | Restrict to subdirectory |
| `--since, -s` | `90` | Days of git history |
| `--profile` | `vibe-coding` | Profile for guided thresholds |
| `--json` | — | JSON output |
| `--top` | `3` | Number of top findings to show |

### `drift check`

CI-mode diff analysis — compare against previous state.

```bash
drift check --fail-on high
drift check --format json --baseline .drift-baseline.json
```

| Option | Default | Description |
|--------|---------|-------------|
| `--repo, -r` | `.` | Repository root |
| `--diff-ref` | `HEAD~1` | Git ref to diff against |
| `--diff-only` | — | Compare against baseline only |
| `--format, -f` | `rich` | Output format |
| `--fail-on` | `none` | Exit 1 threshold |
| `--exit-zero` | — | Always exit 0 |
| `--select` | — | Signal IDs to include |
| `--ignore` | — | Signal IDs to exclude |
| `--baseline` | — | Baseline file path |
| `--output, -o` | — | Write output to file |
| `--quiet, -q` | — | Minimal output |
| `--no-code` | — | Suppress code snippets |

### `drift gate`

Alias for `drift check`.

```bash
drift gate --fail-on high
drift gate --format json
```

Supports the same options and behavior as `drift check`.

### `drift ci`

Zero-config CI command with auto environment detection.

```bash
drift ci
drift ci --fail-on high
drift ci --format sarif -o drift.sarif
```

| Option | Default | Description |
|--------|---------|-------------|
| `--repo, -r` | `.` | Repository root |
| `--fail-on` | `drift.yaml` / `none` | Exit non-zero if findings exceed threshold |
| `--format, -f` | auto | `rich`, `json`, `sarif`, `csv`, `junit`, `github`, `llm` |
| `--baseline` | — | Baseline file path |
| `--output, -o` | — | Write output to file |
| `--exit-zero` | — | Always exit 0 |
| `--diff-ref` | auto | Override base ref for diff analysis |
| `--config, -c` | — | Config file path |
| `--since, -s` | `90` | Days of git history |
| `--quiet, -q` | — | Minimal output |

### `drift start`

Guided first-run path — shows recommended commands for new users.

```bash
drift start
```

No options. Prints the recommended onboarding sequence:

1. `drift analyze --repo .`
2. `drift fix-plan --repo . --max-tasks 5`
3. `drift check --fail-on none`

---

## Agent-Native Commands

JSON-first commands designed for AI coding agents and automation.

### `drift scan`

Agent-native repository scan with structured JSON output.

```bash
drift scan --repo . --max-findings 20
drift scan --select PFS,AVS --strategy top-severity -o findings.json
```

| Option | Default | Description |
|--------|---------|-------------|
| `--repo, -r` | `.` | Repository root |
| `--target-path` | — | Restrict to subdirectory |
| `--since` | `90` | Days of git history |
| `--select` | — | Signal IDs |
| `--exclude-signals` | — | Signal IDs to exclude |
| `--max-findings` | `10` | Maximum findings (1–200) |
| `--max-per-signal` | — | Max findings per signal |
| `--strategy` | `diverse` | `diverse` or `top-severity` |
| `--response-detail` | `concise` | `concise` or `detailed` |
| `--include-non-operational` | — | Include fixture/docs findings |
| `--output, -o` | — | Write JSON to file |

### `drift brief`

Pre-task structural briefing — returns architecture guardrails before you write code.

```bash
drift brief --task "add payment integration to checkout module"
drift brief -t "refactor auth service" --format json --max-guardrails 15
```

| Option | Default | Description |
|--------|---------|-------------|
| `--task, -t` | — | Task description (REQUIRED) |
| `--repo, -r` | `.` | Repository root |
| `--scope` | — | Manual scope override (path or glob) |
| `--format, -f` | `rich` | `rich`, `json`, `markdown` |
| `--max-guardrails` | `10` | Max guardrails (1–50) |
| `--select` | — | Signal IDs |
| `--json` | — | Shortcut for `--format json` |
| `--quiet, -q` | — | Guardrails only |

### `drift diff`

Agent-native change analysis — checks drift impact of recent changes.

```bash
drift diff --uncommitted
drift diff --staged-only --format json
drift diff --target-path src/api --max-findings 20
```

| Option | Default | Description |
|--------|---------|-------------|
| `--repo, -r` | `.` | Repository root |
| `--diff-ref` | `HEAD~1` | Git ref to diff against |
| `--uncommitted` | — | Analyze working-tree changes against HEAD |
| `--staged-only` | — | Analyze only staged changes |
| `--target-path` | — | Restrict to subdirectory |
| `--baseline` | — | Baseline file for comparison |
| `--max-findings` | `10` | Maximum findings |
| `--response-detail` | `concise` | `concise` or `detailed` |
| `--output, -o` | — | Write JSON to file |

### `drift fix-plan`

Prioritized repair plan — returns the highest-impact fixes first.

```bash
drift fix-plan --max-tasks 5
drift fix-plan --signal PFS --automation-fit-min high
drift fix-plan --target-path src/api --max-tasks 10 -o plan.json
```

| Option | Default | Description |
|--------|---------|-------------|
| `--repo, -r` | `.` | Repository root |
| `--finding-id` | — | Target specific finding |
| `--signal` | — | Filter to signal (e.g. `PFS`) |
| `--max-tasks` | `5` | Maximum tasks |
| `--target-path` | — | Restrict to subpath |
| `--exclude` | — | Exclude subpath (repeatable) |
| `--include-deferred` | — | Include deferred findings |
| `--automation-fit-min` | — | Minimum automation fitness: `low`, `medium`, `high` |
| `--output, -o` | — | Write JSON to file |

### `drift validate`

Preflight validation — check config and environment before analysis.

```bash
drift validate
drift validate --baseline .drift-baseline.json
```

| Option | Default | Description |
|--------|---------|-------------|
| `--repo, -r` | `.` | Repository root |
| `--config` | — | Config file path |
| `--baseline` | — | Baseline file for comparison |

### `drift explain`

Signal documentation in the terminal.

```bash
drift explain PFS            # Explain pattern fragmentation
drift explain --all          # All signals
drift explain --tuning       # Weight tuning guide
```

| Option | Default | Description |
|--------|---------|-------------|
| `SIGNAL_NAME` | — | Signal abbreviation (optional) |
| `--all` | — | Show all signals |
| `--json` | — | JSON output |
| `--tuning` | — | Show weight tuning guide |

---

## Calibration & Feedback

Drift includes a **Bayesian learning model** that calibrates signal weights based on your feedback. See the [Feedback & Calibration Guide](../guides/feedback-calibration.md) for the full workflow.

### `drift feedback mark`

Record a finding as true positive (TP), false positive (FP), or false negative (FN).

```bash
drift feedback mark --mark tp --signal PFS --file src/core/handler.py
drift feedback mark --mark fp --signal AVS --file src/api/routes.py --line 42 \
    --reason "Allowed cross-layer import"
```

| Option | Default | Description |
|--------|---------|-------------|
| `--repo, -r` | `.` | Repository root |
| `--mark, -m` | — | `tp`, `fp`, or `fn` (REQUIRED) |
| `--signal, -s` | — | Signal type or abbreviation (REQUIRED) |
| `--file, -f` | — | File path (REQUIRED) |
| `--reason` | — | Reason for verdict |
| `--line, -l` | — | Start line of finding |

### `drift feedback summary`

Show aggregated feedback counts with precision, recall, and F1 per signal.

```bash
drift feedback summary
```

### `drift feedback import`

Import feedback events from an external JSONL file.

```bash
drift feedback import /path/to/prior_feedback.jsonl
```

### `drift calibrate run`

Compute calibrated signal weights from accumulated feedback.

```bash
drift calibrate run                 # Apply to drift.yaml
drift calibrate run --dry-run       # Preview changes
drift calibrate run --format json
```

| Option | Default | Description |
|--------|---------|-------------|
| `--repo, -r` | `.` | Repository root |
| `--dry-run` | — | Preview without writing |
| `--format` | `text` | `text` or `json` |

### `drift calibrate explain`

Show detailed evidence per signal — TP/FP/FN counts and confidence.

```bash
drift calibrate explain
```

### `drift calibrate status`

Show calibration profile status, feedback count, and freshness.

```bash
drift calibrate status
```

### `drift calibrate reset`

Remove calibrated weights and revert to defaults.

```bash
drift calibrate reset
```

---

## Output & Context

### `drift export-context`

Export negative context (anti-patterns) for AI agent consumption.

```bash
drift export-context                          # Preview to stdout
drift export-context --write                  # Write .drift-negative-context.md
drift export-context --format prompt -w -o docs/rules.md
drift export-context --include-positive       # Combined positive + negative
```

| Option | Default | Description |
|--------|---------|-------------|
| `--repo, -r` | `.` | Repository root |
| `--output, -o` | `.drift-negative-context.md` | Output file path |
| `--write, -w` | — | Write to file (default: stdout) |
| `--format` | `instructions` | `instructions`, `prompt`, `raw` |
| `--scope` | — | `file`, `module`, `repo` |
| `--max-items` | `25` | Maximum anti-pattern items |
| `--include-positive` | — | Include positive guidance |

### `drift copilot-context`

Generate Copilot instructions from analysis results.

```bash
drift copilot-context                         # Preview to stdout
drift copilot-context --write                 # Merge into .github/copilot-instructions.md
drift copilot-context -w -o docs/ai.md
```

| Option | Default | Description |
|--------|---------|-------------|
| `--repo, -r` | `.` | Repository root |
| `--output, -o` | `.github/copilot-instructions.md` | Output file |
| `--write, -w` | — | Write/merge into file |
| `--no-merge` | — | Overwrite instead of merge |
| `--format` | `markdown` | `markdown` or `json` |

---

## Metrics & Insights

### `drift precision`

Measure ground-truth precision and recall for all signals.

```bash
drift precision                         # P/R/F1 table
drift precision --signal PFS --json     # Single signal as JSON
drift precision --threshold 0.80        # Exit 1 if any signal F1 < 0.80
```

| Option | Default | Description |
|--------|---------|-------------|
| `--signal` | — | Filter to specific signal |
| `--kind` | — | `positive`, `negative`, `boundary`, `confounder` |
| `--json` | — | JSON output |
| `--threshold` | `0.0` | Min F1; exit 1 if below |

### `drift roi-estimate`

Estimate refactoring effort from current findings.

```bash
drift roi-estimate
drift roi-estimate --format json --top 5
drift roi-estimate --path src/api
```

| Option | Default | Description |
|--------|---------|-------------|
| `--repo, -r` | `.` | Repository root |
| `--path, -p` | — | Restrict to subdirectory |
| `--format` | `rich` | `rich` or `json` |
| `--top` | `3` | Top findings to highlight |

### `drift timeline`

Root-cause analysis — shows when drift began in each module.

```bash
drift timeline
drift timeline --since 180
```

### `drift trend`

Score trend over time.

```bash
drift trend                    # 90-day history
drift trend --last 180         # 180-day history
```

### `drift badge`

Generate a shields.io badge URL for your README.

```bash
drift badge
drift badge --style flat-square -o badge.url
```

| Option | Default | Description |
|--------|---------|-------------|
| `--style` | `flat` | `flat`, `flat-square`, `for-the-badge`, `plastic` |
| `--output, -o` | — | Write badge URL to file |

### `drift patterns`

Display discovered code patterns.

```bash
drift patterns
drift patterns --category error_handling --format json
```

| Option | Default | Description |
|--------|---------|-------------|
| `--category` | — | `error_handling`, `data_access`, `api_endpoint`, `caching`, `logging`, `authentication`, `validation` |
| `--target-path` | — | Restrict to subdirectory |
| `--format, -f` | `rich` | `rich` or `json` |

### `drift self`

Self-analysis — run drift on drift's own codebase (only works inside the drift source repository).

```bash
drift self
drift self --format json -o self_analysis.json
```

---

## Configuration & Setup

### `drift setup`

Interactive guided onboarding — asks 3 questions and generates `drift.yaml`.

```bash
drift setup                    # Interactive
drift setup --non-interactive  # Vibe-coding defaults
drift setup --json             # JSON for agents/CI
```

### `drift completions`

Generate shell tab-completion scripts.

```bash
drift completions bash > ~/.drift-completion.bash
source ~/.drift-completion.bash

drift completions zsh > ~/.zfunc/_drift
drift completions fish > ~/.config/fish/completions/drift.fish
```

| Argument | Description |
|----------|-------------|
| `shell`  | Target shell: `bash`, `zsh`, `fish` |

### `drift config validate`

Validate `drift.yaml` against schema and business rules.

```bash
drift config validate
```

### `drift config show`

Show effective configuration after merging with defaults.

```bash
drift config show
```

---

## Baselines

### `drift baseline save`

Save current findings as a baseline for future comparisons.

```bash
drift baseline save
drift baseline save -o baseline_v2.json
```

### `drift baseline compare`

Compare current findings against a saved baseline.

```bash
drift baseline compare
drift baseline compare --format json -o comparison.json
```

---

## Integration & Deployment

### `drift init`

Scaffold configuration and CI integration files.

```bash
drift init                                    # Interactive
drift init --profile strict --github-actions  # Strict profile + GH Actions
drift init --vscode-mcp                       # Generate .vscode/mcp.json
```

| Option | Default | Description |
|--------|---------|-------------|
| `--profile` | — | `vibe-coding`, `default`, `strict`, `custom` |
| `--github-actions` | — | Generate workflow file |
| `--pre-push-hook` | — | Generate pre-push hook |
| `--vscode-mcp` | — | Generate VS Code MCP config |
| `--no-overwrite` | — | Skip existing files |

### `drift mcp`

Start drift as an MCP (Model Context Protocol) server for VS Code Copilot integration.

```bash
drift mcp --serve               # Start server (stdio transport)
drift mcp --list                # List available tools
drift mcp --schema              # Print tool parameter schema
```

Requires: `pip install drift-analyzer[mcp]`

### `drift serve`

Start an A2A-compatible HTTP server for multi-agent orchestration.

```bash
drift serve --base-url http://localhost:8080
drift serve --base-url https://my-drift.example.com --port 9000
```

| Option | Default | Description |
|--------|---------|-------------|
| `--base-url` | — | Public base URL (REQUIRED) |
| `--host` | `127.0.0.1` | Bind host |
| `--port` | `8080` | Bind port |
| `--reload` | — | Enable auto-reload |

Requires: `pip install drift-analyzer[serve]`
