---
id: ADR-057
status: proposed
date: 2026-04-11
supersedes:
---

# ADR-057: Centralized Test-File Detection and Finding Context Handling

## Kontext

Mehrere Signale melden Findings in Testdateien, obwohl die Muster dort oft beabsichtigt sind.
Das erzeugt False Positives und senkt die Glaubwuerdigkeit der Analyse.

## Entscheidung

Wir zentralisieren die Testdatei-Erkennung in der Ingestion und nutzen einen einheitlichen
Kontext-Klassifizierer fuer `test | generated | production`.

Umfang:
- Neue zentrale Utility: `src/drift/ingestion/test_detection.py`
- `Finding` bekommt ein optionales Feld `finding_context`
- Signale TSB, DCA, CCC, EDS, MAZ nutzen konsistente Test-Handling-Logik
- Neue globale Config: `test_file_handling` (`exclude | reduce_severity | include`),
  default `null` (signalspezifischer Default)

Nicht-Ziele:
- Keine Aenderung an Scoring-Gewichten
- Keine Aenderung an Output-Formaten ausser optionaler Kontextanreicherung

## Begruendung

Die Zentralisierung reduziert Fragmentierung in der Erkennungslogik und verbessert
Reproduzierbarkeit. Signalspezifische Defaults erlauben praezises Verhalten, waehrend
`test_file_handling` als globaler Override die Einfuehrbarkeit erhoeht.

## Konsequenzen

- Positiv: Weniger FP-Rauschen in Testkontexten.
- Positiv: Einheitliche Kontextmetadaten fuer Downstream-Filterung.
- Trade-off: Zusetzliche Verzweigungen in betroffenen Signalen.

## Validierung

```bash
python -m pytest tests/test_signal_utils.py -q
python -m pytest tests/test_type_safety_bypass.py -q
python -m pytest tests/test_missing_authorization.py -q
python -m pytest tests/test_dead_code_accumulation.py -q
python -m pytest tests/test_co_change_coupling.py -q
python -m pytest tests/test_coverage_boost_15_signals_misc.py -q
```

Policy §10 Lernzyklus-Ergebnis: unklar (bis Vollmessung mit Precision/Recall-Lauf).
