---
name: drift-evidence-artifact-authoring
description: "Erstellt und befüllt versioned feature-evidence Artefakte für feat:-Commits im Drift-Repo. Verwenden wenn ein benchmark_results/-Artefakt für einen Feature-Commit fehlt oder unklar ist wie es benannt, strukturiert oder befüllt werden soll. Keywords: feature evidence, benchmark_results, versioned evidence file, feat: commit gate, evidence artifact, precision recall, self_analysis, audit_artifacts_updated."
argument-hint: "Version (z.B. 2.9.0), Feature-Slug (z.B. phr-signal) und kurze Beschreibung der Änderung angeben."
---

# Drift Evidence Artifact Authoring Skill

Dieser Skill produziert ein vollständiges, commit-readies `vX.Y.Z_<feature-slug>_feature_evidence.json` in `benchmark_results/`.

## Wann Verwenden

- `feat:` commit geplant und `drift-commit-push` beanstandet fehlendes Evidence-File
- Neues Signal oder materielle Heuristikänderung abgeschlossen
- Precision-/Recall-Änderung > 5 Prozentpunkte vorhanden und zu belegen
- Signal-Fix oder FP-Reduktion mit empirischen Belegen versehen

## Pflicht-Vorbedingungen

1. Tests laufen durch (`make test-fast` grün)
2. ADR vorhanden oder Entscheidung explizit als fix/refactor eingestuft
3. Version aus `pyproject.toml` oder geplanter nächster Version bekannt
4. `git diff --stat` zeigt, welche Dateien tatsächlich geändert wurden

---

## Step 1: Dateinamen bestimmen

Konvention:

```
benchmark_results/v{VERSION}_{feature-slug}_feature_evidence.json
```

- `{VERSION}` = konkrete Semver-Version (z.B. `2.9.1`), KEIN `v`-Präfix im Feld selbst
- `{feature-slug}` = kurzer Kebab-Case-Bezeichner des Features/Fixes (z.B. `phr-signal`, `avs-co-change-precision-hardening`, `dia-fp-reduction`)
- Keine Leerzeichen, Unterstriche nur als Trenner zwischen Segmenten

Beispiele aus dem Repo:
- `v2.7.1_phr_signal_feature_evidence.json`
- `v2.5.4_avs_co_change_precision_hardening_feature_evidence.json`
- `v2.9.0_actionability_hardening_feature_evidence.json`

---

## Step 2: Pflichtfelder vs. optionale Felder

### Immer vorhanden (Pflicht)

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `version` | string | Semver ohne `v`-Präfix (`"2.9.1"`) |
| `feature` | string | Kurzbeschreibung der Änderung |
| `description` | string | Volltext-Description, 1–3 Sätze |
| `tests` | object | Testergebnis nach Implementierung |
| `audit_artifacts_updated` | array | Welche Audit-Dateien aktualisiert wurden |

### Bei `feat:` mit Signal-Arbeit

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `adrs` | array | ADR-Referenzen (`["ADR-033"]`) |
| `signals_changed` | array | Pro geändertem Signal: `signal`, `adr`, `changes[]` |
| `signal_added` | string | Nur bei neuem Signal: interner Name |
| `signal_abbrev` | string | Drei/Vier-Buchstaben-Kürzel |
| `precision_recall` | object | precision/recall/f1/tp/fp/fn/tn + fixture coverage |
| `benchmarks` | object | mutation_benchmark, self_analysis, ground_truth, unit_tests |

### Optional / situativ

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `date` | string | ISO-Datum (`"2026-04-12"`) — empfohlen bei neuen Signalen |
| `signal_category` | string | z.B. `ai_quality`, `architecture` |
| `signal_weight` | number | Gewichtung im Score (0.0 bei report-only) |
| `signal_scope` | string | z.B. `report-only`, `scored` |
| `change_type` | string | `fix`, `feat`, `refactor` (nützlich für FP-Reduktions-Evidenz) |
| `title` | string | Ausführlicher Titel (nützlich bei fix: mit ADR-Bezug) |

