---
name: "Drift FP Reduction"
agent: agent
description: "Analysiert systematisch, warum Drift legitime Patterns als Architekturdrift meldet, und priorisiert konkrete, testbare Maßnahmen zur False-Positive-Reduktion."
---

# Drift FP Reduction

Du analysierst, welche deterministischen Heuristiken, Thresholds, Guardrails, Suppressions und Gewichtungen in Drift unnötige False Positives erzeugen. Das Ziel ist ein priorisierter Maßnahmenplan, nicht eine Implementation.

> **Pflicht:** Vor Ausführung dieses Prompts das Drift Policy Gate durchlaufen
> (siehe `.github/prompts/_partials/konventionen.md` und `.github/instructions/drift-policy.instructions.md`).

## Relevante Referenzen

- **Instruction:** `.github/instructions/drift-policy.instructions.md`
- **Bewertungssystem:** `.github/prompts/_partials/bewertungs-taxonomie.md`
- **Issue-Filing:** `.github/prompts/_partials/issue-filing.md` (nur verwenden, wenn der Auftrag explizit auch Filing umfasst)
- **Verwandte Prompts:** `drift-signal-quality.prompt.md` (Signalpräzision), `drift-agent-workflow-test.prompt.md` (CLI- und Workflow-Perspektive), `drift-fix-loop.prompt.md` (nachgelagerte Umsetzung)
- **Fokus-Dateien:** `src/drift/precision.py`, `src/drift/negative_context.py`, `src/drift/calibration/`, `src/drift/guardrails.py`, `src/drift/suppression.py`, `src/drift/scoring/engine.py`, `src/drift/signal_registry.py`
- **Primäre Regressionstests:** `tests/test_precision_recall.py`, `tests/test_negative_context.py`, `tests/test_negative_context_export.py`, `tests/test_calibration.py`, `tests/test_scoring.py`, `tests/test_scoring_edge_cases.py`, `tests/test_suppression.py`, `tests/test_brief.py`, `tests/test_plugin_api.py`

## Arbeitsmodus

- Evidenz-first: Jede Empfehlung braucht einen konkreten FP-Mechanismus und einen verifizierten Ort im Code.
- Keine Code-Änderungen vornehmen. Analysiere, priorisiere und begründe nur.
- Bevorzuge kleine, lokale Präzisionsmaßnahmen vor globalen Gewichtungs- oder Architektur-Eingriffen.
- Trenne Beobachtung, Hypothese und Empfehlung sauber voneinander.
- Gib für jede Maßnahme eine verifizierte Zeilenangabe an. Wenn die Zeile noch nicht sicher ist, verifiziere sie zuerst, bevor du die Maßnahme in den priorisierten Output aufnimmst.
- Signal-Heuristik-Änderungen und Änderungen an Scoring-Gewichten als maintainer-approval-pflichtig markieren.

## Ziel

Bestimme, welche Änderungen die False-Positive-Rate von Drift am stärksten senken, ohne Determinismus, Erklärbarkeit, Rückwärtskompatibilität oder Recall unnötig zu beschädigen.

## Erfolgskriterien

Die Aufgabe ist erst abgeschlossen, wenn du mit belastbarer Evidenz beantworten kannst:
- Welche 2 bis 4 Stellschrauben senken die FP-Rate voraussichtlich am stärksten?
- Welche FP-Ursachen sind lokal lösbar und welche würden tiefere Signal- oder Scoring-Eingriffe benötigen?
- Wo ist das Risiko auf neue False Negatives gering, mittel oder hoch?
- Welche Regressionstests in `tests/` sollten erweitert oder neu ergänzt werden?
- Muss `.drift-baseline.json` nach den empfohlenen Änderungen neu generiert werden?

## Arbeitsregeln

- Jede Maßnahme muss enthalten: betroffene Datei, Symbol, verifizierte Zeile, FP-Ursache, erwartete FP-Reduktion, FN-Risiko, Testempfehlung, Public-API-Auswirkung, Freigabebedarf.
- Bevorzuge bestehende Testanker vor dem Vorschlag neuer Testdateien.
- Änderungen an `drift.schema.json` oder Public APIs nur dann empfehlen, wenn sie unvermeidbar sind; in diesem Fall explizit markieren.
- Wenn Evidenz zu dünn ist, die Maßnahme als `review` statt als sichere Empfehlung klassifizieren.
- Wenn ein Bereich voraussichtlich kaum Hebel hat, sag das explizit und begründe warum.
- Stütze Top-Empfehlungen nicht nur auf Code-Lektüre und Tests, sondern zwingend auch auf mindestens einen aktuellen Drift-Lauf im analysierten Repository-State.

## Bewertungs-Labels

