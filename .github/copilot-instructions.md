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

**Das Gate darf nicht übersprungen werden.** Auch nicht bei kleinen Änderungen, Refactorings oder scheinbar offensichtlichen Aufgaben.

---

## Risk-Audit-Pflicht bei Signalarbeit (POLICY §18)

Wenn eine Aufgabe Dateien unter `src/drift/signals/`, `src/drift/ingestion/` oder `src/drift/output/` ändert, MUSS der Agent die betroffenen Audit-Artefakte aktualisieren:

| Änderung | Pflicht-Aktualisierung |
|----------|------------------------|
| Neues/geändertes Signal | `audit_results/fmea_matrix.md` (FP + FN) + `audit_results/fault_trees.md` (FT-Pfade) + `audit_results/risk_register.md` |
| Neuer Input-/Output-Pfad | `audit_results/stride_threat_model.md` (Trust Boundary) + `audit_results/risk_register.md` |
| Precision/Recall Δ > 5% | `audit_results/fmea_matrix.md` (RPNs) + `audit_results/risk_register.md` (Messwerte) |

**Schutzmechanismus:** Pre-Push-Hook und CI blockieren automatisch Pushes mit Signal-Änderungen ohne zugehörige Audit-Updates. Der Agent muss kein separates Gate ausgeben — die Zeile "Betrifft Signal/Architektur" im PFLICHT-GATE genügt.

---

## Nicht verhandelbare Grundregeln

### Was Drift ist
Drift ist ein statischer Analyzer zur Erkennung architektonischer Kohärenzprobleme.
Zweck: strukturelle Erosion erkennen, benennen, priorisieren, über Zeit vergleichbar machen.

### Was Drift nicht ist
- Drift ist kein Tool, das lediglich Probleme auflistet.
- Drift erzeugt keine dekorativen Ergebnisse.
- Drift priorisiert keine Ergebnisse ohne realen Zusammenhang mit struktureller Kohärenz.

---

## Absolute Ausschlusskriterien für neue Arbeit

**Keine Aufgabe darf begonnen werden**, die ausschließlich folgendes erzeugt:
- mehr Ausgabe ohne besseren Erkenntniswert
- mehr Komplexität ohne klaren Nutzen
- mehr Oberfläche ohne bessere Analyse
- mehr Analyse ohne Validierung des Ergebnisses
- mehr technische Ausarbeitung ohne Beitrag zur Produktwirkung
- einen Nutzen, der nicht eindeutig benennbar ist

---

## Priorisierungsformel (Policy §6)

```
Priorität = (Unsicherheit × Schaden × Nutzbarkeit) / Aufwand
```

Bei konkurrierenden Vorhaben gilt diese feste Reihenfolge:
1. Glaubwürdigkeit erhalten
2. Signalpräzision verbessern
3. Verständlichkeit der Befunde verbessern
4. False Positives / False Negatives reduzieren
5. Einführbarkeit verbessern
6. Trendanalyse verbessern
7. Zusätzliche Features, Formate, Komfortmerkmale

**Eine niedrigere Stufe verdrängt niemals eine höhere.**

---

## Qualitätsanforderungen an jeden Befund (Policy §13)

Jeder Befund muss besitzen:
- technische Nachvollziehbarkeit
- Reproduzierbarkeit
- eindeutige Zuordnung zu einer Ursache
- klare Benennung der betroffenen Stelle
- nachvollziehbare Begründung
- erkennbare nächste Maßnahme

Ein Befund ohne klare Begründung ist **unzulässig**.
Ein Befund ohne mögliche nächste Maßnahme ist **unvollständig**.

---

## Zulassungskriterien für neue Arbeit (Policy §8)

Eine Aufgabe darf nur begonnen werden, wenn sie mindestens eines erfüllt:
- reduziert eine zentrale Unsicherheit
- verbessert die Signalqualität
- erhöht die Glaubwürdigkeit
- erhöht die Handlungsfähigkeit
- verbessert die Trendfähigkeit
- erleichtert die Einführbarkeit

---

