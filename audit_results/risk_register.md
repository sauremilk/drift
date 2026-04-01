# Risk Register — drift-analyzer

> **Operatives Risikomanagement** nach AI-RMF-Struktur (Govern → Map → Measure → Manage).
> Konsolidiert Risiken aus FMEA, STRIDE und FTA.
> Lebendes Dokument — Review quartalsweise und bei jedem Minor-Release.

**Erstellt:** 2026-04-01  
**Framework:** NIST AI RMF Playbook (adaptiert für deterministische Static-Analysis-Tools)  
**Input:** `fmea_matrix.md`, `stride_threat_model.md`, `fault_trees.md`

---

## 1. GOVERN — Steuerung und Governance

### 1.1 Geltungsbereich

Dieses Risk Register gilt für drift-analyzer als:
- CLI-Tool auf lokalen Rechnern und CI-Runnern
- GitHub Action in öffentlichen und privaten Repositories
- MCP-Server in IDE-Integrationen (VS Code)

### 1.2 Verantwortlichkeiten

| Rolle | Verantwortung | Aktuell |
|-------|---------------|---------|
| **Maintainer** | Risk-Register-Pflege, Maßnahmen-Umsetzung, Release-Entscheidungen | @sauremilk |
| **Signal-Owner** | Precision/Recall pro Signal überwachen; FMEA-Einträge aktualisieren | Maintainer (bis Team wächst) |
| **Security-Contact** | STRIDE-Review bei Architekturänderungen; Advisory-Triage | Maintainer |

### 1.3 Bindung an POLICY.md

- **Prioritätsordnung:** Glaubwürdigkeit > Signalpräzision > Verständlichkeit > FP/FN-Reduktion > Einführbarkeit > Trend > Features
- **Admissibility-Gate:** Jede Risiko-Maßnahme muss POLICY §8 erfüllen (reduziert Unsicherheit, verbessert Signal, erhöht Glaubwürdigkeit)
- **Befund-Qualität §13:** Nachvollziehbarkeit, Reproduzierbarkeit, Ursachenzuordnung, Begründung, nächste Maßnahme

### 1.4 Entscheidungsregel

> Risiken werden nach der Policy-Priorisierungsformel bewertet:  
> `Priorität = (Unsicherheit × Schaden × Nutzbarkeit) / Aufwand`  
> Bei Gleichstand: größte Unsicherheitsreduktion gewinnt (POLICY §16)

---

## 2. MAP — Risiko-Landkarte

### 2.1 Risiko-Kategorien

| Kategorie | Beschreibung | Primäres Framework |
|-----------|-------------|-------------------|
| **RQ** — Erkennungsqualität | False Positives, False Negatives, Precision/Recall | FMEA |
| **RS** — Sicherheit | Angriffsvektoren, Information Disclosure, DoS | STRIDE |
| **RD** — Degradation | Stille Unvollständigkeit, Parser-Fehler, Timeouts | FTA |
| **RC** — Kontext | Repo-Typ-Mismatch (Library, Monorepo, Minimal) | FMEA + FTA |
| **RM** — Messung | Benchmark-Verzerrung, Ground-Truth-Bias, Disputed Findings | AI-RMF |
| **RO** — Operativ | Release-Risiken, CI-Kompatibilität, Dependency-Supply-Chain | AI-RMF |

### 2.2 Risiko-Heatmap

```
         Wahrscheinlichkeit →
         Niedrig    Mittel    Hoch
    H  ┌──────────┬──────────┬──────────┐
    o  │          │ RQ-03    │ RQ-01    │  ← Hoch: FP/FN mit
    c  │ RS-02    │ RQ-04    │ RC-01    │     direktem Vertrauens-
    h  │          │ RS-01    │          │     verlust
       ├──────────┼──────────┼──────────┤
 S  M  │          │ RD-01    │ RQ-02    │  ← Mittel: Qualitäts-
 c  i  │ RS-03    │ RM-01    │ RQ-05    │     minderung, aber
 h  t  │ RO-01    │ RM-02    │          │     kompensierbar
 w  t  ├──────────┼──────────┼──────────┤
 e  e  │          │          │          │  ← Niedrig: Edge Cases,
 r  l  │ RD-02    │          │          │     geringe Auswirkung
 e     │ RS-04    │          │          │
       └──────────┴──────────┴──────────┘
```

