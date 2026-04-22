# Drift — Verbindliche Arbeitsgrundlage für alle Agenten

**Diese Datei ist für alle Copilot-Agenten, Coding-Agenten und KI-Assistenten im Drift-Workspace bindend.**

Die vollständige Policy befindet sich in:
`POLICY.md` (Workspace-Root)

Lies diese Datei **vor jeder Arbeit** vollständig, sofern sie nicht bereits im Kontext ist.
Die Policy ist ein Vertrag — keine Empfehlung, kein Vorschlag.

---

## PFLICHT-GATE: Zulässigkeitsprüfung vor jeder Aufgabe

**Vor jeder Antwort, die eine Änderung, ein Feature, eine Analyse oder eine Umsetzung enthält, MUSS der Agent dieses Gate sichtbar ausgeben:**

```
### Drift Policy Gate
- Aufgabe: [Kurzbeschreibung der Aufgabe in einem Satz]
- Zulassungskriterium erfüllt: [JA / NEIN] → [welches Kriterium: Unsicherheit / Signal / Glaubwürdigkeit / Handlungsfähigkeit / Trend / Einführbarkeit]
- Ausschlusskriterium ausgelöst: [JA / NEIN] → [falls JA: welches]
- Roadmap-Phase: [Phase 1 / 2 / 3 / 4] — blockiert durch höhere Phase: [JA / NEIN]
- Betrifft Signal/Architektur (§18): [JA / NEIN] → falls JA: Audit-Artefakte aktualisiert: [welche]
- Entscheidung: [ZULÄSSIG / ABBRUCH]
- Begründung: [ein Satz]
```

**Bei Entscheidung ABBRUCH:** Keine weitere Umsetzung. Stattdessen: kurze Erklärung, welches Kriterium verletzt wird und was stattdessen priorisiert werden sollte.

**Korrektheitsregel:** Eine `ZULÄSSIG`-Entscheidung ist nur gültig, wenn das erfüllte Zulassungskriterium konkret zur Aufgabe passt. Generische Platzhalter wie "Signalqualität" oder "Einführbarkeit" ohne Bezug zur Aufgabe sind ungültig.

**Kompaktformat für strikt triviale Mechanikaufgaben:** Für rein mechanische, verhaltensneutrale Änderungen wie `fix: typo`, `docs: wording`, `chore: lockfile refresh` oder `test: fixture rename` ist statt des Vollformats dieses Kurzformat zulässig:

```
### Drift Policy Gate
- Trivialtask: JA
- Zulässig: JA → rein mechanisch, ohne Verhaltens-, Policy-, Architektur- oder Signaleffekt
```

**Nicht trivial** sind insbesondere Änderungen an Policy, Instructions, Prompts, Skills, Agents, Signalen, Output-Formaten, CLI-Verhalten, Tests mit Verhaltensabsicherung oder Architekturgrenzen.

---

## Primärmodus bei Prompt-Engineering

Wenn eine Aufgabe Prompts, Instructions, Skills, Agents oder diese Datei selbst betrifft,
arbeitet der Agent im **Prompt-Engineering-Modus**. Ziel ist nicht schönere Prosa,
sondern härtere, operativere und reviewbare Agentensteuerung.

**Betroffene Pfade:**
- `.github/prompts/**`
- `.github/instructions/**`
- `.github/skills/**`
- `.github/agents/**`
- `.github/AGENTS.md`
- `.github/copilot-instructions.md`

**Detaillierte Zusatzregeln:**
- Routing: `.github/instructions/drift-context-routing.instructions.md`
- Prompt-Engineering: `.github/instructions/drift-prompt-engineering.instructions.md`
- Workflow-Skill: `.github/skills/drift-agent-prompt-authoring/SKILL.md`

### Zuerst das richtige Primitive wählen

| Bedarf | Richtiges Primitive |
|--------|---------------------|
| Repo-weite, immer geltende Regeln | `copilot-instructions.md` |
| Datei- oder Ordner-spezifische Regeln | `*.instructions.md` |
| Wiederverwendbarer Operator-Workflow | `SKILL.md` |
| Konkreter mehrphasiger Ablauf mit Ziel und Artefakten | `*.prompt.md` |
| Isolierter Spezialmodus mit eigener Tool-/Kontextgrenze | `*.agent.md` |

