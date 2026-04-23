---
id: ADR-085
status: proposed
date: 2026-04-21
supersedes:
---

# ADR-085: drift_nudge Cold-Start Latency Reduction via Pipeline File-Hashes Surfacing

## Kontext

`drift_nudge` zeigt beim Cold-Start (kein In-Memory-Baseline, kein Disk-Baseline) eine
Latenz von ~4.7 s auf einem ~1000-Datei-Python-Repo (gemessen in
`benchmark_results/mcp_performance_smoke.json`). Das Ziel aus ADR-084 / Backlog-Item 05 ist
< 1 s.

Ursache: `_NudgeExecution._create_baseline()` führt drei separate Durchläufe über alle Dateien
durch. Pass 3 (nach `analyze_repo()`) liest jede Datei erneut für Hashing und liest jede
Cache-JSON erneut — obwohl `analyze_repo()` intern bereits `ParsedInputs.file_hashes`
aufgebaut und alle Ergebnisse in den ParseCache geschrieben hat. Diese Daten werden aber
verworfen, bevor `RepoAnalysis` zurückgegeben wird.

Detaillierte Analyse: `work_artifacts/feature_05_2026-04-21/profile_before.md`

## Entscheidung

`file_hashes` aus dem Ingestion-Durchlauf über einen optionalen Out-Parameter
`file_hashes_out: dict[str, str] | None` aus `AnalysisPipeline.run()` nach oben propagieren
(durch `_run_pipeline()` und `analyze_repo()`). `_create_baseline()` nutzt diesen Parameter
um das Mapping ohne zweiten I/O-Durchlauf zu befüllen.

Zusätzlich wird `parse_map` in `_create_baseline()` auf `{}` gesetzt (kein dritter Durchlauf).
Dies entspricht dem bereits validierten Verhalten des Disk-Warm-Loads:
`BaselineManager._load_persisted_nudge_baseline()` gibt ebenfalls `{}` als parse_map zurück.

**Explizites Non-Goal**: Keine Änderung der Nudge-Semantik, keine neue Caching-Schicht,
keine Änderung von BaselineSnapshot oder Persistenz-Format.

## Begründung

**Option A (gewählt): Out-Parameter `file_hashes_out`**
- Minimale Änderung: 3 Signaturen + 3 Stellen in `_create_baseline()`
- Kein Breaking-Change an `RepoAnalysis` (kein neues Feld in öffentlichem Modell)
- Rückwärtskompatibel: bestehende Aufrufer übergeben den Parameter nicht
- Sorgt für exakt eine Datenquelle pro Run

**Option B (verworfen): `file_hashes` als neues Feld in `RepoAnalysis`**
- Erfordert Modell-Änderung mit Serialisierungs-Implikationen (JSON-Output, Tests)
- Größerer Scope, höheres Risiko

**Option C (verworfen): Parallele Ausführung von hash-pass + analyze_repo**
- Höhere Komplexität, Threading-Risiken, schwer testbar

## Konsequenzen

- Cold-Start von ~4.7 s auf ~1.2–1.5 s reduziert (Pass 3 entfällt: ~3.5 s gespart)
- `parse_map` ist beim ersten Baseline-Aufbau leer (`{}`); auf warmen Reads ändert sich nichts
- Inkrementelle Signal-Runs funktionieren mit leerem `parse_map` korrekt (bereits verifiziert)
- Bestehende Tests bleiben kompatibel: Mock von `analyze_repo` ignoriert `file_hashes_out`
  → ergibt leere dict → identisches Verhalten wie bisher in Tests

## Validierung

- Neuer Test `tests/test_nudge_cold_start.py`: misst First-Call-Latenz, assert < 1.0 s
  (mit Toleranz-Multiplier `DRIFT_COLD_START_TOLERANCE` für CI-Umgebungen)
- Bestehende `tests/test_nudge.py` müssen unverändert grün bleiben
- Feature-Evidence: `benchmark_results/v2.28.0_feature_evidence.json`
- Referenz Policy §10: Lernzyklus-Ergebnis nach Merge ausstehend
