<div align="center">

<img src="docs/assets/banner.svg" alt="drift — steer your agent before it ships" width="900">

# Drift

**The structural guardrail layer for AI-assisted Python development.**

Before you delegate to an AI agent — `drift brief` generates structural constraints.  
After the session — `drift check` and the learning model adapt signal weights to your repo over time.

[![CI](https://github.com/mick-gsk/drift/actions/workflows/ci.yml/badge.svg)](https://github.com/mick-gsk/drift/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/drift-analyzer?cacheSeconds=300)](https://pypi.org/project/drift-analyzer/)
[![Python versions](https://img.shields.io/pypi/pyversions/drift-analyzer)](https://pypi.org/project/drift-analyzer/)
[![Drift Score](https://img.shields.io/badge/drift%20score-0.50-yellow?style=flat)](docs/STUDY.md)
[![codecov](https://codecov.io/gh/mick-gsk/drift/branch/main/graph/badge.svg)](https://codecov.io/gh/mick-gsk/drift)
[![License](https://img.shields.io/github/license/mick-gsk/drift)](LICENSE)

[Docs](https://mick-gsk.github.io/drift/) · [Benchmarking](docs-site/benchmarking.md) · [Trust & Limitations](docs-site/trust-evidence.md)

</div>

---

| | |
|---|---|
| **Pre-task guardrails** | `drift brief --task "add payment integration"` analyses the affected scope and outputs structural constraints — ready to paste into your agent prompt. |
| **Post-session gate** | `drift check` runs 20+ cross-file signals and exits 1 on violations. Integrates with GitHub Actions, SARIF, and pre-commit. |
| **Adaptive learning model** | Bayesian per-repo calibration combines explicit feedback, git outcome correlation, and GitHub labels to reweight signals for your codebase. |
| **Negative anti-pattern library** | Every finding can be translated into deterministic "what NOT to do" items with IDs, forbidden patterns, and canonical alternatives — zero LLM in the loop. |
| **Guided vibe-coding rollout** | Ready-made config, 30-day plan, and scripts in `examples/vibe-coding/` for teams with heavy AI-coding usage. |
| **AI-native interfaces** | MCP server and HTTP API let Cursor, Claude Code, and Copilot call drift directly — includes `drift_nudge` and negative-context feeds. |

---

## Quick Install

```bash
pip install drift-analyzer
```

Python 3.11+. Full options (pipx, Homebrew, Docker, GitHub Action, pre-commit): [Installation →](docs-site/getting-started/installation.md)

---

## Two ways to work with drift

**Before a session — generate guardrails:**

```bash
drift brief --task "refactor the auth service" --format markdown
# → paste output into your agent prompt before delegation
```

**After a session — enforce structure:**

```bash
drift check --fail-on high         # local or CI gate
drift diff --staged-only           # pre-commit hook
drift analyze --repo . --format json  # full report
```

```yaml
# GitHub Actions — start report-only, tighten once you trust the output
- uses: mick-gsk/drift@v1
  with:
    fail-on: none               # report findings without blocking
    upload-sarif: "true"        # findings appear as PR annotations
```

📖 [Full workflow guide →](docs-site/getting-started/quickstart.md)

<div align="center">
  <img src="demos/demo.gif" alt="drift analyze terminal demo" width="720">
</div>

---

> **Best fit:** Python repos with 20+ files and active AI-assisted development.  
> Tiny repos produce noisy scores. Drift does not replace your linter, type checker, or security scanner — it covers the layer they cannot: cross-file structural coherence over time.

---

## Learning & calibration

Drift does not treat all signals equally forever. It maintains a per-repo profile:

- **Bayesian calibration engine** combines three evidence sources: explicit `drift feedback mark`, git outcome correlation, and GitHub issue/PR label correlation.
- **Feedback events** are stored as structured `FeedbackEvent` records and can be reloaded and replayed across versions (`record_feedback`, `load_feedback`).
- **Profile builder** (`build_profile`) produces a calibrated weight profile that `drift check` and `drift brief` use to focus on the most trusted signals in your codebase.

CLI surface: `drift feedback`, `drift calibrate`, `drift precision` (for your own ground-truth checks).

---

## Negative context library for agents

Drift can turn findings into a structured "what NOT to do" library for coding agents:

- **Per-signal generators** map each signal (PFS, MDS, AVS, BEM, TPD, …) to one or more `NegativeContext` items with category, scope, rationale, and confidence.
- **Anti-pattern IDs** like `neg-MDS-…` are deterministic and stable — ideal for referencing in policies and prompts.
- **Forbidden vs. canonical patterns**: each item includes a concrete anti-pattern code block and a canonical alternative, often tagged with CWE and FMEA RPN.
- **Security-aware**: mappings for `MISSING_AUTHORIZATION`, `HARDCODED_SECRET`, and `INSECURE_DEFAULT` generate explicit security guardrails for agents.

API: `findings_to_negative_context()` and `negative_context_to_dict()` deliver agent-consumable JSON for `drift_nudge`, `drift brief`, and other tools.

---

## Guided mode for vibe-coding teams

If your team ships most changes via AI coding tools (Copilot, Cursor, Claude), drift includes a guided mode:

- **CLI guide**: `drift start` prints the three-command journey for new users: `analyze → fix-plan → check` with safe defaults.
- **Vibe-coding playbook**: [examples/vibe-coding/README.md](examples/vibe-coding/README.md) documents a 30-day rollout plan (IDE → commit → PR → merge → trend) with concrete scripts and metrics.
- **Problem-to-signal map**: maps typical vibe-coding issues (duplicate helpers, boundary erosion, happy-path-only tests, type-ignore buildup) directly to signals like MDS, PFS, AVS, TPD, BAT, CIR, CCC.
- **Baseline + ratchet**: ready-made `drift.yaml`, CI gate, pre-push hook and weekly scripts implement a ratcheting quality gate over time.

📖 **Start here if you are a heavy AI-coding user:** [Vibe-coding technical debt solution →](examples/vibe-coding/README.md)

---

## Coming from another tool?

**From Ruff / pylint:** Drift operates one layer above single-file style. It detects when AI generates the same error handler four different ways across modules — something no linter sees.

**From SonarQube:** Drift runs locally with zero server setup and produces deterministic, reproducible findings per signal. Add it alongside SonarQube — not instead.

**From jscpd / CPD:** Drift's duplicate detection is AST-level, not text-level. It finds near-duplicates that text diff misses and places them in architectural context.

<details>
<summary><b>Full capability comparison</b></summary>

| Capability | drift | SonarQube | pylint / mypy | jscpd / CPD |
|---|:---:|:---:|:---:|:---:|
| Pattern Fragmentation across modules | ✔ | — | — | — |
| Near-Duplicate Detection (AST-level) | ✔ | Partial (text) | — | ✔ (text) |
| Architecture Violation signals | ✔ | Partial | — | — |
| Temporal / change-history signals | ✔ | — | — | — |
| GitHub Code Scanning via SARIF | ✔ | ✔ | — | — |
| Zero server setup | ✔ | — | Partial | ✔ |
| TypeScript support | Experimental ¹ | ✔ | — | ✔ |

✔ = within primary design scope · — = not a primary design target · Partial = limited coverage

¹ Via `drift-analyzer[typescript]`. Python is the primary analysis target.

Comparison reflects primary design scope per [STUDY.md §9](docs/STUDY.md).
</details>

---

## drift runs on itself

Drift analyzes its own source code on every release. Results are checked in as [benchmark_results/drift_self.json](benchmark_results/drift_self.json). Same input, same output — reproducible in CI.

```bash
drift self   # or: drift analyze --repo https://github.com/mick-gsk/drift
```

---

## Documentation

| | |
|---|---|
| [Quick Start](docs-site/getting-started/quickstart.md) | Install → first findings in 2 minutes |
| [Brief & Guardrails](docs-site/integrations.md) | Pre-task agent workflow |
| [CI Integration](docs-site/getting-started/team-rollout.md) | GitHub Action, SARIF, pre-commit, progressive rollout |
| [Signal Reference](docs-site/algorithms/signals.md) | All 21 signals with detection logic |
| [Benchmarking & Trust](docs-site/benchmarking.md) | Precision/Recall, methodology, artifacts |
| [MCP & AI Tools](docs-site/integrations.md) | Cursor, Claude Code, Copilot, HTTP API |
| [Configuration](docs-site/getting-started/configuration.md) | drift.yaml, layer boundaries, signal weights |
| [Calibration & Feedback](docs-site/algorithms/scoring.md) | Bayesian signal reweighting, feedback workflow |
| [Vibe-coding Playbook](examples/vibe-coding/README.md) | 30-day rollout guide for AI-heavy teams |
| [Contributing](CONTRIBUTING.md) | Dev setup, FP/FN reporting, signal development |

---

## Contributing

Drift's biggest blind spots are found by people running it on codebases the maintainers have never seen. A well-documented false positive can be more valuable than a new feature.

| I want to… | Go here |
|---|---|
| Ask a usage question | [Discussions](https://github.com/mick-gsk/drift/discussions) |
| Report a false positive / false negative | [FP/FN template](https://github.com/mick-gsk/drift/issues/new?template=false_positive.md) |
| Report a bug | [Bug report](https://github.com/mick-gsk/drift/issues/new?template=bug_report.md) |
| Suggest a feature | [Feature request](https://github.com/mick-gsk/drift/issues/new?template=feature_request.md) |
| Propose a contribution before coding | [Contribution proposal](https://github.com/mick-gsk/drift/issues/new?template=contribution_proposal.md) |
| Report a security vulnerability | [SECURITY.md](SECURITY.md) — not a public issue |

```bash
git clone https://github.com/mick-gsk/drift.git && cd drift && make install
make test-fast
```

See [CONTRIBUTING.md](CONTRIBUTING.md) · [ROADMAP.md](ROADMAP.md)

---

## Trust and limitations

Drift's pipeline is deterministic and benchmark artifacts are published in the repository — claims can be inspected, not just trusted.

- **No LLM in detection.** Same input, same output. Reproducible in CI and auditable.
- **Benchmarked:** 77 % strict / 95 % lenient precision on a historical ground-truth baseline (286 findings, 5 repos). 88 % mutation recall (15/17 patterns). These numbers apply to historical benchmark models and have not been revalidated for the current signal set.
- **Single-rater caveat:** ground-truth classification is not yet independently replicated.
- **Small-repo noise:** repositories with few files can produce noisy scores. Calibration mitigates but does not eliminate this.
- **Temporal signals** depend on clone depth and git history quality.
- **The composite score is orientation, not a verdict.** Interpret deltas via `drift trend`, not isolated snapshots.

Full methodology: [Benchmarking & Trust](docs-site/benchmarking.md) · [Full Study](docs/STUDY.md)

---

## License

MIT. See [LICENSE](LICENSE).
