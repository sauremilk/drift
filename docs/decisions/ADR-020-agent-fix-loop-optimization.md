---
id: ADR-020
status: proposed
date: 2026-04-07
supersedes:
---

# ADR-020: Agent Fix-Loop Latenz-Optimierung

## Kontext

Eine Fault-Tree-Analyse (FTA) der Coding-Agent-Fix-Latenz bei großen Finding-Mengen (100–200 aktive Findings) identifiziert sieben Minimal Cut Sets (MCS) und drei Common Causes, die zusammen >50h Gesamtlaufzeit verursachen. Das Top Event entsteht durch die multiplikative Kombination von hoher Zykluszeit pro Fix-Iteration (>10 min/Finding) und niedriger Fix-Dichte pro Iteration (<5 Findings/Zyklus).

**Primärursachen (SPOFs):**
- **MCS-1:** `fix_plan` gruppiert Tasks nicht nach Fix-Template-Äquivalenzklassen — der Agent behandelt jeden Task isoliert, obwohl 1 Fix 20 gleichartige Findings auflösen könnte.
- **MCS-2:** Kein Session-Persistenz-Mechanismus im dokumentierten Fix-Loop-Workflow — nach Unterbrechung gibt es keinen Wiederaufnahme-Punkt.
- **MCS-3:** `diff()` unterstützt keinen Signal-Filter — jede Verifikation analysiert alle Findings, nicht nur das gerade reparierte Signal.

**Combined MCS:**
- **MCS-4:** 5-Task-Default + kein Fix-Loop-Modus im System Prompt.
- **MCS-5:** Kein `affected_files_for_pattern` + kein `remaining_count` Hinweis bei Truncation.
- **MCS-6:** Kein `resolved_count_by_rule` + falsches Agent-Mentalmodell (1 Fix = 1 Finding).
- **MCS-7:** `drift baseline save` nicht Teil des dokumentierten Fix-Loop-Workflows.

**Common Causes:**
- **CC-1:** Fehlende Fix-Template-Klassen-Abstraktion → aktiviert MCS-1, MCS-5, MCS-6.
- **CC-2:** Fehlende Session-Persistenz / inkrementelle Analyse → aktiviert MCS-2, MCS-3, MCS-7.
- **CC-3:** Agent-Instruktionen maximieren Korrektheit per Edit, minimieren nicht Edits per Finding.

## Entscheidung

### Wird getan (4 Phasen):

**Phase 0 — MCP System Prompt (kein Code):**
- Fix-Loop-Session-Protokoll in `_BASE_INSTRUCTIONS` ergänzen: Session-Start mit `drift baseline save`, Batch-Awareness bei `batch_eligible` Tasks, Session-Resume via Baseline-Diff.
- `agent_instruction` in `fix_plan()` kontextabhängig: Batch-eligible Tasks → Batch erlaubt, sonst per-file verify.
- `max_tasks` Default bleibt 5; Fix-Loop-Protokoll empfiehlt explizit 20.

**Phase 2 — Batch-Metadata in fix_plan (API-Erweiterung):**
- Neue Funktion `_compute_fix_template_class()` in `agent_tasks.py` — signalspezifische Äquivalenzklassen.
- Batch-Metadata pro Task: `batch_eligible`, `pattern_instance_count`, `affected_files_for_pattern`, `fix_template_class`.
- Neue Top-Level-Felder in `fix_plan()`: `remaining_by_signal`.
- Neue Felder in `scan()`: `total_finding_count`, `remaining_by_signal`.

**Phase 3 — Diff-Enrichment (API-Erweiterung):**
- `resolved_count_by_rule` Aggregation in `diff()` Response.
- `signals` / `exclude_signals` Filter für `diff()` API, MCP Tool und CLI.
- `suggested_next_batch_targets` in `diff()` Response.

**Phase 4 — Batch-Repair-Modus:**
- "BATCH REPAIR MODE" im MCP System Prompt als Opt-in bei `batch_eligible` Tasks.
- Kontextabhängige `agent_instruction` basierend auf Batch-Eligible-Count.
- Batch-Repair-Ausnahme in `drift-quality-workflow.instructions.md`.

### Wird explizit NICHT getan:

