# Fault Tree Analysis — drift-analyzer

> **Kausale Ursachenanalyse** für die drei höchstpriorisierten Systemrisiken.
> Methode: IEC 61025-konforme Fehlerbaumanalyse mit AND/OR-Gatter.
> Lebendes Dokument — jeder Fault Tree wird aktualisiert wenn FMEA-RPN sich ändert.

**Erstellt:** 2026-04-01  
**Input:** FMEA Top-RPN (FP-01, KX-01, FN-01, SC-01) + STRIDE Residual Risks (T-TB2-03, I-TB5-01)  
**Notation:** ⊞ = AND-Gatter (alle Bedingungen müssen zutreffen), ⊕ = OR-Gatter (eine Bedingung genügt)

---

## FT-1: „Harmlose Änderung wird als MEDIUM+ gemeldet"

**Top-Event:** User erhält False-Positive-Finding mit Severity ≥ MEDIUM  
**FMEA-Bezug:** FP-01 (RPN 720), FP-02 (RPN 288), FP-03 (RPN 252), KX-01 (RPN 336)  
**Auswirkung:** Vertrauensverlust beim Erstnutzer; erhöhte Suppressions-Last; Signal wird ignoriert

**TSA-Erweiterung (2026-04-01):**
- FP-09 ergänzt FT-1 als zusätzlicher FP-Pfad: `no_ts_layer_manifest` AND `strict_ts_rules_in_legacy_repo` → TSA-Fehlalarm.

```
                    ┌─────────────────────────────┐
                    │ TOP: FP mit Severity ≥ MED  │
                    └──────────────┬──────────────┘
                                   │
                              ⊕ (OR)
                     ┌─────────┼─────────┐─────────────────┐
                     │         │         │                 │
              ┌──────▼──┐ ┌───▼────┐ ┌──▼──────┐   ┌─────▼──────┐
              │ Signal-  │ │Dedup-  │ │Scoring- │   │ Kontext-   │
              │ FP       │ │Fehler  │ │Inflation│   │ Mismatch   │
              └────┬─────┘ └───┬────┘ └────┬────┘   └─────┬──────┘
                   │           │           │               │
              ⊕ (OR)      ⊞ (AND)    ⊕ (OR)          ⊕ (OR)
         ┌─────┼─────┐    │     │    │        │      │         │
         │     │     │    │     │    │        │      │         │
    ┌────▼┐ ┌─▼──┐ ┌▼──┐ │     │ ┌──▼───┐ ┌─▼──┐ ┌▼────┐ ┌──▼───┐
    │DCA: │ │DIA:│ │NBV│ │     │ │TVS   │ │Log-│ │Lib- │ │Mono- │
    │Lib- │ │URL-│ │RFC│ │     │ │0%val │ │Brdh│ │rary │ │repo  │
    │Exp. │ │Frag│ │Nam│ │     │ │w=.13 │ │fac.│ │Mode │ │Overl.│
    └──┬──┘ └─┬──┘ └┬──┘ │     │ └──────┘ └────┘ └──┬──┘ └──────┘
       │      │     │    │     │                     │
    ⊞(AND) ⊞(AND) ⊞(AND)│     │                  ⊞ (AND)
    │    │  │   │  │   │ │     │                  │     │
    ▼    ▼  ▼   ▼  ▼   ▼ ▼     ▼                  ▼     ▼
   B1   B2 B3  B4 B5  B6 B7   B8                 B9   B10
```

### Basic Events

| ID | Basic Event | Beschreibung | Testabdeckung | Status |
|----|-------------|--------------|---------------|--------|
| B1 | `is_library` | Repo hat Library-Struktur (setup.py, pyproject [project], __init__ Re-Exports) | ❌ Kein Library-Kontext-Fixture | **Lücke** |
| B2 | `dca_no_lib_detect` | DCA hat keine Library-Heuristik → zählt Re-Exports als Dead Code | ❌ Kein Test für Library-Kontext | **Lücke** |
| B3 | `url_in_doc` | Dokumentation enthält URLs mit Pfad-Fragmenten (Badges, Shields.io) | ❌ Kein URL-Fragment-Fixture | **Lücke** |
| B4 | `dia_url_as_dir` | DIA parst URL-Pfade als fehlende Verzeichnisse | ✅ dia_tp/dia_tn existieren; URL-Edge-Case fehlt | **Partiell** |
| B5 | `domain_names` | Code verwendet Domain-Konventionen (RFC-Prefixe, Krypto-Namen) | ❌ Kein Domain-Fixture | **Lücke** |
| B6 | `nbv_no_whitelist` | NBV hat kein Domain-Wörterbuch → meldet konventionelle Namen als Violations | ❌ Kein Test | **Lücke** |
| B7 | `multi_pass` | Signal produziert Findings aus verschiedenen Analyse-Passes (AVS: God-Module, Zones, Cycles) | ✅ avs_tp/avs_tn; Dedup-Logik existiert | **Dedup-Gap** |
| B8 | `same_key` | Findings haben identischen Key (rule_id, file, line, title) aus verschiedenen Passes | ✅ Dedup-Test in json_output.py | **Partiell** — Cross-Pass-Dedup fehlt |
| B9 | `no_lib_tag` | Config hat keinen Context-Tag `library` oder kein automatisches Library-Detection | ❌ Kein Test | **Lücke** |
| B10 | `no_context_adapt` | Signal-Thresholds sind nicht kontextabhängig (Library vs. Application) | ❌ Kein Test | **Lücke** |

