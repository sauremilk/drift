# ADR-094 — Human-Approval-Gate für BLOCK-Findings

- **Status:** proposed
- **Datum:** 2026-05-04
- **Verantwortlich:** @mick-gsk (Maintainer)
- **Kontext:** Paket 2B (QA-Plan 2026 – Glaubwürdigkeit / Bypass-Resistenz)
- **Verwandt:** ADR-089 (Gate-Bypass-Detector), ADR-090 (`agent_telemetry.agent_actions_taken`), ADR-093 (Baseline-Ratchet).

## Kontext

Drift klassifiziert Findings per `safe_to_commit`/`gate_decision` in
`AUTO` / `REVIEW` / `BLOCK`. Bisher wurde diese Klassifikation nur
*beobachtend* telemetriert (ADR-090) und nachträglich per
`scripts/verify_gate_not_bypassed.py` geprüft (ADR-089). Für
Contributor-PRs gab es keinen *verpflichtenden* Review-Gate auf CI-Ebene,
der BLOCK-Findings im PR-Kontext sichtbar und nicht-umgehbar macht.

Risiko ohne formales Gate:

1. Ein Agent (oder eine Nicht-Maintainer-Contribution) kommittiert Code
   mit BLOCK-Gate-Entscheidung; CI ist grün, obwohl die Policy ein
   Maintainer-Review verlangt.
2. Der Agent kann sich selbst nicht freigeben, aber technisch nichts
   hält ihn bisher davon ab, einen BLOCK-Eintrag stillschweigend zu
   akzeptieren und trotzdem zu mergen.

## Entscheidung

Einführung eines dreiteiligen, additiven Maintainer-Gates:

### 1. GitHub-Workflow `drift-agent-gate.yml`

- Trigger: `pull_request` auf `main` mit Pfad-Filter für Agent-nahe
  Dateien (`src/**`, `tests/**`, `drift.agent.prompt.md`, Schema-Dateien,
  `docs/decisions/**`).
- Schritt 1: `drift analyze --format json --exit-zero`.
- Schritt 2: Python-Inline-Check auf
  `agent_telemetry.agent_actions_taken[*].gate == "BLOCK"` sowie
  Sekundärsignal `findings[*].severity in {critical, high}`.
- Schritt 3: Workflow schlägt fehl, sofern mindestens ein BLOCK-Signal
  vorliegt und das PR-Label `drift/approved` nicht gesetzt ist.
- Zusatz: Am Ende ruft der Job `verify_gate_not_bypassed.py
  --all-artifacts` auf (soft-fail bei Exit 2 = keine Artefakte), so
  dass Tampering an Gate-Passage-Evidence im selben Job sichtbar wird.

### 2. Erweiterung `.github/CODEOWNERS`

Neuer Abschnitt „Agent-critical files" ergänzt folgende Pfade:

- `drift.agent.prompt.md`, `drift.output.schema.json`,
  `drift.schema.json`
- `src/drift/signal_registry.py`, `src/drift/intent/handoff.py`
- `.github/workflows/drift-agent-gate.yml`
- `scripts/verify_gate_not_bypassed.py`
- `docs/decisions/`

Konsequenz: GitHub fordert automatisch @mick-gsk als Reviewer an; der
Agent kann die eigene Review nicht substituieren.

### 3. Label-Contract `drift/approved`

Das Label fungiert als *einziger* dokumentierter Override. Nur ein
Maintainer mit Write-Zugriff kann es setzen (GitHub policy). Das Label
hat keine automatisierten Nebeneffekte außer der Workflow-Pass-Through.

## Nicht-Ziele

- **Keine** automatischen PR-Kommentare (User-Regel: „kein ungefragtes
  Posten auf GitHub").
- **Kein** Bypass via `always: success` oder `continue-on-error: true`
  auf Workflow-Ebene. Der Job endet mit Exit 1, wenn BLOCK unabgesegnet
  ist.
- **Kein** Auto-Apply des Labels. Agents dürfen das Label weder
  setzen noch entfernen.
- **Keine** Forks-Policy-Sonderlogik in diesem ADR (separat zu
  behandeln, falls Community-PRs aus Forks behandelt werden sollen).

## Validierung

- CODEOWNERS-Eintrag vorhanden (manueller grep-Check im Commit).
- Workflow-Syntax-Check durch GitHub Actions beim ersten PR-Push.
- `scripts/verify_gate_not_bypassed.py` deckt Artefakt-Seite ab
  (vorhandene Tests in `tests/test_verify_gate_not_bypassed.py`).
- Feature-Evidence:
  `benchmark_results/v2.34.0_human-approval-gate-adr-094_feature_evidence.json`.

## Abhängigkeiten

- Setzt ADR-090 (`agent_telemetry.agent_actions_taken`) voraus. Ältere
  Drift-Versionen emittieren keine `gate`-Felder; der Workflow bleibt
  dann still (needs_block=false), was bewusst so ist.

## Risiken / Audit-Update (§18)

- **RISK-ADR-094-APPROVAL-GATE**: False-positive BLOCK auf legitimen
  Refactors. Mitigierung: Label `drift/approved` + CODEOWNERS-Review.
- **FMEA**: Agent manipuliert `agent_telemetry` im Output, um BLOCK zu
  verstecken. Mitigierung: Output-Schema-Validierung via
  `drift.output.schema.json` in CI, kombiniert mit
  `verify_gate_not_bypassed.py`.
- **STRIDE**: Tampering + Elevation-of-Privilege. Gegenmaßnahme:
  Label-Permission (write-only Maintainer), CODEOWNERS-Review-Pflicht,
  Workflow selbst unter CODEOWNERS.
