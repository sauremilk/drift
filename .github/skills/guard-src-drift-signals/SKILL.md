---
name: guard-src-drift-signals
description: "Drift-generierter Guard fuer `src/drift/signals`. Aktiv bei Signalen: AVS, EDS, PFS. Konfidenz: 0.95. Verwende diesen Skill wenn du Aenderungen an `src/drift/signals` planst oder wiederholte Drift-Findings (AVS, EDS, PFS) fuer dieses Modul bearbeitest."
argument-hint: "Beschreibe das neue oder zu aendernde Signal — Name, Typ, was es erkennen soll."
---

# Guard: `src/drift/signals`

`src/drift/signals` enthaelt alle 25+ `BaseSignal`-Implementierungen. Jede Datei hier ist eine eigenstaendige Erkennungseinheit. AVS, EDS und PFS entstehen wenn Signals zu viel tun, intern verwoben sind oder voneinander abweichende Muster verwenden.

**Konfidenz: 0.95** — dieses Modul ist der Kern der Erkennungsqualitaet; Fehler hier beeinflussen direkt Precision und Recall.

## When To Use

- Du implementierst ein neues Signal
- Du veraenderst die Erkennungslogik eines bestehenden Signals
- Du aenderst `base.py`, `_utils.py`, `__init__.py` oder `register_signal`
- Du bearbeitest `incremental_scope` fuer ein Signal
- Drift meldet AVS, EDS oder PFS fuer eine Datei in `src/drift/signals/`

**Fuer ein vollstaendiges neues Signal** verwende stattdessen `drift-signal-development-full-lifecycle` — der Skill dort enthaelt den vollstaendigen ADR-, Fixture- und Audit-Workflow.

## Warum dieses Modul kritisch ist

| Signal | Ursache in `signals/` |
|--------|----------------------|
| **AVS** | Signals die mehrere unabhaengige Code-Patterns gleichzeitig pruefen (zu breite Verantwortung) |
| **EDS** | `_utils.py`-Aufrufe und AST-Traversierung gemischt mit Pattern-Matching-Logik in derselben Methode |
| **PFS** | 25+ Signals nutzen `_utils.py` unterschiedlich, haben verschiedene `incremental_scope`-Strukturen oder inkonsistente `Finding`-Felder |

## Core Rules

1. **Ein Signal = eine klar benennbare Frage** — ein Signal soll beantworten: "Hat diese Datei/Funktion Problem X?" Wenn die Antwort zwei unabhaengige Ks-Pattern abdeckt, trenne es.

2. **`register_signal` immer am Dateiende** — jedes Signal endet mit `register_signal(MySignal)`. Ohne diesen Aufruf wird das Signal nie ausgefuehrt. AVS entsteht wenn Signals intern Sub-Registrierungen machen.

3. **`incremental_scope` explizit definieren** — jedes Signal muss `incremental_scope` zurueckgeben. Fehlt es oder ist es `None`, wird das Signal bei inkrementellen Scans nie aufgerufen.

4. **`_utils.py` fuer gemeinsame Hilfsfunktionen** — `is_test_file()`, `iter_functions()`, `get_complexity()` etc. gehoeren in `_utils.py`, nicht direkt in die `analyze()`-Methode. PFS entsteht wenn jedes Signal seine eigene Variante dieser Helfer hat.

5. **`AnalysisContext` ist read-only** — Signals duerfen den `AnalysisContext` nicht veraendern. Seiteneffekte hier erzeugen nicht-deterministische Scan-Ergebnisse.

## Iron Law

> **Kein neues Signal ohne Precision/Recall-Fixtures in `tests/fixtures/ground_truth.py`.** Ein Signal ohne TP/TN-Evidenz ist ein blinder Fleck.

## Arbeitsablauf fuer Signal-Aenderungen

```bash
# 1. Precision/Recall-Tests laufen lassen
python -m pytest tests/test_precision_recall.py -v --tb=short

# 2. Nudge nach Aenderung
drift nudge

# 3. Vollstaendiger Scan zur Verifikation
drift analyze --repo . --exit-zero
```

## Review Checklist

- [ ] Signal erbt von `BaseSignal` und implementiert `analyze()` und `incremental_scope`
- [ ] `register_signal(MySignal)` am Ende der Datei
- [ ] Gemeinsame Hilfsfunktionen kommen aus `_utils.py`, nicht inline
- [ ] TP/TN-Fixtures in `tests/fixtures/ground_truth.py` vorhanden
- [ ] `drift nudge` zeigt `safe_to_commit: true`
- [ ] Precision/Recall-Tests laufen durch
- [ ] Keine neuen AVS/EDS/PFS-Findings im Signal-Modul

## References

- [src/drift/signals/base.py](../../../src/drift/signals/base.py) — `BaseSignal`, `AnalysisContext`, `register_signal`
- [src/drift/signals/_utils.py](../../../src/drift/signals/_utils.py) — Gemeinsame Signal-Helfer
- [tests/fixtures/ground_truth.py](../../../tests/fixtures/ground_truth.py) — Precision/Recall-Fixtures
- [.github/skills/drift-signal-development-full-lifecycle/SKILL.md](../drift-signal-development-full-lifecycle/SKILL.md) — Vollstaendiger Signal-Lifecycle