**Falsches Primitive = schwacher Prompt.**
Eine Datei darf nur das regeln, wofür ihr Primitive gedacht ist.

### Nicht verhandelbare Schärferegeln

1. **Deutsch und modellunabhängig.** Keine Modellnamen, keine vendor-spezifischen Prompt-Tricks.
2. **Description ist Discovery-Oberfläche.** Das `description`-Feld muss Triggerwörter,
   Task-Typ und Scope explizit enthalten.
3. **`applyTo` so eng wie möglich.** `applyTo: "**"` nur für wirklich universelle Regeln.
4. **Ein Problem pro Datei.** Keine Mischdateien für Policy, Testing, Release und Prompt-Stil.
5. **Keine Parallel-Policy.** Shared Partials, Policy und Push-Gates referenzieren statt duplizieren.
6. **Keine weichen Verben ohne Vertrag.** Wörter wie "analysiere", "verbessere",
   "prüfe gründlich", "wenn möglich" oder "robust" sind nur zulässig, wenn Inputs,
   Schritte, Ergebnisform und Abbruchkriterium definiert sind.
7. **Keine Halluzinationsflächen.** Keine erfundenen Flags, Dateien, Tools, Issue-Ziele,
   Pfade oder angeblich vorhandenen Artefakte.
8. **Prompts erzeugen Evidenz.** Jeder Prompt muss in Beobachtung, Artefakt, Entscheidung,
   Maßnahme oder sauberem Abbruch enden - nie nur in Prosa.

### Mindestvertrag für jeden guten Prompt

Jeder neue oder geänderte Prompt, Skill oder jede Instruction muss explizit benennen:

- Ziel und Scope
- Eingaben, Voraussetzungen und relevante Umgebungsannahmen
- welches Tool oder welcher Befehl wofür eingesetzt wird
- erwartete Artefakte oder das Ausgabeformat
- Bewertungslogik oder Entscheidungskriterien
- Fehlerpfad, Fallback oder Eskalation
- klare Stop-Bedingung
- referenzierte Single Sources of Truth

Fehlt einer dieser Punkte, ist die Anweisung zu weich.

### Single Sources of Truth für Prompt-Arbeit

Diese Dateien werden wiederverwendet statt kopiert:

- `.github/prompts/_partials/konventionen.md`
- `.github/prompts/_partials/bewertungs-taxonomie.md`
- `.github/prompts/_partials/issue-filing.md`
- `.github/prompts/_partials/issue-filing-external.md`
- `.github/skills/drift-agent-prompt-authoring/SKILL.md`
- `.github/instructions/drift-policy.instructions.md`
- `.github/instructions/drift-context-routing.instructions.md`
- `.github/instructions/drift-prompt-engineering.instructions.md`

### Repo-spezifische Prompt-Regeln

- Interne Drift-Prompts arbeiten gegen den Workspace und referenzieren die Dev-Version.
- Field-Test-Prompts arbeiten gegen externe Repositories und reichen Issues immer an
  `mick-gsk/drift`, nie an das Ziel-Repository.
- Prompt-Arbeit ist nur zulässig, wenn sie Erkenntnis, Vergleichbarkeit, Einführbarkeit
  oder Signalqualität verbessert - nicht wenn sie nur mehr Text produziert.

---

## Policy als Single Source of Truth

`POLICY.md` ist die alleinige Quelle fuer Produkt- und Priorisierungsregeln. Diese Datei dupliziert **nicht** mehr die Inhalte aus Policy §6, §8, §13, §14, §16 oder §18.

Fuer Agentenarbeit gilt deshalb:

- Policy und Gate-Logik: `POLICY.md` und `.github/instructions/drift-policy.instructions.md`
- Risk-Audit-Pflichten: `.github/instructions/drift-policy.instructions.md`
- Push-Vorbereitung: `.github/instructions/drift-push-gates.instructions.md`
- Release-Automation: `.github/instructions/drift-release-automation.instructions.md` und `.github/instructions/drift-release-mandatory.instructions.md`
- MCP-Fix-Loop: `.github/prompts/drift-fix-loop.prompt.md`

