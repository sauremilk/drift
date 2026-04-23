---
id: ADR-071
status: proposed
date: 2026-04-13
supersedes:
---

# ADR-071: Mirror Output Mode — Prescriptive vs. Diagnostic Experiment

## Kontext

Drift's API-Responses enthalten zwei kategorial verschiedene Informationsschichten:

1. **Diagnostisch**: Strukturelle Fakten — Findings, Scores, Deltas, Trends, Datei-Beziehungen, Severity-Klassifikationen, Automation-Fitness.
2. **Prescriptive**: Handlungsanweisungen — `agent_instruction`, `next_tool_call`, `workflow_plan`, `constraints`, `verify_plan`, `success_criteria`, `guardrails`, `guardrails_prompt_block`, `negative_context`, `fix_intent`, `regression_guidance`.

Die Hypothese: Moderne Coding-Agenten (Claude, GPT-4, Gemini) benötigen primär **Sichtbarkeit auf das, was sie nicht sehen können** (cross-file Patterns, historischen Drift, Regressionsketten) — nicht Anweisungen, was zu tun ist. Die prescriptive Schicht könnte kontraproduktiv sein, weil sie:

- Kontext-Budget mit Instruktionen füllt statt mit strukturellen Fakten
- Den Agenten in vorgegebene Tool-Choreografie zwingt
- Impliziert, dass der Agent die Lösung nicht selbst finden kann

Gegenhypothese: Die prescriptive Schicht verhindert Over-Fixing, Regressions und Scope-Creep, die der Agent ohne Leitplanken produzieren würde.

## Entscheidung

Einen konfigurierbaren `output_mode: "full" | "mirror"` in `drift.yaml` einführen, der die prescriptive Schicht entfernt ohne die diagnostische zu berühren. Das ermöglicht einen A/B-Vergleich auf identischen Findings.

### Was getan wird

- `output_mode` Feld in DriftConfig (default `"full"` — kein Breaking Change)
- `apply_output_mode()` in `response_shaping.py` als Post-Serialization-Filter
- Verdrahtung in allen 10 API-Endpoints + MCP-Server-Autopilot (16 Call-Sites)
- Quantitativer Vergleich auf dem Drift-Repo selbst

### Was explizit nicht getan wird

- Keine Entfernung der prescriptive Logik aus dem Code (sie wird nur gefiltert, nicht gelöscht)
- Keine Änderung an Signalen, Scoring oder Output-Schema
- `safe_to_commit` bleibt als Gate-Mechanismus erhalten (nicht prescriptive, sondern konditional)
- Kein Big-Bang-Umbau — Entscheidung über weiteres Vorgehen basiert auf Evidenz

## Experiment-Ergebnisse

### Quantitativer Self-Scan (Drift-Repo, 708 Findings)

| Endpoint | Full (bytes) | Mirror (bytes) | Reduktion | Presc. Keys entfernt |
|----------|-------------:|---------------:|----------:|---------------------:|
| scan     |       21.279 |         21.281 |     ~0,0% | 0                    |
| fix_plan |       19.832 |          8.079 |    59,3%  | 46 (6 Top + 40 Task) |
| brief    |       13.611 |          1.593 |    88,3%  | 5 Top                |
| **Summe**|   **54.722** |     **30.953** | **43,4%** | **51**               |

### Beobachtungen

1. **scan ist bereits diagnostisch.** Keine prescriptive Top-Level-Keys im Scan-Output — die Prescriptive-Last sitzt in fix_plan und brief.
2. **fix_plan ist der Prescriptive-Hotspot.** 59% Reduktion, weil jede der 5 Tasks 8 prescriptive Felder trägt (`action`, `constraints`, `success_criteria`, `verify_plan`, `expected_effect`, `negative_context`, `regression_guidance`, `repair_exemplar`).
3. **brief ist zu 88% prescriptive.** Guardrails und Prompt-Blocks dominieren — nur 1.593 von 13.611 Bytes sind strukturelle Information.
4. **Alle 708 Findings bleiben vollständig erhalten.** Kein diagnostischer Informationsverlust.
5. **Token-Budget-Proxy:** 43,4% weniger Output-Volumen bedeutet ~43% mehr Agent-Kontextbudget für eigene Überlegungen bei identischem diagnostischem Gehalt.

### Prescriptive Keys, die im Mirror-Modus entfernt werden

**Top-level (9 Keys):**
`agent_instruction`, `next_tool_call`, `fallback_tool_call`, `done_when`, `workflow_plan`, `recommended_next_actions`, `guardrails`, `guardrails_prompt_block`, `negative_context`

**Per-Task (11 Keys):**
`action`, `constraints`, `success_criteria`, `verify_plan`, `expected_effect`, `negative_context`, `regression_guidance`, `repair_exemplar`, `fix_intent`, `fix_template_class`, `repair_maturity`

### Diagnostische Keys, die erhalten bleiben (Auswahl)

