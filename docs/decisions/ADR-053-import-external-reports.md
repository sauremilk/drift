---
id: ADR-053
status: proposed
date: 2026-04-11
supersedes:
---

# ADR-053: Import External Tool Reports (SonarQube, pylint, CodeClimate)

## Kontext

Teams migrating to Drift from SonarQube, pylint, or CodeClimate have no migration path.
Adoption research shows that explicit migration paths significantly accelerate tool adoption
(see `adoption_analysis_report.md`, Phase D1). Users want to see what Drift finds
*in addition to* their current tool — a side-by-side value proposition.

Currently, Drift only analyzes source code directly. There is no way to ingest findings
from external tools for comparison or migration tracking.

## Entscheidung

Introduce a `drift import` CLI command that:

1. Reads a JSON report from SonarQube, pylint, or CodeClimate format
2. Maps external findings to Drift's `Finding` model where overlap exists
3. Stores imported findings with clear `source` attribution in metadata
4. Outputs a side-by-side comparison: "External tool found X, Drift additionally found Y"

**What is explicitly not done:**

- No custom signal creation from imported findings — they are passthrough only
- No scoring integration — imported findings do not affect the drift score
- No persistent storage — import is a one-shot comparison command
- No SARIF input (SARIF is already a Drift *output* format; adding it as input creates confusion)

## Begründung

Option A (chosen): Read-only import with side-by-side comparison. Minimal complexity,
clear value proposition for migration. Imported findings are clearly separated from
native Drift findings via `metadata["source"]`.

Option B (rejected): Deep integration where imported findings feed into scoring.
Too complex, blurs the boundary between Drift's own analysis and external tools,
violates the credibility principle (Policy §6, Glaubwürdigkeit > Features).

Option C (rejected): Bidirectional sync with external tools. Far too complex,
maintenance burden, and unclear benefit per effort unit.

## Konsequenzen

- New input path: `src/drift/ingestion/external_report.py` (trust boundary for external JSON)
- New CLI command: `src/drift/commands/import_cmd.py`
- Finding model unchanged — imported findings use existing `metadata` dict for attribution
- STRIDE review required for new input path (external untrusted JSON)
- No scoring impact — no FMEA/fault tree update needed

## Validierung

```bash
# Unit tests for format adapters
pytest tests/test_import_command.py -v

# CLI integration — SonarQube format
echo '{"issues":[]}' > /tmp/sonar.json
drift import /tmp/sonar.json --format sonarqube --repo .

# CLI integration — pylint format
echo '[]' > /tmp/pylint.json
drift import /tmp/pylint.json --format pylint --repo .
```

Lernzyklus-Ergebnis: bestätigt wenn ≥3 Nutzer den Import-Befehl in Feedback/Issues erwähnen.
