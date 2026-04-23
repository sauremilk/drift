# ADR-095 — Opt-in Issue-Auto-Filing für BLOCK-Findings

- **Status:** proposed
- **Datum:** 2026-05-04
- **Verantwortlich:** @mick-gsk
- **Kontext:** Paket 2C (QA-Plan 2026 – Handlungsfähigkeit im Consumer-Repo)
- **Verwandt:** ADR-089 (Bypass-Detector), ADR-090 (`agent_telemetry`), ADR-094 (Human-Approval-Gate).

## Kontext

Das Human-Approval-Gate (ADR-094) blockt PRs mit BLOCK-Findings, aber
BLOCK-Findings, die außerhalb eines PR-Kontextes auftauchen (z. B. im
Nightly-Scan eines Produktions-Repos), verpuffen als Log-Zeile im
Action-Run. Im Consumer-Repo gibt es keinen persistenten Tracker.

Gleichzeitig verbietet die User-Regel "kein ungefragtes Posten" jede
automatische Kommunikation per Default.

## Entscheidung

Opt-in-Issue-Auto-Filing mit strikter Dedup:

### 1. Zwei neue `action.yml`-Inputs

- `create-issue` (default `"false"`): aktiviert den Issue-Schritt.
- `issue-labels` (default `"drift,agent-block"`): Labels, die an jedes
  auto-gefilte Issue gehangen werden. Werden nicht automatisch
  angelegt — Maintainer muss sie vorhanden haben.

### 2. Neuer action.yml-Step nach SARIF-Upload

Läuft mit `if: always() && inputs.create-issue == 'true'`, ruft
`scripts/gh_issue_dedup.py` mit dem drift-JSON-Report auf.

### 3. `scripts/gh_issue_dedup.py`

- Liest JSON-Report, filtert Findings mit `severity in {critical,high}`.
- Berechnet stabile `finding_id` (aus `id`/`finding_id`/`fingerprint`,
  Fallback `signal:file:line`).
- Ruft `gh issue list` mit erstem Label, scannt Bodies auf
  `<!-- drift-finding-id: <id> --> ` Marker → Dedup.
- Nicht-duplikate: `gh issue create` mit Titel `[drift] <msg>` und
  Body, der den Marker enthält.
- Exit 0 clean, 1 bei `gh`-Fehlern, 2 bei Usage/Report-Fehler.
- `--dry-run` für lokale Tests.

### 4. Issue-Template `.github/ISSUE_TEMPLATE/drift-block.yml`

Menschlicher Fallback für Maintainer, die Issues manuell anlegen
wollen (z. B. aus SARIF-Annotation heraus). Enthält denselben Marker.

## Nicht-Ziele

- **Kein** Auto-Close bei Finding-Resolution. Issues müssen manuell
  geschlossen werden, damit verpasste Regressions sichtbar bleiben.
- **Kein** Re-Open bei bereits geschlossenen Issues. Wenn ein
  Maintainer ein Drift-Issue als WONTFIX schließt, wird es nicht neu
  aufgemacht (Dedup-Scope = open issues mit Label).
- **Keine** Agent-Autonomie: der Agent kann weder Label setzen noch
  Issues kommentieren/schließen. Nur `gh issue create` mit Labels.
- **Kein** Cross-Repo-Filing.

## Validierung

- `tests/test_gh_issue_dedup.py`: Unit-Tests für Marker-Roundtrip,
  Finding-ID-Fallback, Severity-Filter und Dedup-Logik.
- `tests/test_action_yml_paket_2c.py`: YAML-Contract-Tests für
  `create-issue`/`issue-labels`-Inputs und Step-Präsenz.
- Feature-Evidence:
  `benchmark_results/v2.34.0_issue-auto-filing-adr-095_feature_evidence.json`.

## Risiken / Audit-Update (§18)

- **FMEA**: Label existiert nicht → `gh issue create` schlägt fehl →
  Script exit 1, sichtbar im Action-Log (Mitigierung: klare
  Error-Meldung mit Label-Name).
- **Risk**: Issue-Spam bei unkalibriertem BLOCK-Gate → Mitigierung:
  Opt-in-Default `false`, Dedup per Marker.
- **STRIDE**: "Agent spamt Tracker" → Tampering mit Marker würde zwar
  Dedup umgehen, erfordert aber Write-Access zu laufenden Issues, was
  das gh-Token hat — daher `agent-block`-Label + `verify_gate_not_bypassed.py`
  sichtbar in Audit-Trail.
