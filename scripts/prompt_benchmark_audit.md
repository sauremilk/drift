# Benchmark-Audit Prompt für Claude Opus 4.6

> **Zweck:** Copy-Paste in ein neues Claude-Gespräch. Alle relevanten Artefakte als Kontext anhängen.
> **Ziel:** Kritische methodische Analyse der Drift-Benchmark-Suite für belastbare empirische Aussagen.

---

## Prompt (ab hier kopieren)

```
Du bist ein methodischer Gutachter für empirische Software-Engineering-Studien.
Deine Aufgabe: Analysiere die Benchmark-Suite des statischen Analysers "Drift"
kritisch auf methodische Fehler, Verzerrungen, Validitätsbedrohungen und
logische Lücken — mit dem expliziten Ziel, dass die Ergebnisse als belastbarer
empirischer Nachweis verwendbar werden sollen.

Drift ist ein statischer Analyser für architektonische Kohärenz in Python/TS-
Codebases. Er erkennt 10 Signale (7 aktive, 3 report-only):
PFS (Pattern Fragmentation), AVS (Architecture Violation), MDS (Mutant Duplicates),
EDS (Explainability Deficit), TVS (Temporal Volatility), SMS (System Misalignment),
DIA (Doc-Implementation Drift), BEM, TPD, GCD.

Die Benchmark-Suite besteht aus 6 Ebenen:
1. Ground-Truth-Precision (15 reale Repos, automatische Klassifikation)
2. Controlled Mutation Benchmark (synthetisches Repo, 41 injizierte Muster)
3. Ground-Truth-Fixture-Testframework (15 deterministische Mikro-Fixtures)
4. Leave-One-Out Cross-Validation (Gewichtskalibrierung)
5. Sensitivity Analysis (Gewichtsstabilität bei ±50% Variation)
6. External Blind Validation (3 unbekannte Repos: httpie, arrow, frappe)

═══════════════════════════════════════════════════════════════════════
ANALYSEAUFTRAG — Prüfe jede der folgenden Dimensionen einzeln und gib
für jede ein Urteil ab: [BELASTBAR], [EINSCHRÄNKUNG], [KRITISCH].
═══════════════════════════════════════════════════════════════════════

### A. GROUND-TRUTH-KLASSIFIKATION (scripts/ground_truth_analysis.py)

Die Klassifikation TP/FP/Disputed erfolgt AUTOMATISCH durch Heuristiken,
NICHT durch manuelle Annotation. Prüfe:

A1. Zirkelschluss-Risiko: classify_finding() nutzt score-Schwellenwerte des
    Tools selbst als Wahrheitskriterium. Beispiel:
      - MDS: score >= 0.85 → TP
      - EDS: score >= 0.5 → TP ("structural correctness by definition")
      - TVS: score >= 0.5 → TP
      - SMS: score >= 0.8 → TP
    Ist das ein klassischer Zirkelschluss (Tool validiert sich selbst)?
    Wie gravierend ist das für die behauptete 97.3% Precision?

A2. Klassifikations-Asymmetrie: Die Heuristiken sind konservativ bei FP
    (nur DIA hat explizite FP-Regeln), aber liberal bei TP (hohe Scores
    werden pauschal als TP akzeptiert). Wie verzerrt das die Precision?

A3. Single-Rater-Bias: Es gibt keinen zweiten Annotator und kein Inter-
    Rater-Agreement (Cohen's κ). Die Heuristiken wurden vom Tool-Autor
    geschrieben. Wie bewertest du die externe Validität?

A4. Sampling-Bias: Stratifiziertes Sampling nimmt die Top-15-Findings pro
    (Signal, Repo), sortiert nach Score. Das heißt, die besten Findings
    werden bewertet. Wie verzerrt das die Gesamtpräzision?

A5. Label-Abdeckung: 263 von 2642 Findings (10%) sind gelabelt. Ist das
    ausreichend für die behaupteten Precision-Statements? Welche
    statistische Konfidenz ergibt sich daraus?

A6. Signal-Heterogenität: AVS hat nur 5 Samples, DIA hat 61 aber 48%
    Precision. Dürfen diese mit PFS (100%, n=49) zu einer Gesamtzahl
    von 97.3% aggregiert werden?

### B. MUTATION BENCHMARK (scripts/mutation_benchmark.py)

B1. Ökologische Validität: Die 41 Mutationen werden in ein synthetisches
    Repo injiziert, das vom Tool-Autor für das Tool designed wurde.
    Wie repräsentativ sind diese Mutationen für echte Codebasen?

B2. Schwellenwert-Sensitivität: 2 von 14 Mutationen werden nicht erkannt
    (PFS-Return-Value-Varianten "below threshold"). Recall 86% klingt
    gut, aber: Wurden die Mutationen auf die Schwellenwerte hin
    konstruiert? Wie hoch wäre Recall bei echt vorkommendem Drift?

B3. Abdeckung: 41 Mutationen für 7 Signale = ~6 pro Signal. Gibt es
    Signal-Typen mit nur 2-3 Mutationen? Ist das genug für eine
    Recall-Aussage?

B4. Schwierigkeitsverteilung: Sind die Mutationen bewusst "einfache"
    Fälle (exakte Duplikate, offensichtliche Violations)? Gibt es
    Grenzfälle, subtile Patterns, Near-Miss-Szenarien?

### C. GROUND-TRUTH-FIXTURE-FRAMEWORK (tests/fixtures/ground_truth.py)

C1. Tautologie-Risiko: Die Fixtures definieren "expected findings" und
    der Test prüft, ob genau diese gefunden werden. Wenn Fixtures VOM
    SELBEN Entwickler wie Signale geschrieben wurden — testen die dann
    den Analyser oder nur die Fixture-Signal-Konsistenz?

C2. F1=1.00: Alle 15 Fixtures haben perfekte F1. Sind die Fixtures
    so einfach, dass sie keine Diskriminationskraft haben? Was passiert
    bei Grenzfällen, Ambiguität, Kontextabhängigkeit?

C3. Fixture-Repräsentativität: 15 Mikro-Fixtures vs. reale Codebases
    mit 100k+ LoC. Wie groß ist die Generalisierungslücke?

### D. LEAVE-ONE-OUT CROSS-VALIDATION (scripts/holdout_validation.py)

D1. Overfit-Risiko: 15 Datenpunkte für 7 Gewichte. Das Verhältnis
    Samples/Parameter (15/7 ≈ 2.1) ist extrem klein. Ist LOOCV
    hier die richtige Methode oder simuliert sie nur Generalisation?

D2. F1=1.00 auf allen Folds: Wenn das Modell auf JEDEM Fold perfekt ist,
    liegt das an guter Generalisierung oder daran, dass die Fixtures
    zu einfach und die Signale zu orthogonal sind?

D3. Gewichtsstabilität: σ ≈ 0.03–0.05 pro Signal wird als Nachweis für
    Stabilität gewertet. Aber bei n=15 und monotoner Fixture-Leichtigkeit
    — hat σ hier überhaupt statistische Aussagekraft?

### E. SENSITIVITY ANALYSIS (scripts/sensitivity_analysis.py)

E1. ±50% Variation: Ist das realistisch? Wenn Gewichte nur wenig variiert
    werden müssen, um Ranking-Änderungen zu erzeugen, ist das dann
    stabil oder fragil?

E2. Spearman ρ auf 15 Repos: n=15 für Rangkorrelation ist grenzwertig.
    Welche Power hat der Test? Kann man aus ρ bei n=15 Stabilität ableiten?

### F. EXTERNAL BLIND VALIDATION

F1. 100% Precision auf 373 Findings (httpie, arrow, frappe): Klingt
    perfekt. Wie wurde "TP" bei diesen 3 Repos bestimmt? Dieselben
    automatischen Heuristiken wie in A1?

F2. 3 Repos als "blind" → reicht das als External-Validity-Nachweis?
    Wie wurden die 3 ausgewählt? Gibt es Selektionsbias?

### G. AGGREGATIONSLOGIK UND BEHAUPTUNGEN

G1. "97.3% Precision" wird prominent kommuniziert (STUDY.md, README,
    docs-site). Ist diese Zahl angesichts von A1-A6 belastbar? Wenn
    nein: was wäre eine ehrliche Reformulierung?

G2. "86% Recall" basiert auf synthetischen Mutationen. Ist das als
    Recall-Metrik im klassischen IR-Sinne zitierbar?

G3. Bekannte Schwächen (DIA 48%, AVS 20% strict, AI-attribution 0%)
    werden in STUDY.md §7 als "Threats to Validity" genannt. Reicht
    Transparenz als Mitigation, oder müssen die schwachen Signale
    aus der Gesamtasgabe entfernt werden?

### H. REPRODUZIERBARKEIT

H1. Git-Stabilität: Benchmark nutzt --depth 50 für Clones. Wie beeinflusst
    die zeitliche Veränderung der Repos die Reproduzierbarkeit? Werden
    konkrete Commit-SHAs gespeichert?

H2. Versionsgebunden: Werden die Benchmark-Ergebnisse an eine bestimmte
    Drift-Version gebunden und getaggt?

H3. Determinismus: Drift behauptet vollständige Determiniertheit. Gibt
    es Quellen von Nichtdeterminismus (z.B. Dateisystem-Reihenfolge,
    Dictionary-Ordering)?

═══════════════════════════════════════════════════════════════════════
AUSGABEFORMAT
═══════════════════════════════════════════════════════════════════════

Für jede Dimension (A–H) und jede Unterfrage:

1. **Befund**: Beschreibe das Problem oder die Stärke konkret.
2. **Bewertung**: [BELASTBAR] / [EINSCHRÄNKUNG] / [KRITISCH]
   - BELASTBAR = methodisch solide, kein relevanter Bias
   - EINSCHRÄNKUNG = akzeptabel wenn transparent dokumentiert
   - KRITISCH = gefährdet die Aussagekraft grundlegend
3. **Empfehlung**: Was muss geändert werden, damit die Aussage
   wissenschaftlich zitierbar wird?

Am Ende:

### GESAMTURTEIL
- Precision-Aussage belastbar: [JA/NEIN/BEDINGT]
- Recall-Aussage belastbar: [JA/NEIN/BEDINGT]
- Empfohlene Reformulierungen für belastbare Kommunikation
- Priorisierte Liste: Top-5 Maßnahmen, die den Benchmark am meisten stärken würden
- Einschätzung: Welche Behauptungen können JETZT empirisch belastbar gemacht werden,
  welche brauchen zusätzliche Evidenz?
```

