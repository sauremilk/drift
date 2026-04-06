# drift – Optimierungsstrategie: Signale schärfen, Findings brauchbar machen

> **Stand:** 23. März 2026 · **Version:** 2.0 · **Status:** Entwurf zur Entscheidung

**Leitprinzip:** drift ist als deterministischer Drift-Scanner gut. Es soll besser werden – nicht anders. Kein Produktumbau, keine neuen Infrastruktur-Abhängigkeiten, kein Feature-Creep. Bestehende Signale schärfen, bestehende Outputs brauchbarer machen.

---

## 1. Kategorie-Definition

**drift ist ein deterministischer Static-Analyzer, der architekturelle Erosion in AI-assistierten Codebases erkennt und jedes Finding mit einer konkreten Handlungsempfehlung versieht.**

---

## 2. Produktthese

AI-Code-Generatoren optimieren für den Prompt-Kontext, nicht für den Codebase-Kontext. Das erzeugt Code, der funktioniert, aber nicht passt – Error-Handling fragmentiert, Layer-Grenzen erodieren, beinahe identische Funktionen akkumulieren.

Kein bestehendes Tool misst diese spezifische Erosionsklasse. drift tut das: deterministisch, in Sekunden, mit spezialisierten Signalen (7 Core-Signale im v0.5-Baseline; seit v0.8.0 15 scoring-aktive Signale mit Auto-Kalibrierung), ohne LLM-Infrastruktur.

drift wird dann klar besser als alles andere in dieser Nische, wenn jedes einzelne Finding direkt sagt, was zu tun ist – nicht als zusammengefasstes Top-3, sondern pro Finding. Ein Entwickler liest ein Finding und weiß sofort: was ist das Problem, wo genau, und was ist der nächste Schritt.

---

## 3. Differenzierungsstrategie

### Was drift von breiten Plattformen trennt

| Dimension | SonarQube / CodeClimate | drift |
|---|---|---|
| Kategorie | Generische Code-Qualität | AI-/Architektur-Drift |
| Signale | Bugs, Smells, Style | Pattern Fragmentation, Mutant Duplicates, Layer Violations, Temporal Volatility, System Misalignment, Doc Drift |
| Kontext | Datei-lokal | Cross-module, cross-file, temporal |
| Speed | Minuten bis Stunden | 2–60 Sekunden |
| LLM | Zunehmend | Null in der Kern-Pipeline |

### Wo drift besser werden muss (statt breiter)

1. **Jedes Finding braucht eine Handlungsempfehlung.** Heute: "26 error_handling variants in connectors/". Morgen: "26 Varianten → dominantes Pattern ist try/except mit Retry (14×), konsolidiere die 12 Abweichungen."
2. **Signal-Precision erhöhen.** DIA bei 48% ist nicht aktivierbar. AVS-Sample zu klein für belastbare Aussagen. Hier liegt ungenutztes Potenzial.
3. **Findings besser priorisieren.** Nicht pauschal Top-3, sondern alle Findings mit Impact-Sortierung und klarer Severity – der Entwickler entscheidet selbst, wie viele er angeht.
4. **Benchmark-Corpus verbreitern.** 5 Repos sind ein Anfang. 15–20 machen die Precision/Recall-Zahlen belastbar und ermöglichen Größen-Normalisierung.

---

## 4. Was ein Entwickler nach einem Scan braucht

### Ist-Zustand (v0.3.0)

```
drift analyze --repo .

DRIFT SCORE: 0.520 (MEDIUM)
Files: 490 | Functions: 5,073

[MDS] HIGH 0.92  Near-duplicate: _run_async() across 6 files
      → pwbs/queue/tasks/briefing.py:12–18
      → pwbs/queue/tasks/embedding.py:14–20
      ...

[PFS] HIGH 0.96  26 error_handling variants in pwbs/connectors/
      → pwbs/connectors/google_calendar.py
      → pwbs/connectors/notion.py
      ...
```

