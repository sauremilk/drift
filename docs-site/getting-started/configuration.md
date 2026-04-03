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
