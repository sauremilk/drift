---
name: "Release Drift Analyzer"
description: "Release-Workflow: Code validieren, Version berechnen, Changelog aktualisieren, committen, taggen und via GitHub Actions auf PyPI publizieren. Verwende nach erfolgreichen Codeänderungen an src/drift/."
---

# Release Drift Analyzer

Du unterstützt beim Erstellen eines neuen Drift-Analyzer-Releases. Deine Aufgabe: Code validieren, nächste Version per Semantic Versioning bestimmen, Changelog aktualisieren und auf GitHub + PyPI publizieren.

> **Pflicht:** Vor Ausführung dieses Prompts das Drift Policy Gate durchlaufen
> (siehe `.github/prompts/_partials/konventionen.md` und `.github/instructions/drift-policy.instructions.md`).

## Relevante Referenzen

- **Skill:** `.github/skills/drift-release/SKILL.md` (vollständiger Release-Workflow)
- **Instructions:** `.github/instructions/drift-release-automation.instructions.md`, `.github/instructions/drift-release-mandatory.instructions.md`
- **Bewertungssystem:** `.github/prompts/_partials/bewertungs-taxonomie.md`
- **Issue-Filing:** `.github/prompts/_partials/issue-filing.md`
- **PSR-Config:** `pyproject.toml` → `[tool.semantic_release]`
- **CI-Workflow:** `.github/workflows/release.yml`

## Arbeitsmodus

- Verifiziere jede Release-Annahme explizit, bevor du den nächsten irreversiblen Schritt einleitest.
- Trenne Repository-Fakten, Git-State und abgeleitete Release-Entscheidungen klar.
- Bevorzuge kurze Operator-Checklisten statt langer Prosa, sobald eine Entscheidung gefallen ist.
- Benenne den exakten Fehlerpunkt und die kleinste sichere Recovery-Aktion, wenn Release-Schritte scheitern.
- Kollabiere keine Unsicherheit über Tags, Versionen oder Publish-State in optimistische Prosa.

## CI-Primat

> **Releases werden vollständig automatisch durch python-semantic-release (PSR) in CI verwaltet.**
> Die CI-Pipeline `.github/workflows/release.yml` läuft bei jedem Push auf `main`.
> Agenten müssen **keinen manuellen Release-Befehl** ausführen.

### Was der Agent tut

1. **Conventional Commits verwenden** — PSR leitet die Versionierung ab:
   - `feat: ...` → MINOR (0.**x**.0)
   - `fix: ...` → PATCH (0.0.**x**)
   - `BREAKING CHANGE:` / `BREAKING: ...` → MAJOR (**x**.0.0)
2. **Tests lokal ausführen** vor dem Commit
3. **Committen und pushen** — PSR übernimmt alles Weitere

### Was PSR automatisch macht (in CI)

1. Analysiert Commits seit letztem Tag
2. Berechnet nächste Version (SemVer, Precedence: BREAKING > feat > fix)
3. Aktualisiert `pyproject.toml` + `CHANGELOG.md`
4. Erstellt Release-Commit + Git-Tag
5. Erstellt GitHub Release
6. Baut + publiziert auf PyPI

### Lokaler Fallback (nur bei CI-Ausfall)

```bash
python scripts/release_automation.py --full-release
```

## Schritt-für-Schritt-Workflow

### 1. Code-Qualität prüfen

```bash
make test-fast
```

- Bei Testfailures: **STOPP** — nicht mit dem Release fortfahren.

### 2. Nächste Version berechnen

```bash
python scripts/release_automation.py --calc-version
```

- Script liest aktuelle Commits
- Bestimmt MAJOR.MINOR.PATCH-Bump
- Zeigt berechnete Version (z.B. v0.11.0)

### 3. Prüfen und bestätigen

Vor dem Fortfahren sicherstellen:
- Berechnete Version sieht korrekt aus
- Letzter Git-Tag stimmt mit erwarteter Vorversion überein
- Aktuelle Commits ergeben Sinn für diesen Bump
- Keine uncommitted Changes vorhanden

### 4. Vollständiges Release ausführen

```bash
python scripts/release_automation.py --full-release
```

### 5. Auf GitHub & PyPI verifizieren

- GitHub Releases prüfen — neuer Tag sollte sichtbar sein
- PyPI drift-analyzer prüfen — neue Version sollte verfügbar sein
- CI-Logs prüfen bei Verzögerung (statt feste Wartezeit)

## Troubleshooting

| Problem | Lösung |
|---------|--------|
| Tests schlagen fehl | Fehler im Code zuerst beheben, nicht mit Release fortfahren |
| Version-Berechnung falsch | Prüfe, ob aktuelle Commits korrekte `feat:`/`fix:`/`BREAKING:`-Prefixe nutzen |
| Tag existiert bereits | Patch-Version inkrementieren (z.B. v0.11.0 → v0.11.1) |
| Push schlägt fehl | Schreibrechte auf main-Branch sicherstellen |
| PyPI-Publish schlägt fehl | GitHub-Release wurde erstellt — PyPI wird beim nächsten Workflow-Trigger wiederholt |

## Rollback bei partieller Failure

| Situation | Recovery |
|-----------|---------|
| Git-Tag erstellt, aber PyPI-Publish fehlgeschlagen | CI-Workflow manuell re-triggern via `workflow_dispatch` |
| Release-Commit erstellt, aber Push fehlgeschlagen | `git push origin main --tags` manuell wiederholen |
| Falsche Version veröffentlicht | Neuen Patch-Release mit Korrektur erstellen (PyPI-Versionen können nicht gelöscht werden) |

## Wichtige Hinweise

- PyPI-Token ist in GitHub Actions vorkonfiguriert (Environment `pypi`, Secret `PYPI_RELEASE`)
- Changelog wird automatisch von PSR aus Commit-History generiert
- Git-Tags lösen automatische GitHub-Releases aus
- `PYTHONUTF8=1` ist im CI-Workflow gesetzt (verhindert UTF-8-Encoding-Probleme auf Windows)

## Wann releasen

**Sofort** nach:
- Signifikantem Feature (`feat:`-Commit)
- Wichtigem Bugfix (`fix:`-Commit)
- Breaking Change (`BREAKING:`-Commit)
- Alle Tests bestehen
- Dokumentation aktualisiert

**Nicht releasen** wenn:
- Tests fehlschlagen
- Code ist unvollständig oder in Entwicklung
- Keine sinnvollen Änderungen seit letztem Release

## GitHub-Issue-Erstellung

Am Ende des Workflows GitHub-Issues erstellen gemäß `.github/prompts/_partials/issue-filing.md`.

**Prompt-Kürzel für Titel:** `release`

### Issues erstellen für

- Release-Automations-Failures durch Repository-Scripts oder Workflow-Logik
- Fehlerhafte Versionsberechnung
- Changelog-Generierungs-Defekte
- Irreführende oder unvollständige Tag/Push/Publish-Anleitung
- Wiederkehrende Release-Blocker

### Keine Issues erstellen für

- Einmalige Credential-Probleme ohne Repository-seitigen Fix
- Vorübergehende GitHub-/PyPI-Ausfälle (sofern Workflow-Guidance ausreichend)
- Duplikate bereits existierender Issues
