---
applyTo: "src/drift/**"
description: "Release-Automatisierung via python-semantic-release (PSR) in CI. Agenten verwenden Conventional Commits — CI übernimmt Version, Changelog, Tag, Release, PyPI."
---

# Drift Release Automation (python-semantic-release)

Releases werden vollständig durch `python-semantic-release` in CI verwaltet.
Workflow: `.github/workflows/release.yml` — läuft bei jedem Push auf `main`.

## Was Agenten tun müssen

1. **Conventional Commits verwenden** — PSR leitet Version aus Commit-Messages ab:
   - `feat: ...` → MINOR (0.x.0)
   - `fix: ...` → PATCH (0.0.x)
   - `BREAKING CHANGE: ...` / `BREAKING: ...` → MAJOR (x.0.0)
2. **Tests lokal ausführen** vor dem Commit:
   ```bash
   make test-fast
   ```
3. **Committen** — PSR übernimmt nach Push alles Weitere

## Was PSR automatisch macht (in CI)

1. Analysiert Commits seit letztem Tag
2. Berechnet nächste Version (SemVer)
3. Aktualisiert `pyproject.toml` + `CHANGELOG.md`
4. Erstellt Release-Commit (`chore: Release X.Y.Z`)
5. Erstellt Git Tag (`vX.Y.Z`)
6. Erstellt GitHub Release
7. Baut Wheel + Sdist → publiziert zu PyPI

## Lokaler Fallback (nur bei CI-Ausfall)

```bash
python scripts/release_automation.py --full-release
```

| Fehler | Aktion |
|--------|--------|
| Tests schlagen fehl | Fehler beheben, dann neu committen. CI startet Release nicht bei fehlenden releasable Commits. |
| PSR findet keine releasable Commits | Normal — kein feat/fix/breaking → kein Release. |
| PyPI Publikation schlägt fehl | GitHub Release existiert. PyPI kann über `publish.yml` (workflow_dispatch) nachgetriggert werden. |

## Konfiguration

- PSR-Config: `pyproject.toml` → `[tool.semantic_release]`
- CI-Workflow: `.github/workflows/release.yml`
- PyPI-Secret: `PYPI_RELEASE` im GitHub Environment `pypi`

---

**Wichtig:** Agenten müssen KEINEN manuellen Release-Befehl mehr ausführen. Conventional Commits + Push auf main genügt.
