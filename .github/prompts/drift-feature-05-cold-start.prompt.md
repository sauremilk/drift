---
name: "Drift Feature 05 — drift_nudge Cold-Start Fix"
description: "Implementiert den Cold-Start-Fix für drift_nudge: Profilierung, Sub-ADR, Optimierung der Baseline-Initialisierung in src/drift/api/nudge.py und Cache-Layer, Benchmark-Evidence. Ziel: <1s Cold-Start auf ~1000-File-Repos. Voraussetzung: ADR-084 accepted Option C."
---

# Drift Feature 05 — Cold-Start Fix für drift_nudge

End-to-End-Implementierungs-Prompt für Item 05. Liefert gate-konform:
Sub-ADR, Profiling-Evidenz, Code-Änderung, Tests, Benchmark-Vergleich
und Audit-Update, sofern POLICY §18 betroffen.

> **Pflicht:** Vor Ausführung das Drift Policy Gate durchlaufen.
> Zusätzlich: ADR-084 muss `accepted` sein (Option C).

## Relevante Referenzen

- **Backlog-Item:** [`master-backlog/05-drift-nudge-cold-start.md`](../../master-backlog/05-drift-nudge-cold-start.md)
- **Code-Einsprung:** `src/drift/api/nudge.py`, `src/drift/baseline.py`, `src/drift/cache.py`, `src/drift/incremental.py`
- **Baseline-Messung:** [`benchmark_results/mcp_performance_smoke.json`](../../benchmark_results/mcp_performance_smoke.json) (~4.7 s heute)
- **ADR-Workflow:** `.github/skills/drift-adr-workflow/SKILL.md`
- **Push-Gates:** `.github/instructions/drift-push-gates.instructions.md`
- **Konventionen:** `.github/prompts/_partials/konventionen.md`

## Arbeitsmodus

- Messen vor Ändern. Kein Fix ohne reproduzierbares Profil.
- Kleinster Fix zuerst. Kein Architekturumbau, wenn Lazy-Init oder
  Caching-Reuse ausreicht.
- Alle Messungen auf einem definierten Referenz-Repo (~1000 Python-
  Files). Wenn nicht vorhanden, Referenz aus `benchmark_results/`
  ableiten.

## Ziel

Cold-Start-Latenz von `drift_nudge` auf einem Repo mit ~1000
Python-Files von heutigen ~4.7 s auf **< 1 s** reduzieren, ohne
Warm-Call-Latenz oder Korrektheit zu verschlechtern.

## Erfolgskriterien

- Sub-ADR unter `docs/decisions/ADR-NNN-drift-nudge-cold-start.md`
  als `proposed` existiert und benennt Ursache, Fix-Strategie,
  erwartete Seiteneffekte.
- Profiling-Evidenz (py-spy / cProfile / built-in Timer) vor und
  nach dem Fix unter `benchmark_results/cold_start_<version>.json`.
- Code-Änderung in minimalem Scope, vorzugsweise in
  `src/drift/api/nudge.py` und ggf. `src/drift/baseline.py` oder
  `src/drift/cache.py`.
- Neuer Test in `tests/` (Namensvorschlag
  `test_nudge_cold_start.py`), der Cold-Start < 1 s auf
  synthetischer Baseline verifiziert (mit Toleranz-Faktor).
- Warm-Call-Test weiterhin grün; keine Regression in
  `tests/test_precision_recall.py`.
- Feature-Evidence unter
  `benchmark_results/vX.Y.Z_feature_evidence.json` (Version aus
  `pyproject.toml` zum Commit-Zeitpunkt).
- Policy §18-Prüfung dokumentiert: falls Caching-Verhalten
  materiell geändert, sind FMEA / Risk-Register aktualisiert.
- Conventional Commit `feat(nudge): reduce cold-start latency
  below 1s` mit `Decision: ADR-NNN`-Trailer.
- Alle Push-Gates lokal grün.

## Phasen

### Phase 1 — Profilierung (Pflicht)

- Referenz-Repo wählen (Drift-Self-Repo oder kontrolliertes
  Fixture-Repo ~1000 files).
- Cold-Start-Messung: Cache und Baseline komplett löschen,
  `drift_nudge` erstmalig aufrufen, Zeit messen.
- Profil-Dump generieren (cProfile → snakeviz-konformes `.prof`
  oder py-spy-Output).
- Hotspots identifizieren und in Sub-ADR dokumentieren.
- Output: `work_artifacts/feature_05_<YYYY-MM-DD>/profile_before.md`.

