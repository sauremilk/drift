---
id: ADR-018
status: proposed
date: 2026-04-07
supersedes:
---

# ADR-018: AVS co_change Precision Hardening (FTA-basiert)

## Kontext

Eine Fault Tree Analysis des `avs_co_change`-Sub-Checks identifiziert drei dominierende Minimal Cut Sets für False Positives:

- **MCS-1 (RPN 144, SPOF):** Same-Package-Ko-Evolution — Geschwisterdateien im selben Paketverzeichnis (z.B. `signals/foo.py` ↔ `signals/bar.py`) co-ändern sich natürlich, ohne dass ein Cross-Boundary-Koppelungsproblem besteht. `_check_co_change` enthält keine Guard-Condition für `os.path.dirname(file_a) == os.path.dirname(file_b)`. Erklärt 7/10 Disputed-Fälle.

- **MCS-2 (RPN 60, SPOF):** Test-Source-Filtering-Inkonsistenz — `known_files` wird aus ungefiltertem `parse_results` gebaut (enthält Testdateien), der Import-Graph wird aus `filtered_prs` gebaut (ohne Testdateien). `has_edge(test_file, source_file)` ist damit strukturell immer `False` — der Suppressor ist blind für Test-Source-Paare. Erklärt 1–2/10 Disputed.

- **MCS-3 (RPN 120):** Bulk-Commit-Inflation — Release/Sweep-Commits berühren viele Dateien gleichzeitig. Die Confidence-Formel in `build_co_change_pairs` gewichtet jeden Commit gleich, unabhängig von der Dateizahl. Hard-Cut bei >20 reicht nicht für Commits mit 10–19 Dateien. Erklärt ~2/10 Disputed.

**Common Causes:**
- CC-1: `known_files` und `filtered_prs` divergieren durch inkonsistente Filter-Anwendung → betrifft MCS-1 + MCS-2
- CC-2: `_check_co_change` kennt keinen Namespace-/Package-Kontext → betrifft MCS-1 + MCS-3

**Evidenz:** 10/10 Disputed in `drift_self`-Stichprobe, `precision_strict = 0.3`, n=20 Findings (2026-03-25). Die Precision-Krise ist vollständig im Sub-Check `avs_co_change` lokalisiert — `avs_circular_dep` und `avs_blast_radius` produzieren ausschließlich TPs.

## Entscheidung

Drei unabhängige Fixes werden implementiert, in Reihenfolge absteigender RPN × SPOF-Eigenschaft:

### Fix 1: Same-Directory Guard in `_check_co_change` (MCS-1)

Vor dem Finding-Append wird geprüft, ob beide Dateien im selben Verzeichnis liegen UND dieses Verzeichnis mindestens 2 Pfad-Segmente hat (kein Root-Level). Wenn ja → `continue`.

```python
# Suppress same-directory co-evolution (sisters in a package)
dir_a = str(PurePosixPath(pair.file_a).parent)
dir_b = str(PurePosixPath(pair.file_b).parent)
if dir_a == dir_b and dir_a != ".":
    continue
```

Der `!= "."` Check schützt Flat-Root-Repos vor FN: Dateien im Root-Level werden weiterhin geprüft.

### Fix 2: `known` aus `filtered_prs` statt `parse_results` (MCS-2)

Eine Zeile in `analyze()`:
```python
# vorher: known = {pr.file_path.as_posix() for pr in parse_results}
known = {pr.file_path.as_posix() for pr in filtered_prs}
```

Testdateien werden damit konsistent aus Co-Change-Analyse UND Import-Graph ausgeschlossen.

### Fix 3: Commit-Größen-Diskontierung in `build_co_change_pairs` (MCS-3)

Jeder Commit wird invers nach Dateizahl gewichtet:
```python
weight = 1.0 / max(1, len(files) - 1)
```

Chirurgische Commits (2 Files) → volle Gewichtung (1.0). 15-File-Commits → 0.07. Die bestehende Hard-Cut-Grenze (>20) bleibt als Belt-and-Suspenders erhalten.

`CoChangePair.co_change_count` und `total_commits_*` bleiben `int` (gerundet) für API-Kompatibilität. Die interne Berechnung nutzt floats.

**Explizit nicht umgesetzt:**
- MCS-4 (latent: `models.py` → Layer 2 cross-cutting) — kein Disputed-Nachweis, niedrigster RPN (48). Separates ADR bei Evidenz.
- Alternative `1/sqrt(n)` Diskont-Kurve — sanftere Kurve, aber schwerer kalibrierbar. Einfache Inverse als Erstansatz, Anpassung nach Benchmark.

## Begründung

- MCS-1 hat den höchsten RPN (144) und ist SPOF — eine einzige fehlende Guard-Condition verursacht 7/10 FPs. Der Same-Directory-Guard ist chirurgisch und hat minimalen FN-Impact (nur Flat-Root-Repos ausgenommen via `!= "."`).
- MCS-2 ist Root Cause CC-1 — eine Zeile behebt die Filter-Inkonsistenz. FN-Risiko minimal (Testdateien hatten ohnehin keinen Edge im Graph).
- MCS-3 adressiert den blinden Fleck des >20-Hard-Cuts für mittlere Commits (10–19 Files). Die inverse Gewichtung ist das einfachste Modell mit klarer Kalibrierbarkeit.

## Konsequenzen

- **Precision steigt** von ~0.3 auf ≥0.7 (geschätzt: MCS-1 eliminiert 7 FPs, MCS-2 eliminiert 1–2 FPs, MCS-3 reduziert ~2 FPs).
- **Minimales FN-Risiko:**
  - Fix 1: Flat-Root-Repos behalten Erkennung (Root-Level ausgenommen). Echte Cross-Package-Kopplungen leben in verschiedenen Verzeichnissen.
  - Fix 2: Test-Source Co-Changes waren nie suppressbar (Graph hatte keine Test-Edges) → keine Verhaltensänderung für TPs.
  - Fix 3: Chirurgische Commits behalten volle Gewichtung. Nur inflated Bulk-Commits verlieren Gewicht.
- **API-Stabilität:** `CoChangePair` Felder bleiben int-typisiert; `build_co_change_pairs` Signatur unverändert.
- **Audit-Updates:** FMEA, Fault Trees, Risk Register müssen parallel aktualisiert werden (Policy §18).

## Validierung

```bash
pytest tests/test_architecture_violation.py -v --tb=short
pytest tests/test_precision_recall.py -v --tb=short
drift analyze --repo . --format json --exit-zero
```

- 4 neue Regressionstests (je einer pro MCS + 1 FN-Schutztest)
- precision_strict(avs_co_change) ≥ 0.7 auf drift_self
- Bestehende AVS-Tests weiterhin grün
- Lernzyklus-Ergebnis: **unklar** (wird nach Merge an realen Repos validiert)
