# FMEA-Matrix — drift-analyzer

> **Failure Mode and Effects Analysis** für Befundtypen, Scoring und Systemverhalten.
> Lebendes Dokument — Review bei jedem Minor-Release.

**Erstellt:** 2026-04-01  
**Methode:** IEC 60812-konforme FMEA mit evidenzbasierter RPN-Bewertung  
**Datenquellen:** `signal-audit.md` (30 Findings, 3 Repos), `ground_truth_analysis.json` (291 Samples), `mutation_benchmark.json` (17 Mutationen), `go-no-go.md`  
**Bewertungsskala:** Schwere (S), Auftretenswahrscheinlichkeit (O), Entdeckbarkeit (D) jeweils 1–10; RPN = S × O × D  
**Schwellen:** RPN ≥ 300 = kritisch (rot), 100–299 = mittel (gelb), < 100 = niedrig (grün)

---

## Abkürzungen

| Kürzel | Bedeutung |
|--------|-----------|
| FP | False Positive — Befund gemeldet, obwohl kein reales Problem |
| FN | False Negative — reales Problem nicht erkannt |
| S | Schwere (Severity): 1 = vernachlässigbar, 10 = kritischer Vertrauensverlust |
| O | Auftretenswahrscheinlichkeit (Occurrence): 1 = extrem selten, 10 = nahezu jedes Repo |
| D | Entdeckbarkeit (Detection): 1 = sofort auffällig, 10 = bleibt unbemerkt |

---

## 1. FP-Fehlermodi — „Signal meldet Problem, obwohl keines existiert"