---

## Step 3: Felder korrekt befüllen

### `tests`

Immer nach einem `make test-fast` oder vollem Test-Run befüllen:

```json
"tests": {
  "total_passing": 1234,
  "total_failing": 0,
  "failing_note": "Nur wenn failing > 0: Erklärung pre-existing vs. neu",
  "changed_test_files": [
    "tests/test_mein_signal.py"
  ]
}
```

Werte aus pytest-Output entnehmen. Nie schätzen.

### `precision_recall` (nur bei Signal-Arbeit)

```json
"precision_recall": {
  "precision": 1.0,
  "recall": 1.0,
  "f1": 1.0,
  "tp": 5,
  "fp": 0,
  "fn": 0,
  "tn": 10,
  "fixture_coverage": {
    "positive": ["fixture_tp_1", "fixture_tp_2"],
    "negative": ["fixture_tn_1"],
    "boundary": ["fixture_boundary_1"],
    "confounder": ["fixture_confounder_1"]
  }
}
```

Werte aus `make test-precision-recall` oder dem `test_precision_recall.py`-Lauf entnehmen.

### `benchmarks.self_analysis`

Vor/nach-Vergleich auf dem Drift-Repo selbst:

```json
"self_analysis": {
  "before": {
    "drift_score": 0.522,
    "total_findings": 345
  },
  "after": {
    "drift_score": 0.501,
    "total_findings": 330
  },
  "delta_findings": -15,
  "delta_score": -0.021,
  "source": "benchmark_results/drift_self_full.json"
}
```

Wenn kein signifikanter Unterschied erwartet: `"note": "keine Auswirkung auf self-analysis erwartet"` reicht.

### `audit_artifacts_updated`

Array der tatsächlich geänderten Audit-Dateien. Nie leer lassen wenn `src/drift/` geändert wurde.

```json
"audit_artifacts_updated": [
  "audit_results/fmea_matrix.md",
  "audit_results/fault_trees.md",
  "audit_results/risk_register.md"
]
```

Regeln aus `drift-commit-push` Step 3:
- Signal geändert → `fmea_matrix.md`, `fault_trees.md`, `risk_register.md`
- Trust-Boundary / Input-Output-Pfad geändert → zusätzlich `stride_threat_model.md`

---

## Step 4: Vollständiges Minimal-Template (fix:)

Für einen `fix:`-Commit mit FP-Reduktion ohne neues Signal:

```json
{
  "version": "X.Y.Z",
  "date": "JJJJ-MM-TT",
  "change_type": "fix",
  "title": "Kurztitel (ADR-NNN wenn vorhanden)",
  "feature": "feature-slug",
  "description": "Ein bis drei Sätze: Was wurde behoben und warum.",
  "adr": "ADR-NNN",
  "signals_changed": [
    {
      "signal": "ABBR",
      "adr": "ADR-NNN",
      "changes": [
        "konkreter Satz zur Änderung"
      ]
    }
  ],
  "tests": {
    "total_passing": 0,
    "total_failing": 0,
    "changed_test_files": []
  },
  "benchmarks": {
    "self_analysis": {
      "before": { "drift_score": 0.0, "total_findings": 0 },
      "after": { "drift_score": 0.0, "total_findings": 0 },
      "delta_findings": 0,
      "delta_score": 0.0,
      "source": "benchmark_results/drift_self_full.json"
    },
    "ground_truth": {
      "all_fixtures_passing": true,
      "precision_recall_tests": 0,
      "regressions": 0,
      "source": "tests/test_precision_recall.py"
    },
    "unit_tests": {
      "changed_signal_suite": "0/0",
      "full_suite_excluding_smoke": "0 passed, 0 skipped"
    }
  },
  "audit_artifacts_updated": [
    "audit_results/fmea_matrix.md",
    "audit_results/fault_trees.md",
    "audit_results/risk_register.md"
  ]
}
```

