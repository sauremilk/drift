---
name: "Drift Integration Priorities"
description: "Bewertet Integrationen nach realem Adoptionseffekt statt nach Vollständigkeit. Liefert eine priorisierte Matrix der 3 wirksamsten Integrationen für Drift."
---

# Drift Integration Priorities

Du analysierst, welche Integrationen Drift am stärksten von „interessant" zu „regelmäßig genutzt" bewegen würden.

> **Pflicht:** Vor Ausführung dieses Prompts das Drift Policy Gate durchlaufen
> (siehe `.github/prompts/_partials/konventionen.md` und `.github/instructions/drift-policy.instructions.md`).

## Relevante Referenzen

- **Instruction:** `.github/instructions/drift-policy.instructions.md`
- **Bewertungssystem:** `.github/prompts/_partials/bewertungs-taxonomie.md`
- **Issue-Filing:** `.github/prompts/_partials/issue-filing.md`
- **Verwandte Prompts:** `drift-ci-gate.prompt.md`, `drift-shareability-review.prompt.md`
- **Aktuelle Integrationen:** `action.yml`, `src/drift/output/`, `src/drift/mcp_server.py`

## Arbeitsmodus

- Bewerte jede Integration nach Adoptionseffekt, Aufwand, Team-Fit und Anschlussfähigkeit.
- Bevorzuge wenige starke Hebel statt breiter Wunschliste.
- Trenne zwischen Demo-Attraktivität und realer täglicher Nutzung.
- Sammle nicht möglichst viele Integrationen, sondern priorisiere die wenigen mit echtem Wirkungspotenzial.

## Ziel

Identifiziere die Integrationen, die Drift am stärksten in tägliche Entwickler-Workflows verankern würden, und liefere eine belastbare Priorisierung.

## Erfolgskriterien

Die Aufgabe ist erst abgeschlossen, wenn du beantworten kannst:
- Welche Integrationen würden Drift am ehesten in tägliche Abläufe bringen?
- Welche Integrationen sind attraktiv, aber überschätzt?
- Welche verbessern First-Run-Value kaum, aber langfristige Adoption stark?
- Welche helfen Teams beim Weiterleiten, Diskutieren und Handeln?
- Welche 3 haben das beste Verhältnis aus Wirkung zu Aufwand?

## Arbeitsregeln

- Bewerte bestehende und denkbare Integrationen.
- Prüfe den aktuellen Stand: `action.yml`, SARIF-Output, MCP-Server, JSON-Output, Badge.
- Keine allgemeinen Integrations-Empfehlungen — nur Drift-spezifische Bewertungen.
- Unsicherheiten explizit benennen.

## Reasoning-Anforderungen

### Spannungsfelder

Navigiere aktiv folgende Spannungen — mache deine Abwägung transparent:

- **Breite Erreichbarkeit vs. Tiefe in wenigen Workflows:** Viele leichte Integrationen vs. wenige tiefe. Was bewegt Adoption stärker?
- **Demo-Attraktivität vs. täglicher Nutzen:** Manche Integrationen sehen in Demos spektakulär aus, werden aber selten genutzt. Prüfe für jede Empfehlung: Würde sie nach der Demo-Phase weiterleben?
- **Build vs. Leverage:** Eigene Integration vs. Andocken an bestehende Ökosysteme (z.B. GitHub Actions Marketplace, IDE-Plugins). Wo hat Drift einen Own-Build-Vorteil?

### Vor-Schlussfolgerungs-Checks

Bevor du eine Integration priorisierst:
- Hast du das Second-Order-Problem bedacht? (Eine CI-Integration erfordert auch: Dokumentation, Defaults, Error-Handling, Edge Cases.)
- Hast du geprüft, ob die Integration ein Pull-Mechanismus ist (Nutzer wollen es) oder ein Push-Mechanismus (wir glauben, sie sollten es wollen)?
- Gibt es eine bestehende Integration, die ausgebaut werden könnte statt eine neue zu bauen?

### Konfidenz-Kalibrierung

Gib für jede Integrations-Empfehlung an:
- **Konfidenz:** hoch / mittel / niedrig — dass sie tatsächlich Adoption steigert
- **Evidenz:** Woraus schließt du auf Nachfrage? (Feature-Requests, Vergleichstools, Workflow-Analyse?)
- **Entkräftung:** Was müsste wahr sein, damit diese Integration keinen Adoptionseffekt hat?

### Fehlerschluss-Wächter

Prüfe aktiv gegen:
- **Integration Laundry List:** Viele Integrationen auflisten ≠ die richtige priorisieren. Weniger ist meistens mehr.
- **Supply-Side-Thinking:** „Wir können das bauen, also sollten wir“ ist kein Priorisierungsgrund.
- **Survivorship Bias bei Vergleichs-Tools:** Nur weil SonarQube eine IDE-Integration hat, heißt das nicht, dass Drift eine braucht. Prüfe ob die Zielgruppen vergleichbar sind.

## Bewertungs-Labels

Verwende ausschließlich Labels aus `.github/prompts/_partials/bewertungs-taxonomie.md`:

- **Ergebnis-Bewertung:** `pass` / `review` / `fail`
- **Risiko-Level:** `low` / `medium` / `high` / `critical`

## Artefakte

Erstelle Artefakte unter `work_artifacts/integration_priorities_<YYYY-MM-DD>/`:

1. `summary.md` — Gesamtbewertung
2. `integration_matrix.md` — Bewertete Matrix aller relevanten Integrationen
3. `top_3_integrations.md` — Die 3 priorisierten Empfehlungen

## Workflow

### Phase 1: Bestandsaufnahme

Dokumentiere bestehende Integrationen:
- GitHub Action (`action.yml`)
- SARIF-Output
- JSON-Output
- MCP-Server
- Badge-Generierung
- CLI-Automation

### Phase 2: Kandidaten-Analyse

Untersuche zusätzlich denkbare Integrationen:
- PR-Kommentierung
- CI-Gating mit Schwellwerten
- GitHub Checks API
- Slack- oder Webhook-Integration
- IDE-Integration
- Dashboard oder Trend-Report
- Package-Vergleich oder Dependency-Kontext

### Phase 3: Integrations-Matrix

Erstelle `integration_matrix.md`:

| Integration | Status | Zielnutzer | Zielworkflow | Adoptionseffekt | Aufwand | Team-Fit | Risiko | Priorität |
|-------------|--------|-----------|-------------|----------------|---------|---------|--------|----------|

### Phase 4: Top 3 Empfehlungen

Erstelle `top_3_integrations.md`:

Für jede der 3 Empfehlungen:
- Integration
- Warum gerade diese
- erwarteter Adoptionseffekt
- Aufwand
- Risiken
- empfohlener erster Schritt

## Abschlussentscheidung

1. Empfiehl genau 3 Integrationen, die Drift jetzt priorisieren sollte. Begründe jede mit Wirkung, Aufwand und Risiko.
2. **Anti-Empfehlung:** Nenne 1 Integration, die verlockendes Potenzial hat, aber aktuell falsch priorisiert wäre. Erkläre warum und wann der richtige Zeitpunkt wäre.
3. **Steelman Nicht-Bauen:** Formuliere das stärkste Argument dafür, gar keine neue Integration zu bauen und stattdessen die bestehenden zu vertiefen.
4. **Sequenzierung:** In welcher Reihenfolge sollten die 3 Empfehlungen umgesetzt werden und warum? Gibt es Abhängigkeiten?
5. **Prüfbares Kriterium:** Woran erkennt man nach 4 Wochen, ob die priorisierte Integration den erwarteten Adoptionseffekt hat?