`drift_score`, `severity`, `findings`, `finding_count`, `top_signals`, `trend`, `score_delta`, `safe_to_commit`, `direction`, `automation_fitness`, `related_files`, `file`, `signal`, `title`, `description`, `metadata`, `finding_context`, `cross_validation`, `ai_ratio`, `blocking_reasons`

## Begründung

### Warum Mirror-Mode statt Entfernung

Ein Switch erlaubt den Vergleich ohne irreversible Änderungen. Wenn das Experiment zeigt, dass die prescriptive Schicht doch hilft (Gegenhypothese bestätigt), genügt `output_mode: full` als Default.

### Warum Post-Serialization-Filter

Die Alternative — prescriptive Felder gar nicht erst zu generieren — hätte tiefgreifende Änderungen an `agent_tasks.py` (~650 LOC), `guardrails.py`, `negative_context.py` und allen Task-Serialisierungen erfordert. Der Post-Filter ist minimal-invasiv: eine Funktion, ein Aufruf pro Endpoint.

### Verworfene Alternativen

1. **Separates `drift_mirror`-Tool**: Würde MCP-Tool-Registrierung duplizieren und die Wartungslast verdoppeln.
2. **Response-Profile `"mirror"`**: Profile filtern auf Whitelist-Basis (behalten was gelistet ist), Mirror filtert auf Blacklist-Basis (entfernen was prescriptive ist). Semantisch verschieden.
3. **Sofortige Entfernung der prescriptive Schicht**: Irreversibel ohne Evidenz.

## Konsequenzen

- **Default bleibt `full`** — kein Risiko für bestehende Nutzer oder MCP-Clients
- **Experiment-Infra steht** — A/B-Vergleich mit realen Agent-Sessions kann gestartet werden
- Die quantitative Evidenz zeigt, DASS Mirror signifikant reduziert — aber noch nicht, OB das den Agenten besser oder schlechter macht
- Nächster Schritt: `mirror_ab_study.py` mit GPT-4o-Klasse-Modell und `--repeats 3` ausführen

## Validierung

### Unit-Tests (bereits bestanden)

```bash
pytest tests/test_output_mode_mirror.py -v        # 11 Tests
pytest tests/ --ignore=tests/test_smoke_real_repos.py -m "not slow" -q -n auto  # 4730 Tests
python scripts/_mirror_experiment.py               # Quantitative Größen-Evidenz
```

### Automatisierte LLM-Evaluation (mirror_ab_study)

Vollautomatische Pipeline — klont Repos, scannt mit Drift, erzeugt gepaarte Prompts
(full vs. mirror fix_plan), sendet an LLM, wendet Patches an, misst via `drift diff`:

```bash
python scripts/mirror_ab_study.py generate-tasks --max-per-repo 5
python scripts/mirror_ab_study.py run-llm --model gpt-4o --temperature 0.2
python scripts/mirror_ab_study.py evaluate
python scripts/mirror_ab_study.py stats
python scripts/mirror_ab_study.py assemble
```

**Lokaler Lauf (Ollama, ohne API-Key):**
```bash
python scripts/mirror_ab_study.py run-llm \
    --base-url http://localhost:11434/v1 --model qwen2.5-coder:14b
```

**Baseline-Ergebnis (qwen2.5-coder:14b, 10 Tasks × 2 Arme):**

| Metrik | Full | Mirror | p-Wert |
|--------|------|--------|--------|
| new_findings (mean) | 8.0 | 10.0 | 0.284 (MW-U) |
| accept_rate | 0% | 0% | 1.0 (Fisher) |
| Apply-Rate | 6/10 | 4/10 | — |

Interpretation: `null_result` — zu wenig gepaarte Datenpunkte (3 von 5 nötig)
für statistisch belastbare Aussage. Die Apply-Rate ist mit einem 14B-Modell
erwartungsgemäß niedrig (~50%). Mit GPT-4o wird die Diff-Qualität und
damit die Apply-Erfolgsrate signifikant steigen.

**Nächste Schritte für belastbare Evidenz:**
1. Re-Run mit GPT-4o (höhere Diff-Qualität → >80% Apply-Rate)
2. `--repeats 3` für statistische Power (≥5 gepaarte Tasks)
3. Mehr Repos einbeziehen (`--max-per-repo 8`)
4. Lernzyklus-Ergebnis: `bestätigt` | `widerlegt` | `unklar`

### Evidenz-Artefakte

- `benchmark_results/mirror_experiment_evidence.json` — quantitative Ergebnisse (Größenvergleich)
- `benchmark_results/mirror_ab_study.json` — qualitative LLM-A/B-Ergebnisse
- `scripts/_mirror_experiment.py` — reproduzierbares Quantitativ-Experiment
- `scripts/mirror_ab_study.py` — vollautomatischer LLM-A/B-Workflow
- `tests/test_output_mode_mirror.py` — Regressionstests für den Filter
