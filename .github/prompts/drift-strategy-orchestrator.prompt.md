---
name: "Drift Strategie-Orchestrator (ADR-084)"
description: "Treibt die systematische Umsetzung der Positionierungsstrategie aus ADR-084 und der Backlog-Items 04–11 voran. Entscheidet je Run, welcher Schritt legal ist, respektiert Gates und produziert Evidenz. Kein Feature-Build ohne Maintainer-Freigabe."
---

# Drift Strategie-Orchestrator (ADR-084)

Ein Steuer-Prompt, der die dokumentierten Strategie-Artefakte aus ADR-084
und den Backlog-Items 04–11 schrittweise in die Realität überführt.

Er wird **wiederholt** aufgerufen (z. B. wöchentlich während des
Validierungs-Experiments). Jeder Run bestimmt den aktuell zulässigen
nächsten Schritt und produziert ein datiertes Artefakt unter
`work_artifacts/strategy_orchestrator_<YYYY-MM-DD>/`.

> **Pflicht:** Vor Ausführung das Drift Policy Gate durchlaufen
> (siehe `.github/prompts/_partials/konventionen.md` und
> `.github/instructions/drift-policy.instructions.md`).

## Relevante Referenzen

- **Strategie-ADR:** [`decisions/ADR-084-positionierung-vibe-coding-tool.md`](../../decisions/ADR-084-positionierung-vibe-coding-tool.md)
- **Validierungs-Experiment:** [`master-backlog/04-audience-validation-experiment.md`](../../master-backlog/04-audience-validation-experiment.md)
- **Gated Items:** `master-backlog/05-drift-nudge-cold-start.md` bis `11-cloud-trend-storage.md`
- **Strategische Epochen:** [`ROADMAP.md`](../../ROADMAP.md) Sektion "Strategische Epochen"
- **Policy Gate:** `.github/instructions/drift-policy.instructions.md`
- **ADR-Workflow:** `.github/skills/drift-adr-workflow/SKILL.md`
- **Konventionen:** `.github/prompts/_partials/konventionen.md`
- **Issue-Filing:** `.github/prompts/_partials/issue-filing.md`
- **Verwandte Prompts:** `drift-positioning-review.prompt.md`,
  `drift-repo-segment-fit.prompt.md`, `drift-integration-priorities.prompt.md`

## Arbeitsmodus

- **Gate-first, nicht task-first.** Kein Schritt wird ausgeführt, bevor
  sein Gate geprüft ist.
- **Agent darf ADR-Status nicht ändern.** `proposed` → `accepted` ist
  Maintainer-Vorbehalt. Der Prompt formuliert höchstens einen
  Entscheidungsvorschlag.
- **Nur eine Phase pro Run.** Der Prompt löst genau einen sinnvollen
  nächsten Schritt aus, nie alle gleichzeitig.
- **Alles wird belegt.** Jede Aussage über Zielgruppen-Signale,
  Retention, Issue-Zählung hat eine konkrete Datenquelle (Telemetrie-
  Datei, GitHub-URL, Commit-Range).

## Ziel

Die in ADR-084 gewählte Positionierung (Option A, B oder C) zu einer
begründeten Maintainer-Entscheidung führen und die daraus folgenden
Backlog-Items 05–11 je Epoche genau dann ins Engineering freigeben,
wenn die Gating-Bedingungen erfüllt sind — nicht früher.

## Erfolgskriterien

Die Aufgabe ist erst abgeschlossen, wenn alle folgenden Fragen mit
Evidenz beantwortet sind:

- In welcher Orchestrator-Phase (P0–P4, siehe unten) befindet sich das
  Repo aktuell?
- Welche Gates sind erfüllt, welche nicht?
- Was ist der einzige legale nächste Schritt?
- Welche konkrete Evidenz wurde in diesem Run hinzugefügt?
- Wurde ADR-084 oder ein Backlog-Item in einen neuen Zustand überführt,
  und durch wen (Agent vs. Maintainer)?

