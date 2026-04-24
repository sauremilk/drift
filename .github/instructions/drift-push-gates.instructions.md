---
description: "Nutze diese Instruction, wenn ein Commit, ein Push oder eine Release-Vorbereitung im Drift-Repo ansteht. Sie ist die autoritative Gate-Quelle fuer Pre-Push-Anforderungen, Bypaesse und lokale CI-Pflichten."
---

# Drift Pre-Push Gates — Vollständige Checkliste für Agenten

Der Hook in `.githooks/pre-push` blockiert jeden Push, der eine der folgenden Bedingungen verletzt.
**Agenten müssen alle zutreffenden Gates erfüllen, bevor sie `git push` ausführen.**

Diese Datei ist nur fuer Commit-/Push-Vorbereitung relevant, nicht fuer allgemeine Implementierungsarbeit.

---

## Übersicht: Welches Gate gilt bei welcher Änderung?

`feat:` / `fix:` / `BREAKING:` folgen den Conventional-Commit-Regeln aus `.github/instructions/drift-release-automation.instructions.md`.

| Geänderte Dateien | Erforderliches Gate |
|-------------------|---------------------|
| `tagesplanung/**` | ❌ Immer blockiert — nie pushen |
| `feat:`-Commit vorhanden | Feature-Evidence-Gate (Gate 2) |
| `feat:` oder `fix:`-Commit vorhanden | Changelog-Gate (Gate 3) |
| `pyproject.toml` geändert | Version-Gate (Gate 4) + Lockfile-Gate (Gate 5) |
| `src/drift/**` geändert | Docstring-Gate (Gate 6) |
| `src/drift/signals/**`, `src/drift/ingestion/**` oder `src/drift/output/**` geändert | Risk-Audit-Gate (Gate 7) |
| Immer (alle Pushes) | CI-Checks (Gate 8) |

---

## Gate 1 — Blockierte Pfade

**Bedingung:** Kein Commit darf Dateien unter `tagesplanung/` enthalten.
**Auslöser:** Immer (jeder Push).
**Aktion:** Diese Pfade niemals committen.

---

## Gate 2 — Feature-Evidence-Gate

**Auslöser:** Push enthält mindestens einen Commit mit Prefix `feat:` (oder `feat(scope):`).
**Alle vier Bedingungen müssen gleichzeitig erfüllt sein:**

1. **Tests vorhanden:** Mindestens eine Datei unter `tests/` muss im Push enthalten sein.
2. **Empirisches Artefakt vorhanden:** Mindestens eine Datei unter `benchmark_results/` oder `audit_results/` muss im Push enthalten sein.
3. **Versioned Evidence-Datei vorhanden:** Eine Datei die auf `benchmark_results/vX.Y.Z_feature_evidence.json` matcht (oder entsprechendes Muster).
4. **STUDY.md aktualisiert:** `docs/STUDY.md` muss im Push enthalten sein (sofern die Datei existiert).

### Gate 2b — Evidence Content Validation (deterministisch)

**Zusatzbedingung:** Die Evidence-Datei muss einen `generated_by`-Block enthalten, der von
`scripts/generate_feature_evidence.py` erzeugt wurde. Der Block wird maschinell geprüft:

- `generated_by.script` muss `"scripts/generate_feature_evidence.py"` sein.
- `generated_by.git_sha` muss ein existierender Git-Commit im Repository sein.
- `generated_by.git_sha` muss ein Ancestor des Push-Heads sein (verhindert SHA-Wiederverwendung).
- `generated_by.timestamp` muss ein valides ISO-8601-Datum sein, das nicht in der Zukunft liegt.
- Metriken wie `drift_score` ∈ [0,1], `tests.total_failing == 0`.

**Validierung läuft via:** `python scripts/validate_feature_evidence.py <file> --require-generated-by --push-head <SHA>`
**Bypass (Notfall):** `DRIFT_SKIP_EVIDENCE_VALIDATION=1 git push`

**Typische Vorgehensweise bei feat::**
```bash
# 1. Tests schreiben
# 2. Evidence-Datei deterministisch erzeugen (NICHT manuell erstellen):
python scripts/generate_feature_evidence.py --version X.Y.Z --slug my-feature
# 3. docs/STUDY.md aktualisieren
# 4. Alle zusammen committen
```

**Backward-Compat:** Bestehende Evidence-Dateien ohne `generated_by`-Block werden nur ohne
`--require-generated-by` akzeptiert. Für neue `feat:`-Commits ist der Block Pflicht.

---

## Gate 3 — Changelog-Gate

