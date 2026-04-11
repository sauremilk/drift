---
name: "Drift First-Run Dropoffs"
description: "Analysiert Abbruchpunkte neuer Nutzer zwischen Erstkontakt und dauerhafter Nutzung. Liefert priorisierte Reibungs- und Vertrauenslücken mit konkreten Verbesserungsvorschlägen."
---

# Drift First-Run Dropoffs

Du analysierst Drift aus der Perspektive eines skeptischen Erstnutzers und identifizierst die konkreten Stellen, an denen neue Nutzer nach dem ersten Kontakt oder dem ersten Run abspringen.

> **Pflicht:** Vor Ausführung dieses Prompts das Drift Policy Gate durchlaufen
> (siehe `.github/prompts/_partials/konventionen.md` und `.github/instructions/drift-policy.instructions.md`).

## Relevante Referenzen

- **Instruction:** `.github/instructions/drift-policy.instructions.md`
- **Bewertungssystem:** `.github/prompts/_partials/bewertungs-taxonomie.md`
- **Issue-Filing:** `.github/prompts/_partials/issue-filing.md`
- **Verwandte Prompts:** `drift-onboarding.prompt.md`, `drift-agent-ux.prompt.md`
- **Einstiegspunkte:** `README.md`, `DEVELOPER.md`, `src/drift/commands/`

## Arbeitsmodus

- Arbeite aus Sicht eines skeptischen Erstnutzers mit begrenzter Geduld.
- Simuliere den Weg vom ersten Kontakt bis zur Entscheidung „weiter nutzen oder abbrechen".
- Beobachte und dokumentiere Reibung, bevor du bewertest.
- Trenne klar zwischen harter Reibung, weicher Reibung und Vertrauenslücken.
- Benenne nicht nur Symptome, sondern die vermutete Ursache.

## Ziel

Identifiziere die konkreten Abbruchpunkte, an denen neue Nutzer Drift verlieren, und liefere priorisierte Verbesserungsvorschläge, die First-Run-Value und Adoption direkt erhöhen.

## Erfolgskriterien

Die Aufgabe ist erst abgeschlossen, wenn du beantworten kannst:
- An welchen Stellen versteht ein Nutzer Drift nicht schnell genug?
- Wo entsteht zu viel Aufwand vor dem ersten Aha-Moment?
- Wo wirkt der Output zu abstrakt, zu intern oder zu wenig priorisiert?
- Wo fehlen klare nächste Schritte?
- Welche Hürden wären leicht zu beheben und welche strukturell?

## Arbeitsregeln

- Bewerte jeden Punkt nach Einfluss auf First-Run-Value und Adoption.
- Unterscheide zwischen Problemen des Produkts, der Kommunikation, der Defaults und der Ergebnisdarstellung.
- Keine allgemeinen UX-Ratschläge — nur Drift-spezifische Beobachtungen.
- Unsicherheiten explizit benennen.

## Bewertungs-Labels

Verwende ausschließlich Labels aus `.github/prompts/_partials/bewertungs-taxonomie.md`:

- **Risiko-Level:** `low` / `medium` / `high` / `critical`
- **Ergebnis-Bewertung:** `pass` / `review` / `fail`

## Artefakte

Erstelle Artefakte unter `work_artifacts/first_run_dropoffs_<YYYY-MM-DD>/`:

1. `summary.md` — Gesamtbewertung
2. `dropoff_catalog.md` — Katalog aller identifizierten Abbruchpunkte
3. `prioritized_fixes.md` — Priorisierte Verbesserungsvorschläge

## Workflow

### Phase 1: Erstkontakt simulieren

Lies README, Quickstart und Produktbeschreibung wie ein Erstnutzer.

Dokumentiere:
- Was wird in den ersten 30 Sekunden verstanden?
- Was bleibt unklar?
- Wo entsteht Motivation weiterzumachen?
- Wo entsteht Zweifel oder Desinteresse?

### Phase 2: Installation und First Run

Führe den typischen Einstiegsweg aus:

```bash
pip install drift-analyzer
drift --help
drift analyze --repo . --format rich
```

Dokumentiere:
- Reibung bei Installation
- Verständlichkeit der CLI-Hilfe
- Qualität und Wirkung des ersten Outputs
- Zeitaufwand bis zum ersten sinnvollen Ergebnis

### Phase 3: Erste Findings bewerten

Analysiere die Findings des ersten Runs:
- Sind sie verständlich ohne Vorwissen?
- Ist die Priorisierung nachvollziehbar?
- Gibt es klare nächste Schritte?
- Erzeugen die Findings Handlungsdruck oder nur Information?

### Phase 4: Nächste Schritte prüfen

Bewerte, was nach dem ersten Run naheliegend wäre:
- Ist klar, was der Nutzer als Nächstes tun soll?
- Gibt es Folge-Workflows, CI-Einbindung oder Vertiefungsoptionen?
- Oder endet die Erfahrung nach dem ersten Output?

### Phase 5: Abbruchpunkte katalogisieren

Erstelle den vollständigen Katalog in `dropoff_catalog.md`:

| Nr. | Abbruchpunkt | Moment im Nutzerfluss | Art der Reibung | Ursache | Risiko-Level | Auswirkung auf |
|-----|-------------|----------------------|----------------|---------|-------------|---------------|
| | | | harte Reibung / weiche Reibung / Vertrauenslücke | | | First-Run-Value / Adoption / beides |

### Phase 6: Priorisierte Empfehlungen

Erstelle `prioritized_fixes.md` mit den 10 wichtigsten Verbesserungen:

Für jeden Fix:
- Beschreibung
- adressierter Abbruchpunkt
- erwarteter Nutzen
- Aufwand
- Risiko
- Priorität

## Abschlussentscheidung

Beantworte abschließend:
Wenn Drift in den nächsten 30 Tagen nur 3 Abbruchpunkte beseitigen dürfte, welche wären das und warum?
