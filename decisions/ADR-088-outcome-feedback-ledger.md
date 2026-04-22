# ADR-088: Outcome-Feedback-Ledger (K2 MVP)

**Status:** proposed
**Datum:** 2026-04-22
**Kontext:** Drift Policy - Phase 2 Feedback-Schleife

## Kontext

Die Drift Policy (§14) fordert einen geschlossenen Outcome-Feedback-Loop zur
Validierung von Signalen und Fix-Plan-Empfehlungen. Bisher fehlt ein
deterministischer, reproduzierbarer Mechanismus, um **bereits gemergte** PRs
retrospektiv auf ihre Drift-Score-Bewegung zu analysieren.

## Entscheidung

Wir fuehren einen append-only **Outcome-Ledger** als JSONL-Artefakt unter
`.drift/outcome_ledger.jsonl` ein. Ein neuer ops-Runner
(`scripts/ops_outcome_trajectory_cycle.py`) enumeriert Merge-Commits der
first-parent History, rescored parent + merge via **detached git worktree**
und schreibt `MergeTrajectory`-Saetze.

### Scope des MVP

- **Nur Ledger + Report.** Keine automatische Anpassung von Scoring-Gewichten,
  keine Rueckkopplung in die Signal-Heuristik. Das bleibt Phase 3.
- **Checkout+Rescore pro Merge** in isolierten, detached worktrees. Der
  Haupt-Worktree des Users wird nie angefasst (HEAD und Files bleiben stabil).
- **Retrospektiv**, nicht live - funktioniert auf historischen Daten.

### Abgrenzung

- **ADR-035** (Bayesian per-signal calibration): signal-intern, online.
  Dieses ADR ist externes Outcome-Signal auf Merge-Ebene.
- **ADR-072** (RemediationMemory): speichert Fix-Vorschlaege & Cache.
  Dieses ADR misst, ob empfohlene Fixes den Score tatsaechlich senken.

### Schema

`MergeTrajectory` ist ein frozen Pydantic-Modell mit `schema_version=1`.
Felder: merge_commit, parent_commit, timestamp, author_type, 
ai_attribution_confidence, pre_score, post_score, delta, direction,
per_signal_delta, recommendation_outcomes, staleness_days.

Staleness-Regime:
- <=90d fresh
- 90-180d warning
- >180d historical (nur fuer long-term baseline, nicht fuer aktive Policy)

## Audit §18

Dieses ADR beruehrt Ingestion (git) und Output (ledger + report). FMEA,
STRIDE, Fault-Trees und Risk-Register sind zu aktualisieren:

- **FMEA**: Fingerprint-Mismatch (E=6,S=5,D=6), Ledger-Staleness,
  Selection-Bias Merge-Korpus, Worktree-Cleanup-Failure.
- **STRIDE**: Detached-worktree Trust-Boundary (Tampering/Info Disclosure),
  Ledger-Integritaet (Tampering).
- **Fault-Trees**: "Fehlgeleitete Weight-Updates" als Top-Event, auch wenn
  Weight-Updates im MVP noch nicht aktiv sind - dokumentiert die
  Mitigation-Pfade fuer Phase 3.
- **Risk-Register**: Miscalibration via falschem Outcome-Signal, als mittleres
  Risiko bis zur ersten Kalibrierungsmessung.

## Konsequenzen

**Positiv:** Reproduzierbare, deterministische Baseline fuer spaetere
Weight-Adaption. Bias-Transparenz durch Author-Split (Human/AI/Mixed) im
Report. Erste Evidenz, ob Drift-Score sich gegenueber gemergten Aenderungen
richtig verhaelt.

**Negativ:** Kosten-Mehrfach-Rescore pro Merge (zwei `analyze_repo`-Laeufe).
Selection-Bias durch first-parent-Only-Filter (dokumentiert im Report).
`git worktree add` setzt schreibbaren `.git`-Ordner voraus (CI-Tauglichkeit
muss in Phase 2 verifiziert werden).