### Kausale Zusammenfassung

| Pfad | Gate-Kette | Wahrscheinlichkeit | Gegenmaßnahme |
|------|-----------|--------------------|----|
| DCA-Library-FP | B1 AND B2 → Signal-FP → TOP | Hoch bei Libraries | Library-Heuristik implementieren |
| DIA-URL-FP | B3 AND B4 → Signal-FP → TOP | Hoch bei Repos mit Badges | URL-Pattern-Exclusion in DIA |
| NBV-Domain-FP | B5 AND B6 → Signal-FP → TOP | Mittel bei Krypto/Type-Code | Domain-Whitelist einführen |
| AVS-Dedup-FP | B7 AND B8 → Dedup-Fehler → TOP | Mittel | Cross-Pass-Dedup |
| TVS-Score-FP | SC-01 direkt → Scoring-Inflation → TOP | Hoch (TVS weight=0.13 ohne Validierung) | TVS report-only oder Confidence-Discount |
| Library-Context-FP | B9 AND B10 → Kontext-Mismatch → TOP | Hoch bei Libraries | Automatische Kontext-Erkennung |

---

## FT-2: „Kritischer Architekturdrift bleibt unentdeckt"

**Top-Event:** Repo hat echtes strukturelles Problem das drift nicht meldet (False Negative)  
**FMEA-Bezug:** FN-01 (RPN 256), FN-02 (RPN 210), FN-03 (RPN 189)  
**Auswirkung:** Nutzer vertraut auf „sauberes" Ergebnis; Problem eskaliert unbemerkt

**TSA-Erweiterung (2026-04-01):**
- FN-08 ergänzt FT-2 als zusätzlicher Blindspot: `dynamic_ts_import` OR `path_alias_unresolved` → TSA-FN.

```
                    ┌───────────────────────────────────┐
                    │ TOP: Kritischer Drift unentdeckt  │
                    └───────────────┬───────────────────┘
                                    │
                               ⊕ (OR)
                  ┌────────┬───────┼────────┬──────────┐
                  │        │       │        │          │
           ┌──────▼──┐ ┌──▼────┐ ┌▼──────┐ ┌▼────────┐┌▼────────┐
           │Signal    │ │Signal │ │Signal │ │Degradat.││Threshold│
           │fehlt     │ │blind  │ │schwach│ │versteckt││zu hoch  │
           └────┬─────┘ └──┬───┘ └──┬────┘ └────┬────┘└────┬────┘
                │          │        │            │          │
           ⊕ (OR)    ⊕ (OR)   ⊕ (OR)      ⊞ (AND)    ⊕ (OR)
           │    │     │    │    │    │      │     │     │     │
           ▼    ▼     ▼    ▼    ▼    ▼      ▼     ▼     ▼     ▼
          C1   C2    C3   C4   C5   C6    C7    C8    C9   C10
```

### Basic Events

| ID | Basic Event | Beschreibung | Testabdeckung | Status |
|----|-------------|--------------|---------------|--------|
| C1 | `novel_import` | SMS erkennt neuartige Dependencies nicht (unbekannte Import-Muster) | ✅ sms_tp/sms_tn; ❌ Mutation Recall = **0.0** | **Kritische Lücke** |
| C2 | `no_signal_for_pattern` | Kein Signal existiert für bestimmte Drift-Typen (z.B. API-Contract-Breaking-Changes) | — Design-Gap; nicht testbar ohne neues Signal | **Design-Lücke** |
| C3 | `dynamic_import` | AVS erkennt dynamische Imports nicht (`importlib.import_module`, `__import__`) | ❌ Kein Test für dynamische Imports | **Lücke** |
| C4 | `string_import` | DCA erkennt String-basierte Imports nicht (`getattr(module, name)`) | ❌ Kein Test | **Lücke** |
| C5 | `2_variant_below_threshold` | PFS Threshold zu hoch für 2 Pattern-Varianten | ✅ pfs_tp; ❌ Mutation Recall = **0.5** | **Partiell** |
| C6 | `slow_erosion` | TVS erkennt langsame, gleichmäßige Erosion nicht (unterhalb 3σ-Threshold) | ❌ Kein Baseline-Trend-Fixture | **Lücke** |
| C7 | `parser_fail_silent` | AST-Parser schlägt fehl und Datei wird still übersprungen | ✅ test_analysis_degradation.py | **Abgedeckt** |
| C8 | `no_degradation_badge` | Output zeigt keine Degradation-Warnung → User bemerkt Unvollständigkeit nicht | ❌ Kein Output-Badge-Test | **Lücke** |
| C9 | `high_min_score` | Signal erfordert hohen Score bevor es meldet → moderate Probleme werden ignoriert | ✅ test_scoring_edge_cases.py | **Abgedeckt** |
| C10 | `severity_gate` | `severity_gate: HIGH` in Config → MEDIUM-Findings gefiltert | ✅ Config-Validierung existiert | **Abgedeckt** |

