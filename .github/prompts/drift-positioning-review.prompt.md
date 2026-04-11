---
name: "Drift Positioning & README Review"
description: "Bewertet Drift als Produkt statt als Codebase: Positionierung, Nutzenversprechen, README-Wirkung, Zielgruppenklarheit und Differenzierung. Liefert konkrete Kommunikationsverbesserungen."
---

# Drift Positioning & README Review

Du analysierst Drift als Produkt, nicht als Codebase. Dein Fokus liegt auf Positionierung, Narrative, Zielgruppenansprache und Einstiegsdokumentation.

> **Pflicht:** Vor Ausführung dieses Prompts das Drift Policy Gate durchlaufen
> (siehe `.github/prompts/_partials/konventionen.md` und `.github/instructions/drift-policy.instructions.md`).

## Relevante Referenzen

- **Instruction:** `.github/instructions/drift-policy.instructions.md`
- **Bewertungssystem:** `.github/prompts/_partials/bewertungs-taxonomie.md`
- **Issue-Filing:** `.github/prompts/_partials/issue-filing.md`
- **Verwandte Prompts:** `drift-onboarding.prompt.md`, `drift-first-run-dropoffs.prompt.md`
- **Produktoberfläche:** `README.md`, `DEVELOPER.md`, `docs/`, `pyproject.toml`

## Arbeitsmodus

- Lies Drift wie ein potenzieller Anwender, nicht wie ein Maintainer.
- Bewerte, was in den ersten 30 bis 90 Sekunden verstanden wird.
- Trenne zwischen technischer Tiefe und überzeugender Nutzenkommunikation.
- Keine Code-Reviews — nur Produktkommunikation.

## Ziel

Bewerte, ob Positionierung und README stark genug sind, um Adoption auszulösen, und liefere konkrete Verbesserungsvorschläge.

## Erfolgskriterien

Die Aufgabe ist erst abgeschlossen, wenn du beantworten kannst:
- Was versteht ein neuer Leser in den ersten 30 Sekunden?
- Ist klar, warum Drift mehr ist als Linting oder bloße Analyse?
- Ist klar, für wen Drift besonders wertvoll ist?
- Welche Narrative sind zu intern, zu abstrakt oder zu wenig verkaufsstark?
- Welche drei Botschaften fehlen oder sind zu schwach?

## Arbeitsregeln

- Bewerte Drift mit der Brille eines skeptischen, aber neugierigen Entwicklers.
- Vergleiche die Klarheit des Nutzenversprechens mit erfolgreichen Dev-Tools.
- Keine allgemeinen Marketing-Tipps — nur Drift-spezifische Produktkommunikation.
- Unsicherheiten explizit benennen.

## Bewertungs-Labels

Verwende ausschließlich Labels aus `.github/prompts/_partials/bewertungs-taxonomie.md`:

- **Ergebnis-Bewertung:** `pass` / `review` / `fail`
- **Risiko-Level:** `low` / `medium` / `high` / `critical`

## Artefakte

Erstelle Artefakte unter `work_artifacts/positioning_readme_<YYYY-MM-DD>/`:

1. `summary.md` — Gesamtbewertung
2. `messaging_gaps.md` — Kommunikationslücken
3. `rewritten_positioning.md` — Konkrete Neuformulierungen

## Workflow

### Phase 1: Erstkontakt-Analyse

Lies `README.md` komplett und dokumentiere:
- Welches Problem wird benannt?
- Welcher Nutzen wird versprochen?
- Wer wird angesprochen?
- In welchem Satz wird die Differenzierung klar?
- In welchem Satz verliert ein Erstleser die Motivation?

### Phase 2: Nutzenversprechen bewerten

Bewerte das aktuelle Nutzenversprechen anhand:

| Kriterium | Bewertung | Anmerkung |
|-----------|-----------|-----------|
| Problemklarheit | | |
| Zielgruppenspezifik | | |
| Differenzierung | | |
| Sofortverständlichkeit | | |
| Motivation zum Ausprobieren | | |
| Verhältnis Tiefe zu Überzeugungskraft | | |

### Phase 3: Vergleich mit Positionierungsmustern

Vergleiche Drift mit der Positionierung erfolgreicher Dev-Tools:
- Wie schnell kommunizieren andere Tools ihren Kernnutzen?
- Welche Narrative-Muster funktionieren für Analysetools besonders gut?
- Was fehlt bei Drift im direkten Vergleich?

### Phase 4: Kommunikationslücken

Erstelle `messaging_gaps.md`:
- Die 5 größten Kommunikationslücken
- warum sie entstehen
- welche Wirkung sie auf Adoption haben
- wie sie geschlossen werden könnten

### Phase 5: Neuformulierungen

Erstelle `rewritten_positioning.md`:
- Empfohlene Kurzpositionierung (5 Sätze)
- Empfohlenes Hero-Statement (1 Satz)
- Empfohlene README-Einstiegsstruktur
- 3 alternative Problem-Statements
- empfohlene Demo-Reihenfolge

## Abschlussentscheidung

Schreibe die empfohlene Kurzpositionierung für Drift in 5 Sätzen und nenne die 3 wichtigsten README-Änderungen.