**Auslöser:** Push enthält mindestens einen `feat:` oder `fix:`-Commit.
**Bedingung:** `CHANGELOG.md` muss im Push geändert sein.
**Bypass:** `DRIFT_SKIP_CHANGELOG=1 git push` (Notfall).

---

## Gate 4 — Version-Bump-Gate

**Auslöser:** `pyproject.toml` ist im Push geändert.
**Bedingung:** Die Version in `pyproject.toml` muss strikt größer sein als der letzte Git-Tag auf Origin (SemVer).
**Bypass:** `DRIFT_SKIP_VERSION_BUMP=1 git push` (Notfall).

> **Hinweis:** Da Releases via python-semantic-release (PSR) in CI laufen, sollten Agenten `pyproject.toml` nie manuell versionieren. Falls `pyproject.toml` aus anderen Gründen geändert wird (Dependencies), kann das Gate ausgelöst werden — dann Bypass verwenden.

---

## Gate 5 — Lockfile-Sync-Gate

**Auslöser:** `pyproject.toml` ist im Push geändert.
**Bedingung:** `uv.lock` muss ebenfalls im Push enthalten sein.
**Behebung:**
```bash
uv lock
git add uv.lock
git commit --amend --no-edit  # oder separater Commit
```
**Bypass:** `DRIFT_SKIP_LOCKFILE=1 git push` (Notfall).

---

## Gate 6 — Public-API-Docstring-Gate

**Auslöser:** Mindestens eine Datei unter `src/drift/` ist im Push geändert.
**Bedingung:** Jede neu hinzugefügte öffentliche Funktion der Form `def name(...)` (lowercase, kein `_`-Prefix) in `src/drift/` muss im selben Diff eine Docstring-Zeile (`"""` oder `'''`) enthalten.
**Bypass:** `DRIFT_SKIP_DOCSTRING=1 git push` (Notfall).

---

## Gate 7 — Risk-Audit-Gate (Policy §18)

**Auslöser:** Mindestens eine Datei unter einem dieser Pfade ist im Push geändert:
- `src/drift/signals/`
- `src/drift/ingestion/`
- `src/drift/output/`

**Bedingung:** Mindestens **eine** der folgenden Audit-Artefakt-Dateien muss im selben Push geändert sein:
- `audit_results/fmea_matrix.md`
- `audit_results/stride_threat_model.md`
- `audit_results/fault_trees.md`
- `audit_results/risk_register.md`

**Außerdem:** Alle vier Audit-Artefakte müssen weiterhin existieren (Löschutz).

**Typische Vorgehensweise bei Signal/Ingestion/Output-Änderungen:**
```
# Nach der Code-Änderung:
# 1. audit_results/risk_register.md öffnen und Änderung dokumentieren
# 2. Je nach Art der Änderung (siehe Tabelle unten):
#    - Neues/geändertes Signal → fmea_matrix.md + fault_trees.md + risk_register.md
#    - Neuer Input-/Output-Pfad → stride_threat_model.md + risk_register.md
# 3. Beides zusammen committen
```

**Welche Audit-Datei bei welcher Änderung:**

| Art der Änderung | Zu aktualisierende Audit-Artefakte |
|---|---|
| Neues oder geändertes Signal | `fmea_matrix.md` (FP+FN Eintrag) + `fault_trees.md` (FT-Pfade) + `risk_register.md` |
| Neuer Input- oder Output-Pfad | `stride_threat_model.md` (Trust Boundary) + `risk_register.md` |
| Precision/Recall Δ > 5% | `fmea_matrix.md` (RPNs neu) + `risk_register.md` (Messwerte) |

**Bypass:** `DRIFT_SKIP_RISK_AUDIT=1 git push` (Notfall, muss begründet werden).

---

## Gate 8 — CI-Checks (lokal, immer)

**Auslöser:** Immer — jeder Push läuft durch die vollständige lokale Check-Kette.

| Schritt | Befehl | Bypass |
|---------|--------|--------|
| 1 | `python scripts/check_version.py --check-semver` | – |
| 1b | `python scripts/check_release_discipline.py` | – |
| 1c | `python scripts/check_model_consistency.py` | – |
| 1d | `python scripts/check_repo_hygiene.py --config .github/repo-guard.blocklist --root-allowlist .github/repo-root-allowlist` | – |
| 2 | `ruff check src/ tests/` | – |
| 3 | `python -m mypy src/drift` | – |
| 4 | `pytest -q --tb=short -n 4 --dist=loadscope --cov --cov-report= --ignore=tests/test_smoke_real_repos.py` | Worker-Zahl via `DRIFT_PYTEST_WORKERS=N` überschreibbar; Default 4 verhindert OOM auf Maschinen mit vielen Kernen |
| 5 | `drift analyze --repo . --format json --exit-zero` | – |

