---
name: "Drift Shareability Review"
description: "Bewertet, wie gut Drift-Ergebnisse in PRs, Issues, Slack, CI-Kontexte und Team-Diskussionen weiterverwendet werden können. Liefert Empfehlungen für teilbarere Outputs."
---

# Drift Shareability Review

Du analysierst, wie gut Drift-Ergebnisse heute in Pull Requests, Issues, Slack-Nachrichten, Reviews und Team-Diskussionen weiterverwendet und geteilt werden können.

> **Pflicht:** Vor Ausführung dieses Prompts das Drift Policy Gate durchlaufen
> (siehe `.github/prompts/_partials/konventionen.md` und `.github/instructions/drift-policy.instructions.md`).

## Relevante Referenzen

- **Instruction:** `.github/instructions/drift-policy.instructions.md`
- **Bewertungssystem:** `.github/prompts/_partials/bewertungs-taxonomie.md`
- **Issue-Filing:** `.github/prompts/_partials/issue-filing.md`
- **Verwandte Prompts:** `drift-ci-gate.prompt.md`, `drift-agent-ux.prompt.md`
- **Output-Implementierung:** `src/drift/output/`

## Arbeitsmodus

- Bewerte jeden Output danach, ob ein Nutzer ihn realistisch intern weiterleiten würde.
- Bevorzuge Formate mit hoher Klarheit und geringem Erklärungsbedarf.
- Trenne zwischen lesbar, teilbar und handlungsfördernd.
- Untersuche keine internen Implementierungsdetails.

## Ziel

Finde heraus, welche Drift-Ergebnisse sich heute gut oder schlecht in PR-, CI-, Team- und Review-Kontexte übertragen lassen, und empfiehl konkrete Verbesserungen für höhere Teilbarkeit.

## Erfolgskriterien

Die Aufgabe ist erst abgeschlossen, wenn du beantworten kannst:
- Welche Drift-Outputs lassen sich heute gut weitergeben?
- Welche Outputs sind zu lang, zu intern oder zu schwer konsumierbar?
- Wo fehlt ein Format für schnelle soziale Anschlussfähigkeit?
- Welche Information müsste in einer idealen PR-Zusammenfassung stehen?
- Welche Ausgabeform wäre für Teams am wirksamsten?

## Arbeitsregeln

- Erzeuge echte Drift-Outputs in verschiedenen Formaten.
- Bewerte Outputs in realistischen Weiterleitungsszenarien.
- Keine allgemeinen Output-Ratschläge — nur Drift-spezifische Verbesserungen.
- Unsicherheiten explizit benennen.

## Bewertungs-Labels

Verwende ausschließlich Labels aus `.github/prompts/_partials/bewertungs-taxonomie.md`:

- **Ergebnis-Bewertung:** `pass` / `review` / `fail`
- **Risiko-Level:** `low` / `medium` / `high` / `critical`

## Artefakte

Erstelle Artefakte unter `work_artifacts/shareability_review_<YYYY-MM-DD>/`:

1. `summary.md` — Gesamtbewertung
2. `shareability_scorecard.md` — Bewertung pro Output-Format und Zielkontext
3. `recommended_output_formats.md` — Empfehlungen für neue oder überarbeitete Formate

## Workflow

### Phase 1: Outputs erzeugen

Erzeuge Drift-Ergebnisse in allen verfügbaren Formaten:

```bash
drift analyze --repo . --format rich
drift analyze --repo . --format json
drift analyze --repo . --format sarif
```

### Phase 2: Teilbarkeits-Szenarien bewerten

Bewerte jeden Output für diese Szenarien:

| Szenario | Zielgruppe | Anforderung |
|----------|-----------|-------------|
| PR-Kommentar | Reviewer | Kurzfassung, Top-Findings, Trend |
| CI-Check-Output | Automatisierung | Maschinenlesbar, Exit-Code, Summary |
| Slack-Nachricht | Team | 5 Sätze Maximum, Handlungsorientiert |
| Issue-Erstellung | Maintainer | Finding-zu-Issue-Übersetzung |
| Management-Report | Tech Lead | Executive Summary, Trend, Risiko |

Dokumentiere in `shareability_scorecard.md`:

| Format | Szenario | Teilbarkeit | Problem | Empfehlung |
|--------|----------|------------|---------|-----------|

### Phase 3: Muster-Analyse

Identifiziere:
- Was macht bestimmte Outputs leicht teilbar?
- Was blockiert Teilbarkeit am stärksten?
- Welche Informationen fehlen für anschlussfähige Kommunikation?

### Phase 4: Empfehlungen

Erstelle `recommended_output_formats.md`:

Für jede Empfehlung:
- Zielkontext
- vorgeschlagenes Format oder Änderung
- Nutzen für Adoption
- Implementierungsaufwand
- erwarteter Adoptionshebel

## Abschlussentscheidung

Empfiehl genau 1 neues oder überarbeitetes Output-Format, das Drift am stärksten in PR- und Team-Workflows verankern würde. Begründe die Wahl.
