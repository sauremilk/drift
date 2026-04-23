# ADR-096 — Automation-Hardening für Pakete 2A/2B/2C

- **Status:** proposed
- **Datum:** 2026-04-22
- **Verantwortlich:** @mick-gsk
- **Kontext:** Nachbesserungen an QA-Paket 2A (Baseline-Ratchet), 2B (Human-Approval-Gate) und 2C (Issue-Auto-Filing), die Automation und Produktivität erhöhen, ohne bestehende Verträge zu brechen.
- **Verwandt:** ADR-093 (Baseline-Ratchet), ADR-094 (Human-Approval-Gate), ADR-095 (Auto-Issue-Filing).

## Kontext

Die Pakete 2A–2C adressieren Agenten-Governance, liefern aber jeweils
lückenhaften Ops-Komfort: kein schneller Baseline-Statusbefehl für
lokale Entwicklung, CI ohne pip-Cache (redundante ~30 s pro PR),
BLOCK-Feedback nur im Artefakt, keine Flut-Sicherung im Issue-Filing,
und Dedup bricht bei Label-Rename.

## Entscheidung

Additive, rückwärtskompatible Erweiterungen ohne Schema- oder
Policy-Änderung:

### 2A — `drift baseline status`

- Neuer Click-Subcommand. Read-only, exit 0 unabhängig von Drift-Menge.
- `--format rich|json`. JSON-Payload: `baseline_exists, baseline_path,
  baseline_findings, total_findings, known_findings, new_findings,
  drift_score`.
- Ersetzt **nicht** `baseline diff --fail-on-new` (das bleibt das
  Gate); erlaubt aber `drift info`-artige Dashboards ohne JSON-Parsing.

### 2B — Workflow-Performance und Wiederverwendung

- `actions/setup-python@v5` mit `cache: pip` und `cache-dependency-path:
  pyproject.toml` → eliminiert redundante Installation pro PR.
- Zweiter Trigger `workflow_call:` mit Input `approval-label`. Externe
  Repositories können den Gate via `uses:` ohne Copy-Paste einbinden.
- Report in `$GITHUB_STEP_SUMMARY`: Maintainer sehen BLOCK-Zahl direkt
  im PR-Check-Detail, ohne Artefakt zu laden. **Kein PR-Kommentar** —
  konsistent mit Repo-Regel "kein ungefragtes Posten".

### 2C — Flood-Guard und Label-robustes Dedup

- Neuer Flag `--max-issues N` (default 10): Findings jenseits der Cap
  werden mit `::warning::` übersprungen; Exit-Code bleibt 0.
- `_existing_open_issues` iteriert über **alle** konfigurierten Labels
  (nicht nur das erste) und dedupliziert über Issue-Nummer. Ein Rename
  von `drift` → `drift-agent` bricht Dedup nicht mehr.
- `capped=N` wird im Summary ausgegeben.

## Konsequenzen

### Positiv

- Maintainer-Schleife: Baseline-Status <1 s lokal, PR-Summary ohne
  Artefakt-Download.
- CI-Zeit: pip-Cache spart typisch 20–40 s pro PR-Durchlauf.
- Wiederverwendbarkeit: Downstream-Konsumenten nutzen das Approval-Gate
  ohne Fork.
- Flood-Schutz: ein fehlkalibrierter Gate füllt nicht mehr 100 Issues.

### Negativ / Trade-offs

- `baseline status` ist eine weitere CLI-Oberfläche, die gepflegt
  werden muss.
- `workflow_call` erweitert den Support-Kontrakt — Aufrufer erwarten
  Input-Stabilität.
- Multi-Label-Dedup erhöht die Zahl `gh issue list`-Requests linear mit
  der Labelanzahl (meist 2–3).

### Abgegrenzt (bewusst nicht im Scope)

- Auto-Close disappearing findings (verletzt User-Regel).
- Automatische Label-Anlage im Consumer-Repo.
- Severity-spezifische Labels (`drift-critical`, `drift-high`) — kann
  später additiv erfolgen.

## Alternativen

1. **Full Dashboard-Service**: verworfen, überdimensioniert.
2. **Slack/Discord Notify**: verletzt "kein ungefragtes Posten".
3. **Auto-Close via cron**: verletzt User-Regel (kein automatischer
   State-Change an Issues).

## Validierung

- `tests/test_baseline_status.py` (4 Tests): exit-0-Contract,
  Missing-Baseline-Pfad, JSON-Payload-Shape.
- `tests/test_automation_enhancements.py` (7 Tests): pip-Cache,
  `workflow_call`, Step-Summary, `--max-issues`-Cap,
  Multi-Label-Dedup.
