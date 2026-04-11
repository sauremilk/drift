# Negative Context for Agents

Drift generates deterministic **anti-pattern constraints** from analysis findings — telling AI coding agents what patterns must *not* be reproduced when generating code.

## Why negative context matters

Findings explain what went wrong. Negative context prevents re-introducing the same problem:

| Component | Purpose |
|-----------|---------|
| **Finding** | "Module X has 4 variants of error handling" |
| **Negative context** | "DO NOT add another bare `except Exception: pass`. INSTEAD use the canonical `raise ServiceError(...)` pattern." |

Without negative context, AI agents frequently fix one finding while re-introducing an already-known anti-pattern elsewhere.

## Quick start

### Generate anti-pattern instructions for your repo

```bash
# Preview to terminal
drift export-context

# Write to file (default: .drift-negative-context.md)
drift export-context --write

# Compact prompt format for system prompts
drift export-context --format prompt -w -o .cursorrules

# Include positive guidance too
drift export-context --include-positive -w
```

### Use in agent workflows

```bash
# Add to Copilot instructions (auto-merged)
drift copilot-context --write

# Export as raw JSON for custom pipelines
drift export-context --format raw -o patterns.json
```

## How it works

```
drift analyze → Findings → Negative Context Generators → Anti-Pattern Items
                                                              │
                    ┌─────────────────────────────────────────┘
                    │
              ┌─────▼──────┐
              │ Deduplicate │
              │ + Sort by   │
              │   severity  │
              └─────┬──────┘
                    │
         ┌──────────┼──────────┐
         │          │          │
    instructions   prompt     raw
    (Markdown)   (compact)   (JSON)
```

Each signal has a **registered generator** that transforms its findings into structured anti-pattern items. Currently **20+ generators** cover all scoring-active and report-only signals.

## Data model

Each anti-pattern item has this stable shape:

```json
{
  "anti_pattern_id": "neg-avs-1234567890",
  "category": "architecture",
  "source_signal": "architecture_violation",
  "severity": "high",
  "scope": "module",
  "description": "Layer boundary violation detected",
  "forbidden_pattern": "Importing from API layer into data layer",
  "canonical_alternative": "Move shared contract into neutral domain module",
  "affected_files": ["src/service/orders.py"],
  "confidence": 0.9,
  "rationale": "Repeated cross-layer imports increase coupling and drift risk",
  "metadata": {}
}
```

### Categories

| Category | Signals | Description |
|----------|---------|-------------|
| `security` | HSC, MAZ, ISD | Hardcoded secrets, missing auth, insecure defaults |
| `error_handling` | BEM, ECM | Broad exceptions, exception contract drift |
| `architecture` | PFS, AVS, MDS, CCC, CIR, FOE, COD | Structural and boundary violations |
| `testing` | TPD | Missing test coverage or polarity |
| `naming` | NBV | Naming convention violations |
| `complexity` | EDS, GCD, CXS | Unnecessary complexity, missing guards |
| `completeness` | DIA, BAT, DCA | Missing docs, accumulated bypasses, dead code |

### Scopes

| Scope | Meaning |
|-------|---------|
| `file` | Pattern specific to a single file |
| `module` | Pattern spans a module/directory |
| `repo` | Repository-wide pattern |

## Output formats

### `instructions` (default)

Markdown with category headings — suitable for `.github/copilot-instructions.md` or `.cursorrules`:

```markdown
## Security Anti-Patterns
- [!] **Hardcoded API token found** (hardcoded_secret, high)
  - **DO NOT:** `API_KEY = "sk-A1B2C3..."`
  - **INSTEAD:** Import from os.environ
  - Affected: src/config.py, src/auth.py
```

### `prompt`

Compact format for system prompts (minimal tokens):

```
AVOID: Bare except Exception: pass (broad_exception_monoculture, high)
USE INSTEAD: Specific exception types with proper handling
---
AVOID: Cross-layer import api→db (architecture_violation, high)
USE INSTEAD: Neutral domain module for shared contracts
```

### `raw`

Full JSON array of anti-pattern items — for custom pipelines and automation.

## Seed pattern library

Drift ships with **12 curated seed patterns** under `data/negative-patterns/patterns/` — ground-truth anti-patterns validated against real codebases:

| Pattern | Signal | Severity | Description |
|---------|--------|----------|-------------|
| `broad_exception_001` | BEM | high | Three connector modules catch bare Exception and log-only |
| `broad_exception_002` | BEM | medium | Four adapters with mixed broad except clauses |
| `explainability_deficit_001` | EDS | high | Complex function: nested conditionals, no docstring |
| `explainability_deficit_002` | EDS | high | Four levels of nested loops with conditional filtering |
| `guard_clause_deficit_001` | GCD | medium | Three public functions with zero guard clauses |
| `guard_clause_deficit_002` | GCD | medium | Deep nesting without guards in pipeline functions |
| `mutant_duplicate_001` | MDS | high | Two functions with identical logic, different names |
| `mutant_duplicate_002` | MDS | high | Near-duplicate functions with renamed variables |
| `mutant_duplicate_003` | MDS | high | Additional mutation-resilient duplicate variant |
| `naming_violation_001` | NBV | medium | `validate_email()` that performs transformation, never raises |
| `pattern_fragmentation_001` | PFS | high | Three handlers with incompatible error-handling strategies |
| `pattern_fragmentation_002` | PFS | medium | Four validators each use different validation approach |

Each pattern file includes metadata conforming to `data/negative-patterns/schema.json`:

```json
{
  "id": "broad_exception_001",
  "signal": "broad_exception_monoculture",
  "origin": "ai_assisted",
  "confirmed_problematic": true,
  "tp_confirmed": true,
  "severity": "high",
  "description": "Three connector modules catch bare Exception and log-only"
}
```

## Adding custom patterns

Create a Python file under `data/negative-patterns/patterns/` with a companion JSON metadata file matching the schema:

1. **Pattern file** (`.py`): Contains the actual anti-pattern code
2. **Metadata file** (`.json`): Describes the pattern per `schema.json`

Patterns must have `confirmed_problematic: true` and `tp_confirmed: true` to count as validated.

## Integration points

| Surface | How negative context appears |
|---------|----------------------------|
| `drift analyze --format json` | Top-level `negative_context` array |
| `drift analyze --format agent-tasks` | Per-task `negative_context` items |
| `drift export-context` | Standalone file generation |
| `drift copilot-context` | Merged into Copilot instructions |
| MCP `drift_scan` | Included in scan response |
| MCP `drift_fix_plan` | Included per repair task |

## Configuration

Control negative context scope and volume via CLI options:

```bash
drift export-context \
  --scope module \       # file, module, or repo scope filter
  --max-items 25 \       # maximum anti-pattern items
  --format instructions  # instructions, prompt, or raw
```

No `drift.yaml` configuration needed — negative context uses the same analysis configuration as `drift analyze`.
