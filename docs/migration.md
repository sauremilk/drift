# Migrating to Drift from Other Tools

Drift detects **cross-file architectural erosion** — a class of problems that
single-file linters and SAST tools cannot see.  It is designed to slot into
existing CI pipelines with minimal changes.

---

## Replace Ruff in 1 line

```yaml
# Before
- run: ruff check . --output-format sarif > results.sarif

# After — cross-file architecture analysis instead of single-file linting
- run: drift check --output-format sarif > results.sarif
```

Drift supports the same `--output-format` flag name as Ruff.  Available
formats: `rich`, `json`, `sarif`, `agent-tasks`, `github`.

| Ruff flag | Drift equivalent | Notes |
|-----------|------------------|-------|
| `--output-format sarif` | `--output-format sarif` | 1:1 compatible |
| `--output-format json` | `--output-format json` | Different schema (architectural findings) |
| `--output-format github` | `--output-format github` | `::warning` / `::error` annotations |
| `--select E,F` | `--select PFS,AVS` | Signal IDs instead of rule codes |
| `--ignore E501` | `--ignore TVS,DIA` | Signal IDs instead of rule codes |
| `--exit-zero` | `--exit-zero` | 1:1 compatible |
| `--config ruff.toml` | `--config drift.yaml` | YAML or TOML (`drift.toml`, `pyproject.toml`) |

> **Note:** Drift and Ruff are complementary.  Ruff catches style and import
> issues per file; Drift catches pattern fragmentation, architecture violations,
> and coherence decay across your codebase.

---

## Replace Semgrep in 1 line

```yaml
# Before
- run: semgrep scan --sarif --sarif-output=results.sarif

# After — zero-config architecture analysis (no rules to write)
- run: drift check --output-format sarif > results.sarif
```

| Semgrep flag | Drift equivalent | Notes |
|--------------|------------------|-------|
| `--sarif` | `--output-format sarif` | Same SARIF 2.1.0 schema |
| `--json` | `--output-format json` | Different schema |
| `--error` | `--fail-on low` | Fail on any finding |
| `--baseline-commit=REF` | `--diff REF` | Diff-based analysis |
| `-j N` | `--workers N` | Parallel workers |
| `--quiet` | `--quiet` | Minimal output |

> **Note:** Semgrep requires YAML rules for each pattern.  Drift detects
> architectural drift automatically with zero configuration.

---

## Replace pylint in 1 line

```yaml
# Before
- run: pylint src/ --output-format=json > results.json

# After — module-level coherence instead of statement-level checks
- run: drift analyze --repo src/ --output-format json > results.json
```

| pylint flag | Drift equivalent | Notes |
|-------------|------------------|-------|
| `--output-format=json` | `--output-format json` | Different schema (architecture findings) |
| `--disable=C0114` | `--ignore DIA` | Signal IDs instead of message codes |
| `--enable=E0401` | `--select AVS` | Signal IDs instead of message codes |
| `-j N` | `--workers N` | Parallel workers |
| `--rcfile=.pylintrc` | `--config drift.yaml` | YAML, TOML, or `pyproject.toml` |

> **Note:** pylint checks individual statements and conventions.  Drift
> measures whether your *modules* are internally coherent and whether
> architectural patterns are consistently applied.

---

## Replace SonarQube locally

```yaml
# Before — requires a SonarQube server instance
- run: sonar-scanner -Dsonar.projectKey=myapp -Dsonar.host.url=https://sonar.example.com

# After — fully local, no server needed
- run: drift analyze --output-format json > drift-results.json
```

> **Note:** SonarQube requires a server.  Drift runs entirely locally with
> `pip install drift-analyzer`, produces deterministic results, and needs
> zero infrastructure.

---

## Signal ID Quick Reference

Use these with `--select` and `--ignore`:

| ID  | Signal | Detects |
|-----|--------|---------|
| PFS | Pattern Fragmentation | Multiple incompatible implementations of the same pattern |
| AVS | Architecture Violation | Layer boundary breaches, circular dependencies |
| MDS | Mutant Duplicate | Near-duplicate functions with subtle differences |
| EDS | Explainability Deficit | Complex functions missing docs/types |
| TVS | Temporal Volatility | Abnormal churn in specific files |
| SMS | System Misalignment | Components in wrong architectural layer |
| DIA | Doc-Impl Drift | Documentation contradicts implementation |
| BEM | Broad Exception Monoculture | Overuse of bare `except` / `Exception` |
| TPD | Test Polarity Deficit | Missing negative/edge-case tests |
| GCD | Guard Clause Deficit | Deep nesting instead of early returns |
| COD | Cohesion Deficit | Low intra-module cohesion |
| NBV | Naming Contract Violation | Inconsistent naming patterns |
| BAT | Bypass Accumulation | Growing TODO/HACK/FIXME markers |
| ECM | Exception Contract Drift | Inconsistent error handling contracts |
| CCC | Co-Change Coupling | Files that always change together (hidden coupling) |

---

## Configuration in pyproject.toml

Drift supports configuration via `drift.yaml`, `drift.toml`, or `pyproject.toml`:

```toml
# pyproject.toml
[tool.drift]
fail_on = "high"
auto_calibrate = true

[tool.drift.weights]
pattern_fragmentation = 0.16
architecture_violation = 0.16

[tool.drift.thresholds]
similarity_threshold = 0.80
```

Config file priority: `--config` flag > `drift.yaml` > `drift.yml` > `.drift.yaml` > `drift.toml` > `pyproject.toml`

---

## GitHub Actions

```yaml
- name: Drift Architecture Check
  uses: sauremilk/drift@v0
  with:
    fail-on: high
    format: sarif
    upload-sarif: true
```

Or without the Action:

```yaml
- name: Install drift
  run: pip install drift-analyzer

- name: Run drift
  run: drift check --output-format sarif --fail-on high > results.sarif

- name: Upload SARIF
  uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: results.sarif
```