**Problem:** Die Findings sagen *was* erkannt wurde, aber nicht *was zu tun ist*.

### Ziel-Zustand

```
[MDS] HIGH 0.92  Near-duplicate: _run_async() across 6 files
      → pwbs/queue/tasks/briefing.py:12–18
      → pwbs/queue/tasks/embedding.py:14–20
      → pwbs/queue/tasks/extraction.py:11–17
      → pwbs/queue/tasks/insights.py:13–19
      → pwbs/queue/tasks/multimodal.py:12–18
      → pwbs/queue/tasks/snapshots.py:14–20
      FIX: Extrahiere _run_async() in pwbs/queue/utils.py.
           6 identische Kopien (Similarity: 1.00).
           Aufwand: S – eine neue Datei, 6 Import-Änderungen.

[PFS] HIGH 0.96  26 error_handling variants in pwbs/connectors/
      Dominantes Pattern: try/except + tenacity retry (14×)
      Abweichungen: bare except (4×), if/else return (5×), custom exception (3×)
      FIX: Konsolidiere auf try/except + retry. Beginne mit den 4 bare-except
           Stellen – höchstes Risiko, niedrigster Aufwand.
      Dateien: google_calendar.py:45, notion.py:82, zoom.py:38, obsidian.py:61
```

**Der Unterschied:** Jedes Finding enthält:
- **Alle betroffenen Stellen** (nicht nur die ersten 2)
- **Eine FIX-Zeile:** Konkreter nächster Schritt, abgeleitet aus dem Signal-Typ und den erkannten Daten
- **Kontext-Daten:** Dominantes Pattern (bei PFS), Similarity-Score (bei MDS), Churn-Daten (bei TVS)
- **Aufwandseinschätzung:** S/M/L basierend auf Anzahl betroffener Dateien und Änderungstyp

### Was sich NICHT ändert

- Die Kern-Signale bleiben stabil. Seit v0.8.0 sind alle 15 Kern-Signale scoring-aktiv (6 Core + 9 promoted/new). Seit v2.0.0 kommen 8 weitere Signale im report-only Modus hinzu (23 total).
- Die Scoring-Formel bleibt deterministisch.
- Kein LLM in der Pipeline.
- Kein neuer CLI-Befehl nötig – die bestehenden Outputs (Rich, JSON, SARIF) werden angereichert.
- Kein History-Store, keine Datenbank, keine neue Infrastruktur.

---

## 5. Priorisierte Optimierungen

### Optimierung 1: Handlungsempfehlungen pro Finding (MUSS)

**Was:** Jedes Finding bekommt ein `fix`-Feld mit einer konkreten, aus den Analysedaten abgeleiteten Empfehlung.

**Warum:** Das ist der höchste Wert pro Aufwand. Keine neuen Module, keine neue Architektur – nur reichere Finding-Objekte.

**Umsetzung pro Signal:**

| Signal | Fix-Logik (deterministisch) |
|---|---|
| **MDS** | Zeige alle Duplikate + gemeinsames Extract-Target-Modul. "Extrahiere {func} in {module}/shared.py. {N} Kopien, Similarity {score}." |
| **PFS** | Identifiziere das häufigste Pattern als Dominant. Liste Abweichungen mit Datei:Zeile. "Konsolidiere auf {dominant_pattern}. {N} Abweichungen in {files}." |
| **AVS** | Zeige den verletzenden Import + die korrekte Schicht. "Import {X} in {layer} verletzt Boundary. Verschiebe in {correct_layer} oder nutze Interface." |
| **EDS** | Zeige Complexity-Score + fehlende Elemente. "Funktion {name} (Complexity {score}): fehlt Docstring, Return-Type, Tests." |
| **TVS** | Zeige Churn-Statistik. "{file}: {N} Commits in {M} Tagen, {K} Autoren. Erwäge Split oder Ownership klären." |
| **SMS** | Zeige die fremden Imports. "{module} nutzt {imports} die sonst nirgends vorkommen. Prüfe ob beabsichtigt – wenn ja, zur Konfiguration hinzufügen." |
| **DIA** | Zeige das konkrete Delta. "README referenziert {dir} – existiert nicht im Source. Entferne aus Dokumentation oder erstelle Verzeichnis." |

