---
name: drift-agent-prompt-authoring
description: "Drift-spezifischer Workflow zum Erstellen und Verbessern von Agent-Prompts unter .github/prompts/. Verwenden bei neuen .prompt.md-Dateien, bei der Schärfung von Evaluierungs-Prompts, bei der Trennung zwischen internem Prompt und Field-Test-Prompt sowie bei der Ausrichtung auf Drift-Policy und Shared Partials. Keywords: agent prompt, prompt authoring, .prompt.md, evaluation prompt, field-test prompt, work_artifacts, issue filing, bewertungs-taxonomie."
argument-hint: "Beschreibe den Prompt, den du schreiben oder überarbeiten willst, wer ihn ausführen soll und ob er das Drift-Repo selbst oder ein externes Repository adressiert."
---

# Drift Skill Für Agent-Prompt-Authoring

Verwende diesen Skill, wenn du einen Drift-Prompt unter `.github/prompts/` neu schreibst oder überarbeitest.

## Wann Verwenden

- Ein neuer Evaluierungs- oder Workflow-Prompt wird benötigt
- Eine bestehende `.prompt.md`-Datei soll geschärft oder neu strukturiert werden
- Ein Prompt muss zwischen interner Drift-Nutzung und externem Field-Test sauber getrennt werden
- Frontmatter, Phasen, Artefakte oder Report-Struktur eines Prompts sollen standardisiert werden

## Kernregeln

1. **Zuerst das Drift Policy Gate ausführen.** Ein gut formulierter Prompt für unzulässige Arbeit bleibt unzulässig.
2. **Prompts sind modellunabhängig und auf Deutsch.** Keine Modellversions-Annahmen oder englische Prompt-Standards einführen.
3. **Shared Partials wiederverwenden statt Konventionen zu duplizieren.** Taxonomie, Issue-Filing und Grundkonventionen haben jeweils eine Single Source of Truth.
4. **Ein Drift-Prompt muss Erkenntnis erzeugen, nicht Dekoration.** Jede Phase soll zu Beobachtung, Artefakt oder Entscheidung führen.
5. **Vor dem Schreiben die richtige Prompt-Klasse wählen.** Interne Prompts und Field-Test-Prompts folgen unterschiedlichen Freshness- und Filing-Regeln.

## Schritt 0: Drift Policy Gate Ausführen

Vor dem Drafting des Prompts das verpflichtende Gate aus `.github/instructions/drift-policy.instructions.md` verwenden.

## Schritt 1: Prompt-Scope Festlegen

Zuerst entscheiden, zu welcher Prompt-Familie der neue Prompt gehört:

- **Interner Drift-Prompt** unter `.github/prompts/`
  verwenden, wenn der Prompt den Drift-Workspace, die Drift-CLI oder Drift-interne Entwicklungsworkflows bewertet
- **Field-Test-Prompt** unter `.github/prompts/field-tests/`
  verwenden, wenn der Prompt Drift gegen beliebige externe Repositories testet

Faustregel fuer die Primitive-Wahl:

- **Instruction-Datei**, wenn die Regel immer gelten und automatisch angewendet werden soll
- **Skill**, wenn ein wiederverwendbarer Operator-Workflow on-demand geladen werden soll
- **Prompt**, wenn ein konkreter mehrphasiger Arbeitsablauf mit Ziel, Artefakten und Bewertung ausgefuehrt werden soll

## Schritt 2: Namensmuster Und Frontmatter An Bestehende Praxis Anlehnen

Die vorhandenen Namensmuster beibehalten:

- interne Prompts wie `drift-agent-workflow-test.prompt.md`
- Field-Test-Prompts wie `drift-field-test.prompt.md`

Das Frontmatter schlicht halten und an die existierenden Prompt-Dateien anlehnen:

```yaml
---
name: "Lesbarer Prompt-Name"
description: "Knapper Zweck, Scope und erwartete Bewertungsart."
---
```

Der sichere Default ist Frontmatter nur mit `name` und `description`.

Ein zusaetzliches Feld wie `agent: agent` nur dann uebernehmen, wenn die direkt verwandten Schwester-Prompts im selben Segment es bereits konsistent verwenden. Es ist kein Pflichtfeld.

Die `description` muss konkret genug sein, dass Menschen den Prompt ohne weitere Rückfragen auswählen können.

## Schritt 3: Den Prompt In Die Shared Konventionen Einhängen

Jeder Prompt soll sich explizit an der gemeinsamen Infrastruktur unter `.github/prompts/_partials/` ausrichten.

Diese Dateien wiederverwenden statt parallele Regeln zu schreiben:

- `_partials/konventionen.md`
- `_partials/bewertungs-taxonomie.md`
- `_partials/issue-filing.md`
- `_partials/issue-filing-external.md`

`_partials/konventionen.md` muss immer beruecksichtigt werden. Die anderen Partials ziehst du dann heran, wenn der Prompt Bewertungssysteme oder Issue-Filing wirklich braucht.

Mindestens diese Konventionen müssen respektiert werden:

