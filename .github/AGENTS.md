---
description: Agents, Skills und Evaluation-Prompts im Drift-Workspace
---

# Drift Agents & Prompts

## Release Agent

**Quick Release** — Nach Code-Änderungen an `src/drift/` den vollständigen Release-Workflow ausführen.

### Verwendung

Im Chat erwähnen: „Release version", „Create release", „Publish to PyPI".

Der Agent: Validiert → Version berechnet → CHANGELOG + pyproject.toml → Commit + Tag → Push → PyPI.

> **Hinweis:** Releases werden automatisch via python-semantic-release in CI verwaltet.
> Lokaler Fallback nur bei CI-Ausfall: `python scripts/release_automation.py --full-release`

### Wann verwenden

- Nach `feat:`, `fix:` oder `BREAKING:`-Commits auf `src/drift/`
- Wenn Tests bestehen und Code committed ist
- Nicht bei unfertiger Arbeit oder fehlschlagenden Tests

---

## Evaluation-Prompts

Prompts unter `.github/prompts/` evaluieren die Drift-CLI aus verschiedenen Perspektiven.
Navigations-Guide: `.github/prompts/README.md`

| Prompt | Zweck | Empfohlene Reihenfolge |
|--------|-------|------------------------|
| `drift-onboarding` | First-Use-Erfahrung (Zero-Knowledge) | 1 |
| `drift-agent-workflow-test` | Vollständiger CLI-Pfadtest | 2 |
| `drift-signal-quality` | Signal-Precision/Recall messen | 3 |
| `drift-ci-gate` | CI-Integration validieren | 4 |
| `drift-ai-integration` | LLM-Context-Qualität bewerten | 5 |
| `drift-agent-ux` | Agent-UX-Audit (Auffindbarkeit, Latenz, Fehler) | 6 |
| `PR-Orchestrator` | PR-Bewertung aus Agent-Perspektive | nach Bedarf |
| `release` | Release-Workflow validieren | nach Bedarf |

### Shared Components

| Datei | Zweck |
|-------|-------|
| `_partials/bewertungs-taxonomie.md` | Einheitliche Bewertungs-Labels |
| `_partials/konventionen.md` | Gemeinsame Konventionen (Policy Gate, Pfade, Sandbox) |
| `_partials/issue-filing.md` | Issue-Filing-Template (interne Prompts) |
| `_partials/issue-filing-external.md` | Issue-Filing-Template (Field-Tests, Cross-Repo) |

---

## Field-Test-Prompts (externe Repos)

Prompts unter `.github/prompts/field-tests/` testen drift in **beliebigen Repositories**.
Issues gehen an `mick-gsk/drift`. Details: `.github/prompts/field-tests/README.md`

| Prompt | Zweck | Empfohlene Reihenfolge |
|--------|-------|------------------------|
| `drift-field-test` | Smoke-Test: Funktioniert drift? | 1 |
| `drift-finding-audit` | Tiefenprüfung: Findings korrekt? | 2 |
| `drift-context-eval` | Kontext-Qualität für AI-Workflows | 3 |

---

## Skills

- **`drift-agent-prompt-authoring`** — Drift-Prompts unter `.github/prompts/` und `field-tests/` strukturiert schreiben oder verbessern
- **`drift-release`** — Vollständiger Release-Workflow
- **`drift-pr-review`** — PR-Review gemäß Drift Policy
- **`drift-security-triage`** — Security-Report-Triage

---

## Dokumentation

- **Release Skill:** `.github/skills/drift-release/SKILL.md`
- **Release Instructions:** `.github/instructions/drift-release-automation.instructions.md`
- **Policy:** `.github/instructions/drift-policy.instructions.md`
- **Push Gates:** `.github/instructions/drift-push-gates.instructions.md`
