---
name: guard-src-drift-config
description: "Drift-generierter Guard fuer `src/drift/config`. Aktiv bei Signalen: PFS. Konfidenz: 0.62. Verwende diesen Skill wenn du Aenderungen an `src/drift/config` planst oder wiederholte Drift-Findings (PFS) fuer dieses Modul bearbeitest."
argument-hint: "Beschreibe welche Konfigurationsoption (neues Feld, neuer Loader, neues Schema-Element) hinzugefuegt wird."
---

# Guard: `src/drift/config`

`src/drift/config` enthaelt `DriftConfig` (das Datenmodell) und `_loader.py` (Laden aus YAML, Defaults, Env-Variablen). PFS entsteht wenn neue Konfigurationsoptionen nicht ueber den zentralen Loader laufen oder wenn Defaults an mehreren Stellen definiert werden.

**Konfidenz: 0.62** — PFS-Risiko real aber moderat; entsteht hauptsaechlich durch Shortcuts beim Laden neuer Optionen.

## When To Use

- Du fuegest ein neues Konfigurationsfeld zu `DriftConfig` hinzu
- Du aenderst wie `drift.yaml` oder `.drift.yaml` geladen wird
- Du fuegest Unterstuetzung fuer neue Env-Variablen hinzu
- Du aenderst Default-Werte fuer bestehende Optionen
- Drift meldet PFS fuer `src/drift/config/`

## Warum PFS hier entsteht

Konfigurations-PFS entsteht typischerweise durch:
- Defaults an zwei Stellen: einmal in `DriftConfig` (Felddefault) und einmal im Laden-Code
- Env-Variable-Handling das `_loader.py` umgeht (direktes `os.getenv()` in anderen Modulen)
- Schema in `drift.schema.json` nicht synchron mit `DriftConfig`-Feldern
- Inkonsistente Benennung: `include_patterns` vs `include_globs` vs `file_patterns`

## Core Rules

1. **`_loader.py` ist der einzige Ladepfad** — kein Modul ausserhalb von `config/` darf `drift.yaml` direkt einlesen oder `DriftConfig` manuell instanziieren. `DriftConfig.from_path()` oder `_loader.load()` ist der Weg.

2. **Defaults nur im Felddefault von `DriftConfig`** — kein Default-Wert in `_loader.py` zusaetzlich zum Felddefault. Wenn ein Feld `include: list[str] = field(default_factory=list)` hat, gibt es keinen Fallback-Wert im Loader.

3. **`drift.schema.json` synchron halten** — jede neue `DriftConfig`-Option bekommt einen Eintrag im Schema. Das Schema ist die User-Dokumentation.

4. **Env-Variablen ausschliesslich in `_loader.py`** — kein anderes Modul macht `os.getenv('DRIFT_...')`. Alle Env-Var-Aufloesung geht durch den Loader.

5. **Neue Default-Includes als bewusste Entscheidung** — die Default-Include-Globs (`**/*.py`, `**/*.pyi`) sind in `_loader.py` zentral. Neue Defaults erfordern Tests in `tests/test_config.py`.

## Review Checklist

- [ ] Neues Feld hat Felddefault in `DriftConfig`, keinen separaten Fallback in `_loader.py`
- [ ] `drift.schema.json` aktualisiert
- [ ] Keine `os.getenv()` ausserhalb von `_loader.py`
- [ ] Test in `tests/test_config.py` fuer neue Option vorhanden
- [ ] `drift nudge` zeigt `safe_to_commit: true`
- [ ] Keine neuen PFS-Findings

## References

- [src/drift/config/_loader.py](../../../src/drift/config/_loader.py) — Zentraler Konfigurations-Loader
- [drift.schema.json](../../../drift.schema.json) — YAML-Schema fuer drift.yaml
- [tests/test_config.py](../../../tests/test_config.py) — Config-Tests
