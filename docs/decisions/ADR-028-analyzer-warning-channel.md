---
id: ADR-028
status: proposed
date: 2026-04-09
supersedes:
---

# ADR-028: Analyzer Warning Channel via BaseSignal Instance Field

## Kontext

`BaseSignal.analyze()` gibt `list[Finding]` zurück. Es existiert kein Mechanismus,
um Nicht-Finding-Informationen (z. B. "Signal wurde übersprungen, weil
Voraussetzungen fehlen") aus einem Signal herauszutransportieren.

Konkreter Auslöser: `TemporalVolatilitySignal` gibt bei leerem `file_histories`-Dict
still eine leere Liste zurück. Nutzer ohne `.git`-Verzeichnis oder mit flachem Clone
erhalten kein Feedback, warum TVS stumm bleibt.

## Entscheidung

Warnungen werden über ein Instanzfeld auf `BaseSignal` transportiert:

1. **Neues Dataclass `AnalyzerWarning`** in `drift/models.py`:
   - `signal_type: str` — Quellsignal
   - `message: str` — menschenlesbarer Text
   - `skipped: bool = True` — ob das Signal übersprungen wurde

2. **`BaseSignal` erhält:**
   - `_warnings: list[AnalyzerWarning]` (initialisiert in `__init__`)
   - `emit_warning(message, *, skipped=True)` — Hilfsmethode zum Anhängen

3. **Engine/Runner** liest `signal._warnings` nach jedem `analyze()`-Aufruf
   und sammelt sie zentral.

4. **CLI** gibt Warnungen als `⚠ Warning`-Zeilen nach der Finding-Ausgabe aus,
   nicht als Findings.

### Was explizit nicht getan wird

- Keine Änderung der `analyze()`-Signatur
- Keine Breaking Change an `AnalysisContext`
- Kein neuer Rückgabetyp (z. B. `AnalysisResult(findings, warnings)`)
- Warnungen fließen nicht in Scoring oder Severity-Berechnung ein

## Begründung

### Verworfene Alternative: `AnalysisContext.warnings`

Signale erhalten keinen Context-Parameter in `analyze()`. Der Context müsste
über `bind_context()` gespeichert und in `analyze()` via `self._analysis_context`
zugänglich gemacht werden. Das erfordert Änderungen an allen bestehenden
`bind_context()`-Callsites und fügt dem Context weitere Verantwortlichkeiten
hinzu.

### Verworfene Alternative: Neuer Rückgabetyp

`analyze()` → `AnalysisResult(findings, warnings)` bricht alle bestehenden
Signal-Implementierungen und alle Callsites. Hoher Aufwand, geringer
Zusatznutzen gegenüber dem Instanzfeld.

### Gewählter Ansatz: Instanzfeld

- Kein Breaking Change
- Rückwärtskompatibel — Signale ohne Warnungen funktionieren unverändert
- Engine-Integration ist ein Einzeiler pro Signal-Aufruf
- Einfach testbar

## Konsequenzen

- Jedes Signal kann Warnungen emittieren, ohne API-Änderung
- Engine-Code muss nach `signal.analyze()` zusätzlich `signal._warnings` lesen
- Warnings accumulate pro Signal-Instanz; bei Wiederverwendung müsste `_warnings`
  geleert werden (aktuell kein Anwendungsfall, da Instanzen pro Lauf erzeugt werden)
- Der precision-Runner und die CLI müssen Warnungen separat weiterreichen

## Validierung

```bash
# TVS emittiert Warning bei leerem file_histories
pytest tests/test_precision_recall.py -v -k tvs_new_file
# Neuer CLI-Befehl zeigt Warnungen
drift precision --signal TVS
```

Lernzyklus-Ergebnis: zurückgestellt (wird nach erstem Produktiveinsatz bewertet).
