---
id: ADR-055
status: proposed
date: 2026-04-11
supersedes:
---

# ADR-055: Dependency-Aware Signal Cache Keying

## Kontext

Der bestehende Signal-Cache in [src/drift/pipeline.py](src/drift/pipeline.py) nutzt pro Signal einen globalen Content-Hash ueber alle ParseResults. Dadurch invalidiert bereits eine kleine, lokale Dateiaenderung den Cache fuer Signale, deren Abhaengigkeit eigentlich enger ist (z. B. dateilokal oder modulweit). Das verursacht unnoetige Recomputations und verschlechtert die Einfuehrbarkeit in schnellen Entwicklungszyklen.

## Entscheidung

Wir fuehren explizite Cache-Dependency-Scopes fuer Signale ein und steuern die neue Logik hinter einem Feature-Flag.

Umfang:
- Neues Signal-Metadatenfeld `cache_dependency_scope` in [src/drift/signals/base.py](src/drift/signals/base.py).
- Vier zulaessige Scope-Typen: `file_local`, `module_wide`, `repo_wide`, `git_dependent`.
- Feature-Flag `signal_cache_dependency_scopes_enabled` in [src/drift/config.py](src/drift/config.py).
- Neue SignalCache-Keybuilder fuer module- und git-abhaengige Fingerprints in [src/drift/cache.py](src/drift/cache.py).
- SignalPhase nutzt bei aktiviertem Flag dependency-aware Keying und selektive Ausfuehrung fuer file/module Scopes.

Nicht im Umfang:
- Keine Aenderung an Signaldetektion, Gewichtung oder Scoring.
- Kein API- oder Output-Contract-Break fuer Findings.
- Kein Erzwingen von `module_wide` auf bestehende Signale ohne spaetere evidenzbasierte Kalibrierung.

## Begruendung

- Reduziert unnoetige Invalidierungen und verbessert Laufzeit fuer kleine Aenderungen.
- Behaelt Ergebnisverhalten stabil, da Signalheuristiken unveraendert bleiben.
- Feature-Flag minimiert Rollout-Risiko und ermoeglicht A/B-Verifikation.
- Explizite Scope-Metadaten erhoehen Wartbarkeit und Transparenz fuer kuenftige Signalentwicklung.

Verworfene Alternative:
- Sofortige Vollumstellung ohne Flag. Grund: hoeheres Rollout-Risiko ohne kontrollierten Vergleichsmodus.

## Konsequenzen

Positiv:
- Hoehere Cache-Hit-Rate bei dateilokalen Aenderungen.
- Bessere Trennung von Scope-Verantwortung je Signal.

Trade-offs:
- Mehr Komplexitaet in SignalPhase-Keying.
- Zusaetzliche Testmatrix fuer Scope-Varianten.

## Validierung

Technische Validierung:
- `pytest tests/test_incremental.py -q`
- `pytest tests/test_pipeline_components.py -q`
- `pytest tests/test_coverage_boost_16_cache_mds_ecd.py -q`
- `python scripts/check_risk_audit.py --diff-base origin/main`

Erfolgskriterien:
- Bei Flag `false`: identisches Legacy-Verhalten.
- Bei Flag `true`: selektive Invalidierung fuer file_local nachweisbar.
- Keine Regression in bestehenden Signal-/Pipeline-Tests.

Policy §10 Lernzyklus-Ergebnis: unklar (bis Abschluss der Messung in realen Repositories).
