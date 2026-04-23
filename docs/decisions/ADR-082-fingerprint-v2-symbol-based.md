---
id: ADR-082
status: proposed
date: 2026-04-21
supersedes:
---

# ADR-082: Fingerprint v2 — symbol-based, line-agnostic

## Kontext

Der aktuelle `finding_fingerprint()` in `src/drift/baseline.py` basiert auf
`(signal_type, file_path, start_line, end_line, title)`. Damit ist er nach
jedem Edit, der Code oberhalb eines Findings verschiebt, nicht mehr stabil.
Dasselbe gilt für Titel, die Metriken enthalten (z. B.
`"return_pattern: 2 variants in scripts/"`).

Die HEAD-Subtraktion in `src/drift/api/diff.py`
(`_subtract_pre_existing_head`) nutzt denselben Fingerprint. Wenn dieser
shiftet, kann sie pre-existing Findings nicht mehr als solche erkennen und
meldet sie fälschlich als "neu".

Belegt durch Field-Test am 2026-04-21
(`work_artifacts/reduce_findings_2026-04-21/`):

- Agent hat 5 Fixes gemacht (extract_function, keine Regression der
  Komplexität in den Zielfunktionen).
- `drift_diff` meldete anschließend **13 neue Findings**, davon:
  - 3 via HEAD-Subtraktion korrekt als pre-existing gefiltert
  - ca. 6 weitere waren pre-existing, wurden aber wegen Line-Shift /
    Metrik-Titel-Änderung nicht erkannt (false-new-FPs)
  - ca. 4 waren echte, aber vermeidbare Agent-Inkonsistenzen
    (PFS error_handling, return_pattern)

Folge: Agent verliert Vertrauen in `drift_diff`, der Fix-Loop wird
abgebrochen oder drift wird abgeschaltet. Das trifft das
Zulassungskriterium "Glaubwürdigkeit" aus `POLICY.md` §8 direkt.

## Entscheidung

Einführen eines neuen Fingerprint-Schemas v2, das ausschließlich
stabile Identitätsmerkmale verwendet und Zeilennummern sowie
metrik-enthaltende Titel-Segmente ignoriert.

**v2-Schema:**

```text
fingerprint_v2 = sha256(
    signal_type || file_path || symbol_identity || stable_title
)[:16]
```

**`symbol_identity`** — erste nicht-leere Komponente dieser Kaskade:

1. `logical_location.fully_qualified_name` (z. B. `src.api.auth.login`)
2. `logical_location.name`
3. `symbol` (z. B. `main`, `login`)
4. Leerstring (Fallback: nur file-scope)

**`stable_title`** — Titel mit entfernten Metriken:

- Zahlen (z. B. `"2 variants"`, `"complexity 19"`) werden durch
  Platzhalter `"<N>"` ersetzt
- Nachlaufende Klammer-Listen mit Zeilenverweisen
  (z. B. `"(scripts/foo.py:87)"`) werden entfernt

**Baseline-Schema bump:** `_BASELINE_VERSION = 1 → 2`.
`save_baseline()` schreibt künftig beide Fingerprints (v1 + v2) in jeden
Eintrag für einen Übergangszeitraum von 2 Minor-Releases.
`load_baseline()` akzeptiert beide Formate und gibt beide Mengen zurück.

**HEAD-Subtraktion in `diff.py`:** Primärer Pass nutzt v2. Optionaler
zweiter ("fuzzy") Pass matcht auf `(signal, file, stable_title)` ohne
Symbol für Signale, die keinen stabilen Symbol-Scope haben
(z. B. TPD repo-weit). Default on, abschaltbar via
`thresholds.diff_fuzzy_head_subtraction = false`.

**Nicht Teil dieser Entscheidung:**

- Kein Umbau von ADR-042 `finding_id`: exponierte `finding_id`-Strings
  wechseln auf v2, ein `finding_id_legacy`-Feld wird für einen
  Release-Zyklus mitgeliefert.
- Keine Änderung am `drift_nudge` Incremental-Baseline-Mechanismus
  (ADR-059). Angleichung erfolgt in separater ADR, sobald v2 stabil ist.
- Kein neues Finding-Schema; `Finding.symbol` und
  `Finding.logical_location` existieren bereits.
- Keine Umbenennung oder Entfernung der v1-Funktion — sie bleibt als
  `finding_fingerprint_v1()` exportiert für Migration und Regression.

## Begründung

**Warum symbol-basiert statt line-basiert?** Line-Nummern sind
definitionsgemäß instabil unter Editing. Ein Fingerprint, der nach
einem Edit zuverlässig matchen soll, darf keine line-sensitive
Komponente enthalten. `symbol` bzw. `logical_location` sind genau die
AST-bezogenen, refactor-stabilen Identitäten, die Drift bereits
produziert (`src/drift/models/_findings.py`).

**Warum `stable_title` statt `title`?** Viele Signale setzen
Aggregat-Metriken in den Titel (`"2 variants"`, `"complexity 19"`).
Diese Metriken ändern sich bei unverwandten Edits → Fingerprint shiftet
ohne echte Identitätsänderung. Metrik-Stripping bewahrt die
Signal-Identität ohne FP-Flut zu maskieren.