**Diese Checks haben keinen Bypass-Mechanismus.**
Vor jedem Push sicherstellen: `make check` lokal bestanden.

> **Windows / PowerShell:** `make` ist nicht nativ verfügbar. Stattdessen:
> ```powershell
> .\scripts\check.ps1        # entspricht make check
> .\scripts\check.ps1 lint   # entspricht make lint
> ```
> Das Skript delegiert an Git Bash (wird mit Git for Windows mitgeliefert).

---

## Gate 9 — Blast-Radius-Gate (ADR-087)

**Auslöser:** Push berührt `src/drift/**`, `docs/decisions/**`, `POLICY.md` oder `.github/skills/**`.

**Schritte:**
1. Hook ermittelt den Diff zwischen Remote- und Local-SHA.
2. `scripts/check_blast_radius_gate.py` sucht einen gespeicherten Report unter `blast_reports/*_<short_sha>.json`.
   - Fehlt er und `DRIFT_BLAST_LIVE=1` ist **nicht** gesetzt → Gate blockiert mit Hinweis auf `python -m drift.blast_radius --persist`.
   - Ist `DRIFT_BLAST_LIVE=1` gesetzt, erzeugt das Gate den Report live und persistiert ihn.
3. Schema-/Ancestry-Check: `trigger.head_sha` im Report muss mit HEAD übereinstimmen.
4. Enthält der Report Impacts mit `requires_maintainer_ack=true` (nur bei `criticality: critical`), ist eine Ack-Datei `blast_reports/acks/<short_sha>.yaml` Pflicht.
5. `degraded=True` erzeugt Warnings, blockiert aber nicht.

**Artefakte:**
- Reports unter `blast_reports/<yyyymmdd_hhmmss>_<short_sha>.json` (deterministisch, schema_v=1).
- Ack-Dateien unter `blast_reports/acks/<short_sha>.yaml` — **nur Maintainer** dürfen diese schreiben.
- ADR-Frontmatter-Validator: `python scripts/validate_adr_frontmatter.py` (lokal aufrufbar).

**Bypass:**
- `DRIFT_SKIP_BLAST_GATE=1` überspringt das Gate mit Warning (Notfall).
- `DRIFT_BLAST_LIVE=1` erlaubt Live-Generierung statt Blockade bei fehlendem Report.

**Agent-Regel:** Der Agent berechnet Reports (via MCP-Tool `blast_radius` oder Script), darf aber **niemals** Ack-Dateien schreiben. Kritische Invalidierungen müssen an den Maintainer eskaliert werden.

---

## Bypass-Übersicht (Notfall)

```bash
# Einzelne Gates überspringen:
DRIFT_SKIP_CHANGELOG=1 git push
DRIFT_SKIP_VERSION_BUMP=1 git push
DRIFT_SKIP_LOCKFILE=1 git push
DRIFT_SKIP_DOCSTRING=1 git push
DRIFT_SKIP_RISK_AUDIT=1 git push
DRIFT_SKIP_BLAST_GATE=1 git push   # Gate 9 — Blast-Radius
DRIFT_BLAST_LIVE=1 git push        # Gate 9 — Live-Report statt Blockade

# Kombinierbar:
DRIFT_SKIP_RISK_AUDIT=1 DRIFT_SKIP_CHANGELOG=1 git push

# ALLE Gates überspringen (äußerster Notfall):
DRIFT_SKIP_HOOKS=1 git push
```

> **CI-Checks (Gate 8) lassen sich nicht per Env-Variable überspringen.**
> Sie können nur bestanden werden, nicht umgangen.

---

## Agent-Workflow vor jedem Push

```
1. git diff --name-only origin/main HEAD   # Welche Dateien sind geändert?
2. Tabelle oben prüfen → Welche Gates greifen?
3. Alle fehlenden Artefakte erzeugen/aktualisieren (Audit, Changelog, STUDY.md etc.)
4. make check  — auf Windows: .\scripts\check.ps1
5. git push
```

> **Wichtig für Agenten auf Windows:** Niemals `make` direkt in PowerShell aufrufen — es ist nicht verfügbar.
> Stets `.\.scripts\check.ps1 <target>` verwenden. Der SHA-Cache-Mechanismus funktioniert identisch:
> nach `check.ps1` wird der HEAD-SHA gecacht und der Pre-Push-Hook überspringt die teuren CI-Checks.

**Keine Ausrede "ich dachte der Hook wäre nicht installiert":**
Der Hook liegt in `.githooks/pre-push` und ist via `git config core.hooksPath .githooks` dauerhaft aktiviert.
