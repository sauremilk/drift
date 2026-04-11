---
id: ADR-035
status: proposed
date: 2026-04-09
supersedes:
---

# ADR-035: Per-Repo Signal Calibration via Statistical Feedback Integration

## Kontext

Drift-Signale verwenden universelle Default-Weights, die aus Ablation-Benchmarks abgeleitet wurden. In der Praxis variiert die Relevanz einzelner Signale jedoch stark nach Projekt-Typ: Guard-Clause-Deficit ist in einem API-Handler kritisch, in einem Datenverarbeitungs-Skript dagegen strukturell anders. Ohne projektspezifische Kalibrierung entstehen vermeidbare False Positives.

Gleichzeitig liegen in jedem Repo bereits Outcome-Daten vor, die bisher nicht systematisch genutzt werden:

- **Git-History**: Korrelation zwischen Drift-Findings und nachfolgenden Bug-Fix-Commits
- **Explizites Feedback**: `drift:ignore` Inline-Suppressions als implizite FP-Signale
- **GitHub Issues/PRs**: Bug-Labels auf Issues, die über Fix-Commits mit Dateien korrelieren

Ziel: Ein per-Repo kalibriertes Gewichtungsprofil, das nach 4–6 Wochen Feedback-Sammlung höhere Precision liefert als universelle Defaults — ohne ML, rein statistisch (Bayesian Weight-Update).

## Entscheidung

### Wird getan

1. **Neues Package `src/drift/calibration/`** mit folgenden Modulen:
   - `feedback.py` — `FeedbackEvent` Datenmodell + append-only JSONL-Persistenz
   - `history.py` — Scan-History-Snapshots für retrospektive Korrelation
   - `outcome_correlator.py` — Git-Defect → Finding-Korrelation
   - `github_correlator.py` — GitHub API Issue/PR → Finding-Korrelation
   - `profile_builder.py` — Bayesian Evidence-Aggregation + Weight-Berechnung

2. **Bayesian Weight-Update pro Signal:**
   ```
   n = TP + FP                              # beobachtete Stichprobe
   confidence = min(1.0, n / min_samples)   # min_samples ≈ 20
   precision_est = TP / max(1, n)           # beobachtete Precision
   calibrated = (1 - confidence) × default + confidence × precision_est × default
   ```
   Cold-Start (confidence = 0): identisch zu Default-Weights.

3. **Drei Evidence-Quellen (priorisiert):**
   - Explizites User-Feedback (`drift feedback --mark tp/fp/fn`)
   - Git-Outcome-Korrelation (Bug-Fix-Commits innerhalb Korrelationsfenster)
   - GitHub Issue/PR Labels (opt-in, Token erforderlich)

4. **Persistenz in `drift.yaml`** — kalibrierte `weights:` Section mit Audit-Trail-Kommentar. Existing manuelle Overrides werden respektiert.

5. **CLI-Commands:** `drift feedback` (Feedback erfassen), `drift calibrate` (Profil berechnen)

6. **MCP-Tools:** `drift_feedback`, `drift_calibrate`

7. **Config-Erweiterung:** `CalibrationConfig` (opt-in, `calibration.enabled: false` by default)

### Wird explizit nicht getan

- Kein ML/LLM — rein deterministisch, reproduzierbar
- Keine automatische GitHub-API-Nutzung ohne expliziten Token
- Kein Überschreiben manueller Weight-Overrides in drift.yaml
- Keine Änderung an bestehender Signal-Logik
- Kein neues Signal — nur Gewichtungs-Kalibrierung bestehender Signale

## Begründung

**Warum Bayesian statt ML:**
- Deterministisch und reproduzierbar (Policy-Anforderung §13)
- Kein externes Modell-Dependency
- Cold-Start-sicher (fällt auf Defaults zurück)
- Mathematisch nachvollziehbar pro Signal

**Warum drei Datenquellen:**
- Git-Korrelation liefert passives TP-Evidence ohne User-Aufwand
- Explizites Feedback ist hochpräzise aber erfordert Interaktion
- GitHub-API schließt die Lücke zwischen Bugs und Findings

**Warum drift.yaml statt separate Profil-Datei:**
- Versioniert im Git → Team sieht Änderungen im Review
- Keine separate Datei zum Synchronisieren
- Bestehende Config-Infrastruktur wiederverwendbar

**Verworfene Alternativen:**
- Separate `.drift/profile.json` — zusätzlicher Sync-Aufwand, nicht reviewbar
- ML-basiertes Modell — zu komplex, nicht reproduzierbar, Dependency-Overhead
- Nur inline-Suppression auswerten — zu wenig Daten, keine TP-Evidence

## Konsequenzen

- **Neue Trust Boundary:** GitHub API (opt-in, Token-basiert) → STRIDE-Update Pflicht
- **Neue Input-Pfade:** `.drift/feedback.jsonl`, `.drift/history/` → STRIDE-Update
- **Backward-kompatibel:** Ohne `calibration:` Block identisches Verhalten
- **Audit-Pflicht:** FMEA (Kalibrierungs-FP: falsche Gewichtung), Risk Register
- **Profil-Staleness:** Kalibrierung verfällt über Zeit → `decay_days` + Warning
- **Team-Divergenz möglich:** Verschiedene Team-Mitglieder erzeugen verschiedenes Feedback → drift.yaml merge conflicts

## Validierung

```bash
# Unit-Tests: Bayesian-Logik mit synthetischen Events
pytest tests/test_calibration.py tests/test_profile_builder.py -v

# Cold-Start: keine Events → exakt Default-Weights
pytest tests/test_calibration.py -k "cold_start" -v

# Integration: feedback → calibrate → weights geändert
pytest tests/test_calibration.py -k "integration" -v

# Regression: kalibrierte Weights nicht schlechter als Defaults auf Ground Truth
pytest tests/test_precision_recall.py -v

# Selbstanalyse stabil
drift analyze --repo . --format json --exit-zero
```

Lernzyklus-Ergebnis: `unklar` — wird nach 4–6 Wochen Feldtest evaluiert.
