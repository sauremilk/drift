---
id: ADR-050
status: proposed
date: 2026-04-11
type: signal-design
signal_id: AVS
supersedes:
---

# ADR-050: AVS Urgency-Gating via Churn für blast_radius und zone_of_pain

## Problemklasse

`architecture_violation` (AVS) meldet `blast_radius`- und `zone_of_pain`-Subtypen für Dateien mit vielen transItiven Abhängigkeiten. Im Actionability Review (2026-04-11) fand sich ein Finding: "107 transitive Abhängigkeiten" für eine Datei, die **6 Monate unverändert** war. Für einen solchen Use Case ist der Handlungsdruck minimal — die Abhängigkeiten existieren, ändern sich aber nicht.

Ein `blast_radius`-Finding ist nur dann dringlich, wenn die betroffene Datei **aktiv geändert** wird (hohe churn_per_week) oder die Abhängigkeitszahl strukturell kritisch ist (>50 transitive). Ohne Churn-Kontext erzeugt AVS systematische False-Positives bei stabilen, gut etablierten Utility-Modulen.

## Heuristik

**Churn-Guard für `_check_blast_radius()`:**
```python
churn = file_histories.get(file_path, FileHistory()).change_frequency_30d  # churn/week
blast_radius = len(transitive_ancestors)

if churn <= 1.0 and blast_radius <= 50:
    # Stable, not urgent — downgrade to INFO instead of HIGH
    severity = Severity.INFO
    description += f" (stable: {churn:.1f} changes/week)"
else:
    # Active or extreme — fire normally
    description += f" (churn: {churn:.1f}/week, blast_radius: {blast_radius})"
```

Metadata-Erweiterung: `finding.metadata["churn_per_week"] = churn`.

**Zone-of-Pain-Verbesserung (`_check_instability()`):**
- Fix-Text erweitern um erste nächste Maßnahme: Angabe von `top_extraction_candidates` (Funktionen/Klassen mit wenigsten internen Cross-Referenzen sind Extraktionskandidaten).

## Scope

`cross_file` mit `git_dependent` — bestehende Einstufung bleibt. `file_histories` ist bereits in `analyze()` verfügbar.

## Erwartete FP-Klassen

- Utility-Modul hat `churn <= 1.0` aber tatsächlich hohes Risiko → jetzt INFO, würde unterdrückt. Akzeptierbar da blast_radius < 50 der sekundäre Guard ist.
- churn_per_week = 0.0 für sehr junge Repos (< 30 Tage History) → unnötiger INFO-Downgrade

## Erwartete FN-Klassen

- Critische Datei mit exactem churn = 1.0 (Grenzfall) → mit ==1.0 Schwelle: bleibt INFO statt HIGH. Threshold kann in Config konfigurierbar gemacht werden.

## Fixture-Plan

- TP-Fixture: `avs_blast_radius_high_churn` — blast_radius > 50, churn > 2.0/week → HIGH-Finding erwartet
- TN-Fixture: `avs_blast_radius_stable` — blast_radius 30, churn 0.2/week → INFO oder kein Finding

## FMEA-Vorab-Eintrag

| Failure Mode | Severity | Occurrence | Detection | RPN |
|---|---|---|---|---|
| FN: Kritische stabile Datei wird zu INFO degradiert | 7 | 4 | 5 | 140 |
| FP: Junges Repo hat 0.0 churn, blast_radius zu niedrig bewertet | 4 | 3 | 6 | 72 |
| FN: churn-Schwelle 1.0 zu niedrig für hochfrequente Repos | 5 | 3 | 5 | 75 |

## Validierungskriterium

1. AVS blast_radius-Findings enthalten `churn_per_week` in Metadata.
2. Self-analysis: AVS-Finding-Count ≤ bisheriger Stand (kein Anstieg durch neue Subtypen).
3. TP-Fixture `avs_blast_radius_high_churn` → HIGH gemeldet.
4. TN-Fixture `avs_blast_radius_stable` → kein HIGH (INFO oder kein Finding).
5. `pytest tests/test_precision_recall.py` — AVS Recall/Precision innerhalb Toleranz.
