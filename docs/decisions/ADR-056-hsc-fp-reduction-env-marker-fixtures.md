---
id: ADR-056
status: proposed
date: 2026-04-11
type: signal-design
signal_id: HSC
supersedes:
---

# ADR-056: HSC FP-Reduktion fuer Env-Name-/Marker-Konstanten (Issue #212)

## Problemklasse

Das HSC-Signal meldet in TypeScript- und Python-Code vermehrt False Positives, wenn String-Literale keine Geheimnisse enthalten, sondern nur Namen oder Marker fuer Konfiguration:
- Env-Var-Namenskonstanten (z. B. `AWS_SECRET_KEY_ENV = "AWS_SECRET_ACCESS_KEY"`) <!-- pragma: allowlist secret -->
- Sentinel/Marker-Konstanten (z. B. `*_MARKER`, `*_TOKEN_PREFIX`, `*_ERROR_CODE`)
- Endpoint-URL-Literale ohne Credentials

Das reduziert die Signal-Glaubwuerdigkeit und Priorisierbarkeit in realen Repositories.

## Heuristik

Ergaenze zwei gezielte Suppression-Heuristiken in HSC, jeweils nach Known-Prefix-Detektion:

1. Env-Var-Name-Literal
- Wenn der RHS-Wert `ALL_CAPS_SNAKE` ist
- und Secret-Terme enthaelt
- und die Variable env-name-typisch benannt ist (`*_ENV`, `*_ENV_KEY`, `*_KEY_ENV`, `*_VAR` oder enthaelt `_ENV`),
- dann kein HSC-Finding.

2. Marker/Sentinel-Konstantenname
- Wenn der Variablenname Marker-Suffixe enthaelt (`MARKER`, `PREFIX`, `ALPHABET`, `MESSAGE`, `ERROR_CODE`),
- dann kein HSC-Finding.

Guardrail:
- Known secret prefixes (`ghp_`, `sk-`, `AKIA`, ...) bleiben hoeher priorisiert und werden weiterhin immer als TP gemeldet.

## Scope

`file_local`

Begruendung: Die Entscheidung basiert nur auf lokalem Variablennamen und lokalem String-Literal; kein Cross-File- oder Git-Kontext noetig.

## Erwartete FP-Klassen

- Env-Var-Namekonstanten mit secret-artigen Bezeichnern.
- Marker-/Sentinel-Konstanten in Runtime-, Setup- und Error-Code-Kontext.
- Endpoint-URL-Konstanten ohne eingebettete Userinfo/Credentials.

## Erwartete FN-Klassen

- Obfuskierte oder fragmentierte Secrets, die keine bekannten Praefixe tragen und durch neue Suppressionspfade verdeckt werden koennten.

Begrenzung:
- Known-Prefix-Pfad bleibt unveraendert priorisiert.
- Suppression ist eng an Namens-/Literalformen gebunden.

## Fixture-Plan

Minimal vor Merge:
- TN: Env-Var-Namekonstante (`*_ENV`, `*_VAR`)
- TN: Marker/Sentinel-Konstante (`*_MARKER`, `*_PREFIX`, `*_ALPHABET`, `*_MESSAGE`, `*_ERROR_CODE`)
- TN: endpoint URL ohne credentials
- TP-Guard: Known-Prefix-Literal in env-/marker-benannter Variable muss weiterhin HSC-Finding erzeugen

## FMEA-Vorab-Eintrag

| Failure Mode | Severity | Occurrence | Detection | RPN |
|---|---:|---:|---:|---:|
| FP: Env-Var-Namekonstanten als Geheimnis gemeldet | 6 | 7 | 3 | 126 |
| FP: Marker/Sentinel-Konstanten als Geheimnis gemeldet | 5 | 7 | 3 | 105 |
| FN: Known-Prefix wird durch neue Suppression verdeckt | 8 | 2 | 3 | 48 |

## Validierungskriterium

Technisch:
- `pytest tests/test_hardcoded_secret.py tests/test_hsc_helpers_coverage.py -q --tb=short`
- `pytest tests/test_precision_recall.py -v --tb=short --maxfail=1`
- `python scripts/check_risk_audit.py --diff-base origin/main`

Erfolg:
- Neue TN-Faelle fuer Env-Name- und Marker-Konstanten bleiben finding-frei.
- Existing TP- und Known-Prefix-Regressionen bleiben stabil.
- Keine neue Risk-Audit-Gate-Verletzung.

Policy-Lernzyklus-Ergebnis: unklar (wird nach breiterer Repo-Stichprobe bestaetigt/widerlegt).