**Änderungen:**
- `Finding`-Modell in `models.py`: neues Feld `fix: str | None`
- Jede Signal-Klasse generiert die Fix-Empfehlung in `analyze()` aus den bereits berechneten Daten
- Rich-Output: FIX-Zeile unter jedem Finding
- JSON/SARIF: `fix`-Feld im Finding-Objekt

**Aufwand:** S–M (1–2 Wochen). Die Daten sind bereits vorhanden – es fehlt nur die Textgenerierung aus den Analyseergebnissen.

---

### Optimierung 2: Vollständige Fundstellen-Auflistung (MUSS)

**Was:** Jedes Finding listet *alle* betroffenen Dateien und Zeilen, nicht nur die ersten 2–3.

**Warum:** Ein Entwickler, der ein MDS-Finding mit "6 Duplikaten" sieht aber nur 2 Dateipfade bekommt, muss selbst suchen. Das bricht den Handlungsfluss.

**Umsetzung:**
- Rich-Output: Alle Lokationen anzeigen (bei >10: die ersten 10 + "und {N} weitere")
- JSON/SARIF: Immer alle Lokationen im `locations`-Array
- Gruppierung: Bei PFS die Varianten nach Pattern-Typ gruppieren, nicht als flache Liste

**Aufwand:** S (wenige Tage). Die Daten sind in den Findings bereits enthalten – der Output begrenzt sie nur künstlich.

---

### Optimierung 3: DIA-Signal Precision verbessern (MUSS)

**Was:** DIA von 48% auf ≥75% Precision bringen, damit es mit Gewicht >0 aktiviert werden kann.

**Warum:** DIA ist das einzige Signal, das Doc/Code-Divergenz misst – ein Kernproblem in AI-assistierten Codebases, wo Docs oft vom tatsächlichen Code abweichen. Bei 48% Precision ist es aber mehr Rauschen als Signal.

**Bekannte False-Positive-Quellen (aus STUDY.md §3.3):**
- URL-Fragmente werden als Verzeichnisse interpretiert (z.B. `actions/` aus GitHub-URLs)
- Badge-URLs, CamelCase-Eigennamen, Digit-only Segmente

**Umsetzung:**
- URL-Blacklist erweitern (GitHub, PyPI, ReadTheDocs, CI-Plattform Patterns)
- Context-Filter: Segmente die in Markdown-Links `[text](url)` vorkommen, ignorieren
- Code-Block-Filter: Segmente innerhalb von Fenced Code Blocks ignorieren
- Validierung: Precision auf dem bestehenden Benchmark-Corpus messen, erst aktivieren bei ≥75%

**Aufwand:** S–M (1–2 Wochen). Die Heuristik liegt in `doc_impl_drift.py`, die Blacklist ist erweiterbar.

---

### Optimierung 4: Impact-basierte Sortierung der Findings (SOLL)

**Was:** Findings nicht nur nach Signal-Score sortieren, sondern nach geschätztem Impact: `Impact = Signal-Weight × Score × betroffene Dateien`.

**Warum:** Heute stehen HIGH-Severity-Findings oben, unabhängig davon wie viele Dateien betroffen sind. Ein MDS-Finding mit 6 Duplikaten über 6 Dateien hat mehr Impact als ein EDS-Finding für 1 Funktion – auch wenn beide HIGH sind.

**Umsetzung:**
- Neues Feld `impact: float` im Finding-Modell
- Berechnung in `scoring/engine.py`: `impact = weight × score × len(locations)`
- Standard-Sortierung in allen Outputs nach `impact` absteigend
- Bestehende Sortierung nach `score` bleibt als `--sort-by score` Option

**Aufwand:** S (wenige Tage). Reine Berechnungs- und Sortierungs-Erweiterung.

