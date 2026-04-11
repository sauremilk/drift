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

## Reasoning-Anforderungen

### Spannungsfelder

Navigiere aktiv folgende Spannungen — mache deine Abwägung transparent:

- **Diagnosetiefe vs. Handlungsdruck:** Je tiefer die Analyse, desto weniger klar oft der nächste Schritt. Wo endet Diagnose und wo beginnt Handlungsfähigkeit?
- **Allgemeingültigkeit vs. Kontextspezifik:** Eine universelle Empfehlung trifft nie ganz. Eine kontextspezifische ist nicht portabel. Wo ist der Optimalpunkt?
- **Automatisierbarkeit vs. Urteilsbedarf:** Manche Findings brauchen menschliches Urteil. Ist das ein Mängel des Findings oder ein Merkmal des Problems?

### Vor-Schlussfolgerungs-Checks

Bevor du ein Finding als „nicht handlungsfähig“ klassifizierst:
- Liegt es am Finding-Text oder an der Natur des Problems? (Nicht jedes Problem hat eine einfache nächste Aktion.)
- Wäre das Finding für eine andere Rolle (Staff Engineer vs. Junior Dev) doch handlungsfähig?
- Verwechselst du „handlungsfähig“ mit „sofort automatisierbar“?

### Konfidenz-Kalibrierung

Gib für jede Actionability-Lücke an:
- **Konfidenz:** hoch / mittel / niedrig — dass die Lücke real ist
- **Evidenz:** Woran machst du fest, dass ein Maintainer hier nicht handeln würde?
- **Entkräftung:** In welchem Kontext wäre dieses Finding doch ausreichend handlungsfähig?

### Fehlerschluss-Wächter

Prüfe aktiv gegen:
- **Illusion of Actionability:** Ein Finding klingt operativ („refactor X“), führt aber zu keiner klaren, scoped Aktion. Prüfe ob „handlungsfähig“ wirklich „durchführbar“ bedeutet.
- **Metric Fixation:** Actionability-Score als Selbstzweck statt als Proxy für reales Handeln.
- **Expert Bias:** Du bewertest als KI mit Vollzugriff auf den Code. Ein Maintainer hat 5 Minuten. Kalibriere darauf.

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

1. Formuliere die 5 stärksten Änderungen, mit denen Drift-Findings deutlich operativer und priorisierbarer würden.
2. **Gegenposition:** Für welche deiner Top-5-Empfehlungen gibt es ein starkes Gegenargument? Formuliere es.
3. **Grenzfall:** Nenne ein Finding, bei dem du unsicher bist, ob mangelnde Actionability ein Bug oder ein Feature ist.
4. **Falsifikation:** Wie könnte man empirisch testen, ob deine Empfehlungen tatsächlich zu mehr Handlung führen?
5. **Was du nicht beurteilen kannst:** Welche Aspekte der Handlungsfähigkeit liegen außerhalb deiner Beurteilungsfähigkeit (z.B. Team-Dynamik, Organisationskultur)?
