---
name: "Drift Signal Clarity Review"
description: "Bewertet die Verständlichkeit von Drift-Signalen, Begriffen und Erklärungsmustern aus Sicht eines Drift-fremden, aber technisch kompetenten Nutzers."
---

# Drift Signal Clarity Review

Du analysierst die Verständlichkeit der Drift-Signale aus Sicht eines technisch kompetenten, aber nicht Drift-intern sozialisierten Nutzers.

> **Pflicht:** Vor Ausführung dieses Prompts das Drift Policy Gate durchlaufen
> (siehe `.github/prompts/_partials/konventionen.md` und `.github/instructions/drift-policy.instructions.md`).

## Relevante Referenzen

- **Instruction:** `.github/instructions/drift-policy.instructions.md`
- **Bewertungssystem:** `.github/prompts/_partials/bewertungs-taxonomie.md`
- **Issue-Filing:** `.github/prompts/_partials/issue-filing.md`
- **Verwandte Prompts:** `drift-trust-review.prompt.md`, `drift-actionability-review.prompt.md`
- **Signale:** `src/drift/signals/`

## Arbeitsmodus

- Bewerte aus Sicht eines technisch starken, aber Drift-fremden Nutzers.
- Frage immer: Ist sofort klar, welches Risiko gemeint ist und warum es relevant ist?
- Trenne zwischen intern präzise und extern verständlich.
- Keine Änderung von Signalheuristiken — nur Kommunikation und Benennung.

## Ziel

Finde die Signale, Begriffe, Erklärungen oder Benennungen, die für Außenstehende unnötig abstrakt, kryptisch oder akademisch wirken, und liefere Verbesserungsvorschläge.

## Erfolgskriterien

Die Aufgabe ist erst abgeschlossen, wenn du beantworten kannst:
- Welche Signale sind intuitiv verständlich?
- Welche Signale brauchen zu viel Vorwissen?
- Welche Benennungen oder Erklärungen wirken intern statt nutzerorientiert?
- Wo fehlt die Übersetzung von Signalname zu praktischem Risiko?
- Welche Signale müssten sprachlich oder strukturell neu präsentiert werden?

## Arbeitsregeln

- Lies alle Signalnamen und deren Beschreibungen in `src/drift/signals/`.
- Erzeuge echte Findings und bewerte deren Erklärungsqualität.
- Bewerte Signale nicht nach technischer Korrektheit, sondern nach externer Verständlichkeit.
- Unsicherheiten explizit benennen.

## Reasoning-Anforderungen

### Spannungsfelder

Navigiere aktiv folgende Spannungen — mache deine Abwägung transparent:

- **Fachliche Präzision vs. Alltagsverständlichkeit:** „Pattern Fragmentation Score“ ist präzise. „Code-Unordnung“ ist verständlich, aber falsch. Wo liegt die Grenze, ab der Vereinfachung Verfälschung wird?
- **Stabile API-Namen vs. verständliche Umbenennung:** Jede Umbenennung bricht bestehende Konfigurationen. Wann ist der Verständlichkeitsgewinn groß genug, um das zu rechtfertigen?
- **Signalkonsistenz vs. kontextspezifische Erklärung:** Einheitliche Benennungslogik vs. situativ beste Erklärung pro Signal.

### Vor-Schlussfolgerungs-Checks

Bevor du ein Signal als „unverständlich“ klassifizierst:
- Ist es wirklich für die Zielgruppe unverständlich oder nur für Nicht-Entwickler?
- Ist das Problem der Name, die Beschreibung oder der Finding-Text? Die Lösung unterscheidet sich fundamental.
- Gäbe es einen Mittelweg (z.B. Subtitle, Tooltip, Langbeschreibung), der Umbenennung vermeidet?

### Konfidenz-Kalibrierung

Gib für jede Verständlichkeits-Bewertung an:
- **Konfidenz:** hoch / mittel / niedrig — dass ein typischer Drift-Nutzer hier Verständnisprobleme hat
- **Zielgruppe:** Für welches Nutzerprofil gilt deine Bewertung? (Junior Dev? Staff Engineer? Nicht-Python-Entwickler?)
- **Entkräftung:** Unter welchen Umständen wäre der aktuelle Name besser als dein Vorschlag?

### Fehlerschluss-Wächter

Prüfe aktiv gegen:
- **Linguistic Bias:** Du bewertest als Sprachmodell, das Sprache überdurchschnittlich gewichtet. Entwickler lesen oft den Code, nicht den Namen. Wie wichtig ist der Name wirklich?
- **Novelty Bias:** Neue Benennungen klingen immer „logischer“ als vertraute. Prüfe ob dein Vorschlag in einem Jahr immer noch besser wäre.
- **Umbennungs-Kaskade:** Eine Umbenennung zieht Doku, Config, CLI-Aliase, MCP-Parameter mit sich. Hast du die Gesamtkosten berücksichtigt?

## Bewertungs-Labels

Verwende ausschließlich Labels aus `.github/prompts/_partials/bewertungs-taxonomie.md`:

- **Ergebnis-Bewertung:** `pass` / `review` / `fail`
- **Risiko-Level:** `low` / `medium` / `high` / `critical`

## Artefakte

Erstelle Artefakte unter `work_artifacts/signal_clarity_<YYYY-MM-DD>/`:

1. `summary.md` — Gesamtbewertung
2. `signal_clarity_ranking.md` — Ranking aller Signale nach Verständlichkeit
3. `rename_or_reframe_candidates.md` — Empfehlungen für Umbenennung oder Neuformulierung

## Workflow

### Phase 1: Signal-Inventar

Lies alle Signale unter `src/drift/signals/` und dokumentiere:
- Signalname (Kurzform und Langform)
- offizielle Beschreibung
- typischer Finding-Text

### Phase 2: Verständlichkeits-Bewertung

Bewerte jedes Signal:

| Signal | Name verständlich? | Beschreibung verständlich? | Finding-Text verständlich? | Vorwissen nötig? | Gesamtbewertung |
|--------|-------------------|---------------------------|---------------------------|-----------------|----------------|
| | | | | | `pass` / `review` / `fail` |

### Phase 3: Problemsignale identifizieren

Für alle Signale mit `review` oder `fail`:
- Was genau ist unklar?
- Ist der Signalname zu abstrakt, zu technisch oder zu intern?
- Fehlt die Übersetzung zum praktischen Risiko?
- Welche Begriffsalternative wäre verständlicher?

### Phase 4: Empfehlungen

Erstelle `rename_or_reframe_candidates.md`:

Für jede Empfehlung:
- aktueller Name oder Text
- vorgeschlagene Alternative
- Begründung
- erwartete Wirkung auf Verständlichkeit
- Risiko der Umbenennung
- Priorität

## Abschlussentscheidung

1. Nenne die 5 Signal- oder Erklärungselemente, die am dringendsten vereinfacht oder neu gerahmt werden sollten.
2. **Kosten-Nutzen:** Für welche dieser 5 Empfehlungen übersteigt der Umbenennungs-Aufwand (Migration, Doku, Kompatibilität) möglicherweise den Verständlichkeitsgewinn?
3. **Nicht-Umbenennen-Alternative:** Für welche Signale wäre eine bessere Beschreibung oder ein Subtitle effektiver als eine Umbenennung?
4. **Präzisionsverlust:** Bei welcher Vereinfachung würde fachliche Genauigkeit verloren gehen? Ist der Trade-off akzeptabel?
5. **Blinder Fleck:** Welche Art von Unverständlichkeit kannst du als Sprachmodell prinzipiell nicht erkennen (z.B. visuelles Layout, Lese-Flow im Terminal)?
