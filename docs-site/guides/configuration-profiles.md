# Configuration Profiles

Drift ships 7 built-in profiles — pre-tuned signal weights, thresholds, and policies for common project types.

```bash
drift init --profile <name>   # scaffold drift.yaml with chosen profile
drift init --profile vibe-coding --full  # profile + CI + hooks + MCP
```

---

## Profile overview

| Profile | Best for | `fail_on` | Key emphasis |
|---|---|---|---|
| **default** | Most Python/TS projects | `none` | Balanced weights across all signals |
| **vibe-coding** | AI-accelerated codebases (Copilot, Cursor, Claude) | `none` | Copy-paste detection ↑, bypass accumulation ↑, test polarity ↑ |
| **strict** | Mature projects with zero tolerance | `medium` | All signals fully weighted, blocks on medium+ severity |
| **fastapi** | FastAPI / web-API projects | `none` | Architecture violations ↑, strict layer boundaries (routes → services → DB) |
| **library** | Reusable Python packages | `none` | API surface quality ↑ (explainability, naming, doc-impl drift) |
| **monorepo** | Large multi-package repos | `none` | Architecture violations ↑, co-change coupling ↑, higher file limits |
| **quick** | First-run / exploration | `none` | AST-only signals, no git, low file limits — fast results |

---

## default

Balanced defaults suitable for most Python/TS projects. This is what you get without any configuration.

```bash
drift init
```

**Signal emphasis:** Pattern fragmentation (0.16), architecture violation (0.16), mutant duplicate (0.13), explainability deficit (0.09).

**When to use:** Starting out, general-purpose repos, when you're not sure which profile fits.

---

## vibe-coding

Optimised for AI-accelerated codebases. Upweights copy-paste detection, bypass accumulation, and test polarity deficit — the dominant debt vectors in vibe-coded repos.

```bash
drift init --profile vibe-coding
```

**Signal emphasis:** Mutant duplicate (0.20), pattern fragmentation (0.18), architecture violation (0.14), explainability deficit (0.10), bypass accumulation (0.06).

**Includes layer boundaries:**

- No DB imports in API layer
- No API imports in DB layer

**When to use:** Any repo where 50%+ of code is AI-generated. If you use Copilot, Cursor, or Claude Code heavily — start here.

📖 [Vibe-coding playbook →](../../examples/vibe-coding/README.md)

---

## strict

Maximum enforcement for mature projects that want zero tolerance on architectural drift.

```bash
drift init --profile strict
```

**Key difference:** `fail_on: medium` — CI and pre-push hooks will block on medium+ severity findings.

**When to use:** Production codebases with established architecture, where every drift regression should be caught immediately.

---

## fastapi

Tuned for FastAPI / web-API projects. Upweights architecture violations and enforces strict layer boundaries.

```bash
drift init --profile fastapi
```

**Signal emphasis:** Architecture violation (0.20), pattern fragmentation (0.14), mutant duplicate (0.13).

**Includes layer boundaries:**

- No DB imports in routers
- No HTTP imports in services

**When to use:** FastAPI, Flask, or Django projects with clear router/service/data layers.

---

## library

Tuned for reusable Python libraries. Upweights API surface quality signals to keep the public interface clean.

```bash
drift init --profile library
```

**Signal emphasis:** Explainability deficit (0.12), pattern fragmentation (0.14), architecture violation (0.12), mutant duplicate (0.10), doc-impl drift (0.08), naming contract (0.08).

**When to use:** PyPI packages, shared libraries, anything where external API quality matters most.

---

## monorepo

Tuned for large monorepos with multiple packages.

```bash
drift init --profile monorepo
```

**Signal emphasis:** Architecture violation (0.18), pattern fragmentation (0.14), mutant duplicate (0.13), co-change coupling (0.02 — elevated).

**Key difference:** `max_discovery_files: 20000` (2× the default) for broader coverage.

**When to use:** Monorepos with 5+ packages, turborepo/nx-style workspaces, micro-service collections in one repo.

---

## quick

Fast first-run scan for new users. Disables git-dependent and expensive signals, raises thresholds to reduce noise.

```bash
drift init --profile quick
# or just:
drift analyze . --max-findings 5
```

**Disabled signals:** Temporal volatility, system misalignment, exception contract drift, cohesion deficit, co-change coupling.

**Key differences:** Higher similarity threshold (0.85), larger minimum function size (15 LOC), lower file limit (2000).

**When to use:** First exploration of a new codebase, demos, quick triage.

---

## Custom profiles

Profiles are starting points. After `drift init`, edit `drift.yaml` to fine-tune:

```yaml
# drift.yaml (generated from vibe-coding profile, then customized)
weights:
  mutant_duplicate: 0.25    # even higher for your codebase
  architecture_violation: 0.10  # less important in your context

thresholds:
  similarity_threshold: 0.70  # catch more near-duplicates

fail_on: high  # block only high+ severity
```

Use `drift calibrate` to let Bayesian learning adjust weights based on your feedback over time.

📖 [Configuration reference →](../getting-started/configuration.md) · [Configuration levels →](configuration-levels.md) · [Feedback & calibration →](feedback-calibration.md)
