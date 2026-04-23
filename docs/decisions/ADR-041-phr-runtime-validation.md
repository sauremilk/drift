---
id: ADR-041
status: proposed
date: 2026-04-11
type: signal-design
signal_id: PHR
supersedes:
---

# ADR-041: Signal Design — PHR Runtime Import Attribute Validation

## Problemklasse

ADR-040 prüft, ob ein Third-Party-Paket **installiert** ist (`find_spec`).
Es erkennt aber nicht, wenn ein AI-Generator einen **existierenden** Paketnamen
mit einem **nicht-existierenden** Attribut kombiniert, z.B.:
- `from requests import parallel_get` (Modul da, Funktion halluziniert)
- `from os import secure_delete` (Stdlib da, Funktion existiert nicht)
- `from pandas import AutoML` (Paket da, Klasse halluziniert)

Dies ist ein häufiges AI-Halluzinationsmuster: das Paket wird korrekt referenziert,
aber die spezifische Funktion/Klasse ist erfunden.

Referenz: Policy §4.2 — Signalpräzision für strukturelle Kohärenz.

## Heuristik

```
Voraussetzung: config.thresholds.phr_runtime_validation == True (opt-in)

Für jeden `from X import Y` Node im AST:
  1. Skip wenn X ∈ project_modules (intern, bereits durch PHR-Basis geprüft)
  2. Skip wenn Import in try/except ImportError Block
  3. Skip wenn Import in TYPE_CHECKING Block
  4. Skip wenn Y == "*" (Star-Import)
  5. Prüfe: importlib.util.find_spec(X.split('.')[0]) is not None? (installiert?)
     → Wenn None: bereits durch ADR-040 abgedeckt, überspringen
  6. Importiere X via import_module(X) mit Thread-Timeout (5s)
  7. Für jeden importierten Namen Y: hasattr(mod, Y)?
     → Wenn False: Phantom-Attribut gefunden
```

## Sicherheits-Constraints (KRITISCH)

| Constraint | Umsetzung |
|---|---|
| Kein `exec()`, kein `eval()` | Nur `importlib.import_module()` + `hasattr()` |
| Opt-in | `thresholds.phr_runtime_validation: bool = False` (Default aus) |
| Timeout | `threading.Thread(daemon=True)` mit 5s Join-Timeout pro Modul |
| Keine Netzwerk-Calls | import_module lädt nur lokale Pakete; Timeout fängt Hänger |
| Idempotent | Bereits importierte Module (in `sys.modules`) nutzen Fast Path |

**Trust Boundary**: drift-Analyseprozess → Third-Party-Paket-Code via `import_module()`.
Dies ist eine neue Trust Boundary, die eine STRIDE-Analyse erfordert.

## Scope

`cross_file` — unverändert. Nutzt denselben `project_modules`-Kontext wie ADR-040.

## Erwartete FP-Klassen

| FP-Klasse | Mitigation | Restrisiko |
|---|---|---|
| Packages mit `__getattr__` in `__init__.py` (lazy loading) | `hasattr()` triggert `__getattr__` → True → kein FP | Gering |
| Packages mit dynamisch generierten Attributen | `hasattr()` erkennt sie zur Laufzeit → kein FP | Gering |
| Version-Mismatch: Attribut in neuerer/älterer Version | metadata `confidence: runtime_verified_env_dependent` | Mittel |

Akzeptanzschwelle: P ≥ 0.95 auf erweitertem Fixture-Set.

## Erwartete FN-Klassen

| FN-Klasse | Begründung |
|---|---|
| Import-Timeout (Paket-Init hängt >5s) | Timeout → Skip → kein Finding |
| Import-Exception (kaputter Paketcode) | Exception → Skip → kein Finding |
| Attribut nur zur Laufzeit verfügbar (conditional auf OS/Platform) | hasattr zum Analyse-Zeitpunkt kann abweichen |

## Fixture-Plan

| Fixture | Art | Beschreibung |
|---|---|---|
| `phr_runtime_missing_attr_tp` | TP | `from os import nonexistent_func` → os da, Attribut nicht |
| `phr_runtime_valid_attr_tn` | TN (Confounder) | `from os.path import join` → existiert |
| `phr_runtime_guarded_tn` | TN (Confounder) | `try: from os import nonexistent except ImportError:` → guarded |

## FMEA-Vorab-Eintrag

| Failure Mode | Severity | Occurrence | Detection | RPN |
|---|---|---|---|---|
| FP: Attribut existiert nur in bestimmter Paket-Version | 4 | 3 | 5 | 60 |
| FP: import_module Timeout → spätere Analyse korrumpiert | 3 | 1 | 3 | 9 |
| FN: import_module Exception → Skip → missed finding | 3 | 2 | 6 | 36 |
| Security: malicious __init__.py ausgeführt | 6 | 1 | 4 | 24 |

## Validierungskriterium

P ≥ 0.95, R ≥ 0.90 auf erweitertem PHR-Fixture-Set (jetzt 25+ Fixtures).
Keine Regression bei existierenden 22 PHR-Fixtures.
Alle Runtime-Checks nur bei explizitem opt-in via `phr_runtime_validation: true`.
