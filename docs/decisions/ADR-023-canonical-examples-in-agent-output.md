---
id: ADR-023
status: proposed
date: 2026-04-08
supersedes:
---

# ADR-023: Canonical Examples in Agent-Output (fix_plan + brief)

## Kontext

Drift liefert Coding-Agenten bereits maschinenlesbare Anti-Patterns (NegativeContext, Guardrails) und Reparaturpfade (AgentTask in fix_plan). Agenten profitieren jedoch stärker von **positiven Referenzen** — konkreten Beispielen aus der analysierten Codebasis, die zeigen, wie es richtig gemacht wird.

Die Daten existieren bereits intern:
- **PFS** erzeugt `canonical_exemplar` und `canonical_variant` in Finding.metadata
- **NegativeContext** hat ein `canonical_alternative` Feld mit der bevorzugten Lösung
- Diese Informationen gehen beim Packaging verloren:
  - `Guardrail` übernimmt `canonical_alternative` nicht aus NegativeContext
  - `_task_to_api_dict()` serialisiert keine positiven Referenzen aus AgentTask

## Entscheidung

### Was getan wird

1. **Guardrail-Dataclass** erhält `preferred_pattern: str = ""` — übernommen aus `NegativeContext.canonical_alternative`
2. **Guardrail prompt_block** zeigt nach jeder Constraint-Zeile optional eine `PREFERRED:` Zeile
3. **fix_plan Task-Serialisierung** erhält `canonical_refs: list[dict]` — extrahiert aus:
   - `AgentTask.metadata["canonical_exemplar"]` (File:Line-Ref, z.B. von PFS)
   - `AgentTask.negative_context[*].canonical_alternative` (Code-Snippet/Rationale)
4. Jede canonical_ref hat die Struktur: `{"type": "file_ref"|"pattern", "ref": "...", "source_signal": "PFS"}`
5. Maximum 3 Refs pro Task (Token-Budget)

### Was explizit nicht getan wird

- Kein neues `PositiveContext`-Dataclass — die Daten kommen aus bestehender Metadata + NegativeContext
- Keine neuen Signal-Felder in BaseSignal — nur Convention für Metadata-Keys
- Kein schema_version Bump — additive Felder sind backward-compatible
- Keine Phase-2-Erweiterung einzelner Signale (MDS, AVS, etc.) in diesem ADR — das ist ein separater Schritt

## Begründung

**Warum positive Refs statt nur Anti-Patterns?**
- Coding-Agenten generieren Code schneller und korrekter, wenn sie ein konkretes Zielbeispiel sehen
- "Consolidate to dominant pattern (exemplar: services/handler_a.py:5)" ist maschinenlesbarer als "Do not introduce another variant"
- Die Daten existieren bereits — es ist ein Surfacing-Problem, kein Daten-Problem

**Warum kein PositiveContext-Dataclass?**
- Over-Engineering für Phase 1; die Daten kommen aus genau zwei Quellen (Metadata + NegativeContext)
- Falls Phase 2 mehr Signale mit Canonical-Daten anreichert, kann ein Dataclass nachgelagert eingeführt werden

**Warum max 3 Refs pro Task?**
- Token-Budget für MCP-Responses; mehr Refs bedeuten mehr Kontext-Overhead ohne proportionalen Nutzen

## Konsequenzen

- **Guardrail.to_dict()** liefert ein neues `preferred_pattern` Feld (leer wenn nicht verfügbar)
- **fix_plan Tasks** liefern ein neues `canonical_refs` Array (leer wenn nicht verfügbar)
- **prompt_block** enthält optional `PREFERRED:` Zeilen — Agenten können diese direkt als Zielreferenz verwenden
- **MCP-Surface** (`drift_brief`, `drift_fix_plan`) profitiert automatisch (JSON-Passthrough)
- **Bestehende Konsumenten** sind nicht betroffen (additive Felder, keine Breaking Changes)

### Betroffene Artefakte

| Datei | Änderung |
|-------|----------|
| `src/drift/guardrails.py` | `preferred_pattern` Feld + Prompt-Block-Erweiterung |
| `src/drift/api_helpers.py` | `canonical_refs` in `_task_to_api_dict()` |
| `tests/test_brief.py` | Tests für preferred_pattern in Guardrails |
| `tests/test_batch_metadata.py` | Tests für canonical_refs in Task-API-Dict |
| `audit_results/stride_threat_model.md` | Output Trust-Boundary-Update |
| `audit_results/risk_register.md` | Neuer Eintrag für Output-Format-Erweiterung |

## Validierung

```bash
pytest tests/test_brief.py -v --tb=short
pytest tests/test_batch_metadata.py -v --tb=short
drift fix-plan --repo . --format json | python -c "import sys,json; d=json.load(sys.stdin); assert any('canonical_refs' in t for t in d.get('tasks',[]))"
drift brief --task 'refactor auth' --repo . --format json | python -c "import sys,json; d=json.load(sys.stdin); assert any('preferred_pattern' in g for g in d.get('guardrails',[]))"
```

Erwartetes Lernzyklus-Ergebnis: `bestaetigt` — wenn Agenten die positiven Referenzen in MCP-Responses konsumieren und Code-Qualität messbar steigt.
