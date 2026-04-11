---
name: "Drift Role-Based Review"
description: "Analysiert Drift aus mehreren Nutzerrollen (Maintainer, Staff Engineer, Tech Lead, OSS-Contributor, Security Reviewer, Engineering Manager). Findet rollenübergreifende Verbesserungshebel."
---

# Drift Role-Based Review

Du analysierst Drift aus mehreren realistischen Nutzerrollen und findest heraus, welche Fragen, Erwartungen und Entscheidungsbedarfe verschiedene Nutzergruppen direkt nach einem Drift-Lauf haben.

> **Pflicht:** Vor Ausführung dieses Prompts das Drift Policy Gate durchlaufen
> (siehe `.github/prompts/_partials/konventionen.md` und `.github/instructions/drift-policy.instructions.md`).

## Relevante Referenzen

- **Instruction:** `.github/instructions/drift-policy.instructions.md`
- **Bewertungssystem:** `.github/prompts/_partials/bewertungs-taxonomie.md`
- **Issue-Filing:** `.github/prompts/_partials/issue-filing.md`
- **Verwandte Prompts:** `drift-actionability-review.prompt.md`, `drift-trust-review.prompt.md`, `drift-positioning-review.prompt.md`
- **Output:** `src/drift/output/`

## Arbeitsmodus

- Simuliere jede Rolle realistisch und mit rollenspezifischen Prioritäten.
- Bewerte Drift-Outputs pro Rolle, nicht pauschal.
- Suche nach Mustern, die mehrere Rollen gleichzeitig verbessern.
- Keine rein technische Vollanalyse ohne Rollenkontext.

## Ziel

Finde heraus, was jede Nutzerrolle direkt nach dem ersten Drift-Run wissen oder tun will und wo Drift diese Fragen noch nicht sauber beantwortet. Liefere rollenübergreifende Verbesserungshebel.

## Erfolgskriterien

Die Aufgabe ist erst abgeschlossen, wenn du für jede Rolle beantworten kannst:
- Was will diese Person nach dem ersten Drift-Run wissen?
- Welche Teile des Outputs sind für sie sofort nützlich?
- Was fehlt oder ist unzureichend?
- Wo verliert Drift diese Rolle?
- Welche Form der Zusammenfassung, Priorisierung oder Handlungsempfehlung wäre ideal?

## Arbeitsregeln

- Verwende echte Drift-Outputs als Grundlage.
- Bewerte pro Rolle separat.
- Identifiziere danach Muster über Rollen hinweg.
- Keine allgemeinen UX-Empfehlungen — nur rollenspezifische Drift-Verbesserungen.
- Unsicherheiten explizit benennen.

## Reasoning-Anforderungen

### Spannungsfelder

Navigiere aktiv folgende Spannungen — mache deine Abwägung transparent:

- **Rollenspezifische Tiefe vs. übergreifende Konsistenz:** Je stärker der Output auf eine Rolle zugeschnitten ist, desto schlechter passt er für andere. Wo ist der sweet spot für Drift?
- **Customization vs. One-Size-Fits-All:** Sollte Drift rollenbasierte Views anbieten oder einen Output, der für alle funktioniert? Was ist realistisch?
- **Information Density für Maintainer vs. Abstraktion für Manager:** Ein Manager will 3 Sätze. Ein Maintainer will alle Details. Kann ein Tool beides gleichzeitig?

### Vor-Schlussfolgerungs-Checks

Bevor du eine Rolle als „schlecht bedient“ klassifizierst:
- Ist diese Rolle überhaupt eine realistische Drift-Zielgruppe? Nicht jede Rolle muss optimal bedient werden.
- Ist das Problem am Output oder an der Art, wie die Rolle Drift konsumiert (direkt vs. gefiltert durch jemand anderen)?
- Wäre eine Verbesserung für Rolle X wirklich eine Verbesserung — oder würde sie den Output für Rolle Y verschlechtern?

### Konfidenz-Kalibrierung

Gib für jedes Rollenprofil an:
- **Konfidenz:** hoch / mittel / niedrig — dass du die Bedürfnisse dieser Rolle realistisch einschätzt
- **Basis:** Eigene Erfahrung, Inferenz aus der Rolle, oder Hypothese?
- **Entkräftung:** Was würde ein echter Vertreter dieser Rolle anders bewerten als du?

