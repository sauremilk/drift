---
name: drift-dependency-update
description: "Dependency-Update-Workflow für das Drift-Repo. Verwenden bei: uv.lock aktualisieren, pyproject.toml Abhängigkeit hinzufügen/upgraden/entfernen, Lockfile synchronisieren, Typecheck und Tests gegen neue Version, Commit mit korrektem chore:-Typ. Keywords: uv lock, uv sync, uv add, dependency, pyproject.toml, lockfile, uv.lock, upgrade, security patch, chore commit."
argument-hint: "Name und Version der zu ändernden Abhängigkeit — z.B. 'pydantic auf >=2.7 upgraden' oder 'tree-sitter-typescript neu hinzufügen'"
---

# Drift Dependency Update

Workflow für alle Änderungen an `pyproject.toml`-Abhängigkeiten im Drift-Repo.
Deckt: neue Abhängigkeit hinzufügen, bestehende upgraden/einschränken, Abhängigkeit entfernen.

**KRITISCH:** `pyproject.toml` und `uv.lock` sind **unlösbar gekoppelt**. Beide Dateien müssen im selben Commit landen. Das Pre-Push-Gate 5 blockiert jeden Push, bei dem `pyproject.toml` geändert, `uv.lock` aber nicht committet wurde.

---

## Wann verwenden

- `pyproject.toml`-Abhängigkeit soll geändert, hinzugefügt oder entfernt werden
- `uv.lock` soll mit aktuellen Constraints synchronisiert werden
- Security-Patch für eine direkte oder transitive Abhängigkeit
- CI schlägt fehl mit „Lockfile not synchronized" oder ähnlichem

---

## Technischer Kontext

**Dependency-Gruppen in `[project.optional-dependencies]`:**

| Gruppe | Zweck |
|--------|-------|
| `typescript` | `tree-sitter`, `tree-sitter-typescript` |
| `embeddings` | `sentence-transformers`, `faiss-cpu`, `numpy` |
| `markdown` | `mistune` |
| `mcp` | `mcp[cli]` |
| `watch` | `watchfiles` |
| `dev` | Alle Test- / Lint- / Release-Werkzeuge |
| `all` | Metagruppe, die alle einschließt |

**Lokale Venv-Aktivierung (Windows):**
```powershell
.\.venv\Scripts\Activate.ps1
```

**Wichtige uv-Befehle:**

| Aufgabe | Befehl |
|---------|--------|
| Neue Abhängigkeit hinzufügen (schreibt auch pyproject.toml) | `uv add <paket>` |
| Abhängigkeit in optionale Gruppe hinzufügen | `uv add --optional <gruppe> <paket>` |
| Abhängigkeit entfernen | `uv remove <paket>` |
| Lockfile neu erzeugen (nach manuellem pyproject.toml-Edit) | `uv lock` |
| Einzelnes Paket im Lock upgraden | `uv lock --upgrade-package <paket>` |
| Alle Transitivs upgraden (innerhalb Constraints) | `uv lock --upgrade` |
| Devenv installieren/aktualisieren | `uv sync --all-extras` |

---

## Schritt-für-Schritt-Workflow

### Schritt 0 — Policy Gate

```
### Drift Policy Gate
- Trivialtask: JA
- Zulässig: JA → rein mechanisch, ohne Verhaltens-, Policy-, Architektur- oder Signaleffekt
```

> Dependency-Updates sind `chore:`-Commits. Sie lösen kein feat:/fix:-Gate aus und erfordern kein CHANGELOG-Update. Ausnahme: Ein Upgrade behebt einen produktiven Bug → dann `fix:`.

### Schritt 1 — Abhängigkeit klassifizieren

Vor der Änderung klären:

- **Nur `pyproject.toml` (Versions-Constraint ändern):** direkt editieren → dann `uv lock`.
- **Neue Abhängigkeit hinzufügen:** `uv add <paket>` bevorzugen — schreibt pyproject.toml **und** uv.lock atomar.
- **Security-Patch für transitive Abhängigkeit (nicht in pyproject.toml):** `uv lock --upgrade-package <paket>` + kein pyproject.toml-Edit nötig.
- **Abhängigkeit entfernen:** `uv remove <paket>`.