### Phase 2 — Sub-ADR drafen

- Nächste freie ADR-Nummer wählen (derzeit ab 085).
- Template: `docs/decisions/templates/adr-template.md`.
- Kontext zitiert Phase-1-Profil-Evidenz und
  `benchmark_results/mcp_performance_smoke.json` Baseline.
- Entscheidung beschreibt exakten Fix (z. B. "Lazy-Init des
  Embeddings-Subsystems in nudge-Pfad verschieben", "Baseline-
  Serialization auf msgpack statt json umstellen", "partieller
  Scope-Scan statt Full-Baseline").
- Nicht-Teil-Liste verpflichtend.
- Validierung: Benchmark-Kriterium < 1 s auf Referenz-Repo,
  Warm-Call keine Regression, Precision-Recall unverändert.
- Status `proposed`. Maintainer-Accept als Freigabe zur Phase 3.

### Phase 3 — Code-Änderung

- Nur die im Sub-ADR benannten Einsprungspunkte anfassen.
- Keine Nebenverbesserungen in `src/drift/api/nudge.py`.
- Type-Hints und Docstrings für alle geänderten öffentlichen
  Funktionen (Push-Gate Docstring-Regel beachten).
- `mcp_nudge`-Aufrufpfad mitprüfen, falls dieser parallel zum
  CLI-Pfad existiert.

### Phase 4 — Tests

- Neuer Test `tests/test_nudge_cold_start.py`:
  - Fixture räumt Cache und Baseline weg
  - Misst erste `nudge`-Call-Dauer
  - Schlägt fehl, wenn > 1.0 s auf Standard-CI-Hardware (mit
    konfigurierbarem Multiplikator via env-var, default 1.0)
- Regressionstests in `tests/test_nudge_*.py` unverändert grün.
- `pytest tests/test_precision_recall.py -v` grün.
- Mutation-Benchmark unangetastet (Nudge-Fix sollte dort keine
  Wirkung haben; falls doch: Review im Sub-ADR).

### Phase 5 — Benchmark-Evidence

- Erneute Cold-Start-Messung nach Fix.
- `benchmark_results/cold_start_vX.Y.Z.json` mit Vorher/Nachher-
  Zahlen, Referenz-Repo-Bezeichnung, Hardware-Stichpunkt, Commit-
  Hash.
- Feature-Evidence unter
  `benchmark_results/vX.Y.Z_feature_evidence.json` gemäß
  bestehender Konvention (Muster: `v2.14.0_patch_engine_feature_evidence.json`).

### Phase 6 — Audit-Update (bedingt)

- Prüfung: Ändert der Fix das Caching-Verhalten messbar (z. B.
  neue Cache-Datei, veränderte Invalidierung, längere TTL)?
- Falls ja: `audit_results/fmea_matrix.md` Zeile(n) zum
  Nudge/Baseline-Pfad ergänzen, `audit_results/risk_register.md`
  Risiko-Eintrag aktualisieren.
- Falls nein: explizit dokumentieren, dass POLICY §18 geprüft und
  nicht anwendbar.

### Phase 7 — CHANGELOG und Commit

- CHANGELOG-Eintrag unter aktueller `pyproject.toml`-Version
  (oder nächstem Minor-Bump falls Release-Strategie es erfordert).
- Commit: `feat(nudge): reduce cold-start latency below 1s`.
- Body: kurze Erklärung, Vorher/Nachher-Zahlen, `Decision: ADR-NNN`.
- Push-Gates lokal laufen lassen — kein Push ohne explizite
  User-Anweisung.

## Artefakte

```
work_artifacts/feature_05_<YYYY-MM-DD>/
    profile_before.md
    profile_after.md
    run.md
docs/decisions/ADR-NNN-drift-nudge-cold-start.md
benchmark_results/cold_start_vX.Y.Z.json
benchmark_results/vX.Y.Z_feature_evidence.json
tests/test_nudge_cold_start.py
src/drift/api/nudge.py        # ggf. modifiziert
src/drift/baseline.py         # ggf. modifiziert
src/drift/cache.py            # ggf. modifiziert
```

## Nicht Teil dieses Prompts

- Keine Erweiterung der Nudge-Output-Felder.
- Kein Refactoring der Baseline-Cache-Logik außerhalb des
  Cold-Start-Pfads.
- Kein Push, kein `accepted`-Flip der Sub-ADR durch den Agent.
- Keine Änderung an anderen MCP-Tools (nur `drift_nudge` / CLI-
  Nudge-Pfad).
