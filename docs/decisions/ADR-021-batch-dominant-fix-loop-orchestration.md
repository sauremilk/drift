---
id: ADR-021
status: proposed
date: 2026-04-07
supersedes:
---

# ADR-021: Batch-Dominant Fix-Loop Orchestrierung

## Kontext

ADR-020 hat die technische Infrastruktur für Batch-Reparaturen geschaffen: Fix-Template-Äquivalenzklassen, `batch_eligible` Metadaten, `affected_files_for_pattern`, `resolved_count_by_rule`, Signal-Filter im Diff, Fix-Loop-Protokoll im MCP-Prompt.

Das operative Problem bleibt: Die Agent-Instruktionen über die fünf API-Endpunkte hinweg transportieren widersprüchliche Mentalmodelle.

**Widerspruch 1 — Scan vs. Fix-Loop-Protokoll:**
`scan()` sagt: *"After each file change, call drift_diff(uncommitted=True) to verify improvement before proceeding."*
Der MCP Fix-Loop-Protokoll sagt: *"Apply the fix to ALL affected_files_for_pattern… Verify the batch with a single drift_diff call, not per-file."*

**Widerspruch 2 — Fix-Plan Default vs. Fix-Loop:**
`fix_plan()` ohne batch_eligible Tasks: *"After each file change… Do not batch changes."*
Aber der Agent kam über den Fix-Loop-Prompt hierher, der Batching erlaubt.

**Widerspruch 3 — Nudge vs. Batch-Modus:**
`nudge()` sagt immer: *"After each file change, call drift_nudge…"*
MCP-Prompt Punkt 8 sagt: *"drift_nudge — get directional feedback after each file change (do not batch)"*

**Konsequenz:** Der Agent bekommt je nach Einstiegspunkt verschiedene Handlungsmodelle und fällt auf den konservativsten zurück: Datei-für-Datei-Verifikation.

**Beobachtete Auswirkung (aus Agententests 2026-03-30, 2026-03-31):**
- Gesamtlaufzeit >50h bei 100-200 Findings
- <5 Findings pro Iteration
- Agent bricht bei unklaren Diff-Ergebnissen ab
- Kein wahrnehmbarer Fortschritt in den ersten 10+ Iterationen

## Entscheidung

### Wird getan:

**1. Einheitliches Agent-Instruktionsmodell über alle Endpunkte:**

Alle `agent_instruction` Felder folgen einem gemeinsamen Entscheidungsbaum:
- **Wenn batch_eligible Tasks vorhanden:** → Batch zuerst, Sammelverifikation via `drift_diff`
- **Wenn keine batch_eligible Tasks:** → Per-Datei-Verifikation via `drift_nudge` (schnell) oder `drift_diff` (vollständig), je nach Kontext
- **Scan verweist auf Fix-Plan als Einstieg**, nicht direkt auf Diff

**2. Scan-Instruktion batch-aware machen:**

Bisherig:
```
Use drift_fix_plan to get prioritised repair tasks.
After each file change, call drift_diff(uncommitted=True) to verify improvement before proceeding.
```

Neu (kontextabhängig):
```
# Bei vielen Findings (>20):
Use drift_fix_plan(max_tasks=20) to get prioritised repair tasks.
Start with batch_eligible tasks for maximum throughput.
Verify batches with drift_diff, not per-file.

# Bei wenigen Findings (≤20):
Use drift_fix_plan to get prioritised repair tasks.
After each fix, call drift_nudge for fast feedback.
```

**3. Fix-Plan-Instruktion Batch-dominanter machen:**

Der nicht-batch Standardpfad erlaubt `drift_nudge` als schnelle Alternative:
```
After each fix, call drift_nudge for fast directional feedback.
Use drift_diff only for full regression analysis or before committing.
```

**4. MCP Fix-Loop-Protokoll: Nudge/Diff-Grenze klar definieren:**

