---
id: ADR-059
status: proposed
date: 2026-04-11
supersedes:
---

# ADR-059: Persistenter Nudge-Baseline-Store ueber Prozessgrenzen

## Kontext

`nudge` in [src/drift/api/nudge.py](src/drift/api/nudge.py) profitiert heute stark von einem warmen In-Memory-Baseline-Zustand aus [src/drift/incremental.py](src/drift/incremental.py). Nach Prozessneustart fehlt diese Baseline jedoch, wodurch der erste `nudge` erneut einen teuren Full-Scan ausloest.

Das fuehrt zu vermeidbarer Latenz in Agent-Loops, CI-Vorpruefungen und lokalen Iterationen, obwohl sich Repository-Zustand und relevante Konfiguration oft nicht geaendert haben.

## Entscheidung

Wir fuehren einen lokalen, versionierten On-Disk-Baseline-Store fuer `nudge` ein.

Umfang:
- Persistente Baseline-Artefakte unter `.drift-cache/nudge_baselines/`.
- Deterministischer Key aus:
  - Repo (indirekt ueber repo-lokalen Speicherort),
  - `HEAD` Commit,
  - Config-Fingerprint,
  - Schema-Version.
- Payload enthaelt nur Baseline-Metadaten plus Findings (keine ParseResults).
- Harte Invalidierung via Key-Mismatch (kein Soft-Fallback).
- Bei Disk-Treffer wird In-Memory-Baseline hydriert (`disk_warm_hit`), um den teuren ersten `nudge` nach Neustart zu vermeiden.

Nicht im Umfang:
- Keine Persistenz kompletter ParseResults in dieser Iteration.
- Keine Aenderung von Signalheuristiken, Gewichtung oder Scoring-Logik.
- Kein neuer externer Storage oder Netzwerkpfad.

## Begruendung

- Reduziert wiederholte Full-Scans in der haeufigsten Warmstart-Situation signifikant.
- Bewahrt Glaubwuerdigkeit durch harte Key-Invalidierung statt riskanter Wiederverwendung.
- Nutzt etablierte Drift-Persistenzmuster (schema versioning, UTF-8, atomare Writes) aus bestehenden Cache-Komponenten.

Verworfene Alternativen:
- Nur In-Memory-Cache: kein Nutzen ueber Prozessgrenzen.
- Persistenz inkl. ParseResults: hoehere Komplexitaet und Kompatibilitaetsrisiko bei geringerer Robustheit.
- Soft-Fallback bei Mismatch: erhoeht Stale-Risiko.

## Konsequenzen

Positiv:
- Deutlich schnellerer erster `nudge` nach Prozessneustart bei unveraendertem `HEAD` und gleicher Konfiguration.
- Konsistente, deterministische Reuse-Regeln.

Trade-offs:
- Zusaetzliche lokale Cache-Artefakte.
- Zusaetzliche Validierungs- und Deserialisierungslogik.

## Validierung

Technische Validierung:
- `pytest tests/test_nudge.py -q --tb=short`
- `pytest tests/test_incremental.py -q --tb=short`
- `python scripts/check_risk_audit.py --diff-base origin/main`
- `drift analyze --repo . --format json --exit-zero`

Erfolgskriterien:
- Nach Baseline-Erzeugung in Prozess A kann Prozess B ohne erneuten Full-Scan auf denselben Zustand warm starten.
- Bei geaendertem `HEAD` oder Config-Fingerprint erfolgt keine Wiederverwendung.
- Keine Regression bestehender nudge- und incremental-Tests.

Policy §10 Lernzyklus-Ergebnis: unklar (bis Benchmarking auf realen Mehrprozess-Loops abgeschlossen ist).
