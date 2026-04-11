# Drift Bot — GitHub App

Drift Bot is a GitHub App that posts architectural drift analysis on every pull request — no workflow files needed.

Install it once on your organization or repository, and every PR gets a **Drift Report** comment with score, trend, and top findings.

## How it works

```
PR opened / updated
       │
       ▼
  Drift Bot receives webhook
       │
       ├── Clones the PR branch
       ├── Runs drift analysis
       └── Posts / updates a Drift Report comment
```

The comment is updated in place on subsequent pushes — no comment spam.

## PR Comment

Every Drift Report includes:

- **Score badge** — color-coded drift score (0.00–1.00)
- **Trend** — improving (🟢), degrading (🔴), or stable (⚪) compared to baseline
- **Severity distribution** — breakdown by critical/high/medium/low
- **Top findings** — the 3 highest-impact findings with signal, location, and fix hint

The comment format matches the [GitHub Action](integrations.md) output, so teams upgrading from the Action get a familiar experience.

## Installation

### 1. Deploy the server

Drift Bot needs a server to receive webhooks and run analysis. See the [deployment guide](https://github.com/mick-gsk/drift/tree/main/github-app) for options:

- **Fly.io** (recommended) — `fly deploy` with 3 secrets
- **Docker** — self-hosted container
- **Any Python host** — `pip install` + `python -m drift_bot.main`

### 2. Register the GitHub App

Create a GitHub App at [Settings → Developer settings → GitHub Apps](https://github.com/settings/apps/new):

| Setting | Value |
|---------|-------|
| Webhook URL | `https://<your-server>/webhook` |
| Permissions | Contents: Read, Pull requests: Write |
| Events | Pull request |

### 3. Install on repositories

Visit your App's installation page and select which repositories should get Drift Reports.

Done. Open a PR and the bot posts a report.

## App vs. Action

| Feature | GitHub Action | Drift Bot App |
|---------|--------------|---------------|
| **Setup** | Workflow file per repo | Install once |
| **Identity** | `github-actions[bot]` | `drift-bot[bot]` |
| **Config needed** | `.github/workflows/drift.yml` | None |
| **Org-wide rollout** | Manual per repo | 1-click |
| **SARIF upload** | ✅ | Planned |
| **Drift Brief** | ✅ | Planned |

**Recommendation:** Start with the Action for a single repo. Switch to the App when you want org-wide coverage without per-repo setup.

## Configuration

Drift Bot reads `drift.yaml` from the repository root — the same configuration used by the CLI and Action. No special App config is needed.

See [Configuration](getting-started/configuration.md) for all options.

## Source code

The full App source is at [`github-app/`](https://github.com/mick-gsk/drift/tree/main/github-app) in the drift repository.

## Related

- [Integrations](integrations.md) — all integration surfaces (Action, CLI, MCP, pre-commit)
- [CI Architecture Checks (SARIF)](use-cases/ci-architecture-checks-sarif.md) — SARIF + code scanning with the Action
- [Team Rollout](getting-started/team-rollout.md) — progressive adoption strategy