- `drift_nudge` = schnelle Richtungsprüfung nach jedem Edit (**innerhalb** eines Batches erlaubt)
- `drift_diff` = vollständige Verifikation **nach** einem abgeschlossenen Batch oder vor Commit
- Streichung von "do not batch" beim Nudge-Toolhinweis

**5. Diff agent_hint batch-aware machen:**

Wenn die letzte fix_plan-Antwort batch_eligible Tasks enthielt, verweist der Diff-Hint auf den nächsten Batch statt auf Datei-für-Datei-Weiterarbeit.

### Wird explizit NICHT getan:

- Kein Ändern des `max_tasks` CLI-/API-Defaults (bleibt 5) — Token-Budget-Schutz.
- Kein automatisches Hochsetzen bei batch_eligible Tasks — stattdessen wird im Fix-Loop-Protokoll `max_tasks=20` empfohlen.
- Keine Änderung an Scoring, Signalen oder Analyse-Logik.
- `schema_version` bleibt "2.0" — nur `agent_instruction` Texte und Steuerungslogik ändern sich.

## Begründung

- **CC-3 Auflösung aus ADR-020:** „Agent-Instruktionen maximieren Korrektheit per Edit, minimieren nicht Edits per Finding." Diese ADR löst genau diesen Common Cause auf.
- **Kein API-Breaking-Change:** Nur `agent_instruction` Plaintext ändert sich — kein Feld wird umbenannt, entfernt oder typisiert.
- **Nudge als Inner-Loop, Diff als Outer-Loop:** Nudge ist 10-100× schneller als Diff und eignet sich für den tight feedback loop. Diff bleibt für Batch-Abschluss und Commit-Gating.
- **Konservatives Fallback:** Wenn keine batch_eligible Tasks vorhanden → altes per-Datei-Modell bleibt erhalten. Batch-Dominanz ist nur der Standard, wenn die Metadaten es stützen.

**Verworfene Alternativen:**
- `max_tasks` Default auf 20 erhöhen: Riskiert Token-Überlauf bei kleinen Repos.
- Automatische Batch-Erkennung im Agent statt in der Instruktion: Agent-Prompts sind nicht deterministisch genug.
- Diff komplett durch Nudge ersetzen: Nudge hat "estimated" Confidence für cross-file Signale — Diff bleibt als Verifikations-Gold-Standard nötig.

## Konsequenzen

- **Agent-Verhalten ändert sich:** Bei batch_eligible Tasks wird der Default-Workflow von per-Datei auf batch-first umgestellt.
- **Nudge wird leichtgewichtiger positioniert:** "Jederzeit nutzbar, auch innerhalb eines Batches" statt "nach jeder Datei und nur einzeln".
- **Diff wird als Batch-Abschluss positioniert:** Nicht mehr nach jeder einzelnen Dateiänderung, sondern nach abgeschlossener Reparaturwelle.
- **Abwärtskompatibel:** Bestehende Agenten, die `agent_instruction` ignorieren, sind nicht betroffen. Agenten, die es befolgen, werden effektiver.
- **Audit-Pflicht:** `stride_threat_model.md`, `risk_register.md` (Output-Kanal-Änderung: agent_instruction Texte).
- **Keine ADR für Signale nötig:** Keine Signal-, Scoring- oder Architektur-Grenz-Änderungen.

## Validierung

```bash
# Instruktions-Konsistenz: Kein "After each file change, call drift_diff" mehr in Batch-Kontexten
grep -rn "After each file change.*drift_diff" src/drift/api.py
# Erwartung: 0 Treffer (alle durch kontextabhängige Verzweigung ersetzt)

# Tests grün
pytest tests/test_batch_metadata.py -v
pytest tests/ --tb=short --ignore=tests/test_smoke.py -q

# MCP-Prompt: "do not batch" entfernt bei Nudge-Toolbeschreibung
grep "do not batch" src/drift/mcp_server.py
# Erwartung: 0 Treffer in Tool-Workflow-Sektion
```

**Lernzyklus-Ergebnis:** `unklar` — erfordert Real-Agent-Test mit ≥50 Findings zur Messung von Fix-Durchsatz-Delta.
