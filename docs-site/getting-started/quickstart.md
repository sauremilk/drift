# Quick Start

> Repo: `mick-gsk/drift` · Package: `drift-analyzer` · Command: `drift`

You want to try drift? Good — you'll have your first findings in two minutes.

If you want to see what drift catches before you install it, check out [Problems Every Vibe-Coder Recognizes](vibe-coding-problems.md) — real code examples from AI-assisted projects.

## 0. Before you start

```bash
python --version
```

Drift requires Python 3.11+. If your shell or CI runner is still on 3.10, fix that first — you want the first run to be a signal test, not an environment fight.

## 1. Install

```bash
pip install -q drift-analyzer    # requires Python 3.11+ (use -q for clean output)
```

!!! tip "One command to get started"
    Not sure where to begin? Run `drift start` - it prints the recommended
    first-run sequence for your repository.

!!! tip "No project handy? Try on FastAPI"
    ```bash
    git clone --depth 50 https://github.com/tiangolo/fastapi /tmp/fastapi
    drift analyze --repo /tmp/fastapi
    ```
    Real findings on a real codebase — no setup, no risk.

## 2. See your health at a glance

```bash
cd /path/to/your/project
drift status
```

`drift status` gives you a traffic-light summary with plain-language explanations and copy-paste prompts for your AI assistant. This is the fastest way to understand what drift sees.

!!! note "Two scoring models, two purposes"
    **`drift status`** uses a traffic-light model on the **overall repo score**: 🟢 GREEN (< 0.35), 🟡 YELLOW (0.35–0.65), 🔴 RED (≥ 0.65). This is a quick health check.

    **`drift analyze`** uses severity levels on **individual findings**: INFO (< 0.20), LOW (≥ 0.20), MEDIUM (≥ 0.40), HIGH (≥ 0.60), CRITICAL (≥ 0.80). These are per-finding confidence levels, not repo health.

    Both use the same underlying scores — they just slice them differently. Use `status` for daily overview, `analyze` for finding-level triage.

## 3. Dive into full findings

```bash
drift analyze --repo .
```

## 4. Turn findings into repair tasks

```bash
drift fix-plan --repo . --max-tasks 5
```

`fix-plan` turns your top findings into concrete, ordered tasks with constraints and success criteria.

## 5. What you'll see

Here's what a typical first run looks like:

```text
╭─ drift analyze  myproject/ ──────────────────────────────────────────────────╮
│  DRIFT SCORE  0.52  │  87 files  │  412 functions  │  AI: 34%  │  2.1s      │
╰──────────────────────────────────────────────────────────────────────────────╯

┌──┬────────┬───────┬──────────────────────────────────────┬──────────────────────┐
│  │ Signal │ Score │ Title                                │ Location             │
├──┼────────┼───────┼──────────────────────────────────────┼──────────────────────┤
│◉ │ PFS    │  0.85 │ Error handling split 4 ways          │ src/api/routes.py:42 │
│◉ │ AVS    │  0.72 │ DB import in API layer               │ src/api/auth.py:18   │
│○ │ MDS    │  0.61 │ 3 near-identical validators          │ src/utils/valid.py   │
└──┴────────┴───────┴──────────────────────────────────────┴──────────────────────┘
```

!!! info "Three numbers, three meanings"
    **Drift Score (header):** Overall repository coherence — higher means more structural erosion. This is an orientation metric, not a pass/fail threshold.

    **Finding Score (table column):** Confidence that this specific finding is a real structural issue. ≥ 0.7 = strong signal, 0.4–0.7 = moderate, < 0.4 = weak.

    **Precision claim (site-wide):** Historical accuracy of drift findings across the benchmark corpus. Currently 77% strict / 95% lenient on the v0.5 baseline. This describes methodology accuracy, not a per-repo promise.

### Severity thresholds

Drift maps finding scores to severity levels. These thresholds determine what `--fail-on` blocks:

