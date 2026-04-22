---
name: "Drift Feature 06 — Trend-Gate Enforcement"
description: "Implementiert konfigurierbares Trend-basiertes Gating: Blockiert CI-Gates, wenn Score sich über N Commits ohne Remediation-Aktivität verschlechtert. Erweitert src/drift/quality_gate.py und trend_history.py. Voraussetzung: ADR-084 accepted Option C."
---

# Drift Feature 06 — Trend-Gate Enforcement

End-to-End-Implementierung von Item 06. Liefert: Sub-ADR,
Config-Schema-Erweiterung, Trend-Gate-Heuristik, CLI-Integration,
Tests, Mutation-Benchmark-Stabilität, Audit-Update, Feature-Evidence.

> **Pflicht:** Drift Policy Gate. ADR-084 `accepted` (Option C).

## Relevante Referenzen

- **Backlog-Item:** [`master-backlog/06-trend-gate-enforcement.md`](../../master-backlog/06-trend-gate-enforcement.md)
- **Code-Einsprung:** `src/drift/quality_gate.py`, `src/drift/trend_history.py`, `src/drift/commands/` (CLI-Flag), `src/drift/config/`
- **Bestehende Gate-Infrastruktur:** `drift check`, `--exit-zero`, `--gate`
- **ADR-Workflow:** `.github/skills/drift-adr-workflow/SKILL.md`
- **Konventionen:** `.github/prompts/_partials/konventionen.md`

## Arbeitsmodus

- Erweiterung, nicht Neubau. `quality_gate.py` und `trend_history.py`
  werden aufgebohrt, nicht ersetzt.
- Defaults konservativ: Trend-Gate per Default **aus**. Nur
  explizite Opt-in-Aktivierung über Config.
- Heuristik ist parametrisierbar: keine Magic Numbers, alle
  Schwellen/Fenster aus Config.

## Ziel

Ein konfigurierbares Gate einführen, das blockiert, wenn:

> "Score verschlechtert sich um ≥ Δ über N Commits, und in diesem
> Fenster wurde keine messbare Remediation-Aktivität erkannt."

"Remediation-Aktivität" = mindestens ein Commit im Fenster, der
mindestens ein Finding aus dem vorherigen Scan-Ergebnis behebt
(Fingerprint-Match über `src/drift/fix_intent.py`-Logik).

## Erfolgskriterien

- Sub-ADR `decisions/ADR-NNN-trend-gate-enforcement.md` `proposed`
  mit Heuristik, Default-Konfiguration, Negativ-Klassen-Analyse
  (wann erzeugt das Gate FP-Blockaden?).
- Config-Schema erweitert:
  ```yaml
  gate:
    trend:
      enabled: false           # Opt-in
      window_commits: 3
      delta_threshold: 0.05
      require_remediation_activity: true
  ```
- `drift.schema.json` und `drift.example.yaml` konsistent.
- CLI-Flag `--trend-gate` (Override) auf `drift check` verfügbar.
- Tests in `tests/test_quality_gate.py` (neu oder erweitert):
  - Positives: Gate blockiert korrekt bei echter Degradation
  - Negatives: Gate lässt Remediation-Aktivität durch
  - Edge: Fenster kleiner als Historie, fehlende Historie,
    Score-Floor, Score-Ceiling
- Ground-Truth-Fixture für Remediation-Detection unter
  `tests/fixtures/ground_truth.py` (siehe Skill
  `drift-ground-truth-fixture-development`).
- Mutation-Benchmark grün — Trend-Gate beeinflusst keinen Signal-
  Score.
- Precision/Recall unverändert.
- Feature-Evidence `benchmark_results/vX.Y.Z_feature_evidence.json`.
- Audit-Update: STRIDE-Threat-Model berührt (CI-Gate-Bypass-
  Risiko), Risk-Register-Eintrag.
- Conventional Commit `feat(gate): trend-based gate with
  remediation-activity detection` + `Decision: ADR-NNN`.

## Phasen

### Phase 1 — Sub-ADR

- Template: `decisions/templates/adr-template.md`.
- Entscheidung beinhaltet **exakt** die Heuristik-Parameter und
  den Remediation-Detection-Algorithmus (Fingerprint-Match über
  Commit-Range).
