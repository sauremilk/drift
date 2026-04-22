# 04 — Audience Validation Experiment (Phase B)

> **Zweck:** Empirisch klären, welche Zielgruppe Drift in der aktuellen
> Distribution-Phase tatsächlich adoptiert. Liefert die Entscheidungs­grundlage
> für [`decisions/ADR-084-positionierung-vibe-coding-tool.md`](../decisions/ADR-084-positionierung-vibe-coding-tool.md).
>
> **Status:** proposed
> **Erstellt:** 2026-04-21
> **Messzeitraum:** 6 Wochen ab Distribution-Push-Start
> **Verwandte Artefakte:** ADR-084, [`work_artifacts/adoption_analysis_report.md`](../work_artifacts/adoption_analysis_report.md), [`src/drift/telemetry.py`](../src/drift/telemetry.py)

---

## Hypothesen-Zielgruppen

Drei plausible Zielgruppen aus der strategischen Analyse vom 21.04.2026:

| ID | Zielgruppe | Hypothetischer Kernnutzen | Hypothetische Zahlungsbereitschaft |
|----|------------|---------------------------|------------------------------------|
| Z1 | Solo-Vibe-Coder | "Mein Agent erzeugt strukturell driftenden Code, ich brauche Feedback während des Bauens" | niedrig, dafür hohe Verbreitung + Multiplikatoreffekt |
| Z2 | Team-Lead mit CI-Gate | "Ich brauche ein Gate, das strukturelle Erosion vor Merge stoppt" | mittel, ROI über Code-Churn-Reduktion |
| Z3 | Agent-Framework-Entwickler | "Ich brauche Drift als Tool-Call-Primitive in meinem Agent-Loop" | hoch, niedrige Verbreitung |

---

## Signalstrategie je Zielgruppe

Alle Signale beruhen auf **bereits vorhandenen Datenquellen** (Telemetrie nach
POLICY §19 opt-in lokal, GitHub-Public-Signale, dev.to-Engagement).
Keine neue Telemetrie-Erfassung wird durch dieses Experiment eingeführt.

### Z1 — Solo-Vibe-Coder

Primärsignale:

- **GitHub-Star-Velocity** (Δ Stars pro Woche) — Datenquelle: GitHub-API,
  Tracking konsistent zu `master-backlog/01-baseline.md`
- **`drift setup` Completion-Rate** — Datenquelle: lokale Telemetrie
  `src/drift/telemetry.py` (event_type `setup_completed` vs. `setup_started`),
  nur falls Nutzer Telemetrie aktiviert
- **dev.to / Show-HN Artikel-Engagement** — Datenquelle:
  `master-backlog/draft-devto-article.md` und `draft-show-hn.md`,
  Reaktionen / Kommentare, manuelle Zählung

### Z2 — Team-Lead mit CI-Gate

Primärsignale:

- **CI-Integration-Adoption** — Datenquelle: GitHub-Code-Search nach
  `drift-analyzer` in `.github/workflows/*.yml`, `.pre-commit-config.yaml`,
  manuelle wöchentliche Stichprobe
- **Issues mit "CI"-Kontext** — Datenquelle: GitHub-Issues im Repo
  mit Labels/Inhalten "CI", "pipeline", "gate", "pre-commit", manuelle
  Klassifikation
- **`drift check` / `--exit-zero` / `--gate`-Aufrufe** — Datenquelle:
  lokale Telemetrie (event_type `cli_invocation`, command-Feld), nur
  bei aktiver Telemetrie

### Z3 — Agent-Framework-Entwickler

Primärsignale:

- **MCP-Server-Aufrufe** — Datenquelle: lokale Telemetrie (event_type
  `mcp_tool_call`), Anzahl unterschiedlicher Tools pro Session,
  Anzahl `drift_nudge`-Calls pro Editing-Session
- **Issues mit "MCP" / "agent" / "LangGraph" / "Claude Code"-Kontext** —
  Datenquelle: GitHub-Issues, manuelle Klassifikation
- **Erwähnungen in Agent-Framework-Repos** — Datenquelle: GitHub-
  Code-Search nach `drift_nudge`, `drift_scan`, `drift_brief` außerhalb
  von `mick-gsk/drift`

---

