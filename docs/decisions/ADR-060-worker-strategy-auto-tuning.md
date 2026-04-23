---
id: ADR-060
status: proposed
date: 2026-04-11
supersedes:
---

# ADR-060: Konfigurierbare Worker-Strategie mit konservativem Auto-Tuning

## Kontext

Drift nutzt bisher eine statische Default-Parallelisierung auf Basis von CPU-Kernen (mit env-Override). In der Praxis fuehrt das je nach Repository-Struktur zu Unter- oder Ueberparallelisierung: kleine Repos starten zu viele Threads, I/O-lastige Mischlasten verlieren durch Overhead, waehrend geeignete Lasten von Auto-Anpassung profitieren koennen.

## Entscheidung

Wir fuehren eine konfigurierbare Worker-Strategie in `drift.yaml` ein:

- `performance.worker_strategy`: `fixed` oder `auto`
- `performance.load_profile`: initial nur `conservative`
- zusaetzliche Guardrails (`min_workers`, `max_workers`, Schwellwerte fuer kleine Repos und I/O-Last-Proxys)

Prioritaetskette fuer die effektive Worker-Zahl:

1. expliziter CLI/API-Wert (`--workers`)
2. `DRIFT_WORKERS` Env-Override
3. konfigurierter Strategiepfad (`fixed` oder `auto`)

`auto` nutzt bewusst eine konservative Heuristik basierend auf Repositorygroesse, Dateitypverteilung und Dateigroessen-Proxys. Standard bleibt `fixed` (stufenweiser Rollout, kein Breaking Change).

Nicht-Ziele:

- kein phasengetrenntes Worker-Splitting fuer Ingestion/Signals/Attribution in dieser Iteration
- kein aggressives Profil in v1 des Rollouts

## Begruendung

Die Loesung reduziert Laufzeitstreuung und Fehlkonfigurationen, ohne bestehende Setups zu brechen. Durch konservatives Tuning und harte Klammern (`min/max`) bleibt Reproduzierbarkeit erhalten. Explizite Overrides bleiben dominant, damit CI und lokale Profile kontrollierbar bleiben.

## Konsequenzen

- Neue Konfigurationsoptionen in `DriftConfig`
- Analyzer/Pipeline erhalten einen zentralen Worker-Resolver
- CLI-Befehle `analyze`, `check`, `baseline` unterstuetzen Strategie/Profile explizit
- Zusetzliche Tests decken Prioritaetskette und Tuning-Heuristik ab

Trade-offs:

- Heuristik ist absichtlich vorsichtig und nicht global optimal fuer jede Last
- Transparenz steigt, Konfigurationsflaeche ebenfalls

## Validierung

- Unit-Tests fuer Resolver-Prioritaet und Heuristikgrenzen
- CLI-Pfade pruefen (`analyze`, `check`, `baseline`) mit/ohne `--workers`
- Schnelltests ausfuehren (`Tests: quick no-smoke`)
- Lernzyklus-Ergebnis gemaess Policy Section 10: anfangs `unklar`, nach Benchmark-Evidence auf `bestaetigt`/`widerlegt`
