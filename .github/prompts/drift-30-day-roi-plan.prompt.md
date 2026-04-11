---
name: "Drift 30-Day ROI Plan"
description: "Erstellt eine belastbare, priorisierte Liste von Drift-Verbesserungen mit maximalem ROI innerhalb von 30 Tagen. Fokus auf First-Run-Value, Adoption, Vertrauen und Handlungsfähigkeit."
---

# Drift 30-Day ROI Plan

Du erstellst eine belastbare Priorisierung der Drift-Verbesserungen mit dem größten kombinierten Effekt auf First-Run-Value, Adoption, Vertrauen und Handlungsfähigkeit innerhalb von 30 Tagen.

> **Pflicht:** Vor Ausführung dieses Prompts das Drift Policy Gate durchlaufen
> (siehe `.github/prompts/_partials/konventionen.md` und `.github/instructions/drift-policy.instructions.md`).

## Relevante Referenzen

- **Instruction:** `.github/instructions/drift-policy.instructions.md`
- **Bewertungssystem:** `.github/prompts/_partials/bewertungs-taxonomie.md`
- **Issue-Filing:** `.github/prompts/_partials/issue-filing.md`
- **Verwandte Prompts:** Alle anderen Drift-Review-Prompts (`drift-first-run-dropoffs.prompt.md`, `drift-actionability-review.prompt.md`, `drift-shareability-review.prompt.md`, `drift-positioning-review.prompt.md`, `drift-trust-review.prompt.md`, `drift-signal-clarity.prompt.md`, `drift-integration-priorities.prompt.md`, `drift-repo-segment-fit.prompt.md`, `drift-role-based-review.prompt.md`)
- **Roadmap:** `ROADMAP.md`
- **Backlog:** `.internal/BACKLOG.md`

## Arbeitsmodus

- Bewerte Maßnahmen nach Impact, Aufwand, Risiko, Abhängigkeiten und Zeit bis Wirkung.
- Bevorzuge wenige hochwirksame Hebel statt vieler kleiner Optimierungen.
- Keine Wunschliste — ein realistischer, umsetzbarer Plan.
- Berücksichtige bestehende Roadmap und Backlog.

## Ziel

Liefere einen konkreten 30-Tage-Umsetzungsplan für Drift, der die wirksamsten Verbesserungen in der richtigen Reihenfolge priorisiert.

## Erfolgskriterien

Die Aufgabe ist erst abgeschlossen, wenn du beantworten kannst:
- Welche Maßnahme hätte den höchsten Gesamthebel?
- Welche Maßnahme wäre der beste kleine Einstieg?
- Welche Maßnahme würde am meisten Vertrauen schaffen?
- Welche Maßnahme würde Adoption am stärksten erhöhen?
- Welche Maßnahme wäre verführerisch, aber aktuell falsch priorisiert?

## Arbeitsregeln

- Konsolidiere relevante Schwächen über Produkt, Output, Doku, Workflow, Vertrauen und Adoption.
- Jede Maßnahme muss realistisch in 30 Tagen umsetzbar sein.
- Falls Artefakte von Schwester-Prompts existieren, nutze sie als Input.
- Keine allgemeinen Strategieempfehlungen — nur umsetzbare Drift-Maßnahmen.
- Unsicherheiten explizit benennen.

## Reasoning-Anforderungen

### Spannungsfelder

Navigiere aktiv folgende Spannungen — mache deine Abwägung transparent:

- **Kurzfristiger Quick Win vs. langfristiger Strukturhebel:** Ein Quick Win zeigt sofort Wirkung, baut aber keine Substanz auf. Ein Strukturhebel braucht Zeit, wirkt aber nachhaltiger. Priorisiere bewusst.
- **Vertrauen vs. Adoption:** Vertrauens-Maßnahmen (weniger FP, bessere Erklärungen) können Adoption verlangsamen (weniger aggressive Findings). Wie gehst du damit um?
- **Sichtbare vs. fundamentale Verbesserung:** Nutzer bemerken UI-Improvements sofort, aber Backend-Fixes können langfristig wichtiger sein. Wie balancierst du wahrgenommenen vs. realen Fortschritt?

### Vor-Schlussfolgerungs-Checks

Bevor du eine Maßnahme in den 30-Tage-Plan aufnimmst:
- Ist sie wirklich in 30 Tagen umsetzbar — oder sagst du dir „bestimmt machbar“ ohne echte Aufwandsschätzung?
- Welche versteckten Abhängigkeiten oder Vorarbeit erfordert die Maßnahme?
- Ist die erwartete Wirkung ein messbares Ergebnis oder nur ein gutes Gefühl?

### Konfidenz-Kalibrierung

Gib für den Gesamtplan an:
- **Plan-Konfidenz:** hoch / mittel / niedrig — dass der Plan als Ganzes umsetzbar und wirksam ist
- **Schwächstes Glied:** Welche einzelne Maßnahme hat die niedrigste Konfidenz und warum?
- **Plan B:** Was wäre der Kern-3-Maßnahmen-Plan, falls die Hälfte der Maßnahmen scheitert?

