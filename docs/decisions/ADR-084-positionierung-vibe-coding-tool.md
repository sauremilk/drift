---
id: ADR-084
status: accepted
date: 2026-04-21
supersedes:
---

# ADR-084: Drift-Positionierung — Nischentool, universelles Vibe-Coding-Tool oder Hybrid

## Kontext

Im Repo existiert eine etablierte Positionierungsentscheidung in
[`docs/PRODUCT_STRATEGY.md`](../docs/PRODUCT_STRATEGY.md) (Stand 23.03.2026, v2.0):

> "drift ist ein deterministischer Static-Analyzer, der architekturelle
> Erosion in **AI-assistierten Codebases** erkennt … Kein Produktumbau,
> keine neuen Infrastruktur-Abhängigkeiten, kein Feature-Creep."

Diese Strategie positioniert Drift bewusst **schmal**: AI-Drift-Detector
in einer Nische, nicht generischer Code-Quality-Analyzer. Die aktuelle
Distribution-Phase in [`ROADMAP.md`](../ROADMAP.md) ("Q2 2026 — keine neuen
Signale, keine neuen Features") leitet sich daraus ab.

Eine strategische Analyse vom 21.04.2026 (siehe Session-Plan und
nachfolgende Backlog-Items 04–11) schlägt eine alternative Positionierung
vor: Drift als **universelles Vibe-Coding-Tool**, also die "architektonische
Gewissensschicht" zwischen Agenten-Output und Produktionscode, in jedem
Übergangsmoment (Commit, PR, Agent-Loop-Ende, Deploy-Gate) konsumierbar.

Die beiden Positionen sind nicht trivial vereinbar:

- Die Nischen-Positionierung schließt Cross-Sprach-Signale, Trend-Gates,
  VS-Code-Extension und Auto-Patch-Loops nicht explizit aus, aber sie
  priorisiert sie auch nicht — die ROADMAP-Sektion "Not currently
  prioritized" sortiert mehrere dieser Items implizit aus.
- Die universelle Positionierung verlangt eine erweiterte
  Investitionsbasis (Go-Support, IDE-Integration, Auto-Remediation,
  Cross-Repo-Telemetrie) und eine andere Zielgruppe.

Die offene Frage ist nicht "Was bauen?", sondern "Welche Zielgruppe
adoptiert Drift tatsächlich, und welche Positionierung erschließt diese
Zielgruppe?".

## Entscheidung

**Status: `accepted`. Option C (Hybrid) gewählt. Auswahl und
Begründung im Abschnitt "Entscheidung getroffen" unten.**

Drei Optionen werden zur Entscheidung gestellt:

### Option A — Nische halten (Status quo)

`docs/PRODUCT_STRATEGY.md` bleibt unverändert. Drift bleibt
"AI-Drift-Detector". Distribution-Track läuft wie geplant; Backlog-Items
06–11 bleiben dauerhaft `proposed` oder werden geschlossen.

### Option B — Universelles Vibe-Coding-Tool

`docs/PRODUCT_STRATEGY.md` wird grundlegend überarbeitet (Folge-ADR).
Drift wird als kontinuierliche Qualitätsschicht für agentengetriebene
Workflows positioniert. Backlog-Items 06–11 werden priorisiert und
durchlaufen jeweils eigene ADRs.

### Option C — Hybrid (Nische als Go-to-Market, universell als Evolution)

`docs/PRODUCT_STRATEGY.md` wird **ergänzt** (nicht ersetzt) um eine
Evolutionssektion. Distribution-Track läuft wie heute, aber Backlog-Items
06–08 werden als Epoche-B-Kandidaten ernst genommen, sobald die Nische
Adoptionsnachweis liefert.

**Nicht Teil dieser Entscheidung:**

- Keine Code-Änderung. Kein neues Signal. Keine Implementierung von
  Trend-Gate, Auto-Patch oder VS-Code-Extension.
- Kein Rewrite von `docs/PRODUCT_STRATEGY.md` solange diese ADR `proposed`
  ist. Bei Option B/C entsteht ein separater Folge-ADR.
- Kein Aufweichen der POLICY-§14-Phasen-Reihenfolge (Trust → Relevance
  → Adoptability → Scaling). Strategische Epochen (A/B/C) werden additiv
  in `ROADMAP.md` dokumentiert und kollidieren begrifflich nicht mit
  Policy-Phasen.

## Entscheidung getroffen

Option C (Hybrid) gewählt durch Maintainer am 2026-04-21. Begründung:
niedrigstes Bruchrisiko, respektiert POLICY §7.1, erschließt
Epoche-B-Investition kontrolliert. Die Nischen-Positionierung bleibt
Go-to-Market-Vehikel; die universelle Evolution wird als additiver Pfad
in `docs/PRODUCT_STRATEGY.md` verankert. Gating-Sätze in den
Backlog-Items 05–08 sind damit aufgehoben; Sub-ADRs je Item bleiben
erforderlich vor Code-Änderungen.

## Begründung

**Warum eine ADR und nicht direkt die ROADMAP ändern?** Die
Positionierungsentscheidung ist eine Weichenstellung mit Folge-Effekten
auf mindestens fünf Dokumente (`PRODUCT_STRATEGY.md`,
`docs-site/product-strategy.md`, `ROADMAP.md`, `README.md`, `llms.txt`)
und auf die gesamte Backlog-Priorisierung. Ohne dokumentierte
Entscheidungsgrundlage entstehen widersprüchliche Folgeänderungen.

**Warum drei Optionen statt einer Empfehlung?** Die strategische Analyse
benennt zwei valide Positionierungen, die jeweils unterschiedliche
Zielgruppen adressieren. Eine vorab gesetzte Empfehlung würde das
Validierungs-Experiment (Item 04) bias'en, dessen Ergebnis gerade die
Entscheidungsgrundlage liefern soll.

**Warum Option C als plausibelste Evolution?** (rein informativ, keine
Vorentscheidung) Die Hybrid-Variante respektiert POLICY §7.1
(Drift-Glaubwürdigkeit zuerst), nutzt die bereits investierte Nischen-
Positionierung als Go-to-Market-Vehikel und hält die universelle
Evolution offen. Sie ist die Option mit dem geringsten Bruchrisiko.

**Alternativen verworfen:**

- *Sofortige Übernahme der universellen Positionierung* (Option B
  ohne Validierung): widerspricht POLICY §6 (Priorität =
  Unsicherheit × Schaden × Nutzen / Aufwand). Die Unsicherheit über
  die richtige Zielgruppe ist hoch, der Aufwand für Phase-B-Items
  beträchtlich — ohne Validierung wäre die Investition spekulativ.
- *Verzicht auf ADR, nur Backlog-Items*: trennt die Positionierungsfrage
  von ihrer Konsequenz. Künftige Reviewer könnten Backlog-Items
  isoliert bewerten, ohne die strategische Klammer zu sehen.

## Konsequenzen

**Bei Option A (Nische halten):**

- `docs/PRODUCT_STRATEGY.md` und `ROADMAP.md` bleiben unverändert.
- Backlog-Items 06–11 werden geschlossen oder bleiben dauerhaft
  `proposed` mit Hinweis "ausgeschlossen durch ADR-084 Option A".
- Cold-Start-Latenz (Item 05) bleibt sinnvoll, aber niedrigere
  Priorität (Agent-Dev als Zielgruppe entfällt).
- Geringstes Implementierungsrisiko, geringster Adoptionsupside.

**Bei Option B (universell):**

- Folge-ADR rewrittet `docs/PRODUCT_STRATEGY.md` komplett.
- Strategische Epochen B+C in `ROADMAP.md` werden Pflichtpfad.
- Backlog-Items 06–08 (Trend-Gate, Auto-Patch, VS-Code) werden in
  eigenen ADRs entschieden.
- Höchster Adoptionsupside, höchstes Bruchrisiko, längste Time-to-Value.

**Bei Option C (Hybrid):**

- Folge-ADR ergänzt `docs/PRODUCT_STRATEGY.md` um eine
  Evolutionssektion ohne Streichung des Nischen-Positioning.
- Distribution-Track läuft unverändert.
- Backlog-Items 06–08 werden ernsthaft priorisiert, sobald
  Validierungs-Experiment ein Zielgruppen-Signal liefert.
- Mittlerer Adoptionsupside, niedriges Bruchrisiko.

**Gemeinsam für alle Optionen:**

- POLICY-§14-Phasen bleiben dominante Begriffsachse für interne
  Qualitätsreife. Strategische Epochen sind additiv und werden klar
  abgegrenzt in `ROADMAP.md` dokumentiert.
- LLM-Output-Format (`src/drift/output/llm_output.py`, stabil seit
  v2.9.13) ist bereits ein Agenten-Interface und wird in keiner Option
  destabilisiert.
- MCP-Server, Fix-Loop, Nudge bleiben unangetastet — die Entscheidung
  ändert nicht das Tool, sondern die Erzählung über das Tool.

## Validierung

Die Entscheidung gilt als validiert, wenn:

1. ADR-084 explizit auf eine der drei Optionen gesetzt wird
   (Status `accepted` durch Maintainer, nicht durch Agent).
2. Das Validierungs-Experiment aus
   [`master-backlog/04-audience-validation-experiment.md`](../master-backlog/04-audience-validation-experiment.md)
   nach 6 Wochen abgeschlossen ist und mindestens eine Zielgruppe die
   dort definierten Schwellen (≥10 externe Nutzer, ≥3 unsolicited
   Issues, ≥1 dokumentierter Retention-Fall) erreicht oder verfehlt.
3. Bei Wahl von Option B oder C ein Folge-ADR existiert, das die
   konkrete Änderung an `docs/PRODUCT_STRATEGY.md` formuliert.
4. Die ROADMAP-Sektion "Strategische Epochen" konsistent zur gewählten
   Option formuliert ist (Epoche B/C entweder gestrichen, priorisiert
   oder als evolutionärer Pfad markiert).

Lernzyklus-Ergebnis-Kategorie (POLICY.md §10): `bestätigt (Option C)`
durch explizite Maintainer-Freigabe 2026-04-21. Post-hoc-Validierung
via Item 04 (Audience-Validation-Experiment) bleibt als
Rückkoppelungsbedingung bestehen: Wenn Item 04 Option C widerlegt,
wird ein Revisions-ADR erstellt.

Referenzen:

- POLICY §6 (Priorisierungsformel)
- POLICY §7 (feste Prioritätsreihenfolge — §7.1 Glaubwürdigkeit zuerst)
- POLICY §8 (Zulassungskriterien — Einführbarkeit als Zulassungsgrund)
- POLICY §14 (Roadmap-Phasen Trust/Relevance/Adoptability/Scaling)
- POLICY §19 (Telemetrie — Datenbasis für Item 04)
- `docs/PRODUCT_STRATEGY.md` (bestehende Positionierung)
- `work_artifacts/adoption_analysis_report.md` (Verpackungslücke als
  Vorbefund)
