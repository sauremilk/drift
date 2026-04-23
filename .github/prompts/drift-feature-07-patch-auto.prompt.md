---
name: "Drift Feature 07 — drift patch --auto Apply-and-Verify"
description: "Erweitert die v2.14-Patch-Engine um autonome Apply-and-Verify-Schleife für hochpräzise Signale (MDS, PFS, EDS). Dry-Run-Default, Sandbox-Apply, drift_nudge-Verify, Rollback bei Degradation. Pro Signal eigene Sub-ADR. Voraussetzung: ADR-084 accepted Option C."
---

# Drift Feature 07 — Patch-Auto-Verify-Loop

End-to-End-Implementierung von Item 07. Baut auf der bestehenden
Patch-Engine (`src/drift/api/patch.py`,
`src/drift/patch_writer/`, `src/drift/commands/patch_cmd.py`,
v2.14) auf und ergänzt eine Apply-and-Verify-Schleife mit
Rollback-Garantie.

> **Pflicht:** Drift Policy Gate. ADR-084 `accepted` (Option C).
> Pro betroffenem Signal **separate Sub-ADR** (signal-design-
> Template), nicht eine Sammel-ADR.

## Relevante Referenzen

- **Backlog-Item:** [`master-backlog/07-patch-auto-verify-loop.md`](../../master-backlog/07-patch-auto-verify-loop.md)
- **Code-Einsprung:** `src/drift/api/patch.py`, `src/drift/patch_writer/`, `src/drift/commands/patch_cmd.py`, `src/drift/repair_template_registry.py`, `src/drift/outcome_tracker.py`
- **Precision-/Recall-Basis:** `tests/test_precision_recall.py`, `tests/fixtures/ground_truth.py`
- **Mutation-Benchmark:** `scripts/_mutation_benchmark.py`, `benchmark_results/mutation_benchmark.json`
- **Feature-Evidence-Muster:** `benchmark_results/v2.14.0_patch_engine_feature_evidence.json`
- **Signal-Design-Template:** `docs/decisions/templates/signal-design-template.md`
- **Skill:** `.github/skills/drift-signal-development-full-lifecycle/SKILL.md` (für Signal-spezifische Anteile)

## Arbeitsmodus

- **Precision first.** Auto-Patch ist nur zulässig für Signale mit
  nachgewiesener Precision ≥ 0.9 in
  `tests/test_precision_recall.py`.
- **Dry-Run-Default.** `--auto` muss explizit gesetzt werden. Kein
  stiller Apply.
- **Sandbox-Apply.** Patches werden in einer isolierten Kopie
  angewendet, nicht direkt im Working Tree.
- **Verify via `drift_nudge`.** `direction == "degrading"` →
  sofortiger Rollback, Finding wird als nicht-auto-patchbar
  markiert.

## Ziel

Dem Nutzer erlauben, einen validierten Auto-Patch-Lauf auf den
drei hochpräzisen Signalen MDS, PFS, EDS auszuführen — mit
Dry-Run-Default, Sandbox-Isolation und messbarer Rollback-
Garantie bei Degradation.

## Erfolgskriterien

- **Drei** Sub-ADRs (`proposed`) mit signal-design-Template
  ausgefüllt — je eine für MDS-Auto-Patch, PFS-Auto-Patch,
  EDS-Auto-Patch. Jede benennt Repair-Template, FP-Klassen,
  FN-Klassen, Fixture-Plan.
- Precision für MDS, PFS, EDS aktuell gemessen und in
  `work_artifacts/feature_07_<YYYY-MM-DD>/precision_baseline.md`
  dokumentiert. Signale mit Precision < 0.9 werden aus diesem
  Feature ausgeschlossen und im Orchestrator-Run-Artefakt
  vermerkt.
- CLI-Flag: `drift patch --auto` (neben bestehender Patch-CLI).
- Sandbox-Apply-Pfad: neues Modul
  `src/drift/patch_writer/sandbox.py` oder Erweiterung in
  `patch_writer/`.
- Verify-Adapter: ruft `drift_nudge` auf Sandbox-Kopie auf.
- Rollback-Garantie: getestet mit bewusst "bösartigem" Patch-
  Template, das Score verschlechtert — Test erwartet
  Wiederherstellung des Ausgangszustands.
- Repair-Coverage-Matrix
  `benchmark_results/repair_coverage_matrix.json` aktualisiert.
- Mutation-Benchmark grün, Precision/Recall grün.
- Feature-Evidence `benchmark_results/vX.Y.Z_feature_evidence.json`:
  - pro Signal: TP-Fixes, FP-Fixes (Rollbacks), Roundtrip-Zeit
