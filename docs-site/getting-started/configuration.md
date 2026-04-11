# Configuration

Create a `drift.yaml` in your project root to customize detection behavior.

## Minimal Example

```yaml
include:
  - "**/*.py"
exclude:
  - "**/node_modules/**"
  - "**/venv/**"
fail_on: none
```

Start with `fail_on: none` so the first rollout teaches the team how to read findings before CI starts blocking merges.

## JSON Schema for drift.yaml

Drift publishes an authoritative JSON Schema at repository root:

- `drift.schema.json`

This schema is generated from the runtime `DriftConfig` model and can be refreshed with:

```bash
drift config schema --output drift.schema.json
```

### Editor autocomplete (YAML language server)

Add this header comment to `drift.yaml`:

```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/mick-gsk/drift/main/drift.schema.json
```

This enables field autocomplete and static validation in editors that support the YAML language server (for example VS Code).

### CI/static validation

You can validate `drift.yaml` against the same schema in CI:

```bash
python -m pip install check-jsonschema
check-jsonschema --schemafile drift.schema.json drift.yaml
```

## Full Configuration Reference

```yaml
# File patterns
include:
  - "**/*.py"
exclude:
  - "**/node_modules/**"
  - "**/__pycache__/**"
  - "**/venv/**"

# Signal weights (normalized internally)
weights:
  pattern_fragmentation: 0.22
  architecture_violation: 0.22
  mutant_duplicate: 0.17
  temporal_volatility: 0.17
  explainability_deficit: 0.12
  system_misalignment: 0.10
  doc_impl_drift: 0.00  # Phase 2

# Detection thresholds
thresholds:
  high_complexity: 10
  medium_complexity: 5
  min_function_loc: 10
  similarity_threshold: 0.80
  recency_days: 14
  volatility_z_threshold: 1.5

# Architecture boundaries
policies:
  layer_boundaries:
    - name: "No DB imports in API layer"
      from: "api/**"
      deny_import: ["db.*", "models.*"]
    - name: "No API imports in DB layer"
      from: "db/**"
      deny_import: ["api.*", "routes.*"]

# CI severity gate
fail_on: none
```

## Signal Weights

Weights control the relative importance of each signal in the composite score. They are normalized internally — they don't need to sum to 1.0.

Default weights are calibrated via ablation study (see [Scoring Model](../algorithms/scoring.md)).

## Architecture Policies

Layer boundaries define which imports are allowed between modules. This is the most impactful configuration for the Architecture Violation Signal (AVS).

## Finding Context Policy

Drift classifies each finding into a machine-readable `finding_context` bucket.
Default contexts are:

- `production`
- `fixture`
- `generated`
- `migration`
- `docs`

By default, non-operational contexts (`fixture`, `generated`, `migration`, `docs`)
remain visible in findings, but are excluded from prioritization queues
(`fix_first`, `fix_plan`) unless explicitly enabled.

Example override with glob rules and precedence:

```yaml
finding_context:
  default_context: production
  non_operational_contexts:
    - fixture
    - generated
    - migration
    - docs
  rules:
    - pattern: "**/benchmarks/**"
      context: fixture
      precedence: 40
    - pattern: "**/generated/**"
      context: generated
      precedence: 35
    - pattern: "src/generated/safe/**"
      context: production
      precedence: 50
```

Trade-off: this reduces remediation noise in mixed repositories, but teams with
generated-code ownership should opt in to include non-operational contexts in
prioritization for those workflows.

## Calibration (Learning Model)

Drift includes a Bayesian learning model that adjusts signal weights based on your feedback. See the [Feedback & Calibration Guide](../guides/feedback-calibration.md) for the full workflow.

```yaml
calibration:
  enabled: true
  min_samples: 20              # Min TP+FP per signal for full confidence
  correlation_window_days: 30  # Days to look for defect-fix commits
  decay_days: 90               # Profile considered stale after this
  weak_fp_window_days: 60      # No defect-fix → counts as weak FP
  fn_boost_factor: 0.1         # Boost weight for high-FN signals (0.0–1.0)
  auto_recalibrate: false      # Auto-calibrate after each analyze run
  github_token: null            # Or set DRIFT_GITHUB_TOKEN env var
  bug_labels:
    - bug
    - regression
    - defect
  feedback_path: ".drift/feedback.jsonl"
  history_dir: ".drift/history"
  max_snapshots: 20
  threshold_adaptation_enabled: false  # Experimental
```

| Field | Default | Description |
|-------|---------|-------------|
| `enabled` | `false` | Master switch |
| `min_samples` | `20` | Min observations per signal for full calibration confidence |
| `correlation_window_days` | `30` | Days after scan to look for defect-fix commits (TP evidence) |
| `decay_days` | `90` | Stale profile threshold |
| `weak_fp_window_days` | `60` | No defect-fix in this window → weak FP evidence |
| `fn_boost_factor` | `0.1` | Weight boost for high-FN signals (max 1.0, 0.0 disables) |
| `auto_recalibrate` | `false` | Recompute weights on every `drift analyze` |
| `github_token` | `null` | GitHub token for issue/PR correlation |
| `bug_labels` | `["bug", "regression", "defect"]` | Issue labels for defect correlation |
| `feedback_path` | `".drift/feedback.jsonl"` | JSONL file for TP/FP/FN verdicts |
| `history_dir` | `".drift/history"` | Directory for scan history snapshots |
| `max_snapshots` | `20` | Max retained snapshots before pruning |
| `threshold_adaptation_enabled` | `false` | Experimental adaptive thresholds |