## Arbeitsregeln

- Kein Code unter `src/` anfassen, solange sich der Orchestrator in
  Phase P0–P3 befindet.
- Phase-B-Items (06, 07, 08) bleiben `proposed`, solange ADR-084 nicht
  auf Option B oder C gesetzt ist.
- Phase-C-Items (09, 10, 11) bleiben Stubs, solange Epoche B nicht
  abgeschlossen ist.
- Jedes Run-Ergebnis wird als Markdown-Artefakt abgelegt — nie nur in
  der Chat-Antwort.
- Verdächtige oder widersprüchliche Zahlen (z. B. plötzlicher Spike
  in Stars) werden als Beobachtung markiert, nicht als Erfolg
  verbucht.

## Orchestrator-Phasen

Der Prompt unterscheidet fünf Phasen. Jeder Run identifiziert exakt
eine aktuelle Phase und führt den zugehörigen Block aus.

| Phase | Bedingung | Aktion |
|-------|-----------|--------|
| **P0** Bootstrap | ADR-084 existiert nicht oder Items 04–11 fehlen | Strategie-Artefakte erstellen / reparieren |
| **P1** Validierung läuft | ADR-084 `proposed` **und** Item 04 Messzeitraum aktiv | Wöchentliche Erfassung aus Item 04 durchführen |
| **P2** Entscheidungsreife | Item 04 Messzeitraum abgelaufen (≥ 6 Wochen) **und** ADR-084 noch `proposed` | Entscheidungsvorlage für Maintainer erzeugen |
| **P3** Nach Maintainer-Entscheidung | ADR-084 Status ≠ `proposed` | Folge-Artefakte je Option anstoßen |
| **P4** Epoche-B-Umsetzung | ADR-084 auf Option B oder C **und** mindestens ein Backlog-Item der Items 05–08 als Engineering-Ziel angenommen | Pro Item eigene Sub-ADR anstoßen, erst dann Code |

## Phase P0 — Bootstrap

Voraussetzung: ADR-084 existiert nicht **oder** ein Backlog-Item aus
04–11 fehlt **oder** ROADMAP-Sektion "Strategische Epochen" fehlt.

Schritte:

1. Fehlende Artefakte gemäß ADR-084-Konsequenzen-Liste und
   ROADMAP-Sektion "Strategische Epochen" rekonstruieren.
2. Sicherstellen, dass `master-backlog/04-*.md` bis `11-*.md` via
   `.gitignore`-Negation tatsächlich getrackt sind
   (`git check-ignore` pro Datei).
3. Verifikationsbericht ins Artefakt schreiben: welche Dateien
   fehlten, welche wurden erzeugt, welche sind jetzt tracked.

Keine Inhalte der Strategie neu erfinden. Bei Konflikt zwischen
rekonstruiertem und historischem Inhalt: den Konflikt markieren und
stoppen, nicht eigenmächtig entscheiden.

## Phase P1 — Validierung läuft

Voraussetzung: ADR-084 `proposed`, Item 04 Messzeitraum aktiv
(< 6 Wochen seit T-0).

Schritte:

1. Aktuelle Kalenderwoche identifizieren (ISO 8601).
2. Für jede der drei Hypothesen-Zielgruppen (Z1 Solo, Z2 Team-Lead,
   Z3 Agent-Dev) die in Item 04 definierten Primärsignale erheben:
   - Z1: GitHub-Star-Velocity, `setup_completed`/`setup_started` aus
     lokaler Telemetrie (nur falls aktiviert), dev.to-/Show-HN-
     Engagement aus `master-backlog/draft-*.md`-verlinkten Posts.
   - Z2: Code-Search-Treffer für `drift-analyzer` in externen
     `.github/workflows/*.yml` und `.pre-commit-config.yaml`,
     GitHub-Issues im Repo mit CI-Kontext,
     `drift check`/`--exit-zero`/`--gate`-Aufrufe aus Telemetrie.
   - Z3: MCP-Tool-Call-Zähler aus Telemetrie, Agent-Framework-Issues,
     externe Repos mit `drift_nudge`/`drift_scan`-Aufrufen.
