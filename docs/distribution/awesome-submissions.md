# Awesome Submissions

This document contains ready-to-submit entries for discovery lists where developers actively evaluate tools.

## Goal

Increase top-of-funnel discovery for drift via curated lists with high evaluator intent.

## Readiness Gate (geprüft 2026-04-06)

Beide Listen haben Mindestanforderungen, die derzeit nicht erfüllt sind:

| Ziel | Stars-Mindest | Alter-Mindest | Kontributor-Mindest | Status (06.04.2026) |
|---|---|---|---|---|
| awesome-python | 100 (sonst auto-reject) | 3 Monate (sonst auto-reject) | – | ❌ drift: 7 Stars, 19 Tage alt |
| awesome-static-analysis | >20 | ≥3 Monate | >1 | ❌ drift: 7 Stars, 19 Tage alt, 1 Kontributor |

**Frühestmöglicher Einreichungszeitpunkt:** ~18. Juni 2026 (3 Monate nach Repo-Erstellung am 18.03.2026).
Star- und Kontributor-Schwelle muss bis dahin erreicht sein.

Der pre-commit-Index benötigt keine explizite Submission — drift ist via `.pre-commit-hooks.yaml`
automatisch über GitHub-Suche (`path:.pre-commit-hooks.yaml`) und Sourcegraph auffindbar.

---

## Target 1: awesome-python

- Repository: https://github.com/vinta/awesome-python
- Section: Code Analysis
- Suggested entry:

```markdown
* [drift](https://github.com/mick-gsk/drift) - Deterministic architecture erosion detection for AI-accelerated Python codebases with actionable findings and CI integration.
```

- Suggested PR title:

```text
Add drift to Code Analysis section
```

- Suggested PR body:

```markdown
## What this adds
Adds [drift](https://github.com/mick-gsk/drift), an open-source static analyzer focused on architectural coherence in AI-accelerated Python repositories.

## Why it belongs
- Deterministic analysis (no LLM dependency in the detection pipeline)
- Practical CI/CD integration with report-only and gated rollout
- Actionable findings for pattern fragmentation, architecture violations, and near-duplicate logic

If preferred, I can shorten the one-line description further.
```

## Target 2: awesome-static-analysis

- Repository: https://github.com/analysis-tools-dev/static-analysis
- **Korrekte Datei:** `data/tools/drift.yml` (ein YAML-File pro Tool, kein python.yml!)
- Suggested YAML entry:

```yaml
name: drift
categories:
  - code-quality
tags:
  - architecture
  - python
license: MIT
types:
  - cli
source: 'https://github.com/mick-gsk/drift'
description: >
  Deterministic architecture erosion detection for AI-accelerated Python codebases.
  Detects pattern fragmentation, architecture violations, near-duplicate logic,
  explainability deficits, and temporal instability. Supports terminal, JSON, and
  SARIF output with CI/CD integration.
```

- Suggested PR title:

```text
Add drift: deterministic architectural drift analysis for Python
```

- Suggested PR body:

```markdown
## What this adds
Adds `drift` to the Python tooling list.

## Why this tool is relevant
- Targets architectural erosion, not only syntax/style issues
- Deterministic and reproducible output
- Supports terminal, JSON, and SARIF output for team workflows

Homepage: https://github.com/mick-gsk/drift
```

## Submission Checklist

- Verify section placement matches maintainer guidelines.
- Keep one-liner neutral and non-promotional.
- Ensure links resolve and README headline matches the description.
- Keep scope clear: architecture/coherence analysis, not bug detection.
- Merge one list at a time to simplify maintainer review.

## Tracking

Record opened PR links here once submitted:

- awesome-python PR: (ausstehend — Gate nicht erfüllt, frühestens ~18.06.2026)
- awesome-static-analysis PR: (ausstehend — Gate nicht erfüllt, frühestens ~18.06.2026)

**Fortschritt-Trigger:** Wenn das Repo ≥ 3 Monate alt ist UND ≥ 21 Stars hat,
das Gate erneut prüfen und PRs eröffnen. Sterne-Zähler via `gh repo view mick-gsk/drift --json stargazerCount`.
