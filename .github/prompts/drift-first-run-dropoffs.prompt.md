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

## Reasoning-Anforderungen

### Spannungsfelder

Navigiere aktiv folgende Spannungen — löse sie nicht vorschnell auf, sondern mache deine Abwägung transparent:

- **Einfachheit vs. Vollständigkeit:** Ein einfacher Quickstart lässt Features aus. Ein vollständiger Einstieg überfordert. Wo liegt der Optimalpunkt für Drift?
- **Kürze vs. Überzeugungskraft:** Schneller erster Output ≠ überzeugender erster Output. Was braucht der Nutzer zuerst — Speed oder Aha-Moment?
- **Selbsterklärender Output vs. Dokumentationsbedarf:** Wenn der Output Erklärung braucht, ist er dann schlecht oder ist das Feature komplex?

### Vor-Schlussfolgerungs-Checks

Bevor du eine Empfehlung finalisierst, prüfe:
- Welche Abbruchpunkte könntest du systematisch übersehen, weil du Drift bereits kennst?
- Gibt es Abbruchpunkte, die nur bei bestimmten Repo-Typen oder Nutzergruppen auftreten?
- Verwechselst du persönliche Irritation mit einem realen Nutzerproblem?

### Konfidenz-Kalibrierung

Gib für jeden identifizierten Abbruchpunkt an:
- **Konfidenz:** hoch / mittel / niedrig — dass er real ist (nicht nur theoretisch)
- **Evidenz:** Woraus leitest du ab, dass hier Nutzer tatsächlich abspringen?
- **Entkräftung:** Was müsste wahr sein, damit dieser Punkt kein echtes Problem ist?

### Fehlerschluss-Wächter

Prüfe aktiv gegen:
- **Curse of Knowledge:** Du kennst Drift. Erstnutzer nicht. Prüfe bei jeder Bewertung: Wüsste jemand ohne Vorwissen, was gemeint ist?
- **Survivorship Bias:** Du beobachtest nur die Punkte, die du selbst erlebst. Welche Stellen könnten Nutzer zum stillen Abbruch bringen, bevor sie überhaupt klicken?
- **Solutionism:** Schlage keine Lösung vor, bevor du das Problem vollständig artikuliert hast.

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

1. Wenn Drift nur 3 Abbruchpunkte beseitigen dürfte, welche wären das und warum?
2. **Gegenposition:** Argumentiere, warum der von dir am höchsten priorisierte Abbruchpunkt möglicherweise gar keiner ist. Was spricht dagegen?
3. **Falsifikation:** Was müsste beobachtbar sein, um deine Empfehlung zu widerlegen?
4. **Konfidenz-Statement:** Wie sicher bist du dir bei deinem Ranking? Was fehlt dir an Information, um sicherer zu sein?
5. **Blinder Fleck:** Welche Art von Abbruchpunkt könntest du mit deiner Methodik prinzipiell nicht entdecken?