| Score | Severity | Grade | Meaning |
|-------|----------|-------|---------|
| ≥ 0.80 | **CRITICAL** | F | Critical structural erosion — fix before shipping |
| ≥ 0.60 | **HIGH** | D | Significant drift — address in current cycle |
| ≥ 0.40 | **MEDIUM** | C | Moderate drift — monitor, fix when touching that module |
| ≥ 0.20 | **LOW** | B | Minor signal — informational |
| < 0.20 | **INFO** | A | Negligible — healthy |

Example: `drift check --fail-on high` exits non-zero when any finding scores ≥ 0.60.

!!! tip "Understand a specific signal"
    ```bash
    drift explain PFS   # Shows detection logic, examples, and fix guidance
    ```
    Run this on whichever signal code appears in your highest-scored finding.

## 6. How to read your first findings

My recommendation: start with the highest-scored findings and check if they match what already felt expensive to maintain.

- **Score ≥ 0.7** → strong signal, likely a real structural issue worth investigating
- **Score 0.4–0.7** → moderate signal, review when you touch that module
- **Score < 0.4** → weak signal, likely noise in small repos — skip for now

Each finding links to a specific file and line. Start with the highest-scored findings and check if the pattern matches your understanding of the codebase.

Typical first-run decisions:

- **You see repeated pattern variants in one module** → standardize on one implementation shape before adding more features there.
- **You see a boundary violation at a stable layer edge** → add or tighten an architecture rule before it spreads.
- **You mostly see weak findings in a small repo** → keep drift in observation mode and revisit after the codebase grows.

!!! warning "Finding looks wrong?"
    Two options:

    1. **Suppress locally:** Add `# drift:context deliberate-variant` above the flagged line
    2. **Report it:** [30-second false-positive report](https://github.com/mick-gsk/drift/issues/new?template=false-positive.yml) — helps improve the next release

    False positives are expected on first runs. Drift improves with every report.

## 7. Add a safe CI gate

Start in report-only mode so teams can build trust before blocking merges:

```bash
drift check --fail-on none
```

When the output is stable for your team, tighten to:

```bash
drift check --fail-on high
```

## 8. Verify your installation

Drift can analyze its own codebase — useful to confirm everything works:

```bash
drift self
```

## Next: add to your workflow

### pre-commit (fastest path)

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/mick-gsk/drift
        rev: v2.9.15
    hooks:
      - id: drift-report          # start report-only, switch to drift-check later
```

### CI (report-only first)

The recommended first step is report-only CI (no build failures):

```bash
drift check --fail-on none    # report findings, never exit 1
```

The GitHub Action now follows the same safe default. Tighten to `high` only after your team has reviewed a few real runs.

See [Team Rollout](team-rollout.md) for the full progressive adoption path, [Integrations](../integrations.md) for CI details, and [Prompts to Try](prompts.md) for copy-paste prompts you can hand to your AI assistant.

## `analyze` vs `check` — when to use which

| | `drift analyze` | `drift check` |
|---|---|---|
| **Purpose** | Full repository scan | Diff-scoped CI gate |
| **Scope** | All files matching include/exclude | Only changed files (`--diff`) |
| **Typical use** | Local exploration, baseline creation | Pull request CI checks |
| **Output** | Rich terminal, JSON, SARIF | Same formats, plus exit code gating |
| **Key flags** | `--path`, `--sort-by`, `--format` | `--fail-on`, `--diff`, `--baseline` |
| **Speed** | Seconds to minutes (depends on repo size) | Typically < 10 seconds |

**Rule of thumb:** Use `analyze` when you want a complete picture. Use `check` when you want a fast CI gate on changed code.

## Other commands

Advanced commands beyond the default first-run journey (`analyze` -> `fix-plan` -> `check`):

```bash
# Machine-readable JSON
drift analyze --format json

# GitHub Code Scanning (SARIF)
drift analyze --format sarif

# PR-ready Markdown summary
drift analyze --format pr-comment

# JUnit XML for CI test reporters
drift analyze --format junit

# LLM-oriented output (deprecated, prefer MCP server workflows)
drift analyze --format llm

# Track drift score over time
drift trend --last 90

# Root-cause analysis per module
drift timeline --repo . --since 90
```
