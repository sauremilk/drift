---
applyTo: "**"
description: "Pre-Push-Gate-Checkliste — Alle Bedingungen, die erfüllt sein müssen bevor ein git push ausgeführt wird. Agenten MÜSSEN diese Datei prüfen bevor sie einen Push vorbereiten."
---

# Drift Pre-Push Gates — Vollständige Checkliste für Agenten

Der Hook in `.githooks/pre-push` blockiert jeden Push, der eine der folgenden Bedingungen verletzt.
**Agenten müssen alle zutreffenden Gates erfüllen, bevor sie `git push` ausführen.**

---

## Übersicht: Welches Gate gilt bei welcher Änderung?

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
**Alle drei Bedingungen müssen gleichzeitig erfüllt sein:**

1. **Tests vorhanden:** Mindestens eine Datei unter `tests/` muss im Push enthalten sein.
2. **Empirisches Artefakt vorhanden:** Mindestens eine Datei unter `benchmark_results/` oder `audit_results/` muss im Push enthalten sein.
3. **Versioned Evidence-Datei vorhanden:** Eine Datei die auf `benchmark_results/vX.Y.Z_feature_evidence.json` matcht (oder entsprechendes Muster).
4. **STUDY.md aktualisiert:** `docs/STUDY.md` muss im Push enthalten sein (sofern die Datei existiert).

**Typische Vorgehensweise bei feat::**
```
# 1. Tests schreiben
# 2. benchmark_results/vNEU_feature_evidence.json erzeugen oder aktualisieren
# 3. docs/STUDY.md aktualisieren
# 4. Alle zusammen committen
```

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

**Auslöser:** Immer — jeder Push läuft durch alle sechs Checks.

| Schritt | Befehl | Bypass |
|---------|--------|--------|
| 1 | `python scripts/check_version.py --check-semver` | – |
| 1b | `python scripts/check_release_discipline.py` | – |
| 1c | `python scripts/check_model_consistency.py` | – |
| 1d | `python scripts/check_repo_hygiene.py --config .github/repo-guard.blocklist --root-allowlist .github/repo-root-allowlist` | – |
| 2 | `ruff check src/ tests/` | – |
| 3 | `python -m mypy src/drift` | – |
| 4 | `pytest -q --tb=short --cov --run-slow -p no:xdist --ignore=tests/test_smoke_real_repos.py` | – |
| 5 | `drift analyze --repo . --format json --exit-zero` | – |

**Diese Checks haben keinen Bypass-Mechanismus.**  
Vor jedem Push sicherstellen: `make check` lokal bestanden.

---

## Bypass-Übersicht (Notfall)

```bash
# Einzelne Gates überspringen:
DRIFT_SKIP_CHANGELOG=1 git push
DRIFT_SKIP_VERSION_BUMP=1 git push
DRIFT_SKIP_LOCKFILE=1 git push
DRIFT_SKIP_DOCSTRING=1 git push
DRIFT_SKIP_RISK_AUDIT=1 git push

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
4. make check  (oder die relevanten Teilschritte)
5. git push
```

**Keine Ausrede "ich dachte der Hook wäre nicht installiert":**  
Der Hook liegt in `.githooks/pre-push` und ist via `git config core.hooksPath .githooks` dauerhaft aktiviert.
