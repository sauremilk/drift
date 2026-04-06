# Demo Recording Workflow (Vhs)

This folder contains the reproducible terminal demo setup for Drift.

## Files

- `demo.tape`: Vhs script that records core CLI commands (`analyze` + `check`). → `demo.gif` (README hero)
- `agent-workflow.tape`: Full agent loop — session baseline (`scan`), staged diff guardrail (`diff --staged-only`), repair tasks (`fix-plan`). → `agent-workflow.gif`
- `trend.tape`: Temporal analysis — score history (`trend`) + per-module root-cause timeline (`timeline`). → `trend.gif`
- `ci-gate.tape`: CI integration — analysis, `check --fail-on` gate, SARIF export. → `ci-gate.gif`
- `onboarding.tape`: First use — `explain PFS`, pattern findings, `init --dry-run`. → `onboarding.gif`
- `agent-fix-plan.tape`: (original) Agent baseline + prioritized repair tasks on the demo project. → `agent-fix-plan.gif`
- `agent-diff.tape`: (original) Staged-change guardrail flow. → `agent-diff.gif`
- `agent-copilot-context.tape`: (original) Copilot instruction generation from drift findings. → `agent-copilot-context.gif`

## Prerequisites

**Option A — VHS** (Linux / macOS recommended):

```bash
# macOS
brew install vhs
# or via Scoop on Windows
scoop install vhs
```

If your setup requires it, install Chrome/Chromium for rendering.

**Option B — Python + Pillow** (Windows-compatible fallback):

```bash
pip install Pillow   # already included in the dev venv
```

## Render the GIF

### Option A — VHS

Run from repository root:

```powershell
# Render all demos at once (recommended):
./scripts/render_demo.ps1

# Or render individual tapes:
vhs demos/demo.tape
vhs demos/agent-workflow.tape
vhs demos/trend.tape
vhs demos/ci-gate.tape
vhs demos/onboarding.tape
vhs demos/agent-fix-plan.tape
vhs demos/agent-diff.tape
vhs demos/agent-copilot-context.tape
```

### Option B — Python (Windows / CI fallback)

```bash
python scripts/make_demo_gif.py
```

This generates `demos/demo.gif` using Pillow with the Catppuccin Mocha colour theme,
terminal window decoration, and a typing-effect animation — no browser or VHS required.

The command updates `demos/demo.gif`.

The other tapes render to:

- `demos/agent-workflow.gif` — agent loop (scan → diff --staged-only → fix-plan)
- `demos/trend.gif` — temporal score history + module timeline
- `demos/ci-gate.gif` — CI check gate + SARIF export
- `demos/onboarding.gif` — explain PFS, patterns, init
- `demos/agent-fix-plan.gif` — (original) agent repair flow
- `demos/agent-diff.gif` — (original) staged diff guardrail
- `demos/agent-copilot-context.gif` — (original) Copilot context generation

## Keep it deterministic

- Prefer commands that run quickly and produce stable output.
- Avoid machine-specific absolute paths.
- Re-record after major CLI output changes.
- The staged diff tape creates its own temporary git repo under `demos/.tmp_agent_diff_demo`.
