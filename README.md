<div align="center">

<img src="https://raw.githubusercontent.com/mick-gsk/drift/main/docs/assets/banner.svg" alt="drift — steer your agent before it ships" width="900">

# Drift

**Your architecture is drifting. Your linter won't tell you. Drift will.**

19 scoring + 5 report-only signals · 77–95 % real-world precision · deterministic, no LLM · ~30 s for a 2 900-file codebase

→ **Vibe-coder / Cursor / Claude user?** [Start here](examples/vibe-coding/README.md) · → **CI & team rollout?** [Team rollout guide](https://mick-gsk.github.io/drift/getting-started/team-rollout/) · → **Evaluating signals?** [Benchmarks & study](docs/STUDY.md)

```bash
pip install drift-analyzer
drift setup          # 3-question wizard: picks the right profile for your project
drift status         # traffic-light health check — your daily entry point
```

<img src="https://raw.githubusercontent.com/mick-gsk/drift/main/demos/demo.gif" alt="drift analyze — Rich terminal output showing structural findings" width="720">

[![CI](https://github.com/mick-gsk/drift/actions/workflows/ci.yml/badge.svg)](https://github.com/mick-gsk/drift/actions/workflows/ci.yml)
[![Drift Score](https://img.shields.io/badge/drift%20score-0.44-yellow?style=flat)](benchmark_results/drift_self.json)
[![codecov](https://codecov.io/gh/mick-gsk/drift/branch/main/graph/badge.svg)](https://codecov.io/gh/mick-gsk/drift)
[![PyPI](https://img.shields.io/pypi/v/drift-analyzer?cacheSeconds=300)](https://pypi.org/project/drift-analyzer/)
[![PyPI Downloads](https://static.pepy.tech/badge/drift-analyzer/month)](https://pepy.tech/project/drift-analyzer)
[![Python versions](https://img.shields.io/pypi/pyversions/drift-analyzer)](https://pypi.org/project/drift-analyzer/)
[![GitHub Stars](https://img.shields.io/github/stars/mick-gsk/drift?style=flat)](https://github.com/mick-gsk/drift/stargazers)
[![License](https://img.shields.io/github/license/mick-gsk/drift)](LICENSE)
[![Discussions](https://img.shields.io/github/discussions/mick-gsk/drift)](https://github.com/mick-gsk/drift/discussions)

[Docs](https://mick-gsk.github.io/drift/) · [Quick Start](https://mick-gsk.github.io/drift/getting-started/quickstart/) · [Benchmarking](https://mick-gsk.github.io/drift/benchmarking/) · [Trust & Limitations](https://mick-gsk.github.io/drift/trust-evidence/)

</div>

---

## ⚡ Try it — zero install

```bash
uvx drift-analyzer analyze --repo .
```

> One command. No pre-install. Results in ~30 seconds.
> No config? Run `drift setup` after install — or: `drift init --profile vibe-coding` for an AI-optimised first run.
>
> **What does `drift setup` do?** Asks 3 questions (project type, AI usage, strictness) and writes a tuned `drift.yaml`.
> The `vibe-coding` profile raises tolerance for missing tests and anti-pattern fixtures — common in AI-prototyped code.

🌐 **No install at all?** [Analyze any public repo in your browser →](https://mick-gsk.github.io/drift/prove-it/)

> [!TIP]
> **Best fit:** Python repos with 20+ files and active AI-assisted development. TypeScript/TSX repo? `pip install 'drift-analyzer[typescript]'` — 17/24 signals supported.
> Tiny repos produce noisy scores. Drift does not replace your linter, type checker, or security scanner — it covers the layer they cannot: cross-file structural coherence over time.

**Recommended install:** `pipx install drift-analyzer` (isolated CLI) · Python 3.11+ · also via [pip, Homebrew, Docker, GitHub Action, pre-commit →](https://mick-gsk.github.io/drift/getting-started/installation/)

| Metric | Value | Evidence |
|---|---|---|
| Wild-repo precision | **77 % strict / 95 % lenient** (5 repos) | [study §5](https://github.com/mick-gsk/drift/blob/main/docs/STUDY.md) |
| Ground-truth regression | 0 FP, 0 FN (47 TP, 114 fixtures) | [v2.7.0 baseline](benchmark_results/v2.7.0_precision_recall_baseline.json) |
| Mutation recall | 100 % (25/25 injected) | [mutation benchmark](benchmark_results/mutation_benchmark.json) |

> [!NOTE]
> **Drift eats its own dog food.** Every release runs `drift self` on its own source — same pipeline, same rules, no exceptions. Results: [drift_self.json](benchmark_results/drift_self.json) · Score 0.50 — driven by explainability findings in internal functions and anti-pattern fixtures; [target ≤ 0.30 via 30-day rollout](examples/vibe-coding/README.md).

---

## 🤔 Why drift?

Most linters catch single-file style issues. Drift catches what they miss:
cross-file structural drift that accumulates silently during AI-assisted development.

<table>
<tr><th>Without Drift</th><th>With Drift</th></tr>
<tr>
<td>

- Agent duplicates a helper in 3 modules — tests pass
- Layer boundary violated in a refactor — CI green
- Auth middleware reimplemented 4 ways — linter silent
- Score degrades over weeks — nobody notices

</td>
<td>

- `drift brief` injects structural guardrails *before* the agent writes code
- `drift nudge` flags new violations in real-time during the session
- `drift check` blocks the commit on high-severity findings
- `drift trend` tracks score evolution — regressions are visible

</td>
</tr>
</table>

> 🔍 **Before** — `drift brief` analyses your repo scope and generates structural constraints ready to paste into your agent prompt  
> 🚦 **After** — `drift check` runs 20+ cross-file signals and exits 1 on violations — CI, SARIF, and pre-commit ready  
> 🧠 **Over time** — Adaptive calibration reweights signals via feedback, git outcome correlation, and GitHub label correlation
> 📚 **Negative context library** — `drift_nudge` delivers structured anti-patterns (canonical alternatives + CWE tags) directly into your agent's context — no manual guardrail writing needed

> [!NOTE]
> **Origin note:** Drift was originally designed to detect cross-file structural erosion in any codebase (v0.1, March 2026). The vibe-coding framing — and the dedicated `vibe-coding` profile — were added in v1.1.11 when it became clear that AI-assisted codebases exhibit these erosion patterns disproportionately. The underlying signals are the same; the profile adjusts weights and thresholds for AI-heavy development styles.

---

## 👤 Who is drift for?

| Audience | Starting point | You'll use |
|---|---|---|
| **Developers using AI tools** (Copilot, Cursor, Claude) | `drift setup` → `drift status` | `brief`, `nudge`, `check` — catch what your agent breaks |
| **Tech leads & teams** adopting AI at scale | [Team Rollout Guide](https://mick-gsk.github.io/drift/getting-started/team-rollout/) | CI gate, SARIF, `trend` — enforce structural standards |
| **Solo developers** wanting structural quality | `drift analyze --repo .` | `fix-plan`, `explain` — find and fix erosion patterns |

---

## 📅 30-day adoption plan

One page, three milestones — enough to go from first run to measurable improvement.

| Week | Goal | Commands | Done when |
|---|---|---|---|
| **1 — Baseline** | See your starting point | `drift setup` → `drift analyze --repo . --format json > baseline.json` | You have a score and a saved baseline file |
| **2 — Understand** | Triage the top 5 findings | `drift status` · `drift explain <signal>` | Each finding is marked fix, ignore, or defer |
| **3–4 — Improve** | Fix findings, block regressions | `drift check --fail-on high` (CI or pre-push) · `drift trend` | Score is lower than baseline; CI gate is green |

> **Which profile?** AI-heavy codebase → `drift init -p vibe-coding`. Unsure → `drift init` (default). You can switch later.

📖 [Full 30-day playbook with scripts →](examples/vibe-coding/README.md)

---

## ⚙️ How it works

**Before a session — generate guardrails:**

```bash
drift brief --task "refactor the auth service" --format markdown
# → paste output into your agent prompt before delegation
```

**After a session — enforce structure:**

```bash
drift check --fail-on high         # local or CI gate
drift check --fail-on none         # pre-commit hook (advisory, report-only)
drift analyze --repo . --format json  # full report
```

📖 [Full workflow guide →](https://mick-gsk.github.io/drift/getting-started/quickstart/)

### Signals at a glance

Drift findings use short codes. Here are the five you'll see most often:

| Code | Signal | What it catches | Example |
|---|---|---|---|
| **PFS** | Pattern Fragmentation | Same pattern reimplemented inconsistently across modules | 3 different `parse_config()` helpers |
| **MDS** | Mutant Duplicate | Near-duplicate functions that diverged over time | Two `validate_input()` with subtle differences |
| **AVS** | Architecture Violation | Imports that cross declared layer boundaries | `api/` importing directly from `db/` |
| **BAT** | Bypass Accumulation | Growing `# noqa`, `type: ignore`, `pragma` bypasses | 40 suppressions added in one sprint |
| **TPD** | Test Polarity Deficit | Missing negative / error-path test coverage | Only happy-path tests for auth module |

Every finding includes a human-readable `reason` and a concrete `next_action`. Full reference: [all 24 signals →](https://mick-gsk.github.io/drift/algorithms/signals/)

---

## 🔌 Works with

| AI Tools (MCP) | CI/CD | Git Hooks | Install |
|:---:|:---:|:---:|:---:|
| Cursor · Claude Code · Copilot | GitHub Actions · SARIF | pre-commit · pre-push | pip · pipx · uvx · Homebrew · Docker |

> **Language support:** Python (full, primary target) · TypeScript/TSX: 17/24 signals — `pip install 'drift-analyzer[typescript]'` · [language matrix](docs/language-support-matrix.md)

> **Bootstrap everything:** `drift init --mcp --ci --hooks` scaffolds config for all integrations in one command.

### GitHub Actions

[![Available on GitHub Marketplace](https://img.shields.io/badge/Marketplace-Drift-orange?logo=github)](https://github.com/marketplace/actions/drift-ai-code-coherence-monitor)

```yaml
# Try it — add this to .github/workflows/drift.yml
name: Drift
on: [push, pull_request]
jobs:
  drift:
    runs-on: ubuntu-latest
    permissions:
      security-events: write   # for SARIF upload
      pull-requests: write     # for PR comments
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0       # full history for temporal signals
      - uses: mick-gsk/drift@v1
        with:
          fail-on: none        # report-only — tighten once you trust the output
          upload-sarif: "true" # findings appear as PR annotations
          comment: "true"      # summary comment on each PR
```

**Outputs available** for downstream steps: `drift-score`, `grade`, `severity`, `finding-count`, `badge-svg`

### MCP / AI Tools

Cursor, Claude Code, and Copilot call drift directly via MCP server — the agent runs a full session loop:

| Phase | MCP Tool | What it does |
|---|---|---|
| **Plan** | `drift_brief` | Scope-aware guardrails injected into the agent prompt |
| **Code** | `drift_nudge` | Real-time `safe_to_commit` check after each edit |
| **Verify** | `drift_diff` | Full before/after comparison before push |
| **Learn** | `drift_feedback` | Mark findings as TP/FP — calibrates signal weights |

#### Copy-paste MCP config

**VS Code** — add to `.vscode/mcp.json`:

```json
{
  "servers": {
    "drift": {
      "type": "stdio",
      "command": "drift",
      "args": ["mcp", "--serve"]
    }
  }
}
```

**Claude Desktop** — add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "drift": {
      "command": "drift",
      "args": ["mcp", "--serve"]
    }
  }
}
```

**Cursor** — add to `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "drift": {
      "type": "stdio",
      "command": "drift",
      "args": ["mcp", "--serve"]
    }
  }
}
```

Or auto-generate: `pip install drift-analyzer[mcp] && drift init --mcp`

📖 [MCP setup guide →](https://mick-gsk.github.io/drift/integrations/)

**pre-commit:** Add `drift diff --staged-only` as a hook — findings block the commit before they reach CI.

📖 [Full integration guide →](https://mick-gsk.github.io/drift/integrations/)

---

## 🎛️ Configuration profiles

Pick a profile that matches your project — or start with `default` and calibrate later:

| Profile | Best for | Command |
|---|---|---|
| **default** | Most projects | `drift init` |
| **vibe-coding** | AI-heavy codebases (Copilot, Cursor, Claude) | `drift init -p vibe-coding` |
| **strict** | Mature projects, zero tolerance | `drift init -p strict` |
| **fastapi** | Web APIs with router/service/DB layers | `drift init -p fastapi` |
| **library** | Reusable PyPI packages | `drift init -p library` |
| **monorepo** | Multi-package repos | `drift init -p monorepo` |
| **quick** | First exploration, demos | `drift init -p quick` |

> **Team workflow:** Commit `drift.yaml` to your repo → CI enforces the same thresholds → team inherits calibrated weights.

📖 [Profile gallery with full details →](https://mick-gsk.github.io/drift/guides/configuration-profiles/) · [Configuration reference →](https://mick-gsk.github.io/drift/getting-started/configuration/)

---

## 📈 Measuring improvement — baseline and ratchet

Drift is most useful when you track score **deltas**, not snapshots.

**Day 0 — capture your baseline:**

```bash
drift analyze --repo . --format json > baseline.json
# note the composite score, e.g. 12.5
```

**Ongoing — ratchet the threshold down:**

```yaml
# drift.yaml — tighten after each successful sprint
thresholds:
  fail_on: high          # block high-severity findings
  max_score: 10.0        # lower this as your score improves
```

**Weekly — track the trend:**

```bash
drift trend              # shows score evolution over recent commits
```

**Example outcome:** *"Score dropped from 12.5 → 8.3 in 4 weeks — 3 PFS and 1 AVS finding resolved, CI gate tightened from 12.0 to 9.0."*

> **Tip:** The GitHub Action exposes `drift-score` as a step output — pipe it to a dashboard or Slack webhook for team visibility.

---

<details>
<summary><b>Advanced: Adaptive learning, Negative context library, Guided mode</b></summary>

### Adaptive learning & calibration

Drift does not treat all signals equally forever. It maintains a per-repo profile:

- **Adaptive calibration engine** uses precision-weighted linear interpolation across three evidence sources: explicit `drift feedback mark`, git outcome correlation, and GitHub issue/PR label correlation. As feedback accumulates, observed signal precision gradually overrides default weights (see [calibration design](src/drift/calibration/profile_builder.py)).
- **Feedback events** are stored as structured `FeedbackEvent` records and can be reloaded and replayed across versions (`record_feedback`, `load_feedback`).
- **Profile builder** (`build_profile`) produces a calibrated weight profile that `drift check` and `drift brief` use to focus on the most trusted signals in your codebase.

CLI surface: `drift feedback`, `drift calibrate`, `drift precision` (for your own ground-truth checks).

### Negative context library for agents

Drift can turn findings into a structured "what NOT to do" library for coding agents:

- **Per-signal generators** map each signal (PFS, MDS, AVS, BEM, TPD, …) to one or more `NegativeContext` items with category, scope, rationale, and confidence.
- **Anti-pattern IDs** like `neg-MDS-…` are deterministic and stable — ideal for referencing in policies and prompts.
- **Forbidden vs. canonical patterns**: each item includes a concrete anti-pattern code block and a canonical alternative, often tagged with CWE and FMEA RPN.
- **Security-aware**: mappings for `MISSING_AUTHORIZATION`, `HARDCODED_SECRET`, and `INSECURE_DEFAULT` generate explicit security guardrails for agents.

API: `findings_to_negative_context()` and `negative_context_to_dict()` deliver agent-consumable JSON for `drift_nudge`, `drift brief`, and other tools.

### Guided mode for vibe-coding teams

If your team ships most changes via AI coding tools (Copilot, Cursor, Claude), drift includes a guided mode:

- **CLI guide**: `drift start` prints the three-command journey for new users: `analyze → fix-plan → check` with safe defaults.
- **Vibe-coding playbook**: [examples/vibe-coding/README.md](examples/vibe-coding/README.md) documents a 30-day rollout plan (IDE → commit → PR → merge → trend) with concrete scripts and metrics.
- **Problem-to-signal map**: maps typical vibe-coding issues (duplicate helpers, boundary erosion, happy-path-only tests, type-ignore buildup) directly to signals like MDS, PFS, AVS, TPD, BAT, CIR, CCC.
- **Baseline + ratchet**: ready-made `drift.yaml`, CI gate, pre-push hook and weekly scripts implement a ratcheting quality gate over time.

📖 **Start here if you are a heavy AI-coding user:** [Vibe-coding technical debt solution →](examples/vibe-coding/README.md)

</details>

---

## 🔄 Coming from another tool?

**From Ruff / pylint:** Drift operates one layer above single-file style. It detects when AI generates the same error handler four different ways across modules — something no linter sees.

**From Semgrep / CodeQL:** Semgrep finds known vulnerability patterns in single files. Drift finds structural erosion across files — pattern fragmentation, layer violations, temporal volatility — that security scanners don't target. Semgrep Pro Engine adds cross-file dataflow analysis for security — drift adds cross-file structural coherence analysis for architecture. Different questions.

**From SonarQube:** Drift runs locally with zero server setup and produces deterministic, reproducible findings per signal. Add it alongside SonarQube — not instead. See [drift vs SonarQube](https://mick-gsk.github.io/drift/comparisons/drift-vs-sonarqube/) for the detailed comparison.

**From GitHub Copilot Code Review:** Copilot Review checks the PR after the code is written. Drift operates before (`drift brief` generates guardrails before an agent task starts) and during (`drift nudge` gives directional feedback inside the editing session). Use both — different positions in the workflow.

**From jscpd / CPD:** Drift's duplicate detection is AST-level, not text-level. It finds near-duplicates that text diff misses and places them in architectural context.

### Capability comparison

| Capability | drift | SonarQube | Ruff / pylint / mypy | Semgrep / CodeQL | jscpd / CPD |
|---|:---:|:---:|:---:|:---:|:---:|
| Pattern Fragmentation across modules | ✔ | — | — | — | — |
| Near-Duplicate Detection (AST-level) | ✔ | Partial (text) | — | — | ✔ (text) |
| Architecture Violation signals | ✔ | Partial | — | Partial (custom rules) | — |
| Temporal / change-history signals | ✔ | — | — | — | — |
| GitHub Code Scanning via SARIF | ✔ | ✔ | — | ✔ | — |
| Adaptive per-repo calibration | ✔ | — | — | — | — |
| MCP server for AI agents | ✔ | — | — | — | — |
| Zero server setup | ✔ | — | ✔ | ✔ | ✔ |
| TypeScript support | Partial ¹ | ✔ | — | ✔ | ✔ |

✔ = within primary design scope · — = not a primary design target · Partial = limited coverage

¹ Via `drift-analyzer[typescript]`. 17/24 signals supported via tree-sitter. Python is the primary analysis target.

Comparison reflects primary design scope per [STUDY.md §9](https://github.com/mick-gsk/drift/blob/main/docs/STUDY.md). This table was authored by the maintainer and has not been independently verified. Corrections welcome via [discussion](https://github.com/mick-gsk/drift/discussions).

---

## 🏷️ Add a drift badge to your README

Show your repo's drift score with a shields.io badge:

```bash
drift badge                    # prints URL + Markdown snippet
drift badge --format svg -o badge.svg  # self-contained SVG
```

Paste the Markdown output into your README:

```markdown
[![Drift Score](https://img.shields.io/badge/drift%20score-12.50-brightgreen?style=flat)](https://github.com/mick-gsk/drift)
```

**Automate in CI:** The [GitHub Action](https://github.com/marketplace/actions/drift-ai-code-coherence-monitor) exposes a `badge-svg` output — pipe it into your repo or a dashboard.

---

## 📚 Documentation

| Topic | Description |
|---|---|
| [Quick Start](https://mick-gsk.github.io/drift/getting-started/quickstart/) | Install → first findings in 2 minutes |
| [Brief & Guardrails](https://mick-gsk.github.io/drift/integrations/) | Pre-task agent workflow |
| [CI Integration](https://mick-gsk.github.io/drift/getting-started/team-rollout/) | GitHub Action, SARIF, pre-commit, progressive rollout |
| [Signal Reference](https://mick-gsk.github.io/drift/algorithms/signals/) | All 25 signals with detection logic |
| [Benchmarking & Trust](https://mick-gsk.github.io/drift/benchmarking/) | Precision/Recall, methodology, artifacts |
| [MCP & AI Tools](https://mick-gsk.github.io/drift/integrations/) | Cursor, Claude Code, Copilot, HTTP API |
| [Configuration](https://mick-gsk.github.io/drift/getting-started/configuration/) | drift.yaml, layer boundaries, signal weights |
| [Configuration Levels](https://mick-gsk.github.io/drift/guides/configuration-levels/) | Zero-Config → Preset → YAML → Calibration → MCP → CI |
| [Calibration & Feedback](https://mick-gsk.github.io/drift/algorithms/scoring/) | Adaptive signal reweighting, feedback workflow |
| [Vibe-coding Playbook](examples/vibe-coding/README.md) | 30-day rollout guide for AI-heavy teams |
| [Open Research Questions](RESEARCH.md) | 5 falsifiable hypotheses on validity and effectiveness |
| [Contributing](CONTRIBUTING.md) | Dev setup, FP/FN reporting, signal development |

---

## 🛠 Troubleshooting

<details>
<summary><strong>No Python files found</strong></summary>

drift walks the repo starting from the path passed to `--repo`. If the path is wrong or the repo uses a non-standard layout, use `--repo /absolute/path/to/project` and verify via `drift analyze --repo . --format json | python -m json.tool | Select-String files`.

</details>

<details>
<summary><strong>Shallow clone — git signals are missing or unreliable</strong></summary>

Time-based and co-change signals (TVS, CCC, AVS) require full git history. Unshallow the clone:

```bash
git fetch --unshallow
```

In CI (GitHub Actions), add `fetch-depth: 0` to your `actions/checkout` step.

</details>

<details>
<summary><strong>drift.yaml schema validation failed</strong></summary>

Validate your config against the schema:

```bash
python -m jsonschema -i drift.yaml drift.schema.json   # requires pip install jsonschema
```

Or regenerate a fresh config: `drift init` (overwrites drift.yaml with safe defaults).

</details>

<details>
<summary><strong>drift: command not found after install</strong></summary>

The `drift` binary may not be on your PATH. Check:

```bash
which drift          # macOS/Linux
where drift          # Windows
python -m drift analyze --repo .   # always works regardless of PATH
```

If you installed with `pip install --user`, add `~/.local/bin` (Linux/macOS) or `%APPDATA%\Python\Scripts` (Windows) to your PATH.

</details>

---

## 🤝 Contributing

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

<div align="center">
  <a href="https://github.com/mick-gsk/drift/graphs/contributors">
    <img src="https://contrib.rocks/image?repo=mick-gsk/drift&max=64" alt="Contributors" />
  </a>
</div>

See [CONTRIBUTING.md](CONTRIBUTING.md) · [ROADMAP.md](ROADMAP.md)

---

## 🔒 Trust and limitations

Drift's pipeline is deterministic and benchmark artifacts are published in the repository — claims can be inspected, not just trusted.

| Metric | Value | Artifact |
|---|---|---|
| Wild-repo precision | 77 % strict / 95 % lenient (5 repos) | [study §5](https://github.com/mick-gsk/drift/blob/main/docs/STUDY.md) |
| Ground-truth regression | 0 FP, 0 FN (47 TP, 114 fixtures) | [v2.7.0 baseline](benchmark_results/v2.7.0_precision_recall_baseline.json) |
| Mutation recall | 100 % (25/25 injected patterns) | [mutation benchmark](benchmark_results/mutation_benchmark.json) |
| Agent session score delta | 0.495→0.506 (1 live run) ² | [Copilot Autopilot artefacts](demos/copilot-autopilot/) |

² Single uncontrolled run — see [RESEARCH.md H4/H5](RESEARCH.md#h4--agent-guardrail-compliance-rate) for what a controlled study would require.

- **No LLM in detection.** The deterministic core uses no LLM inference — same input, same output. Optional local embeddings (`pip install drift-analyzer[embeddings]`) improve near-duplicate detection but are not required and do not call external services.
- **Single-rater caveat:** ground-truth classification is not yet independently replicated.
- **Small-repo noise:** repositories with few files can produce noisy scores. Calibration mitigates but does not eliminate this.
- **Temporal signals** depend on clone depth and git history quality.
- **The composite score is orientation, not a verdict.** Interpret deltas via `drift trend`, not isolated snapshots.
- **Own score context (0.50):** Drift's self-score is driven primarily by explainability deficit (undocumented internal functions) and findings in intentional anti-pattern fixtures under `data/negative-patterns/`. The score is neither aspirational nor concerning — it reflects a codebase that grows fast and prioritizes signal correctness over internal documentation. See [drift_self.json](benchmark_results/drift_self.json) for the full breakdown.
- **Signal overlap:** Some signals measure related phenomena (e.g., MDS and PFS both detect code similarity; CCC and TVS both use git history). A formal inter-signal correlation analysis has not been conducted. Overlap does not produce double-counting in the composite score (each signal contributes independently), but it means some findings may describe the same underlying issue from different angles.
- **Weight derivation:** Default signal weights for the 6 original signals were derived via rank-correlation (Kendall's τ) against manual architectural assessments on 5 open-source repos (single rater). Weights for the 18 newer signals are conservative heuristic assignments pending broader validation. Full methodology: [STUDY.md §1](docs/STUDY.md), [ADR-003](decisions/ADR-003-composite-scoring-model.md).

Full methodology: [Benchmarking & Trust](https://mick-gsk.github.io/drift/benchmarking/) · [Full Study](https://github.com/mick-gsk/drift/blob/main/docs/STUDY.md) · [Open Research Questions](RESEARCH.md)

---

## 🔧 Sustainability

Drift is maintained by [Mick Gottschalk](https://github.com/mick-gsk) as an independent open-source project.

- **License:** MIT — fork-safe, vendor-lock-free, reproducible CI.
- **Bus factor mitigation:** All signals, benchmarks, and release automation are fully documented and reproducible without the maintainer. The project has zero external service dependencies for core analysis.
- **Funding:** Currently unfunded. If your team relies on drift, consider [sponsoring](https://github.com/sponsors/mick-gsk) to support continued development.
- **Response target:** First reply within 72 hours on issues and discussions.

---

## ⭐ Star History

<div align="center">

[![Star History Chart](https://api.star-history.com/svg?repos=mick-gsk/drift&type=Date)](https://www.star-history.com/#mick-gsk/drift&Date)

</div>

---

## 📄 License

MIT. See [LICENSE](LICENSE).
