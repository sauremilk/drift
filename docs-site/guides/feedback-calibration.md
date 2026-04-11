# Feedback & Calibration Guide

Drift includes a **Bayesian learning model** that adjusts signal weights based on your feedback. Over time, drift learns which signals are accurate for *your* codebase and which produce false positives — automatically tuning detection to your context.

## How it works

Drift uses three evidence sources to calibrate signal weights:

```
                    ┌──────────────────┐
                    │  Default Weights  │
                    │  (ablation study) │
                    └────────┬─────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
   ┌─────▼──────┐    ┌──────▼──────┐    ┌──────▼──────┐
   │   Manual    │    │    Git      │    │   GitHub    │
   │  Feedback   │    │ Correlation │    │  Correlation│
   │  (CLI/API)  │    │ (auto)      │    │  (auto)     │
   └─────┬──────┘    └──────┬──────┘    └──────┬──────┘
         │                   │                   │
         └───────────────────┼───────────────────┘
                             │
                    ┌────────▼─────────┐
                    │  Bayesian Engine  │
                    │  build_profile()  │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │ Calibrated Weights│
                    │   (per-repo)      │
                    └──────────────────┘
```

### Evidence source 1: Manual feedback

You mark findings as true positive (TP), false positive (FP), or false negative (FN):

```bash
# This finding is real — I fixed it
drift feedback mark --mark tp --signal PFS --file src/core/handler.py

# This is a false alarm — intentional pattern
drift feedback mark --mark fp --signal AVS --file src/api/routes.py \
    --reason "Allowed cross-layer import by design"

# Drift missed this problem entirely
drift feedback mark --mark fn --signal MDS --file src/utils/helpers.py
```

### Evidence source 2: Git correlation (automatic)

Drift correlates historical findings with subsequent defect-fix commits. If a file flagged by a signal later receives a bugfix commit (matching patterns like `fix:`, `bug`, `hotfix`, `revert`), that counts as automatic TP evidence.

If no defect-fix appears within a configurable window (default 60 days), that counts as weak FP evidence.

### Evidence source 3: GitHub issue correlation (automatic)

When a GitHub token is configured, drift correlates closed bug-labeled issues with the files changed in their fixing PRs. If a signal flagged those files, it gains TP evidence. If no signal flagged buggy files, those signals gain FN evidence.

## The Bayesian formula

For each signal, drift computes calibrated weights using confidence-gated Bayesian interpolation:

$$
\text{confidence} = \min\left(1.0,\ \frac{TP + FP}{\text{min\_samples}}\right)
$$

$$
\text{precision} = \frac{TP}{TP + FP}
$$

$$
w_{\text{calibrated}} = (1 - \text{confidence}) \times w_{\text{default}} + \text{confidence} \times w_{\text{default}} \times \text{precision}
$$

**In plain language:**

- With few observations → weight stays close to the default (conservative)
- With many observations and high precision → weight stays high
- With many observations but low precision → weight drops (signal has too many false positives)
- A safety floor prevents any signal from being fully suppressed (minimum 0.001)

### FN boost

If a signal has false negatives (missed real problems), drift can boost its weight:

$$
w_{\text{calibrated}} \mathrel{+}= w_{\text{default}} \times \text{fn\_boost\_factor} \times \frac{FN}{TP + FN} \times \text{confidence}
$$

## Quick start

### 1. Enable calibration

```yaml
# drift.yaml
calibration:
  enabled: true
```

### 2. Run analysis and review findings

```bash
drift analyze --repo .
```

### 3. Mark findings as you review them

```bash
# Real problem — true positive
drift feedback mark -m tp -s PFS -f src/core/handler.py

# False alarm — false positive
drift feedback mark -m fp -s AVS -f src/api/routes.py --reason "Intentional"

# Missed problem — false negative
drift feedback mark -m fn -s MDS -f src/utils/helpers.py
```

### 4. Check feedback summary

```bash
drift feedback summary
```

Output shows TP/FP/FN counts, precision, recall, and F1 per signal.

### 5. Run calibration

```bash
# Preview changes without applying
drift calibrate run --dry-run

# Apply calibrated weights to drift.yaml
drift calibrate run

# See detailed evidence per signal
drift calibrate explain
```

### 6. Verify calibration status

```bash
drift calibrate status
```

## Auto-calibration

Enable continuous calibration — weights are recomputed on every `drift analyze` run:

```yaml
calibration:
  enabled: true
  auto_recalibrate: true
```

## GitHub correlation setup

For automatic issue↔finding correlation:

```yaml
calibration:
  enabled: true
  github_token: null  # Or set DRIFT_GITHUB_TOKEN env var
  bug_labels:
    - bug
    - regression
    - defect
```

## Import existing feedback

If you have prior feedback data (e.g., from another system), import it:

```bash
drift feedback import /path/to/prior_feedback.jsonl
```

Format: one JSON object per line with fields `signal_type`, `file_path`, `verdict` (`tp`/`fp`/`fn`).

## Calibration lifecycle

```
Week 1:  drift analyze → review findings → mark TP/FP → calibrate run
Week 2:  drift analyze (auto-recalibrate) → fewer false alarms
Week 4:  confidence reaches 100% for active signals
Week 8:  Git correlation adds automatic evidence
Week 12: GitHub correlation enriches the profile further
```

After ~20 observations per signal (configurable via `min_samples`), confidence reaches 100% and your repo has a fully calibrated detection profile.

## Reset calibration

To revert to default weights:

```bash
drift calibrate reset
```

## Configuration reference

| Field | Default | Description |
|-------|---------|-------------|
| `calibration.enabled` | `false` | Master switch |
| `calibration.min_samples` | `20` | Observations for full confidence |
| `calibration.correlation_window_days` | `30` | Days to look for defect-fix commits |
| `calibration.decay_days` | `90` | Stale profile threshold |
| `calibration.weak_fp_window_days` | `60` | No fix in window → weak FP |
| `calibration.fn_boost_factor` | `0.1` | FN boost strength (0.0–1.0) |
| `calibration.auto_recalibrate` | `false` | Auto-calibrate on each analyze |
| `calibration.github_token` | `null` | GitHub API token |
| `calibration.bug_labels` | `["bug", "regression", "defect"]` | Bug issue labels |
| `calibration.feedback_path` | `".drift/feedback.jsonl"` | Feedback storage |
| `calibration.history_dir` | `".drift/history"` | Scan history snapshots |
| `calibration.max_snapshots` | `20` | Max retained snapshots |

## Storage

| File | Purpose |
|------|---------|
| `.drift/feedback.jsonl` | Append-only feedback log (TP/FP/FN verdicts) |
| `.drift/history/scan_*.json` | Historical scan snapshots for outcome correlation |
| `.drift/history/calibration_profile.json` | Computed calibration profile |

All paths are relative to repository root and configurable in `drift.yaml`.
