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

## Broad Exception Monoculture
- Rule Name: BroadExceptionMonocultureSignal
- Source Module: src/drift/signals/broad_exception_monoculture.py
- Signal: SignalType.BROAD_EXCEPTION_MONOCULTURE
- Expected Finding: Module, in denen die Mehrzahl der Exception-Handler nur breite Typen (Exception/BaseException/bare except) fängt und Fehler uniform schluckt (Titelmuster: "Broad exception monoculture in {module}/").
- Known False Positives: Error-Boundary-Module (middleware, error_handler, exception_handler etc.) und Dateien mit Boundary-Decorators (app.exception_handler, task, shared_task etc.) werden ausgenommen; Mindestanzahl Handler (bem_min_handlers) muss erreicht werden.

## Test Polarity Deficit
- Rule Name: TestPolarityDeficitSignal
- Source Module: src/drift/signals/test_polarity_deficit.py
- Signal: SignalType.TEST_POLARITY_DEFICIT
- Expected Finding: Testsuiten mit ausschließlich Happy-Path-Assertions ohne Negativ-Tests (pytest.raises, assertRaises, assertFalse, Boundary-Cases) (Titelmuster: "Happy-path-only test suite in {module}/").
- Known False Positives: Mindestanzahl Testfunktionen (tpd_min_test_functions) und ≥10 Assertions erforderlich; Negativ-Ratio <10% als Schwelle; kleine Testsuiten werden herausgefiltert.

## Guard Clause Deficit
- Rule Name: GuardClauseDeficitSignal
- Source Module: src/drift/signals/guard_clause_deficit.py
- Signal: SignalType.GUARD_CLAUSE_DEFICIT
- Expected Finding: Module, in denen öffentliche, nicht-triviale Funktionen uniform keine Guard Clauses besitzen (isinstance, assert, if-raise/return) (Titelmuster: "Guard clause deficit in {module}/").
- Known False Positives: Testdateien, __init__.py und private Funktionen sind ausgeschlossen; Funktionen mit <2 Parametern, Komplexität <5 oder Validierungs-Decorators werden übersprungen; Mindestanzahl öffentlicher Funktionen (gcd_min_public_functions) muss erreicht werden.

## Naming Contract Violation
- Rule Name: NamingContractViolationSignal
- Source Module: src/drift/signals/naming_contract_violation.py
- Signal: SignalType.NAMING_CONTRACT_VIOLATION
- Expected Finding: Funktionen, deren Name einen Vertrag impliziert, den der Body nicht erfüllt (z.B. validate_* ohne raise/return-False, is_* ohne bool-Return) (Titelmuster: "Naming contract violation: {function}()").
- Known False Positives: Testdateien und private Funktionen werden übersprungen; Mindestzeilenzahl (nbv_min_function_loc) muss erreicht werden; 5 Namensregeln (validate_*, check_*, ensure_*, get_or_create_*, is_*/has_*, try_*) werden geprüft.

## Bypass Accumulation
- Rule Name: BypassAccumulationSignal
- Source Module: src/drift/signals/bypass_accumulation.py
- Signal: SignalType.BYPASS_ACCUMULATION
- Expected Finding: Dateien mit überdurchschnittlich hoher Dichte an Quality-Bypass-Markern (# type: ignore, # noqa, # pragma: no cover, typing.Any, cast(), TODO/FIXME/HACK/XXX) (Titelmuster: "High bypass marker density in {filename}").
- Known False Positives: Testdateien werden ausgeschlossen; Mindest-LOC (bat_min_loc) erforderlich; Vergleich gegen Median-Moduldichte für Anomalie-Kontext.

## Exception Contract Drift
- Rule Name: ExceptionContractDriftSignal
- Source Module: src/drift/signals/exception_contract_drift.py
- Signal: SignalType.EXCEPTION_CONTRACT_DRIFT
- Expected Finding: Öffentliche Funktionen, deren Exception-Profil (geworfene/gefangene Exception-Typen) sich über kürzliche Commits verändert hat, während die Signatur stabil blieb (Titelmuster: "Exception contract drift in {module}/ ({N} function(s))").

---

> **Scope note:** This inventory covers the 18 scoring-active signals only.
> The 6 report-only signals (TSA, CXS, CIR, DCA, MAZ, ISD) are
> visible in findings but do not contribute to the composite score. Their
> detection behaviour is documented in the
> [signal reference](https://mick-gsk.github.io/drift/reference/signals/).
- Known False Positives: Nur Python-Dateien mit Git-Historie (≥2 Commits); stabile Signatur (gleiche Parameteranzahl) erforderlich; neue Funktionen werden übersprungen; Git-Abruffehler werden graceful behandelt.

## Cohesion Deficit
- Rule Name: CohesionDeficitSignal
- Source Module: src/drift/signals/cohesion_deficit.py
- Signal: SignalType.COHESION_DEFICIT
- Expected Finding: Semantisch inkohärente Module, gemessen über Jaccard-Ähnlichkeit der Token-Sets aus Funktions-/Klassennamen; flaggt Dateien mit isolierten Einheiten (Titelmuster: "Cohesion deficit in {file_path}").
- Known False Positives: __init__.py und Testdateien werden ausgeschlossen; mindestens 4 semantische Einheiten erforderlich; Repo-Größen-Dampening-Faktor und Stopword-Filterung (get, set, utils etc.) reduzieren Rauschen.

## Co-Change Coupling
- Rule Name: CoChangeCouplingSignal
- Source Module: src/drift/signals/co_change_coupling.py
- Signal: SignalType.CO_CHANGE_COUPLING
- Expected Finding: Versteckte Datei-Kopplung durch wiederkehrende Co-Change-Muster ohne explizite Import-Beziehung (Titelmuster: "Hidden co-change coupling: {file_a} <-> {file_b} ({N} commits)").
- Known False Positives: Merge-Commits (0.35×) und Bot-/Automated-Commits (0.50×) werden heruntergewichtet; mindestens 4 effektive Commits und ≥0.45 Confidence erforderlich; explizite Import-Abhängigkeiten werden ausgeschlossen.
