---
name: drift-release
description: "Complete release workflow: Validate → Version → Changelog → Commit → Tag → Publish. Use after successful code changes to src/drift/. Single command: `python scripts/release_automation.py --full-release`"
---

# 🚀 Drift Release Skill

Never forget to release code changes to `src/drift/` again.

## Executive Summary

**ONE command does EVERYTHING:**

```bash
python scripts/release_automation.py --full-release
```

Runs tests → Calculates version → Updates files → Creates release → Publishes to PyPI.

---

## When to Use This Skill

✅ **ALWAYS use this after:**
- Feature complete (`feat: ...` commit)
- Bug fixed (`fix: ...` commit)
- Breaking change (`BREAKING: ...` commit)
- All tests pass
- Code committed + pushed to main

❌ **DO NOT use if:**
- Tests still failing
- Code not committed yet
- Change is pure refactor (no user impact)
- Code still incomplete

---

## The Two-Step Release Process

### Step 1: Run the Command

```bash
cd c:\Users\mickg\PWBS\drift
python scripts/release_automation.py --full-release
```

### Step 2: Wait for Output

You should see:

```
============================================================
Drift Release Automation
============================================================
▶ Running quick tests...
✓ Tests passed

▶ Next version: v0.11.0
✓ Updated pyproject.toml: version = 0.11.0
✓ Updated CHANGELOG.md with version 0.11.0

▶ Staging changes for version 0.11.0...
Creating release commit...
✓ Committed: chore: Release 0.11.0 — update version and changelog
▶ Creating git tag v0.11.0...
✓ Tagged: v0.11.0
Pushing to origin/main and tags...
✓ Pushed main and v0.11.0

✅ Release v0.11.0 complete!
   → GitHub release will be created automatically
   → PyPI publication via .github/workflows/publish.yml (triggered by tag)
```

---

## Semantic Versioning Happens Automatically

The script reads your **commit messages** and bumps the version:

```
Your commit message       Version bump       Result
─────────────────────────────────────────────────────
feat: new detector     →  MINOR (0.X.0)  →  v0.9.0
fix: false alarm       →  PATCH (0.0.X)  →  v0.8.3  
BREAKING: remove sig   →  MAJOR (X.0.0)  →  v1.0.0
```

**Priority:** BREAKING > feat > fix

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Tests fail during release | Fix code first. Release will abort automatically. Do NOT skip tests. |
| Version looks wrong | Check your recent commit messages use correct prefixes (feat:, fix:, BREAKING:) |
| Tag already exists | Manually increment patch: v0.11.0 → v0.11.1 and retry |
| Can't push | Check GitHub write access. May need credential refresh. |
| PyPI publish fails | GitHub release is created OK. PyPI will retry automatically within 24h. |

---

## What Happens Under the Hood

1. **Tests run** — aborts if any fail
2. **Git history analyzed** — from last tag to HEAD
3. **Version calculated** — based on commit message patterns
4. **Files updated:**
   - `pyproject.toml` (version field)
   - `CHANGELOG.md` (new entry from commits)
5. **Commits created:**
   - Code changes (if any)
   - Release commit (version + changelog)
6. **Git tag created** — e.g., v0.11.0
7. **Push to GitHub** — main + tag
8. **GitHub Actions triggered** (`.github/workflows/publish.yml`)
   - Builds dist package
   - Validates version consistency
   - Publishes to PyPI

---

## Important Details

- 🔐 **PyPI token:** Already configured in GitHub Actions (no manual setup needed)
- 📊 **CHANGELOG:** Auto-generated from commit history
- 🏷️ **Git tags:** Enable GitHub to create releases automatically
- ⚙️ **Workflows:** `.github/workflows/publish.yml` handles PyPI publication
- 📝 **Tagging format:** Always `vX.Y.Z` (e.g., v0.10.3)

---

## DO NOT DO THIS

❌ Forget to release after code changes  
❌ Skip tests to "speed up" the release  
❌ Manually create git tags/commits for releases  
❌ Edit version numbers outside of `pyproject.toml`  
❌ Push without running the full release workflow  

---

## Quick Reference

```bash
# Full release (recommended)
python scripts/release_automation.py --full-release

# Just calculate version
python scripts/release_automation.py --calc-version

# Just update changelog
python scripts/release_automation.py --update-changelog

# Skip tests (NOT recommended)
python scripts/release_automation.py --full-release --skip-tests
```

---

## Need Full Details?

Reference documentation: `.github/instructions/drift-release-automation.instructions.md`

For questions about releases → Check that file first.
