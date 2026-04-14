# Temporal Volatility Signal (TVS)

**Signal ID:** `TVS`  
**Full name:** Temporal Volatility Score  
**Type:** Report-only signal (weight 0.0 — does not contribute to drift score)  
**Default weight:** `0.0`  
**Scope:** git_dependent

---

## What TVS detects

TVS detects files with **abnormal churn relative to their size and role**. It looks for hotspots that keep changing while the surrounding code stays comparatively stable — often a sign of unclear ownership, weak abstractions, or AI-generated code that is being patched repeatedly.

### Minimal code example

Imagine a small helper that should be boring and stable:

```python
# src/utils/normalizer.py

def normalize_email(value: str) -> str:
    return value.strip().lower()
```

If that same helper is edited in commit after commit — one week to trim dots, the next to preserve plus-addresses, then again to patch edge cases — while neighboring modules barely move, TVS treats it as a volatility hotspot. The issue is not that the file changed once; it is that the file keeps absorbing uncertainty.

### Example finding

```
temporal_volatility in src/utils/normalizer.py
  Change frequency: 12 commits in 30 days (z-score: 2.4)
  Unique authors: 5  |  AI-attributed: 60%
  Defect-correlated commits: 3/12
  → Score: 0.72 (HIGH)
```

This points to a small file that is being revisited disproportionately often compared with the rest of the repository.

---

## Why temporal volatility matters

- **Hotspots predict future bugs** — files that change frequently and attract bug fixes are likely to continue doing so.
- **Multi-author churn erodes conventions** — each author (human or AI) may apply different patterns.
- **High AI attribution + high churn** = "vibe-coding loop" — rapid AI-generated changes without stabilization.
- **Trend indicator** — TVS findings that persist across scans highlight structurally unstable areas.

---

## How the score is calculated

TVS combines four sub-metrics using z-score normalization:

1. **Change frequency** — commits per 30-day window, compared to repository average.
2. **Author entropy** — Shannon entropy of contributing authors (high entropy = many authors).
3. **Defect correlation** — proportion of commits associated with bug fixes.
4. **AI attribution ratio** — proportion of commits attributed to AI tools.

$$
\text{volatility\_score} = w_1 \cdot z(\text{frequency}) + w_2 \cdot \text{entropy} + w_3 \cdot \text{defect\_ratio} + w_4 \cdot \text{ai\_ratio}
$$

Modules exceeding `volatility_z_threshold` (default: 1.5 standard deviations) are flagged.

**Severity thresholds:**

| Score range | Severity |
|-------------|----------|
| ≥ 0.7       | HIGH     |
| ≥ 0.5       | MEDIUM   |
| ≥ 0.3       | LOW      |
| < 0.3       | INFO     |

---

## How to address TVS findings

1. **Extract the volatile logic behind a stable interface** — if one helper keeps changing, move the unstable rules into a dedicated module with clear boundaries.
2. **Assign ownership** — high author entropy often means no one is really responsible for keeping the file coherent.
3. **Add tests before the next patch** — repeated bug-fix commits usually mean the behavior is still underspecified.
4. **Review AI-generated changes more carefully** — volatile, AI-attributed files deserve extra scrutiny before merge.
5. **Treat TVS as a triage signal** — it tells you where to look first, not that the file is automatically wrong.

---

## Configuration

```yaml
# drift.yaml
weights:
  temporal_volatility: 0.0   # report-only (set > 0.0 to make scoring-active)

thresholds:
  volatility_z_threshold: 1.5   # z-score threshold for flagging
  recency_days: 14              # focus window for recent activity
```

TVS is report-only by default because it requires git history and its precision/recall have not yet been validated across diverse repositories. Set weight > 0.0 to include TVS in the drift score.

---

## Detection details

1. **Load git history** — parse commits from the last `since` days (default: 90).
2. **Build file histories** — per-file commit counts, author lists, AI attribution.
3. **Compute per-module metrics** — aggregate file-level metrics to directory level.
4. **Z-score normalization** — compare each module to the repository-wide distribution.
5. **Flag outliers** — modules exceeding the z-score threshold.

TVS **requires git history** (`git_dependent=True`). Without access to a git repository, TVS produces no findings.

---

## Related signals

- **CCC (Co-Change Coupling)** — detects files that change together. TVS identifies volatile individual modules; CCC identifies coupled pairs.
- **ECM (Exception Contract Drift)** — also git-dependent, tracking behavioral changes across commits.
- **SMS (System Misalignment)** — detects convention violations. Volatile modules (TVS) are more likely to contain misaligned code (SMS).