---

## Step 5: Vollständiges Template (feat: neues Signal)

```json
{
  "version": "X.Y.Z",
  "date": "JJJJ-MM-TT",
  "feature": "ABBR: Signal-Name (ADR-NNN)",
  "adr": "ADR-NNN",
  "signal_added": "signal_name_snake_case",
  "signal_abbrev": "ABBR",
  "signal_category": "ai_quality|architecture|code_quality|security",
  "signal_weight": 0.0,
  "signal_scope": "report-only|scored",
  "description": "Kurzbeschreibung des neuen Signals.",
  "precision_recall": {
    "precision": 1.0,
    "recall": 1.0,
    "f1": 1.0,
    "tp": 0,
    "fp": 0,
    "fn": 0,
    "tn": 0,
    "total_fixtures": 0,
    "fixture_coverage": {
      "positive": [],
      "negative": [],
      "boundary": [],
      "confounder": []
    }
  },
  "aggregate_f1_after": 1.0,
  "total_fixtures_after": 0,
  "self_analysis": {
    "findings_on_drift_repo": 0,
    "total_findings": 0,
    "findings_in_src": 0,
    "classification": "alle_true_positive",
    "findings": [],
    "note": "Manuelle Verifikation: ..."
  },
  "tests": {
    "total_passing": 0,
    "total_failing": 0,
    "changed_test_files": []
  },
  "audit_artifacts_updated": [
    "audit_results/fmea_matrix.md",
    "audit_results/fault_trees.md",
    "audit_results/risk_register.md"
  ]
}
```

---

## Step 6: Qualitätskontrolle vor dem Commit

Checkliste (alle Punkte müssen erfüllt sein):

- [ ] Dateiname folgt `vX.Y.Z_<slug>_feature_evidence.json` exakt
- [ ] `version` stimmt mit `pyproject.toml` bzw. geplantem Release überein
- [ ] `tests.total_passing` stammt aus echtem pytest-Lauf (nicht geschätzt)
- [ ] `audit_artifacts_updated` enthält alle tatsächlich geänderten Audit-Dateien
- [ ] Keine Platzhalter (`0`, `""`, `[]`) für Felder, für die echte Daten vorliegen
- [ ] `precision_recall` (bei Signal-Arbeit) aus Test-Output entnommen, nicht geschätzt
- [ ] `self_analysis.delta_score` auf drei Dezimalstellen gerundet (`round(after - before, 3)`)
- [ ] JSON valide (kein trailing comma, korrektes Encoding)

---

## Häufige Fehler

| Fehler | Korrektur |
|--------|-----------|
| Datei heißt `feature_evidence_v2.9.0.json` | Muss `v2.9.0_<slug>_feature_evidence.json` sein |
| `version` enthält `"v2.9.0"` | Ohne `v`-Präfix: `"2.9.0"` |
| `total_passing` = 0 bei laufenden Tests | Immer aus pytest-Output befüllen |
| `audit_artifacts_updated` leer obwohl Signal geändert | Mindestens `fmea_matrix.md` + `fault_trees.md` + `risk_register.md` |
| Kein `self_analysis` bei feat: | Vor/nach-Diff auf Drift-Repo ausführen und eintragen |
| `precision_recall` fehlt bei neuem Signal | Pflichtfeld für jede neue Signal-Implementierung |

---

## Referenzen

- `benchmark_results/README.md` — Übersicht über alle Artefakttypen
- `.github/skills/drift-commit-push/SKILL.md` — Gate-Anforderungen für feat:-Commits (Step 3)
- `.github/skills/drift-signal-development-full-lifecycle/SKILL.md` — Vollständiger Signal-Lifecycle
- `.github/skills/drift-risk-audit-artifact-updates/SKILL.md` — Audit-Artefakt-Updates