---

### Optimierung 5: AVS-Signal validieren und kalibrieren (SOLL)

**Was:** Das Architecture-Violation-Signal hat nur 5 Findings im gesamten Benchmark (20% strict Precision bei n=5). Die Stichprobe ist zu klein für eine belastbare Aussage.

**Warum:** AVS hat das höchste Gewicht (0.22, geteilt mit PFS), aber die dünnste Validierung. Entweder ist das Signal zu selektiv (missed echte Violations) oder die Kalibrierung ist korrekt und Layer Violations sind in gut designten Libraries selten. Beides muss geklärt werden.

**Umsetzung:**
- Benchmark-Corpus um 3–5 Repos erweitern, die bekannte Architektur-Probleme haben (z.B. große Django-Projekte, Monolithen mit organisch gewachsenen Abhängigkeiten)
- Omnilayer-Erkennung reviewen: Werden config/utils zu großzügig als "erlaubt" markiert?
- Hub-Module-Dampening reviewen: Wird durch NetworkX in-degree zu viel gedämpft?
- Controlled Mutations: 5+ gezielte Layer Violations injizieren und Recall messen

**Aufwand:** M (1–2 Wochen – hauptsächlich manuelle Analyse und Benchmark-Erweiterung).

---

### Optimierung 6: Benchmark-Corpus auf 15–20 Repos erweitern (SOLL)

**Was:** Die Precision/Recall-Zahlen basieren auf 5 Repos. Für belastbare Aussagen und Größen-Normalisierung braucht es 15–20.

**Warum:** Mit 15–20 Repos kann drift den Score kontextualisieren ("typisch für ein Repo dieser Größe") und die Größen-Korrelation (r=0.85) adressieren. Außerdem werden Signale robuster kalibriert, wenn sie auf mehr verschiedenen Codebases getestet sind.

**Umsetzung:**
- 10–15 weitere Open-Source-Python-Repos analysieren (Mix aus Größen, Stilen, Domänen)
- Ground-Truth-Klassifikation für jeweils 30–50 Findings
- Präzision pro Signal neu berechnen über den erweiterten Corpus
- Median-Scores pro Größenkategorie berechnen für kontextualisierte Einordnung

**Aufwand:** M (2–3 Wochen – hauptsächlich manuelle Ground-Truth-Klassifikation).

---

### Optimierung 7: Score-Normalisierung nach Repo-Größe (SPÄTER)

**Was:** Den Composite Score so anpassen, dass er nicht primär von der Repo-Größe getrieben wird (aktuell r=0.85 mit log(Dateien)).

**Warum:** Erst sinnvoll wenn der Benchmark-Corpus (Optimierung 6) groß genug ist für statistisch fundierte Normalisierung. Ohne ausreichend Datenpunkte wäre jede Normalisierung willkürlich.

**Mögliche Ansätze:**
- Percentile-Ranking innerhalb von Größenkategorien (S: <100 Files, M: 100–500, L: >500)
- Regressions-Korrektur: Score − β × log(Dateien)
- Densitäts-Normierung: Findings pro 1000 LOC statt absolut

**Abhängigkeit:** Optimierung 6 (Benchmark-Corpus).

---

## 6. Priorisierungs-Übersicht

| # | Optimierung | Kategorie | Was wird besser | Aufwand |
|---|---|---|---|---|
| 1 | Handlungsempfehlungen pro Finding | **MUSS** | Jedes Finding wird direkt umsetzbar | S–M |
| 2 | Vollständige Fundstellen | **MUSS** | Kein manuelles Suchen mehr nötig | S |
| 3 | DIA Precision ≥75% | **MUSS** | Siebtes Signal wird aktivierbar | S–M |
| 4 | Impact-basierte Sortierung | **SOLL** | Wichtigstes zuerst, ohne pauschal Top-3 | S |
| 5 | AVS-Signal Validierung | **SOLL** | Höchst-gewichtetes Signal wird belastbar | M |
| 6 | Benchmark-Corpus ×3 | **SOLL** | Precision-Zahlen werden glaubwürdig | M |
| 7 | Score-Normalisierung | **SPÄTER** | Score wird Repo-Größen-unabhängig | M |