### Schritt 2 — Lockfile synchronisieren

Nach **jedem** manuellen Edit von `pyproject.toml`:

```powershell
uv lock
```

Prüfen, ob keine Konflikte ausgegeben werden. Bei Konflikten Constraint in `pyproject.toml` anpassen und erneut ausführen.

### Schritt 3 — Devenv aktualisieren

```powershell
uv sync --all-extras
```

Stellt sicher, dass das lokale Venv die neuen Versionen enthält, bevor Tests laufen.

### Schritt 4 — Typecheck

```powershell
.\.venv\Scripts\python.exe -m mypy src/drift --ignore-missing-imports
```

Schlägt der Typecheck durch inkompatible API-Änderungen fehl, Constraint in `pyproject.toml` einschränken oder Typ-Fehler beheben.

### Schritt 5 — Quick-Tests

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ --ignore=tests/test_smoke_real_repos.py -m "not slow" -q -n auto --dist=loadscope
```

Bei Testfehlern durch API-Änderungen der aktualisierten Bibliothek:
1. Prüfen, ob es einen Workaround im Drift-Code gibt.
2. Constraint ggf. zurücksetzen (`<neue_version`).
3. Issue gegen die Bibliothek vorbereiten, falls es ein echter Bug ist.

### Schritt 6 — Beide Artefakte committen

**PFLICHT: `pyproject.toml` und `uv.lock` immer gemeinsam in einem Commit.**

```powershell
git add pyproject.toml uv.lock
git status --short   # Sicherheitscheck: keine unerwünschten Dateien
git commit -m "chore: update <paket> to <version>"
```

**Commit-Typ-Regeln:**

| Situation | Commit-Typ |
|-----------|-----------|
| Routine-Upgrade, kein Bug-Fix | `chore:` |
| Upgrade behebt produktiven Drift-Bug | `fix:` |
| Neue optionale Funktionalität ermöglicht | `feat:` |
| Breaking change in Abhängigkeit, Drift-API bricht | `BREAKING:` |

### Schritt 7 — Pre-Push-Gate-Check (vor dem Push)

Gate 4 (Version Bump) feuert, wenn `pyproject.toml` geändert wurde:

- PSR bumpt die Version nicht für `chore:`-Commits → Gate würde blockieren.
- **Lösung für `chore:`-nur-Dependency-Pushes:**

```powershell
DRIFT_SKIP_VERSION_BUMP=1 git push
```

> Bei `fix:` oder `feat:`-Commits ist kein Bypass nötig — PSR erstellt einen Version-Bump-Commit in CI.

---

## Häufige Fehler (und Korrekturen)

| Fehler | Korrekte Vorgehensweise |
|--------|------------------------|
| `pip install <paket>` anstatt `uv add` | Immer `uv add` oder `uv sync` — `pip` umgeht den Lock |
| Nur `pyproject.toml` committen, `uv.lock` vergessen | `git add pyproject.toml uv.lock` immer zusammen |
| `uv lock` vergessen nach manuellem pyproject.toml-Edit | Step 2 ist Pflicht nach jedem manuellen Edit |
| `fix:` statt `chore:` für routinemäßiges Upgrade | Nur `fix:` wenn der Upgrade einen echten Bug in drift-analyzer behebt |
| Version-Bump-Gate blockiert `chore:`-Push | `DRIFT_SKIP_VERSION_BUMP=1 git push` |
| Tests gegen alte gecachte Pakete | `uv sync --all-extras` vor Tests (Schritt 3) |

---

## Checkliste (Kurzform)

```
[ ] Art der Änderung klassifiziert (add / upgrade / remove / security-patch)
[ ] pyproject.toml bearbeitet (oder uv add/remove genutzt)
[ ] uv lock ausgeführt — keine Konflikte
[ ] uv sync --all-extras ausgeführt
[ ] mypy src/drift — sauber
[ ] pytest quick suite — grün
[ ] git add pyproject.toml uv.lock (beide!)
[ ] Commit-Typ korrekt (chore: / fix: / feat:)
[ ] DRIFT_SKIP_VERSION_BUMP=1 wenn chore:-Push
```
