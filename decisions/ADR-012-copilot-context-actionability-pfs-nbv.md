---
id: ADR-012
status: proposed
date: 2026-04-03
supersedes:
---

# ADR-012: Actionable copilot-context remediation for PFS and NBV

## Kontext

Issue #125 zeigt, dass PFS- und NBV-Hinweise im copilot-context fuer Agenten zu vage sind.
Die bisherigen Texte enthalten keine stabilen Ortsreferenzen oder vertragsspezifischen
Verhaltenshinweise und erzwingen zusaetzliches manuelles Quellcode-Lesen.

## Entscheidung

Wir schaerfen die Remediation-Texte an der Signalquelle:

- PFS liefert im `fix` einen kanonischen Exemplar-Ort (`file:line`) plus konkrete
  Abweichungs-Orte mit Zeilenreferenzen.
- NBV liefert im `fix` eine prefix-spezifische Suggestion (z. B. `validate_` mit
  `raise` oder `return False/None`) und den Fundort (`file:line`).

Explizit nicht Teil dieser ADR:

- keine Aenderung an Signal-Scoring oder Schwellwerten
- kein neues Output-Format
- keine Architektur-Aenderung am copilot-context Merge-Mechanismus

## Begruendung

Die Veraenderung erhoeht Signal-Glaubwuerdigkeit und Handlungsfaehigkeit bei
minimalem Risiko: vorhandene Findings werden nicht erweitert, sondern praeziser
formuliert. Das priorisiert Roadmap-Phase 1 (Vertrauen/Erklaerbarkeit).

## Konsequenzen

- Agenten koennen PFS/NBV-Befunde mit weniger Kontextwechsel direkt umsetzen.
- Textaenderungen koennen Snapshot-artige Erwartungswerte in Tests beeinflussen.
- Risiko auf FP/FN bleibt unveraendert, da Detektionslogik nicht geaendert wird.

## Validierung

- Regressionstests in `tests/test_pattern_fragmentation.py` und
  `tests/test_naming_contract_violation.py` pruefen actionability-Merkmale.
- Policy §10 Lernzyklus-Status: unklar (Feedback aus realen copilot-context Runs folgt).