### Fehlerschluss-Wächter

Prüfe aktiv gegen:
- **Planungs-Optimismus:** Du planst als KI ohne Kontextwechsel, Meetings, Debugging und Unvorhergesehenes. Puffere realistisch.
- **Impact-Überschätzung:** „Verbessert Adoption um X%“ ist nicht messbar. Formuliere konkrete, beobachtbare Erfolgskriterien.
- **Vollständigkeits-Bias:** Ein 30-Tage-Plan mit 15 Maßnahmen ist kein Plan, sondern eine Überforderung. Weniger Maßnahmen, dafür tiefer durchdacht.
- **Recency Bias:** Priorisiere nicht nur, was dir gerade einfällt, sondern prüfe gegen die existierende Roadmap und den Backlog.

## Bewertungs-Labels

Verwende ausschließlich Labels aus `.github/prompts/_partials/bewertungs-taxonomie.md`:

- **Ergebnis-Bewertung:** `pass` / `review` / `fail`
- **Risiko-Level:** `low` / `medium` / `high` / `critical`

## Artefakte

Erstelle Artefakte unter `work_artifacts/roi_30_day_plan_<YYYY-MM-DD>/`:

1. `summary.md` — Gesamtbewertung
2. `ranked_initiatives.md` — Bewertete und geordnete Maßnahmen
3. `30_day_plan.md` — Konkreter Umsetzungsplan

## Workflow

### Phase 1: Schwächen konsolidieren

Sammle Drift-Verbesserungspotenziale aus:
- eigener Analyse von Produkt, CLI, Output, Doku, MCP
- vorhandenen `work_artifacts/` von Schwester-Prompts (falls verfügbar)
- `ROADMAP.md` und `.internal/BACKLOG.md`
- eigener Nutzungserfahrung

### Phase 2: Maßnahmen definieren

Erstelle eine Liste von 10 bis 15 realistischen Maßnahmen.

Für jede Maßnahme:
- Beschreibung
- Zielgröße: First-Run-Value / Adoption / Vertrauen / Handlungsfähigkeit
- Art: Produktarbeit / CLI / Output / MCP / Doku / Integration / Distribution

### Phase 3: Scoring

Bewerte jede Maßnahme in `ranked_initiatives.md`:

| Maßnahme | Zielgröße | Impact (1–5) | Aufwand (1–5) | Risiko (1–5) | Abhängigkeiten | Zeit bis Wirkung | Score | Kategorie |
|----------|----------|-------------|--------------|-------------|---------------|-----------------|-------|-----------|
| | | | | | | | | Quick Win / Mittelfristiger Hebel / Strategische Wette |

Score-Formel: `(Impact × 2) / (Aufwand + Risiko)`

### Phase 4: Reihenfolge und Abhängigkeiten

Ordne die Maßnahmen in eine realistische 30-Tage-Reihenfolge:
- Woche 1: Quick Wins mit sofortiger Wirkung
- Woche 2: Mittelfristige Hebel aufsetzen
- Woche 3: Größere Verbesserungen umsetzen
- Woche 4: Verfeinern, validieren, abschließen

Dokumentiere Abhängigkeiten zwischen Maßnahmen.

### Phase 5: 30-Tage-Plan

Erstelle `30_day_plan.md`:

```
## Woche 1: [Fokus]
- [ ] Maßnahme A — [Kurzbeschreibung]
- [ ] Maßnahme B — [Kurzbeschreibung]

## Woche 2: [Fokus]
- [ ] Maßnahme C — [Kurzbeschreibung]
...

## Woche 3: [Fokus]
...

## Woche 4: [Fokus]
...
```

### Phase 6: Negativfilter

Dokumentiere explizit:
- Maßnahmen, die verführerisch, aber aktuell falsch priorisiert wären
- Maßnahmen, die mehr Aufwand als Wirkung erzeugen
- Maßnahmen, die Drift komplexer machen, ohne Kernwert zu steigern

## Abschlussentscheidung

Liefere:
- den besten Quick Win
- den stärksten Vertrauenshebel
- den stärksten Adoptionshebel
- die verführerische, aber aktuell falsche Priorität

Zusätzlich:
1. **Steelman der Nicht-Handlung:** Formuliere das stärkste Argument dafür, in den nächsten 30 Tagen überhaupt nichts an den hier identifizierten Punkten zu ändern und stattdessen nur Kernentwicklung zu betreiben.
2. **Falsifikation:** Was wäre nach 30 Tagen beobachtbar, wenn der Plan gescheitert ist? Definiere konkrete Failure-Kriterien.
3. **Sequenz-Sensitivität:** Wie stark ändert sich das Gesamtergebnis, wenn du die Reihenfolge der Maßnahmen umkehrst? Sind Reihenfolge-Abhängigkeiten real oder kosmetisch?
4. **Konfidenz-Statement:** Wie sicher bist du, dass deine Top-3-Maßnahmen die richtigen sind? Was fehlt dir an Information?

Beantworte abschließend:
Wenn Drift in den nächsten 30 Tagen nur 3 Dinge umsetzen dürfte, welche wären das und warum?
