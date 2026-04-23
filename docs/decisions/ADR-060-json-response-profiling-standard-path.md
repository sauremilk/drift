---
id: ADR-060
status: proposed
date: 2026-04-11
supersedes:
---

# ADR-060: JSON-Response-Profiling als Standardpfad

## Kontext

Die JSON-Ausgabepfade materialisieren derzeit teils teure Felder (insbesondere Recommendation-basierte Felder) auch dort, wo ein schlanker Default-Fluss ausreicht. Das erzeugt vermeidbare CPU-Kosten in Agent- und CI-Pfaden.

## Entscheidung

Wir etablieren einen Profiling-Pfad mit zwei Ebenen:

- `concise`: schlanke Finding-Objekte als Standardpfad in JSON-Responses.
- `detailed`: additive Materialisierung zusaetzlicher Felder.

In dieser Iteration:

- Gemeinsame Basis-Payload fuer Findings wird zentralisiert.
- CLI `analyze --format json` erhaelt `--response-detail {concise,detailed}`.
- `analysis_to_json(..., response_detail=...)` steuert, ob `findings`/`findings_suppressed` als schlanke oder detaillierte Payload gerendert werden.
- Default fuer CLI bleibt `detailed`, um unbeabsichtigte Breaking-Changes im aktuellen Release zu vermeiden.

Nicht im Umfang:

- Keine Aenderung an Scoring oder Signalheuristiken.
- Kein Schema-Major-Bump in dieser Iteration.

## Begründung

Die Trennung in schlanke Basis und additive Detailfelder reduziert Serialisierungskosten und schafft einen klaren, wiederverwendbaren Vertrag fuer API und CLI. Durch Beibehaltung des CLI-Defaults bleibt Kompatibilitaet gewahrt.

## Konsequenzen

Positiv:

- Bessere CPU-Effizienz fuer concise-Pfade.
- Weniger doppelte Serializer-Logik.
- Klarere Semantik fuer Consumer (`concise` vs. `detailed`).

Trade-offs:

- Zusaetzlicher Pflegeaufwand fuer zwei Profilpfade.
- Testmatrix muss beide Detailgrade abdecken.

## Validierung

- `pytest tests/test_json_output.py -q`
- `pytest tests/test_output_golden.py -q`
- `pytest tests/test_api_and_ts_arch_boost.py -q`
- `python scripts/check_risk_audit.py --diff-base origin/main`

Policy §10 Lernzyklus-Ergebnis: unklar.
