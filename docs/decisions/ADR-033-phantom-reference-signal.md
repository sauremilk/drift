---
id: ADR-033
status: proposed
date: 2026-04-09
type: signal-design
signal_id: PHR
supersedes:
---

# ADR-033: Signal Design — Phantom Reference (PHR)

## Problemklasse

KI-Code-Generatoren (Copilot, Cursor, Claude) halluzinieren regelmäßig
Aufrufe an Funktionen, Klassen oder Dekoratoren, die im aktuellen Projekt
weder definiert noch importiert sind. Diese "Phantom-Referenzen" führen
zu NameError/ImportError zur Laufzeit und sind ein KI-spezifisches
Kohärenzproblem, das von bestehenden Drift-Signalen nicht abgedeckt wird.

Referenz: Policy §4.2 — Erkennung struktureller Erosion durch inkonsistente
Code-Generierung.

## Heuristik

```
Für jede Python-Datei im Scope:
  1. Sammle alle Namen, die im AST als Call-Target oder Attribute
     verwendet werden (ast.Name in ast.Call, ast.Attribute)
  2. Baue die lokale Symboltabelle:
     a) Funktionen/Klassen definiert in dieser Datei
     b) Importierte Namen (from X import Y → Y; import X → X)
     c) Builtins (builtins.__dict__)
     d) Globale Zuweisungen (ast.Assign / ast.AnnAssign targets)
     e) Comprehension-Variablen, for-Targets, with-as, except-as
  3. Sammle codebase-weite Exporte (alle FunctionInfo/ClassInfo names
     aus allen ParseResults) → "project symbol table"
  4. Für jeden verwendeten Namen: prüfe ob er auflösbar ist via
     lokale Symboltabelle ODER (importiert UND im Projekt/Stdlib definiert)
  5. Nicht auflösbare Namen = Phantom-Referenzen
```

FP-Suppressions:
- `__getattr__` auf Klasse/Modul → dynamischer Namespace
- Star-Imports (`from X import *`) → konservativ: Datei überspringen
- `try: import X except ImportError` → Guard erkannt, Name gilt als bedingt verfügbar
- Dekoratoren aus Frameworks (pytest.fixture, app.route) → Allowlist
- `TYPE_CHECKING`-guarded Imports → nur für Typ-Annotationen relevant
- Plugin/Entry-Point-Systeme → konfigurierbare Excludes

## Scope

`cross_file` — benötigt die gesamte Codebase-Symboltabelle, um zu prüfen
ob importierte Module die referenzierten Namen tatsächlich exportieren.

## Erwartete FP-Klassen

| FP-Klasse | Mitigierung |
|---|---|
| Dynamische Attribute via `__getattr__` | Klassen mit `__getattr__` als dynamisch markieren |
| Star-Imports | Datei mit `from X import *` überspringen |
| Plugin-Systeme (stevedore, entry_points) | Konfigurierbare Excludes |
| Monkey-Patching | Nicht mitigierbar (akzeptiertes FN-Risiko) |
| exec/eval Code-Generierung | Heuristik: Dateien mit exec()/eval() als unreliable markieren |

## Erwartete FN-Klassen

| FN-Klasse | Begründung |
|---|---|
| Dynamisch generierte Namen (exec, eval) | Nicht statisch analysierbar |
| Referenzen in String-Templates | Außerhalb AST-Scope |
| Referenzen über getattr() | Dynamischer Zugriff |

## Fixture-Plan

| Fixture | Typ | Beschreibung |
|---|---|---|
| `phr_tp` | positive | Funktion ruft `sanitize_input()` auf, die nirgends definiert ist |
| `phr_tn` | negative | Alle Referenzen korrekt importiert/definiert |
| `phr_star_import_tn` | confounder | Star-Import-Datei → kein Finding erwartet |
| `phr_dynamic_tn` | confounder | Klasse mit `__getattr__` → kein Finding |
| `phr_cross_file_tp` | positive | Import von Modul B existiert, aber referenzierte Funktion fehlt in B |
| `phr_builtin_tn` | negative | Builtins (len, print, dict) korrekt erkannt |

## FMEA-Vorab-Eintrag

| Failure Mode | Severity | Occurrence | Detection | RPN |
|---|---|---|---|---|
| FP: Star-Import übersehen → false phantom | 3 | 4 | 8 | 96 |
| FP: Framework-Dekorator als phantom | 3 | 3 | 3 | 27 |
| FN: Monkey-patched Name nicht erkannt | 2 | 3 | 9 | 54 |
| FN: exec()-generierter Name | 2 | 2 | 9 | 36 |

## Validierungskriterium

- Ground-Truth-Fixtures: P ≥ 0.85, R ≥ 0.80
- Selbstanalyse (drift-Repo): 0 false positives
- Externe Validierung: ≥ 3 Oracle-Repos ohne neue FPs
- Signal startet als report-only (weight=0.0) bis externe Validierung abgeschlossen

```bash
pytest tests/test_precision_recall.py -v
pytest tests/test_phantom_reference.py -v
drift analyze --repo . --format json --exit-zero
```

Lernzyklus-Ergebnis: `bestaetigt` wenn P ≥ 0.85 auf externem Corpus,
`zurueckgestellt` wenn P < 0.85.
