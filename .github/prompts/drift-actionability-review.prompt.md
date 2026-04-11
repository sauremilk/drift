---
name: "Drift Finding Actionability Review"
description: "Bewertet, ob Drift-Findings handlungsfähig genug sind, um Maintainer zu Entscheidungen zu führen. Identifiziert Lücken zwischen Diagnose und Handlung."
---

# Drift Finding Actionability Review

Du analysierst, wo Drift-Findings zwar diagnostisch korrekt wirken, aber für Maintainer nicht klar genug in Handlung übersetzt werden.

> **Pflicht:** Vor Ausführung dieses Prompts das Drift Policy Gate durchlaufen
> (siehe `.github/prompts/_partials/konventionen.md` und `.github/instructions/drift-policy.instructions.md`).

## Relevante Referenzen

- **Instruction:** `.github/instructions/drift-policy.instructions.md`
- **Bewertungssystem:** `.github/prompts/_partials/bewertungs-taxonomie.md`
- **Issue-Filing:** `.github/prompts/_partials/issue-filing.md`
- **Verwandte Prompts:** `drift-signal-quality.prompt.md`, `drift-fp-reduction.prompt.md`
- **Output-Implementierung:** `src/drift/output/`, `src/drift/models.py`

## Arbeitsmodus

- Bewerte Findings aus Sicht eines Maintainers unter Zeitdruck.
- Frage bei jedem Finding: Führt es zu einer Entscheidung oder nur zu weiterer Analyse?
- Trenne zwischen informativ, plausibel, handlungsfähig und dringend.
- Keine reine Signalentwicklung oder Recall-Betrachtung.

## Ziel

Finde die Muster, bei denen Drift technisch recht hat, aber für Maintainer trotzdem nicht stark genug zum Handeln motiviert. Liefere konkrete Verbesserungsvorschläge für stärkere Handlungsfähigkeit.

## Erfolgskriterien

Die Aufgabe ist erst abgeschlossen, wenn du beantworten kannst:
- Welche Findings sind informativ, aber nicht entscheidungsstark?
- Wo fehlt die klare Übersetzung von Signal zu Handlung?
- Wo ist Severity zu schwach, zu abstrakt oder nicht ausreichend begründet?
- Wo müsste Drift stärker erklären, warum etwas jetzt relevant ist?
- Welche Finding-Typen eignen sich am meisten für konkrete Aktionsvorschläge?

## Arbeitsregeln

- Bewerte reale Drift-Outputs, nicht hypothetische Szenarien.
- Führe `drift analyze --repo . --format json` und `--format rich` aus.
- Analysiere echte Finding-Texte auf Klarheit, Priorisierung und Next-Step-Qualität.
- Keine allgemeinen Schreibtipps — nur Drift-spezifische Output-Verbesserungen.

## Bewertungs-Labels

Verwende ausschließlich Labels aus `.github/prompts/_partials/bewertungs-taxonomie.md`:

- **Actionability-Score:** `1 automated` / `2 guided` / `3 human-review` / `4 blocked`
- **Risiko-Level:** `low` / `medium` / `high` / `critical`

## Artefakte

Erstelle Artefakte unter `work_artifacts/actionability_review_<YYYY-MM-DD>/`:

1. `summary.md` — Gesamtbewertung der Handlungsfähigkeit
2. `actionability_gaps.md` — Katalog der wichtigsten Lücken
3. `fix_recommendations.md` — Konkrete Verbesserungsvorschläge

## Workflow

### Phase 1: Findings sammeln

Erzeuge echte Drift-Outputs:

```bash
drift analyze --repo . --format json > work_artifacts/actionability_review_<YYYY-MM-DD>/raw_output.json
drift analyze --repo . --format rich
```

### Phase 2: Handlungsfähigkeit pro Finding bewerten

Für jedes Finding prüfen:
- Ist das Problem klar benannt?
- Ist die Ursache nachvollziehbar?
- Ist die Schwere begründet?
- Gibt es einen erkennbaren nächsten Schritt?
- Würde ein Maintainer danach handeln oder nur nicken?

Dokumentiere in `actionability_gaps.md`:

| Signal | Finding-Typ | Actionability-Score | Problem | Was fehlt | Empfehlung |
|--------|-------------|--------------------|---------|-----------|-----------| 

### Phase 3: Muster-Analyse

Gruppiere die Lücken nach:
- fehlende Priorisierung
- fehlende Begründung
- fehlende nächste Schritte
- zu abstrakte Ursachenformulierung
- unklare Severity

### Phase 4: Empfehlungen

Erstelle `fix_recommendations.md` mit konkreten Verbesserungen:

Für jede Empfehlung:
- Problem
- betroffene Signal-Typen
- vorgeschlagene Änderung
- erwarteter Nutzen
- Aufwand
- Priorität

## Abschlussentscheidung

Formuliere die 5 stärksten Änderungen, mit denen Drift-Findings deutlich operativer und priorisierbarer würden.