- Policy-Gate-Pflicht
- ISO-Datumsformat
- Artefakte unter `work_artifacts/`
- Modellunabhängigkeit
- gemeinsame Bewertungslabels
- gemeinsame Issue-Filing-Struktur

## Schritt 4: Einen Operativen Prompt Schreiben

Ein guter Drift-Prompt ist prozedural statt atmosphärisch.

Die Struktur sollte sich eng an der bestehenden Prompt-Bibliothek orientieren:

- kurze Zweckbeschreibung
- relevante Referenzen
- Arbeitsmodus
- Ziel
- Erfolgskriterien
- Arbeitsregeln
- Bewertungslabels, falls nötig
- Artefaktliste
- phasenbasierter Workflow

Jede Phase soll eine echte Frage beantworten und Evidenz erzeugen, die später überprüfbar bleibt.

## Schritt 5: Artefakte Und Outputs Explizit Machen

Ein Prompt muss genau sagen, welche Artefakte entstehen und wohin sie geschrieben werden.

Die Repository-Konvention lautet:

```text
work_artifacts/<prompt-kürzel>_<YYYY-MM-DD>/
```

Wenn der Workflow mehrphasig ist, die erwarteten Dateien vorab benennen. Keine Formulierungen wie "dokumentiere deine Findings" ohne klaren Artefaktvertrag stehen lassen.

## Schritt 6: Internal Vs. Field-Test Freshness Korrekt Behandeln

Interne Prompts sollen die Dev-Version aus dem Workspace verwenden.

Field-Test-Prompts muessen sicherstellen, dass die aktuellste veröffentlichte `drift-analyzer`-Version verwendet wird.

Wenn `pip install --upgrade drift-analyzer` scheitert, ist das kein Grund, die Freshness-Regel stillschweigend zu lockern. Stattdessen muss der Prompt den Fehlschlag dokumentieren und die tatsächlich verwendete Version explizit ausweisen, genau wie in `_partials/konventionen.md` beschrieben.

Diese beiden Ausführungsmodi nicht ohne ausdrücklichen Grund in einem Prompt vermischen.

## Schritt 7: Bewertung Und Issue-Filing Konsistent Halten

Wenn ein Prompt Ergebnisse bewertet, ausschließlich die Shared-Taxonomie verwenden statt eigene Labels einzuführen.

Wenn ein Prompt zu GitHub-Issues führen kann:

- interne Prompts nutzen `_partials/issue-filing.md`
- Field-Test-Prompts nutzen `_partials/issue-filing-external.md`

Bei Field-Test-Prompts zusätzlich explizit festhalten, dass Issues an `mick-gsk/drift` gehen und nicht an das analysierte Ziel-Repository.

Keine prompt-spezifischen Issue-Formate definieren.

## Schritt 8: Verwandte Skills Und Instructions Referenzieren

Ein Prompt soll die Dateien nennen, die ihn steuern oder ergänzen.

Typische Referenzen sind:

- `.github/instructions/drift-policy.instructions.md`
- `.github/instructions/drift-push-gates.instructions.md`
- passende Skills wie `drift-pr-review` oder `drift-release`
- verwandte Prompts unter `.github/prompts/`

So bleibt der Prompt zusammensetzbar und leichter reviewbar.

## Schritt 9: Den Prompt Vor Wiederverwendung Validieren

Vor der Wiederverwendung alle folgenden Punkte prüfen:

- Frontmatter ist valides YAML
- Prompt-Sprache ist Deutsch
- Prompt ist modellunabhängig
- Artefaktpfade folgen der Repository-Konvention
- Labels stammen aus der Shared-Taxonomie
- Issue-Filing verweist auf das korrekte Partial
- Referenzen zeigen auf existierende Dateien
- der Workflow endet in Evidenz oder Entscheidung, nicht nur in Prosa

## Review-Checkliste

- [ ] Policy Gate ist berücksichtigt
- [ ] Der Prompt liegt am richtigen Ort (`.github/prompts/` oder `field-tests/`)
- [ ] Name und Frontmatter folgen der Repository-Praxis
- [ ] Shared Partials werden wiederverwendet statt kopiert
- [ ] Der Workflow ist phasenbasiert und operativ
- [ ] Artefakt-Outputs sind explizit benannt
- [ ] Versions-Freshness-Regeln passen zum Prompt-Typ
- [ ] Bewertungslabels und Issue-Filing sind standardisiert
- [ ] Relevante Skills, Instructions und Schwester-Prompts sind referenziert

## Referenzen

- `.github/AGENTS.md`
- `.github/prompts/README.md`
- `.github/prompts/_partials/konventionen.md`
- `.github/prompts/_partials/bewertungs-taxonomie.md`
- `.github/prompts/_partials/issue-filing.md`
- `.github/prompts/_partials/issue-filing-external.md`
- `.github/prompts/drift-agent-workflow-test.prompt.md`
- `.github/prompts/release.prompt.md`
- `.github/prompts/field-tests/drift-field-test.prompt.md`
- `.github/prompts/field-tests/README.md`
- `.github/instructions/drift-policy.instructions.md`
