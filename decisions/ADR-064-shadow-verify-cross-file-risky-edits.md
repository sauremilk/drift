---
id: ADR-064
status: proposed
date: 2025-07-22
supersedes: []
related: [ADR-024, ADR-025, ADR-063]
---

# ADR-064: Shadow-Verify für Cross-File-Risky Edit-Klassen

## Status

proposed

## Context

ADR-063 (Fix-Intent) klassifiziert jeden Agent-Task mit einer maschinenlesbaren
`edit_kind`-Klasse.  Einige dieser Klassen — insbesondere `remove_import`,
`relocate_import`, `reduce_dependencies`, `extract_module`, `decouple_modules`,
`delete_symbol` und `rename_symbol` — verändern Import-Graphen,
Symbol-Sichtbarkeiten oder Modul-Grenzen.

`drift_nudge` arbeitet inkrementell: File-lokale Signale werden neuberechnet;
cross-file-Signale (co_change_coupling, circular_import, fan_out_explosion,
architecture_violation, …) werden mit geschätzter Konfidenz weitergeführt.
Diese Schätzung ist für die oben genannten Edit-Klassen **nicht ausreichend**,
weil die Edits genau die Strukturen verändern, über die cross-file-Signale
urteilen.

Ein Agent, der nach `remove_import` nur `drift_nudge` aufruft, könnte als
Ergebnis `safe_to_commit == true` erhalten, obwohl der Import anderswo noch
verwendet wird.

## Decision

Für jeden Task, dessen `refined_edit_kind` in `CROSS_FILE_RISKY_EDIT_KINDS`
enthalten ist, wird:

1. `AgentTask.shadow_verify = True` gesetzt.
2. `AgentTask.shadow_verify_scope` mit den relevanten Dateien befüllt:  
   Seed = `{task.file_path} ∪ task.related_files`,  
   erweitert um `related_files` aller Nachbar-Tasks aus
   `task.depends_on ∪ task.blocks` (Task-Graph-Nachbarn, kein AST-Parsing).
3. Im `completion_evidence`-Feld des Task-Vertrags:  
   `tool = "drift_shadow_verify"` statt `"drift_nudge"`,  
   `predicate = "shadow_clean == true"`.
4. Im `verify_plan` wird vor dem abschließenden nudge-Schritt ein
   `drift_shadow_verify`-Schritt eingefügt.

Ein neuer API-Endpunkt `drift.api.shadow_verify.shadow_verify()` und das
entsprechende MCP-Tool `drift_shadow_verify` führen einen **vollen**,
nicht-inkrementellen `analyze_repo()`-Aufruf durch, filtern die Findings auf
`scope_files` und vergleichen sie mit dem aktuellen Baseline.

### Cross-File-Risky Edit-Klassen

```python
CROSS_FILE_RISKY_EDIT_KINDS = frozenset({
    EDIT_KIND_REMOVE_IMPORT,      # "remove_import"
    EDIT_KIND_RELOCATE_IMPORT,    # "relocate_import"
    EDIT_KIND_REDUCE_DEPENDENCIES,# "reduce_dependencies"
    EDIT_KIND_EXTRACT_MODULE,     # "extract_module"
    EDIT_KIND_DECOUPLE_MODULES,   # "decouple_modules"
    EDIT_KIND_DELETE_SYMBOL,      # "delete_symbol"
    EDIT_KIND_RENAME_SYMBOL,      # "rename_symbol"
})
```

### Response von `drift_shadow_verify`

| Feld | Typ | Bedeutung |
|------|-----|-----------|
| `shadow_clean` | bool | True wenn keine neuen Findings im Scope |
| `safe_to_merge` | bool | True wenn `shadow_clean` und `delta <= 0` |
| `delta` | float | Score-Änderung vs. Baseline (positiv = Regression) |
| `scope_files` | list[str] | Geprüfte Dateien |
| `new_findings_in_scope` | list | Neu eingeführte Findings |
| `resolved_findings_in_scope` | list | Behobene Findings |
| `agent_instruction` | str | Handlungsempfehlung |
| `next_tool` | str | "drift_nudge" (wenn clean) oder "drift_fix_plan" |

## Consequences

**Positiv:**
- Agenten erhalten für riskante Edits eine deterministische Bestätigung statt
  inkrementeller Schätzung.
- Das Task-Vertragssystem (ADR-024) bleibt einheitlich: completion_evidence
  steuert das Verifikationsprotokoll.
- Der Scope ist durch Task-Graph-Nachbarn begrenzt — kein vollständiger
  Repo-Scan in der Feedback-Schleife nötig.

**Negativ / Trade-offs:**
- `drift_shadow_verify` ist langsamer als `drift_nudge` (voller
  `analyze_repo()`-Aufruf), begrenzt durch `scope_files` aber nicht
  inkrementell.
- Bei sehr großen Repos mit vielen Task-Graph-Nachbarn kann `shadow_verify_scope`
  breit werden.  Dieser Fall sollte zukünftig durch einen `--max-scope`-Parameter
  adressiert werden.
- Die Findungs-Identität basiert auf `signal_type + file_path + title` (kein
  stabiler UUID).  Umbenennung einer Datei kann False-Positives erzeugen.

## Decision Trailer

- Entscheider: Mick Gottschalk (Maintainer)
- Reviewer: —
- ADR angelegt: 2025-07-22
- Implementierung: Phase 1–10 (src/drift/fix_intent.py, models.py,
  output/agent_tasks.py, api_helpers.py, api/shadow_verify.py, mcp_server.py)
