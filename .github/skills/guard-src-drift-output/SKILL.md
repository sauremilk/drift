---
name: guard-src-drift-output
description: "Drift-generierter Guard fuer `src/drift/output`. Aktiv bei Signalen: EDS. Konfidenz: 0.95. Verwende diesen Skill wenn du Aenderungen an `src/drift/output` planst oder wiederholte Drift-Findings (EDS) fuer dieses Modul bearbeitest."
argument-hint: "Beschreibe welches Ausgabeformat (rich/json/markdown/llm/badge) geaendert wird und warum."
---

# Guard: `src/drift/output`

`src/drift/output` enthaelt 16 Formatter-Dateien: `rich_output.py`, `json_output.py`, `markdown_report.py`, `llm_output.py`, `badge_svg.py`, `guided_output.py`, `grouping.py`, u.a. Jede Datei verantwortet genau ein Ausgabeformat. EDS entsteht wenn Formatter anfangen zu berechnen was sie nur rendern sollten.

**Konfidenz: 0.95** — das Output-Modul hat den schwersten EDS-Befund: komplexe Verschraenkung zwischen Formatierung, Aggregation und Empfehlungslogik.

## When To Use

- Du aenderst wie Findings angezeigt, formatiert oder gerendert werden
- Du fuegest ein neues Ausgabeformat hinzu
- Du aenderst `rich_output.py`, `json_output.py`, `markdown_report.py` oder `guided_output.py`
- Drift meldet EDS fuer eine Datei in `src/drift/output/`

## Warum dieses Modul kritisch ist

**EDS** tritt hier auf weil Formatter historisch begannen, eigene Aggregate zu berechnen:
- `guided_output.py` kennt Scoring-Logik, die eigentlich in `scoring/` liegt
- `markdown_report.py` aggregiert Finding-Counts, die eigentlich in `models/` stehen sollten
- `rich_output.py` hat Farb-Logik UND Layout-Logik UND Conditional-Logik gemischt

Jede neue Berechnung in einem Formatter verstaerkt diese Verschraenkung.

## Core Rules

1. **Formatter berechnen nicht — sie rendern** — ein Formatter erhaelt ein `RepoAnalysis`- oder `list[Finding]`-Objekt und gibt formattierten Text/Dict/SVG zurueck. Keine eigene Score-Berechnung, kein eigenes Grouping-Erstellen.

2. **Gemeinsame Ausgabe-Logik gehoert in `grouping.py`** — wenn zwei Formatter dieselbe Sortier- oder Gruppierungslogik brauchen, gehoert sie in `grouping.py`. Kein Copy-Paste zwischen Formattern.

3. **`json_output.py` ist Single Source of Truth fuer das JSON-Schema** — das Schema in `drift.output.schema.json` muss mit dem tatsaechlichen Output von `json_output.py` uebereinstimmen. Aenderungen an einem erfordern Aenderungen am anderen.

4. **Neue Ausgabeformate als eigene Datei** — kein neues Format als zusaetzliche Funktion in `rich_output.py` oder `json_output.py`. Eine neue Datei wie `sarif_output.py` oder `csv_output.py` ist der richtige Weg.

5. **`RepoAnalysis.preflight` direkter Zugriff** — in `markdown_report.py` und anderen Formattern `analysis.preflight` direkt nutzen (typed), nicht `getattr(analysis, 'preflight', None)`. Das Modell hat einen definierten Typ.

## Iron Law

> **Kein Formatter darf `scoring/`-Module direkt importieren.** Die Scores sind bereits in `RepoAnalysis` enthalten. Doppeltes Scoring in Formattern erzeugt Inkonsistenz.

## Review Checklist

- [ ] Neuer Formatter hat eigene Datei, importiert keine `scoring/`-Module
- [ ] Gemeinsame Logik in `grouping.py`, nicht inline dupliziert
- [ ] `json_output.py`-Aenderungen: Schema in `drift.output.schema.json` aktualisiert
- [ ] `markdown_report.py` nutzt `analysis.preflight` direkt (kein `getattr`)
- [ ] `drift nudge` zeigt `safe_to_commit: true`
- [ ] Keine neuen EDS-Findings in `src/drift/output/`

## References

- [src/drift/output/grouping.py](../../../src/drift/output/grouping.py) — Gemeinsame Gruppierungs-Logik
- [src/drift/output/json_output.py](../../../src/drift/output/json_output.py) — Kanonisches JSON-Format
- [drift.output.schema.json](../../../drift.output.schema.json) — JSON-Output-Schema
- [src/drift/models/_findings.py](../../../src/drift/models/_findings.py) — `RepoAnalysis`-Modell
