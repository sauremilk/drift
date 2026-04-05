# Drift — Vibe-Coding Technical Debt Solution

> **Problem:** AI-generated code (Copilot, Cursor, Claude) ships fast but accumulates
> architectural debt silently — copy-paste patterns replace refactoring, architecture
> boundaries erode, and quality bypasses accumulate unchecked.
>
> **Solution:** drift-analyzer as the single source of truth for structural coherence,
> deployed across the entire developer workflow: IDE → commit → PR → merge → trend.

## Evidence Base (GitClear Data)

| Metric | Pre-AI Baseline | Post-AI Observed | Root Cause |
|--------|----------------|-----------------|------------|
| Refactored/Move lines | ~30% of changes | ~20% of changes | LLMs duplicate rather than refactor |
| Copy-paste lines | ~10% of changes | ~15-25% of changes | Context-window limits prevent cross-file refactoring |
| 14-day code churn | Normal | +40-60% | "Works" ≠ "fits the architecture" |
| Maintenance PR ratio | Stable | Declining | Velocity metrics reward features, not cleanup |

## How drift Solves This

drift detects the **exact patterns** that vibe-coding produces:

| Vibe-Coding Problem | drift Signal | Detection Method |
|---------------------|-------------|-----------------|
| Near-duplicate functions | **MDS** (Mutant Duplicate) | AST Jaccard + embedding similarity |
| Same concern solved N ways | **PFS** (Pattern Fragmentation) | Structural fingerprint grouping |
| Layer boundary violations | **AVS** (Architecture Violation) | Import graph + layer inference |
| Complex code without docs/tests | **EDS** (Explainability Deficit) | Complexity × missing docstring/tests |
| Happy-path-only tests | **TPD** (Test Polarity Deficit) | Positive vs. negative assertion ratio |
| `# type: ignore` / `Any` buildup | **BAT** (Bypass Accumulation) | Quality-bypass marker density |
| Broad `except Exception` | **BEM** (Exception Monoculture) | Uniform error-swallowing detection |
| `validate_*` without raise | **NBV** (Naming Contract) | Name-to-AST contract verification |
| Circular imports between modules | **CIR** (Circular Import) | Import-cycle detection in module graph |
| High-churn files | **TVS** (Temporal Volatility) | Z-score anomaly on 30-day window |
| Hidden coupling | **CCC** (Co-Change Coupling) | Co-change frequency without import |

## Quick Start (5 Minutes)

```bash
# 1. Install
pip install drift-analyzer

# 2. Copy configuration
cp examples/vibe-coding/drift.yaml drift.yaml

# 3. Validate setup
drift validate --config drift.yaml

# 4. Run first analysis (your Day 0 baseline)
drift analyze

# 5. Create baseline for ratchet gate
drift baseline --output .drift-baseline.json
```

## Practical Remediation Loop (triage -> fix -> baseline update)

Use this exact sequence after your first baseline to keep remediation small,
measurable, and repeatable.

1. Capture a Day-0 snapshot (`drift_day0.json`).
2. Triage the top findings (`impact` sort + signal explanation).
3. Create a focused fix queue (`max-tasks 3`).
4. Implement one concrete remediation.
5. Re-run analysis and verify trend direction.
6. Update baseline to lock in the improvement.

```bash
# 1) Snapshot before remediation
drift analyze --repo . --format json -o drift_day0.json

# 2) Triage first
drift analyze --repo . --sort-by impact --max-findings 5
drift explain PFS

# 3) Build a small remediation queue
drift fix-plan --repo . --max-tasks 3

# 4) Apply one fix from the queue

# 5) Verify improvement
drift analyze --repo . --format json -o drift_after_fix.json
drift trend --repo . --last 30

# 6) Update baseline for future delta checks
drift baseline --output .drift-baseline.json
```

Concrete before/after example:

- Before: `PFS` reports fragmented connector error handling as a high-severity finding.
- After: one shared error handler lowers fragmentation and reduces PFS severity in the next scan.

Related docs: [Getting Started](../../docs-site/getting-started/quickstart.md) · [Finding Triage](../../docs-site/getting-started/finding-triage.md) · [Team Rollout](../../docs-site/getting-started/team-rollout.md)

## 30-Day Rollout Plan

### Week 1: Foundation (Day 1–7)

| Day | Action | Command | Verification |
|-----|--------|---------|-------------|
| 1 | Install + initial analysis | `drift analyze -f json -o baseline.json` | Baseline score documented |
| 2 | Apply vibe-coding config | Copy `drift.yaml` to project root | `drift validate` → green |
| 3 | IDE integration (MCP) | Copy `mcp.json` to `.vscode/mcp.json` | `drift_scan` works in IDE |
| 4 | Pre-push hook | Copy `pre-push` to `.git/hooks/` | Push with HIGH finding → blocked |
| 5–7 | Fix top-5 MDS/PFS findings | `drift fix-plan --max-tasks 5` | Score decreases |

