---
applyTo: "src/drift/**"
description: "Release-Automatisierung für Drift-Analyzer: Nach Code-Änderungen automatisch Tests, Versionierung, Versionshistorie, Commit, GitHub Release und PyPI-Publikation durchführen. Verwendet Semantic Versioning basierend auf Commit-Nachricht (fix→patch, feat→minor, BREAKING→major)."
---

# Drift Release Automation

Wenn du Code-Änderungen an `src/drift/` durchführst, führe nach erfolgreichem Test automatisch den Complete-Release-Workflow aus:

## Workflow nach jeder Code-Änderung

1. **Tests validieren** (Quick-Test, ohne `--run-slow`)
   ```bash
   python -m pytest tests/ --tb=short --ignore=tests/test_smoke.py -q --maxfail=1
   ```
   - Verhindert defekten Code in Releases
   - Bei Fehler: ABBRUCH, Agent muss Fehler beheben

2. **Versionsnummer berechnen** (Semantic Versioning)
   - Lese alle Commits seit letzter v* Tag
   - Analysiere Commit-Nachrichtsköpfe:
     - `fix: ...` → PATCH erhöhen
     - `feat: ...` → MINOR erhöhen  
     - `BREAKING: ...` oder `BREAKING CHANGE` → MAJOR erhöhen
   - Priorität: MAJOR > MINOR > PATCH
   - Standard: PATCH (wenn keine der Keywords vorhanden)

3. **CHANGELOG.md aktualisieren**
   - Neue Sektion am Top mit neuer Version
   - Format:
     ```markdown
     ## [vX.Y.Z] — YYYY-MM-DD
     
     ### Added
     - [feat] ...
     
     ### Fixed
     - [fix] ...
     
     ### Changed
     - [change] ...
     ```
   - Im Abschnitt "Commits seit letztem Release": nutze urspr. Commit-Nachrichten

4. **Committen** (zwei Commits empfohlen)
   ```bash
   git add src/drift/ tests/  # Falls Tests aktualisiert wurden
   git commit -m "feat/fix/change: [deine ursprüngliche Message]"
   
   git add CHANGELOG.md pyproject.toml  # Version + History
   git commit -m "chore: Release vX.Y.Z — update version and changelog"
   ```

5. **Git Tag erstellen + pushen**
   ```bash
   git tag -a vX.Y.Z -m "Release vX.Y.Z"
   git push origin master --tags
   ```
   - Dies triggert `.github/workflows/publish.yml` automatisch
   - Workflow: validiert Tag ↔ pyproject.toml → baut Dist → published zu PyPI

6. **Warte auf GitHub Actions**
   - Check GitHub Release wurde erstellt
   - Check PyPI Publikation erfolgreich (erfolgt ~1-2 min nach Release)

## Fehlerfälle

| Fehler | Aktion |
|--------|--------|
| Quick-Test schlägt fehl | Beende Workflow. Agent muss Fehler beheben, dann neu starten. |
| Tag bereits vorhanden | Inkrementiere Patch um 1, neuer Tag z.B. v0.10.3 → v0.10.4, retry. |
| PyPI Publikation schlägt fehl | Release wird trotzdem erstellt (sichtbar auf GitHub), manuell mit `twine` wiederholen oder `Publish` Workflow re-triggern. |

## Umgebungsvariablen (bereits vom User gesetzt)

```bash
# Aus Terminal für lokale Fallbacks
$env:TWINE_USERNAME = "__token__"
$env:TWINE_PASSWORD = "pypi-..."  # Der PyPI Token
```

Diese werden von GitHub Actions falls lokal nötig, aber automatisch via GitHub Secret `PYPI_API_TOKEN` in Workflows gelöst.

## Befehle als Schnellreferenz

```bash
# 1. Quick-Test
python -m pytest tests/ --ignore=tests/test_smoke.py -q --maxfail=1

# 2. Version + CHANGELOG
python scripts/release_automation.py --calc-version --update-changelog

# 3. Commit + Tag + Push
git add .
git commit -m "chore: Release vX.Y.Z — update version and changelog"
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin master --tags
```

---

**Wichtig:** Diese Instruktion ist bindend für alle Coding-Agenten, die `src/drift/**` Dateien ändern. Der Workflow muss nach jedem erfolgreichen Test durchgeführt werden, bevor der Agent die Aufgabe als abgeschlossen markiert.