### Fehlerschluss-Wächter

Prüfe aktiv gegen:
- **Rollen-Stereotypisierung:** „Manager wollen nur Executive Summaries“ ist ein Klischee. Manche Manager lesen jeden Finding. Differenziere innerhalb der Rolle.
- **Gleichverteilungs-Bias:** Nicht jede Rolle ist gleich wichtig für Drift. Priorisiere nach Adoptionsrelevanz, nicht nach Vollständigkeit.
- **Simulation statt Empirie:** Du simulierst Rollen als KI. Markiere explizit, wo deine Rollensimulation unsicher ist.

## Bewertungs-Labels

Verwende ausschließlich Labels aus `.github/prompts/_partials/bewertungs-taxonomie.md`:

- **Ergebnis-Bewertung:** `pass` / `review` / `fail`
- **Actionability-Score:** `1 automated` / `2 guided` / `3 human-review` / `4 blocked`

## Artefakte

Erstelle Artefakte unter `work_artifacts/role_based_review_<YYYY-MM-DD>/`:

1. `summary.md` — Gesamtbewertung
2. `role_profiles.md` — Detaillierte Bewertung pro Rolle
3. `cross_role_improvements.md` — Rollenübergreifende Empfehlungen

## Workflow

### Phase 1: Drift-Output erzeugen

```bash
drift analyze --repo . --format rich
drift analyze --repo . --format json
```

### Phase 2: Rollenprofile bewerten

Bewerte Drift für jede der folgenden Rollen:

**Rolle 1: Maintainer**
- Primärfrage: Was muss ich an meinem Code ändern?
- Kernbedarf: priorisierte Findings, klare nächste Schritte, wenig Noise

**Rolle 2: Staff Engineer**
- Primärfrage: Wie steht es um die Architektur-Gesundheit?
- Kernbedarf: Trends, Module-Scores, strategische Risiken

**Rolle 3: Tech Lead**
- Primärfrage: Wo investiere ich als Nächstes Zeit?
- Kernbedarf: Executive Summary, ROI-Priorisierung, Team-Kommunikation

**Rolle 4: OSS-Contributor**
- Primärfrage: Was kann ich schnell fixen?
- Kernbedarf: leicht adressierbare Findings, klare Scope-Begrenzung

**Rolle 5: Security-affiner Reviewer**
- Primärfrage: Gibt es strukturelle Sicherheitsrisiken?
- Kernbedarf: Security-relevante Signale, Vertrauenswürdigkeit, Schweregrade

**Rolle 6: Engineering Manager**
- Primärfrage: Wie präsentiere ich Architektur-Qualität?
- Kernbedarf: Report-Format, Trends, Vergleichbarkeit

Dokumentiere pro Rolle in `role_profiles.md`:

| Aspekt | Bewertung | Anmerkung |
|--------|-----------|-----------|
| Sofort nützliche Teile | | |
| Fehlende Information | | |
| Schwachste Stelle | | |
| Ideales Format | | |

### Phase 3: Rollenübergreifende Muster

Identifiziere in `cross_role_improvements.md`:
- Welche Verbesserungen helfen mehreren Rollen gleichzeitig?
- Wo gibt es Rollenkonflikte (was Rolle A hilft, stört Rolle B)?
- Welche Priorisierung maximiert den Gesamtnutzen?

## Abschlussentscheidung

1. Nenne die 5 Änderungen, die über mehrere Rollen hinweg den größten Mehrwert für Drift stiften würden. Ordne nach Wirkungsbreite.
2. **Rollenkonflikte:** Nenne mindestens 1 Verbesserung, die für eine Rolle hilft, aber eine andere Rolle verschlechtert. Wie würdest du den Konflikt lösen?
3. **Priorisierung der Rollen selbst:** Welche 2 Rollen sind für Drifts Adoption am wichtigsten? Begründe, warum die anderen weniger kritisch sind.
4. **Grenzen deiner Simulation:** Welche deiner Rollen-Bewertungen hast du die niedrigste Konfidenz und warum? Was bräuchte man, um sicherer zu urteilen?
5. **Unerwartetes Muster:** Gab es eine Erkenntnis, die über mehrere Rollen hinweg überraschend war? Etwas, das du vor der Analyse nicht erwartet hättest?
