---
id: ADR-039
status: proposed
date: 2026-04-10
supersedes:
---

# ADR-039: AST-basierte logische Lokalisierung in Findings

## Kontext

Autonome Coding-Agenten, die Drift-Findings korrigieren, arbeiten in dynamischen
Umgebungen: Durch vorhergehende Edits verschieben sich Zeilennummern ständig.
`Finding.start_line` / `end_line` sind daher als alleinige Lokalisierung unzuverlässig.

Die AST-Daten für eine präzisere Lokalisierung existieren bereits intern:
`FunctionInfo` trägt class-qualifizierte Namen (`"AuthService.login"`),
`ClassInfo` trägt Methodenlisten mit Zeilenbereichen.  Diese Informationen
werden jedoch **nicht auf Findings übertragen** und sind in keinem Output-Format
exponiert — weder in JSON noch in SARIF noch in AgentTask/fix_plan-Responses.

## Entscheidung

### Was wird getan

1. Neuer Dataclass `LogicalLocation` in `models.py` mit SARIF-v2.1.0-kompatiblen Feldern:
   `fully_qualified_name`, `name`, `kind` ("function"/"method"/"class"/"module"),
   `class_name`, `namespace`.

2. Neues Feld `Finding.logical_location: LogicalLocation | None` (optional, backward-compatible).

3. Zentraler Enrichment-Schritt `enrich_logical_locations()` in der Pipeline-ScoringPhase:
   - Baut Interval-Index aus `ParseResult`-Daten (FunctionInfo/ClassInfo)
   - Für jedes Finding: Lookup via `file_path` + Zeilenbereich → engster Match (Methode > Klasse > Modul)
   - Back-fill von `Finding.symbol` wenn leer

4. Serialisierung in **allen** Output-Kanälen:
   - JSON-Output: `"logical_location"` Objekt
   - SARIF-Output: `logicalLocations` Array (SARIF v2.1.0 §3.33)
   - AgentTask/fix_plan/nudge: `"logical_location"` Dict

### Was nicht getan wird

- Keine Änderung an den 24 Signalen selbst — der Enrichment ist rein zentral.
- Kein Line-Level-Blame, kein AST-Diff.
- Kein neues Parsing — ausschließlich Nutzung bestehender `ParseResult`-Daten.
- `start_line`/`end_line` werden **nicht entfernt** — sie bleiben als physische Koordinaten erhalten.

## Begründung

**Warum zentraler Enrichment statt Signal-Änderungen?**
24 Signale einzeln anzupassen wäre unverhältnismäßig aufwendig und fehleranfällig.
Ein Pipeline-Schritt analog zu `annotate_finding_contexts()` ist wartbarer und
verursacht keine Verhaltensänderungen in der Signallogik.

**Warum SARIF-Alignment?**
SARIF v2.1.0 spezifiziert `logicalLocations` explizit für exakt diesen Zweck.
GitHub Code Scanning und andere SARIF-Konsumenten können die Information sofort nutzen.

**Alternativen verworfen:**
- *Per-Signal-Enrichment*: zu aufwendig, zu fehleranfällig
- *`symbol`-Feld allein nutzen*: zu wenig Struktur, kein `kind`/`namespace`/`class_name`

## Konsequenzen

- **Neue Datenstruktur** in `models.py` — alle Konsumenten des `Finding`-Modells
  erhalten ein optionales neues Feld
- **Backward-compatible**: Bestehende Integrationen, die `logical_location` nicht lesen,
  funktionieren unverändert
- **Symbol-Backfill**: Bestehende Konsumenten, die nur `Finding.symbol` lesen,
  profitieren sofort — Feld wird jetzt konsistent befüllt
- **Output-Schema erweitert**: JSON- und SARIF-Responses enthalten neue Felder
- **Keine Signal-Änderung**: Precision/Recall bleiben unverändert

## Validierung

```bash
# Unit-Tests für Enrichment-Logik
pytest tests/test_logical_location.py -v

# Keine Precision/Recall-Regression
pytest tests/test_precision_recall.py -v

# Selbstanalyse: logical_location in JSON-Output prüfen
drift analyze --repo . --format json --exit-zero | python -c "
import json, sys
data = json.load(sys.stdin)
locs = [f for f in data['findings'] if f.get('logical_location')]
print(f'{len(locs)}/{len(data[\"findings\"])} findings with logical_location')
"

# SARIF: logicalLocations vorhanden
drift analyze --repo . --format sarif --exit-zero | python -c "
import json, sys
data = json.load(sys.stdin)
results = data['runs'][0]['results']
with_ll = [r for r in results
           if any('logicalLocations' in loc for loc in r.get('locations', []))]
print(f'{len(with_ll)}/{len(results)} SARIF results with logicalLocations')
"

# Vollständiger CI-Check
make check
```

Policy §10 Lernzyklus-Ergebnis: **zurückgestellt** — Validierung nach Implementierung.
