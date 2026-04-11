---
name: "Drift Trust Review"
description: "Analysiert Vertrauenswirkung von Drift-Findings aus Sicht skeptischer Maintainer. Identifiziert Vertrauensrisiken und -hebel jenseits reiner FP/FN-Statistik."
---

# Drift Trust Review

Du analysierst, welche Aspekte von Drift-Findings Vertrauen schaffen oder zerstören, insbesondere aus Sicht eines skeptischen Maintainers.

> **Pflicht:** Vor Ausführung dieses Prompts das Drift Policy Gate durchlaufen
> (siehe `.github/prompts/_partials/konventionen.md` und `.github/instructions/drift-policy.instructions.md`).

## Relevante Referenzen

- **Instruction:** `.github/instructions/drift-policy.instructions.md`
- **Bewertungssystem:** `.github/prompts/_partials/bewertungs-taxonomie.md`
- **Issue-Filing:** `.github/prompts/_partials/issue-filing.md`
- **Verwandte Prompts:** `drift-fp-reduction.prompt.md`, `drift-signal-quality.prompt.md`, `drift-actionability-review.prompt.md`
- **Signale:** `src/drift/signals/`

## Arbeitsmodus

- Frage bei jedem Finding: Würde ein Maintainer dieses Finding glauben, ignorieren oder aktiv ablehnen?
- Trenne zwischen statistischem FP-Risiko und wahrgenommenem Vertrauensverlust.
- Bewerte Explainability, Confidence, Severity, Reproduzierbarkeit, Tonalität und Fairness.
- Bevorzuge Maßnahmen, die Skepsis früh reduzieren.

## Ziel

Finde die Wahrnehmungslücke zwischen technischer Korrektheit und erlebtem Vertrauen. Liefere konkrete Verbesserungen, die Skepsis reduzieren und Glaubwürdigkeit stärken.

## Erfolgskriterien

Die Aufgabe ist erst abgeschlossen, wenn du beantworten kannst:
- Welche Findings oder Signale wirken erklärungsbedürftig?
- Wo fehlt sichtbare Begründung?
- Wo würde ein Maintainer sagen: „Das glaube ich noch nicht"?
- Welche Elemente reduzieren Skepsis sofort?
- Welche Output-Muster verstärken Vertrauen am stärksten?

## Arbeitsregeln

- Arbeite mit echten Drift-Outputs.
- Bewerte aus Maintainer-Perspektive unter Zeitdruck.
- Fokus auf Wahrnehmung, nicht nur auf Metriken.
- Keine reine FP/FN-Analyse — sondern Vertrauensanalyse.
- Unsicherheiten explizit benennen.

## Bewertungs-Labels

Verwende ausschließlich Labels aus `.github/prompts/_partials/bewertungs-taxonomie.md`:

- **Signal-Vertrauensstufe:** `trusted` / `needs_review` / `unsafe`
- **Risiko-Level:** `low` / `medium` / `high` / `critical`

## Artefakte

Erstelle Artefakte unter `work_artifacts/trust_review_<YYYY-MM-DD>/`:

1. `summary.md` — Gesamtbewertung
2. `trust_risks.md` — Katalog der Vertrauensrisiken
3. `trust_levers.md` — Katalog der Vertrauenshebel und Empfehlungen

## Workflow

### Phase 1: Findings erzeugen

```bash
drift analyze --repo . --format json > work_artifacts/trust_review_<YYYY-MM-DD>/raw_output.json
drift analyze --repo . --format rich
```

### Phase 2: Vertrauenswirkung pro Signal bewerten

Für jedes Signal und seine Findings prüfen:
- Ist die Begründung nachvollziehbar?
- Ist die Severity plausibel?
- Ist die Confidence sichtbar und verständlich?
- Wirkt das Finding fair oder übertrieben?
- Ist das Ergebnis reproduzierbar und konsistent?
- Würde ein skeptischer Maintainer handeln oder ignorieren?

Dokumentiere in `trust_risks.md`:

| Signal | Finding | Vertrauensstufe | Problem | Wahrnehmungsrisiko | Empfehlung |
|--------|---------|-----------------|---------|-------------------|-----------| 

### Phase 3: Positive Vertrauenselemente identifizieren

Identifiziere, was heute bereits Vertrauen schafft:
- Welche Begründungen überzeugen?
- Welche Priorisierungen wirken fair?
- Welche Outputs erzeugen sofort Handlungsdruck?
- Welche Erklärungsmuster sind besonders stark?

### Phase 4: Empfehlungen

Erstelle `trust_levers.md`:

Für jeden Hebel:
- Beobachtetes Problem oder ungenutztes Potenzial
- Auswirkung auf Adoption und Nutzertreue
- Drift-spezifische Empfehlung
- Aufwand
- Priorität

## Abschlussentscheidung

Nenne die 3 kurzfristig wirksamsten Änderungen, um das Vertrauen in Drift-Findings spürbar zu erhöhen.