### Week 2: CI Gate (Day 8–14)

| Day | Action | Command | Verification |
|-----|--------|---------|-------------|
| 8 | Add GitHub Action (report-only) | Copy `drift-gate.yml` to `.github/workflows/` | PR shows drift comment |
| 9 | Enable SARIF upload | Set `upload-sarif: "true"` in workflow | Inline annotations in PR |
| 10 | Enable delta gate | Uncomment `fail_on_delta` in `drift.yaml` | Score regression >5% → blocks |
| 11–14 | Fix top-10 findings | `drift fix-plan --max-tasks 10` | `drift trend` shows ↓ |

### Week 3: Enforcement (Day 15–21)

| Day | Action | Verification |
|-----|--------|-------------|
| 15 | Activate blocking: `fail-on: high` | PR with HIGH finding → CI red |
| 16 | Establish weekly fix-plan routine | `drift fix-plan` → top-3 tasks/week |
| 17–21 | Focus on AVS + CIR (architecture) | AVS and CIR findings trend down |

### Week 4: Validation (Day 22–30)

| Day | Action | Verification |
|-----|--------|-------------|
| 22 | Full snapshot | `drift analyze -f json -o week4.json` |
| 23 | Compare with baseline | Score vs. Day 0, per-signal delta |
| 24 | Update baseline (new ratchet point) | `drift baseline -o .drift-baseline.json` |
| 25 | Evaluate `fail-on: medium` | Optional escalation |
| 26–30 | Remaining fix-plan tasks | **Target: score ≤ 0.30** |

## Files in This Example

| File | Measure | Purpose |
|------|---------|---------|
| [`drift.yaml`](drift.yaml) | M005 | Vibe-coding-optimised signal weights and thresholds |
| [`drift-gate.yml`](drift-gate.yml) | M001 | GitHub Actions workflow for pre-merge gate |
| [`pre-push`](pre-push) | M002 | Git pre-push hook with drift check |
| [`mcp.json`](mcp.json) | M003 | VS Code MCP server config for IDE integration |
| [`setup-baseline.sh`](setup-baseline.sh) | M004 | Baseline setup script with delta gate |
| [`weekly-check.sh`](weekly-check.sh) | M006/M007 | Weekly trend monitoring + fix-plan script |

## Fault Tree: What drift Eliminates

```
Technical debt grows uncontrolled in AI codebases
│
├── AI code merged without architecture check
│   ├── LLM ignores layer boundaries      → AVS signal + CI gate (M001)
│   ├── Developer misses erosion           → SARIF annotations (M001) + MCP (M003)
│   └── No structural check in CI         → drift check --fail-on high (M001/M002)
│
├── Copy-paste instead of refactoring
│   ├── LLM duplicates instead of reusing  → MDS signal detects near-duplicates
│   ├── No duplicate scan before merge    → PFS + MDS in pre-merge gate
│   └── Debt is invisible                 → drift trend + weekly snapshots (M006)
│
├── Day-2 costs rise silently
│   ├── Circular imports grow              → CIR signal
│   ├── God-modules form                   → COD signal
│   └── No trend monitoring               → drift trend + baseline ratchet (M004)
│
└── LLM-specific anti-patterns accumulate
    ├── type: ignore / noqa buildup       → BAT signal
    ├── Happy-path-only tests              → TPD signal
    └── Broad except Exception             → BEM signal
```

**Expected outcome:** reduced architecture drift and faster debt triage when the workflow is adopted consistently.
Exact impact depends on repository shape, baseline score, and enforcement level.

## Success Metrics

| Metric | Baseline | Target (30 days) | Measurement |
|--------|----------|------------------|-------------|
| drift composite score | ~0.50–0.60 | **≤ 0.30** | `drift analyze --quiet` |
| MDS findings (duplicates) | N | **-70%** | `drift analyze -f json \| jq '.findings \| map(select(.rule_id=="MDS")) \| length'` |
| PFS findings (fragmentation) | N | **-50%** | Same pattern with `PFS` |
| AVS findings (architecture) | N | **-60%** | Same pattern with `AVS` |
| BAT findings (bypasses) | N | **-50%** | Same pattern with `BAT` |
| PRs merged with HIGH findings | Untracked | **0** | CI enforcement via drift-gate.yml |

## Residual Risks

| Risk | Why drift can't fully solve it | Mitigation |
|------|-------------------------------|------------|
| LLM context-window limit | LLM can't see all files for cross-file refactoring | `drift_fix_plan` via MCP server guides targeted refactoring |
| Prompt quality | drift can't control what the developer prompts | `drift explain` as training; policies in drift.yaml |
| Developer bypasses gate | `--exit-zero` or `DRIFT_SKIP_CHECK=1` | Enforce in CI (no skip option); pre-push as second layer |
| Novel LLM anti-patterns | Future models may produce new patterns | `auto_calibrate: true` + modular signal architecture |