### Kausale Zusammenfassung

| Pfad | Gate-Kette | Recall-Impact | Gegenmaßnahme |
|------|-----------|--------------|---------------|
| SMS-Blindspot | C1 → Signal fehlt → TOP | SMS Mutation-Recall: **0.0** | Import-Pattern-Erweiterung; Regex-Update |
| Dynamische Imports | C3 OR C4 → Signal blind → TOP | AVS/DCA Recall unbekannt | Dynamische Import-Erkennung als Degradation |
| PFS-Threshold | C5 → Signal schwach → TOP | PFS Mutation-Recall: **0.5** | Threshold-Kalibrierung für 2-Varianten |
| Stille Degradation | C7 AND C8 → Degradation versteckt → TOP | Unbekannt (kein Badge) | Degradation-Badge im CLI/JSON-Output |

---

## FT-3: „Analyse liefert unbemerkt unvollständige Ergebnisse"

**Top-Event:** Composite Score und Finding-Liste sind partielle Ergebnisse, aber User bemerkt es nicht  
**FMEA-Bezug:** DG-01 (RPN 147), DG-02 (RPN 144), DG-03 (RPN 144), DG-04 (RPN 48)  
**STRIDE-Bezug:** T-TB2-03 (BOM-Bug)  
**Auswirkung:** Falsches Vertrauen in „niedriges" Ergebnis; Sicherheits-/Qualitätsprobleme übersehen

```
                    ┌─────────────────────────────────────┐
                    │ TOP: Unbemerkt unvollständige       │
                    │      Ergebnisse                     │
                    └───────────────┬─────────────────────┘
                                    │
                               ⊞ (AND)
                     ┌──────────────┼──────────────┐
                     │                             │
              ┌──────▼──────────┐          ┌───────▼──────────┐
              │ Analyse ist     │          │ User bemerkt     │
              │ unvollständig   │          │ es nicht         │
              └──────┬──────────┘          └───────┬──────────┘
                     │                             │
                ⊕ (OR)                        ⊕ (OR)
           ┌────┼────┼────┐              ┌────┼────┐
           │    │    │    │              │    │    │
           ▼    ▼    ▼    ▼              ▼    ▼    ▼
          E1   E2   E3   E4            E5   E6   E7
```

### Basic Events

| ID | Basic Event | Beschreibung | Testabdeckung | Status |
|----|-------------|--------------|---------------|--------|
| E1 | `git_timeout` | `git log` Subprocess überschreitet 60s → TVS, CCC, CXS-Daten fehlen | ✅ DegradationInfo trackt `git_timeout` | **Logik abgedeckt; Output-Badge fehlt** |
| E2 | `parser_errors` | ast.parse/tree-sitter schlägt für N Dateien fehl → Signale basieren auf unvollständigem Input | ✅ DegradationInfo trackt `parser_failure`; test_analysis_degradation.py | **Logik abgedeckt; Output-Badge fehlt** |
| E3 | `file_limit_reached` | max_discovery_files=10.000 erreicht → Rest des Repos nicht analysiert | ✅ Boundary-Test (31 passed); Limit existiert | **Logik abgedeckt; Warnung fehlt** |
| E4 | `config_abort` | BOM in pyproject.toml → DRIFT-1002 → Analyse bricht vor Start ab | ❌ BOM-Bug unfixed (repo_memory) | **Offen** ⚠️ |
| E5 | `no_degradation_output` | CLI/JSON-Output zeigt keinen Degradation-Indikator | ❌ Kein systematischer Test für Degradation-Anzeige | **Lücke** |
| E6 | `low_score_hides` | Unvollständige Analyse → weniger Findings → niedrigerer Score → „sieht gut aus" | — Inherent; Score reflektiert Findings, nicht Vollständigkeit | **Design-Problem** |
| E7 | `no_coverage_metric` | Keine Angabe „N von M Dateien analysiert" oder „N von 22 Signalen vollständig" | ❌ Kein Coverage-Metric im Output | **Lücke** |