Verwende ausschließlich Labels aus `.github/prompts/_partials/bewertungs-taxonomie.md`:

- **Ergebnis-Bewertung** pro Analysebereich: `pass` / `review` / `fail`
- **Abdeckungs-Status** pro Test- oder Evidenzpfad: `tested` / `skipped` / `blocked`
- **FN-Risiko / Umsetzungsrisiko**: `low` / `medium` / `high` / `critical`

## Harte Constraints

- Keine Änderungen an der Public API ohne explizite Kennzeichnung
- Determinismus muss erhalten bleiben
- Kein LLM-Scoring ohne deterministischen Fallback
- Rückwärtskompatibilität zu `drift.schema.json` muss erhalten bleiben
- Keine halluzinierten Pfade, Symbole oder Zeilenangaben
- Maßnahmen mit hohem FN-Risiko nicht als Quick Wins darstellen

## Artefakte

Erstelle Artefakte unter `work_artifacts/fp_reduction_<YYYY-MM-DD>/`:

1. `scope_map.md`
2. `live_scan_evidence.md`
3. `evidence_log.md`
4. `prioritization_matrix.md`
5. `regression_test_plan.md`
6. `fp_reduction_report.md`

## Workflow

### Phase 0: Scope und Repo-Stand fixieren

**Dev-Version sicherstellen** (siehe `_partials/konventionen.md` → Versions-Freshness):

```bash
pip install -e .
drift --version
```

Dokumentiere:
- verwendete Drift-Version
- analysierten Repository-Stand
- welche der Fokus-Dateien und Tests tatsächlich betrachtet wurden
- welche Drift-Kommandos zur Live-Evidenz verwendet werden

### Phase 1: FP-Hotspots inventarisieren

Analysiere die folgenden Bereiche gezielt:

1. `src/drift/precision.py`
   - Prüfe `ensure_signals_registered`, `run_fixture`, `has_matching_finding`, `PrecisionRecallReport`, `evaluate_fixtures`
   - Frage: Entstehen False Positives durch zu grobe Match-Logik, Threshold-Annahmen oder unzureichende Fixture-Interpretation?

2. `src/drift/negative_context.py`
   - Prüfe `findings_to_negative_context`, `_gen_fallback` und signal-spezifische `_gen_*`-Generatoren
   - Frage: Fehlen legitime Gegenmuster für Utility-Code, absichtliche Architekturabweichungen, Test-Fixtures oder bekannte Ausnahmepfade?

3. `src/drift/calibration/`
   - Prüfe alle Stellschrauben im Verzeichnis, einschließlich `__init__.py`, `profile_builder.py`, `threshold_adapter.py`, `feedback.py`, `outcome_correlator.py`, `github_correlator.py` und `history.py`
   - Frage: Wird dünne, verrauschte oder einseitige Evidenz zu aggressiv in Gewichte oder Thresholds übersetzt?

4. `src/drift/guardrails.py`
   - Prüfe `pre_task_relevance`, `generate_guardrails`, `guardrails_to_prompt_block`
   - Frage: Sind Guardrails zu generisch oder zu aggressiv formuliert und verstärken dadurch FP-nahe Fehlinterpretationen?

5. `src/drift/suppression.py`
   - Prüfe `scan_suppressions` und `filter_findings`
   - Frage: Fehlen Suppressions für bekannte legitime Patterns oder sind bestehende Mechanismen zu unpräzise?

6. `src/drift/scoring/engine.py`
   - Prüfe `compute_signal_scores`, `composite_score`, `severity_gate_pass`, `delta_gate_pass`, `auto_calibrate_weights`, `calibrate_weights`
   - Frage: Verstärken Gewichte oder Gates Signale mit schwacher lokaler Evidenz überproportional?

7. `src/drift/signal_registry.py`
   - Prüfe alle relevanten Registry-Stellschrauben, einschließlich `SignalMeta`, `register_signal_meta`, `get_all_meta`, `get_meta`, `get_weight_defaults` und `resolve_abbrev`
   - Frage: Sind Default-Gewichte, Kategorien oder implizite Confidence-Annahmen für FP-arme Produktionseinsätze plausibel?

### Phase 2: Vorhandene Evidenz und Tests gegenprüfen

Nutze bestehende Tests als Oracle, aber verlasse dich nicht ausschließlich auf Testevidenz. Führe mindestens einen aktuellen Drift-Lauf auf dem Repository aus und verknüpfe die Empfehlungen mit real beobachteten Findings, Rankings oder fehlenden Gegenmustern.

Pflicht-Live-Evidenz:

```bash
drift scan --max-findings 50 --response-detail detailed
drift analyze --repo . --format json
```

