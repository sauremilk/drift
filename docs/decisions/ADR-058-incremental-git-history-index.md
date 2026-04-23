---
id: ADR-058
status: proposed
date: 2026-04-11
supersedes:
---

# ADR-058: Inkrementeller persistenter Git-History-Index

## Kontext

Die aktuelle History-Ermittlung in [src/drift/ingestion/git_history.py](src/drift/ingestion/git_history.py) basiert auf einem vollstaendigen `git log --numstat` pro Analyse-Lauf (innerhalb des `since_days` Fensters), abgesichert nur durch einen kurzlebigen In-Memory-Cache in [src/drift/pipeline.py](src/drift/pipeline.py). Bei haeufigen Scans auf grossen Repositories fuehrt das zu wiederholtem Parsing derselben Commit-Historie.

## Entscheidung

Wir fuehren einen opt-in, lokalen, persistenten Git-History-Index ein.

Umfang:
- Neues Config-Flag `git_history_index_enabled` (default `false`) in [src/drift/config.py](src/drift/config.py).
- Neuer konfigurierbarer Unterordner `git_history_index_subdir` unterhalb `cache_dir`.
- Persistenter Index in `.drift-cache/<subdir>/` mit:
  - `manifest.json` (Schema-Version, Repo-Identitaet, letzter Head, Parameter-Fingerprint)
  - `commits.jsonl` als append-only Commit-Store bei linearem Fortschritt.
- Inkrementeller Pfad:
  - Wenn `indexed_head` Vorfahr von aktuellem `HEAD` ist: nur Delta-Range `<indexed_head>..<HEAD>` parsen und anhaengen.
  - Bei Rebase/Force-Push/Nicht-Vorfahr: Full-Rebuild.
- Fachliche Semantik bleibt unveraendert: Rueckgabe weiterhin auf `since_days` gefiltert und im Pipeline-Pfad auf `known_files` eingegrenzt.

Nicht im Umfang:
- Keine Aenderung an Signalheuristiken oder Scoring.
- Keine neuen externen I/O- oder Netzwerk-Kanaele.
- Kein default-on Rollout in dieser Iteration.

## Begruendung

- Reduziert wiederholtes Git-Parsing auf Warm-Runs signifikant.
- Behaelt Korrektheit durch ancestry-basierte Sicherheitsregeln.
- Feature-Flag minimiert Rollout-Risiko und erlaubt kontrollierte Aktivierung.

Verworfene Alternativen:
- Immer Full-Parse mit groesserem In-Memory-TTL: beschleunigt nur kurzzeitige Wiederholungen, nicht ueber Prozessgrenzen.
- Sofort default-on: hoeheres Risiko ohne gestufte Validierung.

## Konsequenzen

Positiv:
- Schnellere wiederholte Scans bei unveraenderter oder linear fortgeschriebener Historie.
- Bessere Einfuehrbarkeit in lokalen Agenten-/CI-Feedback-Loops.

Trade-offs:
- Zusetzliche Persistenz- und Invalidation-Logik.
- Neuer lokaler Cache-Artefaktpfad muss robust gegen Korruption/Fallback behandelt werden.

## Validierung

Technische Validierung:
- `pytest tests/test_git_history_index.py -q`
- `pytest tests/test_pipeline_components.py -q`
- `python scripts/check_risk_audit.py --diff-base origin/main`
- `drift analyze --repo . --format json --exit-zero`

Erfolgskriterien:
- Bei deaktiviertem Flag: Legacy-Verhalten unveraendert.
- Bei aktiviertem Flag: Delta-Append bei linearem Head-Fortschritt, Rebuild bei History-Rewrite.
- Keine Regression in bestehenden Pipeline-Tests.

Policy §10 Lernzyklus-Ergebnis: unklar (bis Benchmarking auf grossen Repositories abgeschlossen ist).
