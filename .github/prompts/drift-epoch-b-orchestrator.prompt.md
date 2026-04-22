---
name: "Drift Epoche-B Orchestrator"
description: "Wählt je Run das nächste legal umsetzbare Feature aus Items 05–08 (Cold-Start, Trend-Gate, Patch-Auto, VS-Code-Extension) und ruft den zugehörigen Feature-Prompt auf. Setzt voraus, dass ADR-084 Option C akzeptiert ist (via drift-strategy-flip.prompt.md)."
---

# Drift Epoche-B Orchestrator

Steuert die sequenzielle oder priorisierte Umsetzung der Epoche-B-
Features nach ADR-084 Option C. Pro Run wird **ein** Feature
ausgewählt und an seinen dedizierten Prompt übergeben. Der
Orchestrator baut keinen Code selbst, er trifft Reihenfolge- und
Gate-Entscheidungen.

> **Pflicht:** Vor Ausführung das Drift Policy Gate durchlaufen.
> Zusätzlich muss ADR-084 `status: accepted` sein. Andernfalls
> zuerst `drift-strategy-flip.prompt.md` ausführen.

## Relevante Referenzen

- **Strategie-Flip:** `drift-strategy-flip.prompt.md`
- **Feature-Prompts:**
  - `drift-feature-05-cold-start.prompt.md`
  - `drift-feature-06-trend-gate.prompt.md`
  - `drift-feature-07-patch-auto.prompt.md`
  - `drift-feature-08-vscode-extension.prompt.md`
- **ADR-Workflow:** `.github/skills/drift-adr-workflow/SKILL.md`
- **Push-Gates:** `.github/instructions/drift-push-gates.instructions.md`
- **Policy §18:** Risk-Audit-Pflichten bei Signal-/Architektur-Änderung

## Arbeitsmodus

- **Wählend, nicht implementierend.** Dieser Prompt baut keinen
  Feature-Code.
- **Abhängigkeiten respektieren.** Siehe Reihenfolge-Matrix unten.
- **Eine Dispatch-Entscheidung pro Run.** Kein paralleles Starten.

## Ziel

Items 05–08 in einer für Precision/Recall, Push-Gates und Agent-
Nutzung sinnvollen Reihenfolge abarbeiten, ohne Audit-Debt
aufzubauen.

## Empfohlene Reihenfolge

| Rang | Item | Begründung |
|------|------|-----------|
| 1 | 05 Cold-Start | Kleinster Scope, reine Perf, kein neues Signal, keine FMEA-Schwergewichte. Schafft sofort Nutzen für Agent-Workflows. |
| 2 | 06 Trend-Gate | Erweiterung bestehender Gate-Infrastruktur (`quality_gate.py`, `trend_history.py`). Kein neues Signal, aber neue Config-Oberfläche. |
| 3 | 07 Patch-Auto | Erweiterung der v2.14-Patch-Engine (`src/drift/api/patch.py`, `commands/patch_cmd.py`). Benötigt Precision/Recall-Validierung je betroffenem Signal. |
| 4 | 08 VS-Code-Extension | Größter Scope, polyglott (TypeScript). Abhängig von stabilem MCP-Interface; nach 05 reif, weil Cold-Start den IDE-UX-Eindruck prägt. |

Abweichungen von dieser Reihenfolge sind nur mit dokumentierter
Begründung im Run-Artefakt zulässig.

## Dispatch-Logik

Je Run in dieser Reihenfolge prüfen:

1. **ADR-084 `accepted`?** — Falls nein: Abbruch, auf
   `drift-strategy-flip.prompt.md` verweisen.
2. **Item 05 offen?** — Kein `feat:`-Commit mit Item-05-Evidenz
   in `benchmark_results/`? Dispatch auf
   `drift-feature-05-cold-start.prompt.md`.
3. **Item 06 offen?** — Kein `feat:`-Commit mit Item-06-Evidenz?
   Dispatch auf `drift-feature-06-trend-gate.prompt.md`.
4. **Item 07 offen?** — Kein `feat:`-Commit mit Item-07-Evidenz?
   Dispatch auf `drift-feature-07-patch-auto.prompt.md`.
5. **Item 08 offen?** — Keine funktionsfähige VS-Code-Extension in
   `extensions/vscode-drift/` mit Drift-MCP-Integration? Dispatch
   auf `drift-feature-08-vscode-extension.prompt.md`.
6. **Alle vier erledigt?** — Epoche B abgeschlossen. Empfehlung:
   Item-04-Retrospektive starten, Epoche C erwägen.

## Push-Gates-Reminder

Bevor irgendein Feature-Prompt endet, müssen die lokalen Push-Gates
grün sein. Der Orchestrator trägt im Run-Artefakt eine
Vorab-Checkliste ein, die der Feature-Prompt durchläuft:

- Alle Tests grün (quick no-smoke + precision-recall)
- FMEA / Risk-Register / Fault-Trees / STRIDE aktuell
- Feature-Evidence-JSON unter `benchmark_results/vX.Y.Z_feature_*.json`
- CHANGELOG-Eintrag (konsistent mit `pyproject.toml`-Version)
- `Decision: ADR-NNN` im Commit-Body

## Artefakte

```
work_artifacts/epoch_b_orchestrator_<YYYY-MM-DD>/
    run.md                     # Dispatch-Entscheidung + Begründung
    gate_check.md              # Ergebnis der ADR-Vorfinden-Prüfung
```

## Nicht Teil dieses Prompts

- Kein eigener Code.
- Keine ADR-Erstellung.
- Keine Priorisierung entgegen der Reihenfolge-Matrix ohne Begründung.
- Keine Status-Flips an ADR-084 oder Sub-ADRs.
