---
id: ADR-063
status: proposed
date: 2026-04-12
supersedes:
---

# ADR-063: Fix-Intent — Strukturierter maschinenlesbarer Vertrag pro Agent-Task

## Kontext

Das `action`-Feld jedes Agent-Tasks (aus `fix_plan`) ist natürlichsprachlich. Agenten interpretieren
es frei — es gibt keinen maschinenprüfbaren Vertrag, der die Patch-Größe begrenzt, den betroffenen
Symbol-Bereich einschränkt oder die Art der erlaubten AST-Transformation festlegt. Das führt zu
Over-Fixing: Agenten refaktorieren über das Finding hinaus, ändern Signaturen, erzeugen neue
Abstraktionen oder bearbeiten nicht autorisierte Dateien.

Phase F in ADR-025 hat `allowed_files` und `completion_evidence` als erste Task-Vertrags-Felder
eingeführt. Diese Entscheidung ergänzt Phase F um ein vollständiges `fix_intent`-Objekt, das
Signal- und Metadaten-gestützt ableitet, welche Art von AST-Transformation erwartet wird und was
verboten ist.

## Entscheidung

Das Task-API-Response-Dict erhält ein neues Top-Level-Feld `fix_intent`. Es ist **additiv** (kein
Breaking Change) und wird rein serialisierungsseitig aus vorhandenen Task-Feldern und statischen
Signal-Lookup-Tabellen abgeleitet. Kein Live-AST-Parsing, kein neues Pflichtfeld auf dem
`AgentTask`-Dataclass, kein Scoring-Einfluss.

### Struktur des `fix_intent`-Objekts

```json
"fix_intent": {
  "edit_kind": "merge_function_body",
  "target_span": {"start_line": 10, "end_line": 30},
  "target_symbol": "process_payment",
  "canonical_source": "services/canonical.py",
  "expected_ast_delta": {
    "type": "body_replace",
    "scope": "function",
    "touches_signature": false
  },
  "allowed_files": ["services/payment.py"],
  "forbidden_changes": ["signature_change", "new_abstraction", "style_change", "unrelated_refactor"]
}
```

### Felder

| Feld | Typ | Semantik |
|------|-----|----------|
| `edit_kind` | closed string enum | Maschinenlesbare Kategorie der erwarteten Transformation |
| `target_span` | object \| null | Zeilen-Span des betroffenen Codes (`start_line`, `end_line`) |
| `target_symbol` | string \| null | FQN oder Name des primären Symbols |
| `canonical_source` | string \| null | Referenz-Datei oder Referenz-Pattern für die korrekte Form |
| `expected_ast_delta` | object | Art, Scope und Signatur-Auswirkung der Transformation |
| `allowed_files` | list[string] | Dateien, die der Agent ändern darf (Mirror von `allowed_files` auf Task-Ebene) |
| `forbidden_changes` | list[string] | Machine-readable Verbotsliste — closed enum |

### `edit_kind`-Wertemenge (geschlossen)

`merge_function_body`, `update_docstring`, `normalize_pattern`, `add_docstring`,
`add_type_annotation`, `extract_function`, `remove_import`, `delete_symbol`, `rename_symbol`,
`add_guard_clause`, `narrow_exception`, `remove_bypass`, `add_test`, `relocate_import`,
`replace_literal`, `change_default`, `add_authorization_check`, `reduce_dependencies`,
`extract_module`, `decouple_modules`, `update_exception_contract`, `unspecified`

### `forbidden_changes`-Wertemenge (geschlossen)

`signature_change`, `new_abstraction`, `implementation_change`, `cross_file_edit`,
`production_code_change`, `style_change`, `unrelated_refactor`

Die letzten beiden (`style_change`, `unrelated_refactor`) werden immer angehängt.

### Dynamische Inferenz von `edit_kind`

Für `explainability_deficit` wird `edit_kind` anhand von Finding-Metadaten übersteuert:
- `has_docstring == false` → `add_docstring`
- `has_return_type == false` → `add_type_annotation`
- `complexity > 10` (wenn Docstring + Return-Type vorhanden) → `extract_function`

Für `architecture_violation` wird Subtyp aus `title` inferiert:
- Enthält "blast" → `reduce_dependencies`
- Sonst → `remove_import`

### Implementierung

