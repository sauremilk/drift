---
id: ADR-073
status: proposed
date: 2026-04-17
supersedes:
---

# ADR-073: Consolidation Opportunity Detector

## Kontext

AI-generierter Code begünstigt N ähnliche Implementierungen statt einer
kanonischen. Agenten fixen PFS/MDS-Findings einzeln, obwohl gebündelte
Konsolidierung effizienter wäre. `batch_group` und `batch_eligible` existieren
in der Task-Graph-Infrastruktur, aber es fehlt ein explizites Consolidation-
Objekt, das Instanzen, kanonische Variante und erwartete Netto-Reduktion
bündelt.

## Entscheidung

### Was getan wird

1. **`ConsolidationGroup`-Dataclass** in `models/_agent.py`: Bündelt
   `group_id`, `signal`, `instance_count`, `canonical_file`, `affected_files`,
   `estimated_net_finding_reduction` und `edit_kind`.
2. **`build_consolidation_groups()`** in `task_graph.py`: Clustert
   batch-eligible Tasks nach (signal_type, fix_template_class). Pro Gruppe
   wird die kanonische Datei (häufigste) und die geschätzte Netto-Reduktion
   berechnet.
3. **`consolidation_opportunities`** im fix_plan-Response: Liste der
   Consolidation Groups mit kompakten Metadaten. Jeder Task bekommt eine
   `consolidation_group_id`-Referenz.

### Was explizit nicht getan wird

- Keine neue Signal-Implementierung — nutzt bestehende PFS/MDS-Metadaten.
- Keine automatische Konsolidierung — nur Erkennung und Empfehlung.
- Kein Cross-Signal-Clustering (PFS + MDS bleiben getrennte Gruppen).

## Begründung

Agent sieht "5 Findings durch 1 Consolidation lösbar" statt "5 separate Tasks".
Das reduziert Patch-Kaskaden und gibt dem Agent eine effizientere Strategie.
Die bestehende `batch_group`-Mechanik wird nicht ersetzt, sondern mit
strukturierten Consolidation-Metadaten angereichert.

## Konsequenzen

- fix_plan-Response wächst um ein `consolidation_opportunities`-Array.
- Tasks in Consolidation Groups tragen ein zusätzliches Feld.
- Kanonische Variante ist heuristisch (häufigste Datei) — kann falsch liegen
  bei intentional-divergenten Varianten. Conservative Heuristik minimiert das.

## Validierung

```bash
pytest tests/test_consolidation_groups.py -v
pytest tests/test_task_graph.py -v --tb=short
```

Erwartetes Lernzyklus-Ergebnis: `bestätigt` wenn Consolidation-Gruppen in
Mutation-Benchmark weniger Tasks bei gleicher Finding-Reduktion erzeugen.
