---
id: ADR-037
status: proposed
date: 2026-04-10
type: signal-design
signal_id: DIA
supersedes:
---

# ADR-037: DIA — Konfigurierbare Auxiliary-Dirs und Keyword-Gate

## Problemklasse

DIA hat die höchste FP-Rate aller Scoring-aktiven Signale (33% strict, 9/27). Viele FPs stammen von projektspezifischen Verzeichnissen, die in der hardcodierten `_AUXILIARY_DIRS`-Liste fehlen, oder von fehlenden Kontext-Keywords im Codespan-Gate. Die FP-Klassen sind bereits weitgehend mitigiert (P1–P6), aber die fehlende Konfigurierbarkeit verhindert repo-spezifische FP-Reduktion.

## Heuristik

1. Neue Config-Klasse `DocImplDriftConfig` mit:
   - `extra_auxiliary_dirs: list[str]` — erweitert die Standard-`_AUXILIARY_DIRS`
   - `extra_context_keywords: list[str]` — erweitert das Keyword-Gate für Codespans
2. Integration in `DriftConfig` als Feld `dia: DocImplDriftConfig`.
3. Im Signal werden die Config-Werte mit den Hardcode-Defaults gemergt.

## Scope

`file_local` — keine Änderung am bestehenden Scope.

## Erwartete FP-Klassen

- **Reduziert:** Projektspezifische Verzeichnisse (z.B. `infra/`, `deploy/`, `migrations/`) als "undokumentiert" gemeldet
- **Reduziert:** Repos mit eigenen Terminologien im Keyword-Gate (z.B. `component`, `layer`, `service`)

## Erwartete FN-Klassen

- **Neu:** Zu aggressives `extra_auxiliary_dirs` könnte echte undokumentierte Dirs maskieren
- **Mitigation:** Nur explizite Opt-in-Liste; keine Glob-Patterns

## Fixture-Plan

- `dia_custom_auxiliary_tn` — Verzeichnis in `extra_auxiliary_dirs` → kein Finding

## FMEA-Vorab-Eintrag

| Failure Mode | Severity | Occurrence | Detection | RPN |
|---|---|---|---|---|
| FN: echte undokumentierte Dirs durch zu breite extra_auxiliary_dirs maskiert | 3 | 2 | 5 | 30 |
| Config-Validierung fehlt: ungültige Dir-Namen in extra_auxiliary_dirs | 2 | 2 | 3 | 12 |

## Validierungskriterium

- `pytest tests/test_precision_recall.py -v` — DIA precision ≥ 0.50
- Kein Recall-Verlust bei bestehenden DIA-Fixtures
- Lernzyklus-Ergebnis: `bestaetigt` wenn DIA FP-Rate in Self-Analysis sinkt
