---
applyTo: "**"
description: "Kontext-Routing — Zuordnung von Aufgabentypen zu relevanten Instructions und Skills. Hilft Agenten, bei großem Instruction-Volumen die richtigen Regeln zu priorisieren."
---

# Kontext-Routing — Welche Regeln gelten wann?

> **Zweck:** Nicht alle Instructions und Skills sind für jede Aufgabe gleich relevant.
> Diese Datei hilft dem Agenten, den Fokus auf die wichtigsten Regeln zu legen.

## Routing-Tabelle

| Aufgabentyp | Primäre Instructions | Relevante Skills | Primärer Fokus |
|-------------|---------------------|-----------------|----------------|
| **Signal-Arbeit** (neues Signal, Heuristik-Änderung) | drift-policy, drift-push-gates (Gate 2+7) | drift-signal-development-full-lifecycle, drift-risk-audit-artifact-updates, drift-adr-workflow | ADR-Pflicht, Audit-Pflicht, Precision/Recall |
| **Scoring/Gewichte** | drift-policy (§6 Priorisierung) | drift-adr-workflow | ADR-Pflicht, Benchmark-Evidence |
| **Output-Format** | drift-policy, drift-push-gates (Gate 7) | drift-adr-workflow, drift-risk-audit-artifact-updates | ADR-Pflicht, STRIDE-Update |
| **Bugfix** (`fix:`) | drift-policy, drift-push-gates (Gate 3+8) | drift-commit-push | CHANGELOG, Tests, kein ADR nötig |
| **Feature** (`feat:`) | drift-policy, drift-push-gates (Gate 2+3) | drift-commit-push | Feature-Evidence, Tests, CHANGELOG, STUDY.md |
| **Refactoring** | drift-policy, drift-quality-workflow | drift-commit-push | Kein ADR nötig, Tests grün |
| **Prompt/Instruction** | drift-policy | drift-agent-prompt-authoring | Shared Partials, Modellunabhängigkeit |
| **PR-Review** | drift-quality-workflow (Stufe 4) | drift-pr-review | Review-Checkliste (`.github/prompts/_partials/review-checkliste.md`) |
| **Release/Push** | drift-push-gates (alle Gates) | drift-commit-push, drift-release | Alle Gates prüfen, `make check` |
| **Fixture/Test** | drift-policy | drift-ground-truth-fixture-development | Precision/Recall, Ground Truth |
| **Dokumentation** | drift-policy (§13 Befund-Qualität) | — | Keine Gate-Pflicht außer Gate 8 |

## Priorisierungsregel

Wenn mehrere Instructions geladen sind, gilt:
1. **drift-policy** hat immer Vorrang (PFLICHT-GATE zuerst)
2. **drift-push-gates** nur relevant bei Commit/Push-Vorbereitung
3. **drift-quality-workflow** nur relevant bei nicht-trivialen Änderungen
4. **Release-Instructions** nur relevant bei `src/drift/**`-Änderungen

## Kontextreduktion

Bei einfachen Aufgaben (Doku-Fix, Typo, triviales Refactoring) reicht:
- Policy-Gate ausgeben
- Relevante Gates prüfen (meist nur Gate 8: `make check`)
- Kein vollständiger Quality-Workflow nötig