3. Werte in die Kopiervorlage aus Item 04 "Wöchentliche Erfassung"
   eintragen und ins Artefakt einhängen.
4. Kumulierte Schwellen-Annäherung je Zielgruppe berechnen
   (Nutzer / 10, Issues / 3, Retention / 1).
5. Qualitative Notiz ergänzen: welche Signale lassen sich *nicht*
   messen, welche Datenquelle fehlt?

Keine Zielgruppen-Entscheidung in P1. Nur Erfassung.

## Phase P2 — Entscheidungsreife

Voraussetzung: Item 04 Messzeitraum abgelaufen **und** ADR-084
`proposed`.

Schritte:

1. Summen je Zielgruppe aus allen P1-Runs aggregieren.
2. Je Zielgruppe Adoptionsnachweis prüfen (alle drei Schwellen erfüllt
   ja/nein).
3. Entscheidungsvorlage erzeugen: welche der drei ADR-084-Optionen
   (A / B / C) wird durch die Daten gestützt, welche widerlegt?
4. Vorlage klar mit dem Hinweis markieren: "Entscheidung durch
   Maintainer, nicht durch Agent."
5. Bei Abbruchkriterium (keine Zielgruppe erreicht Schwellen)
   explizit empfehlen, die Distribution-Push-Strategie zu prüfen
   bevor Features gebaut werden.
6. Ergebnis in ADR-084 Sektion "Validierung" **als Entwurf**
   einfügen (z. B. auskommentierter Block) — Status `proposed`
   bleibt unangetastet.

## Phase P3 — Nach Maintainer-Entscheidung

Voraussetzung: ADR-084 Status ≠ `proposed`.

Schritte pro Option (Agent wählt nur den Block, der zur gesetzten
Option passt):

- **Option A — Nische:** Items 06–11 in `master-backlog/` mit
  `Status: closed — per ADR-084 Option A` markieren.
  `docs/PRODUCT_STRATEGY.md` bleibt unverändert. Orchestrator endet.
- **Option B — Universell:** Folge-ADR-Entwurf für das Rewrite von
  `docs/PRODUCT_STRATEGY.md` anlegen (nicht committen, nur drafen).
  Items 06–08 bleiben `proposed`, warten auf Einzel-ADR in P4.
- **Option C — Hybrid:** Folge-ADR-Entwurf für die **Ergänzung** von
  `docs/PRODUCT_STRATEGY.md` um eine Evolutionssektion anlegen
  (nicht committen). Items 06–08 bleiben `proposed`.

In allen Optionen: ROADMAP-Sektion "Strategische Epochen" mit dem
gewählten Ausgang konsistent halten (Epoche B gestrichen bei A,
priorisiert bei B/C).

## Phase P4 — Epoche-B-Umsetzung

Voraussetzung: ADR-084 auf Option B oder C **und** Maintainer hat
mindestens ein Backlog-Item (typisch 05, 06, 07, 08) zur Umsetzung
freigegeben.

Schritte pro freigegebenem Item:

1. Eigene ADR drafen. Nummerierung fortlaufend. Status `proposed`.
   Kein Item-Code ohne eigene ADR.
2. Für Signal- oder Architektur-betreffende Items den
   signal-design-Template-Pfad gemäß
   `.github/skills/drift-adr-workflow/SKILL.md` verwenden.
3. Risk-Audit-Bedarf prüfen (POLICY §18). Falls FMEA / Fault Trees /
   STRIDE / Risk Register betroffen: Änderungen vormerken, nicht
   eigenständig schreiben (Maintainer-Review).
