---
id: ADR-069
status: proposed
date: 2025-07-24
supersedes:
---

# ADR-069: Protocol-basierte Dependency Inversion für Embedding und TS-Parsing

## Kontext

`src/drift/signals/_utils.py` war ein High-Fan-In-Modul (>30 Importeure), das sowohl allgemeine Helper (is_test_file, Konstanten) als auch optionale Abhängigkeiten (tree-sitter via ts_parse_source/ts_walk/ts_node_text) enthielt.

`src/drift/signals/base.py` enthielt die konkrete `EmbeddingService`-Klasse als Type-Annotation in `AnalysisContext`, was alle Signale transitiv an `sentence-transformers` koppelte — obwohl nur 2 Signale Embeddings nutzen.

Die Zone-of-Pain-Analyse identifizierte beide als instabile High-Coupling-Knoten.

## Entscheidung

### Tree-Sitter-Isolation

Die drei Funktionen `ts_parse_source()`, `ts_walk()` und `ts_node_text()` werden in `src/drift/signals/_ts_support.py` extrahiert. Die 5 Signal-Dateien, die diese Funktionen nutzen, importieren direkt aus `_ts_support`. `_utils.py` enthält keine TS-Funktionen mehr.

### EmbeddingService Protocol

Ein `@runtime_checkable class EmbeddingServiceProtocol(Protocol)` wird in `src/drift/protocols.py` definiert. `AnalysisContext` in `base.py` referenziert nur das Protocol, nicht die konkrete Klasse. Die bestehende `EmbeddingService`-Implementierung erfüllt das Protocol strukturell (keine explizite Vererbung nötig).

## Konsequenzen

### Positiv
- Signale ohne TS-Parsing importieren tree-sitter nicht mehr transitiv
- `_utils.py` ist stable leaf mit nur constants + is_test_file
- Embedding-Dependency ist invertiert — Signale hängen vom Protocol ab, nicht von der Implementierung

### Negativ
- `protocols.py` wird neuer Hub mit hohem Blast Radius (Ca=84) laut AVS-Analyse nach Refactoring
- 5 Signal-Dateien mussten Import-Pfade anpassen (einmalig)

## Evidenz

- 4641 Tests bestehen nach Extraktion
- Kein Laufzeit-Regressionstest fehlgeschlagen
- AVS meldet protocols.py als neuen High-Coupling-Knoten (erwartetes Trade-off)
