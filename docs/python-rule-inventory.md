# Python Rule Inventory

## Pattern Fragmentation
- Rule Name: PatternFragmentationSignal
- Source Module: src/drift/signals/pattern_fragmentation.py
- Signal: SignalType.PATTERN_FRAGMENTATION
- Expected Finding: Mehrere inkompatible Pattern-Varianten innerhalb eines Moduls (Titelmuster: "{category}: {num_variants} variants in {module}/").
- Known False Positives: Async/Sync-Varianten werden normalisiert (is_async/async/await-Normalisierung), um äquivalente Implementierungen nicht als unterschiedliche Varianten zu zählen.

## Architecture Violations
- Rule Name: ArchitectureViolationSignal
- Source Module: src/drift/signals/architecture_violation.py
- Signal: SignalType.ARCHITECTURE_VIOLATION
- Expected Finding: Verbotene Layer-Importe (Policy-Verstoß), aufwärtsgerichtete Layer-Importe sowie zirkuläre Abhängigkeiten zwischen Modulen.
- Known False Positives: Omnilayer-Verzeichnisse (z. B. config/utils/shared) werden ausgenommen; Patterns aus allowed_cross_layer unterdrücken Findings; externe/unaufgelöste Ziele werden bei Layer-Checks übersprungen.

## Mutant Duplicates
- Rule Name: MutantDuplicateSignal
- Source Module: src/drift/signals/mutant_duplicates.py
- Signal: SignalType.MUTANT_DUPLICATE
- Expected Finding: Exakte Duplikate, Near-Duplicates und semantische Duplikate zwischen Funktionen.
- Known False Positives: Dunder-/Protocol-Methoden sind explizit ausgeschlossen; sehr kleine/triviale Funktionen werden über LOC- und Komplexitätsgates herausgefiltert; große Größenunterschiede zwischen Funktionen werden vor Similarity-Alarmen abgefangen.

## Explainability Deficit
- Rule Name: ExplainabilityDeficitSignal
- Source Module: src/drift/signals/explainability_deficit.py
- Signal: SignalType.EXPLAINABILITY_DEFICIT
- Expected Finding: Komplexe Funktionen mit unzureichender Erklärbarkeit (z. B. fehlende Docstring/Tests/Return-Type), Titelmuster: "Unexplained complexity: {function}".
- Known False Positives: Testdateien und kurze/triviale Funktionen werden ausgeschlossen; Schwellenwerte für Komplexität und Funktionslänge reduzieren Rauschen.

## Doc-Implementation Drift
- Rule Name: DocImplDriftSignal
- Source Module: src/drift/signals/doc_impl_drift.py
- Signal: SignalType.DOC_IMPL_DRIFT
- Expected Finding: Fehlende README, veraltete Doku-Verzeichnisreferenzen (README/ADR) oder nicht dokumentierte Source-Verzeichnisse.
- Known False Positives: URL-Pfadsegmente werden per Blacklist gefiltert; Link-URLs, Bilder und Codeblöcke werden bei Extraktion ignoriert; versions-/numerik-/Prosa-Rauschen wird über Heuristiken ausgeschlossen.

## Temporal Volatility
- Rule Name: TemporalVolatilitySignal
- Source Module: src/drift/signals/temporal_volatility.py
- Signal: SignalType.TEMPORAL_VOLATILITY
- Expected Finding: Dateien mit anomaler Änderungsvolatilität (Churn/Author-Diversität/Defect-Korrelation), Titelmuster: "High volatility: {path}".
- Known False Positives: Z-Score-Schwelle und Mindestscore filtern schwache Ausreißer; ohne belastbare Git-Historie werden keine Findings erzeugt.

## System Misalignment
- Rule Name: SystemMisalignmentSignal
- Source Module: src/drift/signals/system_misalignment.py
- Signal: SignalType.SYSTEM_MISALIGNMENT
- Expected Finding: Neu eingeführte, modulfremde Abhängigkeiten in kürzlich geänderten Dateien (Titelmuster: "Novel dependencies in {module}/").
- Known False Positives: Relative Imports und Python-Stdlib sind ausgeschlossen; bei zu dünner Baseline (<10% etablierte Dateien) wird die Regel komplett übersprungen.
