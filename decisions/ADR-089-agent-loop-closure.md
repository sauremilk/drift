---
id: ADR-089
status: proposed
date: 2026-04-22
supersedes:
---

# ADR-089: Autonomer Agent-Regelkreis mit konservativem Severity-Gate

## Kontext

`drift.agent.prompt.md` wird von `drift.intent.handoff.handoff()` generiert
(`drift intent run --phase 3`). Der bisherige Prompt listet nur Contracts,
formuliert aber weder einen geschlossenen Regelkreis noch ein verbindliches
Routing, welches Finding durch den Agenten autonom behoben werden darf und
welches einen Menschen erfordert.

Die vorhandene Infrastruktur liefert alle Bausteine (Intent-Phasen 1–5,
`drift_nudge` mit `safe_to_commit`/`revert_recommended`, `drift feedback`,
`action.yml` mit `comment: true`, Label-Workflow
`.github/workflows/drift-label-feedback.yml`, Baseline-Persist), aber ohne
expliziten Vertrag zwischen ihnen wird der Agent reaktiv und der Mensch
außen vor gelassen.

Zusätzlich enthält der bisherige Prompt einen Schreibfehler:
`drift intent --phase 4` statt `drift intent run --phase 4`. Dies ist ein
kein-op-Command und bricht die Validierung, wenn der Agent die Vorgabe
wörtlich befolgt.

## Entscheidung

Der Generator `handoff()` wird um sechs verbindliche Sections erweitert, die
den autonomen Regelkreis vollständig kodieren:

1. **`## Trigger`** — Datei-Edit (Post-Edit-Nudge), Cron, PR-Event.
2. **`## Regelkreis`** — Fünf Phasen: Analyze → Classify → Decide → Act →
   Feedback, jede mit verbindlichem Werkzeug.
3. **`## Severity-Gate`** — Konservatives Mapping (siehe Tabelle unten).
4. **`## Approval-Gate`** — `work_artifacts/agent_run_*.md` als Vorschlag,
   Maintainer-Label `drift/approved` oder `safe_to_commit=true` als Passage.
   Bypass wird durch `scripts/verify_gate_not_bypassed.py` (Paket 2B)
   erkannt.
5. **`## Feedback-Loop`** — `drift feedback` plus Label-Workflow.
6. **`## Rollback-Trigger`** — `revert_recommended=true` oder
   `direction=degrading` nach AUTO-Patch erzwingt Revert.

Severity-Gate-Mapping (konservativ, Maintainer-Antwort 2026-04-22):

| Severity | auto_repair_eligible | Gate |
|---|---|---|
| low / info | true | AUTO |
| low / info | false | REVIEW |
| medium | egal | REVIEW |
| high / critical | egal | BLOCK |

Der Bug `drift intent --phase 4` wird in derselben Änderung zu
`drift intent run --phase 4` korrigiert.

**Explizit nicht Teil dieser Entscheidung:**

- Änderungen am `_render_constraint_block` Output außer der Ergänzung des
  Gate-Labels pro Contract.
- Neue öffentliche CLI-Flags.
- Änderungen am Output-Schema (`agent_telemetry` folgt in ADR zu Paket 1B).

## Begründung

**Konservatives Mapping** (gewählte Variante) vergibt AUTO nur bei niedriger
Severity UND expliziter `auto_repair_eligible`-Freigabe. Alternativen waren:

- Intent-zentriert (nur `auto_repair_eligible` + Confidence entscheiden) —
  verworfen, weil Severity die dominante Risikoachse in POLICY §6 ist und
  Confidence-Werte für viele Signale noch nicht stabil kalibriert sind.
- Zweistufige Gate-Score-Formel — verworfen, weil sie eine weitere
  Konfigurationsachse (`drift.yaml`) einführt, bevor empirische Daten aus dem
  Feld vorliegen.

**Generator-Anpassung statt Markdown-Edit**: `drift.agent.prompt.md` wird
durch `save_agent_prompt()` vollständig überschrieben, Edits am Artefakt
wären bei jedem `drift intent run --phase 3` verloren. Der Vertrag gehört in
den Code.

**Section-Konstanten in `REQUIRED_SECTIONS`** erlauben einen Contract-Test,
der das Skeleton prüft, ohne Wortlaut zu fixieren.

## Konsequenzen

**Positiv**

- Der Agent bekommt ein deterministisches Routing für jedes Finding.
- Der Mensch bleibt kontrollierender Punkt bei medium/high/critical und bei
  `auto_repair_eligible=false`.
- Contract-Test (`tests/test_agent_prompt_contract.py`) verhindert
  Regression des Regelkreises.

**Akzeptierte Trade-offs**

- Die Prompt-Datei wird länger. Token-Kosten steigen für LLM-Konsumenten um
  grob 1–2 KB; akzeptabel gegen den Gewinn an Klarheit.
- Sections referenzieren Artefakte aus Paket 2B
  (`scripts/verify_gate_not_bypassed.py`) und Paket 1B (`agent_telemetry`),
  die zum Zeitpunkt des Mergens dieses ADR noch nicht existieren. Die
  Referenzen sind als Erwartung an kommende Pakete formuliert und werden
  durch Policy-Gate und Maintainer-Review koordiniert freigegeben.

**Negativ / Risiken**

- Konservatives Mapping lässt potenziell viele `low`-Findings in REVIEW
  landen, wenn `auto_repair_eligible` noch nicht gepflegt ist. Mitigiert
  durch Feedback-Loop und spätere Kalibrierungs-ADR.

## Validierung

- `tests/test_agent_prompt_contract.py` muss in CI grün sein; er prüft
  Existenz und Reihenfolge aller sechs Sections, Severity-Gate-Mapping für
  alle Severity × auto_repair-Kombinationen, Anker-Referenzen auf
  `drift_nudge`, `drift feedback`, `drift/approved`,
  `verify_gate_not_bypassed`, `revert_recommended`.
- Der Bug-Fix `drift intent run --phase 4` wird durch einen Anti-Assertion im
  selben Test abgesichert.
- Nach Merge: einmalig `drift intent run --phase 3` ausführen und prüfen,
  dass `drift.agent.prompt.md` deterministisch regeneriert wird.
- Feldvalidierung durch Paket 3A (E2E Agent-Loop-Benchmark): Severity-Gate
  erzeugt in drei Referenz-Repos die erwartete Verteilung AUTO/REVIEW/BLOCK.
- Policy §10 Lernzyklus-Ergebnis: **unklar** (initialer Vertrag,
  Revaluierung nach Paket 3A).
