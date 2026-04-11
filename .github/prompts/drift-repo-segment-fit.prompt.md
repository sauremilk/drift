---
name: "Drift Repo Segment Fit"
description: "Analysiert, für welche Repository-Typen Drift heute stark wirkt und welche Segmente priorisiert werden sollten. Liefert eine Segment-Matrix und Positionierungsempfehlungen."
---

# Drift Repo Segment Fit

Du analysierst, für welche Repository-Typen Drift heute bereits stark ist und für welche Segmente der Fit noch schwach oder unscharf wirkt.

> **Pflicht:** Vor Ausführung dieses Prompts das Drift Policy Gate durchlaufen
> (siehe `.github/prompts/_partials/konventionen.md` und `.github/instructions/drift-policy.instructions.md`).

## Relevante Referenzen

- **Instruction:** `.github/instructions/drift-policy.instructions.md`
- **Bewertungssystem:** `.github/prompts/_partials/bewertungs-taxonomie.md`
- **Issue-Filing:** `.github/prompts/_partials/issue-filing.md`
- **Verwandte Prompts:** `drift-positioning-review.prompt.md`, `drift-first-run-dropoffs.prompt.md`
- **Benchmark-Daten:** `benchmark_results/`, `benchmarks/oracle_repos.json`

## Arbeitsmodus

- Beurteile Segment-Fit nach Nutzenklarheit, First-Run-Value, Handlungskraft der Findings und realistischer Adoption.
- Trenne zwischen gut analysierbar und gut positionierbar.
- Keine universelle Positionierung für alle denkbaren Repos.
- Verwende reale oder gut simulierte Repo-Profile.

## Ziel

Schaffe Klarheit darüber, wo Drift bereits überzeugend ist, wo das Produktversprechen schwächer wird und welche Zielsegmente Drift aktiv priorisieren sollte.

## Erfolgskriterien

Die Aufgabe ist erst abgeschlossen, wenn du beantworten kannst:
- Für welche Repo-Typen ist Drift heute am überzeugendsten?
- Wo ist der Nutzen schwerer nachweisbar?
- Wo müssten Positionierung, Defaults oder Output angepasst werden?
- Welche Segmente sollten aktiv priorisiert werden?
- Welche Segmente sollten eher nicht im Vordergrund stehen?

## Arbeitsregeln

- Bewerte mindestens 8 verschiedene Repo-Typen.
- Nutze wenn möglich echte Drift-Analysen oder Benchmark-Daten.
- Keine bloße Aufzählung — jede Bewertung braucht Begründung.
- Unsicherheiten explizit benennen.

## Reasoning-Anforderungen

### Spannungsfelder

Navigiere aktiv folgende Spannungen — mache deine Abwägung transparent:

- **Derzeitige Stärken optimieren vs. neue Segmente erschließen:** Drift bei aktuellen Kernnutzern verbessern vs. neue Zielgruppen adressieren. Was bringt mehr Adoption pro Aufwand?
- **Breite Positionierung vs. Nischenfokus:** „Funktioniert überall“ ist nichts wert als Positionierung. „Nur für X“ schränkt ein. Wo ist der Sweet Spot?
- **Segment-Fit vs. Segment-Nachfrage:** Drift passt möglicherweise gut zu Segment X, aber Segment X hat keinen Bedarf (oder weiß noch nichts davon). Trenne Fit von Marktpotenzial.

### Vor-Schlussfolgerungs-Checks

Bevor du ein Segment als „stark“ oder „schwach“ bewertest:
- Basiert dein Urteil auf einer echten oder einer imaginären Drift-Analyse für diesen Repo-Typ?
- Könnte ein Segment nur deswegen schwach wirken, weil die Defaults für diesen Typ falsch konfiguriert sind? (Kein Fitness-Problem, sondern ein Config-Problem.)
- Hast du zwischen „Drift liefert hier wenig Findings“ und „Drift liefert hier irrelevante Findings“ unterschieden?

### Konfidenz-Kalibrierung

Gib für jede Segment-Bewertung an:
- **Konfidenz:** hoch / mittel / niedrig — basierend auf realer Evidenz
- **Evidenzquelle:** echte Drift-Analyse / Benchmark-Daten / Hypothese?
- **Entkräftung:** Was müsste wahr sein, damit deine Bewertung dieses Segments falsch ist?

### Fehlerschluss-Wächter

Prüfe aktiv gegen:
- **Availability Bias:** Du kennst bestimmte Repo-Typen besser als andere. Kompensiere durch explizite Unsicherheitsmarker.
- **Segment-Romantik:** Ein Segment klingt attraktiv („AI-Agent-Repos!“), aber Drift hat dort möglicherweise keinen echten Hebel. Prüfe nüchtern.
- **False Generalization:** Ein positives Ergebnis bei einem Repo ≠ guter Fit für das gesamte Segment.

## Bewertungs-Labels

Verwende ausschließlich Labels aus `.github/prompts/_partials/bewertungs-taxonomie.md`:

- **Ergebnis-Bewertung:** `pass` / `review` / `fail`
- **Risiko-Level:** `low` / `medium` / `high` / `critical`

## Artefakte

Erstelle Artefakte unter `work_artifacts/repo_segment_fit_<YYYY-MM-DD>/`:

1. `summary.md` — Gesamtbewertung
2. `segment_matrix.md` — Bewertete Matrix pro Segment
3. `priority_segments.md` — Priorisierte Segmente mit Empfehlungen

## Workflow

### Phase 1: Segment-Definition

Definiere mindestens diese Repo-Typen:
- kleines Python-Tool (< 5 000 LOC)
- Python-Bibliothek
- Framework
- Monorepo
- AI-Agent-Repo
- CLI-Tool
- Infra- oder Plattform-Repo
- Security-nahes Repo
- stark wachsendes OSS-Projekt

### Phase 2: Segment-Bewertung

Bewerte Drift für jedes Segment:

| Segment | Nutzenklarheit | First-Run-Value | Handlungskraft der Findings | Signal-Relevanz | Adoptions-Wahrscheinlichkeit | Gesamtfit |
|---------|---------------|----------------|---------------------------|----------------|----------------------------|----------|

### Phase 3: Stärken und Schwächen

Für jedes Segment:
- Was funktioniert gut?
- Was funktioniert schlecht?
- Welche Signale sind besonders relevant?
- Welche Signale sind irrelevant oder störend?
- Welche Defaults müssten angepasst werden?

### Phase 4: Positionierungsempfehlungen

Erstelle `priority_segments.md`:
- Die 3 attraktivsten Zielsegmente mit Begründung
- Empfohlene Narrative pro Segment
- Empfohlene Default-Anpassungen pro Segment
- Segmente, die bewusst nicht priorisiert werden sollten

## Abschlussentscheidung

1. Nenne die 3 Repo-Typen, für die Drift zuerst in Kommunikation und Produktarbeit optimiert werden sollte. Begründe die Reihenfolge.
2. **Gegenposition:** Formuliere das stärkste Argument für eine völlig andere Segment-Priorisierung als deine Empfehlung.
3. **Fit vs. Nachfrage:** Für welches deiner Top-Segmente ist der Drift-Fit stark, aber die Marktnachfrage unklar? Wie würde man die Nachfrage validieren?
4. **Mutigster Vorschlag:** Welches Segment würde niemand erwarten, könnte aber der stärkste Wachstumshebel sein? Begründe, selbst wenn die Konfidenz niedrig ist.
5. **Expliziter Verzicht:** Welche 2 Segmente sollte Drift bewusst nicht priorisieren und warum?
