---
id: ADR-017
status: proposed
date: 2026-04-07
supersedes:
---

# ADR-017: DIA False-Positive Reduction (FTA-basiert)

## Kontext

Eine Fault Tree Analysis des DIA-Signals identifiziert drei dominierende Cut Sets für False Positives:

- **CS-1 (Hoch):** `codespan`-Tokens werden mit `allow_without_context=True` extrahiert. Inline-Code wie `` `auth/callback` `` in Prosa ohne Strukturkontext erzeugt phantom-dir Findings.
- **CS-2 (Mittel):** Pfad-Normalisierung erkennt Container-Prefixe nicht. Ein Pfad wie
  ```
  src/services/
  ```
  existiert, aber die README-Kurzreferenz wird als phantom gemeldet, weil nur `parts[0]` ("src") in `source_dirs` aufgenommen wird.
- **CS-3 (Mittel):** ADR-Status wird ignoriert. `Superseded`-ADRs referenzieren bewusst veraltete Strukturen, die als phantom-dir Findings emittiert werden.

## Entscheidung

Drei unabhängige Fixes werden implementiert:

1. **Sibling-Context für codespan-Tokens:** `_walk_tokens()` sammelt `text`-Children-Content aus `paragraph`/`heading`-Tokens und reicht ihn als `sibling_context` an `codespan`-Verarbeitung weiter. `allow_without_context=True` wird nur gesetzt wenn der Sibling-Context ein Directory-Keyword enthält.

2. **Container-Prefix-Existenzprüfung:** Neuer Helper `_ref_exists_in_repo()` prüft Existenz unter kuratierten Container-Prefixen (`src`, `lib`, `app`, `pkg`, `packages`, `libs`, `internal`) zusätzlich zum direkten Pfad. Ersetzt die doppelte Existenz-Logik in `analyze()` und `_scan_adr_files()`.

3. **ADR-Status-Parsing:** Neuer Helper `_extract_adr_status()` liest YAML-Frontmatter und MADR-Freitext. ADRs mit Status `superseded`, `deprecated` oder `rejected` werden übersprungen.

**Explizit nicht umgesetzt:**
- Phase D (strukturelle URL-Heuristik zur Ablösung der `_URL_PATH_SEGMENTS`-Blacklist) — separater Scope.
- `proposed`-ADRs werden **nicht** übersprungen — zukünftige Strukturen können legitime Finding-Kandidaten sein.

## Begründung

- CS-1 ist der dominierende Cut Set (tritt in fast jedem README auf). Sibling-Context nutzt die bestehende `_DIRECTORY_CONTEXT_KEYWORDS`-Infrastruktur und erfordert minimalen Code-Eingriff.
- Container-Prefixes statt `source_dirs`-Erweiterung vermeidet Seiteneffekte auf die "undocumented source dir"-Prüfung und begrenzt die FN-Oberfläche.
- ADR-Status-Parsing nutzt etablierte Konventionen (MADR, YAML-Frontmatter) und ist konservativ (nur nachweislich ungültige Status werden übersprungen).

**Verworfene Alternative für CS-1:** `parent_raw` aus Paragraph-Token lesen — unmöglich, da mistune v3 Paragraphs kein `raw`-Feld haben.

**Verworfene Alternative für CS-2:** `_source_directories()` erweitern — hätte Seiteneffekte auf nachgelagerte Prüfungen.

## Konsequenzen

- DIA-Precision steigt durch Elimination der drei dominierenden FP-Quellen.
- Minimales FN-Risiko: (A) Codespans ohne Struktur-Keywords werden nicht extrahiert — akzeptabel, da selten echte Strukturclaims. (B) Container-Prefix-Liste ist kuratiert und begrenzt. (C) Superseded-ADRs sind per Definition nicht autoritativ.
- Neue öffentliche Helper: `_ref_exists_in_repo()`, `_extract_adr_status()` (beide modul-privat).
- Bestehende Tests müssen weiter grün sein; neue Regressionstests für alle drei Cut Sets.

## Validierung

- `pytest tests/test_dia_enhanced.py -v` — bestehende + neue Tests
- `pytest tests/test_precision_recall.py -v` — DIA precision ≥ vorher
- `drift analyze --repo . --format json --exit-zero` — DIA FP-Count sinkt
- Lernzyklus-Ergebnis: **unklar** (wird nach Merge an realen Repos validiert)

## Nachtrag (2026-04-07) — FTA v2 Refinement

Zwei verbleibende Self-Analysis-FPs nach FTA v1-Implementierung wurden durch FTA v2 kausale Analyse identifiziert und behoben:

- **IE-5a:** ADR-017 verwendete Inline-Codespans für illustrative Beispielpfade (z.B. `` `services/` ``). Da ADR-Scanning mit `trust_codespans=True` läuft, wurden diese als Phantom-Refs extrahiert. Fix: Beispiele in Fenced-Code-Blöcke verschoben.
- **BE-8a:** `work_artifacts/` (Arbeitsverzeichnis mit Ad-hoc-Scripts) war nicht in `_AUXILIARY_DIRS` enthalten und wurde als undocumented source dir gemeldet. Fix: `_AUXILIARY_DIRS` um `artifacts` und `work_artifacts` erweitert.

**Messwerte:** DIA Self-Analysis 2→0. 76/76 Tests grün (3 neue Regressionstests). 97/97 Precision/Recall unverändert.
