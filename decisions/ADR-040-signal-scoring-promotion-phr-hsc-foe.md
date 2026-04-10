---
id: ADR-040
status: proposed
date: 2026-04-10
type: scoring-change
supersedes:
---

# ADR-040: Scoring-Promotion — PHR, HSC, FOE für Agenten-Sicherheit

## Kontext

Drift v2.8.1 hat 9 report-only Signale (weight=0.0), die zwar Findings
erzeugen, aber weder in den Composite Score einfließen noch
safe_to_commit blockieren. Drei davon — PHR (Phantom Reference),
HSC (Hardcoded Secret) und FOE (Fan-Out Explosion) — sind für
autonome Coding-Agenten besonders relevant:

- **PHR**: Einziges Signal zur Erkennung halluzinierter Referenzen (AI-spezifisch)
- **HSC**: Erkennt hardcoded Secrets, die Agenten bei Prototyping-Iterationen einführen
- **FOE**: Erkennt Import-Akkumulation ("God-File"-Tendenz bei Agent-generiertem Code)

Alle drei haben auf ihren Ground-Truth-Fixtures F1=1.00 und mindestens
eine Runde Selbstanalyse ohne FPs im src/drift/-Bereich bestanden.

## Entscheidung

1. **PHR** wird von weight=0.0 auf **weight=0.02** promoviert
2. **HSC** wird von weight=0.0 auf **weight=0.02** promoviert
3. **FOE** wird von weight=0.0 auf **weight=0.01** promoviert
4. **PHR** wird zum Abbreviation-Mapping hinzugefügt (fehlte bisher)
5. HSC und FOE erhalten zusätzliche Ground-Truth-Fixtures
6. PHR-Findings mit severity HIGH blockieren `safe_to_commit` (bereits
   durch bestehende Rule (a) in nudge.py abgedeckt — keine Code-Änderung nötig)

## Begründung

### Warum konservative Gewichte (0.01–0.02)?

Die Fixture-Anzahl ist noch gering: PHR hat 15, HSC hat 1, FOE hat 0.
Konservative Gewichte stellen sicher, dass diese Signale im Composite
Score sichtbar werden und safe_to_commit blockieren können, ohne den
Score bei möglichen FPs dramatisch zu verzerren.

### Warum diese drei zuerst?

Priorisierung nach Impact ÷ Aufwand:

| Signal | Agent-Relevanz | FP-Risiko | Implementierungsreife |
|--------|----------------|-----------|----------------------|
| PHR    | Sehr hoch (Halluzinationserkennung) | Niedrig (cross-file, umfangreiche Suppressions) | Hoch (15 Fixtures, ADR-033) |
| HSC    | Hoch (Security-Gate) | Niedrig (3-Tier mit Entropy, Prefix, FP-Suppression) | Hoch (650 LOC, ML/URL/Placeholder-Suppressions) |
| FOE    | Mittel (Architektur-Gate) | Sehr niedrig (80 LOC, konfigurierbarer Threshold) | Hoch (einfachstes Signal) |

### Warum nicht MAZ und ISD?

- MAZ ist Python-only und Framework-Heuristik-basiert; middleware-basierte Auth ist unsichtbar für AST → höheres FP/FN-Risiko
- ISD ist Django-zentriert; geringe Breite ohne Multi-Framework-Support

Beide bleiben report-only bis Framework-Detection-Hardening in einer späteren Phase.

## Nicht-Ziele

- Keine Gewichtsänderung für MAZ, ISD, TSA, CXS, CIR, DCA oder TSB
- Keine Änderung der PHR-, HSC- oder FOE-Detektionslogik selbst
- Kein neuer safe_to_commit-Code (bestehende Rule (a) deckt HIGH-severity bereits ab)

## Trade-offs

- **PHR weight 0.02 statt höher**: Geringerer Score-Impact, aber sicherer bei unentdeckten FP-Klassen
- **HSC overlap mit detect-secrets/Gitleaks**: Akzeptabel, weil Drift in-loop arbeitet (pre-commit vs. in-agent-loop)
- **FOE threshold 15 möglicherweise zu niedrig für Agent-Code**: Konfigurierbar via `foe_max_imports`

## Fixture-Anforderungen

Vor Merge müssen folgende Fixtures existieren:

### HSC (neu):
- `hsc_github_token_tp`: GitHub PAT Token Assignment
- `hsc_high_entropy_tp`: High-Entropy String in Variable mit Secret-Pattern
- `hsc_env_read_tn`: os.environ/os.getenv-basierter Zugriff
- `hsc_placeholder_tn`: Placeholder-String (`changeme`, `xxx`)

### FOE (neu):
- `foe_high_import_tp`: Datei mit >20 unique Imports
- `foe_normal_import_tn`: Datei mit <10 Imports
- `foe_barrel_file_tn`: `__init__.py` mit vielen Re-Exports (excluded)

### PHR (Lücken schließen):
- `phr_third_party_import_tn`: Korrekte Third-Party-Imports
- `phr_conditional_import_tn`: try/except ImportError Guard
- `phr_framework_decorator_tn`: pytest/Flask-Decorator-Referenz

## Validierungskriterium

```bash
pytest tests/test_precision_recall.py -v       # Alle 3 Signale: P=1.0, R=1.0
pytest tests/test_phantom_reference.py -v      # PHR-spezifische Tests
make test-fast                                  # Gesamtsuite grün
drift analyze --repo . --format json --exit-zero  # Selbstanalyse stabil
```

Erwartetes Lernzyklus-Ergebnis: `bestaetigt` wenn alle Fixtures F1=1.00
und Selbstanalyse 0 neue FPs in src/drift/.
