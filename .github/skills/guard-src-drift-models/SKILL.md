---
name: guard-src-drift-models
description: "Drift-generierter Guard fuer `src/drift/models`. Aktiv bei Signalen: AVS. Konfidenz: 0.62. Verwende diesen Skill wenn du Aenderungen an `src/drift/models` planst oder wiederholte Drift-Findings (AVS) fuer dieses Modul bearbeitest."
argument-hint: "Beschreibe welches Modell (Finding, RepoAnalysis, Enum...) geaendert oder erweitert wird."
---

# Guard: `src/drift/models`

`src/drift/models` enthaelt die zentralen Datentransfer-Objekte: `Finding`, `RepoAnalysis`, `ParseResult`, `FileHistory`, `CommitInfo`, `SignalType`, sowie die StrEnum-Typen `AnalysisStatus` und `TrendDirection`. AVS entsteht wenn Models beginnen Geschaeftslogik zu enthalten.

**Konfidenz: 0.62** — AVS-Risiko real aber noch moderat; Modelle neigen dazu Convenience-Methoden anzusammeln die eigentlich woanders hingehoeren.

## When To Use

- Du fuegest ein Feld zu `Finding` oder `RepoAnalysis` hinzu
- Du aenderst `AnalysisStatus` oder `TrendDirection` Enums
- Du erweiterst `ParseResult`, `FileHistory` oder `CommitInfo`
- Du fuegest neue Model-Typen hinzu
- Drift meldet AVS fuer `src/drift/models/`

## Warum AVS hier entsteht

Models akkumulieren Logik wenn:
- Convenience-Properties wie `@property def critical_count()` Berechnungen machen statt nur Daten zu lesen
- Methoden wie `to_dict()` Transformationen vornehmen statt nur zu serialisieren
- `RepoAnalysis` anfaengt Findings zu sortieren/filtern statt sie nur zu halten
- `Finding.severity_level` eine Berechnung statt ein gespeicherter Wert ist

## Core Rules

1. **Models sind Datenbehaalter — keine Geschaeftslogik** — `Finding`, `RepoAnalysis` und Geschwister enthalten Felder und einfache `to_dict()`/`from_dict()`-Serialisierung. Berechnungen (Scores, Prioritaeten, Aggregationen) gehoeren in `scoring/` oder `api/`.

2. **Enums aus `_enums.py` verwenden** — `AnalysisStatus` und `TrendDirection` sind StrEnum. Neue Status-Typen kommen als neue StrEnum in `_enums.py`, nicht als freie Strings irgendwo anders.

3. **`RepoAnalysis.preflight` als konkreter Typ** — `preflight: PreflightResult | None` ist der deklarierte Typ, kein `Any`. Code der `preflight` liest, nutzt direkten Zugriff (`analysis.preflight`), kein `getattr`.

4. **Keine `import`-Zyklen durch Models** — `models/` darf nur `config/` importieren, nicht `signals/`, `output/` oder `api/`. Zirkulaere Imports durch Models sind schwer zu debuggen.

5. **Neue Felder mit Tests absichern** — jedes neue Feld in `RepoAnalysis` oder `Finding` braucht mindestens einen Test der sicherstellt, dass JSON-Serialisierung und JSON-Deserialisierung korrekt sind.

## Iron Law

> **Keine Berechnung in `models/`-Klassen die einen anderen Wert als ein gespeichertes Feld zurueckgibt.** Wenn du das Wort `compute`, `calculate` oder `score` in einem Model-Property verwendest, gehoert es in `scoring/`.

## Review Checklist

- [ ] Neues Feld ist ein Datenbehaalter, kein berechneter Wert
- [ ] Neue Enums kommen in `_enums.py` als StrEnum
- [ ] `preflight`-Feld bleibt `PreflightResult | None` (kein `Any`)
- [ ] Kein `import` von `signals/`, `output/` oder `api/` in `models/`
- [ ] JSON-Roundtrip-Test fuer neue Felder vorhanden
- [ ] `drift nudge` zeigt `safe_to_commit: true`
- [ ] Keine neuen AVS-Findings

## References

- [src/drift/models/_findings.py](../../../src/drift/models/_findings.py) — `Finding`, `RepoAnalysis`
- [src/drift/models/_enums.py](../../../src/drift/models/_enums.py) — `AnalysisStatus`, `TrendDirection`
- [src/drift/models/__init__.py](../../../src/drift/models/__init__.py) — Oeffentliche Model-Exports
