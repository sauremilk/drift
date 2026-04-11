---
applyTo: "src/drift/**"
description: "Releases are automated via python-semantic-release in CI. Agents must use conventional commits (feat:/fix:/BREAKING:) — no manual release command needed."
---

# Release Automation

> **Vollständige Dokumentation:** siehe `drift-release-automation.instructions.md` (gleicher Scope).

**Kurzregel:** Conventional Commits (`feat:`, `fix:`, `BREAKING:`) verwenden — CI übernimmt Version, Tag, Release, PyPI.
Kein manueller Release-Befehl nötig. Fallback: `python scripts/release_automation.py --full-release`.

## See Also

- Release Workflow: `.github/workflows/release.yml`
- PSR Configuration: `pyproject.toml` → `[tool.semantic_release]`
- Detailed Skill: `.github/skills/drift-release/SKILL.md`
