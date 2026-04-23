---
id: ADR-068
status: proposed
date: 2025-07-24
supersedes:
---

# ADR-068: Package-Dekomposition von models, config und errors

## Kontext

Die drei Module `src/drift/models.py` (614 Zeilen, 94 Importeure), `src/drift/config.py` (902 Zeilen, 85 Importeure) und `src/drift/errors.py` (370 Zeilen, 20+ Importeure) waren monolithische God-Module in der Zone of Pain (hohe Afferent Coupling + hohe Instabilität).

Drift's eigene Selbstanalyse identifizierte diese Module als AVS-Findings:
- models.py: Ca=94, blast radius hoch
- config.py: Ca=85, blast radius hoch
- errors.py: Ca=20+, Kopplung zu Exception-Hierarchie + Error-Registry

Die Module wurden in der Roadmap Phase 1 als technische Schuld erkannt.

## Entscheidung

Jedes Modul wird in ein gleichnamiges Package mit internen Sub-Modulen aufgeteilt.
Ein `__init__.py`-Shim re-exportiert alle bisherigen Public Symbols, sodass bestehende `from drift.X import Y`-Imports ohne Änderung weiterarbeiten.

### models.py → models/

| Sub-Modul | Inhalt |
|-----------|--------|
| `_enums.py` | Severity, FindingStatus, SignalType, RegressionPattern u.a. |
| `_parse.py` | FileInfo, FunctionInfo, ClassInfo, ImportInfo, ParseResult |
| `_git.py` | CommitInfo, FileHistory, BlameLine, Attribution |
| `_findings.py` | Finding, AnalyzerWarning, ModuleScore, RepoAnalysis |
| `_context.py` | NegativeContext |
| `_agent.py` | AgentTask |
| `__init__.py` | Kompatibilitäts-Shim mit expliziten Re-Exports |

### config.py → config/

| Sub-Modul | Inhalt |
|-----------|--------|
| `_schema.py` | 19 Pydantic BaseModel-Klassen (LayerBoundary bis AttributionConfig) |
| `_loader.py` | DriftConfig, _default_includes, build_config_json_schema |
| `_signals.py` | SIGNAL_ABBREV, resolve_signal_names, apply_signal_filter |
| `__init__.py` | Kompatibilitäts-Shim |

### errors.py → errors/

| Sub-Modul | Inhalt |
|-----------|--------|
| `_codes.py` | ErrorInfo, ERROR_REGISTRY, EXIT_*-Konstanten, explain-Helpers |
| `_exceptions.py` | DriftError, DriftConfigError, DriftSystemError, DriftAnalysisError, YAML-Helpers |
| `__init__.py` | Kompatibilitäts-Shim |

### Dependency Inversion (Phase A)

- Tree-Sitter-Funktionen aus `_utils.py` (high fan-in) in `signals/_ts_support.py` isoliert
- `EmbeddingServiceProtocol` in `protocols.py` als Protocol-Interface extrahiert
- Kein Signal importiert mehr direkt aus `_utils.py` für TS-Parsing

## Konsequenzen

### Positiv
- Isolierte Änderungen an Schema-Klassen erfordern kein Neuladen des gesamten Moduls
- Klare Verantwortlichkeitstrennung (Enums vs. Git-Modelle vs. Findings)
- Interne Import-Zyklen durch saubere Abhängigkeitsrichtung vermieden
- Alle 4641 Tests bestehen ohne Anpassung externer Importe

### Negativ
- `protocols.py` hat hohen Blast Radius (84 Module), da alle Signale es transitiv importieren
- Zusätzliche Dateien erhöhen die Navigations-Komplexität
- Score hat sich nicht signifikant verbessert (0.501 → 0.525), da dominierende Findings (explainability_deficit, cognitive_complexity, DCA) nicht adressiert werden

### Neutral
- Kompatibilitäts-Shims können in einem späteren Breaking-Release entfernt werden

## Evidenz

- Testsuite: 4641 passed, 0 failed, 126 skipped (nach jeder Phase verifiziert)
- Kein externer Import musste angepasst werden (Shim-Strategie validiert)
- Score-Entwicklung: 0.501 (Baseline) → 0.525 (nach Dekomposition)