- Audit-Update Pflicht:
  - `stride_threat_model.md`: Auto-Patch als neuer Trust-Übergang
  - `fmea_matrix.md`: Pro Signal eine Auto-Patch-Zeile
  - `risk_register.md`: Risiko "Auto-Patch verschlechtert Code"
    + Mitigation (Sandbox + Rollback)
  - `fault_trees.md`: "Rollback versagt"-Pfad
- Conventional Commit `feat(patch): apply-and-verify loop for
  MDS/PFS/EDS auto-patches` + `Decision: ADR-NNN, ADR-NNN+1,
  ADR-NNN+2`.

## Phasen

### Phase 1 — Precision-Baseline

- `pytest tests/test_precision_recall.py -v -k "mds or pfs or eds"`
- Ergebnisse in `work_artifacts/feature_07_<YYYY-MM-DD>/precision_baseline.md`.
- Signale mit Precision < 0.9 hier dokumentiert ausschließen,
  nicht stillschweigend übergehen.

### Phase 2 — Drei Sub-ADRs drafen

- `docs/decisions/templates/signal-design-template.md` je Signal.
- Jede ADR benennt konkretes Repair-Template aus
  `src/drift/repair_template_registry.py`.
- Jede ADR benennt, welche Fixture-Klassen in
  `tests/fixtures/ground_truth.py` benötigt werden (TP, FP,
  Confounder).
- Status `proposed`.

### Phase 3 — Sandbox-Apply-Modul

- Neues Modul für isoliertes File-Apply (kopierter Work-Tree in
  tmp-Dir; atomic replace; Rollback durch Dir-Drop).
- Zeit-Budget pro Patch begrenzen (Default 5 s, konfigurierbar).

### Phase 4 — Verify-Adapter

- Adapter ruft `drift_nudge` (via In-Process-API, nicht via
  MCP-Roundtrip) auf Sandbox-Kopie.
- Entscheidung: `improving` / `stable` → commit.
  `degrading` → rollback + Finding als nicht-auto-patchbar
  in `outcome_tracker.py` vermerken.

### Phase 5 — CLI-Integration

- `src/drift/commands/patch_cmd.py`: `--auto`-Flag,
  `--max-patches`-Flag, `--signals`-Filter.
- Keine neuen Subcommands; nur Flags an `drift patch`.

### Phase 6 — Tests

- `tests/test_patch_auto_*.py` je Signal:
  - Happy-Path (TP-Fixture, Patch gelingt, Score verbessert)
  - Rollback-Path (Fixture, bei der der Patch degradieren würde)
  - Edge: kein Patch-Kandidat, Sandbox-Fehler, Timeout
- Mutation-Benchmark muss stabil bleiben.

### Phase 7 — Repair-Coverage-Matrix

- `benchmark_results/repair_coverage_matrix.json` je Signal
  um Auto-Patch-Spalte ergänzen.

### Phase 8 — Audit-Update (Pflicht, §18)

- Alle vier `audit_results/*.md` aktualisieren (siehe
  Erfolgskriterien).
- Audit-Diff-Check via `scripts/check_risk_audit.py --diff-base origin/main`.

### Phase 9 — Feature-Evidence + Commit

- `benchmark_results/vX.Y.Z_feature_evidence.json` mit Vorher/Nachher-
  Precision, Roundtrip-Zeiten, Rollback-Rate.
- CHANGELOG-Eintrag.
- Conventional Commit + Decision-Trailer.
- Push-Gates lokal grün.

## Artefakte

```
work_artifacts/feature_07_<YYYY-MM-DD>/
    precision_baseline.md
    run.md
docs/decisions/ADR-NNN-auto-patch-mds.md
docs/decisions/ADR-NNN+1-auto-patch-pfs.md
docs/decisions/ADR-NNN+2-auto-patch-eds.md
src/drift/patch_writer/sandbox.py
src/drift/api/patch.py                        # erweitert
src/drift/commands/patch_cmd.py               # neues Flag
src/drift/outcome_tracker.py                  # Rollback-Tracking
tests/test_patch_auto_mds.py
tests/test_patch_auto_pfs.py
tests/test_patch_auto_eds.py
tests/fixtures/ground_truth.py                # neue Fixtures
benchmark_results/repair_coverage_matrix.json
benchmark_results/vX.Y.Z_feature_evidence.json
audit_results/stride_threat_model.md
audit_results/fmea_matrix.md
audit_results/risk_register.md
audit_results/fault_trees.md
CHANGELOG.md
```

## Nicht Teil dieses Prompts

- Kein Auto-Commit / Auto-Merge — Mensch bleibt im Loop.
- Keine Ausweitung auf Signale mit Precision < 0.9 in diesem Run.
- Keine Änderung der Signal-Scoring-Gewichte.
- Kein Push, keine Sub-ADR-Akzeptanz durch Agent.
