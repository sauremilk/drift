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
- Entscheidung: [ZULÄSSIG / ABBRUCH]
- Begründung: [ein Satz]
```

**Bei Entscheidung ABBRUCH:** Keine weitere Umsetzung. Stattdessen: kurze Erklärung, welches Kriterium verletzt wird und was stattdessen priorisiert werden sollte.

**Das Gate darf nicht übersprungen werden.** Auch nicht bei kleinen Änderungen, Refactorings oder scheinbar offensichtlichen Aufgaben.

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

## Automatisierte Release-Pipeline für Coding-Agenten

**WICHTIG:** Nach jeder erfolgreichen Code-Änderung an `src/drift/` MUSS der Agent automatisch den Release-Workflow durchführen.

Siehe: `.github/instructions/drift-release-automation.instructions.md`

### Release-Workflow (für Agenten verpflichtend)

1. **Tests ausführen** (schnelle Tests ohne `--run-slow`)
2. **Version berechnen** (Semantic Versioning basierend auf Commit-Mitteilungen)
3. **CHANGELOG aktualisieren** (automatisch aus Commit-History)
4. **Committen** (Version + CHANGELOG)
5. **Tagen** (annotierter Git Tag mit Versionsnummer)
6. **Pushen** (zu master + Tag)
7. **Warten auf Workflow** (.github/workflows/publish.yml triggert automatisch → PyPI Publikation)

**Commit-Nachricht-Format für Versionsbumps:**
- `feat: ...` → MINOR Versions-Bump (0.x.0)
- `fix: ...` → PATCH Versions-Bump (0.0.x)
- `BREAKING CHANGE: ...` oder `BREAKING: ...` → MAJOR Versions-Bump (x.0.0)

**Befehl für vollständigen Release:**
```bash
python scripts/release_automation.py --full-release
```

Dieser Befehl:
- Führt Quick-Tests durch (stoppt bei Fehler)
- Berechnet automatisch die nächste Versionsnummer
- Aktualisiert CHANGELOG.md
- Erstellt Release-Commit
- Erstellt Git Tag
- Pushed alles zu GitHub
- Triggert automatisch GitHub Release + PyPI Publikation

---

## Entscheidungsregel bei Unklarheit (Policy §16)

> Wähle die Option, die die größte Unsicherheit reduziert.
> Sind mehrere gleich gut: höchsten Erkenntniswert pro Aufwandseinheit.
> Ist keine Option hinreichend begründet: **keine Umsetzung**.

---

## Schlussbestimmung

Diese Policy ist verbindlich (Policy §18).
Abweichungen sind nur zulässig wenn: dokumentiert, begründet, als Ausnahme gekennzeichnet.
Im Zweifel gilt: geringerer Interpretationsspielraum, höherer Erkenntniswert.

---

## Schnellreferenz für Agenten

Aktueller Release-Stand: **v0.8.2** (2026-03-28)

Vollständiger Developer Guide: **[DEVELOPER.md](../DEVELOPER.md)**

### Architektur (Datenfluss)

```
ingestion/ → signals/ → scoring/ → output/
  AST + Git     15 Detektoren  Score+Severity   Rich/JSON/SARIF
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
| **Release (vollständig)** | `python scripts/release_automation.py --full-release` |
| Release: nur Version berechnen | `python scripts/release_automation.py --calc-version` |
| Release: CHANGELOG aktualisieren | `python scripts/release_automation.py --update-changelog` |

### Verzeichnisstruktur

| Pfad | Inhalt |
|------|--------|
| `src/drift/signals/` | 15 Signale (PFS, AVS, MDS, EDS, TVS, SMS, DIA, BEM, TPD, GCD, NBV, BAT, ECM, COD, CCC) |
| `src/drift/ingestion/` | AST-Parsing, Git-History, File-Discovery |
| `src/drift/scoring/` | Composite-Score, Module-Scores, Severity |
| `src/drift/output/` | Rich-Terminal, JSON, SARIF |
| `src/drift/commands/` | Click-CLI-Subcommands |
| `tests/` | 27+ Testdateien, conftest.py mit tmp_repo Fixture |
