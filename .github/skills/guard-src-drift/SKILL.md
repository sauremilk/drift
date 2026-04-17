---
name: guard-src-drift
description: "Drift-generierter Guard fuer `src/drift`. Aktiv bei Signalen: AVS, EDS, MDS, PFS. Konfidenz: 0.95. Verwende diesen Skill wenn du Aenderungen an `src/drift` planst oder wiederholte Drift-Findings (AVS, EDS, MDS, PFS) fuer dieses Modul bearbeitest."
argument-hint: "Beschreibe die geplante Aenderung in `src/drift` — welche Datei, welche Funktion, welcher Zweck."
---

# Guard: `src/drift`

`src/drift` ist der Kern des gesamten Analyzers. Er enthaelt `analyzer.py`, `pipeline.py`, `cache.py`, `scoring/`, `mcp_*.py`-Orchestrierung und alle oeffentlichen Einstiegspunkte. Jede Aenderung hier hat breite Auswirkungen auf Scan-Korrektheit, Scoring und Agenten-Verhalten.

**Konfidenz: 0.95** — alle vier Hauptsignale treten wiederholt auf.

## When To Use

- Du aenderst eine Datei direkt in `src/drift/` (nicht in einem Unterpaket)
- Du bearbeitest `analyzer.py`, `pipeline.py`, `cache.py`, `api_helpers.py`, `task_graph.py` oder `scoring/`
- Ein Drift-Scan meldet AVS, EDS, MDS oder PFS fuer Dateien im Wurzelpaket
- Vor einem Commit der `src/drift/__init__.py` oder oeffentliche Exports aendert

**Nicht benutzen** fuer Aenderungen ausschliesslich in `src/drift/signals/`, `src/drift/api/` oder `src/drift/output/` — dafuer gibt es dedizierte Guards.

## Warum dieses Modul kritisch ist

`src/drift/` ist das einzige Modul mit allen vier Hochrisiko-Signalen gleichzeitig:

| Signal | Was es bedeutet | Konkretes Risiko hier |
|--------|-----------------|----------------------|
| **AVS** | God-Module / Abstraction Violation | `analyzer.py` baut Verantwortlichkeiten auf — neue Logik dort zieht AVS an |
| **EDS** | Unexplained Complexity | `drift_map`, `pipeline.py` haben bereits EDS — neue verschraenkte Logik verschlimmert das |
| **MDS** | Exakte Duplikate | Hilfsfunktionen entstehen oft doppelt wenn man nicht `_utils.py` oder `api_helpers.py` nutzt |
| **PFS** | Pattern Fragmentation | MCP-Handler (`mcp_*.py`) haben schon inkonsistente Muster — neue Varianten erhoehen PFS |

## Core Rules

1. **Keine neue Logik direkt in `analyzer.py` oder `pipeline.py`** — diese Dateien sind bereits God-Module-Kandidaten (AVS). Neue Faehigkeiten gehoeren in dedizierte Untermodule oder Klassen.

2. **Duplikate aktiv vermeiden** — vor dem Schreiben einer neuen Hilfsfunktion `grep_search` in `_utils.py`, `api_helpers.py`, `scoring/` und `task_graph.py` laufen lassen. MDS entsteht fast immer dadurch, dass eine existierende Funktion nicht gefunden wurde.

3. **MCP-Handler konsistent halten** — `mcp_router_*.py`-Dateien folgen demselben Muster. Neue Handler muessen dasselbe Routing-Interface implementieren, sonst steigt PFS.

4. **`cache.py` nicht fuer neue Concerns erweitern** — `cache.py` hat bereits hohe DCA (unused exports). Neue Cache-Logik kommt als separate Klasse, nicht als weitere Methode in `BaselineManager`.

5. **Oeffentliche API-Exports explizit halten** — was in `__init__.py` landet, ist Vertrag. Kein implizites Re-Export von internen Symbolen.

## Arbeitsablauf vor einem Commit

```bash
# 1. Scan auf Ziel-Scope
drift analyze --repo . --format rich --exit-zero

# 2. Schnelle Richtungspruefung nach Aenderung
drift nudge  # erwartet: safe_to_commit: true

# 3. Keine neuen AVS/EDS/MDS/PFS einfuehren
# Vergleiche Finding-Count vorher vs. nachher
```

## Review Checklist

- [ ] Neue Logik geht in ein Unterpaket, nicht in `analyzer.py` oder `pipeline.py`
- [ ] Vor neuer Hilfsfunktion: Duplikat-Check in `_utils.py`, `api_helpers.py`, `scoring/`
- [ ] MCP-Handler folgt dem bestehenden `mcp_router_*.py`-Muster
- [ ] `drift nudge` zeigt `safe_to_commit: true`
- [ ] `__init__.py`-Exports sind bewusste, dokumentierte Entscheidungen
- [ ] Keine neuen AVS/EDS/MDS/PFS-Findings im Diff

## References

- [DEVELOPER.md](../../DEVELOPER.md)
- [src/drift/pipeline.py](../../../src/drift/pipeline.py) — Analyse-Pipeline
- [src/drift/analyzer.py](../../../src/drift/analyzer.py) — Haupt-Analyzer
- [src/drift/api_helpers.py](../../../src/drift/api_helpers.py) — Gemeinsame Hilfsfunktionen