Neues Modul `src/drift/fix_intent.py` mit:
- `_EDIT_KIND_FOR_SIGNAL` — Mapping SignalType → default edit_kind
- `_EXPECTED_AST_DELTA_FOR_EDIT_KIND` — Mapping edit_kind → AST-Delta-Descriptor
- `_FORBIDDEN_CHANGES_FOR_EDIT_KIND` — Mapping edit_kind → forbidden_changes-Liste
- `_UNIVERSAL_FORBIDDEN_CHANGES` — immer angehängte Verbote
- `_refine_edit_kind()` — dynamische Übersteuerungslogik
- `derive_fix_intent()` — öffentliche Funktion, kombiniert alles

Aufgerufen in `_task_to_api_dict()` in `api_helpers.py` und `task_graph.py`, jeweils **nach**
`_derive_task_contract()` (damit `allowed_files` bereits im Dict steht).

## Explizit nicht umgesetzt

- Kein Live-AST-Parsing oder statische Analyse zur Laufzeit
- Kein neues Pflichtfeld auf `AgentTask`-Dataclass (bleibt stabil)
- Kein Scoring-Einfluss, keine Signal-Logik-Änderung
- Kein JSON-Schema-Update für `drift.output.schema.json` (betrifft nur fix_plan-Output)
- Kein Breaking Change an bestehenden Task-API-Feldern (`action`, `constraints`, `allowed_files` bleiben unverändert)
- Keine Enforcement-Logik (Advisory-Stufe, keine Server-seitige Patch-Ablehnung)

## Begründung

**Warum additives Feld statt Ersatz von `action`?** Rückwärtskompatibilität. Agenten, die `action`
heute konsumieren, brechen nicht. `fix_intent` ist opt-in für Agenten, die maschinenlesbare
Constraints auswerten wollen.

**Warum neues Modul statt Erweiterung von `_derive_task_contract`?** Die Signal-spezifische
Lookup-Tabellen-Logik wächst pro Signal und ist orthogonal zur Vertrags-Ableitung (allowed_files,
completion_evidence). Trennung vermeidet eine überwucherte `_derive_task_contract`-Funktion.

**Warum `edit_kind` als closed enum statt Freitext?** Agenten-Tooling soll auf feste Werte
branchen können (z. B. CI-Validator: "wenn `touches_signature: true`, dann PR-Review erforderlich").
Open-Ended lässt das nicht zu. Plugin-Signale landen im sicheren Fallback `unspecified`.

**Alternativen verworfen:**
- Felder flach in `_derive_task_contract` — würde Funktion auf ~80 Felder aufblasen, keine Gruppierung
- Live-AST-Parse zur Laufzeit — zu teuer für den fix_plan-Hotpath, zu viele Sprachen
- Pflichtfeld auf `AgentTask` — Dataclass-Migration, Breaking für Plugins, unnötiger Overhead

## Konsequenzen

**Positiv:**
- Agenten erhalten präzisen, maschinenprüfbaren Vertrag über Patch-Grenzen
- `forbidden_changes` ersetzt oder präzisiert natürlichsprachliche `constraints` für Tooling
- `touches_signature: true` kann CI-Gate triggern ohne Freitext-Parsing
- Kein Breaking Change, keine Migrations-Pflicht

**Trade-offs:**
- `edit_kind`-Mapping muss bei neuen Signalen gepflegt werden (Reviewer-Checkliste)
- Dynamik-Inferenz für EDS/AVS kann falsch-positiv sein wenn Metadaten fehlen (Fallback: `unspecified`)
- `fix_intent.allowed_files` dupliziert Top-Level-`allowed_files` (akzeptiert, da Vertrags-Objekt
  in sich vollständig sein soll)

## Validierung

```bash
pytest tests/test_fix_intent.py -v
pytest tests/test_api_helpers_coverage.py tests/test_task_graph_contracts_types.py tests/test_orchestration_extensions.py -v
pytest tests/test_agent_tasks.py -v
pytest tests/ -m "not slow" -q --ignore=tests/test_smoke_real_repos.py
```

**Lernzyklus-Erwartung:** `bestätigt` wenn Agenten bei Nutzung von `fix_intent.forbidden_changes`
und `edit_kind` messbar weniger Over-Fixing produzieren (beobachtbar in manuellen
Field-Test-Protokollen oder Benchmark-Auswertungen).