---

## 3. MEASURE — Metriken und Schwellen

### 3.1 Metriken-Framework

| Metrik | Messverfahren | Datenquelle | Frequenz | Schwelle |
|--------|--------------|-------------|----------|----------|
| **Precision (strict)** | TP / (TP + FP) auf Ground-Truth-Labels | `ground_truth_labels.json` | Pro Release | ≥ 0.70 gesamt; ≥ 0.50 pro Signal |
| **Precision (lenient)** | TP / (TP + FP + Disputed als TP) | `ground_truth_analysis.json` | Pro Release | ≥ 0.90 gesamt |
| **Recall (Mutation)** | Detected / Injected auf synthetischen Mutationen | `mutation_benchmark.json` | Pro Release | ≥ 0.80 gesamt; ≥ 0.50 pro Signal |
| **Macro-F1** | Arithm. Mittel der Signal-F1-Werte | `test_precision_recall.py` | Pro Commit (CI) | ≥ 0.50 (aktueller Gate) |
| **FP-Rate pro Signal** | FP / Total pro Signal auf 3+ Repos | Signal-Audit (manuell) | Pro Minor-Release | ≤ 30%; bei >50% → report-only |
| **Disputed-Rate** | Disputed / Total | `ground_truth_analysis.json` | Pro Release | ≤ 15% (aktuell: 15.5% = 45/291) |
| **Finding-Overload** | Repos mit >100 Findings / Repos gesamt | Benchmark-Suite | Quartalsweise | ≤ 20% |
| **Degradation-Rate** | Analysen mit `is_degraded=True` / Total | Telemetrie (opt-in) | Quartalsweise | ≤ 5% |

### 3.2 Aktuelle Messwerte (Stand: v1.3.x, 2026-04-01)

| Metrik | Wert | Status |
|--------|------|--------|
| Precision (strict) | 0.769 (291 Samples) | ✅ über Schwelle |
| Precision (lenient) | 0.948 | ✅ über Schwelle |
| Recall (Mutation) | 0.88 (15/17) | ✅ über Schwelle |
| Macro-F1 | ≥ 0.50 (CI-Gate) | ✅ |
| FP-Rate DCA | >90% bei Libraries | ❌ → report-only (weight=0.0) |
| FP-Rate DIA | ~40% | ⚠️ knapp über Schwelle |
| FP-Rate NBV | ~50% bei Krypto/Type-Code | ⚠️ kontextabhängig |
| Disputed-Rate | 15.5% (45/291) | ⚠️ knapp über Schwelle |

---

## 4. MANAGE — Risiko-Register

### Risiko-Einträge

