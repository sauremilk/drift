---
id: ADR-040
status: proposed
date: 2026-04-10
type: signal-design
signal_id: PHR
supersedes:
---

# ADR-040: Signal Design — Phantom Reference Import Resolver (PHR)

## Problemklasse

PHR erkennt aktuell nur projekt-interne Phantom-Referenzen: unbekannte Funktionsnamen
und `from <project_module> import <name>` mit fehlendem Export. Third-Party-Imports
wie `import nonexistent_package` oder `from requests import hallucinated_func` werden
**nicht** geprüft. AI-Code-Generatoren halluzinieren aber regelmäßig Third-Party-Pakete,
die nicht installiert oder gar nicht existent sind.

Referenz: Policy §4.2 — Signalpräzision für strukturelle Kohärenz.

## Heuristik

```
Für jeden Import-Node (import X / from X import Y) im AST:
  1. Berechne root_module = X.split('.')[0]
  2. Skip wenn root_module ∈ sys.stdlib_module_names (Stdlib)
  3. Skip wenn root_module ∈ project_modules (bereits intern geprüft)
  4. Skip wenn Import in try/except ImportError Block (conditional import)
  5. Skip wenn Import in TYPE_CHECKING Block
  6. Prüfe: importlib.util.find_spec(root_module) is None?
     → Wenn None: Third-Party-Phantom gefunden (Paket nicht installiert)
  7. Für `from X import Y`: wenn find_spec(X) erfolgreich,
     prüfe ob X.Y als Submodul existiert via find_spec(X.Y)
     → Bei None: Third-Party-Phantom (Submodul halluziniert)
```

Sicherheit: `find_spec()` führt **keinen Code aus** — nur Pfad-Traversal auf `sys.path`.

## Scope

`cross_file` — unverändert. Import-Validierung nutzt Projekt-Kontext (project_modules
für die Skip-Logik) und globalen Python-Installationskontext (sys.path).

## Erwartete FP-Klassen

| FP-Klasse | Mitigation | Restrisiko |
|---|---|---|
| Paket in anderer venv installiert (CI vs. lokal) | Hinweis in Finding-metadata: `"confidence": "env_dependent"` | Mittel |
| Conda/System-Python Mismatch | Gleiche Mitigation | Mittel |
| Namespace-Packages ohne `__init__.py` | `find_spec` erkennt PEP 420 namespace packages | Gering |
| Optional Dependencies hinter `try/except` | AST-Guard: try/except ImportError wird geskippt | Sehr gering |

Akzeptanzschwelle: P ≥ 0.95 auf erweitertem Fixture-Set.

## Erwartete FN-Klassen

| FN-Klasse | Begründung |
|---|---|
| Dynamische Imports via `importlib.import_module(var)` | Nicht statisch auflösbar |
| String-basierte Plugin-Loader | Nicht statisch auflösbar |
| Paket installiert aber falsche Version (fehlende Klasse) | find_spec prüft nur Existenz, nicht API-Oberfläche |

## Fixture-Plan

| Fixture | Art | Beschreibung |
|---|---|---|
| `phr_missing_package_tp` | TP | `import nonexistent_ai_helper` → Paket nicht installiert |
| `phr_wrong_submodule_tp` | TP | `from os import nonexistent_util` → Submodul halluziniert |
| `phr_optional_dep_tn` | TN (Confounder) | `try: import optional_lib except ImportError: pass` |
| `phr_stdlib_import_tn` | TN (Confounder) | `import json, os, sys` → Stdlib immer verfügbar |
| `phr_type_checking_import_tn` | TN (Boundary) | Third-party import inside TYPE_CHECKING |

## FMEA-Vorab-Eintrag

| Failure Mode | Severity | Occurrence | Detection | RPN |
|---|---|---|---|---|
| FP: Paket in CI installiert, lokal nicht → false finding | 4 | 3 | 6 | 72 |
| FP: Conditional import nicht erkannt → false finding | 5 | 2 | 3 | 30 |
| FN: Dynamischer Import nicht erkannt → missed finding | 3 | 4 | 8 | 96 |
| FN: Paket installiert aber API geändert → missed finding | 4 | 3 | 8 | 96 |

## Validierungskriterium

PHR Precision ≥ 0.95 und Recall ≥ 0.90 auf erweitertem Fixture-Set (inkl. Third-Party-Fixtures).
Keine neuen PHR-FP in Drift-Selbstanalyse (`drift analyze --repo .`).
