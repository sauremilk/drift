---
name: "Drift Strategie-Flip (ADR-084 Option C)"
description: "Einmal-Prompt: Setzt ADR-084 auf accepted/Option C (Hybrid), ergänzt docs/PRODUCT_STRATEGY.md um die Evolutions-Sektion, aktiviert ROADMAP Epoche B und markiert Backlog-Items 05–08 als active. Voraussetzung für alle Feature-Prompts 05–08."
---

# Drift Strategie-Flip (ADR-084 Option C)

Ein einmaliger, konsolidierender Prompt. Führt die Maintainer-
vorgefreigegebene Option C (Hybrid: Nische als Go-to-Market,
universell als Evolution) aus ADR-084 ins Repository ein. Danach ist
die Gating-Kette für Items 05–08 offen.

> **Explizite Voraussetzung — diese Freigabe ersetzt das sonst
> übliche Abwarten der 6-Wochen-Messperiode:**
> Der Maintainer (Mick Gottschalk) hat Option C vorab freigegeben
> und den Agent beauftragt, den Flip direkt umzusetzen. Diese
> Freigabe ist im Commit-Body als `Decision: ADR-084 (Option C)`
> zu dokumentieren. Ohne diese explizite Freigabe ist der Prompt
> ungültig und muss abgebrochen werden.

> **Pflicht:** Vor Ausführung das Drift Policy Gate durchlaufen
> (siehe `.github/prompts/_partials/konventionen.md` und
> `.github/instructions/drift-policy.instructions.md`).

## Relevante Referenzen

- **Strategie-ADR:** [`docs/decisions/ADR-084-positionierung-vibe-coding-tool.md`](../../docs/decisions/ADR-084-positionierung-vibe-coding-tool.md)
- **Positionierungsdokument:** [`docs/PRODUCT_STRATEGY.md`](../../docs/PRODUCT_STRATEGY.md)
- **Externes Strategiedokument:** [`docs-site/product-strategy.md`](../../docs-site/product-strategy.md)
- **ROADMAP:** [`ROADMAP.md`](../../ROADMAP.md) Sektion "Strategische Epochen"
- **Backlog-Items:** [`master-backlog/04-audience-validation-experiment.md`](../../master-backlog/04-audience-validation-experiment.md) bis `11-cloud-trend-storage.md`
- **ADR-Workflow:** `.github/skills/drift-adr-workflow/SKILL.md`
- **Konventionen:** `.github/prompts/_partials/konventionen.md`

## Arbeitsmodus

- Ein Run, ein Commit. Keine Teilschritte ohne einander.
- Kein Code in `src/`. Dieser Prompt ist reine Strategie-Dokumentation.
- Alle geänderten Dateien sind dokumentarisch; keine Tests oder
  Benchmarks werden ausgelöst.

## Ziel

ADR-084 von `proposed` auf `accepted` setzen mit expliziter Wahl von
Option C, alle abhängigen Dokumente konsistent halten, und die
Gating-Sätze in Items 05–08 so aktualisieren, dass die zugehörigen
Feature-Prompts nicht mehr blockiert sind.

## Erfolgskriterien

- ADR-084 trägt `status: accepted`, `date: <heute ISO>`, und die
  Entscheidung ist als Option C (Hybrid) ausformuliert.
- `docs/PRODUCT_STRATEGY.md` enthält eine neue, klar abgegrenzte
  Sektion "Evolutions-Perspektive (ADR-084 Option C)". Keine
  Streichung bestehender Inhalte.
- `docs-site/product-strategy.md` enthält einen Verweis auf diese
  Sektion (nur Hinweis, keine Streichung).
- `ROADMAP.md` Epoche B ist von "gated" auf "active" gesetzt, mit
  Bezug auf die Maintainer-Freigabe.
- `master-backlog/05-drift-nudge-cold-start.md` bis `08-vscode-extension-beta.md`:
  Gating-Satz wird durch Status-Zeile ersetzt — `Status: active,
  siehe ADR-084 Option C, eigener Sub-ADR erforderlich`.
- `master-backlog/09`–`11`: Gating-Satz bleibt, wird nur präzisiert
  auf "erfordert Epoche-B-Abschluss, nicht Option-C-Beschluss".
- Policy Gate wurde dokumentiert ausgeführt.
- Kein Push.

## Arbeitsregeln