Wenn diese Datei und eine Single Source of Truth kollidieren, gilt immer die Single Source of Truth.

---

## Drift-Version-Freshness (Pflicht für alle Agenten)

Jeder Agent, der `drift` ausfuehrt, analysiert oder konfiguriert, MUSS sicherstellen,
dass er die aktuellste verfuegbare Version nutzt. Ein Test oder eine Analyse gegen eine
veraltete Version hat keinen Erkenntniswert.

### Interner Workspace (Entwicklungsversion)

Wenn ein Agent im Drift-Workspace selbst arbeitet, MUSS er die Dev-Version verwenden:

```bash
pip install -e '.[dev]'   # Dev-Version aus Workspace installieren / auffrischen
drift --version           # Muss mit pyproject.toml uebereinstimmen
```

Der MCP-Server in `.vscode/mcp.json` zeigt auf das Workspace-venv und ist immer
automatisch aktuell, wenn `pip install -e .` ausgefuehrt wurde.

### Externe Repositories / Field-Tests

Wenn ein Agent drift in einem externen Repository einsetzt, MUSS er zuerst upgraden:

```bash
pip install --upgrade drift-analyzer   # Immer zuerst: aktuellste PyPI-Version
drift --version                        # Version im Report dokumentieren
```

Falls das Upgrade scheitert (Netzwerk, Index-Fehler), MUSS dies im Report
dokumentiert werden und die tatsaechlich verwendete Version explizit angegeben sein.

### Version im Report

Jede Analyse, jedes Audit-Artefakt und jeder Field-Test-Report MUSS den Output von
`drift --version` als Metadatum enthalten — entweder im Header oder im Repo-Profil.

### Autoritativer Versions-Freshness-Standard

Die vollstaendige Freshness-Regel fuer Prompts ist Single Source of Truth in
`.github/prompts/_partials/konventionen.md` (Abschnitt "Versions-Freshness").

---

## Agent-Delegation-Boundaries

### Eigenständig (ohne Maintainer-Approval)

- ADR-Templates vorbefüllen (Status bleibt `proposed`)
- Backlog-Items vorschlagen (Status `proposed`)
- Audit-Artefakte gemäß §18 aktualisieren
- Tests schreiben und ausführen
- Lint/Typecheck-Fehler beheben
- Fixture-Dateien erstellen
- CHANGELOG-Einträge vorbereiten

### Erfordert Maintainer-Approval

- ADR-Status auf `accepted` oder `rejected` setzen
- Backlog-Reihenfolge ändern
- Signal-Heuristik oder Scoring-Gewichte ändern
- Policy-Änderungen vorschlagen (nicht eigenständig umsetzen)
- Commits pushen
- Issues/PRs kommentieren oder schließen
- Neue Signale implementieren

---

## Agent Workflow Shortcuts (Pflicht)

Fuer jeden Coding-Agenten im Drift-Workspace gelten folgende Pflicht-Shortcuts.
Die detaillierte Referenz liegt in `.github/instructions/drift-agent-quickref.instructions.md`.

| Workflow-Moment | Pflicht-Befehl |
|---|---|
| Vor dem ersten Edit bei `feat:` | `make feat-start` |
| Vor dem ersten Edit bei `fix:` | `make fix-start` |
| Gates vor Push pruefen | `make gate-check COMMIT_TYPE=<feat\|fix\|chore>` |
| Audit-Pflichten pruefen (bei signals/ingestion/output) | `make audit-diff` |
| CHANGELOG-Snippet erzeugen | `make changelog-entry COMMIT_TYPE=<typ> MSG='<text>'` |
| Session-Handover anlegen | `make handover TASK='<beschreibung>'` |
| Unbekanntes Skript suchen | `make catalog` oder `make catalog ARGS='--search <stichwort>'` |
| Vollstaendiger CI-Check | `make check` |

