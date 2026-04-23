---
id: ADR-061
status: proposed
date: 2026-04-11
supersedes:
---

# ADR-061: Pflichtmaessige Phasen-Telemetrie im Analyze-Standard

## Kontext

Performance-Optimierung wurde bisher oft auf Basis der Gesamtlaufzeit (`analysis_duration_seconds`) priorisiert. Das reduziert die Praezision bei Bottleneck-Analysen, weil unklar bleibt, ob Verzoegerungen in Discovery, Parsing, Git-History, Signalausfuehrung oder Ergebnisaufbereitung entstehen.

## Entscheidung

Drift fuehrt verpflichtende, standardmaessig aktive Phasen-Telemetrie ein und gibt fuer jeden Analyse-Lauf diese Zeiten aus:

- `discover_seconds`
- `parse_seconds`
- `git_seconds`
- `signals_seconds`
- `output_seconds`
- `total_seconds`

Die Werte werden als additive Erweiterung im JSON-Output unter `summary.phase_timing` publiziert und im Rich-Output sichtbar gemacht.

Nicht Teil der Entscheidung:

- per-signal Mikro-Telemetrie
- externes Telemetrie-Backend
- optionales Opt-in Flag fuer Phasen-Telemetrie

## Begründung

Die Entscheidung adressiert direkt eine zentrale Unsicherheit in der Laufzeitanalyse und verbessert die Glaubwuerdigkeit von Performance-Arbeit:

- Bottlenecks koennen reproduzierbar pro Phase lokalisiert werden.
- Maßnahmen werden evidenzbasiert priorisiert statt anhand von Vermutungen.
- Output bleibt rueckwaertskompatibel, da bestehende Felder erhalten bleiben.

Alternativen:

- Nur Gesamtdauer beibehalten: verworfen, da fuer gezielte Optimierung zu grob.
- Optionales Telemetrie-Flag: verworfen, da Pflichtbeobachtung fuer kontinuierliche Verbesserung erforderlich ist.

## Konsequenzen

- Analyzer/Pipeline fuehren zusaetzliche `time.monotonic()`-Messungen aus.
- JSON/Rich-Vertraege werden additiv erweitert.
- Parse/Git koennen innerhalb der Ingestion parallel laufen; Teilzeiten sind wall-clock pro Segment und nicht zwingend strikt summierbar ohne Ueberlappung.
- Audit-Pflichten nach Policy §18 greifen fuer Output-Path-Aenderungen.

## Validierung

Technische Validierung erfolgt ueber:

```bash
pytest tests/test_json_output.py -q
pytest tests/test_output_golden.py -q
pytest tests/test_rich_output_boost.py -q
pytest tests/test_pipeline_components.py -q
```

Akzeptanzkriterien:

- `summary.phase_timing` ist in JSON immer vorhanden.
- Alle Phasenfelder sind numerisch und nicht negativ.
- Bestehendes Feld `analysis_duration_seconds` bleibt erhalten.
- Rich-Output zeigt den Phasenblock standardmaessig.

Lernzyklus-Ergebnis nach Policy §10: **unklar** (vor Implementierungs-Merge), anschliessend zu aktualisieren auf `bestaetigt` oder `widerlegt` anhand Laufzeitmessungen auf Referenz-Repos.
