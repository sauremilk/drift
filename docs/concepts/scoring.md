# Scoring

Der Drift-Score ist die zentrale Kennzahl, die architektonische Erosion auf einer einzigen Skala von 0.0 bis 1.0 zusammenfasst. Diese Seite erklärt, wie er berechnet wird, was die Schwellwerte bedeuten und wie du ihn beeinflussen kannst.

---

## Wie wird der Drift-Score berechnet?

Die Score-Berechnung besteht aus drei Stufen:

### Stufe 1: Finding Score (pro Befund)

Jedes `Finding` erhält einen Score zwischen 0.0 und 1.0, der die Konfidenz und Stärke des erkannten Musters widerspiegelt. Dieser Score ist Signal-spezifisch — PFS beispielsweise berechnet ihn aus der Anzahl inkompatible Varianten und ihrer Haesslichkeits-Schwere, AVS aus der Layer-Verletzungstiefe.

### Stufe 2: Signal-aggregierter Score (pro Signal)

Die Finding-Scores jedes aktiven Signals werden zu einem per-Signal-Score aggregiert:

$$\text{signal\_score}(s) = \text{mean}(\text{scores}_s) \times \min\!\left(1,\; \frac{\ln(1 + n)}{\ln(1 + k)}\right)$$

Dabei ist:
- $n$ die Anzahl der Findings dieses Signals
- $k = 20$ — der Count-Dampening-Konstante

Die logarithmische Dämpfung verhindert, dass ein prolifikales Signal mit vielen schwachen Findings den Gesamtscore dominiert. Ein einzelner hochkonkfidenter Befund trägt weniger bei als viele moderate — aber das Verhältnis ist sublinear, nicht linear.

### Stufe 3: Composite Score (Repository-Gesamtscore)

Der Composite Score ist eine gewichtete Summe aller Signal-Scores, normiert auf die Summe der aktiven Gewichte:

$$\text{drift\_score} = \min\!\left(1.0,\; \frac{\sum_s w_s \cdot \text{signal\_score}(s)}{\sum_s w_s}\right)$$

Nur Signale mit `weight > 0.0` gehen in den Score ein. Signals mit `weight = 0.0` sind report-only.

### Impact-Score (pro Finding)

Zusätzlich wird für jedes Finding ein `impact`-Wert berechnet, der seinen Anteil am Composite Score schätzt:

$$\text{impact} = w_s \times \text{score} \times \min\!\left(4.0,\; 1 + \ln(1 + \text{related\_file\_count})\right)$$

Der logarithmische Breadth-Multiplier belohnt Findings, die viele Dateien betreffen — aber mit einer Deckelung bei 4.0, um extreme Inflation bei sehr großen Clustern zu verhindern.

---

## Was bedeuten die Schwellwerte?

Der Composite Score wird auf fünf Severity-Stufen abgebildet:

| Score-Bereich | Severity | Bedeutung |
|---------------|----------|-----------|
| 0.0 – 0.19 | `info` | Keine nennenswerte Erosion nachweisbar |
| 0.2 – 0.39 | `low` | Erste Anzeichen struktureller Inkohärenz |
| 0.4 – 0.59 | `medium` | Spürbare Erosion; empfehlenswert zu adressieren |
| 0.6 – 0.79 | `high` | Signifikante strukturelle Risiken |
| 0.8 – 1.0 | `critical` | Kritische Erosion; sollte vor weiterer Entwicklung adressiert werden |

Diese Schwellwerte sind fest im Code verankert (`severity_for_score()` in `models.py`) und unabhängig von der Konfiguration. Was dagegen konfigurierbar ist: der `--fail-on`-Schwellwert in CI, der bestimmt, ab welcher Severity ein Build fehlschlägt.

**Empfehlung für den Einstieg:**

| Team-Phase | `fail-on`-Empfehlung |
|------------|---------------------|
| Neue Codebase | `high` — Nur echte Strukturprobleme blockieren |
| Laufendes Projekt | `medium` — Nach Baseline-Einführung |
| Kritische Infrastruktur | `critical` oder `high` mit spezifischen Signals |

---

## Wie beeinflusst Signal-Gewichtung den Score?

Die Standardgewichte sind so kalibriert, dass Signals mit dem höchsten Strukturrisiko das größte Gewicht haben:

```
PFS (Pattern Fragmentation): 0.16  — Höchstes Gewicht (AI-typisches Muster)
AVS (Architecture Violation): 0.16  — Höchstes Gewicht (Layer-Integrität)
MDS (Mutant Duplicate):       0.13
EDS (Explainability Deficit):  0.09
SMS (System Misalignment):     0.08
TPD (Test Polarity Deficit):   0.04
DIA (Doc/Impl Drift):          0.04
BEM (Broad Exception):        0.04
NBV (Naming Contract):        0.04
GCD (Guard Clause Deficit):    0.03
BAT (Bypass Accumulation):     0.03
ECM (Exception Contract):      0.03
COD (Cohesion Deficit):        0.01
CCC (Co-Change Coupling):      0.005
```

**Beispiel:** Ein einzelnes kritisches PFS-Finding mit Score 0.85 trägt mehr bei als fünf schwache TPD-Findings mit Score 0.25, weil PFS dreimal so stark gewichtet ist.

**Modularer Score:** Neben dem Repository-Gesamtscore berechnet drift auch per-Modul-Scores, die zeigen, in welchem Verzeichnis die stärkste Erosion vorliegt.

---

## `drift calibrate` und `drift precision`

### `drift calibrate`

Wenn die Standardgewichte nicht zu eurem Projekt passen (z. B. weil ihr in einer frühen KI-intensiven Phase seid oder einen stark regulierten Legacy-Stack habt), berechnet `drift calibrate run` aus eurem gesammelten Feedback projektspezifische Gewichte:

```bash
drift calibrate run          # Kalibrierung berechnen, Ergebnis anzeigen
drift calibrate run --apply  # Gewichte direkt in drift.yaml schreiben
drift calibrate status       # Aktuellen Kalibrierungsstatus anzeigen
drift calibrate reset        # Auf Standardgewichte zurücksetzen
```

Feedback wird durch das Markieren von Findings als false positive (FP) oder confirmed gesammelt, typischerweise über `drift feedback` oder den MCP-Server.

### `drift precision`

`drift precision` führt eine Präzisions-/Recall-Evaluation gegen Ground-Truth-Fixtures aus. Es ist das Werkzeug für Maintainer und fortgeschrittene Nutzer, die die Signal-Güte messen und kalibrieren wollen:

```bash
drift precision              # Precision/Recall-Report für alle Signals
drift precision --signal PFS # Nur für ein Signal
```

Der Report zeigt pro Signal, wie viele True Positives, False Positives und False Negatives in den Standard-Fixtures erkannt werden — und damit, ob eine Gewichtsanpassung gerechtfertigt ist.

---

## Nächste Schritte

- [**signals.md**](signals.md) — Alle Signals und ihre Gewichte im Detail
- [**baseline.md**](baseline.md) — Score-Entwicklung über Zeit mit Baselines verfolgen
- [**diagnosis-vs-navigation.md**](diagnosis-vs-navigation.md) — Wann scoring-basierte Diagnose vs. Navigations-Modus
- [**../guides/ci-integration.md**](../guides/ci-integration.md) — `--fail-on` in CI-Pipelines einsetzen