4. Erst nach `accepted`-Status der Sub-ADR: Implementierung über
   bestehenden Fix-Loop-Prompt (`drift-fix-loop.prompt.md`) starten.
5. Feature-Evidence-Artefakt unter `benchmark_results/<version>_*.json`
   anlegen, wenn die Implementierung abgeschlossen ist.

Dieser Prompt startet **nie selbst** Code-Änderungen in Phase P4 —
er stellt nur die ADR-Pipeline bereit.

## Artefakte

Pro Run entsteht genau ein Artefakt-Ordner:

```
work_artifacts/strategy_orchestrator_<YYYY-MM-DD>/
    run.md                    # Haupt-Artefakt dieses Runs
    adopted_phase.md          # Welche Phase P0–P4 dieser Run bedient
    evidence/                 # Rohdaten (Telemetrie-Excerpts, GitHub-URLs)
        z1_signals.md
        z2_signals.md
        z3_signals.md
    decision_proposal.md      # Nur in Phase P2, sonst fehlt
```

`run.md` enthält als Pflichtabschnitte:

1. Durchgelaufenes Policy Gate (wörtlich)
2. Phasen-Diagnose mit Begründung
3. Gates-Matrix (welche Gates erfüllt/verletzt)
4. Ausgeführter Schritt (genau einer)
5. Erzeugte oder geänderte Dateien (Pfade, Diffs-Zusammenfassung)
6. Evidenzen (Telemetrie-Snippets, GitHub-URLs, Commit-Ranges)
7. Nächster Run: empfohlene Phase + Vorbedingungen

## Bewertungs-Labels

Ausschließlich die Shared-Taxonomie aus
`.github/prompts/_partials/bewertungs-taxonomie.md` verwenden.

Zusätzlich zu den Shared-Labels darf dieser Prompt den Phasen-Tag
vergeben (`P0 Bootstrap`, `P1 Validierung`, `P2 Entscheidungsreife`,
`P3 Post-Decision`, `P4 Umsetzung`) — dies ist kein
Bewertungssystem, sondern Zustandsmarkierung.

## Issue-Filing

Wenn der Orchestrator ein Problem aufdeckt, das ein GitHub-Issue
rechtfertigt (z. B. Telemetrie-Lücke, fehlende Datenquelle,
Widerspruch zwischen ROADMAP und ADR-084), verwendet der Agent
`.github/prompts/_partials/issue-filing.md` und adressiert an
`mick-gsk/drift`.

Ohne Nutzerfreigabe werden keine Issues oder Kommentare gepostet.

## Nicht Teil dieses Prompts

- Keine ADR-Status-Änderung durch den Agent.
- Keine Code-Änderungen in `src/drift/**`.
- Kein Push auf `main`.
- Kein Commit auf fremdem Branch.
- Keine Positionierungs-Vorentscheidung (Option A/B/C) — diese bleibt
  dem Maintainer vorbehalten.
- Keine Abkürzung der 6-Wochen-Messperiode aus Item 04.
- Keine Vermischung von Policy-§14-Phasen und strategischen Epochen
  A/B/C. Begriffsabgrenzung laut ROADMAP-Sektion einhalten.

## Review-Checkliste

Siehe `.github/prompts/_partials/review-checkliste.md`. Zusätzlich
für diesen Prompt:

- [ ] Policy Gate durchgeführt und im Artefakt verankert
- [ ] Genau eine Phase P0–P4 diagnostiziert
- [ ] Genau ein Schritt ausgeführt
- [ ] Alle erhobenen Zahlen haben eine Datenquelle
- [ ] Keine ADR-Status-Änderung durch Agent
- [ ] Keine Gate-Übersprünge (Phase-B vor Maintainer-Entscheidung)
- [ ] Artefakt-Ordner korrekt datiert und strukturiert
- [ ] Empfehlung für den nächsten Run enthält Vorbedingungen