**Reihenfolge:** 1 → 2 → 3 (diese drei zusammen als nächstes Release), dann 4 + 5 parallel, dann 6, zuletzt 7.

---

## 7. Erfolgsmetriken

| Metrik | Ziel | Messmethode |
|---|---|---|
| **Finding-Precision (gesamt, strikt)** | ≥85% (aktuell 80%, exkl. DIA: 89%) | Benchmark-Suite auf erweitertem Corpus |
| **DIA-Precision** | ≥75% (aktuell 48%) | Ground-Truth auf 5+ Repos |
| **Findings mit Fix-Empfehlung** | 100% aller Findings | Automatischer Check im Test |
| **Durchschnittliche Fundstellen pro Finding** | Alle angezeigt (keine künstliche Begrenzung) | Output-Validierung |
| **Benchmark-Repos** | ≥15 (aktuell 5) | Interne Zählung |
| **AVS-Stichprobe** | ≥30 klassifizierte Findings (aktuell 5) | Benchmark-Suite |
| **PyPI Downloads** | Wachstum >20% pro Quartal | PyPI Stats |

---

## 8. Offene Risiken und Annahmen

### Risiken

| # | Risiko | Impact | Mitigation |
|---|---|---|---|
| R1 | Fix-Empfehlungen sind zu generisch ("Konsolidiere Patterns") | Hoch | Templates pro Signal mit konkreten Daten befüllen. Gegen 3 STUDY.md-Case-Studies validieren. |
| R2 | DIA-Precision bleibt auch nach Heuristik-Verbesserung unter 75% | Mittel | Signal auf Gewicht 0 belassen und als "experimental" markieren. Kein Grund zum Forcen. |
| R3 | Score-Größen-Korrelation verunsichert Nutzer großer Repos | Mittel | Bis Normalisierung steht: Hinweis im Output ("Score für Repos mit >500 Dateien typischerweise 0.45–0.65"). |
| R4 | Vollständige Fundstellen-Listen werden bei großen Repos unübersichtlich | Niedrig | Threshold: Rich-Output zeigt max. 10, dann Zusammenfassung. JSON immer vollständig. |

### Annahmen

| # | Annahme | Validierung |
|---|---|---|
| A1 | Fix-Empfehlungen direkt am Finding sind wertvoller als ein separater Top-N-Plan | Nutzer-Feedback auf Show HN / Reddit |
| A2 | Die für Fix-Empfehlungen benötigten Daten sind in den Signalen bereits vorhanden | Review der Signal-Ausgaben bestätigt dies für MDS, PFS, AVS, EDS, TVS |
| A3 | DIA-False-Positives sind primär URL-Fragmente (behebbar durch Heuristik) | STUDY.md §3.3 benennt dies als Hauptquelle |
| A4 | 15–20 Repos reichen für belastbare Precision-Aussagen pro Signal | Statistisch: ≥30 Findings pro Signal bei 15 Repos erwartet |

---

## 9. Nicht-Ziele (explizit ausgeschlossen)

- **Kein History-Store / Trend-Tracking / Datenbank.** drift bleibt ein stateless CLI-Tool.
- **Kein LLM in der Pipeline.** Auch nicht opt-in. Die Stärke ist Determinismus und Geschwindigkeit.
- **Keine neuen CLI-Befehle.** Die bestehenden (`analyze`, `check`, `self`, `patterns`, `badge`) reichen.
- **Keine PR-Level-Analyse.** `drift check --diff` existiert bereits – das reicht für CI.
- **Keine Produkt-Infrastruktur** (Telemetrie, Accounts, Dashboards, Remote Services).
- **Kein Scope-Creep in Richtung generische Code-Qualität.** drift misst Drift, nicht Bugs.