---

## Anhänge die du dem Prompt beifügen solltest

Hänge folgende Dateien als Kontext an das Claude-Gespräch an:

| Datei | Zweck |
|-------|-------|
| `scripts/ground_truth_analysis.py` | Automatische TP/FP-Klassifikation |
| `scripts/mutation_benchmark.py` | Synthetische Mutationen + Recall |
| `scripts/holdout_validation.py` | LOOCV-Gewichtsvalidierung |
| `scripts/sensitivity_analysis.py` | Gewichtssensitivität |
| `scripts/evaluate_benchmark.py` | Precision-Evaluierung |
| `scripts/benchmark.py` | Benchmark-Runner (15 Repos) |
| `tests/fixtures/ground_truth.py` | 15 Mikro-Fixtures |
| `benchmark_results/ground_truth_analysis.json` | Precision-Ergebnisse |
| `benchmark_results/mutation_benchmark.json` | Recall-Ergebnisse |
| `benchmark_results/holdout_validation.json` | LOOCV-Ergebnisse |
| `benchmark_results/all_results.json` | 15-Repo-Zusammenfassung |
| `STUDY.md` | Empirische Studie (publizierte Behauptungen) |
| `EPISTEMICS.md` | Erkenntnistheoretische Grenzen |
| `docs-site/trust-evidence.md` | Öffentliche Trust-Claims |

> **Hinweis**: Claude Opus 4.6 hat ein 200k-Token-Kontextfenster. Alle obigen
> Dateien zusammen sind deutlich unter 50k Tokens — es passt alles in einen
> einzelnen Turn.
