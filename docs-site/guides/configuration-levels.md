# Configuration Levels

Drift works out of the box — no config needed. As your needs grow, unlock
more control one level at a time.

## Level 0 — Zero Config

```bash
pip install drift-analyzer
drift analyze .
```

Drift discovers Python files, runs all 24 signals with default weights,
and prints a Rich terminal report. No `drift.yaml` required.

**When to stay here:** You want a quick health check on a new repo.

---

## Level 1 — Built-in Preset

```yaml
# drift.yaml
extends: quick        # or: vibe-coding, strict, fastapi, library, monorepo
```

Presets tune signal weights, thresholds, and output language for common
scenarios. Run `drift preset list` to see all available presets, or
`drift preset show quick` for a full diff against defaults.

| Preset | Focus |
|--------|-------|
| `quick` | Fast first scan — disables expensive git signals, limits file discovery |
| `vibe-coding` | Guided mode with German output, relaxed thresholds |
| `strict` | Tighter thresholds for mature codebases |
| `fastapi` | Tuned for FastAPI/Starlette projects |
| `library` | Emphasis on API surface stability |
| `monorepo` | Larger file limits, module-aware grouping |

**When to move here:** You want faster scans (`quick`) or domain-specific
defaults (`fastapi`, `library`).

---

## Level 2 — Custom `drift.yaml`

```yaml
# drift.yaml
extends: strict

include:
  - "src/**"

exclude:
  - "**/generated/**"
  - "**/migrations/**"

signals:
  pattern_fragmentation:
    weight: 0.30             # increase importance
  temporal_volatility:
    weight: 0.0              # disable completely

scoring:
  min_function_loc: 10
  similarity_threshold: 0.80
```

Override any preset value. Only the keys you set change — the rest
inherits from the preset (or defaults).

**When to move here:** You want to suppress noisy signals, adjust
weights, or scope the scan to specific directories.

---

## Level 3 — Feedback & Calibration

```bash
# Mark a finding as false positive
drift feedback --finding-id PFS-src/utils.py:42 --label fp

# Run calibration cycle — tunes weights from accumulated feedback
drift calibrate
```

Drift tracks TP/FP labels in `.drift/feedback.jsonl` and reweights
signals via Bayesian calibration. Git-outcome correlation and GitHub
label correlation further refine weights automatically.

**When to move here:** You've triaged a few dozen findings and want
the signal weights to learn from your judgement.

---

## Level 4 — MCP Agent Session

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

The MCP server exposes 13 tools for real-time agent integration:

| Phase | Tool | Purpose |
|-------|------|---------|
| **Plan** | `drift_brief` | Scope-aware guardrails before code generation |
| **Code** | `drift_nudge` | Fast `safe_to_commit` check after each edit (~0.2 s) |
| **Verify** | `drift_diff` | Full before/after comparison before push |
| **Learn** | `drift_feedback` | TP/FP labels that calibrate signal weights |

The agent runs a full session loop: `session_start → nudge → diff →
session_end`. Session state persists across tool calls.

**When to move here:** Your AI coding agent (Cursor, Claude Code,
Copilot) should enforce structural constraints autonomously.

---

## Level 5 — CI/CD Pipeline

```yaml
# .github/workflows/drift.yml
- uses: mick-gsk/drift@v1
  with:
    fail-on: none          # start report-only
    upload-sarif: "true"   # PR annotations
    comment: "true"        # summary comment
```

Outputs `drift-score`, `grade`, `severity`, `finding-count`, and
`badge-svg` for downstream steps.

**When to move here:** You want every PR reviewed for structural
coherence — automatically.

---

## Summary

| Level | Config | Effort | Control |
|:-----:|--------|:------:|:-------:|
| 0 | None | Zero | Defaults |
| 1 | `extends: preset` | 1 line | Preset defaults |
| 2 | `drift.yaml` | Minutes | Full signal/weight control |
| 3 | Feedback + calibrate | Ongoing | Weights learn from your judgement |
| 4 | MCP server | JSON block | Real-time agent integration |
| 5 | GitHub Action | Workflow file | Automated PR gate |

Each level builds on the previous one. Start at Level 0 and move up
only when you need more control.