| ID | Signal | Fehlermodus | S | O | D | RPN | Evidenz | Gegenmaßnahme | Status |
|----|--------|-------------|---|---|---|-----|---------|---------------|--------|
| FP-01 | DCA | Library-Exports als Dead Code gemeldet (\_\_all\_\_, Re-Exports) | 9 | 9 | 8 | **720** 🔴 | >90% FP bei Libraries (signal-audit); weight=0.0 (report-only) | Library-Heuristik: `setup.py`/`pyproject.toml` + `__init__` Re-Exports erkennen → DCA supprimieren | **Blocker** — report-only bleibt bis Fix |
| FP-02 | DIA | Badge-URLs und URL-Fragmente als fehlende Verzeichnisse | 6 | 8 | 6 | **288** 🟡 | ~40% FP-Rate (signal-audit); `strict: 0.63` (ground_truth) | URL-Fragment-Detection: `http(s)://`, `#`-Anker, Badge-Patterns ausschließen | Offen |
| FP-03 | AVS | Identische Findings 2–3× gemeldet (God-Module, Zones, Cycles aus verschiedenen Passes) | 7 | 6 | 6 | **252** 🟡 | +15–20% Finding-Volumen (go-no-go Blocker #2); `strict: 0.30` vs `lenient: 0.80` | Deduplizierung: UNIQUE(rule_id, file, start_line, title) auf Pass-Ebene | **Blocker** |
| FP-04 | NBV | Domain-Konventionen (RFC, Krypto, Type-System) als Naming-Violations | 5 | 4 | 5 | **100** 🟢 | ~50% FP bei Krypto/Type-Code (signal-audit); `kex_`, `auth_` Patterns | Domain-Whitelist für bekannte Namenskonventionen (RFC, Framework-Suffixe) | Wünschenswert |
| FP-05 | PFS | Redundante Findings über Verzeichnishierarchie (selbes Pattern auf Parent + Child) | 5 | 7 | 5 | **175** 🟡 | Finding-Redundanz bei tiefen Verzeichnisbäumen (signal-audit) | Deep-Finding-Only: nur tiefste Ebene reporten; Parent-Aggregation optional | Wünschenswert |
| FP-06 | EDS | Überflutung: 70+ korrekte Findings pro Repo → Noise | 4 | 6 | 3 | **72** 🟢 | `precision_strict: 1.0` aber 72 Findings im Ground-Truth-Sample | Top-N-Filterung (default: 10 pro Signal); Severity-Gate für EDS | Wünschenswert |
| FP-07 | MDS | Near-Duplicate FP bei Boilerplate-Code (\_\_init\_\_, Conftest) | 3 | 2 | 3 | **18** 🟢 | `strict: 0.82`, 2 FP bei 68 Samples | Boilerplate-Ausschlussliste (\_\_init\_\_.py, conftest.py, \_\_main\_\_.py) | Niedrig |
| FP-08 | MAZ | Healthcheck/Docs-Endpoints als fehlende Authorization gemeldet | 4 | 5 | 4 | **80** 🟢 | Report-only (weight=0.0); Allow-List existiert (health, metrics, docs) | Erweiterte Allow-List pflegen; Framework-spezifische Patterns | Überwachung |
| FP-09 | TSA | TS/JS-Regelbefunde auf Legacy-Monorepos ohne deklarierte Layer als falsche Architecture-Violations gemeldet | 5 | 4 | 6 | **120** 🟡 | Neues Signal TSA (report-only) — geringe Feldvalidierung außerhalb Testsuite | Report-only beibehalten; Präzisionsmessung über repräsentative TS-Repos vor Scoring-Promotion | Neu (2026-04-01) |

---

## 2. FN-Fehlermodi — „Reales Problem bleibt unerkannt"

| ID | Signal | Fehlermodus | S | O | D | RPN | Evidenz | Gegenmaßnahme | Status |
|----|--------|-------------|---|---|---|-----|---------|---------------|--------|
| FN-01 | SMS | Neuartige Dependencies nicht erkannt (unbekannte Import-Muster) | 8 | 4 | 8 | **256** 🟡 | Mutation-Recall: 0.0 (1 injiziert, 0 erkannt) | Import-Pattern-Erweiterung; dynamische Import-Erkennung | **Priorität** |
| FN-02 | PFS | Subtile Fragmentierung bei nur 2 Varianten (unterhalb Threshold) | 6 | 5 | 7 | **210** 🟡 | Mutation-Recall: 0.5 (2 injiziert, 1 erkannt) | Threshold-Kalibrierung: 2-Varianten-Detection bei hinreichender Divergenz | Offen |
| FN-03 | AVS | Layer-Violations in dynamischen Imports (`importlib`, `__import__`) | 7 | 3 | 9 | **189** 🟡 | Nicht in Mutation-Benchmark getestet; AST-basiert → dynamische Imports unsichtbar | Erkennung dynamischer Imports als Degradation-Marker (Vollständigkeitswarnung) | Offen |
| FN-04 | MDS | Semantische Duplikate (unterschiedliche Syntax, gleiche Logik) | 7 | 3 | 8 | **168** 🟡 | `strict: 0.82`; AST-Fingerprint basiert → strukturelle Ähnlichkeit nötig | Embedding-basierter Vergleich (optional, experimentell) | Langfristig |
| FN-05 | TVS | Langsame Erosion über Monate (unterhalb Churn-Threshold) | 5 | 5 | 7 | **175** 🟡 | 30/30 Findings = Disputed; keine Ground Truth | Langzeit-Trend-Analyse über Baseline-Vergleiche | Nach TVS-Validierung |
| FN-06 | HSC | Obfuskierte Secrets (Base64-encoded, Environment-Variable-Fallback) | 7 | 3 | 8 | **168** 🟡 | Report-only; Entropy-basiert (≥3.5), Länge ≥16 | Pattern-Erweiterung: Base64-Decode-Heuristik; `.env`-Fallback-Prüfung | Überwachung |
| FN-07 | DIA | Doc-Drift in nicht-englischen Dokumenten (andere Sprachstruktur) | 4 | 3 | 6 | **72** 🟢 | Nicht getestet; DIA parst Markdown-Struktur sprachunabhängig | Internationalisierungstest mit Nicht-EN-Repos | Niedrig |
| FN-08 | TSA | TS-Architekturverletzungen mit dynamischen Imports oder Alias-Resolvern bleiben unerkannt | 6 | 4 | 7 | **168** 🟡 | TS-Regeln arbeiten primär statisch auf Datei-/Importebene | Alias- und Dynamic-Import-Heuristiken erweitern; Recall mit TS-Mutationsfällen messen | Neu (2026-04-01) |

---

## 3. Klarheits-Fehlermodi — „Befund korrekt, aber nicht verständlich oder handlungsfähig"

| ID | Signal | Fehlermodus | S | O | D | RPN | Evidenz | Gegenmaßnahme | Status |
|----|--------|-------------|---|---|---|-----|---------|---------------|--------|
| CL-01 | MDS | Remediation-Platzhalter `?` statt echtem Symbolnamen | 6 | 7 | 3 | **126** 🟡 | Go-no-go Blocker #3: schlechter Ersteindruck | Symbol-Extraction in MDS-Remediation; Fallback auf Datei:Zeile | **Blocker** |
| CL-02 | Alle | Findings ohne klare nächste Maßnahme (nur Problembeschreibung) | 5 | 4 | 5 | **100** 🟢 | signal-audit: 13% der Findings = „unklar formuliert" | Remediation-Templates pro Signal; `explain`-Befehl verlinken | Wünschenswert |
| CL-03 | EDS/PFS | Massenhafte gleichartige Findings → Informationsüberflutung | 5 | 6 | 4 | **120** 🟡 | signal-audit: EDS 70+ Findings, PFS redundant über Ebenen | Gruppierung gleichartiger Findings; Summary statt Einzelliste | Wünschenswert |
| CL-04 | AVS | „God Module" ohne Erklärung warum problematisch im Kontext | 4 | 3 | 5 | **60** 🟢 | signal-audit: korrekt aber „schwach" bei 17% | Kontextuelle Erklärung: Abhängigkeitsanzahl, Änderungsfrequenz, Kopplung | Niedrig |

---

## 4. Scoring-Fehlermodi — „Composite Score über-/unterbewertet"

| ID | Bereich | Fehlermodus | S | O | D | RPN | Evidenz | Gegenmaßnahme | Status |
|----|---------|-------------|---|---|---|-----|---------|---------------|--------|
| SC-01 | Gewichtung | TVS (weight=0.13) fließt in Score trotz 0% validierter Precision | 7 | 6 | 5 | **210** 🟡 | TVS: 30/30 Disputed; weight=0.13 (dritthöchste) beeinflusst Composite substanziell | TVS-Gewicht auf 0.0 (report-only) bis Validierung abgeschlossen; oder Confidence-Discount | **Priorität** |
| SC-02 | Gewichtung | DCA-Findings (weight=0.0) rauschen nicht in Score, aber in Finding-Count und UX-Wahrnehmung | 5 | 7 | 4 | **140** 🟡 | DCA >90% FP bei Libraries (signal-audit) | Finding-Count-Display ohne report-only-Signale; klare report-only-Markierung im Output | Wünschenswert |
| SC-03 | Breadth | Log-basierter Breadth-Faktor überhöht multi-file Findings mit geringem Score | 4 | 3 | 6 | **72** 🟢 | `impact = weight × score × (1 + log(1 + related_count))` | Cap auf Breadth-Faktor oder Minimum-Score-Gate vor Breadth-Anwendung | Niedrig |
| SC-04 | Dampening | >10 Findings pro Signal: sub-lineares Wachstum kann echte Großprobleme abschwächen | 5 | 3 | 7 | **105** 🟡 | Dampening ab 10 Findings; bei 70 EDS-Findings → stark abgeschwächt | Differenzierte Dampening-Kurve je Signal (EDS flacher, AVS steiler) | Offen |

---

## 5. Degradation-Fehlermodi — „Analyse stillschweigend unvollständig"

| ID | Komponente | Fehlermodus | S | O | D | RPN | Evidenz | Gegenmaßnahme | Status |
|----|-----------|-------------|---|---|---|-----|---------|---------------|--------|
| DG-01 | Git-Subprocess | `git log` Timeout (60s) → TVS/CCC-Signale fallen still aus | 7 | 3 | 7 | **147** 🟡 | 60s-Timeout existiert; DegradationInfo trackt `git_timeout` | Degradation-Badge im Output wenn git-abhängige Signale ausgefallen | Teilweise (DegradationInfo existiert, Output-Badge fehlt) |
| DG-02 | AST-Parser | Parser-Fehler bei ungültigem Python → Datei übersprungen, Signale unvollständig | 6 | 4 | 6 | **144** 🟡 | `parser_failure` in DegradationInfo; test_analysis_degradation.py existiert | Prozentangabe „N von M Dateien vollständig geparst" im Output | Teilweise |
| DG-03 | File-Discovery | max_discovery_files=10.000 → bei Monorepos stille Beschneidung | 6 | 3 | 8 | **144** 🟡 | Guardrail existiert; boundary-test bestanden (31 passed) | Warnung wenn Limit erreicht: „Analyse auf N/M Dateien beschränkt" | Teilweise |
| DG-04 | BOM-Bug | pyproject.toml mit UTF-8 BOM → DRIFT-1002, Analyse bricht ab | 8 | 2 | 3 | **48** 🟢 | Bekannter Bug (repo_memory); `tomllib.loads` scheitert an BOM | `codecs.open()` oder BOM-Strip vor Parsing | **Bekannt, unfixed** |
| DG-05 | Cache | Parse-Cache-Invalidierung bei Branch-Wechsel → veraltete Ergebnisse | 5 | 2 | 8 | **80** 🟢 | Cache invalidiert via Git-Commit-Hash; Edge Case: uncommitted changes | Cache-Key um Datei-mtime erweitern; oder Cache-Clear-Option | Niedrig |

---

## 6. Kontext-Fehlermodi — „Repo-Typ verfälscht Ergebnisse systematisch"

| ID | Kontext | Fehlermodus | S | O | D | RPN | Evidenz | Gegenmaßnahme | Status |
|----|---------|-------------|---|---|---|-----|---------|---------------|--------|
| KX-01 | Library-Repos | DCA/DIA/NBV FP-Cluster: Library-Patterns (Re-Exports, Plugins, RFC-Namen) erzeugen systematische Fehlalarme | 8 | 7 | 6 | **336** 🔴 | signal-audit: DCA >90% FP, DIA ~40% FP, NBV ~50% FP bei Libraries | Automatische Library-Erkennung (`setup.py`, `pyproject.toml [project]`); Context-Tag `library` → Signal-Anpassung | **Priorität** |
| KX-02 | Monorepos | PFS/AVS Overload: Hunderte Module → Finding-Explosion | 6 | 4 | 5 | **120** 🟡 | Frappe-Audit: 1.179 Dateien, 913 Findings | Module-Scoping per `path_overrides`; Standard-Empfehlung in Dokumentation | Wünschenswert |
| KX-03 | Minimale Repos | EDS/SMS Noise: <10 Dateien → Signale statistisch nicht aussagekräftig | 4 | 5 | 4 | **80** 🟢 | Arrow-Audit: 10 Dateien, 20 Findings (akzeptabel) | Minimum-File-Count-Gate pro Signal; Warnung unter Schwelle | Niedrig |
| KX-04 | Ungewöhnl. Git-History | Squash-Merges, Force-Pushes → TVS/CCC können nicht sinnvoll kalkulieren | 5 | 3 | 7 | **105** 🟡 | Nicht systematisch getestet; TVS 30/30 Disputed | Git-History-Qualitätscheck vor Temporal-Signalen; Confidence-Marker | Offen |

---

## RPN-Ranking — Top 10

| Rang | ID | Fehlermodus | RPN | Kategorie | Status |
|------|----|-------------|-----|-----------|--------|
| 1 | FP-01 | DCA Library-Exports als Dead Code | **720** 🔴 | FP | Report-only (mitigiert durch weight=0.0) |
| 2 | KX-01 | Library-FP-Cluster (DCA/DIA/NBV) | **336** 🔴 | Kontext | **Priorität** |
| 3 | FP-02 | DIA URL-Fragmente als Missing Dirs | **288** 🟡 | FP | Offen |
| 4 | FN-01 | SMS: neuartige Dependencies unerkannt | **256** 🟡 | FN | **Priorität** |
| 5 | FP-03 | AVS Duplikate | **252** 🟡 | FP | **Blocker** |
| 6 | SC-01 | TVS im Score trotz 0% Validation | **210** 🟡 | Scoring | **Priorität** |
| 7 | FN-02 | PFS: 2-Varianten-Lücke | **210** 🟡 | FN | Offen |
| 8 | FN-03 | AVS: dynamische Imports unsichtbar | **189** 🟡 | FN | Offen |
| 9 | FP-05 | PFS Verzeichnis-Redundanz | **175** 🟡 | FP | Wünschenswert |
| 10 | FN-04/05 | MDS semantische Dup. / TVS langsame Erosion | **168–175** 🟡 | FN | Langfristig |

---

## Testabdeckung je Fehlermodus

| ID | P/R-Fixture | Mutation-Test | Ground-Truth | Lücke |
|----|-------------|--------------|--------------|-------|
| FP-01 | — | — | — | Kein Library-Kontext-Fixture |
| FP-02 | dia_tp, dia_tn | dia: 3/3 = 1.0 | strict: 0.63 | Kein URL-Fragment-Fixture |
| FP-03 | avs_tp, avs_tn, avs_circular_tp | avs: 2/2 = 1.0 | strict: 0.30 | Kein Dedup-Fixture |
| FN-01 | sms_tp, sms_tn | sms: 0/1 = **0.0** | strict: 1.0 | **Mutation-Lücke** |
| FN-02 | pfs_tp, pfs_tn + 3 Varianten | pfs: 1/2 = **0.5** | strict: 1.0 | **2-Varianten-Fixture fehlt** |
| SC-01 | tvs_tp, tvs_tn | tvs: 1/1 = 1.0 | strict: **0.0** (30/30 Disputed) | **Validierungs-Lücke** |
| CL-01 | — | — | — | Kein Remediation-Quality-Test |
| DG-01 | — | — | — | Kein Timeout-Degradation-E2E-Test |
| KX-01 | — | — | — | Kein Library-Kontext-Fixture |

---

## Review-Trigger

- **Bei neuem Signal:** FMEA-Eintrag für FP und FN Pflicht vor Merge
- **Bei Minor-Release:** Top-10-RPN Review; RPN-Werte aktualisieren
- **Bei Precision-Änderung >5%:** betroffene Fehlermodi neu bewerten
- **Bei neuem Blocker in go-no-go:** sofortiger FMEA-Eintrag