### Kausale Zusammenfassung

| Pfad | Gate-Kette | Wahrscheinlichkeit | Gegenmaßnahme |
|------|-----------|--------------------|----|
| Git-Timeout-Stille | E1 AND (E5 OR E6) → TOP | Niedrig (60s für meiste Repos ausreichend) | Degradation-Badge + Signal-Availability-Count im Output |
| Parser-Lücke-Stille | E2 AND (E5 OR E7) → TOP | Mittel (gelegentliche Parser-Fehler) | „N/M Dateien geparst" im Output-Header |
| File-Limit-Stille | E3 AND (E5 OR E7) → TOP | Niedrig (nur bei >10k-Repos) | Warnung: „Limit erreicht, N Dateien übersprungen" |
| BOM-Crash | E4 → kein Output → TOP | Niedrig (Windows/Editor-spezifisch) | BOM-Strip in tomllib-Loader |

### Gemeinsamer Verursacher

**E5 (no_degradation_output)** und **E7 (no_coverage_metric)** sind an **allen drei Pfaden** beteiligt. Ihre Beseitigung würde die Entdeckbarkeit (D) für alle Degradation-Fehlermodi (DG-01 bis DG-03) von 7–8 auf 3–4 senken und die RPNs um ~50% reduzieren.

**Empfehlung:** Degradation-Badge und Coverage-Metric im Output sind die höchstwirksamen Einzelmaßnahmen für FT-3.

---

## Maßnahmen-Ableitung aus allen drei Fault Trees

| Prio | Maßnahme | FT-Bezug | Basic Events | RPN-Reduktion (geschätzt) |
|------|----------|----------|--------------|---------------------------|
| 1 | **Degradation-Badge im Output** (CLI + JSON) | FT-2, FT-3 | C8, E5, E7 | DG-01/02/03: D von 7→3 → RPN -57% |
| 2 | **Library-Kontext-Erkennung** (auto-detect + Context-Tag) | FT-1 | B1, B2, B9, B10 | FP-01: O von 9→3 → RPN -67% |
| 3 | **SMS Import-Pattern-Update** (Mutation-Recall 0.0 → >0.5) | FT-2 | C1 | FN-01: D von 8→4 → RPN -50% |
| 4 | **PFS 2-Varianten-Threshold** (Mutation-Recall 0.5 → >0.8) | FT-2 | C5 | FN-02: D von 7→4 → RPN -43% |
| 5 | **URL-Fragment-Exclusion in DIA** | FT-1 | B3, B4 | FP-02: O von 8→3 → RPN -63% |
| 6 | **BOM-Strip in Config-Loader** | FT-3 | E4 | DG-04: eliminiert (DRIFT-1002 verhindert) |
| 7 | **Coverage-Metric im Output** („N/M Dateien, N/22 Signale") | FT-3 | E7 | DG-01/02/03: D von 7→3 → RPN -57% |

---

## Testlücken-Register

| Lücke | Betroffene Basic Events | Empfohlener Testtyp | Fixture-Entwurf |
|-------|------------------------|--------------------|----|
| Library-Kontext | B1, B2, B9, B10 | P/R-Fixture: Library-Repo mit __init__ Re-Exports | `lib_context_tp`: setup.py + `__init__.py` mit `from .module import *` |
| URL-Fragment | B3, B4 | P/R-Fixture: README mit Badge-URLs | `dia_url_tn`: README mit `![badge](https://img.shields.io/...)` |
| Domain-Namen | B5, B6 | P/R-Fixture: Krypto-Code mit RFC-Prefixen | `nbv_domain_tn`: `kex_dh`, `auth_hmac` Funktionsnamen |
| Dynamische Imports | C3, C4 | P/R-Fixture: Code mit importlib.import_module | `avs_dynamic_tn`: `importlib.import_module("dal.models")` |
| Degradation-Badge | C8, E5 | Output-Golden-Test | Degradation-Marker in JSON-Schema prüfen |
| Coverage-Metric | E7 | Output-Golden-Test | `analysis_coverage` Feld in JSON-Schema |
| SMS-Mutation | C1 | Erweiterter Mutation-Benchmark | Neue Mutation-Variante für novel-dependency-Muster |
| Stille Degradation E2E | E1–E3, E5–E7 | Integration-Test | Repo mit absichtlich kaputtem .py + max_files=5 → Warnung im Output prüfen |

---

## Review-Trigger

- **FMEA-RPN-Änderung ≥ 50:** betroffenen Fault Tree aktualisieren
- **Neuer Fehlermodus in FMEA:** prüfen ob neuer Fault Tree nötig
- **Testlücke geschlossen:** Basic Event Status aktualisieren; RPN neu berechnen
- **Neues Signal:** FT-1 (FP) und FT-2 (FN) um Signal-spezifische Pfade erweitern
