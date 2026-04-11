---
id: ADR-054
status: proposed
date: 2026-04-11
supersedes:
---

# ADR-054: File-Discovery Manifest Cache mit Hybrid-Invalidierung

## Kontext

Die Dateierkennung in der Ingestion basiert auf repo-weiten Glob-Laeufen plus Stat-Aufrufen. Auf groesseren Repositories wird dieser Schritt bei wiederholten Runs zum dominanten Kostenfaktor, obwohl sich Dateimenge und Konfiguration oft nicht aendern. Gleichzeitig soll die Discovery-Semantik im ersten Schritt stabil bleiben.

## Entscheidung

Wir fuehren einen persistenten Discovery-Manifest-Cache ein, der in `.drift-cache/file_discovery_manifest.json` gespeichert wird.

- Primaere Invalidierung: Git-HEAD (`git rev-parse HEAD`)
- Sekundaere Invalidierung (Fallback): mtime-basierter Fingerprint ohne Git
- Cache-Key umfasst: repo, include/exclude, max_files, ts_enabled, unterstuetzte Sprachen, Schema-Version
- Manifest-Writes erfolgen atomar
- Korruptes/inkompatibles Manifest fuehrt zu sicherem Re-Scan statt Fehler

Nicht-Ziele fuer diesen Schritt:
- Keine Umstellung auf git-only Discovery-Quelle (`git ls-files`) im ersten Patch
- Keine Aenderung an Finding- oder Scoring-Logik

## Begruendung

Der Ansatz reduziert Laufzeit bei wiederholten Analysen deutlich, ohne die Discovery-Quelle im ersten Schritt umzubauen. Dadurch sinkt das Regressionsrisiko. Git-HEAD ist in Drift bereits als stabile Invalidierungsbasis etabliert; mtime-Fallback deckt Non-Git-Umgebungen ab.

## Konsequenzen

- Positiv: Wiederholte Runs koennen Discovery aus Manifest laden statt erneut global zu globben.
- Positiv: Bestehende API-Semantik bleibt kompatibel.
- Trade-off: Zusaetzlicher Persistenzpfad erfordert Robustheit gegen korrupten Cache.
- Trade-off: mtime-Fallback ist konservativer als Git-HEAD und kann in Randfaellen oefter invaldieren.

## Validierung

Geplante Checks:

```bash
python -m pytest tests/test_file_discovery.py -q
python -m pytest tests/test_precision_recall.py -v --maxfail=1
python scripts/check_risk_audit.py --diff-base origin/main
python -m drift analyze --repo . --format json --exit-zero
```

Erfolgskriterien:
- Discovery-Tests decken Cache-Hit, HEAD-Invalidierung, mtime-Fallback und Manifest-Korruptions-Fallback ab.
- Funktionale Ergebnissemantik bleibt zwischen cold/warm Runs unveraendert.
- Lernzyklus-Ergebnis nach Messung: bestaetigt | widerlegt | unklar | zurueckgestellt.