## Attribution (Git Blame)

Enrich findings with git-blame provenance — shows which commit introduced the drifting code.

```yaml
attribution:
  enabled: true
  cache_enabled: true
  timeout_per_file_seconds: 3.0
  max_parallel_workers: 4
  include_branch_hint: true
```

When enabled, each finding gains `attribution: {commit_hash, author, email, date, branch_hint}`. Blame results are cached in `.drift-cache/blame_cache.db`.

## Plugins

Selectively disable plugins discovered via Python entry points.

```yaml
plugins:
  disabled:
    - my-noisy-plugin
    - experimental-signal
```

Plugin names must match entry-point names exactly. Invalid names are silently ignored.

## Agent Objective

Declare the agent's current task so drift provides targeted feedback and tracks effectiveness.

```yaml
agent:
  goal: "Migrate payment module to Stripe API"
  strict_guardrails: false
  out_of_scope:
    - "legacy/"
    - "tests/fixtures/"
  success_criteria:
    - "No new AVS findings in src/billing/"
    - "All PFS findings resolved"
  effectiveness_thresholds:
    low_effect_resolved_per_changed_file: 0.25
    low_effect_resolved_per_100_loc_changed: 0.5
    high_churn_min_changed_files: 5
    high_churn_min_loc_changed: 200
```

| Field | Default | Description |
|-------|---------|-------------|
| `goal` | `""` | Natural-language task description |
| `strict_guardrails` | `false` | Enforce MCP tool ordering (brief→scan→fix-plan→nudge→diff) |
| `out_of_scope` | `[]` | Paths the agent should not touch |
| `success_criteria` | `[]` | Human-readable completion conditions |
| `effectiveness_thresholds` | (see above) | Deterministic low-effect/high-churn warning thresholds |

## Path Overrides

Per-path weight overrides, signal exclusions, and severity gates.

```yaml
path_overrides:
  "tests/**":
    weights:
      pattern_fragmentation: 0.0
      architecture_violation: 0.05
    exclude_signals:
      - temporal_volatility
  "legacy/**":
    severity_gate: "critical"
    weights:
      pattern_fragmentation: 0.05
      architecture_violation: 0.05
```

Most specific (longest) glob match wins. `exclude_signals` takes precedence over `weights` for the same signal.

## Deferred Areas

Mark known technical debt — analyzed but tagged as `deferred=true` (unlike `exclude`, which skips analysis entirely).

```yaml
deferred:
  - pattern: "legacy/**"
    reason: "Scheduled Q3 rewrite"
    review_by: "2026-09-01"
  - pattern: "vendor/**"
    reason: "Third-party code"
```

Deferred findings are excluded from `fix-plan` by default (opt in via `--include-deferred`).

## Brief Scope Aliases

Keyword → path mapping for convenient `drift brief --scope` resolution.

```yaml
brief:
  scope_aliases:
    payment: src/billing/
    auth: src/auth/
    api: src/api/
    legacy: legacy/
```

Usage: `drift brief --scope payment` resolves to `src/billing/`. Exact paths still work.

## Monorepo Configuration Examples

Drift works with any Python repository layout, including monorepos. Two
complementary approaches are available — often used together.

### When to use `--path` vs `include`/`exclude`

| Approach | When to use |
|---|---|
| `--path packages/my_service` | One-off scan of a single package from the command line; no config file changes needed. |
| `include`/`exclude` in `drift.yaml` | Permanent, reviewable configuration committed next to the code; required for CI and multi-package setups. |

Use `--path` for quick ad-hoc analysis. Use `include`/`exclude` when the scope
should be reproducible and versioned.

### Example 1 — Scanning a single package

Place a `drift.yaml` inside the package directory (or at the repo root and
pass `--path` on the command line):

```yaml
# packages/payment_service/drift.yaml
include:
  - "**/*.py"
exclude:
  - "**/tests/**"
  - "**/migrations/**"
  - "**/__pycache__/**"
fail_on: medium
```

Run with:

```bash
drift analyze --repo . --path packages/payment_service
```

Drift restricts file discovery and Git-history analysis to
`packages/payment_service/` so findings from other packages do not appear.

### Example 2 — Scanning multiple packages with shared config

Keep one `drift.yaml` at the repo root that covers all packages but excludes
infrastructure, tooling, and generated code:

```yaml
# drift.yaml (repo root)
include:
  - "packages/**/*.py"
  - "libs/**/*.py"
exclude:
  - "**/tests/**"
  - "**/migrations/**"
  - "**/generated/**"
  - "**/node_modules/**"
  - "**/__pycache__/**"
  - "infra/**"
  - "scripts/**"
fail_on: none
```

Run a single analysis that covers the entire monorepo:

```bash
drift analyze --repo .
```

Or scan individual packages in CI per job:

```bash
drift analyze --repo . --path packages/auth_service
drift analyze --repo . --path packages/payment_service
```

### Example 3 — Per-package `drift.yaml` with package-local overrides

For packages that need stricter or looser thresholds than the default, add a
`drift.yaml` directly inside that package and pass `--path`:

```yaml
# packages/core_lib/drift.yaml
include:
  - "**/*.py"
exclude:
  - "**/tests/**"
thresholds:
  high_complexity: 8       # stricter than default (10)
  similarity_threshold: 0.75
fail_on: high
```

```bash
drift analyze --repo . --path packages/core_lib
```

The local `drift.yaml` is resolved relative to the `--path` argument, so each
package can carry its own policy independent of the repo root.
