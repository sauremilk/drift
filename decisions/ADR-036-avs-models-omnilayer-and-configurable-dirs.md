---
id: ADR-036
status: proposed
date: 2026-04-10
type: signal-design
signal_id: AVS
supersedes:
---

# ADR-036: AVS — `models` als Omnilayer + konfigurierbare Omnilayer-Dirs

## Problemklasse

AVS co-change-Subkomponente hat eine strict-Precision von 0.30 in der Ground-Truth-Analyse (drift_self, n=20). 70% der Findings sind Disputed. Der Hauptgrund: `models.py`-Dateien sind in `_DEFAULT_LAYERS` als Layer 2 (DB) klassifiziert, obwohl in vielen Projekten (inkl. drift selbst) Models DTOs, Dataclasses oder Config-Objekte sind — also cross-cutting.

Zusätzlich sind die Omnilayer-Dirs nicht konfigurierbar, sodass Repos mit projektspezifischen cross-cutting-Modulen (z.B. `dtos/`, `contracts/`) keine Möglichkeit haben, FPs zu vermeiden.

## Heuristik

1. `"models"` wird aus `_DEFAULT_LAYERS` (Layer 2) entfernt und zu `_OMNILAYER_DIRS` hinzugefügt.
2. Neues Config-Feld `policies.omnilayer_dirs: list[str]` erlaubt, zusätzliche Verzeichnisse als Omnilayer zu markieren.
3. In `_check_inferred_layers()` wird die effektive Omnilayer-Menge zur Laufzeit gebildet: `_OMNILAYER_DIRS | set(config.policies.omnilayer_dirs)`.

## Scope

`cross_file` — keine Änderung am bestehenden Scope.

## Erwartete FP-Klassen

- **Reduziert:** Upward-Import-FPs durch `models.py` in DTO/Config-Projekten
- **Reduziert:** Latentes FP-Risiko für `models.py`-Importe in CLI-Architektur-Repos

## Erwartete FN-Klassen

- **Neu:** Django/SQLAlchemy-Repos mit echtem DB-ORM-Layer in `models/` → Upward-Import-Detection entfällt per Default
- **Mitigation:** Diese Repos können `policies.allowed_cross_layer` oder `policies.layer_boundaries` nutzen, die das Verhalten explizit steuern

## Fixture-Plan

- `avs_models_omnilayer_tn` — models.py importiert aus routes.py → kein Finding (Omnilayer-Default)
- `avs_confounder_dto_tn` — DTO-models cross-layer → kein Finding

## FMEA-Vorab-Eintrag

| Failure Mode | Severity | Occurrence | Detection | RPN |
|---|---|---|---|---|
| FN: DB-ORM-models nicht als Layer-2 erkannt | 4 | 3 | 5 | 60 |
| FP: Custom omnilayer_dirs falsch gesetzt → echte Violations unterdrückt | 3 | 2 | 6 | 36 |

## Validierungskriterium

- `pytest tests/test_precision_recall.py -v` — AVS precision ≥ 0.50 (aktuell 0.30 strict)
- `pytest tests/test_avs_enhanced.py -v` — alle Omnilayer-Tests grün
- `drift analyze --repo . --format json --exit-zero` — AVS co_change Disputed-Anteil reduziert
- Lernzyklus-Ergebnis: `bestaetigt` wenn AVS precision_strict > 0.50, sonst `unklar`
