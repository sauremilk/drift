---
id: ADR-042
status: proposed
date: 2026-04-10
supersedes:
---

# ADR-042: Schema-Versionierung, Finding-IDs und Finding-Level-Explain

## Kontext

Drift erzeugt maschinenlesbare Ausgaben (JSON, SARIF, Agent-Tasks) für CI/CD-Pipelines und autonome Coding-Agenten. Agenten verlassen sich auf stabile Strukturen — jede nicht-versionierte Änderung kann den Reasoning-Loop brechen.

Aktueller Stand:

1. **Zwei divergierende Schema-Versionen**: CLI-JSON verwendet `"1.1"` (`json_output.py`), API/MCP verwendet `"2.0"` (`api_helpers.py`). Für Konsumenten ist unklar, welche Version gilt.
2. **Kein publiziertes Output-JSON-Schema**: Agenten können Responses nicht vorab validieren. `drift.schema.json` im Root deckt nur die Config (`drift.yaml`) ab.
3. **Kein stabiler Finding-Identifier im CLI-JSON-Output**: Der `finding_fingerprint()` existiert in `baseline.py` und wird in API-Responses als `fingerprint` exponiert, fehlt aber im CLI-JSON und SARIF-Output.
4. **Kein Finding-Level-Drill-Down**: `drift explain` akzeptiert nur Signal-Abbreviations und Error-Codes, nicht einzelne Finding-Fingerprints.

## Entscheidung

### 1. Einheitliche Schema-Version 2.1

- CLI-JSON (`json_output.py`) und API (`api_helpers.py`) verwenden beide `"2.1"`.
- Gemeinsame Konstante `OUTPUT_SCHEMA_VERSION` in `drift.models`.
- Versionierungs-Vertrag: Major = Breaking (Feld-Entfernung, Typ-Änderung), Minor = Additiv (neue optionale Felder).

### 2. `finding_id` als Pflichtfeld

- Jedes Finding in CLI-JSON, API-Response und SARIF erhält ein explizites `finding_id`-Feld.
- Wert = `finding_fingerprint()` aus `baseline.py` (16-Char SHA256-Hex).
- Bestehende `fingerprint`-Felder in API-Responses bleiben als Alias erhalten.
- Agent-Tasks (`agent_tasks.py`) erhalten ein separates `finding_id` zur Cross-Referenzierung.

### 3. Finding-Level-Explain via Fingerprint

- `drift explain <FINGERPRINT>` erkennt 16-Char-Hex-Strings und löst sie gegen einen Session-Cache oder Re-Scan auf.
- Rückgabe: vollständige Finding-Details + Signal-Info + Remediation.
- MCP-Tool-Beschreibung wird um Finding-Fingerprints erweitert.

### 4. Output-JSON-Schema publizieren

- Neue Datei `drift.output.schema.json` im Root beschreibt das vollständige CLI-JSON-Format.
- `$schema`-Referenz im JSON-Output ermöglicht Agent-seitige Validierung.
- Schema-Generierung via Script (`scripts/generate_output_schema.py`) mit CI-Validierung.

### Nicht-Ziele

- Kein neues MCP-Tool (`drift_finding_detail`) — `drift explain` wird erweitert.
- Kein neues ID-System — bestehender Fingerprint wird promoted.
- Keine Pydantic-Migration für Models — Schema wird aus Code abgeleitet.

## Begründung

- **Einheitliche Version**: Reduziert Verwirrung bei Agenten, die CLI- und API-Output mischen.
- **Finding-ID**: Ermöglicht gezielten Drill-Down und stabile Cross-Referenzierung zwischen Scan-Ergebnissen und Explain-Aufrufen.
- **Fingerprint als ID**: Deterministisch, content-based, bereits battle-tested für Baseline-Vergleiche.
- **Schema-Publikation**: Agenten können Responses vorab validieren und beim Parsing Fehler früh erkennen.

Alternative verworfen: Neues UUID-basiertes Finding-ID-System — wäre nicht deterministisch und würde Baseline-Vergleiche verkomplizieren.

## Konsequenzen

- **Additiver Breaking-Change**: Schema-Version steigt von 1.1/2.0 auf 2.1. Neue Felder (`finding_id`, `$schema`) sind additiv, bestehende Felder bleiben stabil.
- **Test-Updates**: Tests die `schema_version == "2.0"` oder `"1.1"` hart prüfen, müssen auf `"2.1"` aktualisiert werden.
- **Fingerprint-Volatilität**: Finding-IDs sind session-stabil, aber nicht refactoring-stabil (ändern sich bei Datei-Rename oder Titel-Änderung). Dies muss dokumentiert werden.
- **Re-Scan bei Finding-Explain ohne Session**: ~3s Latenz. Session-Context wird bevorzugt.
- **Audit-Pflicht**: Output-Pfad-Änderung erfordert STRIDE + Risk Register Update.

## Validierung

```bash
pytest tests/test_baseline.py -v
pytest tests/test_agent_native_cli.py -v
pytest tests/test_cli_runtime.py -v
drift analyze --repo . --format json --exit-zero | python -c "import sys,json; d=json.load(sys.stdin); assert d['schema_version']=='2.1'; assert 'finding_id' in d.get('findings',[[]])[0] if d.get('findings') else True"
```

Erwartetes Lernzyklus-Ergebnis: `bestaetigt` — Schema wird nach Integration in reale Agent-Loops validiert.