**Warum Fuzzy-Pass optional aber default on?** Ohne Fuzzy-Pass bleiben
Signale ohne Symbol-Scope (TPD, repo-weite DCA) weiter anfällig.
Mit Fuzzy-Pass besteht theoretisches Risiko, dass ein echtes neues
Finding mit gleichem `stable_title` wie ein pre-existing als
pre-existing gefiltert wird. Dieses Risiko ist in der Praxis klein
(Signal+Datei+title-Basiswort muss identisch sein) und der UX-Gewinn
überwiegt. Config-Escape bleibt.

**Warum Übergang über 2 Minor-Releases?** Externe CI-Pipelines
persistieren evtl. v1-Fingerprints. Breaking Change in einem Minor
widerspricht ADR-042-Geist. Dual-Write in v2.27–v2.29 plus
v1-Entfernung in einem späteren Major (oder v3.0).

**Alternativen verworfen:**

- *Line-Range-Tolerance* (± N Zeilen): Heuristisch, fehleranfällig bei
  größeren Umstrukturierungen.
- *Content-Hash des Quelltext-Ausschnitts*: Bricht bei jeder Code-
  Änderung in der Funktion selbst — genau das, was wir nicht wollen.
- *Nur-Fuzzy ohne v2*: Löst das Shift-Problem nicht für Findings mit
  variablem Titel und für baseline-basierten Vergleich.

## Konsequenzen

**Positiv:**

- `drift_diff` meldet nach Zeilenverschiebung 0 false-new-Findings
  (verifiziert durch Fixture `shift_only`, Test
  `test_diff_uncommitted_ignores_shifted_findings`).
- Baseline-Dateien bleiben nach lokalen Refactorings länger nutzbar.
- Grundlage für künftige symbol-basierte Features (z. B. Finding-
  Tracking durch Rename-Detection).

**Trade-offs / Risiken:**

- Signale, die `symbol` oder `logical_location` heute nicht setzen,
  erhalten v2-Fingerprints auf Basis nur von `(signal, file, title)`.
  Das ist strikt besser als v1 (kein Line-Shift), aber nicht ideal.
  Audit-Follow-up: alle funktions-scoped Signale (EDS, CXS, GCD, MDS,
  AVS, PFS) müssen `symbol` setzen. Separat getrackt.
- Baseline-Dateien aus v1 führen beim Laden zu einer Warnung und
  werden auf Best-Effort-Basis konvertiert; Einträge ohne v2-Match
  gelten weiter als bekannt (v1-Set bleibt aktiv für diesen Release).
- Externe Konsumenten, die `fingerprint`-Strings persistieren, müssen
  auf `finding_id` + `finding_id_legacy` migrieren.

**Policy §18 (Risk-Audit) betroffen:** JA.

- `audit_results/fmea_matrix.md`: Ausfallmodus
  "drift_diff meldet pre-existing Findings als neu" wird als
  `mitigated` markiert.
- `audit_results/risk_register.md`: Risiko
  "Agent verliert Vertrauen in drift_diff" von `open` → `mitigated`.
- `audit_results/fault_trees.md`: Pfad
  "drift_diff reports false-new" aktualisiert mit Fingerprint-v2 als
  Gegenmaßnahme.
- `audit_results/stride_threat_model.md`: Re-Evaluierung ob Fuzzy-Pass
  Tampering-Angriffsfläche vergrößert. Erwartung: nein, weil
  Severity/High-Gate auf den anderen Feldern davor greift.

## Validierung

Die Entscheidung gilt als validiert, wenn alle folgenden Kriterien
erfüllt sind:

1. **Shift-Stability**: Fixture `shift_only` in
   `tests/fixtures/ground_truth.py`: gleiches Symbol, Zeilen +10
   verschoben → v2-Fingerprint identisch. Test:
   `test_fingerprint_v2_stable_across_line_shift`.

2. **Metric-Title-Stability**: Fixture `metric_only`: gleiches Symbol,
   Titel-Metrik ändert sich → v2-Fingerprint identisch. Test:
   `test_fingerprint_v2_stable_across_metric_title_change`.

3. **Rename-Sensitivity**: Fixture `rename`: Symbol-Name ändert sich →
   v2-Fingerprint **unterschiedlich** (echter Neu-Finding). Test:
   `test_fingerprint_v2_detects_genuine_rename`.

4. **Baseline-Migration**: v1-Baseline-Datei laden → kein Crash, v2-
   Fingerprints für matchende Einträge enthalten, Warnung emittiert.
   Test: `test_baseline_v1_to_v2_migration_roundtrip`.

5. **Diff-Regression**: Re-Run des reduce-findings-Field-Tests
   (v2.26.2 target) mit v2-Code → `new_finding_count <= 6` (statt 13
   wie in v1). Evidenz in
   `benchmark_results/v2.27.0_feature_evidence.json`.

6. **Keine Präzisions-Regression**: `tests/test_precision_recall.py`
   (Signal-Precision/Recall) darf keine Degradation zeigen. Baseline-
   Werte im selben Commit aktualisieren, falls nominale Änderung durch
   Fingerprint-Schema (erwartet: keine).

7. **Mutation-Benchmark**: `scripts/_mutation_benchmark.py` neutral
   oder besser.

Lernzyklus-Ergebnis-Kategorie (POLICY.md §10): erwartet `bestätigt`
nach Field-Test-Re-Run.