- Kein inkrementeller Rescan-Pfad (selektiver Rescan nur für geänderte Dateien) — zu komplex für Phase 1, Signale sind größtenteils cross-file.
- Kein `session_id` / Resumption-Token in der API — stattdessen Baseline als einfacherer Persistenz-Mechanismus.
- Kein Ändern des `max_tasks` Defaults — Token-Budget-Schutz bleibt erhalten.
- `schema_version` bleibt "2.0" — alle neuen Felder sind additiv.

## Begründung

- **MCS-Priorisierung:** MCS-1 (Batch-Metadata) hat SPOF-Status und den höchsten theoretischen Impact — 1 Fix kann 20 Findings auflösen. MCS-2 (Session-Protokoll) ist sofort umsetzbar ohne Code. MCS-3 (Signal-Filter) reduziert die Verifikationszeit.
- **CC-1 Auflösung:** Die Fix-Template-Klassen-Abstraktion löst drei MCS gleichzeitig.
- **CC-3 Kompromiss:** Statt die "minimale Änderungen"-Regel aufzuheben, wird eine explizite Batch-Repair-Ausnahme für `batch_eligible` Tasks eingeführt — der Korrektheits-Guardrail bleibt für nicht-batch Tasks erhalten.
- **Additive Response-Felder:** Bestehende Integrationen brechen nicht. Neue Felder sind optionale Enrichments.
- **Baseline statt Session-Token:** Die existierende Baseline-Infrastruktur (`drift baseline save/diff`) wird als Session-Persistenz wiederverwendet — kein neues Konzept nötig.

**Verworfene Alternativen:**
- Inkrementeller Rescan: Zu komplex, cross-file-Signale (AVS, CCC, MDS) erfordern Repo-weite Analyse.
- `max_tasks` Default erhöhen: Riskiert Token-Budget-Überlauf bei Repos mit vielen Findings.
- Universeller String-Match auf `action`-Text für Äquivalenzklassen: Zu instabil, signalspezifische Logik ist präziser.

## Konsequenzen

- **Neue Response-Felder:** 4 Task-Level-Felder (`batch_eligible`, `pattern_instance_count`, `affected_files_for_pattern`, `fix_template_class`), 3 Top-Level-Felder in fix_plan/scan (`remaining_by_signal`, `total_finding_count`), 3 Felder in diff (`resolved_count_by_rule`, `batch_resolution_summary`, `suggested_next_batch_targets`).
- **Geändertes Agent-Verhalten:** Fix-Loop-Protokoll ändert das empfohlene Vorgehen bei >20 Findings fundamental — von "ein Finding nach dem anderen" zu "batch-eligible Gruppen zusammenfassen".
- **Audit-Pflicht:** `stride_threat_model.md` und `risk_register.md` müssen aktualisiert werden (Output-Kanal-Änderung).
- **Trade-off:** Bei `response_detail="concise"` werden `affected_files_for_pattern` Felder die Response vergrößern — Token-Budget-Impact muss gemessen werden.

## Validierung

**Messbare Checks:**

```bash
# Unit-Tests für alle neuen Response-Felder
pytest tests/test_agent_tasks.py tests/test_scan_diversity.py tests/test_diff_regression.py -v

# Selbstanalyse: fix_plan auf Drift selbst enthält batch_eligible Felder
drift fix-plan --repo . --format json | python -c "
import json, sys
data = json.load(sys.stdin)
tasks = data.get('tasks', [])
batch = [t for t in tasks if t.get('batch_eligible')]
print(f'batch_eligible tasks: {len(batch)}/{len(tasks)}')
"

# Alle Checks grün
make check
```

**Erwartetes Lernzyklus-Ergebnis:** `unklar` — empirische Validierung der Gesamtlaufzeit-Reduktion erfordert Agent-Loop-Benchmark mit realen Repos (>100 Findings). Benchmark-Design ist Teil der Phase-2-Implementierung.

**Evidence-Artefakte:**
- `benchmark_results/` — Agent-Loop-Benchmark vorher/nachher
- `tests/` — Unit-Tests für Batch-Metadata, Diff-Enrichment, Signal-Filter
- `audit_results/` — STRIDE und Risk Register Updates