**Verwendungsregel:** Ein Agent DARF `CHANGELOG.md` nicht manuell formattieren —
er MUSS stattdessen `make changelog-entry` aufrufen und den Output einfuegen.
Ein Agent SOLL `make gate-check` vor jedem Push aufrufen, damit kein Hook-Abbruch
durch fehlende Artefakte entsteht.

---

## MCP Fix-Loop — Optimierter Workflow für Finding-Behebung

Wenn ein Agent Drift-Findings ueber MCP-Tools behebt, gilt ausschliesslich der Workflow in `.github/prompts/drift-fix-loop.prompt.md`. Diese Datei wiederholt den Ablauf nicht; sie verweist nur auf die verbindliche Quelle.

---

## Post-Edit Drift-Nudge (Pflicht für alle Coding-Agenten)

Nach **jeder** Dateiänderung MUSS ein Coding-Agent `drift_nudge` als schnellen Regression-Detektor aufrufen. Dieser Workflow ist verbindlich:

1. **Nach jedem Edit:** `drift_nudge(changed_files=["<geaenderte_datei>"], timeout_ms=1000)` aufrufen.
2. **`latency_exceeded: true` UND `baseline_created: false`:** Nudge ist genuinely zu langsam → diesen und alle weiteren Nudge-Aufrufe im laufenden Task überspringen. Stattdessen am Ende `drift_diff` verwenden.
2b. **`latency_exceeded: true` UND `baseline_created: true`:** Cold-Start (Baseline wurde gerade neu erstellt, einmalige Kosten) → **nicht** überspringen. Nachfolgende Nudge-Aufrufe sind schnell (~0.2 s).
3. **`revert_recommended: true`:** Edit **sofort revertieren**. Bedeutet: `direction == "degrading"` **und** `safe_to_commit == false`. Neuen Ansatz wählen, dann erneut implementieren.
4. **`auto_fast_path: true`:** Alle Signale liefen mit exakter Konfidenz (nur file-local, kein Cross-File-Estimated). Das Ergebnis ist vollständig verlässlich.
5. **`auto_fast_path: false`:** MDS/AVS sind estimated (Baseline-Carryforward). Bei Unsicherheit zusätzlich `drift_diff` oder `drift_scan` aufrufen.

**Schnell-Referenz:**

| Feld | Bedeutung | Agent-Aktion |
|------|-----------|--------------|
| `revert_recommended: true` | Edit verschlechtert Architektur messbar | **Edit revertieren, neu versuchen** |
| `latency_exceeded: true` + `baseline_created: false` | Nudge genuinely zu langsam (>1 s) | Weitere Nudge-Calls überspringen |
| `latency_exceeded: true` + `baseline_created: true` | Cold-Start: Baseline wurde neu erstellt (einmalig) | **Nicht** überspringen; nächste Calls sind schnell |
| `auto_fast_path: true` | Nur file-local Signale, 100 % exakt | Ergebnis vertrauen |
| `auto_fast_path: false` | Cross-file Signale geschätzt | Ggf. Vollscan ergänzen |
| `direction: "improving"` | Architekturqualität verbessert | Weiter |
| `direction: "stable"` | Kein messbarer Effekt | Weiter |

**Grenzen:** Signale mit `cross_file`-Scope (MDS, AVS) sind im Nudge-Modus estimated — sie brauchen für volle Präzision einen Vollscan (`drift_diff`).

---

## Arbeitsnavigation

Die operative Referenz liegt in den folgenden Dateien und soll von Agenten bevorzugt gelesen werden statt hier gepflegte Kurzfassungen zu erraten:

- Developer-Workflow und verifizierte Kommandos: `DEVELOPER.md`
- Prompt-Bibliothek: `.github/prompts/README.md`
- Prompt-Authoring: `.github/skills/drift-agent-prompt-authoring/SKILL.md`
- Kontext-Routing: `.github/instructions/drift-context-routing.instructions.md`
- Push-Gates: `.github/instructions/drift-push-gates.instructions.md`
- Release-Regeln: `.github/instructions/drift-release-automation.instructions.md` und `.github/instructions/drift-release-mandatory.instructions.md`

Veraltbare Angaben wie feste Versionsstaende, statische Signallisten oder duplizierte Kommandotabellen gehoeren nicht in diese Datei.