## Zielwerte je Zielgruppe (Adoptionsnachweis-Schwelle)

Eine Zielgruppe gilt als **adoptiert**, wenn nach 6 Wochen alle drei
Schwellen erreicht sind. Zahlen leiten sich aus POLICY §8
(Einführbarkeit als Zulassungskriterium) und der Distribution-Phase-
Vorgabe "≥10 externe Nutzer" ab.

| Schwelle | Z1 Solo | Z2 Team-Lead | Z3 Agent-Dev |
|----------|---------|--------------|--------------|
| Externe Nutzer im Segment | ≥ 10 | ≥ 10 | ≥ 10 |
| Unsolicited GitHub-Issues mit segment-typischem Kontext | ≥ 3 | ≥ 3 | ≥ 3 |
| Dokumentierter Retention-Fall (Nutzer kommt nach ≥ 2 Wochen wieder) | ≥ 1 | ≥ 1 | ≥ 1 |

"Externer Nutzer" = jemand außerhalb von `mick-gsk` und nicht direkt
adressierter Beta-Tester. Identifikation über öffentliche Signale
(Issue-Author, GitHub-Code-Search-Treffer, dev.to-Kommentar).

---

## Abbruchkriterium

Erreicht **keine** der drei Zielgruppen nach 6 Wochen die Schwellen,
gilt das Experiment als negativ:

- **Konsequenz:** Positionierung neu bewerten, **nicht** zusätzliche
  Features bauen. Distribution-Push-Strategie analysieren (Hat das
  Marketing greift überhaupt? Ist die Verpackungslücke aus
  `work_artifacts/adoption_analysis_report.md` ursächlich?).
- **ADR-084-Auswirkung:** Lernzyklus-Ergebnis `widerlegt`. Maintainer
  entscheidet über Re-Run mit verändertem Distribution-Push oder
  Verlängerung des Messzeitraums.

Erreicht **mehr als eine** Zielgruppe die Schwellen, gilt das Hybrid-
Szenario aus ADR-084 Option C als wahrscheinlich.

---

## Operative Schritte

- [ ] T-0: Distribution-Push-Start dokumentieren (Datum festhalten)
- [ ] Wöchentlich: Signal-Werte je Zielgruppe in Tabelle eintragen
      (siehe Kopiervorlage unten)
- [ ] Woche 3: Zwischenbewertung — sind die Signale grundsätzlich
      messbar oder fehlt Datenquelle?
- [ ] Woche 6: Endbewertung — Schwellen erreicht/verfehlt je Zielgruppe
- [ ] Ergebnisbericht in `work_artifacts/audience-validation-2026-Q2/`
      ablegen (Ordner bei Abschluss anlegen, nicht jetzt)
- [ ] ADR-084 mit Validierungs-Ergebnis aktualisieren (Maintainer setzt
      Status `accepted` mit gewählter Option)

---

## Wöchentliche Erfassung (Kopiervorlage)

```markdown
## KW [__] — ____-__-__

### Z1 — Solo-Vibe-Coder
- GitHub-Stars (Δ Woche): ___
- setup_completed / setup_started: ___ / ___
- dev.to / Show-HN Reaktionen (kumuliert): ___
- Externe Nutzer Z1 (kumuliert): ___
- Z1-Issues (kumuliert): ___

### Z2 — Team-Lead mit CI-Gate
- CI-Integrationen via Code-Search (kumuliert): ___
- Z2-Issues (kumuliert): ___
- check / --exit-zero / --gate-Calls (Telemetrie, kumuliert): ___

### Z3 — Agent-Framework-Entwickler
- MCP-Tool-Calls (Telemetrie, kumuliert): ___
- Z3-Issues (kumuliert): ___
- Externe Repos mit Drift-MCP-Aufrufen: ___

### Notizen
- Beobachtungen, qualitative Signale, Hypothesen
```

---

## Nicht Teil dieses Experiments

- Keine Code-Änderung an Drift.
- Keine neue Telemetrie-Erfassung. Alles, was nicht heute schon erfasst
  wird, wird qualitativ aus öffentlichen Quellen erhoben.
- Keine Befragung adressierter Beta-Tester — würde Bias erzeugen.
- Keine Zielgruppen-Vorentscheidung. ADR-084 bleibt offen bis Endbewertung.