| ID | Kategorie | Risiko | RPN/Schwere | Quelle | Owner | Metrik | Schwelle | Gegenmaßnahme | Status | Review |
|----|-----------|--------|-------------|--------|-------|--------|----------|---------------|--------|--------|
| **RQ-01** | Erkennungsqualität | DCA meldet Library-Exports als Dead Code → >90% FP bei Libraries | RPN 720 🔴 | FMEA FP-01, FTA B1/B2 | Maintainer | DCA FP-Rate | ≤ 30% | weight=0.0 (report-only); Library-Heuristik implementieren | **Mitigiert** (report-only); Fix ausstehend | Q2 2026 |
| **RQ-02** | Erkennungsqualität | DIA parst URLs als fehlende Verzeichnisse → ~40% FP | RPN 288 🟡 | FMEA FP-02, FTA B3/B4 | Maintainer | DIA FP-Rate | ≤ 30% | URL-Fragment-Exclusion in DIA-Parser | **Offen** | Q2 2026 |
| **RQ-03** | Erkennungsqualität | AVS-Findings doppelt gemeldet → +15–20% Noise | RPN 252 🟡 | FMEA FP-03, FTA B7/B8 | Maintainer | AVS Dedup-Rate | 0% Duplikate | Cross-Pass-Deduplication | **Offen** (go-no-go Blocker) | Q2 2026 |
| **RQ-04** | Erkennungsqualität | SMS erkennt neuartige Dependencies nicht → Recall 0.0 | RPN 256 🟡 | FMEA FN-01, FTA C1 | Maintainer | SMS Mutation-Recall | ≥ 0.50 | Import-Pattern-Erweiterung | **Offen** | Q2 2026 |
| **RQ-05** | Erkennungsqualität | PFS erkennt 2-Varianten-Fragmentation nicht → Recall 0.5 | RPN 210 🟡 | FMEA FN-02, FTA C5 | Maintainer | PFS Mutation-Recall | ≥ 0.80 | Threshold-Kalibrierung | **Offen** | Q3 2026 |
| **RQ-06** | Erkennungsqualität | TSA kann in Legacy-TS-Repos ohne Layer-Kontrakt übermelden (FP-Risiko) | RPN 120 🟡 | FMEA FP-09, FTA FT-1 TSA-Pfad | Maintainer | TSA FP-Rate | ≤ 30% | Report-only behalten; TS-Repo-Validierung vor Weight-Promotion | **Neu** | Q2 2026 |
| **RQ-07** | Erkennungsqualität | TSA kann dynamische Imports/Alias-Pfade übersehen (FN-Risiko) | RPN 168 🟡 | FMEA FN-08, FTA FT-2 TSA-Pfad | Maintainer | TSA Mutation-Recall | ≥ 0.50 | TS-spezifische Recall-Suite + Resolver-Heuristik | **Neu** | Q2 2026 |
| **RC-01** | Kontext | Library-Repos produzieren systematisch FP-Cluster (DCA/DIA/NBV) | RPN 336 🔴 | FMEA KX-01, FTA B9/B10 | Maintainer | FP-Rate bei Library-Repos | ≤ 30% gesamt | Automatische Library-Erkennung; Context-Tag; Signal-Anpassung | **Offen** | Q2 2026 |
| **RS-01** | Sicherheit | Config in Fork/PR kann kritische Signale deaktivieren | Mittel | STRIDE S-TB2-01, T-TB2-01 | Maintainer | — | — | `--no-repo-config` Option; Warnung bei >50% Core-Signale deaktiviert | **Offen** | Q3 2026 |
| **RS-02** | Sicherheit | AI-Attribution heuristisch manipulierbar (Co-author-Spoofing) | Mittel | STRIDE S-TB4-01, R-TB4-01 | Maintainer | — | — | „Heuristisch" Marker; Confidence-Level; Docs-Einschränkung | **Akzeptiert** (Design-Limitation) | Q4 2026 |
| **RS-03** | Sicherheit | related_files leaken Pfade außerhalb target-path | Mittel | STRIDE I-TB5-01 | Maintainer | — | 0 Pfade außerhalb Scope | Related-files auf target-path filtern | **Offen** | Q2 2026 |
| **RS-04** | Sicherheit | BOM in pyproject.toml → Analyse bricht ab (DRIFT-1002) | Niedrig | STRIDE T-TB2-03, FTA E4 | Maintainer | — | 0 BOM-Crashes | BOM-Strip in Config-Loader | **Offen** | Q2 2026 |
| **RD-01** | Degradation | Stille Unvollständigkeit: Parser/Git-Fehler ohne sichtbare Warnung | RPN 147 🟡 | FMEA DG-01/02/03, FTA E5/E7 | Maintainer | Degradation sichtbar in Output | 100% Degradation → Badge | Degradation-Badge + Coverage-Metric im Output | **Offen** | Q2 2026 |
| **RD-02** | Degradation | max_files Limit erreicht → Repo nur teilweise analysiert | RPN 144 🟡 | FMEA DG-03, FTA E3 | Maintainer | — | Warnung bei Limit | „N/M Dateien analysiert" Warnung | **Offen** | Q3 2026 |
| **RM-01** | Messung | TVS weight=0.13 im Score trotz 0% validierter Precision (30/30 Disputed) | RPN 210 🟡 | FMEA SC-01 | Maintainer | TVS Precision (strict) | ≥ 0.50 | TVS auf report-only (weight=0.0) bis Validierung; oder Confidence-Discount | **Offen** — Priorität | Q2 2026 |
| **RM-02** | Messung | Ground-Truth-Labels sind partiell selbst-generiert → Zirkularitätsrisiko | Mittel | AI-RMF Measure | Maintainer | External-Rater-Anteil | ≥ 30% extern validiert | Finding-Rating-Kit an 2–3 externe Rater (A4) | **In Arbeit** (Rating-Kit existiert) | Q2 2026 |
| **RO-01** | Operativ | Self-hosted Runner offline → Publish-Queue blockiert | Niedrig | Repo-Memory | Maintainer | Runner-Status | Online | Runner-Health-Check; Fallback auf GitHub-hosted Runner | **Bekannt** | Q3 2026 |