- FP-Klassen explizit:
  - legitime Score-Verschlechterung durch neue Feature-Arbeit
  - Fingerprint-Drift (fälschlich nicht-remediiert erkannt)
  - Baseline-Neubau (Score-Sprung ohne Bezug zu echten Findings)
- Validierung: welche Fixtures müssen existieren, welcher
  Mutation-Benchmark-Run bleibt grün.

### Phase 2 — Config-Schema

- `src/drift/config/` Schema um `gate.trend`-Subtree erweitern.
- `drift.schema.json` aktualisieren, `drift.example.yaml`
  kommentierte Beispielzeile hinzufügen.
- Test in `tests/test_config.py`: Default `enabled: false` ist
  gesetzt.

### Phase 3 — Implementierung

- `src/drift/trend_history.py`: API ergänzen, um Score-Historie
  über N letzte Commits zu liefern (falls nicht vorhanden).
- `src/drift/quality_gate.py`: neue Gate-Regel `TrendGate`
  hinzufügen; bestehende statische Schwellen unverändert.
- Remediation-Detection: neues Helper-Modul
  `src/drift/remediation_activity.py` oder Erweiterung in
  `fix_intent.py`, das Commit-Range auf Fingerprint-Matches prüft.
- Alle neuen öffentlichen Funktionen mit Docstring (Pflicht laut
  Push-Gate).
- Logging konsistent mit bestehender `src/drift/errors/`-
  Infrastruktur.

### Phase 4 — Tests

- `tests/test_quality_gate.py` erweitern.
- `tests/test_remediation_activity.py` neu.
- Ground-Truth-Fixtures unter `tests/fixtures/ground_truth.py`:
  - TP: echtes Degradation-ohne-Fix-Szenario
  - TN: Degradation-mit-Fix-Szenario
  - Confounder: Baseline-Switch

### Phase 5 — Dokumentation

- `docs/` um kurzen Abschnitt "Trend-Gate Enforcement" ergänzen,
  Referenz auf Sub-ADR.
- Output-Formate (`--gate`, `pr-comment`, `ci`) zeigen bei
  Trend-Block eine klare Begründung.

### Phase 6 — Audit-Update (Pflicht bei diesem Feature)

- `audit_results/stride_threat_model.md`: neue Threat-Klasse
  "CI-Gate-Bypass durch manipulierte Trend-Historie".
- `audit_results/risk_register.md`: Risiko-Eintrag mit
  Mitigation (Historie signiert / append-only).
- `audit_results/fmea_matrix.md`: Zeile für Trend-Gate-Modul.
- `audit_results/fault_trees.md`: Pfad für
  "Remediation-Detection versagt".

### Phase 7 — Feature-Evidence + Commit

- `benchmark_results/vX.Y.Z_feature_evidence.json`:
  - Precision/Recall vor/nach (unverändert erwartet)
  - Gate-TP/FP-Fallzahl aus neuen Fixtures
  - Mutation-Benchmark-Stabilität
- CHANGELOG-Eintrag.
- Conventional Commit + `Decision: ADR-NNN`.
- Push-Gates lokal grün. Kein Push ohne User-Anweisung.

## Artefakte

```
work_artifacts/feature_06_<YYYY-MM-DD>/
    run.md
decisions/ADR-NNN-trend-gate-enforcement.md
src/drift/config/*                            # schema update
src/drift/trend_history.py                    # API extension
src/drift/quality_gate.py                     # new rule
src/drift/remediation_activity.py             # new (oder fix_intent.py ext)
drift.schema.json
drift.example.yaml
tests/test_quality_gate.py
tests/test_remediation_activity.py
tests/fixtures/ground_truth.py
audit_results/stride_threat_model.md
audit_results/risk_register.md
audit_results/fmea_matrix.md
audit_results/fault_trees.md
benchmark_results/vX.Y.Z_feature_evidence.json
CHANGELOG.md
```

## Nicht Teil dieses Prompts

- Keine neue Score-Metrik.
- Kein Eingriff in Signal-Implementierungen.
- Kein Auto-Fix; Trend-Gate blockiert nur, repariert nichts.
- Kein Push, keine Sub-ADR-Akzeptanz durch Agent.
