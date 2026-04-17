---
name: guard-src-drift-scoring
description: "Drift-generierter Guard fuer `src/drift/scoring`. Aktiv bei Signalen: EDS. Konfidenz: 0.62. Verwende diesen Skill wenn du Aenderungen an `src/drift/scoring` planst oder wiederholte Drift-Findings (EDS) fuer dieses Modul bearbeitest."
argument-hint: "Beschreibe welche Scoring-Logik (Gewichte, Grade-Bands, Prioritaets-Formel) geaendert wird."
---

# Guard: `src/drift/scoring`

`src/drift/scoring` berechnet aus rohen Signal-Findings den aggregierten Repo-Score, die Grade-Bands (A-F) und die Finding-Prioritaeten. EDS entsteht wenn Scoring-Logik und Prioritaets-Logik ineinander verschraenkt werden statt sauber getrennt zu bleiben.

**Konfidenz: 0.62** — EDS-Risiko moderat; entsteht hauptsaechlich wenn Scoring-Formeln komplexer werden ohne Refaktorierung.

## When To Use

- Du aenderst Signal-Gewichte oder Scoring-Formeln
- Du veraenderst Grade-Band-Grenzen (A-F)
- Du aenderst `finding_priority.py` oder Prioritaets-Logik
- Du fuegest neue Score-Dimensionen hinzu
- Drift meldet EDS fuer `src/drift/scoring/`

## Warum EDS hier entsteht

Scoring-EDS entsteht wenn:
- `finding_priority.py` beginnt Scores neu zu berechnen anstatt vorgefertigte Scores zu nutzen
- Gewichte an mehreren Stellen definiert sind (z.B. in `scoring.py` UND in `finding_priority.py`)
- Grade-Berechnung und Prioritaets-Sortierung in derselben Funktion passieren
- Neue Score-Dimensionen als Sonderfaelle in bestehende Formeln eingebaut werden

## Core Rules

1. **Scoring und Priorisierung sind getrennt** — `scoring.py` berechnet numerische Werte. `finding_priority.py` sortiert und filtert anhand dieser Werte. Kein Scoring in `finding_priority.py`.

2. **Gewichte sind an einem Ort** — Signal-Gewichte existieren genau einmal, in der zentralen Gewichtstabelle in `scoring/`. Kein hartkodierter Gewichts-Faktor ausserhalb dieser Datei.

3. **Grade-Bands durch ADR absichern** — Aenderungen an Grade-Band-Grenzen sind Verhaltensaenderungen die Nutzer direkt betreffen. Sie erfordern einen ADR-Eintrag und Feature-Evidenz in `benchmark_results/`.

4. **Scoring-Aenderungen mit `kpi_snapshot.json` verifizieren** — nach jeder Scoring-Aenderung den Self-Analysis-Score mit dem Benchmark-Baseline vergleichen. Regression ist ein Commit-Blocker.

5. **Neue Score-Dimensionen als eigene Funktion** — kein neues Scoring-Kriterium als Sonderfall in einer bestehenden Formel. Neue Dimension = neue, klar benannte Funktion.

## Arbeitsablauf bei Scoring-Aenderungen

```bash
# 1. Baseline dokumentieren (vor der Aenderung)
drift analyze --repo . --format json > /tmp/before.json

# 2. Aenderung vornehmen

# 3. Nach der Aenderung vergleichen
drift analyze --repo . --format json > /tmp/after.json

# 4. Score-Delta pruefen
python -c "
import json
b = json.load(open('/tmp/before.json'))
a = json.load(open('/tmp/after.json'))
print('Before:', b.get('grade'), b.get('drift_score'))
print('After:', a.get('grade'), a.get('drift_score'))
"
```

## Review Checklist

- [ ] Scoring und Priorisierung in separaten Funktionen/Dateien
- [ ] Gewichte nur an einem Ort definiert
- [ ] Grade-Band-Aenderungen: ADR-Eintrag vorhanden
- [ ] Self-Analysis-Score vor/nach Aenderung verglichen
- [ ] `drift nudge` zeigt `safe_to_commit: true`
- [ ] Keine neuen EDS-Findings in `src/drift/scoring/`

## References

- [src/drift/finding_priority.py](../../../src/drift/finding_priority.py) — Finding-Priorisierung
- [benchmark_results/kpi_snapshot.json](../../../benchmark_results/kpi_snapshot.json) — Score-Baseline
- [decisions/](../../../decisions/) — ADR-Verzeichnis
- [DEVELOPER.md](../../DEVELOPER.md)