## Roadmap-Phasen-Hierarchie (Policy §14)

**Phase 1 — Vertrauen** (Vorrang vor allem anderen):
Nachvollziehbarkeit → Reproduzierbarkeit → Fehlalarmreduktion → Erklärbarkeit

**Phase 2 — Relevanz** → **Phase 3 — Einführbarkeit** → **Phase 4 — Skalierung**

Phase 4 verdrängt niemals Phase 1.
Skalierungsmaßnahmen ohne gesichertes Vertrauen sind **nachrangig**.

---

## Automatisierte Release-Pipeline (python-semantic-release)

Releases werden vollständig automatisiert durch `python-semantic-release` (PSR) in CI verwaltet.
Der CI-Workflow `.github/workflows/release.yml` läuft bei jedem Push auf `main`.

**Agenten müssen KEINEN manuellen Release-Befehl mehr ausführen.**

### Was Agenten tun müssen

1. **Conventional Commits verwenden** — PSR leitet die Versionierung aus Commit-Messages ab:
   - `feat: ...` → MINOR Versions-Bump (0.x.0)
   - `fix: ...` → PATCH Versions-Bump (0.0.x)
   - `BREAKING CHANGE: ...` oder `BREAKING: ...` → MAJOR Versions-Bump (x.0.0)
2. **Tests lokal ausführen** vor dem Commit
3. **Committen** — PSR übernimmt alles weitere nach Push

### Was PSR automatisch macht (in CI)

1. Analysiert Commits seit letztem Tag
2. Berechnet nächste Version (SemVer)
3. Aktualisiert `pyproject.toml` + `CHANGELOG.md`
4. Erstellt Release-Commit (`chore: Release X.Y.Z`)
5. Erstellt Git Tag (`vX.Y.Z`)
6. Erstellt GitHub Release
7. Baut + publiziert zu PyPI

**Lokaler Fallback** (nur bei CI-Ausfall):
```bash
python scripts/release_automation.py --full-release
```

---

## Entscheidungsregel bei Unklarheit (Policy §16)

> Wähle die Option, die die größte Unsicherheit reduziert.
> Sind mehrere gleich gut: höchsten Erkenntniswert pro Aufwandseinheit.
> Ist keine Option hinreichend begründet: **keine Umsetzung**.

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

## MCP Fix-Loop — Optimierter Workflow für Finding-Behebung

Wenn ein Agent Drift-Findings über MCP-Tools beheben soll, **muss** dieser Ablauf verwendet werden:

1. **`drift_session_start(path=".", autopilot=true)`** — ein Aufruf statt vier (bündelt validate + brief + scan + fix_plan)
2. **`drift_nudge(session_id=..., changed_files=...)`** — nach jeder Dateiänderung als schneller Inner-Loop (~0.2 s statt ~3 s für scan)
3. **`drift_fix_plan(session_id=..., max_tasks=1)`** — nächsten Task holen (immer `max_tasks=1`)
4. **`drift_diff(session_id=..., uncommitted=true)`** — nur einmal am Ende als Abschluss-Verifikation

**Verboten im Fix-Loop:**
- `drift_scan` nach jeder Dateiänderung (zu teuer, nutze `nudge`)
- `session_start` ohne `autopilot=true` (verschenkt 4 Roundtrips)
- `fix_plan` ohne `max_tasks=1` (unnötig große Responses)
- Tool-Aufrufe ohne `session_id` (verliert Kontext)

**Immer:** `agent_instruction` und `next_tool_call` aus Responses befolgen.

Vollständiger Workflow: `.github/prompts/drift-fix-loop.prompt.md`

---

## Schlussbestimmung

Diese Policy ist verbindlich (Policy §18).
Abweichungen sind nur zulässig wenn: dokumentiert, begründet, als Ausnahme gekennzeichnet.
Im Zweifel gilt: geringerer Interpretationsspielraum, höherer Erkenntniswert.

---

## Schnellreferenz für Agenten

Aktueller Release-Stand: **v2.5.1** (2026-04-06)

Vollständiger Developer Guide: **[DEVELOPER.md](../DEVELOPER.md)**