---

## 5. Maßnahmen-Backlog (priorisiert nach Policy §6)

| Prio | Maßnahme | Risk-IDs | Aufwand | RPN-Reduktion | Roadmap-Phase |
|------|----------|----------|---------|---------------|---------------|
| 1 | **Degradation-Badge + Coverage-Metric** | RD-01, RD-02 | Niedrig | -57% auf DG-01/02/03 | Phase 1 (Vertrauen) |
| 2 | **Library-Kontext-Erkennung** | RQ-01, RC-01 | Mittel | -67% auf FP-01, -60% auf KX-01 | Phase 1 (Vertrauen) |
| 3 | **TVS report-only oder Confidence-Discount** | RM-01 | Niedrig | -100% Score-Impact (TVS) | Phase 1 (Vertrauen) |
| 4 | **External Precision Validation (Rating-Kit)** | RM-02 | Mittel | Validiert Metriken-Framework | Phase 1 (Vertrauen) |
| 5 | **SMS Import-Pattern-Update** | RQ-04 | Niedrig | -50% auf FN-01 | Phase 2 (Relevanz) |
| 6 | **DIA URL-Fragment-Exclusion** | RQ-02 | Niedrig | -63% auf FP-02 | Phase 2 (Relevanz) |
| 7 | **AVS Cross-Pass-Dedup** | RQ-03 | Niedrig | -100% auf AVS-Duplikate | Phase 2 (Relevanz) |
| 8 | **BOM-Strip in Config-Loader** | RS-04 | Niedrig | Eliminiert DRIFT-1002 | Phase 3 (Einführbarkeit) |
| 9 | **Related-files target-path Filter** | RS-03 | Niedrig | Schließt Info-Disclosure | Phase 3 (Einführbarkeit) |
| 10 | **--no-repo-config CLI-Option** | RS-01 | Niedrig | Reduziert Config-Injection-Risiko | Phase 3 (Einführbarkeit) |
| 11 | **PFS Threshold-Kalibrierung** | RQ-05 | Mittel | -43% auf FN-02 | Phase 2 (Relevanz) |

---

## 6. Review-Zyklen

| Trigger | Aktion | Verantwortlich |
|---------|--------|----------------|
| **Minor-Release** | FMEA Top-10 RPN Review; Messwerte aktualisieren; Risk Register Status-Update | Maintainer |
| **Architekturänderung** | STRIDE Refresh für betroffene Trust Boundary | Maintainer |
| **Neues Signal** | FMEA-Eintrag (FP + FN) Pflicht; FT-1 und FT-2 erweitern | Signal-Owner |
| **Neuer Input-/Output-Pfad** | STRIDE-Element Pflicht (S/T/R/I/D/E) | Maintainer |
| **Precision-Änderung >5%** | Betroffene FMEA-RPNs + Risk-Register-Einträge neu bewerten | Signal-Owner |
| **Security-Advisory** | STRIDE Trust Boundary + Residual Risk aktualisieren | Security-Contact |
| **Quartalsweise** | Vollständiger Register-Review; Heatmap aktualisieren; Disputed-Rate prüfen | Maintainer |

---

## 7. Dokumenten-Verweise

| Artefakt | Pfad | Zweck |
|----------|------|-------|
| FMEA-Matrix | `audit_results/fmea_matrix.md` | Fehlermodi + RPN pro Signal |
| STRIDE Threat Model | `audit_results/stride_threat_model.md` | Threat-Analyse pro Trust Boundary |
| Fault Trees | `audit_results/fault_trees.md` | Kausale Ursachenketten für Top-3-Risiken |
| Ground-Truth-Labels | `benchmark_results/ground_truth_labels.json` | Precision-Messung |
| Mutation-Benchmark | `benchmark_results/mutation_benchmark.json` | Recall-Messung |
| Signal-Audit | `audit_results/validation/signal-audit.md` | Manuelle Precision-Klassifizierung |
| Go/No-Go | `audit_results/validation/go-no-go.md` | Release-Entscheidung + Blockers |
| SECURITY.md | `SECURITY.md` | Security-Boundary-Controls |
| POLICY.md | `POLICY.md` | Governance-Rahmen + Priorisierung |