Dokumentiere pro Lauf:
- welche Findings oder Nicht-Findings die FP-Hypothese stützen
- welche Signal- oder Ranking-Unterschiede zwischen `scan` und `analyze` relevant sind
- welche Empfehlung ohne diese Live-Evidenz nicht belastbar wäre

Bevorzugte Testläufe:

```bash
python -m pytest tests/test_precision_recall.py -q
python -m pytest tests/test_negative_context.py tests/test_negative_context_export.py -q
python -m pytest tests/test_calibration.py tests/test_scoring.py tests/test_scoring_edge_cases.py -q
python -m pytest tests/test_suppression.py tests/test_brief.py tests/test_plugin_api.py -q
```

Pro Bereich dokumentieren:
- Welche Evidenz stammt aus aktuellen Drift-Läufen?
- Welche Evidenz stammt direkt aus Code-Lektüre?
- Welche Evidenz stammt aus bestehenden Tests?
- Welche Aussage bleibt ohne weiteren Oracle unsicher?

### Phase 3: Maßnahmen nach Impact geteilt durch Aufwand priorisieren

Erstelle eine Priorisierungsmatrix mit mindestens diesen Spalten:

| Priorität | Maßnahme | Datei / Symbol / Zeile | FP-Ursache | Erwartete FP-Reduktion | Aufwand | FN-Risiko | Public API | Freigabebedarf | Bewertung |
|-----------|----------|------------------------|------------|------------------------|---------|-----------|------------|----------------|-----------|

Verwende für `Erwartete FP-Reduktion` eine explizite Bandbreite oder Prozentklasse, zum Beispiel `gering (0-5%)`, `mittel (5-15%)`, `hoch (15-30%)` oder `sehr hoch (>30%)`.

Priorisiere dabei:
- zuerst lokale Präzisionsgewinne in Negative Context, Suppression oder klaren Threshold-Grenzen
- danach Guardrail-Schärfung und testnahe Kalibrierungsverbesserungen
- zuletzt Gewichts- und Registry-Eingriffe, wenn lokale Maßnahmen nicht ausreichen

### Phase 4: Regressionstest-Plan formulieren

Für jede Top-Maßnahme angeben:
- welche bestehende Testdatei erweitert werden sollte
- welcher neue Testfall das legitime Pattern absichert
- welches neue False-Negative-Risiko zusätzlich abgesichert werden muss
- ob ein neuer Test nötig ist oder eine bestehende Fallmatrix genügt

Nutze bevorzugt diese Zuordnung:
- Precision/Fixture-Änderungen → `tests/test_precision_recall.py`
- Negative-Context-Änderungen → `tests/test_negative_context.py`, `tests/test_negative_context_export.py`
- Calibration-Änderungen → `tests/test_calibration.py`
- Scoring-Änderungen → `tests/test_scoring.py`, `tests/test_scoring_edge_cases.py`
- Guardrail-Änderungen → `tests/test_brief.py`
- Suppression-Änderungen → `tests/test_suppression.py`
- Registry-/Default-Gewicht-Änderungen → `tests/test_plugin_api.py`

### Phase 5: Baseline-Entscheidung erzwingen

Beantworte explizit:
- Muss `.drift-baseline.json` nach den vorgeschlagenen Änderungen neu generiert werden?
- Wenn ja: welche Art von Finding- oder Ranking-Änderung macht das notwendig?
- Wenn nein: warum bleibt der bestehende Baseline-Vertrag stabil?

### Phase 6: Abschlussbericht erstellen

Erstelle `fp_reduction_report.md` in dieser Struktur:

```markdown
# Drift FP Reduction Report

**Datum:** <YYYY-MM-DD>
**drift-Version:** [VERSION]
**Repository:** drift

## Gesamteinschätzung

- [2 bis 4 wichtigste Hebel]

## Priorisierte Maßnahmen

| Priorität | Maßnahme | Ort | Erwartete FP-Reduktion | FN-Risiko | Testempfehlung | API-Impact | Freigabebedarf |
|-----------|----------|-----|------------------------|-----------|----------------|-----------|----------------|

## Sekundäre oder nachrangige Bereiche

- [...]

## Regressionstest-Plan

| Maßnahme | Testdatei | Neuer oder erweiterter Test | Ziel |
|----------|-----------|-----------------------------|------|

## Baseline-Entscheidung

- Neu generieren: [ja/nein]
- Begründung: [...]
```

## Entscheidungsregel

Wenn lokale Präzisionsmaßnahmen ausreichend sind, keine globale Signal- oder Gewichtungsanpassung als Top-Empfehlung ausgeben. Wenn eine tiefere Änderung dennoch nötig ist, muss die lokale Unzulänglichkeit explizit nachgewiesen werden.

## Relevanter Skill

- `.github/skills/drift-agent-prompt-authoring/SKILL.md`