- Zeitstempel konsistent: `date:` im ADR, Datum im
  PRODUCT_STRATEGY-Abschnitt, Datum in den Backlog-Status-Zeilen
  müssen identisch sein (heute, ISO 8601).
- Keine Neuformulierung von ADR-084 Kontext/Begründung. Nur
  Status-Feld, Validierungs-Sektion (Ergebnis dokumentieren) und
  ein zusätzlicher "Entscheidung getroffen"-Kurzabschnitt werden
  geschrieben.
- Die Folge-ADR-Drafts für Items 05–08 sind **nicht** Teil dieses
  Prompts. Sie entstehen in den jeweiligen Feature-Prompts.

## Schritte

1. **Policy Gate sichtbar ausgeben.** Zulassungskriterium
   "Einführbarkeit" unter expliziter Maintainer-Vorfreigabe für
   Option C.
2. **ADR-084 updaten.** Nur drei Änderungen:
   - Frontmatter: `status: accepted`, `date: <heute>`
   - Neuer kurzer Abschnitt "Entscheidung getroffen" nach
     "Entscheidung"-Sektion: "Option C (Hybrid) gewählt durch
     Maintainer am <heute>. Begründung: niedrigstes Bruchrisiko,
     respektiert POLICY §7.1, erschließt Epoche-B-Investition
     kontrolliert."
   - Validierungs-Sektion: Lernzyklus-Ergebnis von `zurückgestellt`
     auf `bestätigt (Option C)` setzen; Item-04-Verweis als
     Post-hoc-Validierungsbedingung beibehalten.
3. **`docs/PRODUCT_STRATEGY.md` ergänzen.** Neue Sektion am Ende
   (nicht am Anfang) mit Überschrift "## Evolutions-Perspektive
   (ADR-084 Option C, <heute>)". Inhalt maximal 20 Zeilen:
   - Kategorie-Definition bleibt gültig
   - Agenten-native Nutzung als Evolutionspfad explizit erwähnt
   - Verweis auf Backlog-Items 05–08
   - Klare Trennung: Nische ist Go-to-Market, universell ist
     Evolutionsrichtung
4. **`docs-site/product-strategy.md` ergänzen.** Ein kurzer Block
   am Ende: "Update <heute>: Hybrid-Positionierung per ADR-084
   Option C. Siehe docs/PRODUCT_STRATEGY.md Evolutions-Sektion."
5. **ROADMAP.md aktualisieren.** In der Sektion "Epoche B — Agenten-
   First (gated)": "gated" auf "active" ändern, Gating-Satz
   ersetzen durch "Aktiv per ADR-084 Option C (Maintainer-Freigabe
   <heute>). Sub-ADRs pro Item sind weiterhin erforderlich."
6. **Backlog-Items 05–08 aktualisieren.** In jeder Datei den
   Gating-Satz ersetzen durch:
   > `Status: active, siehe ADR-084 Option C. Sub-ADR erforderlich
   > vor Code-Änderungen.`
7. **Commit vorbereiten (nicht pushen).** Conventional Commit:
   `docs(strategy): accept ADR-084 option C and activate epoch B items`.
   Body enthält `Decision: ADR-084 (Option C)` als letzte Zeile.
8. **Run-Artefakt schreiben.**
   `work_artifacts/strategy_flip_<YYYY-MM-DD>/run.md` mit
   Policy-Gate-Ausgabe, Diff-Zusammenfassung pro Datei und
   Liste der nun freigeschalteten Feature-Prompts.

## Artefakte

```
work_artifacts/strategy_flip_<YYYY-MM-DD>/
    run.md
```

## Nicht Teil dieses Prompts

- Keine Sub-ADR-Erstellung für Items 05–08.
- Kein Code in `src/`, `extensions/`, `tests/`.
- Keine Änderung an POLICY.md oder Instructions.
- Kein Push.
- Kein Re-Schreiben bestehender PRODUCT_STRATEGY-Sektionen.

## Nachfolge-Prompts

Nach erfolgreichem Flip werden die folgenden Prompts der Reihe nach
(oder parallel, falls ressourcen-unabhängig) ausführbar:

- `drift-epoch-b-orchestrator.prompt.md` (wählt die Reihenfolge)
- `drift-feature-05-cold-start.prompt.md`
- `drift-feature-06-trend-gate.prompt.md`
- `drift-feature-07-patch-auto.prompt.md`
- `drift-feature-08-vscode-extension.prompt.md`
