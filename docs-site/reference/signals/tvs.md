# Temporal Volatility Signal (TVS)

**Signal ID:** `TVS`  
**Full name:** Temporal Volatility Score  
**Type:** Report-only signal (weight 0.0 — does not contribute to drift score)  
**Default weight:** `0.0`  
**Scope:** git_dependent

---

## What TVS detects

TVS detects modules with **anomalous change patterns** — unusually high churn, many distinct authors, frequent defect-correlated commits, and high AI attribution. These are "hotspots" where architectural erosion is most likely accelerating.

### Example finding

```
temporal_volatility in src/api/handlers.py
  Change frequency: 12 commits in 30 days (z-score: 2.4)
  Unique authors: 5  |  AI-attributed: 60%
  Defect-correlated commits: 3/12
  → Score: 0.72 (HIGH)
```

A file that changes frequently, by many authors, with high AI involvement and frequent bug-fix follow-ups.

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

1. **Stabilize the module** — reduce churn by completing in-progress refactoring or consolidating competing changes.
2. **Assign ownership** — high author entropy often means no one owns the module. Designate a responsible maintainer.
3. **Review AI-generated changes more carefully** — AI-attributed commits in volatile modules need extra scrutiny.
4. **Split large modules** — if a file attracts changes from many features, it may have too many responsibilities.

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