### Architektur (Datenfluss)

```
ingestion/ → signals/ → scoring/ → output/
  AST + Git     23 Detektoren  Score+Severity   Rich/JSON/SARIF
              (15 scoring-aktiv, 8 report-only)
```

### Wichtigste Kommandos

| Aufgabe | Befehl |
|---------|--------|
| Dev-Setup | `make install` |
| Alle Checks | `make check` |
| Nur Tests (schnell) | `make test-fast` |
| Lint + Autofix | `make lint-fix` |
| CI lokal replizieren | `make ci` |
| Selbstanalyse | `make self` |
| **Release** | Automatisch via PSR in CI bei Push auf `main` |
| Release: lokaler Fallback | `python scripts/release_automation.py --full-release` |
| Release: Version prüfen | `semantic-release version --print` |

### Pre-Push-Gates — PFLICHT vor jedem `git push`

Der Hook `.githooks/pre-push` (aktiv via `core.hooksPath = .githooks`) blockiert jeden Push, der eine Gate-Bedingung verletzt. **Agenten müssen VOR `git push` sicherstellen, dass alle zutreffenden Gates erfüllt sind.**

Vollständige Gate-Dokumentation: **`.github/instructions/drift-push-gates.instructions.md`**

**Kurz-Übersicht: Was löst welches Gate aus?**

| Geänderte Dateien | Erforderlich |
|---|---|
| `tagesplanung/**` | ❌ Immer blockiert |
| `feat:`-Commit | Tests + `benchmark_results/vX.Y.Z_feature_evidence.json` + `docs/STUDY.md` update |
| `feat:` oder `fix:`-Commit | `CHANGELOG.md` aktualisieren |
| `pyproject.toml` geändert | Version größer als letzter Tag + `uv.lock` aktualisieren (`uv lock`) |
| `src/drift/**` neu public `def` | Docstring hinzufügen |
| `src/drift/signals/`, `ingestion/` oder `output/` | Mind. eine Audit-Datei in `audit_results/` aktualisieren (`fmea_matrix.md`, `stride_threat_model.md`, `fault_trees.md` oder `risk_register.md`) |
| Immer | `make check` lokal bestanden (ruff + mypy + pytest + self-analysis) |

**Notfall-Bypässe** (nur wenn begründet):
```bash
DRIFT_SKIP_RISK_AUDIT=1 git push     # Audit-Gate überspringen
DRIFT_SKIP_CHANGELOG=1 git push      # Changelog-Gate überspringen
DRIFT_SKIP_DOCSTRING=1 git push      # Docstring-Gate überspringen
DRIFT_SKIP_HOOKS=1 git push          # ALLE Gates (äußerster Notfall)
```
> CI-Checks (ruff/mypy/pytest) können nicht per Env-Variable umgangen werden.

### Konventionen

- Bei ADR-Umsetzung: `Decision: ADR-NNN` Trailer im Commit-Body
- ADR-Pflicht vor Implementierung bei Änderungen an Signalen, Scoring, Output oder Architektur-Boundaries
- ADRs liegen unter `.internal/decisions/`, Templates (öffentlich) unter `decisions/templates/`
- Priorisierter Backlog: `.internal/BACKLOG.md`

### Verzeichnisstruktur

| Pfad | Inhalt |
|------|--------|
| `src/drift/signals/` | 23 Signale — 15 scoring-aktiv (PFS, AVS, MDS, EDS, TVS, SMS, DIA, BEM, TPD, GCD, NBV, BAT, ECM, COD, CCC) + 8 report-only (TSA, CXS, FOE, CIR, DCA, MAZ, ISD, HSC) |
| `src/drift/ingestion/` | AST-Parsing, Git-History, File-Discovery |
| `src/drift/scoring/` | Composite-Score, Module-Scores, Severity |
| `src/drift/output/` | Rich-Terminal, JSON, SARIF |
| `src/drift/commands/` | Click-CLI-Subcommands |
| `tests/` | 27+ Testdateien, conftest.py mit tmp_repo Fixture |
