# Risk Register

## 2026-05-04 - ADR-092: `llms.txt` autogen aus signal_registry (Paket 1C)

- Risk ID: RISK-ADR-092-LLMS-DISCOVERY
- Component: `scripts/generate_llms_txt.py`, `llms.txt`, `scripts/check_model_consistency.py` (Checks 5+6 delegiert), `.githooks/pre-push` Schritt `[0/6]`, `.github/workflows/release.yml` Schritt "Sync version refs".
- Type: Documentation / Discovery-Surface — keine neue Trust-Boundary, kein externer Input, kein Scoring-Pfad. Datei ist Public-Read-Only Discovery-Oberfläche für LLM-Konsumenten.
- Description: `llms.txt` wird deterministisch aus `pyproject.toml` (Version) und `src/drift/signal_registry.py` (Signale) regeneriert. Pre-Push-Hook und Release-Workflow rufen den Generator auf; Drift auf `main` wird durch `check_model_consistency.py` geblockt.
- Severity: MEDIUM — Die Datei wird von externen Agenten, Skills und LLM-Tools als Ground-Truth-Inventar der drift-Signale konsumiert. Drift zwischen Datei und Registry unterläuft ADR-091-Grounding und die öffentliche Dokumentation.
- Triggers:
  - Neues Signal in `signal_registry.py` registriert, ohne `scripts/generate_llms_txt.py --write` auszuführen.
  - Maintainer editiert `llms.txt` manuell (z. B. um ein SEO-Label zu ändern) und die Änderung geht bei der nächsten Regeneration verloren.
  - Security-Signal bekommt CWE-Tag im Code, aber `_DOC_OVERRIDES`-Eintrag im Generator wird vergessen.
  - `DRIFT_SKIP_VERSION_SYNC=1` Bypass bleibt als Default-Env gesetzt, Pre-Push-Hook repariert nicht mehr.
- Impact without mitigation:
  - Öffentliche Discovery-Datei listet weniger Signale als tatsächlich existieren (TSB-Fall vor Paket 1C).
  - Weight-Tabelle in `llms.txt` widerspricht `SignalWeights`-Defaults → externe Studien zitieren falsche Gewichtung.
  - Release-Notes geben neuen Tag bekannt, während `llms.txt` noch den vorherigen `Release status` zeigt.
- Mitigations:
  - Deterministischer Generator: gleiche Inputs → byte-identische Ausgabe; keine editorialen Tie-Breaks im Code.
  - Pre-Push-Hook Schritt `[0/6]` repariert und committet still (ein `chore: sync version refs` pro Push).
  - `check_model_consistency.py` ruft `--check` per Subprocess → CI-Gate identisch zum lokalen Generator.
  - 7 Regressionstests in `tests/test_llms_txt_generator.py` decken `--check` exit-Verhalten, Idempotenz, Versions-Rundlauf, vollständige Abkürzungs-Abdeckung, Counts und Gewicht-Roundtrip ab.
  - Release-Workflow amend+re-tagt nur, wenn tatsächlich Dateien geändert wurden; keine leeren Re-Tags.
  - ADR-092 dokumentiert Scope (nur `llms.txt`, nicht `README.md` / `docs/`) und Override-Konvention für CWE-Footnotes.
- Residual Risk: LOW — SEO-tuned Prose-Edits (Tagline, Use-Cases, Keywords) bleiben manuell und sind nicht durch Tests geschützt. Akzeptabel, weil diese Bereiche Policy-relevant sind und Review verdienen.

## 2026-04-27 - ADR-091: Drift-Retrieval-RAG

- Risk ID: RISK-ADR-091-RETRIEVAL-CORPUS
- Component: `src/drift/retrieval/{corpus_builder,cache,index,search,fact_ids,models}.py`, `src/drift/mcp_router_retrieval.py`, neue MCP-Tools `drift_retrieve` / `drift_cite`, `.github/instructions/drift-rag-grounding.instructions.md`, `decisions/fact_id_migrations.jsonl`.
- Type: Trust-Boundary (neu): Corpus-Loader liest Repo-eigene Markdown-, JSON- und Python-Quellen und emittiert daraus SHA-verankerte Fact-Chunks, die von Coding-Agenten als Ground-Truth zitiert werden.
- Description: Lexical-BM25-Retrieval über POLICY, ROADMAP, ADRs, Audit-Artefakte, Signal-Docstrings und benchmark-evidence; exponiert als zwei MCP-Tools. Kein LLM, keine Embeddings, keine Net-I/O. MVP ist Instruction-Level Grounding (soft gate), keine harte CI-Erzwingung.
- Severity: MEDIUM — Soft-Gate erzeugt ein neues Vertrauensartefakt (`fact_id` + `sha256`) ohne direkten Scoring- oder Weight-Update-Pfad; Hauptrisiko ist Grounding-Illusion durch Staleness, Fact-ID-Drift oder manipulierten Corpus.
- Triggers:
  - Refactor an `POLICY.md`, ADR-Struktur, oder Slug-/Heading-Heuristik ohne Migration-Registry-Eintrag.
  - Änderungen an BM25-Tokenizer oder k1/b-Parametern ohne Re-Run des Gold-Set-Tests.
  - Zusätzliche Corpus-Quellen (z. B. `docs/`) ohne Trust-Boundary-Review.
  - Optionaler Phase-2-Hook (semantisches Retrieval gemäss ADR-031-Demarkation) ohne erneute STRIDE-Runde.
- Impact without mitigation:
  - Agent zitiert veraltete Policy als Fakt (Staleness), Maintainer erkennt den Drift spät.
  - Externe Skills/Tools pinnen Fact-IDs, die nach einem stillen Slug-Refactor nicht mehr auflösbar sind → Zitat-Verlust.
  - Manipulierter Checkout (z. B. im Field-Test auf Fremdrepo mit injected POLICY.md) liefert Corpus-Treffer mit SHA-Anker, die Agenten als glaubwürdig behandeln.
- Mitigations:
  - `CorpusManifest` mit `corpus_sha256` und `SourceEntry(mtime_ns, sha256)` macht Staleness auditierbar; 3-Layer-Cache prüft Memory → Disk → SHA.
  - `MigrationRegistry` (append-only JSONL mit transitiver, zyklus-sicherer Auflösung) entkoppelt stabile Fact-IDs von internen Slug-Algorithmen.
  - Gold-Set-Gate `tests/test_retrieval_search.py::test_gold_set_precision_at_5` (>= 80%) macht Precision-Regressionen zum Test-Fail.
  - `drift_retrieve`-Response enthält `corpus_sha256` + `chunk_count` als Reproduzierbarkeits-Anker.
  - `.github/instructions/drift-rag-grounding.instructions.md` setzt den Grounding-Contract als operatives Gate (Zitations-Pflicht + „keine erfundenen Fact-IDs").
  - ADR-091 demarkiert MVP-Umfang (lexical-only) explizit gegen Phase-2 (Semantic), Phase-3 (Target-Repo-Facts) und Phase-4 (harte CI-Enforcement).
- Monitoring:
  - 28 Tests (27 grün, 1 Skip ohne FastMCP) in `tests/test_retrieval_corpus.py`, `tests/test_retrieval_search.py`, `tests/test_mcp_retrieval_tools.py`.
  - Feature-Evidence: `benchmark_results/v_next_drift_retrieval_rag_feature_evidence.json`.
  - Determinismus verifiziert: `corpus_sha256 == 82bc1229b87ea51d5791d257c83f3240731945a80ec900c87aaf01c2639991a1` (1318 Chunks über 164 Sources).
- Residual Risk:
  - Instruction-Level Grounding ist freiwillig — ein Agent, der das Gate ignoriert, kann weiterhin halluzinieren. Harte CI/MCP-Validator-Enforcement ist Phase 4.
  - Signal-Class-Detection ist Heuristik (Substring `Signal` im Base-Namen); seltene False-Positives sind dokumentiert (FMEA RPN 12 accepted).
  - Der Corpus spiegelt ausschliesslich den lokalen Repo-Checkout — ein Agent, der auf einem manipulierten Branch arbeitet, bekommt SHA-konsistente, aber inhaltlich falsche Facts. Field-Test-Prompts verwenden ohnehin den Drift-Workspace-Checkout als Ground Truth.
  - Embedding-/semantic Retrieval ist bewusst exkludiert (ADR-091 + ADR-031-Demarkation); Queries mit starker Paraphrase können unter 80% Precision fallen, wenn der Gold-Set nicht mitwächst.
- Status: MITIGATED (MVP; keine Rückkopplung in Scoring; soft-gate grounding).

## 2026-04-22 - ADR-090: Agent-Telemetry Schema 2.2 (Paket 1B)

- Risk ID: RISK-ADR-090-AGENT-TELEMETRY-SCHEMA
- Component: `drift.output.schema.json` (Property `agent_telemetry`), `src/drift/models/_findings.py` (`AgentAction`, `AgentTelemetry`), `src/drift/models/_enums.py` (`AgentActionType`, `OUTPUT_SCHEMA_VERSION="2.2"`), `src/drift/output/json_output.py` (`_agent_telemetry_to_dict`), `scripts/generate_output_schema.py`, `tests/test_output_schema_drift.py`, `tests/test_agent_telemetry_schema.py`.
- Type: Output-/Audit-Schema (additiv, Backward-Compatible — keine Breaking-Change für Konsumenten ohne `agent_telemetry`-Nutzung).
- Description: Drift-JSON-Output bekommt optionalen Block `agent_telemetry` (Schema 2.2), der Agent-Aktionen einer Loop-Iteration protokolliert (ADR-089 Gate-Routing → ADR-090 Audit-Trail). Block ist rein additiv; `schema_version` wird von "2.1" auf "2.2" gehoben. Drift selbst schreibt den Block nicht — externe Agenten befüllen ihn nach `drift analyze`.
- Severity: LOW — Additiv, kein Score- oder Signal-Effekt, kein Weight-Update. Risiko beschränkt auf stille Schema-Drift zwischen Code und eingechecktem JSON-Schema oder auf falsch attribuierte Agent-Aktionen in retrospektiven Reports.
- Triggers:
  - Änderungen an `AgentActionType` / Severity-Gate / `_agent_telemetry_to_dict()` ohne Schema-Regenerate.
  - Externe Agent-Implementierungen, die `agent_telemetry` manuell konstruieren statt über Drift-Modelle.
- Impact without mitigation: Konsumenten validieren gegen falsches Schema; Tampering durch Agent mit Write-Access auf Output-JSON ist möglich (keine Signatur); Repudiation-Risk, wenn Agent `auto_fix` mit fingiertem `finding_id` protokolliert.
- Mitigations:
  - `scripts/generate_output_schema.py --check` als CI-Gate (via `tests/test_output_schema_drift.py::test_schema_file_is_up_to_date`).
  - `test_agent_action_type_enum_complete` macht Enum-Drift zwischen `AgentActionType` und Schema zum harten Test-Fail.
  - Echte `analysis_to_json`-Ausgabe wird gegen Draft-7-Schema validiert (positiv + negativ Test mit ungültigem Gate-Wert).
  - `additionalProperties: True` auf Top-Level bleibt erhalten → kein Breaking-Change für bestehende Konsumenten.
  - `AgentTelemetry.total_auto/review/block` sind computed properties, keine frei schreibbaren Felder → keine In-Schema-Inkonsistenz möglich.
- Monitoring:
  - 29 Tests: 20 in `tests/test_agent_telemetry_schema.py` + 9 in `tests/test_output_schema_drift.py` (Schema-Drift, Enum-Sync, Gate-Enum, Positiv/Negativ-Validation).
  - Feature-Evidence: `benchmark_results/v_next_paket_1b_agent_telemetry_schema_feature_evidence.json`.
- Residual Risk:
  - Agent-Tampering: Telemetrie-Block ist nicht signiert; malicious agent kann `auto_fix`-Aktionen für fremde Findings fingieren. Blast-Radius MVP-begrenzt, weil Drift-Scoring/-Findings unberührt bleiben und kein automatischer Downstream-Konsument die Telemetrie aktuell verwendet. Phase 3 (Human-Approval-Gate) MUSS vor Scoring-Kopplung signierte oder hash-kettete Einträge einführen.
  - Schema-Drift für externe Consumer: Nur Drift-Repo-eigener CI-Gate schützt; externe Projekte, die `drift.output.schema.json` gepinnt haben, müssen manuell migrieren. ADR-090 dokumentiert additive Minor-Bump-Konvention explizit.
- Status: MITIGATED (MVP; keine Rückkopplung in Scoring/Weight-Updates).

## 2026-04-24 - ADR-088: Outcome-Feedback-Ledger (K2 MVP)

- Risk ID: RISK-ADR-088-OUTCOME-LEDGER
- Component: `src/drift/outcome_ledger/**`, `src/drift/api/analyze_commit_pair.py`, `scripts/ops_outcome_trajectory_cycle.py`, Artefakte `.drift/outcome_ledger.jsonl` + `.drift/reports/<ts>/outcome_trajectory.{json,md}`.
- Type: Feedback-/Observability-Artefakt (kein Signal, kein Score, noch kein Weight-Update).
- Description: Ledger schreibt retrospektive Merge-Trajektorien (pre/post Drift-Score, per-signal delta, author_type) als JSONL. MVP-Scope: nur Schreiben + Reporting, keine Rueckkopplung in Signal-Heuristik oder Scoring.
- Severity: MEDIUM — Outcome-Signal kann zukuenftige Weight-Adjustments fehlleiten, wenn Merge-Korpus biased, Fingerprints instabil oder Worktree-Cleanup haengen bleibt. Im MVP nur beobachtend, daher Auswirkung begrenzt auf Report-Qualitaet.
- Triggers:
  - Ops-Runner `scripts/ops_outcome_trajectory_cycle.py --apply` appendet neue Eintraege.
  - Aenderung an Fingerprint-/Scoring-Code (ADR-082) kann pre/post nicht mehr vergleichbar machen.
- Impact without mitigation: Kalibrierungsdaten mit systematischem Bias (AI vs. Human, first-parent-Filter); stale Daten ueber 180d verzerren Baseline; Worktree-Leaks verbrauchen Platte und koennen HEAD-State stoeren.
- Mitigations:
  - Detached `git worktree` mit garantiertem Cleanup via `contextlib.suppress` + `shutil.rmtree` in `finally`.
  - Staleness-Buckets (<=90d fresh, 90-180d warning, >180d historical) im Report sichtbar.
  - Author-Split (Human/AI/Mixed) macht Bias im Report transparent.
  - `schema_version=1` und immutables frozen Pydantic-Modell verhindern silent Schema-Drift.
  - Kein automatisches Weight-Update im MVP (Scope-Guard via ADR-088).
- Monitoring:
  - `tests/test_outcome_ledger.py` (12 pass, 2 skipped: worktree-integration tests die echtes Git brauchen).
  - `git status` vor/nach ops-Runner muss identisch sein (Worktree-Isolations-Contract).
- Residual Risk:
  - Selection-Bias durch `--merges --first-parent`-Filter (squash/rebase merges uebersehen) → Report dokumentiert den Filter; Phase 2 erweitert.
  - Fingerprint-Mismatch bei Signal-Aenderungen zwischen pre und post → noise_floor 0.005 filtert sehr kleine Deltas; Phase 3 braucht Versions-Stamp pro Eintrag.
- Status: MITIGATED (MVP; keine Signal-/Score-Rueckkopplung).

## 2026-04-23 - ADR-087: Blast-Radius-Engine (K1)

- Risk ID: RISK-ADR-087-BLAST-RADIUS
- Component: `src/drift/blast_radius/**`, `scripts/check_blast_radius_gate.py`, `scripts/validate_adr_frontmatter.py`, `.githooks/pre-push` (Gate 9), MCP-Tool `blast_radius`.
- Type: Governance-/Pre-Push-Kontrollpfad (kein Signal, kein Score).
- Description: Die Engine berechnet deterministisch, welche ADRs (via `scope:`-Glob oder Text-Fallback), Guard-Skills (via `applies_to:` oder Namenskonvention), Arch-Module und Policy-Gates durch einen Diff invalidiert werden, und blockiert Push, wenn kritische Impacts ohne Maintainer-Ack vorliegen.
- Severity: MEDIUM — Gate greift nur vor Push. Degraded-Pfade (fehlender ArchGraph, fehlendes Git, fehlendes Frontmatter) werden als Warnings durchgelassen, hartes Block nur bei `criticality: critical` + fehlendem Ack.
- Triggers:
  - Änderungen in `src/drift/**`, `decisions/**`, `POLICY.md`, `.github/skills/**`.
  - Kritische ADR-Scope-Matches ohne `blast_reports/acks/<sha>.yaml`.
- Impact without mitigation: Strukturelle Erosion durch unbemerkte ADR-Invalidierung; Policy-/Audit-Artefakt-Drift nach Signal-Änderungen.
- Mitigations:
  - Text-Fallback für ADRs ohne Frontmatter (Migration-Toleranz, kein harter Break).
  - Guard-Skill-Matching via Namenskonvention, wenn `applies_to` fehlt.
  - Live-Modus `DRIFT_BLAST_LIVE=1` für Gate, wenn kein gespeicherter Report vorliegt.
  - Bypass `DRIFT_SKIP_BLAST_GATE=1` mit Warning-Log (analog zu §7-Gates).
  - Agent-Boundary: Engine und Gate erzeugen nur Reports; Ack-Dateien sind Maintainer-only.
- Monitoring:
  - `tests/test_blast_radius_core.py` (8 Tests: Analyzer-Kontrakte, Severity-Order, Persistence-Roundtrip, Immutability).
  - `tests/test_blast_radius_mcp.py` (4 Tests: Dispatch, Summary, Input-Validation, Default-Persistierung).
  - Pre-Push-Gate 9: blockiert Push hart bei kritischen Impacts ohne Ack.
- Residual Risk:
  - False Positives durch überbreite `scope:`-Globs → Maintainer kann Ack schreiben; Policy-Gate ist auditierbar.
  - Bypass-Missbrauch via `DRIFT_SKIP_BLAST_GATE=1` → Warning ist im Push-Log; ADR-087 dokumentiert akzeptierte Risiken.
  - Performance: Live-Scan >10 s bei >5k geänderten Dateien → Timeout setzt Report auf `degraded=True`, Gate warnt statt blockt.
- Status: MITIGATED (v-next Release-Kandidat; ADR-087 proposed).

## 2026-04-22 - ADR-082: Fingerprint v2 (Symbol-based, Line-independent)

- Risk ID: RISK-ADR-082-FINGERPRINT-V2
- Component: `src/drift/baseline.py` (finding_fingerprint, save_baseline, load_baseline, baseline_diff), `src/drift/analyzer.py` (_HeadMatchIndex, get_head_match_index_for_diff), `src/drift/api/diff.py` (_subtract_pre_existing_head), `src/drift/config/_schema.py` (thresholds.diff_fuzzy_head_subtraction).
- Type: Signal/output-contract risk (affects finding identity and baseline compatibility).
- Description: v1-Fingerprints hashten `(signal, file, start_line, end_line, title)`. Jeder Edit, der Zeilen verschiebt, und jede Titel-Metrik-Änderung erzeugten einen neuen Hash → `drift_diff` meldete unveränderte HEAD-Findings als "new". Field-Test 2026-04-21 bestätigte 13 "new findings" post-fix-loop, davon ~6 reine Shift-FPs. v2 hasht `(signal, file, symbol_identity, stable_title)` mit Kaskade `logical_location.fully_qualified_name → logical_location.name → symbol → ""` und Titel-Normalisierung (`\d+ → <N>`, strip trailing `(file:line)`).
- Severity: MEDIUM — `finding_id` in CLI/SARIF-Output ändert sich, externe Konsumenten müssen umstellen; `finding_id_v1` bleibt aber als Alias im Baseline-Schema für 2 Minor-Release-Zyklen erhalten.
- Triggers: Agent-Fix-Loop mit Helper-Extraktion (shiftet Zeilen); Metrik-tragende Titel wie `"return_pattern: 2 variants"`, wo der Count bei jedem Rescan driftet; File-Moves.
- Impact without mitigation: Agent verliert Vertrauen in `drift_diff`, deaktiviert Drift-Integration oder ignoriert `accept_change=false`; Baseline-Workflow wird praktisch unbenutzbar nach jedem Refactor.
- Mitigations:
  - Fingerprint v2 als Default (`finding_fingerprint` delegiert an v2).
  - Baseline-Schema v2 mit `fingerprint_v1`-Alias pro Entry → alte Dateien laden weiter, `baseline_diff` macht Dual-Lookup.
  - Fuzzy-HEAD-Subtraktion als Safety-Net für symbol-lose Findings (TPD, DRS): `(signal, file, stable_title)`-Match, default on, abschaltbar via `thresholds.diff_fuzzy_head_subtraction=false`.
  - Migrationswarnung: v1-Baselines emittieren beim Load ein Warning mit klarem Upgrade-Hinweis.
- Monitoring:
  - `tests/test_baseline.py::TestFingerprintV2Stability` (7 Stabilitäts-Asserts).
  - `tests/test_baseline.py::TestStableTitle` (Normalisierungs-Contract).
  - `tests/test_baseline.py::test_v1_schema_baseline_still_loads` (Migrations-Compat).
  - `tests/test_scan_diversity.py::test_uncommitted_ignores_shifted_findings_via_v2_fingerprint` + fuzzy-Pendant (End-to-End-Beweis des HEAD-Subtraktions-Pfads).
- Residual Risk: Signale ohne `symbol` UND ohne `logical_location` (z. B. repo-scoped TPD) greifen nur auf `(signal, file, stable_title)` zurück — Fuzzy-Pass fängt das meiste ab, aber ein genuines Umbenennen eines solchen Findings bleibt detektierbar. Akzeptabel: unter 5 % der Findings sind symbol-los und repo-weit.
- Status: MITIGATED (v2.27.0 Release-Kandidat).

## 2026-04-22 - ADR-083: Agent Pre-Edit Pattern-Scan via drift_steer

- Risk ID: RISK-ADR-083-PATTERN-DRIFT-POST-FIX
- Component: `.github/prompts/drift-fix-loop.prompt.md` (Schritt 2b, neu), Agent-Fix-Loop-Workflow.
- Type: Prozess-/Prompt-Risiko (kein Code-Contract).
- Description: Nach Helper-Extraktion führt der Agent Fremd-Pattern ein (z. B. `raise ValueError` in einem Modul, das bereits `DomainError` nutzt), obwohl PFS dies messen und anzeigen kann. Field-Test 2026-04-21 zeigte ~4 echte post-fix PFS-Findings (return_pattern, error_handling) — vermeidbar, wenn der Agent vor dem Edit das dominante Pattern liest.
- Severity: MEDIUM — echte Findings, nicht Tooling-FPs; entstehen konsistent in einer messbaren Rate.
- Triggers: Jede Refactor-Task, die ein neues Symbol einführt (Helper-Extraktion, Duplikat-Konsolidierung, Skeleton-Funktion).
- Mitigations:
  - `drift_steer(target=<file>)` VOR Symbol-Einführung wird im Fix-Loop-Prompt zur Pflicht.
  - Agent extrahiert `patterns_used_in_scope` und zitiert das gewählte Pattern im Task-Log.
  - Ausnahme nur für rein lokale Bugfixes ohne neues Symbol.
- Monitoring: Post-Fix-Loop-Audit (Anzahl neuer PFS-Findings in `work_artifacts/reduce_findings_*/`); Folge-Feldtest nach Rollout muss Rate auf ≤1 echte PFS-Finding pro 10 Fixes senken.
- Residual Risk: Agent ignoriert Prompt-Pflicht. Gegenmaßnahme in Folge-Iteration: `patterns_used_in_scope` direkt im `drift_fix_plan`-Task-Payload mitliefern (Stream 4b, deferred).
- Status: MITIGATED (Prompt-Ebene); Stream 4b als Follow-up offen.

## 2026-04-21 - Q3 (ADR-081 Nachschärfung): concurrent-writer advisory lock

- Risk ID: RISK-ADR-081-CONCURRENT-WRITER
- Component: `src/drift/session_writer_lock.py` (new), integration in `src/drift/mcp_router_session.py::run_session_start` and `::run_session_end`.
- Type: Persistence integrity risk (additive detection, no hard-block).
- Description: ADR-081 required single-writer per repo but offered no detection; two overlapping MCP sessions (restart window, second editor, parallel agents) could interleave writes into `queue.jsonl` and leave the log corrupt. Replay tolerates corrupt single lines but a corrupted `plan_created` can erase recoverable state.
- Severity: LOW — same-host, same-user, additive response fields only, lockfile is advisory (never denies a session start).
- Triggers (concrete): opening the same repo in two VS Code windows after a session timeout; a crashed previous MCP process leaving an orphaned session context; CI harnesses starting a second drift MCP against the same repo for smoke tests.
- Impact without mitigation: Silent queue corruption, lost terminal events, agent follows a state-diverged queue on next start.
- Mitigations:
  - `.drift-cache/queue.lock` records `{pid, session_id, started_at}` at session-start; released on session-end when `session_id` matches.
  - Session-start reads the existing holder: dead PID → ignored; lockfile older than 24 h → ignored; live PID within window → surfaced as `concurrent_sessions_detected=true` and `concurrent_writer={…}` in the response, with an added warning in `agent_instruction`.
  - "Last session wins" — overwrite is unconditional so a crashed session cannot block the next one.
  - Liveness uses only stdlib: POSIX `os.kill(pid, 0)`; Windows `OpenProcess`/`GetExitCodeProcess` via `ctypes`.
- Verification: `tests/test_session_writer_lock.py` (15 unit tests covering liveness probe, acquire/overwrite, release-owner-check, read-holder happy path, stale/malformed/non-mapping/bad-pid fallbacks); `tests/test_session.py::TestConcurrentWriterAdvisory` (5 integration tests: no-lockfile, live foreign writer surfaced, dead PID ignored, last-session-wins ownership, end releases lock).
- STRIDE: `audit_results/stride_threat_model.md` 2026-04-21 "ADR-081 Nachschärfung (Q3)" covers Spoofing (labels only), Tampering (advisory only), R/I/D/E mitigations.
- FMEA: `audit_results/fmea_matrix.md` 2026-04-21 Q3-Zeile (RPN = 12, mitigated).
- Residual risk: Hard-block variant deliberately deferred to a separate ADR — a stale lockfile never blocks a start, so in a pathological interleaving window two live sessions could both overwrite the lockfile in quick succession. The queue.jsonl still carries OS-level append locks to bound corruption within a single write call, so this residual window produces noisy warnings, not silent data loss.

## 2026-04-21 - Q2 (ADR-081 Nachschärfung): plan-staleness surfacing in run_session_start

- Risk ID: RISK-ADR-081-STALE-PLAN-REPLAY
- Component: `src/drift/session_queue_log.py::ReplayedState` / `reduce_events`, `src/drift/mcp_router_session.py::run_session_start`
- Type: Persistence / replay observability risk (additive response fields, no interface change)
- Description: ADR-081 replays the most recent `plan_created` event on session start but the response surfaced only a boolean `resumed_from_log`. An abandoned project could leave `.drift-cache/queue.jsonl` untouched for weeks; a new agent would silently inherit a zombie plan. Rotation only triggers beyond 10 MB so small logs live indefinitely. The agent had no signal to distinguish "plan is 5 min old, keep working" from "plan is 5 days old, re-plan first".
- Severity: LOW — additive; no existing caller sees a breaking change. `fresh_start=true` continues to suppress replay entirely.
- Triggers (concrete): MCP server restarts after 48 h idle, resumed queue is a pre-weekend snapshot; a second VS Code window reopens a repo that hadn't been touched in a week; agent re-starts an exhausted session on a branch that diverged since the original plan.
- Impact: Agent follows stale prioritisation; recent findings are ignored; queue-persistence nudges the agent back to obsolete tasks instead of serving its purpose.
- Mitigations:
  - `ReplayedState` now carries `plan_created_at` and `plan_session_id` (drawn from the most recent `plan_created` event).
  - `run_session_start` response adds `resumed_plan_created_at`, `resumed_plan_age_seconds`, `resumed_plan_stale`.
  - Default staleness threshold = 24 h; override via `DRIFT_QUEUE_STALE_SECONDS` (invalid / non-positive values fall back to default).
  - When `resumed_plan_stale=true`, `agent_instruction` reports the age in hours and instructs the agent to call `drift_fix_plan` again; `next_tool_call` is rewritten from `drift_scan` to `drift_fix_plan`.
  - `fresh_start=true` bypasses the entire replay, leaving all plan-age fields `None`.
- Verification: `tests/test_session_queue_log.py::test_reduce_events_exposes_latest_plan_metadata`, `::test_reduce_events_metadata_none_without_plan`; `tests/test_session.py::TestResumedPlanStaleness` (7 integration tests covering fresh, stale, env override, invalid / non-positive env, fresh_start, empty log).
- FMEA: `audit_results/fmea_matrix.md` 2026-04-21 "Q2 (ADR-081 Nachschärfung): plan-staleness surfacing in run_session_start" (RPN = 9, mitigated).
- Residual risk: Agent can still ignore the `agent_instruction` warning and call `drift_fix_apply` directly — SG-008/SG-009 (Q1) then require `drift_fix_plan` to populate `selected_tasks`, but the queue may still carry stale tasks if `drift_fix_plan` is never re-run. Detection remains on the agent layer, not enforced in orchestration.

## 2026-04-21 - Q1 (ADR-081 Nachschärfung): SG-008/SG-009 queue-driven mutation gates

- Risk ID: RISK-ADR-081-QUEUE-BYPASS
- Component: `src/drift/mcp_orchestration.py::_strict_guardrail_violations`
- Type: Orchestration / enforcement risk (additive strict-mode rule, no interface change)
- Description: ADR-081 queue persistence makes `selected_tasks` durable across session restarts but does not enforce that agents actually use the queue. Before Q1, an agent in strict mode could satisfy SG-005/SG-006 with only `drift_brief` and then call `drift_fix_apply` / `drift_patch_begin` directly, bypassing `drift_fix_plan` and the queue entirely. This reintroduces the "ad-hoc fixes instead of prioritised queue" failure mode that ADR-081 tried to solve at the persistence layer.
- Severity: LOW — strict-mode-only; `agent.strict_guardrails: false` opt-out fully restores prior behaviour; additive rule surfaces via existing `DRIFT-6002` block-response contract.
- Triggers (concrete): agent calls `drift_fix_apply(session_id=sid)` on a fresh session after only `drift_validate` + `drift_brief`; agent skips `drift_fix_plan` after a scan because the finding count is low; agent calls `drift_patch_begin` directly after re-briefing without re-planning.
- Impact: Without SG-008/009, priorities from `drift_fix_plan` are silently ignored; queue persistence (ADR-081) cannot recover lost intent because no plan ever existed.
- Mitigations:
  - SG-008 blocks `drift_fix_apply` when `session.selected_tasks` is empty or `None`.
  - SG-009 blocks `drift_patch_begin` with the same precondition.
  - Violation message names both recovery paths: `drift_fix_plan` for queue-driven mutation and `drift_nudge` / `drift_diff` for ad-hoc regression feedback (no mutation).
  - Resumed sessions (ADR-081 replay) restore `selected_tasks` from the log, so a session that resumed a non-empty plan satisfies SG-008/009 automatically.
- Verification: `tests/test_mcp_orchestration_coverage.py::TestQueueDrivenMutationRules` (8 tests covering empty queue block, non-empty pass, `None` selected_tasks, and explicit non-triggering for `drift_nudge`, `drift_diff`, `drift_scan`).
- FMEA: `audit_results/fmea_matrix.md` 2026-04-21 "Q1 (ADR-081 Nachschärfung): SG-008/SG-009 queue-driven mutation gates" (RPN = 24, mitigated).
- Residual risk: Agent can still call `drift_session_end` or `drift_scan` without queue; these do not mutate code and remain intentionally unblocked. Gates cannot detect a malicious fork where an attacker pre-seeds `selected_tasks` via queue-log tampering — existing STRIDE tampering mitigation (SG-005/006/007 stack) still applies.

## 2026-04-21 - ADR-081: Session-Queue-Persistenz via Append-Log

- Risk ID: RISK-ADR-081-SESSION-QUEUE-LOG
- Component: `src/drift/session_queue_log.py`, `src/drift/session.py` (write hooks on `claim_task`/`complete_task`/`release_task`), `src/drift/mcp_orchestration.py::_update_session_from_fix_plan`, `src/drift/mcp_router_session.py::run_session_start`
- Type: Persistence / replay consistency risk (additive behaviour, minimal blast radius)
- Description: Introduces an append-only event log at `<repo>/.drift-cache/queue.jsonl` that persists fix-plan queue mutations across MCP server restarts and session TTL expiry. `drift_session_start` replays the log by default and reconstructs `selected_tasks`, `completed_task_ids`, `failed_task_ids` from the most recent `plan_created` event plus all subsequent terminal events (`task_completed`/`task_failed`). Transient events (`task_claimed`/`task_released`) are deliberately ignored on replay.
- Severity: LOW — no breaking interface change; new optional `fresh_start: bool = False` parameter on `drift_session_start` allows opt-out; the log path is already gitignored via `.drift-cache/`. Write failures are swallowed (logged debug) so they never block session state mutations.
- Mitigations:
  - `fresh_start=true` skips replay entirely; use in tests or when the log is suspected stale.
  - Corrupt lines are logged and skipped per `tests/test_session_queue_log.py::test_replay_skips_corrupt_lines`.
  - Thread-safe writes via `threading.Lock` + best-effort OS lock (`msvcrt`/`fcntl`); single-writer-per-repo is the documented contract.
  - Rotation at 10 MB drops transient events; terminal audit events survive (see `_compact_events`).
  - STRIDE review (`audit_results/stride_threat_model.md` 2026-04-21) notes Tampering risk: attacker with local write access to `.drift-cache/queue.jsonl` can inject fake `plan_created` events; tasks are still subject to SG-005/SG-006/SG-007 strict guardrail enforcement before any fix-apply.
- FMEA: `audit_results/fmea_matrix.md` 2026-04-21 (5 failure modes, highest RPN = 27 "Replay rekonstruiert Task-State aus veraltetem Plan", accepted-with-mitigations).
- Tests: `tests/test_session_queue_log.py` (13 unit tests), `tests/test_session.py::TestQueueLogHooks`, `tests/test_session.py::TestRestartReplay` (end-to-end restart simulation).

## 2026-04-22 - v2.26.0: Strict MCP guardrails default, SG-007 / SG-005a / SG-006a, nudge revert enforcement

- Risk ID: RISK-MCP-2026-04-22-STRICT-DEFAULT
- Component: `src/drift/config/_schema.py`, `src/drift/mcp_orchestration.py`, `src/drift/api/nudge.py`, `src/drift/api/brief.py`, `scripts/nudge_gate.py`
- Type: Behavior / enforcement risk (BREAKING default flip)
- Description: `agent.strict_guardrails` default flipped `false -> true` (ADR-080). Three new rules added:
  SG-007 blocks `drift_fix_apply` / `drift_patch_begin` when the last brief raised `scope_gate.action_required=ask_user`;
  SG-005a / SG-006a block the same tools when the brief is stale (baseline score drift > 0.1,
  tool_calls_since_brief > 20, or age > 30 min). `drift_nudge.revert_recommended` hardened to
  `not safe_to_commit AND (direction=degrading OR parse_failures>0 OR git_blind_without_changed_files)`.
  Pre-commit hook `scripts/nudge_gate.py` blocks commits when the last nudge recommended REVERT
  and flagged files are unchanged (sha256-16 hash compare).
- Severity: MEDIUM — changes default agent behaviour; existing workflows relying on advisory-only
  guardrails will start seeing blocks. Opt-out is explicit and documented.
- Mitigations:
  - `strict_guardrails: false` in `drift.yaml` restores v2.25.0 behaviour.
  - `DRIFT_SKIP_NUDGE_GATE=1` bypasses the pre-commit gate per commit.
  - `nudge_gate.on_missing` config key (default `warn`) controls behaviour when no nudge state exists.
  - CHANGELOG marks the flip as BREAKING behavior with explicit rollback steps.
  - Tests: `tests/test_mcp_orchestration_coverage.py::TestScopeGateAndStalenessRules` (11 cases),
    `tests/test_nudge_gate.py` (8 cases), `tests/test_nudge.py` (revert matrix), full quick suite passes.
- Residual risk: Thresholds (delta 0.1, 20 calls, 30 min) not yet empirically validated across
  real agent sessions. Accepted pending field-test evidence; adjustable via constants in
  `src/drift/mcp_orchestration.py` (`_BRIEF_STALE_DELTA`, `_BRIEF_STALE_TOOL_CALLS`, `_BRIEF_STALE_SECONDS`).
- Status: Accepted-with-mitigations
- Evidenz: `benchmark_results/v2.26.0_feature_evidence.json`, `decisions/ADR-080-strict-mode-default.md`.

## 2026-04-21 - v2.25.0: Brief-staleness, session score fields, SG hardening, mypy/ruff fixes

- Risk ID: RISK-SESSION-2026-04-21-BRIEF-STALENESS
- Component: `src/drift/session.py`, `src/drift/mcp_orchestration.py`, `src/drift/mcp_router_session.py`, `src/drift/mcp_server.py`
- Type: Correctness / observability risk
- Description: Session now tracks `last_brief_at`, `last_brief_score`, `last_scan_score`, `tool_calls_since_brief`.
  `_brief_staleness_reason()` fires when score delta > 0.05, elapsed > 600 s, or calls_since_brief > 10.
  SG-005/SG-006: `drift_fix_apply` and `drift_patch_begin` reset brief counters. Mypy/ruff fixes in
  `file_discovery.py` (type annotations), `session_handover.py` (getattr fallback), `nudge.py` (line length).
  Changed signal-relevant files: `file_discovery.py`, `git_blame.py`, `git_history.py`, `json_output.py`,
  `markdown_report.py`, `architecture_violation.py`, `hardcoded_secret.py` — all changes are mypy/ruff
  correctness fixes with no behavioral signal changes.
- Severity: LOW — type annotation and staleness-tracking changes; no signal logic altered.
- Mitigations: All changes covered by existing test suite (5984 passed). Mypy reports 0 errors.
- Residual risk: Staleness threshold defaults (0.05 score delta, 600 s, 10 calls) may need tuning post-observation. Accepted pending empirical data.
- Status: Accepted-with-mitigations
- Evidenz: `benchmark_results/v2.25.0_feature_evidence.json`.

## 2026-04-21 - ADR-079: Session-Handover-Gate Bypass

- Risk ID: RISK-SESSION-2026-04-21-HANDOVER-BYPASS
- Component: `src/drift/session_handover.py`, `src/drift/mcp_router_session.py::run_session_end`
- Type: Process / governance risk
- Description: `drift_session_end(force=true)` erlaubt einen auditierbaren Notausgang am Handover-Gate.
  Missbrauch würde Security-Theater erzeugen (Session wird beendet, ohne dass verwertbare Handover-Artefakte
  vorliegen). Mitigationen: `bypass_reason` mit mindestens 40 Zeichen und ohne Denylist-Tokens, WARNING-Log
  in der `drift`-Logger-Kette, `record_trace` mit `advisory="session_handover.blocked"` bzw. bei Bypass
  mit `handover_bypass.forced=true` in der Session-Summary. Retry-Counter begrenzt Dauerblockaden auf
  `MAX_HANDOVER_RETRIES=5`, danach kann ausschliesslich mit validem `bypass_reason` beendet werden.
- Verbleibendes Risiko: Agent koennte plausiblen aber unehrlichen Bypass-Grund formulieren. Akzeptiert,
  weil jeder Bypass in Trace und Log vorliegt und manuell gereviewt werden kann.
- Status: Accepted-with-mitigations
- Evidenz: `tests/test_session_end_gate.py::test_force_with_valid_reason_unblocks`,
  `tests/test_session_end_gate.py::test_force_with_placeholder_reason_blocks`,
  `benchmark_results/v2.25.0_session_handover_gate_feature_evidence.json`.

## 2026-04-20 - interactive_review.py: pragma annotation only (non-functional)

- Risk ID: RISK-OUTPUT-2026-04-20-PRAGMA-ANNOTATION
- Component: `src/drift/output/interactive_review.py`
- Type: Non-functional hygiene annotation
- Description: Added `# pragma: allowlist secret` to the `"hardcoded_secret": "HSC"` string-abbreviation
  mapping in the `SIGNAL_ABBREVIATIONS` dict. This is a pure detect-secrets false-positive suppression;
  no code logic, output format, or signal behavior was changed.
- Severity: NONE — no behavioral change; annotation is invisible at runtime.
- Mitigations: N/A — purely declarative comment.
- Residual risk: None.



- Risk ID: RISK-OUTPUT-2026-04-20-HUMAN-MESSAGE-FIELD
- Component: `src/drift/output/json_output.py`, `src/drift/output/rich_output.py`
- Type: Additive output-format extension (new JSON field)
- Description: `human_message` field added to per-finding JSON output; `description` now prefers
  `human_message` (plain-language, audience-aware) over raw `description` when the lang module
  provides one. Rich output uses the same preference. Additive only — consumers ignoring unknown
  fields are unaffected; no existing fields removed or renamed.
- Severity: LOW — backward-compatible addition; no trust-boundary change; no new write paths.
- Mitigations: (1) Existing `description` field preserved unchanged; (2) `human_message` is
  `None` when lang module not active (transparent fallback); (3) JSON schema updated to allow
  the new optional field.
- Residual risk: Minimal — additive field, no precision/recall impact.

## 2026-04-20 - COD FP: Private Helper Extraction in Mono-Function Files

- Risk ID: RISK-COD-PRIVATE-HELPERS-2026-04-20
- Component: `src/drift/signals/cohesion_deficit.py` — `_function_unit`
- Type: Signal precision hardening (false-positive reduction)
- Description: `_function_unit` previously counted `_private_helper` functions as independent
  semantic units, inflating `isolation_ratio` after helper extraction refactorings in
  single-responsibility modules (e.g. `drift_map_api.py`, `github_correlator.py`). Private
  functions are implementation details of their file, not independent domain responsibilities.
  Fix: `_function_unit` returns `None` for any `fn.name.startswith("_")`.
- Recall risk: Modules whose *only* units are private functions (no public API) will produce zero
  units and never trigger COD. This is acceptable — such files have no public surface area to
  represent independent responsibilities.
- FN risk: A file with 5+ unrelated private functions (unusual) would no longer be flagged.
  Assessed as LOW: private functions are not discoverable API and are not independent
  responsibilities in the COD sense.
- Detection: `test_cod_private_helper_extraction_does_not_flag` (unit); `cod_private_helpers_tn`
  ground-truth fixture; existing TP fixtures (`cod_tp`, `test_cod_true_positive_fixture`) verify
  recall is preserved for all-public mixed-domain files.
- Residual risk: LOW — no scoring model or threshold change; only unit collection scope narrowed.

## 2026-04-19 - ADR-042: drift explain <fingerprint> — Finding-Level-Explain

- Risk ID: RISK-OUTPUT-2026-04-19-ADR042-EXPLAIN-FINGERPRINT
- Component: `src/drift/api/explain.py`, `src/drift/commands/explain.py`
- Type: Additive CLI/Output-Erweiterung
- Description:
  1. Neuer `--from-file` Pfad liest user-supplied JSON (read-only); `code_context` exponiert Quellcode-Zeilen.
  2. Re-Scan-Pfad ruft `analyze_repo()` auf — gleiche Laufzeit wie `drift analyze` (~3s); kein Amplification-Risiko.
  3. Fingerprint-Volatilität: `finding_id` ändert sich bei Datei-Rename oder Titel-Änderung. Dokumentiert in ADR-042.
- Severity: LOW — keine neuen Write-Pfade, kein neues Trust-Boundary.
- Mitigations: (1) `--from-file` validiert Datei-Existenz via Click `exists=True`; (2) `_extract_code_context` gibt leere Liste bei nicht lesbaren Dateien zurück (safe fallback); (3) `_explain_finding_from_analysis_file` gibt `None` bei ungültigem JSON zurück.
- Residual risk: Akzeptiert — read-only, keine neuen Permissions, gleiche Expositionsfläche wie bestehender `drift analyze` JSON-Output.

## 2026-04-19 - Issue #526: PFS FP-Reduktion error_handling-Propagation und Exception-Typ-Normalisierung

- Risk ID: RISK-PFS-PROPAGATION-EXTYPE-2026-04
- Component: `src/drift/signals/pattern_fragmentation.py`, `src/drift/ingestion/ast_parser.py`
- Type: Signal-Precision-Verbesserung (FP-Reduktion, geringe FN-Risiken abgesichert)
- Description:
  1. `ast.Continue` in except-Körpern wird jetzt explizit als `"loop_skip"` klassifiziert
     statt in `"other"` zu fallen.
  2. `_normalize_error_handling_fingerprint()` strippt Exception-Typen (ValueError, OSError,
     JSONDecodeError) vor Variant-Key-Bildung — nur die Handler-Actions-Struktur zählt für
     Fragmentation. Same-Action/Different-Exception-Type gilt nicht als Variante.
  3. `_is_propagation_only()` schließt Propagation-Patterns (`raise` als letztes Action,
     kein `log` davor) aus dem Varianten-Vergleich aus.
- Trigger: Trifft auf alle ERROR_HANDLING-Patterns in Python-Modulen, insbesondere auf
  Module mit gemischtem Propagation + Sentinel + Loop-Skip (z. B. calibration/).
- Impact: Reduziert False-Positive-Rate bei PFS/error_handling; verhindert nicht sichere
  Fix-Task-Empfehlungen (raise → return None). Log-and-rethrow (`["log", "raise"]`) bleibt
  als legitime Variante erhalten.
- Mitigation:
  - `_is_propagation_only` schließt Handler mit `"log"`-Action aus → log-and-rethrow bleibt
    als echter Variant (PFS_BOUNDARY_TP ground-truth guard aktiv).
  - Exception-Typ-Normalisierung nur für Fingerprints mit `handlers`-Key; synthetische
    Test-Fixtures ohne dieses Feld sind nicht betroffen.
  - 4 neue Regression-Tests in `tests/test_pattern_fragmentation.py`.
  - Golden snapshot aktualisiert (neues Metadata-Feld `propagation_excluded_count`).
- Status: Mitigated

## 2026-04-19 - ADR-077: EDS Private Micro-Helper Threshold Dampening

- Risk ID: RISK-EDS-PRIVATE-THRESHOLD-2026-04
- Component: `src/drift/signals/explainability_deficit.py`
- Type: Scoring-threshold change (FN-risk increase for bounded case)
- Description: `min_threshold` für private Funktionen mit LOC<40 und ohne Defekt-Korrelation
  wird von `0.45` auf `0.55` erhöht. Privater Micro-Helper direkt nach CXS-Extraktion feuert
  dadurch kein EDS — Oscillation im Fix-Loop wird verhindert.
- Trigger: Trifft auf jede private Python-Funktion mit Unterstrich-Prefix, LOC<40 und
  keinem `defect_correlated_commits > 0`-Commit-Eintrag.
- Impact: Gezielt reduziertes Noise für frisch extrahierte Helpers; echter Explainability-Debt
  in kleinen privaten Funktionen ohne Defekt-Korrelat wird potenziell später priorisiert.
- Mitigation:
  - Bedingung schließt `defect_correlated_commits > 0` explizit aus — riskante Files bleiben
    bei `min_threshold=0.30` (override).
  - Boundary ist strict `func.loc < 40` — LOC=40 fällt in altes Profil.
  - Neue TN-Fixture `eds_private_micro_helper_tn` dokumentiert Erwartung und verhindert Regression.
  - `tests/test_precision_recall.py` guards existing TP fixtures.
- Residual risk: Low. Scope ist eng definiert; defekt-korrelierte Files nicht betroffen.



- Risk ID: RISK-PATCH-WRITER-2026-07-FILE-WRITE
- Component: `src/drift/patch_writer/`, `src/drift/api/fix_apply.py`, `src/drift/commands/fix_plan.py`
- Type: New file-write capability (opt-in, requires `--apply` flag)
- Description: `drift fix-plan --apply` applies high-confidence auto-patches directly to the working tree. libcst transforms Python source and the result is written to disk via `write_text`. This introduces a file-write trust boundary not present in any prior API endpoint.
- Trigger: User invokes `drift fix-plan --apply` (or `--dry-run` for preview). Not triggered by any existing command path.
- Impact: Positive intent (reduces manual remediation effort), with controlled risk: files can be modified incorrectly or incompletely in edge cases.
- Mitigation:
  - Git-clean-state gate (`_is_git_clean`) enforced before any write. Dirty repos are rejected with a clear error.
  - `--dry-run` mode previews patches without writing. Default behavior of `fix_apply()` is `dry_run=True`.
  - Only tasks meeting HIGH/LOCAL/LOW automation-fit bar are processed.
  - libcst parse→transform→`module.code` round-trip preserves formatting; parse errors return `FAILED` status with no write.
  - Each file write is one atomic `write_text` call; rollback via `git checkout <file>`.
  - Python-only scope in v1; TypeScript/JS not patched.
- Residual risk: Low-Medium. Multi-file partial-patch state (some files written, later ones failing) is possible; mitigation is clear `status` per entry and documented `git checkout` rollback.



- Risk ID: RISK-OUTPUT-2026-04-18-PER-SIGNAL-TIMING
- Component: `src/drift/output/json_output.py`, `src/drift/output/rich_output.py`, `src/drift/pipeline.py`
- Type: Output field addition (additive, backward-compatible)
- Description: `SignalPhase` now records per-signal wall-clock durations in `phase_timings.per_signal` (dict keyed by signal type). JSON output exposes the nested map alongside the existing `signals_seconds` aggregate; Rich output renders slow-signal hints at high verbosity. No existing output fields were removed or renamed.
- Trigger: Any `drift scan` or `drift analyze` run.
- Impact: Neutral to positive. Consumers that parse `phase_timings` JSON may observe a new `per_signal` key; all prior keys remain. Rich consumers see additional timing hints only when verbosity is elevated.
- Mitigation:
  - Additive change only; no field removals or renames.
  - Timing values coerced to float via `_safe_float()` to prevent type errors on mixed inputs.
  - Tests added in `test_pipeline_components.py` and `test_json_output.py`.
- Residual risk: Low. New JSON key is optional and additive; no precision/recall impact.

## 2026-04-17 - LLM output max-findings cap

- Risk ID: RISK-OUTPUT-2026-04-17-LLM-MAX-FINDINGS-CAP
- Component: `src/drift/output/llm_output.py`
- Type: Output behavior change (additive parameter, backward-compatible)
- Description: `analysis_to_llm()` gains a `max_findings` parameter (default 50) that caps the number of findings serialized into the LLM plain-text report. Previously the function included all findings, which could produce outputs exceeding typical LLM context windows.
- Trigger: Repositories with more than 50 findings when `llm` output format is used.
- Impact: Positive. Prevents token-overflow silent truncation by LLM clients; default preserves prior behavior for repos with ≤50 findings.
- Mitigation:
  - Default value (50) matches the existing practical cap in most callers.
  - Finding selection prioritizes by severity so highest-impact findings are always included.
  - Callers that need all findings can pass `max_findings=0` (unlimited).
- Residual risk: Low. Callers that relied on implicit unlimited output may receive fewer findings; this is a safe degradation and the parameter is documented.

## 2026-04-17 - File discovery extension coverage + output field additions

- Risk ID: RISK-INGESTION-OUTPUT-2026-04-17-DISCOVERY-AND-OUTPUT-FIELDS
- Component: `src/drift/ingestion/file_discovery.py`, `src/drift/output/json_output.py`, `src/drift/output/rich_output.py`
- Type: Ingestion scope expansion + additive output fields (backward-compatible)
- Description: (1) `file_discovery.py`: default discovery and language detection now include `.pyi`, `.mjs`, `.cjs`, `.mts`, `.cts` so modern stub and module files are no longer silently excluded from analysis scope. (2) `json_output.py`: JSON output now includes `broad_security_suppressions` top-level field listing any bare drift:ignore suppressions over security signals. (3) `rich_output.py`: rich summary now surfaces a dedicated `Parser failures` line when degradation includes `parser_failure` events.
- Trigger: Analysis of repos with TypeScript module, stub, or ESM files; repos using bare drift:ignore over security signals; repos with parser coverage gaps.
- Impact: Positive. Wider file coverage reduces false negatives; explicit security suppression visibility reduces audit blind spots; parser failure visibility improves reliability signaling.
- Mitigation:
  - Regression tests: `tests/test_file_discovery.py`, `tests/test_json_output.py`, `tests/test_rich_output_boost.py`, `tests/test_scan_diversity.py`
  - New fields are additive; no existing consumer field is removed or renamed.
  - Discovery scope expansion only affects file types previously ignored — no behavioral regression on existing Python-only repos.
- Residual risk: Low. Additional file types are enumerated but not analyzed if tree-sitter is unavailable; `skipped_languages` surfaces the count. No new trust boundary introduced.



- Risk ID: RISK-OUTPUT-2026-04-16-GITHUB-FORMAT-TSB-FIX
- Component: `src/drift/output/github_format.py`, `src/drift/signals/type_safety_bypass.py`
- Type: Output correctness fix + Signal precision hardening (both backward-compatible)
- Description: (1) `github_format.py`: newlines in finding messages are now `%0A`-encoded so GitHub Actions `::error` annotations do not break on multi-line messages. (2) `type_safety_bypass.py`: TSB findings are now suppressed when `effective_bypass_count` is zero to eliminate spurious critical-severity findings on clean files. Both are fix-type changes with no scoring model change.
- Trigger: GitHub Actions annotation output with multi-line messages; TSB scan on files with no actual bypass patterns.
- Impact: Positive. Reduces annotation rendering defects in CI; reduces TSB false positives. No user-visible API change.
- Mitigation:
  - Regression tests: `tests/test_type_safety_bypass.py`, `tests/test_cli_runtime.py`
  - Output-format gate: annotation encoding is unit-tested and verified against live CI output
- Residual risk: Negligible. Both changes are strictly precision-improving with no new trust boundaries.

## 2026-04-14 - CLI onboarding and Windows-safe rendering hardening

- Risk ID: RISK-OUTPUT-2026-04-14-CLI-UX-HARDENING
- Component: `src/drift/commands/config_cmd.py`, `src/drift/commands/init_cmd.py`, `src/drift/commands/_shared.py`, `src/drift/output/rich_output.py`, `src/drift/copilot_context.py`
- Type: Output resilience and actionability hardening (backward-compatible)
- Description: The CLI now presents a newcomer-friendly configuration summary, preserves the MCP install hint literally, prioritizes operational agent context, and falls back to ASCII-safe rendering on Windows or non-UTF-8 terminals. This reduces misleading or unreadable terminal output without changing scoring behavior.
- Trigger: Running `drift config show`, `drift init`, `drift copilot-context`, or rich CLI output in legacy or encoding-constrained terminals.
- Impact: Positive. Improves finding credibility and next-step clarity while preserving machine-readable automation paths such as `--raw` and JSON output.
- Mitigation:
  - Human-facing summaries remain additive; script-safe raw output is still available.
  - Console rendering degrades safely to ASCII when the output stream cannot encode rich glyphs.
  - Regression tests cover config onboarding, init hint visibility, minimal output labels, and operational context prioritization.
- Verification:
  - `pytest tests/test_config_validate.py tests/test_init_cmd.py tests/test_output_minimal_and_signal_labels.py tests/test_mcp_copilot.py tests/test_finding_context.py -q --tb=short`
- Residual risk: Low. Very narrow terminals may still wrap lines, but the content remains legible and automation consumers can avoid rich formatting entirely.

## 2025-07-26 - ADR-070: drift verify — binary pass/fail coherence verification

- Risk ID: RISK-OUTPUT-2025-07-26-ADR070-VERIFY
- Component: `src/drift/api/verify.py`, `src/drift/commands/verify.py`, `src/drift/mcp_server.py` (drift_verify tool), `src/drift/tool_metadata.py`
- Type: New API function + CLI command + MCP tool (additive, no breaking change)
- Description: New `drift verify` command wraps `shadow_verify()` with a binary pass/fail envelope suitable for CI gating and agentic workflows. Applies severity-threshold gate (default: high) and score-degradation check to produce blocking reasons.
- Trigger: `drift verify` CLI, `verify()` API, or `drift_verify` MCP tool invocation.
- Impact: No impact on existing functionality. shadow_verify is called as-is. verify() adds a pass/fail decision layer on top.
- Mitigation:
  - 20 unit tests cover pass/fail logic, severity gate, direction detection, error propagation, CLI exit codes
  - MCP tool follows identical session-resolution pattern as drift_shadow_verify
  - CLI exit code 1 for fail (unless --exit-zero), matching `drift check` convention
- Verification:
  - `python -m pytest tests/test_verify.py -v --tb=short`
  - `python -m pytest tests/test_tool_metadata.py -v --tb=short`
- Residual risk: Low. false-pass if shadow_verify has finding-identity bugs (documented in ADR-064 FMEA). No new trust boundary introduced.

## 2025-07-24 - ADR-068/069: Package-Dekomposition + Protocol Dependency Inversion

- Risk ID: RISK-ARCH-2025-07-24-ADR068-PACKAGE-DECOMPOSITION
- Component: `src/drift/models/`, `src/drift/config/`, `src/drift/errors/`, `src/drift/protocols.py`, `src/drift/signals/_ts_support.py`
- Type: Architektur-Refactoring (internal restructuring, backward-compatible shims)
- Description: Drei monolithische God-Module (models.py, config.py, errors.py) wurden in Packages mit internen Sub-Modulen aufgeteilt. Kompatibilitaets-Shims (`__init__.py`) re-exportieren alle Public Symbols. Tree-Sitter-Funktionen aus _utils.py in _ts_support.py isoliert. EmbeddingServiceProtocol in protocols.py extrahiert.
- Trigger: Jeder Import von `drift.models`, `drift.config` oder `drift.errors` — unveraendertes Verhalten durch Shim-Layer.
- Impact: Neutral auf Score (0.501 → 0.525). Architektonisch klarer, aber protocols.py erzeugt neuen High-Coupling-Hub (blast radius 84). Kein Breaking Change fuer externe Consumer.
- Mitigation:
  - __init__.py-Shims re-exportieren ALLE bisherigen Symbole inkl. privater Helper
  - 4641 Tests nach jeder Phase verifiziert (0 failed)
  - check_model_consistency.py Pfad aktualisiert fuer neue config/_schema.py Lokation
  - protocols.py ist stabiles read-only Interface (5 Methoden), Aenderungen selten
- Verification:
  - `\.venv\Scripts\python.exe -m pytest tests/ --ignore=tests/test_smoke_real_repos.py -m "not slow" -q -n auto --dist=loadscope`
  - `\.venv\Scripts\python.exe -m pytest tests/test_model_consistency.py -v --tb=short`
- Residual risk: Niedrig. Hauptrisiko ist Shim-Vergessen bei zukuenftigen Symbol-Hinzufuegungen. Bestehendes test_model_consistency erkennt Schema-Divergenz sofort.

## 2025-07-22 - ADR-064: Shadow-Verify fuer cross-file-risky edit_kinds

- Risk ID: RISK-OUTPUT-2025-07-22-ADR064-SHADOW-VERIFY
- Component: `src/drift/fix_intent.py`, `src/drift/models.py`, `src/drift/output/agent_tasks.py`, `src/drift/api_helpers.py`, `src/drift/api/shadow_verify.py`, `src/drift/mcp_server.py`
- Type: Neue API-Funktion + MCP-Tool + Erweiterung Task-Vertragssystem (additiv, kein breaking change)
- Description: Tasks mit cross-file-risky edit_kind (remove_import, relocate_import, reduce_dependencies, extract_module, decouple_modules, delete_symbol, rename_symbol) erhalten jetzt `shadow_verify=true` und `completion_evidence.tool="drift_shadow_verify"` statt `drift_nudge`. Neues MCP-Tool `drift_shadow_verify` fuehrt vollen `analyze_repo()`-Lauf durch, filtert auf `scope_files` und vergleicht mit Baseline.
- Trigger: Jeder `drift_fix_plan`- oder `fix_plan`-API-Aufruf auf einem Repo mit Findings, die auf cross-file-risky Repair-Aktionen hinweisen.
- Impact: Positiv. Agenten erhalten deterministische Verifikationsbestätigung statt inkrementeller Schätzung fuer riskante cross-file-Edits. Falsch-positive `safe_to_commit`-Rueckmeldungen werden reduziert.
- Mitigation:
  - Alle neuen Felder in `AgentTask` haben Defaults (`shadow_verify=False`, `shadow_verify_scope=[]`); bestehende Tasks sind unveraendert.
  - `completion_evidence`-Aenderung ist conditional: nur Tasks mit `shadow_verify=true` erhalten neues Schema; alle anderen bleiben auf `nudge_safe`.
  - `shadow_verify()` faengt alle Exceptions und gibt `_error_response` zurueck (kein unkontrollierter Absturz).
  - Scope-Begrenzung durch Task-Graph-Nachbarn verhindert Full-Repo-Scans im Regelfall.
  - 30 dedizierte Tests in `tests/test_shadow_verify.py` sichern alle Kernkontrakte ab.
- Verification:
  - `\.venv\Scripts\python.exe -m pytest tests/test_shadow_verify.py -v --tb=short`
  - `\.venv\Scripts\python.exe -m pytest tests/ --ignore=tests/test_smoke_real_repos.py -m "not slow" -q`
- Residual risk: Niedrig. Finding-Identitaet basiert auf `signal_type:file_path:title` (kein UUID); Datei-Umbenennung kann False-Positives im Shadow-Verify erzeugen. Scope im ADR-064 dokumentiert; UUID-Matching als Follow-up adressiert.



- Risk ID: RISK-OUTPUT-2026-04-12-ADR063-FIX-INTENT
- Component: `src/drift/fix_intent.py`, `src/drift/api_helpers.py`, `src/drift/task_graph.py`
- Type: Output contract extension (additive, no breaking change)
- Description: New `fix_intent` field in fix_plan task responses provides machine-readable `edit_kind`, `target_span`, `target_symbol`, `canonical_source`, `expected_ast_delta`, `allowed_files`, and `forbidden_changes`. Derived from static signal-lookup tables and existing task fields; no scoring or signal logic affected.
- Trigger: Any `drift fix_plan` or `drift_fix_plan` MCP call.
- Impact: Positive. Reduces agent over-fixing by providing precise, closed-enum patch-boundary constraints without breaking existing consumers of `action`, `constraints`, or `allowed_files`.
- Mitigation:
  - `fix_intent` is additive; consumers that do not read it are unaffected.
  - `edit_kind` closed-enum with `"unspecified"` fallback prevents hallucinated values.
  - Call-site order (`_derive_task_contract` before `derive_fix_intent`) guarantees `allowed_files` consistency.
  - Full test coverage in `tests/test_fix_intent.py` including signal completeness guard.
- Verification:
  - `\.venv\Scripts\python.exe -m pytest tests/test_fix_intent.py tests/test_api_helpers_coverage.py tests/test_task_graph_contracts_types.py tests/test_orchestration_extensions.py -q --tb=short`
- Residual risk: Low. `edit_kind` inference for dynamic signals (EDS complexity, AVS subtype) degrades to `"add_docstring"` or `"remove_import"` when metadata is absent — still safe defaults.

## 2026-04-12 - Issue #317-332 follow-up: test-context and co-change precision hardening

- Risk ID: RISK-SIGNAL-2026-04-12-317-332-FOLLOWUP
- Component: `src/drift/ingestion/test_detection.py`, `src/drift/signals/co_change_coupling.py`, issue regressions `tests/test_issue_317_*.py` ... `tests/test_issue_332_*.py`, `tests/test_co_change_coupling.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: Follow-up hardening consolidates two recurring false-positive families found in external TypeScript repositories: (1) shared test/support utility path classification including `test-utils` conventions, and (2) CCC dependency mapping for stem-shadowed relative ESM imports (`./types.js` to TS sibling targets).
- Trigger: `drift analyze` on TypeScript repos with shared test utility folders and stem-shadowed file/directory layouts.
- Impact: High-positive. Reduces non-actionable production-context findings across DCA/TSB/EDS and avoids erroneous CCC coupling escalation.
- Mitigation:
  - Extend shared test-context path matcher with bounded `test-utils` directory handling.
  - Harden CCC relative-import target normalization for stem-shadowed TS layouts.
  - Preserve bounded scope via dedicated issue regressions and negative guards.
- Verification:
  - `\.venv\Scripts\python.exe -m pytest tests/test_test_detection.py tests/test_co_change_coupling.py -q --tb=short`
  - `\.venv\Scripts\python.exe -m pytest tests/test_issue_317_*.py tests/test_issue_332_*.py -q --tb=short`
- Residual risk: Low-Medium. Naming/path heuristics remain pattern-based; atypical repository layouts may still require targeted follow-up regressions.

## 2026-04-12 - Issue #301: EDS QA-lab mock-server test-context precision hardening

- Risk ID: RISK-SIGNAL-2026-04-12-301
- Component: `src/drift/ingestion/test_detection.py`, `tests/test_test_detection.py`, `tests/test_issue_301_eds_qa_lab_mock_server.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: Shared test detection now classifies `extensions/qa-lab/src/mock-openai-server.ts` as test context. This prevents Explainability Deficit (EDS) from treating this QA-lab mock infrastructure file as production complexity debt.
- Trigger: `drift analyze` on repositories that contain QA mock infrastructure at `extensions/qa-lab/src/mock-openai-server.ts`.
- Impact: High-positive. Reduces non-actionable EDS findings and improves trust in default production-vs-test triage.
- Mitigation:
  - Added bounded test-context rule for exact file path `extensions/qa-lab/src/mock-openai-server.ts` in shared test detection.
  - Added regression coverage in shared classifier tests.
  - Added EDS-focused regression to verify `finding_context=test` and LOW severity under `reduce_severity` handling.
- Verification:
  - `\.venv\Scripts\python.exe -m pytest tests/test_test_detection.py tests/test_issue_301_eds_qa_lab_mock_server.py -q --tb=short`
- Residual risk: Low-Medium. The rule is an exact-file matcher and may miss similarly purposed QA files with different names until explicit evidence justifies extension.

## 2026-04-12 - Issue #288: AVS generated-header precision hardening

- Risk ID: RISK-SIGNAL-2026-04-12-288
- Component: `src/drift/signals/architecture_violation.py`, `tests/test_architecture_violation.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: Architecture Violation (AVS) now suppresses files that carry explicit auto-generated header markers even when the filename does not include `.generated.*`. This addresses false positives for generated outputs with regular naming.
- Trigger: `drift analyze` on repositories where code generators produce files like `schema_base.ts` with explicit headers such as `Auto-generated ... Do not edit directly.`.
- Impact: High-positive. Reduces non-actionable AVS findings and improves architecture-finding credibility in codegen workflows that do not use generated filename suffixes.
- Mitigation:
  - Added AVS header-marker guard in parse-result filtering before import-graph construction.
  - Added targeted regression `test_generated_header_file_without_generated_suffix_is_ignored_for_avs_findings`.
  - Preserved existing filename/path-based generated suppression and normal AVS behavior for non-marked files.
- Verification:
  - `\.venv\Scripts\python.exe -m pytest tests/test_architecture_violation.py -q --tb=short`
  - `\.venv\Scripts\python.exe -m ruff check src/drift/signals/architecture_violation.py tests/test_architecture_violation.py`
- Residual risk: Low-Medium. Hand-written files that intentionally include generated markers can be suppressed; marker matching is intentionally narrow and only checks early header lines.

## 2026-04-12 - Issue #287: AVS generated-file precision hardening

- Risk ID: RISK-SIGNAL-2026-04-12-287
- Component: `src/drift/signals/architecture_violation.py`, `tests/test_architecture_violation.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: Architecture Violation (AVS) now excludes generated source files from analysis input by using shared generated-file classification before import-graph construction. This suppresses non-actionable AVS findings for code-generated modules (for example `src/config/bundled-channel-config-metadata.generated.ts`).
- Trigger: `drift analyze` on repositories that include generated TS/JS modules with synthetic import/coupling structure.
- Impact: High-positive. Reduces AVS false positives and improves credibility/actionability of architecture findings in codegen-heavy repositories.
- Mitigation:
  - Added generated-file exclusion in AVS analyze pre-filter (`is_generated_file`).
  - Added targeted regression `test_generated_typescript_file_is_ignored_for_avs_findings`.
  - Preserved AVS behavior for non-generated production/test classification paths.
- Verification:
  - `\.venv\Scripts\python.exe -m pytest tests/test_architecture_violation.py -q --tb=short`
  - `\.venv\Scripts\python.exe -m ruff check src/drift/signals/architecture_violation.py tests/test_architecture_violation.py`
- Residual risk: Low-Medium. Rare hand-written files with generated-style naming may be suppressed; classifier scope remains bounded and non-generated files retain full AVS analysis.

## 2026-04-12 - Issue #285: TVS generated-file volatility precision hardening

- Risk ID: RISK-SIGNAL-2026-04-12-285
- Component: `src/drift/signals/temporal_volatility.py`, `src/drift/ingestion/test_detection.py`, `tests/test_test_detection.py`, `tests/test_coverage_pipeline_and_helpers.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: Temporal Volatility (TVS) now suppresses generated source files from finding emission when paths match explicit generated conventions (`*.generated.ts/js/tsx/jsx`) or file headers contain explicit auto-generated markers (`Auto-generated`, `generated by ... do not edit`).
- Trigger: `drift analyze` on repositories using code generation pipelines that update generated metadata/config files frequently (for example `bundled-channel-config-metadata.generated.ts`).
- Impact: High-positive. Removes non-actionable TVS findings for expected codegen churn and improves signal credibility/actionability in codegen-heavy repos.
- Mitigation:
  - Extended shared generated-file detection patterns with `.generated.{ts,tsx,js,jsx}` suffix support.
  - Added TVS generated-path and generated-header guards before finding emission.
  - Added targeted regressions for generated suffix and header marker behavior.
- Verification:
  - `\.venv\Scripts\python.exe -m pytest tests/test_test_detection.py tests/test_coverage_pipeline_and_helpers.py -q --tb=short`
  - `\.venv\Scripts\python.exe -m ruff check src/drift/signals/temporal_volatility.py src/drift/ingestion/test_detection.py tests/test_test_detection.py tests/test_coverage_pipeline_and_helpers.py`
- Residual risk: Low-Medium. Rare hand-written files with misleading generated markers may be suppressed; mitigation scope is tightly bounded and production non-generated paths remain fully scored.

## 2026-04-12 - Issue #283: COD test-harness filename precision hardening

- Risk ID: RISK-SIGNAL-2026-04-12-283
- Component: `src/drift/signals/cohesion_deficit.py`, `tests/test_cohesion_deficit.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: Cohesion Deficit (COD) now classifies explicit shared test utility filename conventions (`*.test-harness.*`, `*.test-helpers.*`, `*.test-support.*` plus basename variants) as test context and skips finding emission for those files.
- Trigger: `drift analyze` on TS/Vitest repositories that store mixed mock/factory helpers in shared harness files like `dispatch-from-config.shared.test-harness.ts`.
- Impact: High-positive. Removes non-actionable COD findings for intentional test infrastructure aggregation modules and improves signal credibility/actionability.
- Mitigation:
  - Added bounded harness/helper/support filename matching in COD `_is_test_like(...)`.
  - Added targeted regression `test_issue_283_test_harness_file_is_ignored`.
  - Preserved existing COD behavior for non-matching production files.
- Verification:
  - `\.venv\Scripts\python.exe -m pytest tests/test_cohesion_deficit.py -q --tb=short`
  - `\.venv\Scripts\python.exe -m ruff check src/drift/signals/cohesion_deficit.py tests/test_cohesion_deficit.py`
- Residual risk: Low. Rare production files intentionally named with test-harness conventions could be suppressed; scope is tightly constrained to explicit naming patterns.

## 2026-04-12 - Issue #279: TSB Playwright runtime-guarded duck-typing double-cast precision hardening

- Risk ID: RISK-SIGNAL-2026-04-12-279
- Component: `src/drift/signals/type_safety_bypass.py`, `tests/test_type_safety_bypass.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: Type Safety Bypass (TSB) now treats Playwright SDK duck-typing double-casts (`as unknown as T`) as guarded interop when they are immediately followed by a runtime member-existence guard with fail-fast throw. Guarded casts are still visible in metadata (`double_cast_sdk_guarded`) but no longer inflate severity.
- Trigger: `drift analyze` on Playwright snapshot/automation modules using internal API bridge patterns like `const maybe = page as unknown as WithSnapshotForAI; if (!maybe._snapshotForAI) { throw ... }`.
- Impact: High-positive. Reduces non-actionable TSB findings and urgency inflation for known SDK interop patterns while preserving visibility and keeping unguarded double-casts actionable.
- Mitigation:
  - Added bounded helper `_is_runtime_guarded_playwright_double_cast(...)` in TSB.
  - Added new bypass kind `double_cast_sdk_guarded` with effective score weight `0.0`.
  - Added targeted regressions for guarded and unguarded Playwright double-cast behavior (Issue 279).
- Verification:
  - `\.venv\Scripts\python.exe -m pytest tests/test_type_safety_bypass.py -q --tb=short`
  - `\.venv\Scripts\python.exe -m ruff check src/drift/signals/type_safety_bypass.py tests/test_type_safety_bypass.py`
- Residual risk: Low-Medium. A narrow guard-shape heuristic may miss some valid guarded variants; this is acceptable to avoid broad over-suppression and preserve scoring for unguarded casts.

## 2026-04-12 - Issue #280: TSB test-support filename precision hardening

- Risk ID: RISK-SIGNAL-2026-04-12-280
- Component: `src/drift/ingestion/test_detection.py`, `tests/test_test_detection.py`, `tests/test_type_safety_bypass.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: Type Safety Bypass false positives occurred for TypeScript test-support helpers because `.test-support.ts` filenames were not classified as test context by shared test detection.
- Trigger: `drift analyze` on TS/Vitest repos that keep mock builders or harness wiring in files like `message-handler.test-support.ts`.
- Impact: High-positive. Eliminates non-actionable TSB findings for canonical test-double patterns while preserving existing production-file behavior.
- Mitigation:
  - Extended shared test-detection patterns with `.test-support.{ts,tsx,js,jsx}` and `test-support.{ts,tsx,js,jsx}`.
  - Added regression coverage in `tests/test_test_detection.py`.
  - Added TSB end-to-end regression `test_issue_280_test_support_double_casts_are_treated_as_test_context` to lock default skip + reduced-severity behavior.
- Verification:
  - `\.venv\Scripts\python.exe -m pytest tests/test_test_detection.py tests/test_type_safety_bypass.py -q --tb=short`
  - `\.venv\Scripts\python.exe -m ruff check src/drift/ingestion/test_detection.py tests/test_test_detection.py tests/test_type_safety_bypass.py`
- Residual risk: Low. Classification scope is bounded to explicit `test-support` filename markers and does not alter non-test naming behavior.

## 2026-04-12 - CXS/DCA follow-up hardening: schema-context marker coverage and package-root inspection dedupe

- Risk ID: RISK-SIGNAL-2026-04-12-CXS-DCA-FOLLOWUP
- Component: `src/drift/signals/cognitive_complexity.py`, `src/drift/signals/dead_code_accumulation.py`, `tests/test_cognitive_complexity.py`
- Type: Signal precision/performance hardening
- Description: Follow-up signal hardening adds explicit `config-schema` filename marker coverage for CXS context dampening and deduplicates package-root inspection in DCA published-package discovery to avoid repeated `package.json` parses for the same root.
- Trigger: `drift analyze` on extension/plugin repositories with `config-schema` files and monorepos with many JS/TS files under shared `packages/<name>` roots.
- Impact: Positive. Improves precision consistency (CXS) and reduces redundant processing/metadata churn (DCA).
- Mitigation:
  - Extend CXS inherent-context filename markers with `config-schema`.
  - Track inspected package roots in DCA published-package discovery and skip repeat inspections.
  - Add regression coverage for `extensions/feishu/src/config-schema.ts` context recognition.
- Verification:
  - `\.venv\Scripts\python.exe -m pytest tests/test_cognitive_complexity.py -q --tb=short`
  - `\.venv\Scripts\python.exe -m ruff check src/drift/signals/cognitive_complexity.py src/drift/signals/dead_code_accumulation.py tests/test_cognitive_complexity.py`
- Residual risk: Low. CXS remains bounded to explicit filename markers, and DCA dedupe only skips repeated inspections of identical package roots.

## 2026-04-12 - Issue #277: TVS test-file volatility precision hardening

- Risk ID: RISK-SIGNAL-2026-04-12-277
- Component: `src/drift/signals/temporal_volatility.py`, `tests/test_coverage_pipeline_and_helpers.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: Temporal Volatility (TVS) now excludes clear test-code paths from finding emission. Explicit test conventions (`tests/**`, `__tests__`, `test_*`, `*_test.py`, `*.test.*`, `*.spec.*`) are treated as expected maintenance churn and no longer escalated as volatility hotspots.
- Trigger: `drift analyze` on active repositories where test files change frequently alongside feature and bug-fix work (for example extension workspaces with many `.test.ts` files).
- Impact: High-positive. Removes non-actionable HIGH TVS clusters on test files and improves signal credibility/actionability.
- Mitigation:
  - Added `_is_test_file_path()` classifier to TVS.
  - Skips TVS finding creation for test-classified file paths while keeping production-file volatility scoring intact.
  - Added targeted regression test `test_test_like_files_are_skipped_from_volatility_findings`.
- Verification:
  - `.\.venv\Scripts\python.exe -m pytest tests/test_coverage_pipeline_and_helpers.py -q --tb=short`
  - `.\.venv\Scripts\python.exe -m ruff check src/drift/signals/temporal_volatility.py tests/test_coverage_pipeline_and_helpers.py`
- Residual risk: Low-Medium. TVS no longer surfaces churn in test infrastructure files; this is accepted to preserve production-focused signal actionability and reduce high-volume false positives.

## 2026-04-12 - Issue #276: AVS passive-definition Zone-of-Pain precision hardening

- Risk ID: RISK-SIGNAL-2026-04-12-276
- Component: `src/drift/signals/architecture_violation.py`, `tests/test_architecture_violation.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: Architecture Violation (AVS) now suppresses `avs_zone_of_pain` findings for passive TypeScript/Python definition modules that contain no imports, functions, classes, or patterns and have no parser errors. This addresses false positives on pure constants and type-definition files.
- Trigger: `drift analyze` on extension/plugin repositories with dedicated constants or type-shape carrier files (for example `cdp-timeouts.ts`, `client-actions-types.ts`) that are widely depended upon but contain no executable logic.
- Impact: High-positive. Reduces high-severity AVS triage noise and improves trust/actionability for architecture findings.
- Mitigation:
  - Added `_is_passive_definition_module()` guard in AVS instability pass.
  - Restricted suppression to parser-healthy modules (`parse_errors` empty).
  - Added targeted regressions for constants and type-only TS modules (Issue 276).
- Verification:
  - `\.venv\Scripts\python.exe -m pytest tests/test_architecture_violation.py -q --tb=short`
  - `\.venv\Scripts\python.exe -m ruff check src/drift/signals/architecture_violation.py tests/test_architecture_violation.py`
- Residual risk: Low-Medium. Rare passive modules with hidden architectural risk may be down-ranked in Zone-of-Pain view; other AVS checks still surface coupling/pathology signals.

## 2026-04-12 - Issue #275: CXS config-schema context precision hardening

- Risk ID: RISK-SIGNAL-2026-04-12-275
- Component: `src/drift/signals/cognitive_complexity.py`, `tests/test_cognitive_complexity.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: Cognitive Complexity (CXS) now recognizes TypeScript/JavaScript `config-schema` filename convention as inherent schema context and caps those findings to informational severity (`INFO`, `score <= 0.19`) using the existing `context_dampened` path.
- Trigger: `drift analyze` on TypeScript extension/plugin repositories that define large declarative Zod configuration schemas in files like `extensions/*/src/config-schema.ts`.
- Impact: High-positive. Reduces high-urgency false positives for declarative schema definition modules and improves CXS triage credibility.
- Mitigation:
  - Extended `_is_inherent_ts_complexity_context()` with bounded `config-schema` filename marker.
  - Added targeted regression coverage for path recognition and INFO-cap behavior on `extensions/feishu/src/config-schema.ts`.
  - Preserved existing non-context CXS behavior and visibility (no suppression).
- Verification:
  - `\.venv\Scripts\python.exe -m pytest tests/test_cognitive_complexity.py -q --tb=short`
  - `\.venv\Scripts\python.exe -m ruff check src/drift/signals/cognitive_complexity.py tests/test_cognitive_complexity.py`
- Residual risk: Low-Medium. Imperative complexity inside some `config-schema` files can be down-ranked; findings remain visible and scope is constrained to explicit naming.

## 2026-04-12 - Issue #273: DCA false positives for published npm package exports

- Risk ID: RISK-SIGNAL-2026-04-12-273
- Component: `src/drift/signals/dead_code_accumulation.py`, `tests/test_dead_code_accumulation.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: Dead Code Accumulation (DCA) now recognizes published npm package context for monorepo package sources. For JS/TS files under `packages/<name>/src|lib`, DCA checks `packages/<name>/package.json`; if a package `name` exists and `private` is not `true`, findings are bounded to LOW severity to reflect likely downstream external consumption not visible to repo-local static import analysis.
- Trigger: `drift analyze` on monorepos that publish SDK packages (for example `packages/*`) where exports are consumed by external package users.
- Impact: High-positive. Reduces high-volume DCA false positives and improves signal credibility/actionability for package-based ecosystems.
- Mitigation:
  - Added package-root detection for `packages/<name>` paths and safe `package.json` parsing.
  - Added published-package dampening path with cap (`score <= 0.39`) and explicit metadata traceability (`published_package_heuristic_applied`, `published_package_name`).
  - Added regression tests for positive published-package behavior and negative `private: true` guard.
- Verification:
  - `\.venv\Scripts\python.exe -m pytest tests/test_dead_code_accumulation.py -q --tb=short`
  - `\.venv\Scripts\python.exe -m ruff check src/drift/signals/dead_code_accumulation.py tests/test_dead_code_accumulation.py`
- Residual risk: Low-Medium. Some genuinely dead exports in published packages may be down-ranked; findings remain visible and private/internal package roots are excluded from the dampening path.

## 2026-04-12 - Issue #274: TSB Playwright SDK non-null assertion precision hardening

- Risk ID: RISK-SIGNAL-2026-04-12-274
- Component: `src/drift/signals/type_safety_bypass.py`, `tests/test_type_safety_bypass.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: Type Safety Bypass (TSB) now treats Playwright SDK idiomatic non-null assertions more conservatively. In addition to existing SDK event-emitter forms (`page.on!`, `page.off!`, `page.once!`), locator-argument non-null assertions (`page.locator(resolved.selector!)`) are classified as SDK interop patterns and no longer contribute to severity score inflation.
- Trigger: `drift analyze` on Playwright-heavy TypeScript interaction modules with many SDK-idiomatic non-null assertions plus a small number of true bypasses.
- Impact: High-positive. Reduces HIGH-severity false positives and improves trust/actionability of TSB findings.
- Mitigation:
  - Extended SDK interop pattern detection to Playwright `locator(...!)` call context.
  - Kept SDK interop non-null assertions visible in metadata (`non_null_assertion_sdk`) while setting their effective score contribution to zero.
  - Added targeted Issue-274 regression test to prevent future high-severity inflation for this pattern class.
- Verification:
  - `\.venv\Scripts\python.exe -m pytest tests/test_type_safety_bypass.py -q --tb=short`
  - `\.venv\Scripts\python.exe -m ruff check src/drift/signals/type_safety_bypass.py tests/test_type_safety_bypass.py`
- Residual risk: Low-Medium. Some genuine unsafe non-null assertions in SDK-importing files may be down-ranked; direct bypass indicators (`as any`, double casts, `@ts-ignore`) remain fully weighted.

  ## 2026-04-12 - Issue #278: TSB Playwright-core import context precision hardening

  - Risk ID: RISK-SIGNAL-2026-04-12-278
  - Component: `src/drift/signals/type_safety_bypass.py`, `tests/test_type_safety_bypass.py`
  - Type: Signal precision hardening (false-positive reduction)
  - Description: Type Safety Bypass (TSB) now recognizes `playwright-core` imports as SDK context for EventEmitter non-null assertion patterns. This ensures idiomatic `page.on!`/`page.off!` usage in Playwright-core modules is classified as `non_null_assertion_sdk` and does not inflate severity.
  - Trigger: `drift analyze` on Playwright-core TypeScript interaction modules using event listener binding via `page.on!`/`page.off!`.
  - Impact: High-positive. Removes a reproducible FP path and improves TSB trust in browser automation repositories.
  - Mitigation:
    - Extended `_SDK_IMPORT_RE` in TSB to include `playwright-core` import source.
    - Added targeted regression test `test_issue_278_playwright_core_event_emitter_patterns_are_sdk_dampened`.
    - Preserved full weighting for direct bypass classes (`as any`, `double_cast`, ts-directives).
  - Verification:
    - `\.venv\Scripts\python.exe -m pytest tests/test_type_safety_bypass.py -q --tb=short`
    - `\.venv\Scripts\python.exe -m ruff check src/drift/signals/type_safety_bypass.py tests/test_type_safety_bypass.py`
  - Residual risk: Low-Medium. Some true non-null misuse in SDK-adjacent modules may be down-ranked; findings remain visible and high-signal bypass types stay fully weighted.

## 2026-04-12 - Issue #271: DCA false positives for non-exported TS file-local declarations

- Risk ID: RISK-SIGNAL-2026-04-12-271
- Component: `src/drift/signals/dead_code_accumulation.py`, `src/drift/ingestion/ts_parser.py`, `src/drift/models.py`, `tests/test_dead_code_accumulation.py`, `tests/test_typescript_parser.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: Dead Code Accumulation (DCA) now excludes non-exported TypeScript/JavaScript class-like declarations from export-candidate counting. TypeScript parser extraction now annotates class/interface/type-alias declarations with `is_exported`, and DCA uses this metadata to avoid misclassifying file-local declarations as dead exports.
- Trigger: `drift analyze` on large TS modules with many file-local type aliases/interfaces plus a small set of real exports (for example translator-style gateway files).
- Impact: High-positive. Prevents inflated dead-export counts and high-severity false positives, improving DCA credibility and triage quality.
- Mitigation:
  - Added `ClassInfo.is_exported` model field.
  - Added TS export-state propagation for class/interface/type-alias declarations.
  - Restricted DCA TS/JS class-like export candidates to `is_exported=True`.
  - Added targeted regressions for parser export flags and DCA false-positive scenario.
- Verification:
  - `.\\.venv\\Scripts\\python.exe -m pytest tests/test_dead_code_accumulation.py tests/test_typescript_parser.py -q --tb=short`
- Residual risk: Low-Medium. Declarations exported via separate export-list statements may remain under-modeled and should be evaluated separately if recall evidence appears.

## 2026-04-12 - Issue #272: DCA false positives for TypeScript testkit contract APIs

- Risk ID: RISK-SIGNAL-2026-04-12-272
- Component: `src/drift/signals/dead_code_accumulation.py`, `tests/test_dead_code_accumulation.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: Dead Code Accumulation (DCA) now applies a bounded dampening for TypeScript/JavaScript testkit contract modules (`*.testkit.ts/js/...`) because these exports are frequently consumed by downstream test suites outside the local static import graph.
- Trigger: `drift analyze` on TS monorepos that expose contract-test harness APIs in files like `adapter-contract.testkit.ts`.
- Impact: High-positive. Prevents high-severity false positives for testkit public contract exports and improves DCA credibility/actionability.
- Mitigation:
  - Added `_is_testkit_contract_path()` heuristic for explicit `.testkit.` filename convention.
  - Applied bounded LOW dampening (`score *= 0.45`) and metadata marker (`testkit_contract_heuristic_applied`).
  - Added targeted regression to enforce LOW severity/score cap behavior for `.testkit.ts` files.
- Verification:
  - `.\.venv\Scripts\python.exe -m pytest tests/test_dead_code_accumulation.py -q --tb=short`
  - `.\.venv\Scripts\python.exe -m ruff check src/drift/signals/dead_code_accumulation.py tests/test_dead_code_accumulation.py`
- Residual risk: Low-Medium. Genuine dead exports in stale testkit modules may be down-ranked; findings remain visible and heuristic scope is constrained to explicit `.testkit.` naming.

## 2026-04-12 - Issue #270: MAZ false positive on localhost-only TS media server routes

- Risk ID: RISK-SIGNAL-2026-04-12-270
- Component: `src/drift/ingestion/ts_parser.py`, `src/drift/signals/missing_authorization.py`, `tests/test_typescript_parser.py`, `tests/test_missing_authorization.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: TypeScript ingestion now detects explicit loopback-only listener host bindings (`127.0.0.1`, `localhost`, `::1`) from `*.listen(...)` calls and annotates extracted API endpoints with `loopback_only`. MAZ suppresses findings for those loopback-only endpoint patterns.
- Trigger: `drift analyze` on TS/JS projects that expose helper/media routes only on localhost but without route-level auth checks.
- Impact: High-positive. Prevents CRITICAL false positives for local-only endpoints and improves MAZ security finding credibility.
- Mitigation:
  - Added file-level loopback listener detector for TS AST ingestion.
  - Added endpoint metadata propagation (`loopback_only`) into API endpoint pattern fingerprints.
  - Added MAZ suppression logic for loopback-only endpoint patterns.
  - Added parser and signal regressions for positive/negative cases.
- Verification:
  - `\.venv\Scripts\python.exe -m pytest tests/test_typescript_parser.py tests/test_missing_authorization.py -q --tb=short`
- Residual risk: Low-Medium. Loopback inference is currently file-level; unusual mixed-listener files may need future app-instance-level host association.

## 2026-04-12 - Issue #269: MAZ false positive on Express app-level auth middleware

- Risk ID: RISK-SIGNAL-2026-04-12-269
- Component: `src/drift/ingestion/ts_parser.py`, `tests/test_typescript_parser.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: TypeScript endpoint extraction now treats unscoped Express/Fastify-style app/router `use(...)` middleware as auth evidence when middleware references auth markers or contains inline auth+reject guards. This prevents MAZ from flagging protected routes that rely on global middleware chains.
- Trigger: `drift analyze` on Express codebases where routes use app-level JWT/Bearer auth middleware (`app.use(...)`) instead of per-route middleware arguments.
- Impact: High-positive. Reduces CRITICAL false positives for MAZ in common Express security patterns and improves security finding credibility.
- Mitigation:
  - Added file-level middleware auth detector for unscoped `*.use(...)` calls.
  - Reused existing inline-handler auth/body heuristics to identify guard+reject middleware bodies.
  - Intentionally ignored scoped `app.use('/prefix', ...)` middleware to avoid over-crediting auth for unrelated routes.
  - Added targeted parser regression for Bearer-header guard middleware.
- Verification:
  - `.\.venv\Scripts\python.exe -m pytest tests/test_typescript_parser.py tests/test_missing_authorization.py -q --tb=short`
- Residual risk: Low-Medium. Prefix-scoped middleware is still treated conservatively and may require future route-prefix modeling; this change only credits unscoped global middleware.

## 2026-04-12 - Issue #268: TPD early-stage extension severity cap

- Risk ID: RISK-SIGNAL-2026-04-12-268
- Component: `src/drift/signals/test_polarity_deficit.py`, `tests/test_consistency_proxies.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: Test Polarity Deficit (TPD) now applies a bounded lifecycle-aware dampening for runtime plugin workspaces (`extensions/<name>`, `plugins/<name>`): findings in newly introduced workspaces with very small module test-file coverage (`<= 3` files) are capped to LOW severity (`score <= 0.39`) and annotated with traceability metadata (`early_stage_extension`, `runtime_plugin_workspace`, `test_file_count`).
- Trigger: `drift analyze` on extension-heavy monorepos where prototype-stage plugins currently contain mostly happy-path tests.
- Impact: High-positive. Reduces non-actionable high-severity TPD clusters while preserving finding visibility.
- Mitigation:
  - Added runtime workspace key extraction for nested/absolute paths.
  - Added new-workspace detection from file history recency.
  - Added bounded severity cap only when both conditions hold: new workspace and module test-file count <= 3.
  - Added targeted regressions for capped and non-capped behavior.
- Verification:
  - `.\\.venv\\Scripts\\python.exe -m pytest tests/test_consistency_proxies.py -q -k "early_stage_extension or established_extension" --tb=short`
- Residual risk: Low-Medium. Some true early-stage deficits may be down-ranked; findings remain emitted with explicit metadata for reviewer override.

## 2026-04-12 - Issue #267: SMS extension workspace novelty severity inflation

- Risk ID: RISK-SIGNAL-2026-04-12-267
- Component: `src/drift/signals/system_misalignment.py`, `tests/test_coverage_signals.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: System Misalignment (SMS) now applies a bounded cap for extension/plugin-local novel dependencies when all newly introduced packages are only observed inside one runtime workspace (`extensions/<name>` or `plugins/<name>`). Findings remain visible but are downgraded to `INFO` (`score <= 0.19`) and marked with `workspace_scoped_novel_capped` metadata.
- Trigger: `drift analyze` on large extension monorepos where established extension packages introduce domain-specific dependencies that are intentionally unique per workspace.
- Impact: High-positive. Reduces medium-severity false-positive clusters and improves SMS credibility/actionability for plugin-style architectures.
- Mitigation:
  - Added workspace package-scope index across runtime plugin paths.
  - Added bounded cap only when all novel packages are isolated to one workspace.
  - Preserved normal severity when at least one novel package is shared across workspaces.
  - Added targeted regressions for capped and non-capped paths.
- Verification:
  - `.\\.venv\\Scripts\\python.exe -m pytest tests/test_coverage_signals.py -q -k "sms_" --tb=short`
- Residual risk: Low-Medium. Some genuine in-workspace dependency drift may be down-ranked; findings remain emitted with metadata for manual escalation.

## 2026-04-12 - Issue #266: PFS multi-extension boundary precision hardening

- Risk ID: RISK-SIGNAL-2026-04-12-266
- Component: `src/drift/signals/pattern_fragmentation.py`, `tests/test_pattern_fragmentation.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: Pattern Fragmentation Signal (PFS) now treats API-endpoint and error-handling heterogeneity in multi-plugin extension layouts as expected inter-plugin boundary variation and caps urgency to INFO with explicit metadata marker `plugin_boundary_variation_expected`.
- Trigger: `drift analyze` on large monorepos with many `extensions/*` or `plugins/*` packages where each plugin intentionally owns distinct endpoint and provider-specific error behavior.
- Impact: High-positive. Reduces non-actionable PFS urgency inflation and improves triage credibility in extension/plugin ecosystems.
- Mitigation:
  - Added category-bounded inter-plugin variation heuristic for PFS (`api_endpoint`, `error_handling`).
  - Applied INFO severity cap only when plugin-layout evidence is strong (`plugin_count >= 3`).
  - Added targeted Issue-266 regressions for API and error-handling contexts plus non-plugin guard.
- Verification:
  - `python -m pytest tests/test_pattern_fragmentation.py -q --tb=short`
- Residual risk: Low-Medium. Some genuine intra-extension fragmentation can be down-ranked in large plugin layouts; findings remain visible with metadata for reviewer override.

## 2026-04-12 - Issue #264: MDS absolute-path workspace isolation precision fix

- Risk ID: RISK-SIGNAL-2026-04-12-264
- Component: `src/drift/signals/mutant_duplicates.py`, `tests/test_mutant_duplicates_edge_cases.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: Mutant Duplicate Signal (MDS) now resolves extension/plugin workspace scope from path segments across full normalized paths, so cross-workspace dampening also applies when parse results carry absolute file paths.
- Trigger: `drift analyze` on large monorepos where findings use absolute file paths (for example cloned temp directories or Windows absolute paths), especially under `extensions/*` and `plugins/*`.
- Impact: High-positive. Reduces high-severity false positives for intentional vendored utility duplicates across isolated extension workspaces.
- Mitigation:
  - Hardened `_workspace_plugin_scope()` to detect `extensions/<name>` and `plugins/<name>` in any path segment position.
  - Kept existing pair/group INFO cap behavior and added explicit metadata marker `cross_extension_vendored`.
  - Added Issue-264 regressions for absolute-path scope detection and end-to-end exact-duplicate severity capping.
- Verification:
  - `python -m pytest tests/test_mutant_duplicates_edge_cases.py -q --tb=short`
- Residual risk: Low-Medium. Path-segment scanning may still classify edge-case folder naming collisions; matching remains bounded to exact marker segments and findings stay visible (no suppression).

## 2026-04-12 - Issue #263: AVS intra-extension unstable-dependency suppression

- Risk ID: RISK-SIGNAL-2026-04-12-263
- Component: `src/drift/signals/architecture_violation.py`, `tests/test_architecture_violation.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: Architecture Violation (AVS) now suppresses `avs_unstable_dep` findings when source and target are both inside the same extension workspace (`extensions/<name>/...`). This avoids unstable-dependency escalation for expected intra-extension wiring in monorepos.
- Trigger: `drift analyze` on extension-heavy TypeScript monorepos where composition-root/runtime/config files import local extension modules.
- Impact: High-positive. Reduces large clusters of non-actionable AVS findings and improves signal credibility/actionability.
- Mitigation:
  - Added `_extension_workspace_root()` helper in AVS.
  - Added same-workspace edge suppression in `_check_unstable_dependencies()` for `extensions/<name>` scope.
  - Added regressions for suppression and cross-extension guard behavior.
- Verification:
  - `python -m pytest tests/test_architecture_violation.py -q --tb=short`
- Residual risk: Low-Medium. Genuine unstable dependencies within one extension workspace may be down-ranked; cross-extension detection remains intact.

## 2026-04-12 - Issue #261: TVS mature extension workspace burst precision hardening

- Risk ID: RISK-SIGNAL-2026-04-12-261
- Component: `src/drift/signals/temporal_volatility.py`, `tests/test_coverage_pipeline_and_helpers.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: Temporal Volatility (TVS) now classifies coordinated bursts in established runtime plugin workspaces more robustly by combining active-file density with recent-modification density, instead of relying on a strict active-ratio trigger only.
- Trigger: `drift analyze` on large extension/plugin monorepos where workspaces contain mixed-age files but concentrated recent iteration windows.
- Impact: High-positive. Reduces persistent TVS high-severity false positives in active extension workspaces and improves fix-first prioritization credibility.
- Mitigation:
  - Extended `_workspace_burst_profiles()` with `recent_modified_count`/`recent_modified_ratio`.
  - Added bounded mature-workspace burst criteria (`size`, `active_count`, `active_ratio`, `recent_modified_ratio`, `established_count`).
  - Preserved existing score cap (`<= 0.45`) and metadata traceability (`workspace_burst_dampened`).
  - Added regression test for mixed-age mature workspace behavior.
- Verification:
  - `python -m pytest tests/test_coverage_pipeline_and_helpers.py -k "temporal_volatility or workspace" --tb=short -q`
  - `python -m ruff check src/drift/signals/temporal_volatility.py tests/test_coverage_pipeline_and_helpers.py`
- Residual risk: Low-Medium. Some genuine plugin-workspace instability may be down-ranked during broad coordinated activity windows; guardrails remain bounded and findings are still emitted.

## 2026-04-12 - Issue #260: DCA plugin/extension workspace false-positive reduction

- Risk ID: RISK-SIGNAL-2026-04-12-260
- Component: `src/drift/signals/dead_code_accumulation.py`, `tests/test_dead_code_accumulation.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: Dead Code Accumulation (DCA) now applies bounded dampening for JS/TS exports in plugin/extension workspaces (`extensions/*`, `plugins/*`, including nested paths such as `.pi/extensions/*`) where runtime host/plugin loaders frequently consume exports outside static import graphs.
- Trigger: `drift analyze` on monorepos with extension/plugin packages loaded via runtime registration or dynamic import across workspace boundaries.
- Impact: High-positive. Reduces medium/high false-positive clusters in plugin ecosystems and improves DCA actionability.
- Mitigation:
  - Added workspace-path heuristic in DCA for runtime plugin/extension export surfaces.
  - Applied bounded LOW cap (`score <= 0.39`) with explicit metadata (`runtime_plugin_workspace_heuristic_applied`).
  - Marked affected findings as `library_context_candidate` for downstream context-aware triage.
  - Added regressions for `extensions/*`, nested `.pi/extensions/*`, and a non-plugin guard case.
- Verification:
  - `python -m pytest tests/test_dead_code_accumulation.py -q --tb=short`
  - `python -m ruff check src/drift/signals/dead_code_accumulation.py tests/test_dead_code_accumulation.py`
- Residual risk: Low-Medium. Some genuine dead exports in plugin workspaces may be down-ranked; findings remain visible and non-plugin paths are unaffected.

## 2026-04-12 - Issue #259: CXS context cap for TS/JS config-default files

- Risk ID: RISK-SIGNAL-2026-04-12-259
- Component: `src/drift/signals/cognitive_complexity.py`, `tests/test_cognitive_complexity.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: Cognitive Complexity (CXS) now recognizes TS/JS config-default resolver file conventions (`config-defaults.*`, `config.defaults.*`, `default-config.*`) as inherent complexity context and caps those findings to informational severity (`INFO`, `score <= 0.19`).
- Trigger: `drift analyze` on TypeScript/JavaScript plugin/config repositories with fallback-heavy configuration default resolvers.
- Impact: High-positive. Reduces urgency inflation for structurally branch-heavy config-default code and improves CXS credibility/actionability.
- Mitigation:
  - Extended `_is_inherent_ts_complexity_context()` with bounded config-default filename markers.
  - Reused existing context dampening severity cap path with explicit metadata (`context_dampened`).
  - Added targeted regressions for config-default positive matching, negative regular-file guard, and context-cap severity behavior.
- Verification:
  - `python -m pytest tests/test_cognitive_complexity.py -q --tb=short`
  - `python -m ruff check src/drift/signals/cognitive_complexity.py tests/test_cognitive_complexity.py`
- Residual risk: Low-Medium. Some real complexity debt in config-default files may be down-ranked; scope is constrained to explicit naming patterns and findings remain visible.

## 2026-04-12 - Issue #258: EDS TS/TSX internal UI high-severity cap

- Risk ID: RISK-SIGNAL-2026-04-12-258
- Component: `src/drift/signals/explainability_deficit.py`, `tests/test_coverage_boost_15_signals_misc.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: Explainability Deficit (EDS) caps TypeScript/TSX `HIGH` severity to `MEDIUM` for weak-evidence internal implementation contexts (`is_exported=False`) and UI/DOM wiring contexts, to prevent score-driven severity inflation in large internal UI functions.
- Trigger: `drift analyze` on large TS monorepos with event-binding/render-heavy modules (for example `web/src/app.ts`, `ui-render.ts`) that intentionally omit JSDoc on internal functions.
- Impact: High-positive. Reduces concentrated high-severity false positives and improves signal credibility/actionability without suppressing findings.
- Mitigation:
  - Added TS/TSX context cap in EDS severity mapping (`HIGH -> MEDIUM`, `score <= 0.69`) for internal/UI implementation contexts.
  - Added metadata traceability (`ts_ui_high_cap_applied`) on each affected finding.
  - Added regression tests for both directions: capped internal UI case and unchanged exported API escalation.
- Verification:
  - `python -m pytest tests/test_coverage_boost_15_signals_misc.py -k "issue_258 or internal_ui_function_caps_high_to_medium or exported_function_can_still_be_high" -q --tb=short`
  - `python -m ruff check src/drift/signals/explainability_deficit.py tests/test_coverage_boost_15_signals_misc.py`
- Residual risk: Low-Medium. Some real high-risk internal TS functions may be down-ranked; exported APIs still escalate to `HIGH`, and findings remain visible.

## 2026-04-12 - Issue #256: EDS TS/JS test evidence mapping and unknown-status neutral scoring

- Risk ID: RISK-SIGNAL-2026-04-12-256
- Component: `src/drift/signals/explainability_deficit.py`, `tests/test_coverage_boost_15_signals_misc.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: Explainability Deficit (EDS) verwendet fuer TS/JS jetzt zusaetzliche dateibasierte Test-Evidenz (`*.test.*`, `*.spec.*`, `__tests__/*`, `src/... -> tests/...`) und behandelt nicht verifizierbaren Teststatus (`has_test=None`) neutral statt negativ.
- Trigger: `drift analyze` auf TypeScript/JavaScript-Repositories mit ko-lokierten Tests und/oder default-Discovery-Excludes fuer Testpfade.
- Impact: High-positive. Reduziert systematische EDS-Score-Inflation und verbessert Glaubwuerdigkeit/Actionability in TS/JS-Projekten.
- Mitigation:
  - Neue TS/JS-Testdatei-Zuordnung in EDS, wenn keine Funktionsziel-Evidenz vorhanden ist.
  - Tri-State `has_test` mit neutralem Scoring bei unbekanntem Status.
  - Erweiterte Finding-Metadata (`has_test_unknown`) und differenzierte Description-Hinweise.
  - Neue Regressionstests fuer colocated/test-dir Mapping und neutralen Unknown-Fall.
- Verification:
  - `python -m pytest tests/test_coverage_boost_15_signals_misc.py -q --maxfail=1`
  - `python -m ruff check src/drift/signals/explainability_deficit.py tests/test_coverage_boost_15_signals_misc.py`
- Residual risk: Low-Medium. Datei-Namens-Mapping kann in Randfaellen Tests als Evidenz annehmen, ohne funktionale Abdeckung zu garantieren; die Heuristik bleibt auf konventionelle Muster begrenzt.

## 2026-04-12 - Issue #255: CXS context cap for schema and migration files

- Risk ID: RISK-SIGNAL-2026-04-12-255
- Component: `src/drift/signals/cognitive_complexity.py`, `tests/test_cognitive_complexity.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: Cognitive Complexity (CXS) now detects TypeScript/JavaScript schema and migration file contexts and caps those findings to informational severity (`INFO`, `score <= 0.19`) because branching in these files is often structural and expected.
- Trigger: `drift analyze` on TS/JS repositories with schema validation modules (`*.schema.ts/js`) and migration-heavy files (`*migration*`, `*/migrations/*`).
- Impact: High-positive. Reduces CXS false-positive severity inflation in data-shape and migration infrastructure code, improving signal credibility and triage focus.
- Mitigation:
  - Added `_is_inherent_ts_complexity_context()` in CXS to detect bounded schema/migration file patterns.
  - Added context-aware severity cap in `_make_finding()` with trace metadata (`context_dampened`).
  - Added targeted regressions for positive and negative path context matching plus severity-cap behavior.
- Verification:
  - `python -m pytest tests/test_cognitive_complexity.py -q --tb=short`
  - `python -m ruff check src/drift/signals/cognitive_complexity.py tests/test_cognitive_complexity.py`
- Residual risk: Low-Medium. Genuine complexity debt in migration/schema files can be down-ranked; scope is tightly bounded and findings remain visible for manual follow-up.

## 2026-04-12 - Issue #254: FOE groups plugin SDK sub-path imports by dependency identity

- Risk ID: RISK-SIGNAL-2026-04-12-254
- Component: `src/drift/signals/fan_out_explosion.py`, `tests/test_fan_out_explosion.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: Fan Out Explosion (FOE) now counts JS/TS sub-path imports by dependency identity (`vendor/pkg` or `@scope/pkg`) instead of raw import specifiers, so plugin SDK exports no longer inflate fan-out counts.
- Trigger: `drift analyze` on plugin/provider repositories that consume one SDK package through many sub-path imports (for example `openclaw/plugin-sdk/*`).
- Impact: High-positive. Removes a concentrated false-positive class and improves FOE signal credibility/actionability for extension ecosystems.
- Mitigation:
  - Added `_dependency_key()` normalization in FOE for package-based counting.
  - Preserved relative import granularity to avoid masking local file-level coupling.
  - Added Issue-254 regressions for unscoped and scoped SDK sub-path patterns.
- Verification:
  - `python -m pytest tests/test_fan_out_explosion.py -q --tb=short`
  - `python -m ruff check src/drift/signals/fan_out_explosion.py tests/test_fan_out_explosion.py`
- Residual risk: Low-Medium. Some edge cases with intentionally broad sub-path usage may be down-ranked; thresholding and non-subpath dependency counts remain unchanged.

## 2026-04-12 - Issue #252: NBV TS ensure_ delegated-method false-positive reduction

- Risk ID: RISK-SIGNAL-2026-04-12-252
- Component: `src/drift/signals/naming_contract_violation.py`, `tests/test_naming_contract_violation.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: Naming Contract Violation (NBV) now reparses TypeScript dotted method snippets (`Class.method`) inside a synthetic class wrapper before TS contract checks. This preserves return/throw AST nodes for `ensure_*` delegation patterns and prevents false positives.
- Trigger: `drift analyze` on TypeScript class-based runtime/provider code where `ensure_*` methods delegate to helper objects and return delegated promises/results.
- Impact: Medium-positive. Reduces recurring NBV false positives for delegated ensure contracts and improves signal credibility.
- Mitigation:
  - Added method-context parse fallback in `_ts_check_rule()` for dotted method names.
  - Added Issue-252 regressions for delegated ensure method, Promise<boolean> bool-contract, and explicit throw-based validate contract.
  - Kept existing strict negative ensure guard for no-op ensure functions.
- Verification:
  - `python -m pytest tests/test_naming_contract_violation.py -q --tb=short`
  - `python -m pytest tests/test_nbv_helpers_coverage.py -q --tb=short`
- Residual risk: Low-Medium. Synthetic wrapping is a heuristic and may mask malformed method snippets in edge cases; scope is limited to dotted method names and guarded by negative regression tests.

## 2026-04-12 - Issue #265: NBV TS predicate and assertion-contract false-positive reduction

- Risk ID: RISK-SIGNAL-2026-04-12-265
- Component: `src/drift/signals/naming_contract_violation.py`, `tests/test_naming_contract_violation.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: Naming Contract Violation (NBV) now treats TypeScript `is*`/`has*` functions without explicit return annotation conservatively: violations are emitted only when return expressions provide clear non-boolean evidence. Additionally, `ensure*` functions with TS assertion signatures (`asserts ...`) are accepted as valid ensure contracts.
- Trigger: `drift analyze` on TypeScript extension/runtime repositories where predicate helpers delegate to boolean-producing calls without explicit annotations and ensure-style guards use assertion signatures.
- Impact: High-positive. Reduces dominant NBV false positives in TS-heavy codebases and improves signal credibility/actionability.
- Mitigation:
  - Refined `_ts_has_bool_return()` classification into `bool` / `non_bool` / `unknown`, with conservative handling for unknown inferred returns.
  - Added `_ts_is_assertion_return_contract()` and integrated it into `ensure_` TS contract checks.
  - Added Issue-265 regressions for inferred-bool call returns, assertion-signature ensure contracts, and explicit non-bool negative control.
- Verification:
  - `python -m pytest tests/test_naming_contract_violation.py -q --tb=short`
- Residual risk: Low-Medium. Conservative unknown-return handling may down-rank a subset of true violations; explicit non-bool return evidence remains strictly reportable.

## 2026-04-12 - Issue #253: TVS dampening for active extension/plugin development bursts

- Risk ID: RISK-SIGNAL-2026-04-12-253
- Component: `src/drift/signals/temporal_volatility.py`, `tests/test_coverage_pipeline_and_helpers.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: Temporal Volatility (TVS) now identifies runtime plugin workspaces (`extensions/*`, `plugins/*`) and dampens score impact for new or coordinated active-development bursts, preventing high-severity inflation for expected plugin feature iteration.
- Trigger: `drift analyze` on plugin/provider monorepos with concentrated recent churn inside one extension workspace during active delivery windows.
- Impact: High-positive. Reduces dominant TVS false positives and improves trust/actionability in active extension ecosystems.
- Mitigation:
  - Added workspace classification helper for plugin scopes in TVS.
  - Added workspace burst profiling (new workspace and coordinated active-ratio detection).
  - Added bounded score cap (`<= 0.45`) plus metadata traceability (`workspace_burst_dampened`).
  - Added targeted regressions for dampened plugin workspace and unchanged non-plugin outlier severity.
- Verification:
  - `python -m pytest tests/test_coverage_pipeline_and_helpers.py -q`
  - `python -m ruff check src/drift/signals/temporal_volatility.py tests/test_coverage_pipeline_and_helpers.py`
- Residual risk: Low-Medium. Genuine volatility inside an actively developed plugin workspace may be down-ranked; scope is intentionally bounded and findings remain visible.

## 2026-04-12 - Issue #251: TSB/BAT precision hardening for src test-helper naming and SDK event-emitter non-null assertions

- Risk ID: RISK-SIGNAL-2026-04-12-251
- Component: `src/drift/ingestion/test_detection.py`, `src/drift/signals/type_safety_bypass.py`, `tests/test_test_detection.py`, `tests/test_type_safety_bypass.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: Type Safety Bypass now classifies `src`-co-located test helper filenames (`test-helpers.*`, `test-*.ts/js/tsx/jsx`) as test context and applies reduced weighting to SDK-idiomatic EventEmitter non-null assertions (`on!/off!/once!`) for known Playwright/Discord import contexts.
- Trigger: `drift analyze` on TypeScript monorepos with co-located test helpers under `src/` and SDK interaction files that use EventEmitter non-null assertion patterns.
- Impact: High-positive. Reduces dominant TSB/BAT false positives and improves finding credibility/actionability in SDK-heavy extension repos.
- Mitigation:
  - Extended centralized test-path detection with filename-based TS/JS test helper patterns.
  - Added SDK-aware `non_null_assertion_sdk` classification and weighted scoring path in TSB.
  - Added targeted regressions for both path-classification and score dampening behavior.
- Verification:
  - `python -m pytest tests/test_test_detection.py tests/test_type_safety_bypass.py -q --tb=short`
  - `python -m ruff check src/drift/ingestion/test_detection.py src/drift/signals/type_safety_bypass.py tests/test_test_detection.py tests/test_type_safety_bypass.py`
- Residual risk: Low-Medium. Some real unsafe `!` usage in SDK-adjacent code may be down-ranked; dampening is constrained to known SDK imports and explicit EventEmitter method patterns.

## 2026-04-12 - Issue #249: COD dampening for plugin registration and typed utility modules

- Risk ID: RISK-SIGNAL-2026-04-12-249
- Component: `src/drift/signals/cohesion_deficit.py`, `tests/test_cohesion_deficit.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: Cohesion Deficit (COD) now applies targeted dampening for cohesive action-prefix families (`register*`, `format*`, `create*`), filename-domain alignment, and plugin workspace patterns under `extensions/*/src`.
- Trigger: `drift analyze` on plugin-oriented TypeScript monorepos with registration/helper/format modules that share domain intent but low raw token overlap.
- Impact: High-positive. Reduces COD false positives for plugin/provider ecosystems and improves finding actionability.
- Mitigation:
  - Added `shared_action_prefix_ratio` heuristic for dominant action-family modules.
  - Added `filename_token_cohesion_ratio` heuristic for filename-domain alignment.
  - Added bounded plugin workspace dampening (`extensions/*/src`) when one of the cohesion hints is strong.
  - Added Issue-249 regressions in `tests/test_cohesion_deficit.py` for register-family, create-family, and format-module patterns.
- Verification:
  - `python -m pytest tests/test_cohesion_deficit.py -q --tb=short`
  - `python -m ruff check src/drift/signals/cohesion_deficit.py tests/test_cohesion_deficit.py`
- Residual risk: Low-Medium. Some true deficits that match these patterns may be down-ranked; thresholds are conservative and bounded to explicit cohesion hints.

## 2026-04-12 - Issue #250: MAZ suppresses outbound API-client FPs in unknown TS frameworks

- Risk ID: RISK-SIGNAL-2026-04-12-250
- Component: `src/drift/signals/missing_authorization.py`, `tests/test_missing_authorization.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: Missing Authorization (MAZ) now requires inbound-handler-like TypeScript/JavaScript function parameters (`req/request/res/response/reply/ctx/context/next`) when `framework=unknown` and the finding originates from route-like path evidence. This suppresses outbound API client helper false positives.
- Trigger: `drift analyze` on TS/JS repositories where SDK client wrappers call external APIs with route-looking paths (for example `/channels/...`) but do not expose inbound HTTP handlers.
- Impact: High-positive. Reduces CRITICAL-grade false positives for outbound client helpers and improves MAZ trust/actionability.
- Mitigation:
  - Added `_has_ts_inbound_handler_signature()` guard in MAZ unknown-framework branch.
  - Kept existing strong route-path requirement for unknown TS/JS framework detections.
  - Added regression `test_typescript_unknown_framework_skips_outbound_api_client_signature`.
  - Updated existing unknown-framework positive regression to include inbound handler params (`req`, `res`).
- Verification:
  - `python -m pytest tests/test_missing_authorization.py -q`
  - `python -m ruff check src/drift/signals/missing_authorization.py tests/test_missing_authorization.py`
- Residual risk: Low-Medium. Unknown-framework handlers that use non-standard parameter names may be down-prioritized; known framework branches are unaffected.

## 2026-04-12 - Issue #248: EDS TS/TSX self-documenting signature heuristic

- Risk ID: RISK-SIGNAL-2026-04-12-248
- Component: `src/drift/signals/explainability_deficit.py`, `tests/test_coverage_boost_15_signals_misc.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: Explainability Deficit (EDS) treats typed TypeScript/TSX function signatures as explainability evidence and no longer penalizes missing JSDoc or explicit return annotations in those self-documenting signature contexts.
- Trigger: `drift analyze` on TypeScript-heavy repositories where many functions are typed but intentionally undocumented via JSDoc.
- Impact: High-positive. Reduces dominant EDS false-positive volume and improves signal credibility/actionability in TS/TSX ecosystems.
- Mitigation:
  - Added `_has_self_documenting_ts_signature()` and language-aware scoring in EDS.
  - Added inferred-return evidence path for TS/TSX signatures without explicit return types.
  - Restricted behavior to TS/TSX; JS behavior remains unchanged.
  - Added targeted regressions for typed signature, inferred return, and JS guard behavior.
- Verification:
  - `python -m pytest tests/test_coverage_boost_15_signals_misc.py -q --tb=short`
  - `python -m ruff check src/drift/signals/explainability_deficit.py tests/test_coverage_boost_15_signals_misc.py`
- Residual risk: Low-Medium. Some truly unclear TS helpers may be down-prioritized when signatures exist; mitigation scope is language-bounded and keeps non-TS behavior intact.

## 2026-04-12 - Issue #247: GCD TypeScript precision hardening for declarative wrappers

- Risk ID: RISK-SIGNAL-2026-04-12-247
- Component: `src/drift/signals/guard_clause_deficit.py`, `tests/test_ts_signals_phase2.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: Guard Clause Deficit (GCD) erkennt jetzt TypeScript-Call-through-Wrapper und stark typisierte non-imperative Funktionen als guarded, um false positives in deklarativem Plugin-/Adaptercode zu reduzieren.
- Trigger: `drift analyze` auf TS-Repositories mit delegierenden `export function`/arrow Wrappern und stark typisierten Transformationsfunktionen ohne imperative Kontrollflusszweige.
- Impact: Medium-positive. Reduziert GCD-FP-Noise und verbessert Signal-Glaubwuerdigkeit bei plugin-/integration-lastigen Monorepos.
- Mitigation:
  - Neue TS-Wrapper-Heuristik fuer einzeilige parameter-forwarding delegation functions.
  - Neue Typ-Heuristik fuer stark typisierte TS-Parameter (Ausschluss weak types) in non-imperativen Bodies.
  - Korrektur eines doppelten Guarded-/Complexity-Zaehlpfads im GCD-Loop zur konsistenten Modulaggregation.
  - Regressionen in `tests/test_ts_signals_phase2.py` fuer Wrapper- und Typed-Pattern plus bestehender unguarded Kontrolltest.
- Verification:
  - `python -m ruff check src/drift/signals/guard_clause_deficit.py tests/test_ts_signals_phase2.py`
  - `python -m pytest tests/test_ts_signals_phase2.py -k "GCDTypeScript and (delegation or strongly_typed or unguarded_functions_triggers or guarded_functions_no_finding)" --tb=short -q`
- Residual risk: Low-Medium. Echte Guard-Defizite in einfach aufgebauten Wrappern koennen punktuell niedriger priorisiert werden; Scope bleibt durch enge Pattern-Bedingungen begrenzt.

## 2026-04-12 - Issue #246: SMS suppresses novel deps in newly introduced plugin workspaces

- Risk ID: RISK-SIGNAL-2026-04-12-246
- Component: `src/drift/signals/system_misalignment.py`, `tests/test_coverage_signals.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: System Misalignment (SMS) erkennt jetzt neue Runtime-Plugin-Workspaces (`extensions/*`, `plugins/*`) ueber Dateihistorie und unterdrueckt dort Novel-Dependency-Findings waehrend der initialen Einfuehrungsphase.
- Trigger: `drift analyze` auf Plugin-Monorepos, in denen neue Extension-Provider in einem Zeitfenster mit mehreren erstmaligen Drittanbieter-Abhaengigkeiten eingefuehrt werden.
- Impact: High-positive. Reduziert dominante SMS-False-Positives und verhindert Severity-Inflation bei architektonisch erwarteter Plugin-Erweiterung.
- Mitigation:
  - Neue Workspace-Heuristik `_runtime_plugin_workspace_key` + `_new_runtime_plugin_workspaces`.
  - SMS skippt Novel-Import-Erkennung nur fuer Workspaces mit ausschliesslich recent getrackter Historie.
  - Regressionen fuer beide Richtungen: neue Workspace-Suppression und unveraenderte Erkennung bei etabliertem Workspace.
- Verification:
  - `python -m pytest tests/test_coverage_signals.py -q --tb=short -k sms`
  - `python -m ruff check src/drift/signals/system_misalignment.py tests/test_coverage_signals.py`
- Residual risk: Low-Medium. Echte Erst-Commit-Misalignment-Faelle in brandneuen Workspaces werden voruebergehend nicht durch SMS priorisiert; nach Etablierung des Workspaces greift SMS wieder normal.

## 2026-04-12 - Issue #245: PFS combined framework+plugin context severity cap

- Risk ID: RISK-SIGNAL-2026-04-12-245
- Component: `src/drift/signals/pattern_fragmentation.py`, `tests/test_pattern_fragmentation.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: Pattern Fragmentation (PFS) now caps severity to `INFO` when both context dampeners are active (`framework_context_dampened=true` and `plugin_context_dampened=true`). This targets intentional cross-extension diversity in plugin monorepos.
- Trigger: `drift analyze` on repositories with multiple extensions/plugins where framework-facing API/error-handling variants differ by provider contract.
- Impact: Medium-positive. Reduces residual PFS triage noise for known intentional plugin-boundary diversity while preserving finding traceability.
- Mitigation:
  - Add combined-context terminal severity cap (`combined_plugin_framework_cap`).
  - Keep full finding metadata so context remains inspectable for manual review.
  - Add targeted regression `test_combined_framework_and_plugin_dampening_caps_to_info`.
- Verification:
  - `python -m pytest tests/test_pattern_fragmentation.py -q --tb=short`
  - `python -m ruff check src/drift/signals/pattern_fragmentation.py tests/test_pattern_fragmentation.py`
- Residual risk: Low-Medium. Some real extension-local fragmentation may be down-ranked when both hints are present; scope is intentionally narrow to combined-context cases.

## 2026-04-12 - Issue #244: MDS caps cross-plugin workspace duplicates to INFO

- Risk ID: RISK-SIGNAL-2026-04-12-244
- Component: `src/drift/signals/mutant_duplicates.py`, `tests/test_mutant_duplicates_edge_cases.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: Mutant Duplicate Signal (MDS) now detects duplicate groups/pairs that span different plugin workspaces (`extensions/*` or `plugins/*`) and caps those findings to `INFO` with reduced score, because this pattern is often deliberate isolation.
- Trigger: `drift analyze` on plugin monorepos with intentionally copied helpers/boilerplate across independent workspace packages.
- Impact: High-positive. Reduces dominant MDS false-positive severity inflation and improves trust/actionability for plugin architectures.
- Mitigation:
  - Added workspace-scope helpers in MDS (`_workspace_plugin_scope`, cross-workspace pair/group detection).
  - Exact duplicate groups across different plugin scopes are emitted as `INFO` with low score and explicit metadata marker.
  - Near-duplicate cross-workspace pairs are severity/score-capped and get intent-preserving fix guidance.
  - Added targeted regressions for cross-workspace and same-workspace behavior.
- Verification:
  - `python -m pytest tests/test_mutant_duplicates_edge_cases.py -q --tb=short`
  - `python -m ruff check src/drift/signals/mutant_duplicates.py tests/test_mutant_duplicates_edge_cases.py`
- Residual risk: Low-Medium. Some true cross-plugin duplication worth refactoring may now be lower priority; bounded by strict cross-workspace scope requirement and preserved same-workspace high-severity behavior.

## 2026-04-12 - Issue #243: CCC suppresses parallel implementation FPs and honors explicit TS type imports

- Risk ID: RISK-SIGNAL-2026-04-12-243
- Component: `src/drift/signals/co_change_coupling.py`, `tests/test_co_change_coupling.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: Co-Change Coupling (CCC) now suppresses known intentional parallel-implementation patterns (runtime variant siblings and cross-extension template entrypoints) and treats resolved relative TypeScript type imports as explicit dependencies.
- Trigger: `drift analyze` on plugin/runtime-heavy TypeScript monorepos where contract-level co-changes dominate (`*-gateway`/`*-node`, `extensions/*/src/index.ts`) and where explicit imports use runtime specifiers (`./types.js` from `.ts`).
- Impact: High-positive. Reduces dominant CCC false-positive clusters and improves finding actionability and trust.
- Mitigation:
  - Added bounded parallel-pattern suppressions:
    - same-directory runtime sibling variants via normalized filename tokens
    - cross-extension template entrypoints for `src/index.{ts,js,tsx,jsx}`
  - Extended relative import resolver to normalize relative paths and map JS runtime extensions to TS source candidates for known in-repo files.
  - Added regression tests for all three Issue #243 FP classes.
- Verification:
  - `python -m pytest tests/test_co_change_coupling.py -q --tb=short`
  - `python -m ruff check src/drift/signals/co_change_coupling.py tests/test_co_change_coupling.py`
- Residual risk: Low-Medium. Some true hidden-coupling cases that intentionally mimic variant/template naming may be under-reported; suppression scope is intentionally narrow and guarded by non-template cross-extension detection tests.

## 2026-04-12 - Issue #242: DCA plugin entrypoint FP reduction (`components`/`plugin-sdk`)

- Risk ID: RISK-SIGNAL-2026-04-12-242
- Component: `src/drift/signals/dead_code_accumulation.py`, `tests/test_dead_code_accumulation.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: Dead Code Accumulation (DCA) daempft nun plugin-/extension-Entrypoint-Pfade mit `components` oder `plugin-sdk` unter `extensions/*` und `plugins/*`, da diese Exporte haeufig indirekt via Host-Registry oder Framework-Runtime konsumiert werden.
- Trigger: `drift analyze` auf Plugin-Monorepos mit UI-Komponenten-Barrels und SDK-Entrypoints ohne direkte in-repo Importkanten.
- Impact: Medium-positive. Reduziert dominante DCA-FP-Cluster fuer Plugin-Entrypoints und verhindert CRITICAL/HIGH-Ueberpriorisierung bei statisch schwer aufloesbaren Runtime-Consumption-Pfaden.
- Mitigation:
  - Neue Heuristik `_is_runtime_plugin_entrypoint_path()` fuer `components`/`plugin-sdk`-Indikatoren in `extensions|plugins`.
  - Bestehendes DCA-Daempfungsmuster wiederverwendet (Score-Daempfung, Severity-Cap MEDIUM).
  - Neues Metadata-Feld `runtime_plugin_entrypoint_heuristic_applied` fuer technische Nachvollziehbarkeit.
  - Regressionen: `test_extensions_components_entrypoint_is_dampened_to_medium`, `test_extensions_plugin_sdk_entrypoint_is_dampened_to_medium`.
- Verification:
  - `python -m pytest tests/test_dead_code_accumulation.py -q --tb=short`
  - `python -m ruff check src/drift/signals/dead_code_accumulation.py tests/test_dead_code_accumulation.py`
- Residual risk: Low-Medium. Echte ungenutzte Exporte in betroffenen Entrypoint-Dateien koennen geringer priorisiert werden; durch engen Scope und fehlende Vollsuppression begrenzt.

## 2026-04-12 - Issue #241: AVS TS ESM relative import extension mapping

- Risk ID: RISK-SIGNAL-2026-04-12-241
- Component: `src/drift/signals/architecture_violation.py`, `tests/test_architecture_violation.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: AVS import graph resolution now maps TypeScript ESM relative runtime specifiers (`.js`, `.jsx`, `.mjs`, `.cjs`) to matching source extensions (`.ts`, `.tsx`, `.mts`, `.cts`) and resolves path-like relative imports against known internal files.
- Trigger: `drift analyze` on TS/JS ESM repositories that import local source modules using runtime extensions (for example `../agents/chutes-oauth.js` from `.ts` files).
- Impact: High-positive. Reduces AVS hidden-coupling false positives where a real static import edge exists but was previously unresolved.
- Mitigation:
  - New AVS helper `_relative_path_candidates()` normalizes relative path specs and applies extension alias candidates.
  - `build_import_graph()` now resolves both module-like and path-like imports via `module_to_file` and `path_to_file` indices.
  - Regressions added for `.js -> .ts` and `.mjs/.cjs -> .mts/.cts` mappings.
- Verification:
  - `python -m pytest tests/test_architecture_violation.py -q --tb=short`
  - `python -m ruff check src/drift/signals/architecture_violation.py tests/test_architecture_violation.py`
- Residual risk: Low-Medium. Aggressive extension aliasing may resolve to an unintended sibling file in edge cases with mixed source/runtime mirrors; scope is bounded to relative specifiers and known in-repo files.

## 2026-04-12 - Issue #240: NBV TS naming-contract FP reduction (`try*` nullable getter)

- Risk ID: RISK-SIGNAL-2026-04-12-240
- Component: `src/drift/signals/naming_contract_violation.py`, `tests/test_naming_contract_violation.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: Naming Contract Violation (NBV) erkennt fuer TypeScript `try*` nun nullable Getter-Vertraege (`T | undefined` / `T | null`) als gueltige Attempt-Semantik. Zusaetzlich sichern Regressionstests die konkreten OpenClaw-Muster fuer `tryGet*`, `ensureSession` Lazy-Init und `is*`-Bool-Ausdrucke.
- Trigger: `drift analyze` auf TypeScript-Repositories mit best-effort Runtime-Gettern und lazy-init Patterns.
- Impact: Medium-positive. Erwartete Reduktion dominanter NBV-FPs bei TS-Konventionen und verbesserte Signal-Glaubwuerdigkeit.
- Mitigation:
  - Neue TS-Contract-Heuristik `_ts_has_nullable_return_contract()` fuer `try_*`.
  - Regressionen: `test_try_ts_nullable_getter_contract_no_finding`, `test_ensure_ts_lazy_init_method_no_finding`, `test_boolean_or_expression_return_no_finding`.
  - Keine Aenderung an Python-Regeln; Prefix-begrenzte TS-Logik.
- Verification:
  - `python -m pytest tests/test_naming_contract_violation.py -q --tb=short`
  - `python -m ruff check src/drift/signals/naming_contract_violation.py tests/test_naming_contract_violation.py`
- Residual risk: Low-Medium. Nullable-Return-Signaturen koennen in Randfaellen semantisch schwache `try*`-Implementierungen passieren lassen; Risiko ist durch enge Prefix-Skopierung und bestehende Negativkontrollen begrenzt.

## 2026-04-12 - Issue #238: HSC suppresses dynamic template literals

- Risk ID: RISK-SIGNAL-2026-04-12-238
- Component: `src/drift/signals/hardcoded_secret.py`, `tests/test_hardcoded_secret.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: Hardcoded Secret (HSC) treats TS/JS template literals with interpolation (`${...}`) as runtime-generated values and suppresses these findings before entropy evaluation.
- Trigger: `drift analyze` on repositories that build token-like strings via template interpolation (for example UUID-based test tokens, display tokenizers, JWT assembly).
- Impact: Medium-positive. Reduces high-severity HSC false positives and improves actionability in JS/TS-heavy repositories.
- Mitigation:
  - New HSC helper `_is_dynamic_template_literal(quote, string_val)` with strict guard `quote == "`" and `${` present.
  - Suppression only for interpolated template literals; static string literals and known-prefix token detection remain unchanged.
  - Regression tests for three concrete OpenClaw patterns added to `tests/test_hardcoded_secret.py`.
- Residual risk: Low-Medium. A true secret intentionally assembled via template interpolation may now be under-reported; known-prefix hardcoded tokens and non-interpolated literals remain covered.

## 2026-04-11 - ADR-061: Pflichtmaessige Phasen-Telemetrie

- Risk ID: RISK-OUTPUT-2026-04-11-061
- Component: `src/drift/analyzer.py`, `src/drift/pipeline.py`, `src/drift/output/json_output.py`, `src/drift/output/rich_output.py`
- Type: Performance observability and output contract extension
- Description: Drift publiziert standardmaessig Zeitmessungen pro Analysephase (`discover`, `parse`, `git`, `signals`, `output`) und `total`.
- Trigger: Jeder `drift analyze` Lauf (JSON und Rich Rendering).
- Impact: Medium-positive fuer Bottleneck-Diagnose; low compatibility risk fuer Consumer, die `summary`-Schluessellisten strikt validieren.
- Mitigation:
  - Additive Erweiterung (`summary.phase_timing`) ohne Entfernen bestehender Felder.
  - Beibehaltung von `analysis_duration_seconds` als bestehender Gesamtwert.
  - Golden- und Output-Tests auf aktualisierten Summary-Vertrag.
- Verification:
  - `pytest tests/test_json_output.py -q`
  - `pytest tests/test_output_golden.py -q`
  - `pytest tests/test_rich_output_boost.py -q`
  - `pytest tests/test_pipeline_components.py -q`
  - `python scripts/check_risk_audit.py --diff-base origin/main`
- Residual risk: Low. Phasenzeiten sind additive Diagnosefelder; Summenabweichungen durch Ingestion-Parallelitaet (parse/git) sind dokumentiert.

## 2026-04-11 - ADR-060: JSON-Response-Profiling fuer analyze-output

- Risk ID: RISK-OUTPUT-2026-04-11-060
- Component: `src/drift/output/json_output.py`, `src/drift/commands/analyze.py`, `src/drift/api_helpers.py`
- Type: Output shaping and serialization performance hardening
- Description: JSON finding payloads can now be emitted as `concise` or `detailed`; serializer uses shared slim base payloads with additive detailed materialization.
- Trigger: `drift analyze --format json --response-detail concise|detailed` and internal serializer usage.
- Impact: Medium-positive for CPU/time on concise flows; low-medium compatibility risk if consumers implicitly rely on detailed-only fields while requesting concise.
- Mitigation:
  - CLI default remains `detailed` for backward compatibility.
  - Explicit profile opt-in via `--response-detail`.
  - Targeted serializer tests for concise/detailed behavior and existing golden structure.
- Verification:
  - `pytest tests/test_json_output.py -q`
  - `pytest tests/test_output_golden.py -q`
  - `pytest tests/test_api_and_ts_arch_boost.py -q`
  - `python scripts/check_risk_audit.py --diff-base origin/main`
- Residual risk: Low. Profile-specific field expectations can still cause downstream adaptation work if concise is enabled by consumers.

## 2026-04-11 - ADR-059: Persistenter Nudge-Baseline-Store

- Risk ID: RISK-INCREMENTAL-2026-04-11-059
- Component: `src/drift/incremental.py`, `src/drift/api/nudge.py`, `tests/test_nudge.py`
- Type: Incremental runtime performance path extension (local persistent baseline)
- Description: `nudge` kann Baselines ueber Prozessgrenzen aus `.drift-cache/nudge_baselines/` wiederverwenden, key-basiert auf `HEAD` + Config-Fingerprint + Schema-Version.
- Trigger: Wiederholte `nudge`-Aufrufe mit Prozessneustart bei unveraendertem Repository-Zustand.
- Impact: Medium-positive fuer Latenz des ersten `nudge`; Medium-Risiko fuer stale/inkonsistente Cache-Zustaende bei Artefaktmanipulation oder Schema-Drift.
- Mitigation:
  - Harte Key-Invalidierung (HEAD + config fingerprint + schema version).
  - Defensive Deserialisierung und fallback auf Full-Scan statt Hard-Fail.
  - Atomare Writes (temp file + replace) mit explizitem UTF-8.
  - Regressionstest fuer Prozessgrenzen-Warmstart (`disk_warm_hit`) und Config-Mismatch-Rebuild.
- Verification:
  - `pytest tests/test_nudge.py -q --tb=short`
  - `pytest tests/test_incremental.py -q --tb=short`
  - `python scripts/check_risk_audit.py --diff-base origin/main`
- Residual risk: Low-Medium. Lokale Cache-Korruption oder absichtliche Tampering-Angriffe koennen Warm-Hits reduzieren; Ergebnis-Korrektheit bleibt durch deterministischen Full-Scan-Fallback priorisiert.

## 2026-04-11 - ADR-058: Inkrementeller persistenter Git-History-Index

- Risk ID: RISK-INGESTION-2026-04-11-058
- Component: `src/drift/ingestion/git_history.py`, `src/drift/pipeline.py`, `src/drift/config.py`, `tests/test_git_history_index.py`
- Type: Ingestion performance path extension (local persistent index)
- Description: Optionaler persistenter Git-History-Index (`manifest.json` + `commits.jsonl`) ersetzt bei Warm-Runs das wiederholte Full-Parsing von `git log --numstat` und laedt nur Delta-Commits seit letztem indexierten Head nach.
- Trigger: Wiederholte `drift analyze`-Laeufe auf grossen Repositories mit aktiviertem `git_history_index_enabled`.
- Impact: Medium-positive fuer Laufzeit und Ressourcenverbrauch; gleichzeitig Medium-Risiko fuer inkonsistente Cache-Zustaende bei History-Rewrite/Korruption.
- Mitigation:
  - Feature-Flag default `false` fuer kontrollierten Rollout.
  - Manifest-Validierung (Schema-Version, Repo-Key, Parameter-Fingerprint).
  - Ancestry-Guard (`merge-base --is-ancestor`) fuer Delta-Append; Full-Rebuild bei Rebase/Force-Push.
  - Defensive JSONL-Deserialisierung und sichere Fallbacks ohne Hard-Fail der Analyse.
  - Regressionstests fuer Initial-Build, Delta-Append und Rebuild bei Rewrite.
- Verification:
  - `pytest tests/test_git_history_index.py -q`
  - `pytest tests/test_pipeline_components.py -q`
  - `python scripts/check_risk_audit.py --diff-base origin/main`
- Residual risk: Low-Medium. Stark fragmentierte oder manipulierte lokale Cache-Dateien koennen Warm-Run-Vorteile reduzieren; durch deterministic fallback auf Full-Rebuild bleibt Ergebnis-Korrektheit priorisiert.

## 2026-04-11 - Issue #237: DCA dampening fuer runtime plugin config module

- Risk ID: RISK-SIGNAL-2026-04-11-237
- Component: `src/drift/signals/dead_code_accumulation.py`, `tests/test_dead_code_accumulation.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: Dead Code Accumulation (DCA) daempft nun Findings fuer plugin-/extension-Config-Dateien (`extensions/*` oder `plugins/*` mit `config*` Dateinamen), da solche Module in Plugin-Architekturen haeufig per runtime `import()` geladen werden und statisch schwer aufloesbar sind.
- Trigger: `drift analyze` auf monorepoartigen Plugin-Repositories (z. B. OpenClaw), in denen `config.ts`-Exporte dynamisch konsumiert werden.
- Impact: Medium-positive. Reduziert dominante DCA-FP-Cluster und verhindert HIGH-Ueberpriorisierung fuer runtime-geladene Config-Exports.
- Mitigation:
  - Neue DCA-Heuristik fuer `extensions|plugins` + `config*` Dateimuster.
  - Score-Daempfung (`*0.6`) plus Severity-Cap auf MEDIUM (`<=0.69`).
  - Metadata-Marker `runtime_plugin_config_heuristic_applied` fuer Nachvollziehbarkeit.
  - Regressionen fuer gedaempfte Config-Datei und unveraenderte HIGH-Priorisierung bei Nicht-Config-Datei.
- Residual risk: Low-Medium. Echte ungenutzte Exports in Plugin-Config-Dateien koennen niedriger priorisiert werden; Risiko ist durch engen Scope und fehlende komplette Suppression begrenzt.

## 2026-04-11 - Issue #235: CCC suppresses intra-package monorepo co-change pairs

- Risk ID: RISK-SIGNAL-2026-04-11-235
- Component: `src/drift/signals/co_change_coupling.py`, `tests/test_co_change_coupling.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: Co-Change Coupling now suppresses file pairs that belong to the same monorepo subpackage, using nearest subpackage `package.json` (below repo root) and a bounded `extensions/<name>/` fallback. This prevents expected extension-internal co-changes from being reported as hidden coupling.
- Trigger: `drift analyze` on monorepos with extension/package layout where config/types/index/tool files co-change inside a single extension.
- Impact: High-positive. Removes dominant CCC FP cluster in extension-based monorepos and improves finding actionability.
- Mitigation:
  - Intra-subpackage suppression gate in CCC pair evaluation.
  - Root-level package manifest intentionally ignored to avoid globally suppressing single-package repos.
  - Regressions added for suppressed intra-extension pair and preserved cross-extension detection.
- Residual risk: Low-Medium. Real coupling within one extension package may be under-reported; bounded by intentional package-local interpretation and retained cross-package detection.

## 2026-04-11 - Issue #236: HSC suppression fuer test-prefix fixture secrets

- Risk ID: RISK-SIGNAL-2026-04-11-236
- Component: `src/drift/signals/hardcoded_secret.py`, `tests/test_hardcoded_secret.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: Hardcoded Secret (HSC) behandelt jetzt explizit testmarkierte Variablennamen (`TEST_`, `MOCK_`, `FAKE_`, `DUMMY_`, `STUB_`) als Fixture-Kontext und unterdrueckt entsprechende Findings. Zusaetzlich erkennt HSC `*.test-helpers.*` robust als testnahen Kontext.
- Trigger: `drift analyze` auf Repositories mit testnahen Credentials in Hilfs-/Fixture-Dateien (z. B. OpenClaw test-fixtures und test-helpers).
- Impact: Medium-positive. Reduziert HSC-False-Positives in Testinfrastruktur und verbessert Glaubwuerdigkeit/Actionability.
- Mitigation:
  - Prefix-Suppression in Python/TS HSC-Pfaden inklusive Known-Prefix-Erkennung.
  - Erweiterte HSC-Path-Heuristik fuer `test-helpers` plus bestehende `test-fixture` Varianten.
  - Regressionssuite erweitert um test-helper-Datei und Prefix-Faelle in Python/TypeScript.
- Residual risk: Low-Medium. Echte Leaks mit absichtlich testartigen Variablennamen koennen unterdrueckt werden; Risiko bleibt durch enge Prefix-Liste und bestehende TP-Guards begrenzt.

## 2026-04-11 - Issue #234: Test-file detection erweitert fuer test-harness/test-helpers Konventionen

- Risk ID: RISK-INGESTION-2026-04-11-234
- Component: `src/drift/ingestion/test_detection.py`, `tests/test_test_detection.py`
- Type: Ingestion precision hardening (false-positive reduction)
- Description: Die zentrale Testdatei-Erkennung stuft jetzt `*.test-harness.{ts,js,tsx,jsx}`, `*.test-helpers.{ts,js,tsx,jsx}` sowie Verzeichnisse `test-support/` und `test-helpers/` als Testkontext ein.
- Trigger: Repositories mit testnahen Konventionen ausserhalb klassischer `tests/`- oder `*.spec/*test`-Namen (z. B. OpenClaw).
- Impact: High-positive. Reduziert grosse FP-Cluster ueber mehrere Signale durch korrekte `finding_context=test` Klassifikation.
- Mitigation:
  - Erweiterte zentrale Regex-Muster in `is_test_file` statt signal-spezifischer Sonderlogik.
  - Regressionen fuer alle neuen Muster in `tests/test_test_detection.py`.
  - Bestehende Fixture-Ausnahmen (`tests/fixtures`, `test/fixtures`) bleiben unveraendert.
- Residual risk: Low-Medium. Projekte mit produktiven Dateinamen, die absichtlich `test-helpers`/`test-support` verwenden, koennten in Einzelfaellen als Testcode klassifiziert werden.

## 2026-04-11 - Issue #232: SMS excludes test-only framework imports from production novel-import analysis

- Risk ID: RISK-SIGNAL-2026-04-11-232
- Component: `src/drift/signals/system_misalignment.py`, `tests/test_coverage_signals.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: System Misalignment (SMS) schliesst Testdateien aus der Baseline- und Novel-Import-Analyse aus. Damit werden Test-Framework-Imports wie `vitest` in `.test.ts` nicht mehr als produktive Novel Imports in Modulfindings gezahlt.
- Trigger: `drift analyze` auf Repositories mit co-lokierten Tests in Modulpfaden (z. B. `*.test.ts`, `*.spec.ts`, `__tests__/`).
- Impact: Medium-positive. Reduziert SMS-FP-Cluster deutlich und verbessert Glaubwuerdigkeit sowie Handlungsfaehigkeit der SMS-Befunde.
- Mitigation:
  - Filter ueber zentrale Testdatei-Erkennung (`is_test_file`) in `_module_imports`, `_find_novel_imports` und im Analyze-Kandidaten-Set.
  - Regressionstest `test_find_novel_imports_ignores_test_only_framework_imports` deckt den vitest-Fall ab.
  - Keine neue, signal-spezifische Pfadheuristik; Nutzung der etablierten zentralen Klassifikation.
- Residual risk: Low-Medium. Randfaelle mit testaehnlicher Dateibenennung koennen produktive Dateien ausschliessen; Risiko ist durch bestehende zentrale Klassifikationsregeln und Fixture-Ausnahmen begrenzt.

## 2026-04-11 - Issue #230: COD Logger-/Utility-FP-Reduktion

- Risk ID: RISK-SIGNAL-2026-04-11-230
- Component: `src/drift/signals/cohesion_deficit.py`, `tests/test_cohesion_deficit.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: Cohesion Deficit (COD) beruecksichtigt jetzt Logger- und Utility-Modulkontext. Logger-Fassaden (`trace/debug/info/warn/error`) werden als absichtliches Muster erkannt und stark gedaempft; Utility-Dateinamen (`utils/helpers/constants`) erhalten eine moderate Dempfung.
- Trigger: `drift analyze` auf TypeScript-/Python-Repositories mit Logger-Facades oder Utility-Modulen mit voneinander unabhaengigen Hilfsfunktionen.
- Impact: Medium-positive. Erwartete deutliche Reduktion von COD-False-Positives und bessere Actionability bei grossen Repos.
- Mitigation:
  - Neue Logger-Mustererkennung ueber Dateinamen- und Unit-Namens-Signale.
  - Pattern-Dempfung im Scoring-Pfad (`module_pattern_dampening`) mit konservativen Faktoren.
  - Utility-Dempfung bleibt bounded, sodass klare Defizite weiter detektierbar sind.
  - Regressionen: `test_cod_logger_module_is_not_flagged`, `test_cod_utility_filename_still_flags_clear_deficit`.
  - Ground-truth/Precision-Recall Suite weiterhin gruen.
- Residual risk: Low-Medium. In seltenen Faellen kann echte Inkohaerenz in Logger-Modulen abgeschwaecht priorisiert werden; durch begrenzte Triggerbedingungen und bestehende COD-Regressionen reduziert.

## 2026-04-11 - Issue #231: DCA TS/JS default-export helper false positives

- Risk ID: RISK-SIGNAL-2026-04-11-231
- Component: `src/drift/signals/dead_code_accumulation.py`, `tests/test_ts_export_detection.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: Dead Code Accumulation (DCA) betrachtet in TS/JS jetzt nur tatsaechlich exportierte Funktionen (`is_exported=True`) als Exportkandidaten. Modulinterne Helper in Dateien mit `export default` werden dadurch nicht mehr als ungenutzte Exports klassifiziert.
- Trigger: `drift analyze` auf TypeScript-/JavaScript-Repositories mit Facade-Modulen, Plugin-Entrypoints oder default-export-basierten Extension-Dateien.
- Impact: Medium-positive. Reduziert dominante DCA-FP-Cluster und verbessert Signal-Glaubwuerdigkeit/Actionability.
- Mitigation:
  - DCA-Exportsammlung fuer TS/JS an `FunctionInfo.is_exported` gebunden.
  - Regression `test_non_exported_ts_functions_are_not_treated_as_exports` deckt den FP-Fall ab.
  - Bestehende TS Export-Detection-Tests bleiben als Guard aktiv.
- Residual risk: Low-Medium. Wenn Export-Erkennung im Parser fehlerhaft ist, kann es zu FN bei echten ungenutzten Exports kommen; durch bestehende Export-Detection-Tests begrenzt.

## 2026-04-11 - Issue #229: PFS Plugin-/Extension-Boundary Dempfung

- Risk ID: RISK-SIGNAL-2026-04-11-229
- Component: `src/drift/signals/pattern_fragmentation.py`, `tests/test_pattern_fragmentation.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: Pattern Fragmentation (PFS) erkennt jetzt Plugin-Architekturkontext (`extensions`/`plugins`/`packages`) und reduziert Severity in Multi-Plugin-Surfaces, damit absichtliche extension-spezifische API-Varianten nicht als HIGH-Drift priorisiert werden.
- Trigger: `drift analyze` auf Repositories mit pluginbasierter Struktur wie `extensions/<plugin>/src` und heterogenen Endpunkt-/Handler-Mustern pro Plugin.
- Impact: High-positive. Reduziert FP-Cluster und verbessert Handlungsfaehigkeit bei PFS in Monorepos mit Plugin-System.
- Mitigation:
  - Neue Plugin-Scope-Erkennung ueber Modulpfad.
  - Dempfung nur bei nachweisbarer Multi-Plugin-Struktur (`>=3` Plugin-Namen unter gleichem Root).
  - Severity-Cap auf LOW bei aktivem Plugin-Kontext.
  - Metadata-Erweiterung: `plugin_context_dampened`, `plugin_context_hints`.
  - Regressionstest: `test_plugin_architecture_api_fragmentation_is_dampened_to_low`.
- Residual risk: Low-Medium. In seltenen Faellen kann echte Fragmentierung in Plugin-Modulen unterpriorisiert werden; Core-Module ohne Plugin-Kontext bleiben unbeeinflusst.

## 2026-04-11 - Issue #227: HSC FP-Reduktion fuer Prefix-/Endpoint-/Fixture-/Profile-ID-Konstanten

- Risk ID: RISK-SIGNAL-2026-04-11-227
- Component: `src/drift/signals/hardcoded_secret.py`, `tests/test_hardcoded_secret.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: Hardcoded Secret (HSC) unterdrueckt jetzt vier dominante FP-Klassen aus OpenClaw-Validierung: (1) kurze Token-Prefix-Marker-Literale, (2) Endpoint/Issuer-Template-Konstanten, (3) `test-fixture`-Pfadkontexte, (4) Profil-/Config-ID-Literale.
- Trigger: `drift analyze` auf TS/Python-Repos mit OAuth-Endpoint-Konstanten, Token-Prefix-Validatoren oder test-fixture-Dateinamen ausserhalb klassischer `tests/`-Pfade.
- Impact: Medium-positive. Erwartete deutliche FP-Reduktion im HSC-Signal und bessere Actionability.
- Mitigation:
  - Prefix-Marker-Suppression nur fuer markerartige kurze Literale mit `-`/`_`-Suffix.
  - Endpoint-Template-Suppression fuer endpointartige Variablennamen.
  - Extra test-fixture-Pfaderkennung (`test-fixture`, `test_fixture`).
  - Config/Profile-ID-Suppression fuer identifierartige Literale ohne Leerzeichen.
  - Regressionssuite erweitert (`test_token_prefix_constant_not_flagged_when_literal_is_only_prefix`, `test_ts_token_endpoint_template_constant_not_flagged`, `test_config_profile_id_constant_not_flagged`, `test_ts_test_fixture_placeholder_not_flagged`).
- Residual risk: Low-Medium. Edge-Cases mit absichtlich geheimen Werten in identifierartigen Konstanten bleiben moeglich; Known-Prefix-Guard-Test fuer volle Tokenwerte bleibt aktiv.

## 2026-04-11 - Issue #219: NBV TS style-only naming checks removed + duplicate findings eliminated

- Risk ID: RISK-SIGNAL-2026-04-11-219
- Component: `src/drift/signals/naming_contract_violation.py`, `tests/test_ts_naming_consistency.py`
- Type: Signal behavior change (precision hardening)
- Description: NBV no longer reports TypeScript interface I-prefix convention and mixed generic parameter naming as drift findings. Additionally, duplicated TS naming blocks in NBV were consolidated, removing duplicate findings emitted for the same file/pattern.
- Trigger: `drift analyze` on TS-heavy repositories with mixed `T`/`TName` generic naming or repository-specific interface naming conventions (`I*` vs no-prefix).
- Impact: High-positive. Reduces style-driven false positives and removes duplicate low-severity noise, improving NBV credibility and actionability.
- Mitigation:
  - Removed TS style-only NBV sub-checks for interface prefix and generic naming mix.
  - Kept architecture-relevant enum casing consistency check.
  - Added regressions asserting no I-prefix/generic-style findings and exactly one enum-casing finding (duplicate guard).
- Residual risk: Low-Medium. Teams that intentionally want strict naming-style enforcement no longer receive these NBV findings; this is accepted because the checks are stylistic, not architectural.

## 2026-04-11 - Issue #215: NBV TS is*/has* bool-return extraction and fallback hardening

- Risk ID: RISK-SIGNAL-2026-04-11-215
- Component: `src/drift/ingestion/ts_parser.py`, `src/drift/signals/naming_contract_violation.py`, `tests/test_typescript_parser.py`, `tests/test_naming_contract_violation.py`
- Type: Signal behavior change (precision hardening)
- Description: NBV now extracts TypeScript return types from typed-arrow declarators (`const isX: (...) => boolean = ...`) and treats TS type-predicate annotations (`x is Foo`) as bool-compatible. If return annotations are absent, NBV uses bounded expression heuristics (`!`, comparisons, `instanceof`, `in`, `Boolean(...)`) for bool-return inference.
- Trigger: `drift analyze` on TS-heavy repositories with `is*`/`has*` helpers where parser metadata previously exposed `return_type: N/A`.
- Impact: High-positive. Expected strong false-positive reduction for NBV naming checks without weakening strict non-bool controls.
- Mitigation:
  - Added `_extract_ts_return_type()` in TS parser with declarator type fallback.
  - Extended `_is_bool_like_return_type()` for TS type predicates.
  - Hardened `_ts_has_bool_return()` with conservative bool-expression checks for unannotated returns.
  - Added regressions for typed-arrow, type-predicate, and comparison-return scenarios.
- Residual risk: Low-Medium. Some edge-case expressions with implicit truthy/falsy semantics remain intentionally strict to avoid new false negatives.

## 2026-04-11 - Issue #214: NBV TS/JS ensure_* side-effect false positives

- Risk ID: RISK-SIGNAL-2026-04-11-214
- Component: `src/drift/signals/naming_contract_violation.py`, `tests/test_naming_contract_violation.py`
- Type: Signal behavior change (precision hardening)
- Description: NBV for TS/JS `ensure_*` now accepts idempotent ensure-by-side-effect contracts in addition to throw/value-return contracts. Covered side-effects include stateful assignments (`obj.key = ...`, `obj[key] ??= ...`) and common mutating initialization calls (`mkdir*`, `set`, `register`, `push`, `attachShadow`, `initialize`).
- Trigger: `drift analyze` on TS/JS repositories with initialization helpers that intentionally return `void`.
- Impact: Medium-positive. Reduces high-volume false positives in bootstrap/init code and improves NBV credibility.
- Mitigation:
  - Added `_ts_has_idempotent_side_effect()` and integrated it into `_ts_has_ensure_contract()`.
  - Added three positive regression tests for mkdir/property-assignment/registry-set ensure patterns.
  - Preserved strict negative control for no-op ensure functions without throw, return-value, or side-effects.
- Residual risk: Low. Some edge-case mutating call names may still be missed or overly accepted; bounded by explicit markers and regression coverage.

## 2026-04-11 - Issue #218: Zentralisierte Testdatei-Erkennung und finding_context-Angleichung

- Risk ID: RISK-SIGNAL-2026-04-11-218
- Component: `src/drift/ingestion/test_detection.py`, `src/drift/finding_context.py`, `src/drift/models.py`, `src/drift/signals/type_safety_bypass.py`, `src/drift/signals/missing_authorization.py`, `src/drift/signals/dead_code_accumulation.py`, `src/drift/signals/co_change_coupling.py`, `src/drift/signals/explainability_deficit.py`
- Type: Signal precision hardening (kontextbasierte Testdatei-Behandlung)
- Description: Test-/Generated-Kontext wird zentral klassifiziert und über `finding_context` standardisiert propagiert. Betroffene Signale nutzen einheitliches Verhalten via `test_file_handling` (`exclude` oder `reduce_severity`) statt uneinheitlicher lokaler Pfadregeln.
- Trigger: `drift analyze` auf Repositories mit hohem Anteil an Testdateien, Specs oder Mock-Code.
- Impact: Medium-positive. Reduziert FP-Volumen in Testkontexten und erhöht Vergleichbarkeit der Befunde über Signale hinweg.
- Mitigation:
  - Zentrale Pfadklassifizierung in `ingestion/test_detection.py`.
  - Einheitliche Kontexteinordnung über `classify_file_context` und `Finding.finding_context`.
  - Signal-spezifische Standardstrategie beibehalten (`TSB/MAZ` eher `exclude`, `DCA/CCC/EDS` eher `reduce_severity`).
  - Regressions- und Verhaltenstests für alle angepassten Signale ergänzt.
- Residual risk: Low-Medium. Falschklassifizierung in Randfällen (insbesondere projektspezifische Testpfade) bleibt möglich, ist aber per Konfigurations-Override begrenzbar.

## 2026-04-11 - Issue #213: MAZ unknown-framework false-positive suppression

- Risk ID: RISK-SIGNAL-2026-04-11-213
- Component: `src/drift/signals/missing_authorization.py`, `tests/test_missing_authorization.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: Missing Authorization (MAZ) now suppresses TypeScript/JavaScript findings when framework detection is `unknown` and endpoint evidence is weak (non-route-like path metadata). MAZ also applies the existing public endpoint allowlist to route paths (for example `/oauth/callback`) and not only to function names.
- Trigger: `drift analyze` on TS/JS repositories with utility calls that resemble HTTP verbs (`get`, `post`) but are not router declarations.
- Impact: Medium-positive. Reduces high-volume false positives and improves MAZ trust/actionability in TS-heavy repos.
- Mitigation:
  - Added strong-evidence gate for unknown-framework TS/JS patterns (`route` must look like HTTP path).
  - Added route-path allowlist check in MAZ pattern evaluation.
  - Added regression tests for suppression and retained true-positive behavior under unknown framework.
- Residual risk: Low to Medium. Some true endpoints with dynamic/non-literal route definitions may now be missed when framework detection remains unknown.

## 2026-06-15 — Phase 4: Complex Signal Ports (HSC/CXS/ISD/MAZ for TypeScript)

- Risk ID: RISK-SIGNAL-2026-06-15-TS-PHASE4
- Component: `src/drift/signals/hardcoded_secret.py`, `src/drift/signals/cognitive_complexity.py`, `src/drift/signals/insecure_default.py`, `src/drift/signals/missing_authorization.py`, `src/drift/ingestion/ts_parser.py`
- Type: Signal coverage extension (4 complex signals ported to TypeScript)
- Description: Phase 4 extends HSC, CXS, ISD, and MAZ signals to analyze TypeScript/JavaScript files. HSC uses regex-based line scanning (`_analyze_typescript`), CXS uses tree-sitter-based cognitive complexity computation (`_ts_cognitive_complexity`), ISD uses regex-based CORS/TLS/cookie detection (`_analyze_typescript`), MAZ leverages existing ts_parser API endpoint fingerprints with new auth detection (`_has_auth_in_call_args`, `_has_auth_decorator_ts`). The ts_parser was enhanced with 30+ auth marker identifiers and `has_auth` in API_ENDPOINT fingerprint.
- Trigger: `drift analyze` on TypeScript/JavaScript repositories now reports findings for HSC, CXS, ISD, and MAZ signals.
- Impact: Medium-positive. Increases validated TS signal coverage from 17/24 to 21/24, covering the most critical security-relevant signals (hardcoded secrets, insecure defaults, missing authorization) in TypeScript.
- Mitigation:
  - 9 new ground-truth fixtures (HSC TP/TN, CXS TP/TN, ISD TP/TP/TN, MAZ TP/TN) in precision/recall suite.
  - 196/196 precision/recall tests pass.
  - All Python suppression heuristics (entropy, placeholders, URLs, file paths, ML tokenizers) reused in HSC TS path.
  - CXS tree-sitter nesting model uses explicit `_TS_NESTING_TYPES` — no JSX false positives.
  - ISD cookie detection requires context keyword on same line.
  - MAZ auth detection covers Express middleware args, NestJS decorators, and 30+ common auth identifiers.
  - Mypy clean, ruff clean, 4146 tests pass.
- Residual risk: Low-Medium. Main gaps: (1) HSC template literals not covered by regex, (2) ISD dynamic CORS configs not detectable, (3) MAZ custom NestJS guard names may be missed. All documented as accepted risks in FMEA.

## 2026-04-11 - Issue #212: HSC FP-Reduktion (Env-Name-/Marker-Konstanten)

- Risk ID: RISK-SIGNAL-2026-04-11-212
- Component: `src/drift/signals/hardcoded_secret.py`, `tests/test_hardcoded_secret.py`, `tests/test_hsc_helpers_coverage.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: Hardcoded Secret (HSC) unterdrueckt jetzt zwei dominante FP-Klassen: (1) Env-Var-Namenskonstanten wie `AWS_SECRET_KEY_ENV = "AWS_SECRET_ACCESS_KEY"` und (2) Marker/Sentinel-Konstanten mit Suffixen wie `MARKER`, `PREFIX`, `ALPHABET`, `MESSAGE`, `ERROR_CODE`.
- Trigger: `drift analyze` auf Repositories mit TypeScript/Python-Konstantenmodulen, die env var names oder Marker-Literale als Stringwerte halten.
- Impact: Medium-positive. Deutlich weniger HSC-Triage-Rauschen, bessere Actionability und hoehere Signal-Glaubwuerdigkeit.
- Mitigation:
  - Neue Helper `_is_env_var_name_literal()` und `_is_marker_constant_name()` im HSC-Signal.
  - Suppression bleibt hinter der Known-Prefix-Detektion, damit echte Prefix-Secrets weiterhin gemeldet werden.
  - Regressionen fuer TN-Faelle (env-name/marker) und Guard-Tests fuer TP-Erhalt (known prefix) hinzugefuegt.
- Residual risk: Low. Restrisiko liegt in edge-case Namensmustern; durch Reihenfolge (prefix zuerst) und Guard-Regressionen begrenzt.

## 2026-04-11 - Issue #211: TSB test/spec path exclusion

- Risk ID: RISK-SIGNAL-2026-04-11-211
- Component: `src/drift/signals/type_safety_bypass.py`, `tests/test_type_safety_bypass.py`
- Type: Signal precision hardening (false-positive reduction)
- Description: Type Safety Bypass now skips known test/spec and mock contexts (`*.test.ts`, `*.spec.ts`, `*.test.tsx`, `*.spec.tsx`, `__tests__/`, `__mocks__/`) to prevent test scaffolding from being triaged as production drift.
- Trigger: `drift analyze` on TypeScript-heavy repositories with test mocks and double-casts in test code.
- Impact: Medium-positive. Reduces dominant TSB false positives and improves actionability.
- Mitigation:
  - Added explicit TSB path classifier for test/spec/mock patterns.
  - Added parametrized regression test covering all intended skip patterns.
  - Kept matcher narrow to avoid suppressing production findings.
- Residual risk: Low. Main residual risk is edge-case naming collisions; bounded by explicit suffix/dir checks and regression coverage.

## 2026-04-11 - ADR-055: Dependency-aware Signal Cache Keying

- Risk ID: RISK-PIPELINE-2026-04-11-055
- Component: `src/drift/signals/base.py`, `src/drift/cache.py`, `src/drift/pipeline.py`, `src/drift/config.py`
- Type: Signal execution + cache invalidation strategy change (feature-flagged)
- Description: Introduces dependency-aware signal cache keying with explicit scopes (`file_local`, `module_wide`, `repo_wide`, `git_dependent`) and selective cache invalidation.
- Trigger: `drift analyze` runs with `signal_cache_dependency_scopes_enabled: true`.
- Impact: Medium-positive for performance. Main risk is stale reuse if scope-key mapping is incorrect.
- Mitigation:
  - Feature flag defaults to `false` for safe rollout.
  - Conservative fallback to `repo_wide` for unknown scopes.
  - Cache schema version bump invalidates incompatible legacy entries.
  - Regression tests for file-local selective invalidation and git-state fingerprint changes.
- Residual risk: Low. Behavior is gated, deterministic, and covered by targeted tests.

## 2026-04-11 - ADR-054: File-Discovery Manifest Cache (Hybrid Invalidation)

- Risk ID: RISK-INGESTION-2026-04-11-054
- Component: `src/drift/ingestion/file_discovery.py`
- Type: Input/output path extension (repository-local cache manifest)
- Description: Discovery introduces a persistent manifest in `.drift-cache/file_discovery_manifest.json` with cache key + invalidator metadata (`git_head` primary, `mtime` fallback) and serialized file descriptors.
- Trigger: Repeated `drift analyze` / API calls that perform file discovery.
- Impact: Low to Medium. Incorrect cache reuse could serve stale file lists and mask newly added/removed files until invalidation.
- Mitigation:
  - Deterministic cache key includes repo path, include/exclude, `max_files`, TS toggle, supported languages, and schema version.
  - Hybrid invalidation: HEAD-based invalidation for git repos, mtime fingerprint fallback for non-git environments.
  - Manifest read is defensive (version/type checks); malformed manifests degrade safely to full re-scan.
  - Atomic manifest writes and bounded cache entry count reduce corruption/bloat risk.
  - Regression tests added for cache hit, HEAD invalidation, fallback invalidation, and corrupt-manifest recovery.
- Residual risk: Low. Main residual risk is conservative false cache misses (extra scans), not silent wrong findings.

## 2026-06-15 — Phase 3: TypeScript Verständlichkeit & Einführbarkeit

- Risk ID: RISK-OUTPUT-2026-06-15-TS-PHASE3
- Component: `src/drift/models.py`, `src/drift/output/json_output.py`, `src/drift/output/rich_output.py`, `src/drift/ingestion/file_discovery.py`, `src/drift/config.py`
- Type: Output enrichment + configuration extension (TypeScript visibility)
- Description: Phase 3 adds four capabilities: (1) `language` field on Finding model with auto-inference from file extension, (2) Rich console warning when TS files are skipped due to missing tree-sitter, (3) `tmp_ts_repo` conftest fixture for TypeScript-centric tests, (4) `LanguagesConfig` sub-model allowing `languages.typescript: false` in drift.yaml.
- Trigger: Any `drift analyze` run that encounters TypeScript files without tree-sitter installed, or any output consumption (JSON, SARIF, Rich).
- Impact: Low — all changes are additive, backward-compatible, and default-preserving. `language` field defaults to `None` (auto-inferred from extension). `languages.typescript` defaults to `true`. Warning panel only appears when `skipped_languages` is non-empty.
- Mitigation:
  - `language` field uses hardcoded `_LANG_MAP` ClassVar — no user input, no injection risk.
  - `LanguagesConfig` is Pydantic-validated with `extra="forbid"`.
  - Rich warning uses `Text.assemble()` — no markup injection.
  - JSON/SARIF schema updated with nullable `language` enum.
  - 1600 tests pass; no regressions.
- Residual risk: Minimal. `language` field is informational only — no scoring, filtering, or routing depends on it yet.

## 2026-04-11 - Phase 2 TS Parity: BEM/EDS/MDS/PFS validated for TypeScript

- Risk ID: RISK-SIGNAL-2026-04-11-TS-PHASE2
- Component: `tests/fixtures/ground_truth.py`, `scripts/_mutation_benchmark.py`, `docs/language-support-matrix.md`
- Type: Signal coverage extension (TypeScript language validation for 4 additional signals)
- Description: BEM, EDS, MDS, and PFS were already language-neutral in implementation but lacked TypeScript ground-truth fixtures and mutation benchmarks. Phase 2 added 8 TS fixtures (TP+TN per signal) and 10 TS mutation scenarios to the benchmark, raising validated TS signal count from 13/24 to 17/24.
- Trigger: `drift analyze` on TypeScript repositories now reports findings for BEM, EDS, MDS, and PFS signals.
- Impact: Medium-positive. Increases TS signal coverage from 54% to 71% and provides precision/recall evidence.
- Mitigation:
  - 8 ground-truth fixtures (BEM TP/TN, EDS TP/TN, MDS TP/TN, PFS TP/TN) in precision/recall suite.
  - 10 TS mutation scenarios in mutation benchmark (BEM, EDS, MDS, PFS, NBV, GCD, TSB).
  - All 187 precision/recall tests pass; mutation benchmark overall recall 96.9%.
- Residual risk: Low. No signal logic was changed; only validation artifacts added. TS FP rates on real-world repos not yet measured beyond oracle repo set.

## 2026-04-11 - Issue #210: NBV TS/JS ensure_* upsert false positives

- Risk ID: RISK-SIGNAL-2026-04-11-210
- Component: `src/drift/signals/naming_contract_violation.py`, `tests/test_naming_contract_violation.py`, `tests/fixtures/ground_truth.py`
- Type: Signal behavior change (language-aware NBV ensure_* contract)
- Description: NBV no longer enforces Python-only `ensure_* -> raise` semantics for TypeScript/JavaScript. For TS/JS, `ensure_*` now passes when the function has either a `throw` path or a value-returning `return` path (upsert/get-or-create semantics).
- Trigger: `drift analyze` on TS/JS repos with helper functions such as `ensureRecord(...)` that create and return guaranteed objects.
- Impact: Medium-positive. Reduces a major NBV false-positive class in TS/JS repositories and improves actionability.
- Mitigation:
  - Added TS/JS-specific ensure checker in NBV signal (`throw` OR value-returning `return`).
  - Added TS regression tests for upsert TN and bare-return TP behavior.
  - Added ground-truth TN fixture `nbv_ts_ensure_upsert_tn` to precision/recall suite.
- Residual risk: Low. Relaxation is constrained to TS/JS and still flags `ensure_*` functions without throw and without value-returning contract.

## 2026-04-11 - Issue #209: NBV TypeScript async bool-wrapper false positives

- Risk ID: RISK-SIGNAL-2026-04-11-209
- Component: `src/drift/signals/naming_contract_violation.py`, `tests/test_naming_contract_violation.py`, `tests/test_nbv_helpers_coverage.py`, `tests/fixtures/ground_truth.py`
- Type: Signal behavior change (NBV bool-return contract hardening)
- Description: NBV now treats TypeScript async wrappers `Promise<boolean>`, `PromiseLike<boolean>`, and `Observable<boolean>` as bool-compatible for `is_*/has_*` naming contracts. This directly addresses large-scale false positives reported in Issue 209.
- Trigger: `drift analyze` on TypeScript repositories containing async bool-returning `is_*`/`has_*` functions.
- Impact: Medium-positive. Reduces FP pressure and improves trust for NBV on TS-heavy repos.
- Mitigation:
  - New helper `_is_bool_like_return_type()` with strict terminal bool matching.
  - Reused in both Python and TypeScript NBV bool-check path to keep behavior consistent.
  - Regression tests added for `Promise<boolean>`, `PromiseLike<boolean>`, `Observable<boolean>`, nested wrappers, and negative control (`Promise<string>`).
  - New ground-truth TN fixture `nbv_ts_async_bool_tn` added to precision/recall suite.
- Residual risk: Low. Over-acceptance risk is bounded by strict terminal-type checks and explicit negative controls.

## 2026-04-13 - ADR-047 through ADR-051: Actionability Hardening (MAZ, EDS, PFS, AVS, CCC)

- Risk ID: RISK-SIGNAL-2026-04-13-047-051
- Component: `src/drift/signals/missing_authorization.py`, `src/drift/signals/explainability_deficit.py`, `src/drift/signals/pattern_fragmentation.py`, `src/drift/signals/architecture_violation.py`, `src/drift/signals/co_change_coupling.py`, `src/drift/output/rich_output.py`
- Type: Signal behavior change (scoring + filtering + metadata + output)
- Description: Five targeted signal changes to improve actionability of findings and a Rich output
  security-findings panel rendered before the main findings table.
  - **MAZ (ADR-047):** Score raised from 0.7 to 0.85, severity from HIGH to CRITICAL for unauthorized endpoints. Fix text adds A2A agent card exemption note. Security signals (MAZ, HSC, ISD) now get a dedicated `_render_security_section()` banner at the top of `render_findings()`.
  - **EDS (ADR-048):** Private function minimum threshold raised from 0.30 to 0.45. Defect-correlated files override threshold downward to 0.30. FileHistory lookup moved before threshold guard.
  - **PFS (ADR-049):** New `_extract_canonical_snippet()` reads source lines for canonical exemplar. Canonical ratio severity downgrade: < 10% canonical instances lowers HIGH→MEDIUM or MEDIUM→LOW; < 15% lowers HIGH→MEDIUM. `canonical_snippet` and `canonical_ratio` added to Finding metadata.
  - **AVS (ADR-050):** `_check_blast_radius()` gains `file_histories` parameter. Stable modules with `change_frequency_30d <= 1.0` AND `blast_radius <= 50` are skipped (churn guard). `churn_per_week` added to Finding metadata.
  - **CCC (ADR-051):** `pair_commit_messages` accumulates truncated (60 chars) commit message strings alongside commit hashes. Finding `fix` text includes intentional-vs-accidental branch with test scaffold template. `commit_messages` added to Finding metadata.
- Trigger: Any `drift analyze` run that produces MAZ/EDS/PFS/AVS/CCC findings.
- Impact: Medium. Score and severity changes affect prioritization outputs (JSON, SARIF, CI gates). Threshold changes affect recall — EDS may produce fewer FPs for private helpers; AVS may produce fewer stable-module FPs. New metadata keys added to JSON output.
- FP Risk: Lower — EDS private-helper filter and AVS churn gate both reduce FPs.
- FN Risk: Low — MAZ CRITICAL bump guards security findings from being buried; EDS defect-correlation override prevents suppressing risky helpers.
- Mitigation:
  - Threshold changes tuned against existing ground-truth fixtures (no reported regressions).
  - `_extract_canonical_snippet()` uses try/except with `OSError`+`IndexError` — any read failure yields empty string (no finding suppression).
  - Rich `_render_security_section()` is additive output only — no scoring change.
  - AVS churn guard uses dual condition (`<= 1.0/week AND <= 50`): avoids suppressing truly high-coupling modules with low activity.
  - All changes covered by existing test suite (1179 passing tests).
- Residual risk: Low. All changes are deterministic, purely in-process, and well-guarded by the pre-push gate and CI.

## 2026-04-12 - ADR-053: External Report Import (drift import)

- Risk ID: RISK-INPUT-2026-04-12-053
- Component: `src/drift/ingestion/external_report.py` (new), `src/drift/commands/import_cmd.py` (new), `src/drift/cli.py`
- Type: New input path (external JSON files) + new CLI command (additive)
- Description: `drift import <report> --format sonarqube|pylint|codeclimate` reads a user-supplied JSON report file, parses it through format-specific adapters, and displays a side-by-side comparison with Drift's own analysis. Imported findings have `score=0.0` and are never fed into scoring. Three adapter functions use `dict.get()` with defaults — no dynamic dispatch, no `eval`, no shell interaction.
- Trigger: User runs `drift import report.json --format sonarqube`.
- Impact: Low. Malformed JSON is handled by stdlib `json.loads()` raising `JSONDecodeError` (caught and surfaced as `ClickException`). Unexpected keys are ignored via `.get()` defaults. No imported data persists beyond the command's lifetime.
- Mitigation:
  - JSON parsing uses stdlib `json.loads()` only — no `yaml.load()`, no `pickle`, no `eval`.
  - Adapter functions extract only expected fields with `.get()` defaults — unknown keys silently ignored.
  - Imported `Finding` objects always have `score=0.0` — no scoring contamination.
  - File reads use `encoding="utf-8"` explicitly.
  - All adapters and CLI covered by 15 dedicated tests (`tests/test_import_command.py`).
  - `ValueError` for unsupported format raised before any file I/O.
- Residual risk: Minimal. Memory consumption on very large JSON files is bounded by Python stdlib limits. No external network calls, no file writes, no dynamic code execution.

## 2026-04-11 - ADR-052: PR-Comment Output + SARIF Enrichment + Markdown Compact + CSV signal_label

- Risk ID: RISK-OUTPUT-2026-04-11-052
- Component: `src/drift/output/pr_comment.py` (new), `src/drift/output/json_output.py`, `src/drift/output/markdown_report.py`, `src/drift/output/csv_output.py`, `src/drift/commands/analyze.py`
- Type: Output path extension (additive + one breaking column change)
- Description: Four output-layer changes — new `--format pr-comment` formatter; SARIF `message.text` appended with `generate_recommendation()` title (capped at 400 chars) and rule `help` field added; `analysis_to_markdown()` extended with `include_modules` / `include_signal_coverage` flags wired to `--compact`; CSV gains `signal_label` column (breaking: column indices shift by 1). No signal/scoring/ingestion changes.
- Trigger: User runs `drift analyze --format pr-comment|sarif|markdown|csv`.
- Impact: Low. CSV breaking change may affect existing automation pipelines reading CSV by column index. SARIF `message.text` length cap (400 chars) may truncate very long recommendations. No trust boundary crossed.
- Mitigation:
  - CSV breaking change documented in CHANGELOG as `BREAKING CHANGE`.
  - SARIF text cap set conservatively at 400 chars — GitHub UI renders first ~300 chars.
  - `generate_recommendation()` calls wrapped in `try/except` — missing recommender silently falls back to existing behavior.
  - `get_meta()` calls wrapped in `try/except` — unknown signal_type falls back to raw signal_type string.
  - All changes covered by dedicated tests (`test_pr_comment.py`, +2 in `test_json_output.py`, updated `test_csv_output.py`).
- Residual risk: Minimal. All new paths are pure in-process output composition with no I/O or external calls.


- Risk ID: RISK-OUTPUT-2026-04-11-S1S5
- Component: `src/drift/output/junit_output.py`, `src/drift/output/llm_output.py`, `src/drift/commands/ci.py`, `src/drift/commands/completions.py`, `src/drift/ci_detect.py`
- Type: Output path extension + new commands (additive, non-breaking)
- Description: Five DX features adding shell completions, JUnit XML and LLM text output formats, a zero-config CI command with auto-environment detection, and a `gate` alias for `check`. No signal, scoring, or ingestion changes. All outputs consume existing `RepoAnalysis` data.
- Trigger: User runs `drift completions <shell>`, `drift analyze --format junit|llm`, `drift ci`, or `drift gate`.
- Impact: Low. JUnit XML malformation could break CI parsers; LLM output changes could affect agent workflows; CI auto-detection could select wrong diff-ref on unsupported providers. No trust boundary crossed.
- Mitigation:
  - JUnit uses `xml.etree.ElementTree` for proper XML escaping and structure.
  - LLM output is pure text composition with no markup or escape codes.
  - CI detection has explicit provider cascade with generic fallback.
  - All features have dedicated test suites (24 tests total).
  - `drift gate` is an exact alias — no code duplication.
- Residual risk: Minimal. Additive output paths, no new dependencies, well-tested formatters.

## 2026-04-11 - ADR-046: Markdown CLI format + Guidance footer

- Risk ID: RISK-OUTPUT-2026-04-11-046
- Component: `src/drift/commands/analyze.py`, `src/drift/output/rich_output.py`
- Type: Output path extension (additive, non-breaking)
- Description: `drift analyze --format markdown` is now wired to the existing `analysis_to_markdown()` formatter. Additionally, `render_full_report()` appends a "What's Next?" guidance footer when no `drift.yaml` exists in the analyzed repo. No scoring, finding-generation, or signal changes. Both are additive surfaces reusing existing infrastructure.
- Trigger: User runs `drift analyze --format markdown` or views rich output in an unconfigured repo.
- Impact: Low. Misrendered markdown output could confuse PR comments; the guidance footer could show for configured repos if detection logic drifts. No trust boundary crossed.
- Mitigation:
  - Markdown formatter was already complete and tested indirectly via `drift brief` and copilot-context.
  - Guidance footer detection uses same config-presence check as existing first-run logic.
  - CLI integration test + guidance footer tests added in `tests/test_preflight_and_report.py`.
  - `--quiet` mode and non-rich formats are unaffected.
- Residual risk: Minimal. Additive output path, no new dependencies, well-tested formatter.

## 2026-04-11 - ADR-041: PHR Runtime Import Attribute Validation

- Risk ID: RISK-SIGNAL-2026-04-11-041
- Component: `src/drift/signals/phantom_reference.py`, `src/drift/config.py`
- Type: Signal enhancement (opt-in, non-breaking)
- Description: PHR gains optional runtime attribute validation. When `phr_runtime_validation: true`, `importlib.import_module()` is called on third-party modules to verify `hasattr(mod, name)` for `from X import Y` patterns. This crosses a new trust boundary (analysis process → third-party package code) but is gated behind an explicit opt-in flag.
- Trigger: User sets `thresholds.phr_runtime_validation: true` in `drift.yaml` and runs analysis on a project with third-party imports.
- Impact: Medium. Module import executes third-party `__init__.py` code; malicious or buggy packages could cause side effects. Timeout prevents hangs. Disabled by default.
- Mitigation:
  - Opt-in only (`phr_runtime_validation: false` default)
  - Daemon thread with 5s timeout prevents blocking
  - `sys.modules` fast path avoids re-import of cached modules
  - Skips project-internal modules, TYPE_CHECKING imports, and try/except-guarded imports
  - No `exec`/`eval`/`compile` in drift code path
  - Ground-truth fixtures: `phr_runtime_missing_attr_tp`, `phr_runtime_valid_attr_tn`, `phr_runtime_guarded_tn`
  - Precision/recall: 25/25 PHR fixtures passing, 169/169 total fixtures green
- Residual risk: Low. Primary residual risk is version-mismatch false positives (module installed but different version). Bounded by metadata and opt-in gating.

## 2026-04-10 - Output channel extension: session report + TUI visualize

- Risk ID: RISK-OUTPUT-2026-04-10-SESSION-TUI
- Component: `src/drift/commands/session_report.py`, `src/drift/output/session_renderer.py`, `src/drift/commands/visualize.py`, `src/drift/output/tui_renderer.py`, `src/drift/cli.py`
- Type: Output path extension (additive, optional)
- Description: New CLI output surfaces add session-effectiveness rendering (`drift session-report`) and an optional interactive Textual dashboard (`drift visualize`). The underlying analysis engine is unchanged, but user-facing output paths and rendering logic are expanded.
- Trigger: Running `drift session-report` with session files or invoking `drift visualize` with the optional `tui` dependency.
- Impact: Low to Medium. Misrendered or misleading presentation can reduce actionability even when findings remain correct.
- Mitigation:
  - `drift visualize` is dependency-gated and exits explicitly when `textual` is unavailable.
  - Additive output path only; no scoring or finding-generation logic changed.
  - Dedicated command/output tests added (`tests/test_session_report.py`, `tests/test_visualize.py`, renderer-focused coverage tests).
  - Golden-snapshot stability hardened for Windows/xdist to reduce CI flakiness in output validation.
- Residual risk: Low. Primary residual risk is UX-level misinterpretation in new renderers, bounded by dedicated tests and non-invasive integration.

## 2026-04-10 - ADR-043: Shared First-Run Summary Contract

- Risk ID: RISK-OUTPUT-2026-04-10-043
- Component: `src/drift/finding_rendering.py`, `src/drift/output/json_output.py`, `src/drift/output/rich_output.py`, `src/drift/commands/analyze.py`, `src/drift/commands/status.py`
- Type: Output contract extension (additive, non-breaking)
- Description: `drift analyze` and `drift status` now share one deterministic first-run prioritization path. JSON output gains a top-level `first_run` block, Rich output gains a `Start Here` / `Starte hier` panel, and status JSON adds `why_this_matters` plus `next_step`. This improves first-run clarity but creates a risk that command surfaces drift apart again if one path is changed without the shared helper.
- Trigger: `drift analyze` Rich/JSON output or `drift status --json` after future output-only changes that bypass the shared helper.
- Impact: Low to Medium. Incorrect or divergent first-step guidance can mis-prioritize remediation work even when the underlying findings remain correct.
- Mitigation:
  - Shared helper functions `select_priority_findings()` and `build_first_run_summary()` centralize ranking and summary text.
  - Additive contract only; existing `fix_first`, findings, and status fields remain intact.
  - Regression coverage added in `tests/test_guided_mode.py`, `tests/test_json_output.py`, and `tests/test_output_golden.py`.
  - ADR-043 updated so future output work is expected to preserve the shared contract.
  - Verification commands:
    - `pytest tests/test_guided_mode.py tests/test_json_output.py tests/test_output_golden.py -q --maxfail=1`
    - `drift analyze --repo . --format json --exit-zero`
- Residual risk: Low. Main residual risk is future maintenance drift between user-facing surfaces, bounded by the shared helper and regression tests.

## 2026-04-10 - ADR-040: PHR Third-Party Import Resolver

- Risk ID: RISK-PHR-IMPORT-RESOLVER-2026-04-10-040
- Component: `src/drift/signals/phantom_reference.py` (`_check_third_party_imports`, `_is_in_try_except_import_error`, `_collect_type_checking_import_ids`)
- Type: Signal heuristic extension (new detection capability for third-party imports)
- Description: PHR now validates third-party `import X` / `from X import Y` statements using `importlib.util.find_spec()`. If the root module is not found in the current Python environment, it is flagged as a phantom import. This extends PHR's recall to cover AI-hallucinated third-party packages. The check is safe (no code execution — only path traversal on sys.path).
- Severity: Low
- Likelihood: Low to Medium (environment-dependent FP for packages not installed locally)
- Mitigation:
  - Stdlib modules excluded via `sys.stdlib_module_names`
  - Project-internal modules excluded (already checked by existing import-from logic)
  - try/except ImportError and ModuleNotFoundError blocks detected and skipped
  - TYPE_CHECKING blocks detected and skipped via pre-pass
  - 5 new ground-truth fixtures: 1 TP (missing package), 4 TN (optional dep, stdlib, TYPE_CHECKING, ModuleNotFoundError)
  - 1 existing fixture updated (flask decorator: added flask stub to fixture project files)
  - Precision/recall validated: 166/166 fixtures pass (22 PHR-specific)
  - `find_spec()` is safe: no side effects, no code execution, no imports triggered
- Residual Risk: FP when package is in CI but not local venv (bounded by metadata hint)
- Status: Open (bounded)

## 2026-06-14 - ADR-039: Activate MAZ/PHR/HSC/ISD/FOE for Scoring

- Risk ID: RISK-SIGNAL-ACTIVATION-2026-06-14-039
- Component: `src/drift/config.py` (SignalWeights), `tests/fixtures/ground_truth.py`
- Type: Signal behavior change (report-only → scoring-active for 5 signals)
- Description: Five previously report-only signals are promoted to scoring-active with conservative weights: MAZ=0.02, PHR=0.02, HSC=0.01, ISD=0.01, FOE=0.005. This adds +0.065 to the total signal weight budget (~6.5% of composite score). Finding detection logic is unchanged — only the weight (and therefore score impact) changes from 0.0 to non-zero.
- Severity: Low to Medium
- Likelihood: Low (all signals were already emitting findings in report-only mode; only score contribution changes)
- Mitigation:
  - Conservative weights chosen based on signal maturity and existing precision data
  - All 5 signals have ground-truth fixture coverage (ISD: 5 new, MAZ: 1 TN, HSC: 6, FOE: 3, PHR: 17)
  - Precision/recall validated via `test_precision_recall.py` — all fixtures pass
  - Existing FP-reduction mechanisms (CLI-path fence, drift:ignore-security, barrel-file detection, env-template suppression) remain active
  - Score comparability: baseline diff via `drift_diff` recommended after activation
  - Weights are configurable via `drift.yaml` — users can revert individual signals to 0.0
- Residual risk: Low. Primary residual risk is minor score inflation for repositories that trigger multiple newly-scoring signals simultaneously. Conservative weights and per-signal configurability bound the impact. No detection logic changes means no new FP/FN modes beyond those already documented.

## 2026-06-01 - ADR-042: Schema Evolution and Finding-ID Promotion

- Risk ID: RISK-OUTPUT-2026-06-01-042
- Component: `src/drift/output/json_output.py`, `src/drift/api_helpers.py`, `src/drift/api/explain.py`, `src/drift/models.py`, `src/drift/mcp_server.py`
- Type: Output schema version bump (additive, minor) + new output field + explain input extension
- Description: Schema version unified from split "1.1" (CLI) / "2.0" (API) to "2.1". All output channels (JSON, SARIF, API) gain a `finding_id` field (16-char SHA256 fingerprint). `drift explain` and MCP `drift_explain` now accept finding fingerprints for finding-level drill-down, triggering a full analysis scan.
- Severity: Low
- Likelihood: Low (additive changes only; no fields removed or renamed)
- Mitigation:
  - Schema version bump follows established minor-version convention (additive fields only)
  - `finding_id` is deterministic and content-based — no randomness or state dependency
  - Fingerprint-based explain reuses existing `analyze_repo()` pipeline with same security boundaries
  - Existing consumers of `schema_version` "1.1" or "2.0" may need test updates but face no runtime breakage (new fields are ignored by lenient parsers)
  - `drift.output.schema.json` enables machine-verifiable contract validation
  - Regression tests updated for new schema version
- Residual risk: Low. Consumers with strict schema validation against "1.1" or "2.0" will reject "2.1" output until updated. This is intentional — the version bump signals the schema change. Fingerprint-based explain has the same performance cost as a normal scan.

## 2026-04-10 - TypeScript signal expansion and parser/output wiring hardening

- Risk ID: RISK-TS-SIGNALS-2026-04-10
- Component: `src/drift/signals/type_safety_bypass.py`, `src/drift/signals/naming_contract_violation.py`, `src/drift/signals/ts_architecture.py`, `src/drift/ingestion/ts_parser.py`, `src/drift/output/agent_tasks.py`, `src/drift/models.py`
- Type: New signal + signal behavior change + ingestion/output path adjustments
- Description: TypeScript analysis coverage was expanded with a dedicated type-safety-bypass detector and additional TS naming/architecture checks. Parser extraction and agent-task output shaping were adjusted to surface the new findings consistently.
- Severity: Medium
- Likelihood: Low to Medium
- Mitigation:
  - New focused TS fixture suites for export detection, naming consistency, React hooks, and type-safety bypass
  - Golden cache artifacts updated for deterministic corpus behavior
  - Pre-commit lint gate enforced and fixed for touched files
- Residual risk: Medium-Low. Main residual risk is precision drift in heterogeneous TS codebases with mixed naming conventions or intentional casts.

## 2026-04-13 - ADR-036/037/038: AVS/DIA/MDS FP-Reduction

- Risk ID: RISK-SIGNAL-2026-04-13-036-037-038
- Component: `src/drift/signals/architecture_violation.py`, `src/drift/signals/doc_impl_drift.py`, `src/drift/signals/mutant_duplicates.py`, `src/drift/config.py`
- Type: Signal behavior change (FP-reduction heuristics) + new config fields
- Description: Three signals receive precision hardening: AVS moves `models/` to Omnilayer and adds configurable `omnilayer_dirs`; DIA adds configurable `extra_auxiliary_dirs`; MDS adds name-token similarity, protocol-method skip, and thin-wrapper dampening. All changes aim to reduce false positives without degrading recall.
- Severity: Low to Medium
- Likelihood: Low (conservative defaults; all changes bounded by narrow heuristics)
- Mitigation:
  - AVS: `models` Omnilayer is reversible via config; current default covers >80% of observed repos
  - DIA: extra_auxiliary_dirs starts empty — no default behavior change
  - MDS: name component is only 10% weight; protocol set is narrow; thin-wrapper gate is LOC + Call-count
  - Ground-truth fixtures cover all new behaviors (6 TN fixtures)
  - Precision/recall baseline validated via `test_precision_recall.py`
- Residual risk: Low. Primary residual risk is MDS protocol-method FN in rare cases where protocol implementations contain genuinely duplicated non-trivial logic.

## 2026-04-12 - ADR-035: Per-Repository Signal Calibration

- Risk ID: RISK-SIGNAL-2026-04-12-035
- Component: `src/drift/calibration/`, `src/drift/signals/phantom_reference.py`, `src/drift/task_spec.py`, `src/drift/commands/calibrate.py`, `src/drift/commands/feedback.py`
- Type: Signal behavior adaptation (repo-scoped calibration) + new local input path (`data/negative-patterns/`)
- Description: Drift now applies repository-scoped precision hardening for selected signal patterns (initially PHR) using persisted calibration snapshots derived from user feedback and benchmark traces.
- Severity: Medium
- Likelihood: Low to Medium (calibration is bounded and confidence-weighted, but mis-calibration can suppress valid findings)
- Mitigation:
  - Calibration operates per repository fingerprint, not globally
  - Conservative default when calibration data is missing or stale
  - Signal-level guardrails cap score dampening and prevent full suppression from a single sample
  - Tests cover calibration loading, persistence, and PHR behavior under calibrated/un-calibrated paths
  - Audit/benchmark artifacts are updated alongside calibration changes (`docs/STUDY.md`, evidence JSON)
- Residual risk: Medium-Low. Main residual risk is repository-local false negatives if repeated incorrect feedback is provided; bounded dampening and fallback defaults reduce blast radius.

## 2026-04-12 - ADR-034: Causal Attribution via Git Blame

- Risk ID: RISK-INGESTION-2026-04-12-034
- Component: `src/drift/ingestion/git_blame.py`, `src/drift/attribution.py`, `src/drift/pipeline.py`
- Type: New subprocess input path (git blame) + additive output field (Finding.attribution)
- Description: Opt-in enrichment that invokes `git blame --porcelain` per analyzed file to attribute findings to commits, authors, and branches. Subprocess execution introduces a new trust boundary (drift ↔ git CLI). Author data from git history is surfaced in JSON/SARIF/Rich output.
- Severity: Low
- Likelihood: Low (opt-in, disabled by default; subprocess uses same git binary as existing git_history.py)
- Mitigation:
  - Feature disabled by default (`attribution.enabled: false`)
  - Per-file timeout (3s) prevents blame on slow/large files from blocking analysis
  - ThreadPoolExecutor capped at 4 workers; in-memory LRU cache (500 entries)
  - No `shell=True` in subprocess calls; arguments are explicit
  - File paths sourced from existing ingestion pipeline (already validated)
  - Branch hint extraction via deterministic regex on merge commit messages only
- Residual risk: Low. Author/email data in blame output could be spoofed in git history (inherent git limitation, not a drift-specific risk). Performance on very large repos with thousands of files may require increasing timeout or disabling attribution.

## 2026-04-09 - ADR-029: Preflight-Diagnose und Markdown-Report-Export

- Risk ID: RISK-OUTPUT-2026-04-09-029
- Component: `src/drift/preflight.py`, `src/drift/output/markdown_report.py`, `src/drift/finding_rendering.py`
- Type: Neuer Output-Pfad (additiv, non-breaking)
- Description: Die Analyseausgabe wird um einen strukturierten Preflight-Diagnosepfad und einen Markdown-Report erweitert. Ziel ist bessere Handlungsfaehigkeit fuer Review- und Agent-Workflows ohne Aenderung bestehender JSON-Schemas.
- Trigger: Aufrufe, die den neuen Markdown-/Preflight-Ausgabepfad aktivieren.
- Impact: Niedrig bis mittel. Falsche oder missverstaendliche Zusammenfassungen koennen die Priorisierung von Folgemaassnahmen beeinflussen, ohne den zugrunde liegenden Finding-Datensatz zu veraendern.
- Mitigation:
  - Additiver Kanal; bestehende JSON- und CLI-Standardausgaben bleiben erhalten
  - Deterministische Ableitung aus vorhandenen Findings und Metadaten
  - Testabdeckung fuer Rendering, Tool-Metadaten und semantische Advisory-Regeln
- Residual risk: Niedrig. Hauptrestrisiko liegt in Darstellungsinterpretation, nicht in der Kernanalyse oder Score-Berechnung.

## 2026-04-08 - ADR-027: Finding-Status fuer Suppression-Transparenz

- Risk ID: RISK-OUTPUT-2026-04-08-027
- Component: `src/drift/models.py`, `src/drift/suppression.py`, `src/drift/pipeline.py`, `src/drift/output/json_output.py`
- Type: Output schema extension + lifecycle transparency (additive, non-breaking)
- Description: Inline-Suppressions werden nicht mehr nur gezaehlt, sondern als expliziter Finding-Status (`suppressed`) modelliert und separat im JSON ausgegeben (`findings_suppressed`). Ziel ist die Trennung von real behobenen und nur unterdrueckten Findings.
- Trigger: `drift analyze`/`drift check` JSON-Ausgabe bei vorhandenen `drift:ignore` Kommentaren.
- Impact: Additiv. Bestehende `findings`-Consumer bleiben funktionsfaehig; neue Felder verbessern Audierbarkeit und reduzieren False-Negative-Wahrnehmung.
- Mitigation:
  - Statusfelder sind optional und additive (`schema_version` 1.1)
  - Primarliste `findings` bleibt unveraendert fuer Rueckwaertskompatibilitaet
  - Regressionstests fuer Suppression-Markierung und JSON-Serialisierung
- Residual risk: Niedrig. Consumer, die strikt auf exakte Payload-Groesse optimieren, sehen mehr Felder und sollten ggf. kompaktes Format verwenden.

## 2026-04-08 - ADR-026: A2A Agent Card and HTTP Serve Endpoint

- Risk ID: RISK-SERVE-2026-04-08-026a
- Component: `src/drift/serve/app.py`, `src/drift/serve/a2a_router.py`
- Type: New HTTP input/output path (network-accessible trust boundary)
- Description: `drift serve` exposes analysis capabilities over HTTP without authentication. Any client that can reach the bind address can invoke analysis on any local directory the OS user has read access to.
- Severity: Medium
- Likelihood: Low (default localhost-only; network exposure requires explicit `--host 0.0.0.0`)
- Mitigation:
  - Default bind to `127.0.0.1` — not reachable from network without explicit opt-in
  - Documentation warns about production exposure requiring reverse proxy with auth
  - No sensitive credentials stored or processed by the serve endpoint
- Residual risk: Low. Localhost-only default limits attack surface to local processes. Users deploying on `0.0.0.0` accept responsibility for network-level access control.

- Risk ID: RISK-SERVE-2026-04-08-026b
- Component: `src/drift/serve/a2a_router.py`
- Type: Input validation (path traversal prevention)
- Description: A2A JSON-RPC requests include a `path` parameter specifying which repository to analyze. Insufficient validation could allow path traversal to analyze or probe arbitrary filesystem directories.
- Severity: Medium
- Likelihood: Low (requires network access to the serve endpoint)
- Mitigation:
  - `_validate_repo_path()` normalizes via `os.path.realpath(os.path.normpath(path))`
  - Validates `os.path.isdir()` — rejects non-existent and non-directory paths
  - Resolved path is used for all downstream API calls (no raw user input forwarded)
  - ValueError raised with descriptive message on invalid paths
- Residual risk: Low. Validation prevents traversal; attacker can only analyze directories the OS user can read (same as running `drift` directly). Combined with localhost-only default, risk is very low.

## 2026-04-08 - Ingestion dedup + signal factory active_signals pass-through + git history cache

- Risk ID: RISK-INGESTION-2026-04-08-DEDUP
- Component: `src/drift/ingestion/file_discovery.py`, `src/drift/signals/base.py`, `src/drift/pipeline.py`
- Type: Ingestion correctness fix + signal factory optimization + performance cache
- Description: Three related changes applied together:
  1. **`file_discovery.py` (ingestion):** `include` patterns are now deduped via `dict.fromkeys` before glob iteration. Previously a file matching multiple patterns could be discovered and appended multiple times, producing duplicate `FileInfo` entries and inflated finding counts. Lazy `glob()` iterator replaces `list(glob())` to avoid materializing all matches at once; `relative_to()` result reused instead of called twice.
  2. **`signals/base.py` (signals):** `create_signals()` gains an `active_signals: set[str] | None` parameter so callers can pre-filter signals before instantiation. A `_SIGNAL_TYPE_VALUE_CACHE` avoids repeated probe-instantiation for the signal-type lookup on cached code paths.
  3. **`pipeline.py`:** `fetch_git_history()` adds a short-lived in-process LRU cache (TTL 120 s, max 16 entries, keyed by HEAD SHA + parameters) to avoid redundant `git log` parsing across rapid consecutive scans. `SignalPhase` passes `active_signals` to the factory directly with a backward-compatible fallback for custom `signal_factory` implementations.
- FP risk: Low. Dedup prevents double-processing; if a legitimate file happened to be discovered twice it was already a pre-existing FP source, not a TP. Active-signals pre-filtering uses same `signal_type.value` values that were already filtered downstream.
- FN risk: Low. Dedup cannot suppress files that match at least one pattern once. The cache is keyed on HEAD SHA + all analysis parameters; any repo or config change invalidates the cache entry.
- Mitigation:
  - New tests in `tests/test_pipeline_components.py` cover cache hit/miss and HEAD-change invalidation.
  - Full test suite passes; ruff + mypy clean.
- Residual risk: Very low. Cache is process-local and bounded; no persistent state. Dedup is idempotent. Backward-compat fallback ensures custom signal factories continue to work.

## 2026-04-11 - ADR-024: Machine-Readable Next-Step Contracts

- Risk ID: RISK-OUTPUT-2026-04-11-024
- Component: `src/drift/api.py`, `src/drift/api_helpers.py`, `src/drift/mcp_server.py`
- Type: Output schema extension (additive, non-breaking)
- Description: ADR-024 introduces machine-readable next-step contracts to reduce agent hallucinations in tool-call chains. Three fields added to every agent-oriented API response:
  - `next_tool_call`: `{tool: str, params: dict}` — primary recommended action. Null when no action needed.
  - `fallback_tool_call`: `{tool: str, params: dict}` — alternative if primary fails. Null when not applicable.
  - `done_when`: Predicate string describing the termination condition for the current workflow step.
  - MCP session enrichment injects `session_id` into contract params via `setdefault`.
  - `_error_response` gains optional `recovery_tool_call` for recoverable errors.
- Trigger: All API calls returning agent-oriented responses (scan detailed, diff, fix_plan, nudge, brief, negative_context), plus MCP session_start.
- Impact: Additive only — `schema_version` remains "2.0". Existing `agent_instruction` and `recommended_next_actions` fields preserved. No scoring, signal, or ingestion logic affected. Backward-compatible: consumers ignoring new fields are unaffected.
- Mitigation:
  - 9 new tests in `TestNextStepContract` class (tests/test_scan_diversity.py)
  - Contract shape validator `_assert_contract_shape()` enforces structural invariants
  - Full test suite passes (2147 passed); ruff + mypy clean
  - `done_when` is advisory text, not code — no injection or execution risk
  - `_tool_call()` helper centralizes descriptor construction
  - 8 `DONE_*` constants ensure predicate consistency across endpoints
- Residual risk: Very low. All contract content is deterministic, derived from existing response state. Agents may ignore contracts — no enforcement, no side effects if misinterpreted.

## 2026-04-08 - ADR-023: Canonical Examples in Agent-Output (fix_plan + brief)

- Risk ID: RISK-OUTPUT-2026-04-08-023
- Component: `src/drift/guardrails.py`, `src/drift/api_helpers.py`
- Type: Output schema extension (additive, non-breaking)
- Description: ADR-023 surfaces existing positive-reference data through two new additive fields:
  - `Guardrail.preferred_pattern`: Carries `NegativeContext.canonical_alternative` through to brief guardrails and prompt block (previously lost during NC→Guardrail transformation).
  - `canonical_refs` list in fix_plan task dicts: Extracts `canonical_exemplar` from Finding metadata (e.g. PFS file:line refs) and `canonical_alternative` from NegativeContext items. Capped at 3 refs per task.
  - `guardrails_to_prompt_block()`: Emits optional `PREFERRED:` line after each constraint when preferred_pattern is non-empty.
- Trigger: `brief()` and `fix_plan()` API calls; MCP `drift_brief` and `drift_fix_plan` tools (JSON passthrough).
- Impact: Additive only — `schema_version` remains "2.0". No existing fields changed. Empty defaults (`""` / `[]`) when source data unavailable. No scoring, signal, or ingestion logic affected.
- Mitigation:
  - 4 new tests in `tests/test_brief.py` (28 total in class)
  - 4 new tests in `tests/test_batch_metadata.py` (56 total)
  - Full test suite passes; ruff + mypy clean
  - canonical_refs capped at 3 per task (token budget)
  - preferred_pattern truncated to 200 chars (injection prevention)
- Residual risk: Very low. All new data is derived from existing analysis artifacts. Comment-prefix stripping is deterministic and bounded. No new computation paths or external data sources.

## 2026-04-09 - ADR-021: Batch-Dominant Fix-Loop Orchestration (Agent Instruction Alignment)

- Risk ID: RISK-OUTPUT-2026-04-09-021
- Component: `src/drift/api.py`, `src/drift/mcp_server.py`
- Type: Agent instruction text change (output channel, non-breaking)
- Description: ADR-021 resolves contradictory `agent_instruction` texts that caused agents to fall back to per-file verification even when batch capabilities (ADR-020) exist. Changes:
  - `_scan_agent_instruction()`: Threshold-based branching (>20 findings → batch-first guidance with max_tasks=20, ≤20 → nudge-based per-fix workflow)
  - `_fix_plan_agent_instruction()`: Non-batch path recommends nudge (not diff) for inner loop; batch path adds nudge guidance between edits
  - Diff `_agent_hint`: "improved" and "no change" cases now reference batch_eligible groups and nudge
  - Nudge `agent_instruction`: References new inner-loop/outer-loop model (nudge = inner, diff = outer)
  - MCP `_BASE_INSTRUCTIONS`: Removed "do not batch" from nudge tool description; added explicit FEEDBACK LOOP ROLES section; batch step 2 now mentions nudge between edits
- Trigger: All API endpoints that return `agent_instruction` fields
- Impact: Only plaintext `agent_instruction` strings changed — `schema_version` remains "2.0". No structural, scoring, or field-level changes.
- Mitigation:
  - 5 new tests in `tests/test_batch_metadata.py` (24 total)
  - Full test suite passes (2083 passed, 168 skipped)
  - ruff + mypy clean
  - Contradictions verified eliminated via grep (zero matches for "do not batch" in MCP, zero matches for "After each file change.*drift_diff" in api.py)
- Residual risk: Very low. Agent instruction texts are non-binding recommendations that guide but do not constrain agent behavior. No scoring, schema, or functional logic changed.

## 2026-04-08 - Agent Repair Workflow Quick Wins (V-3a/V-5/V-6/V-8a/V-13)

- Risk ID: RISK-OUTPUT-2026-04-08-021
- Component: `src/drift/api.py`, `src/drift/output/agent_tasks.py`, `src/drift/api_helpers.py`, `src/drift/models.py`, `src/drift/mcp_server.py`
- Type: Output schema extension + MCP tool parameter addition (additive, non-breaking)
- Description: Six Quick Win improvements for agent repair workflow effectiveness:
  - V-3c: Baseline-warming step added to Fix-Loop Protocol in MCP system prompt
  - V-5: `finding_count_by_signal` dict added to scan response (Counter over ALL findings pre-truncation)
  - V-6: `expected_score_delta` field added to AgentTask model, populated from `finding.score_contribution`, exposed in `_task_to_api_dict()`
  - V-8a: Negative context `max_items` increased from 3 to 5 for richer anti-pattern guidance
  - V-3a: `signals`/`exclude_signals` params added to `nudge()` and MCP `drift_nudge` — post-hoc result filtering (score unaffected)
  - V-13: `dependency_depth` metadata via BFS in `_compute_dependencies()` — depth 0 = no deps, depth N = max(dep depths)+1, -1 = cycle
- Trigger: scan, fix_plan, or nudge API calls
- Impact: Schema additive only — `schema_version` remains "2.0". No existing fields removed or renamed.
- Mitigation:
  - All new fields are optional/additive (backward-compatible)
  - 7 new tests added to `tests/test_batch_metadata.py` (19 total)
  - Full test suite passes (2085 passed, 168 skipped)
  - ruff + mypy clean
- Residual risk: Low. Nudge signal filtering is display-only — score/direction always reflect full analysis.

## 2026-04-07 - ADR-020: Agent Fix-Loop Batch Metadata (Output Schema Extension)

- Risk ID: RISK-OUTPUT-2026-04-07-020
- Component: `src/drift/output/agent_tasks.py`, `src/drift/api.py`, `src/drift/api_helpers.py`
- Type: Output schema extension (additive, non-breaking)
- Description: ADR-020 adds batch metadata fields to fix_plan and diff responses to reduce agent fix-loop latency. Changes include:
  - `_inject_batch_metadata()` in agent_tasks.py computes fix-template equivalence classes
  - `_task_to_api_dict()` exposes 4 new fields: `batch_eligible`, `pattern_instance_count`, `affected_files_for_pattern`, `fix_template_class`
  - `diff()` gains `signals`/`exclude_signals` params, `resolved_count_by_rule`, `suggested_next_batch_targets`
  - `fix_plan()` gains `remaining_by_signal`, context-dependent `agent_instruction`
  - `scan()` gains `total_finding_count`
- Trigger: Any fix_plan, diff, or scan API call
- Impact: Schema additive only — no existing fields removed or renamed. `schema_version` remains "2.0".
- Mitigation:
  - All new fields are optional/additive (backward-compatible)
  - 12 dedicated tests in `tests/test_batch_metadata.py`
  - Existing test suite (865+ tests) passes without modifications
- Residual risk: Low. `_UNIFORM_TEMPLATE_SIGNALS` set may need expansion as new signals are added.

## 2026-04-07 - PFS FTA v1: RETURN_PATTERN extraction (MCS-1 recall fix)

- Risk ID: RISK-SIG-2026-04-07-193
- Component: `src/drift/ingestion/ast_parser.py` (`_process_function`, `_fingerprint_return_strategy`)
- Type: Signal quality (FTA v1 — 1 SPOF, mitigated)
- Description: FTA on pfs_002 mutation identifies a single SPOF: no `PatternCategory.RETURN_PATTERN` enum value and no return-strategy extraction path in `_process_function()`. This causes PFS recall = 0.5 (pfs_002 undetected in mutation benchmark).
  - MCS-1 (SPOF, RPN 112→20): `PatternCategory.RETURN_PATTERN` added to enum; `_fingerprint_return_strategy()` classifies per-function return exits into strategy labels (`return_none`, `raise`, `return_tuple`, `return_dict`, `return_value`); emits `PatternInstance` when ≥2 distinct strategies found. **Mitigated.**
- Trigger: `drift analyze` on repo with module containing functions using divergent return conventions (None vs raise vs tuple).
- Impact: PFS recall drops to 0.5; return-strategy fragmentation invisible to users.
- Mitigation (implemented, 2026-04-07):
  - `PatternCategory.RETURN_PATTERN` enum value in `src/drift/models.py`
  - `_fingerprint_return_strategy()` in `src/drift/ingestion/ast_parser.py`
  - Extraction call in `_process_function()` after API endpoint block
  - Queue-based walk excludes nested function/class defs
- Verification:
  - `test_return_strategy_mutation_benchmark_scenario` — exact pfs_002 scenario
  - `test_return_strategy_multiple_strategies_detected` — basic extraction
  - `test_return_strategy_ignores_nested_functions` — nested-def isolation
  - `test_return_pattern_two_variants_detected` — PFS integration
  - `PFS_RETURN_PATTERN_TP` ground-truth fixture
- Residual risk: Low. FP risk for intentional return-overloading modules (get/get_or_raise patterns) — accepted as correct detection of diversity. Dynamic returns via callbacks remain FN (static analysis limitation).

## 2026-04-07 - SMS FTA v1: sms_001 Recall=0 (Benchmark-Fixture, 2 SPOFs, behoben)

- Risk ID: RISK-BENCH-2026-04-07-192
- Component: `scripts/_mutation_benchmark.py` (Benchmark-Fixture, kein Signal-Code)
- Type: Benchmark-Fixture-Defekt (FTA v1 — 2 SPOFs, beide behoben)
- Description: FTA auf `sms_001`-Mutation deckt zwei minimale Schnittmengen auf, die zusammen Recall=0 erklären:
  - MCS-1 (SPOF): Fixture injiziert ausschließlich stdlib-Imports (`ctypes`, `struct`, `mmap`, `ast`, `dis`, `multiprocessing`, `xml`). `_STDLIB_MODULES` filtert alle — kein Novel-Import → leere Findings-Liste. Das Signal funktioniert korrekt; der Fehler liegt in der falschen Fixture-Erwartung.
  - MCS-2 (SPOF): Alle Baseline-Dateien im Initial-Commit ohne explizites Datum → Timestamp „heute“ → `established_count = 0` von `len(parse_results) ≈ 25` → 10%-Guard feuert → `return []` vor jeder Analyse. Unabhängig von MCS-1, würde auch bei validen Third-Party-Imports feuern.
  - Common Cause: fehlende Datum-Spreizung im Corpus-Setup aktiviert beide Äste gleichzeitig.
- Trigger: `drift analyze --repo <tmp_repo> --format json --since 90` auf synthetischem Benchmark-Repo.
- Mitigation (implementiert, 2026-04-07):
  - MCS-1: `outlier_module.py` in separatem Recent-Commit mit `numpy`, `cffi`, `msgpack` überschrieben.
  - MCS-2: Initial-Commits auf Feb 2026 zurückdatiert via `GIT_AUTHOR_DATE`/`GIT_COMMITTER_DATE`.
- Verification:
  - Benchmark post-fix: `sms_001` detected = 1, recall = 100%, Gesamt-Recall 16/17 = 94%.
  - 2056/2056 Test-Suite grün.
  - `benchmark_results/mutation_benchmark.json` aktualisiert.
- Residual risk: Kein Restrisiko für diesen Defekt. Langfristig: Benchmark-Fixture-Validierungsprozess sollte sicherstellen, dass injizierte Imports gegen Signal-Filterlogik ge-cross-validated werden.

## 2026-04-07 - AVS FTA v1: co-change precision failure (3 primary MCS, 1 latent)

- Risk ID: RISK-SIG-2026-04-07-191
- Component: src/drift/signals/architecture_violation.py (`_check_co_change`)
- Type: Signal quality (FTA v1 — causal decomposition, 3 primary MCS, 1 latent MCS) — **MITIGATED**
- Description: FTA auf `avs_co_change`-Sub-Check deckt drei minimale Schnittmengen auf, die zusammen alle 10 Disputed-Fälle in der `drift_self`-Stichprobe erklären (precision_strict = 0.3, n=20, 2026-03-25):
  - MCS-1 (SPOF, RPN 144→24): Same-directory guard via `PurePosixPath.parent` comparison mit root-level Exception (`!= "."`) in `_check_co_change`. **Mitigated.**
  - MCS-2 (SPOF, RPN 60→10): `known` wird jetzt aus `filtered_prs` statt `parse_results` gebaut — konsistent mit Graph. **Mitigated.**
  - MCS-3 (RPN 120→30): `build_co_change_pairs` diskontiert Commits nach Dateizahl (`weight = 1.0 / max(1, len(files) - 1)`). Hard >20 cut bleibt als Belt-and-Suspenders. **Mitigated.**
  - MCS-4 (latent, RPN 48): `_DEFAULT_LAYERS` mappt `models` auf Layer 2 ohne Cross-Cutting-Ausnahme — potenziell irreführende `avs_upward_import`-Findings auf DTO-Pattern-Repos. **Unchanged — keine Evidenz.**
  - Common Causes: CC-1 (Filter-Inkonsistenz) behoben durch MCS-2 Fix; CC-2 (kein Namespace-Kontext) behoben durch MCS-1 Guard.
- Implementation: ADR-018 (proposed), 3 Code-Fixes, 4 Regressionstests (27/27 grün), 97/97 Precision-Recall grün.
- Regressionstests:
  - `test_co_change_same_directory_suppressed` (MCS-1)
  - `test_co_change_root_level_not_suppressed` (MCS-1 FN guard)
  - `test_co_change_test_source_pair_suppressed` (MCS-2)
  - `test_co_change_bulk_commits_discounted` (MCS-3)
- Residual risk: Niedrig. MCS-4 (latent, `models.py` Layer-Zuordnung) ohne Disputed-Evidenz bleibt unverändert. Bulk-Commit-Diskont-Kurve (`1/(n-1)`) kann nach breiterer Benchmark-Validierung kalibriert werden.

## 2026-04-07 - DIA FTA v2: deep false-positive reduction (6 minimal cut sets)

- Risk ID: RISK-SIG-2026-04-07-190
- Component: src/drift/signals/doc_impl_drift.py
- Type: Signal quality (FTA v2 — deep causal decomposition to 16 basis events, 6 MCS)
- Description: FTA v1 (3 cut sets) reduced DIA self-analysis from 10→9 FPs with precision 63%. FTA v2 performed proper NIST/NASA-grade decomposition, identifying 3 common causes (CC-1: flat regex `_PROSE_DIR_RE`, CC-2: missing undocumented-dir convention filter, CC-3: ADR `trust_codespans=True` bypass) and 6 minimal cut sets. Four targeted guards implemented:
  - P5 (MCS-4): Negative lookahead `(?!\w)` on `_PROSE_DIR_RE` — blocks `try/except`, `match/case`, `parent/tree`, multi-segment path decomposition, dotfile-path, and URL owner/repo extractions.
  - P3 (MCS-2): URL stripping via `_strip_urls()` before regex extraction — defense-in-depth against GitHub/registry URLs in plain text.
  - P6 (MCS-5): Dotfile prefix check `.{ref}` in `_ref_exists_in_repo()` — recognizes `.drift-cache` for ref `drift-cache`.
  - P1 (MCS-1): Auxiliary directory exclusion `_AUXILIARY_DIRS` frozenset — suppresses undocumented-dir findings for `tests/`, `scripts/`, `benchmarks/`, `docs/`, etc.
- Dead code removed: `_FALLBACK_DIR_RE` (defined but never referenced).
- Impact: DIA self-analysis findings 9→2 (−78%), ground truth auxiliary FPs eliminated.
- Verification:
  - 73/73 DIA unit tests green (15 new tests for P1/P3/P5/P6)
  - 97/97 precision/recall fixtures green
  - 2056/2056 full test suite green
  - Mutation benchmark DIA recall 3/3 = 100%
  - Self-analysis DIA: 2 remaining (1× ADR meta-doc `services/`, 1× non-standard `work_artifacts/`)
- Residual risk: Low. P5 negative lookahead only extracts terminal path segments (before whitespace/EOL), which may miss intermediate segments in rare prose. Acceptable because intermediate segments (e.g. `src` in `src/drift/`) are never the meaningful claim target.

## 2026-04-08 - DIA FTA v2 refinement: eliminate remaining 2 self-analysis FPs

- Risk ID: RISK-SIG-2026-04-08-191
- Component: src/drift/signals/doc_impl_drift.py, decisions/ADR-017-dia-false-positive-reduction.md
- Type: Signal quality (final FP elimination in self-analysis)
- Description: Two residual DIA FPs from FTA v2 remain on self-analysis:
  1. `services/` extracted from ADR-017 inline codespan (illustrative example, not architectural claim). Root cause: ADR scanning uses `trust_codespans=True`, which extracts example refs.
  2. `work_artifacts/` flagged as undocumented source dir (contains ad-hoc Python scripts, not a structured module). Root cause: not in `_AUXILIARY_DIRS`.
- Mitigation:
  - ADR-017: Illustrative directory references moved from inline codespans to fenced code block. DIA already correctly skips `block_code` tokens, so example refs are no longer extracted.
  - `_AUXILIARY_DIRS`: Extended with `artifacts` and `work_artifacts` entries to cover CI/build artifact and working directories — common conventions across projects.
- Impact: DIA self-analysis findings 2→0 (100% FP elimination on own repo).
- FN-risk: Negligible. Directories named `artifacts` or `work_artifacts` virtually never contain architecturally significant source modules. Fenced code block usage in ADRs for example paths is semantically correct and improves readability.
- Verification:
  - 76/76 DIA unit tests green (3 new regression tests)
  - 97/97 precision/recall fixtures green
  - 2056/2056 full test suite green
  - Self-analysis DIA: 0 findings

## 2026-04-07 - DIA false-positive reduction (FTA v1, 3 cut sets)

- Risk ID: RISK-SIG-2026-04-07-189
- Component: src/drift/signals/doc_impl_drift.py
- Type: Signal quality (false-positive reduction via FTA-driven precision hardening)
- Description: DIA signal emitted false positives through three independent failure paths identified via Fault Tree Analysis: (CS-1) inline codespan tokens were extracted without context validation, (CS-2) directory existence checks missed paths under common prefixes like `src/`, (CS-3) superseded/deprecated ADR documents were scanned as if active.
- Trigger examples:
  - README with `` `auth/callback` `` in prose → phantom-dir finding for `auth/` (CS-1).
  - Repo with `src/services/` + README mentioning `services/` → false FP (CS-2).
  - ADR with `status: superseded` referencing pre-refactoring path → stale finding (CS-3).
- Impact: Reduced DIA precision and triage trust, especially on repos with inline code examples and mature ADR processes.
- Mitigation:
  - CS-1: Sibling-context keyword gate — collect text-children from paragraph/heading, only trust codespans when structure keywords present in sibling context. Added "architecture" and "component"/"components" to keyword set. ADR files use `trust_codespans=True`.
  - CS-2: Container-prefix existence check via `_ref_exists_in_repo()` — checks direct path plus curated prefixes (`src`, `lib`, `app`, `pkg`, `packages`, `libs`, `internal`).
  - CS-3: ADR status parsing via `_extract_adr_status()` — YAML frontmatter + MADR freetext; skip `superseded`/`deprecated`/`rejected`.
  - 14 new regression tests covering all 3 cut sets + FN edge cases.
  - Golden snapshots updated (corpus findings count changed due to improved precision).
- Verification:
  - `python -m pytest tests/test_dia_enhanced.py -v --maxfail=1`
  - `python -m pytest tests/test_precision_recall.py -k dia -v --maxfail=1`
  - `python -m pytest tests/test_golden_snapshot.py -v`
- Residual risk: Low; conservative defaults limit FN surface. Codespan context gate may miss structure refs in keyword-free prose, but such cases are rare and rarely constitute genuine structure claims. Container-prefix set is curated and excludes test/docs dirs.

## 2026-04-07 - MAZ/ISD/HSC wave-2 calibration

- Risk ID: RISK-SIG-2026-04-07-188
- Component: src/drift/signals/missing_authorization.py, src/drift/signals/insecure_default.py, src/drift/signals/hardcoded_secret.py
- Type: Signal quality (edge-case precision/recall hardening)
- Description: Follow-up calibration addressed remaining edge-cases after ADR-015: MAZ auth-parameter matching was too narrow for composed/camelCase contexts, ISD ignore directive parsing was too permissive, and HSC missed wrapped known-prefix tokens.
- Trigger examples:
  - Decorator fallback endpoints with `currentUserContext` or `access_token` parameters.
  - Header comments like `drift:ignore-security-bypass` accidentally suppressing ISD.
  - Literals like `Bearer sk-...` in auth-header assignments.
- Impact: Prior behavior could reduce signal credibility via missed detections or unintended suppression.
- Mitigation:
  - MAZ: normalize parameter names and apply conservative auth-context regexes in fallback path.
  - ISD: accept only explicit `# drift:ignore-security` directive forms.
  - HSC: normalize common credential wrappers before known-prefix checks.
  - Add regressions in `tests/test_missing_authorization.py`, `tests/test_insecure_default.py`, `tests/test_hardcoded_secret.py`.
- Verification:
  - `python -m pytest tests/test_missing_authorization.py tests/test_insecure_default.py tests/test_hardcoded_secret.py -q --maxfail=1`
  - `python -m pytest tests/test_precision_recall.py::test_precision_recall_report -q -s`
- Residual risk: Medium-low; matcher scope is conservative but may require future tuning for uncommon naming conventions.

## 2026-04-06 - MAZ/ISD/HSC scoring-readiness calibration

- Risk ID: RISK-SIG-2026-04-06-187
- Component: src/drift/signals/missing_authorization.py, src/drift/signals/insecure_default.py, src/drift/signals/hardcoded_secret.py
- Type: Signal quality (precision/recall readiness for scoring promotion)
- Description: MAZ/ISD/HSC had quality gaps that reduced scoring-readiness credibility: MAZ fallback over-reported some auth-injected routes, ISD lacked local-dev severity context for localhost `verify=False`, and HSC under-reported known token prefixes in generic variable names.
- Trigger examples:
  - Decorated route handlers with injected auth context but no explicit auth decorator marker.
  - Localhost health calls using `verify=False` for local development.
  - Generic config names containing high-confidence API-token prefixes (`ghp_`, `sk-`, `AKIA`).
- Impact: Unbalanced precision/recall behavior in security findings, limiting confidence for future scoring-weight activation.
- Mitigation:
  - MAZ: conservative auth-like parameter suppression in decorator fallback path.
  - ISD: explicit localhost/loopback downgrade rule (`insecure_ssl_verify_localhost`, lower score) while keeping finding visibility.
  - HSC: prefix-first known-token literal detection independent of variable name shape.
  - Expanded TP/TN fixtures and explicit security precision/recall gates in `tests/test_precision_recall.py`.
- Verification:
  - `python -m pytest tests/test_missing_authorization.py tests/test_insecure_default.py tests/test_hardcoded_secret.py -q --maxfail=1`
  - `python -m pytest tests/test_precision_recall.py::test_precision_recall_report -q -s`
- Residual risk: Medium-low; conservative heuristics may still trade off edge-case recall or severity ranking, but regression coverage now enforces explicit security readiness gates.

## 2026-04-06 - MDS precision-first scoring-readiness calibration

- Risk ID: RISK-SIG-2026-04-06-186
- Component: src/drift/signals/mutant_duplicates.py
- Type: Signal quality (false positives / scoring credibility)
- Description: MDS produced low-actionability noise from semantic-only matches and
  intentional sync/async API variants, weakening trust when MDS contributes to
  repository scoring.
- Trigger examples:
  - Semantic-only matches within same-file context with high embedding similarity.
  - Sync/async file variants (`sync_*` vs `async_*`) with same function names.
  - Hybrid threshold previously lower than AST threshold, allowing borderline findings.
- Impact: Inflated MDS noise density and score distortion in precision-sensitive workflows.
- Mitigation:
  - Hybrid threshold is now precision-first (not lower than AST threshold).
  - Suppress intentional sync/async variant pairs for exact/near/semantic checks.
  - Tighten semantic-only gate and suppress same-file semantic pairs.
  - Keep cross-file semantic matches (including same class names) to avoid over-suppression.
  - Add regression tests in `tests/test_mutant_duplicates_edge_cases.py`.
- Verification:
  - `python -m pytest tests/test_mutant_duplicates_edge_cases.py -q --maxfail=1`
  - `python -m pytest tests/test_precision_recall.py::test_precision_recall_report -q -s`
- Residual risk: Medium-low; some true duplicates in sync/async ecosystems may be
  under-reported, but suppression is conservative and precision gains improve scoring reliability.

## 2026-04-06 - TPD unexpected source-segment exception hardening (Issue #184)

- Risk ID: RISK-SIG-2026-04-06-184
- Component: src/drift/signals/test_polarity_deficit.py
- Type: Signal quality (runtime robustness / false negatives)
- Description: `test_polarity_deficit` could still abort signal execution when `ast.get_source_segment` raised unexpected exception types beyond the previously guarded metadata errors.
- Trigger examples:
  - Field-test runs against microsoft/agent-framework showed TPD skip with `IndexError` and degraded context export quality.
  - Similar repositories with edge-case AST/source position behavior.
- Impact: Full TPD signal dropout for affected runs, causing incomplete context export and under-reporting.
- Mitigation:
  - Broadened source-segment guard in `_AssertionCounter.visit_Assert` to handle unexpected exceptions safely.
  - Added defensive per-file guards around parse/AST visit in TPD analyze path to prevent whole-signal abort.
  - Added regression `test_tpd_ignores_unexpected_source_segment_exception` in `tests/test_test_polarity_deficit.py`.
- Verification: `python -m pytest tests/test_test_polarity_deficit.py -q --maxfail=1`
- Residual risk: Low-medium; malformed files can be skipped for TPD counting, but signal execution remains stable and explicit logging supports diagnosis.

## 2026-04-06 - Stable signal abbreviation mapping in scan/analyze JSON (Issue #183)

- Risk ID: RISK-OUT-2026-04-06-183
- Component: src/drift/api.py, src/drift/api_helpers.py, src/drift/output/json_output.py
- Type: Output contract clarity / cross-command interoperability
- Description: `scan` and `analyze` used different identifier conventions without a
  first-class mapping field, forcing consumers to hardcode and maintain manual lookup tables.
- Trigger examples:
  - Agent workflows that correlate `scan` findings (`signal_id`/abbrev) with
    `analyze` findings (`signal_type`/snake_case).
  - CI pipelines that merge or compare findings across commands and versions.
- Impact: Reduced reproducibility and higher risk of wrong signal joins when mapping drifts.
- Mitigation:
  - Added top-level `signal_abbrev_map` (abbrev -> canonical `signal_type`) to
    both `scan` and `analyze --format json` outputs.
  - Reused centralized mapping source in `api_helpers` to prevent divergent maps.
  - Added regression tests in `tests/test_scan_diversity.py` and `tests/test_json_output.py`.
- Verification: `python -m pytest tests/test_scan_diversity.py tests/test_json_output.py -q --maxfail=1`
- Residual risk: Low; additive schema extension, existing fields remain unchanged.

## 2026-04-06 - HSC YAML env-template variable-name false-positive mitigation (Issue #181)

- Risk ID: RISK-SIG-2026-04-06-181
- Component: src/drift/signals/hardcoded_secret.py
- Type: Signal quality (false positives / precision calibration)
- Description: HSC flagged YAML configuration templates as hardcoded secrets when variable names contained secret-like tokens (for example `YAML_OPENAI_WITH_API_KEY`) although values only referenced `${ENV_VAR}` placeholders.
- Trigger examples:
  - microsoft/agent-framework: multi-line YAML template containing `openai_api_key: ${OPENAI_API_KEY}`.
  - Similar repositories storing config templates in Python triple-quoted strings.
- Impact: High-severity false positives and reduced trust in HSC precision/actionability.
- Mitigation:
  - Added narrow suppression for multi-line key/value template literals that contain environment placeholders (`${...}`).
  - Preserved high-confidence known-prefix checks before suppression.
  - Added targeted regressions in `tests/test_hardcoded_secret.py` for suppression and known-prefix safety.
- Verification: `python -m pytest tests/test_hardcoded_secret.py -q --maxfail=1`
- Residual risk: Low-medium; mixed template literals containing unusual non-prefixed credentials may be under-reported, but suppression remains constrained and known-prefix coverage is unchanged.

## 2026-04-06 - TPD ast.get_source_segment crash mitigation (Issue #180)

- Risk ID: RISK-SIG-2026-04-06-180
- Component: src/drift/signals/test_polarity_deficit.py
- Type: Signal quality (runtime robustness / false negatives)
- Description: `test_polarity_deficit` could crash with `IndexError: list index out of range` (or `ValueError`) when `ast.get_source_segment` processes assert nodes with malformed source-position metadata.
- Trigger examples:
  - microsoft/agent-framework scan reported deterministic TPD crash during assert polarity classification.
  - Similar repositories containing edge-case AST metadata combinations in assert nodes.
- Impact: Full TPD signal dropout on affected scans (0 findings), causing systematic under-reporting and drift-score distortion for TPD weight.
- Mitigation:
  - Added exception-safe guard around `ast.get_source_segment` in `_AssertionCounter.visit_Assert`.
  - Added targeted regression `test_tpd_ignores_out_of_range_assert_position_metadata` in `tests/test_test_polarity_deficit.py`.
- Verification: `python -m pytest tests/test_test_polarity_deficit.py -q --maxfail=1`
- Residual risk: Low-medium; malformed-node asserts may skip regex-based fallback classification, but scan stability is preserved and AST-based polarity heuristics remain active.

## 2026-04-06 - MDS numbered sample-step duplicate false-positive mitigation (Issue #179)

- Risk ID: RISK-SIG-2026-04-06-179
- Component: src/drift/signals/mutant_duplicates.py
- Type: Signal quality (false positives / precision calibration)
- Description: `mutant_duplicate` over-penalized intentional duplication across numbered sample progression directories (for example `01_single_agent` and `02_multi_agent`) because suppression only matched `step*` directory names.
- Trigger examples:
  - microsoft/agent-framework: `python/samples/04-hosting/durabletask/01_single_agent/worker.py` and `02_multi_agent/worker.py` duplicate `get_worker` helper patterns.
  - Similar repositories that structure tutorial/sample progression via numeric prefixes instead of `step_*` naming.
- Impact: High-severity false-positive noise in MDS and reduced confidence in duplicate findings.
- Mitigation:
  - Extended tutorial-step suppression to include conservative numbered sample-step directory names (`^\d{1,3}[-_].+`) in addition to `step*`.
  - Kept suppression context-gated to tutorial/sample/example path markers.
  - Added regressions in `tests/test_mutant_duplicates_edge_cases.py` for helper detection and exact-duplicate suppression in numbered sample directories.
- Verification: `python -m pytest tests/test_mutant_duplicates_edge_cases.py -q --maxfail=1`
- Residual risk: Medium-low; true duplicates in pedagogical numbered sample trees may be under-reported, while non-step sample duplicates remain detectable.

## 2026-04-06 - MDS tutorial-step sample duplicate false-positive mitigation (Issue #177)

- Risk ID: RISK-SIG-2026-04-06-177
- Component: src/drift/signals/mutant_duplicates.py
- Type: Signal quality (false positives / precision calibration)
- Description: `mutant_duplicate` over-penalized intentional helper duplication across tutorial step sample directories (for example repeated `get_worker` across `step_*` folders) as high-severity exact duplicates.
- Trigger examples:
  - microsoft/agent-framework: durabletask tutorial steps with standalone helper copies.
  - Similar repositories with pedagogical step-by-step sample trees.
- Impact: High-severity triage noise in MDS and reduced confidence in duplicate findings.
- Mitigation:
  - Added conservative path-context suppression for MDS candidate collection when file path indicates tutorial/sample/example plus explicit `step*` directory markers.
  - Added regressions in `tests/test_mutant_duplicates_edge_cases.py` for suppression and control-case detection outside step directories.
- Verification: `python -m pytest tests/test_mutant_duplicates_edge_cases.py -q --maxfail=1`
- Residual risk: Medium-low; true duplication in tutorial-step paths may be under-reported, but heuristic scope is intentionally narrow and non-step sample duplicates remain detectable.

## 2026-04-06 - DCA script-context false-positive mitigation (Issue #176)

- Risk ID: RISK-SIG-2026-04-06-176
- Component: src/drift/signals/dead_code_accumulation.py
- Type: Signal quality (false positives / precision calibration)
- Description: DCA reported script-internal functions in executable Python utility/CI modules as unused exports because usage is often local call graph + `__main__` execution, not cross-file imports.
- Trigger examples:
  - microsoft/agent-framework: `.github/workflows/python-check-coverage.py`
  - Similar repositories with executable Python scripts under `.github/workflows`, `scripts`, `tools`, or `bin`.
- Impact: Medium-high false-positive noise in DCA, reduced trust in dead-code recommendations.
- Mitigation:
  - Added conservative script-context path suppression for Python files in script-like locations.
  - Added regression test in `tests/test_dead_code_accumulation.py` for `.github/workflows/python-check-coverage.py`.
- Verification: `python -m pytest tests/test_dead_code_accumulation.py -q --maxfail=1`
- Residual risk: Medium-low; script-like paths containing genuine import-oriented library modules may be under-reported, but scope is intentionally limited to executable-context locations.

## 2026-04-05 - HSC OpenTelemetry GenAI semconv false-positive mitigation (Issue #175)

- Risk ID: RISK-SIG-2026-04-05-175
- Component: src/drift/signals/hardcoded_secret.py
- Type: Signal quality (false positives / precision calibration)
- Description: HSC flagged OpenTelemetry GenAI observability constants (for example `INPUT_TOKENS = "gen_ai.usage.input_tokens"`) as hardcoded secrets because `token` in symbol names triggered the secret-variable heuristic.
- Trigger examples:
  - microsoft/agent-framework: `python/packages/core/agent_framework/observability.py` with GenAI metrics constants.
  - Similar repositories using OpenTelemetry GenAI semantic-convention keys (`gen_ai.*`) in constants.
- Impact: High-severity false positives in telemetry modules, reduced trust in HSC precision, and avoidable remediation churn.
- Mitigation:
  - Added conservative suppression for OpenTelemetry GenAI semantic-convention literals (`gen_ai.<segment>.<segment...>`).
  - Preserved high-confidence secret detection ordering (known prefixes are evaluated before suppression).
  - Added targeted regressions in `tests/test_hardcoded_secret.py` for non-detection of semconv constants and continued detection of known-prefix secrets.
- Verification: `python -m pytest tests/test_hardcoded_secret.py -q --maxfail=1`
- Residual risk: Low-medium; rare credential strings mimicking `gen_ai.*` key format may be under-reported, but suppression scope is intentionally narrow and known-prefix checks remain active.

## 2026-04-05 - Scan/Analyze Cross-Validation Felder im Scan-Output (Issue #171)

- Risk ID: RISK-OUT-2026-04-05-171
- Component: src/drift/api.py, src/drift/api_helpers.py
- Type: Output contract clarity / automation reliability
- Description: Agenten mussten Scan- und Analyze-Resultate mit unterschiedlichen Feldnamen und ohne stabilen Finding-Fingerprint korrelieren. Das erhöhte das Risiko von fehlerhaften Deduplikationen und inkonsistenter Priorisierung.
- Trigger examples:
  - Vergleich `scan` vs `analyze` in CI/Agent-Workflows mit signalabhängiger Bündelung.
  - Automatisierte Merges von Findings über mehrere Läufe ohne stabile ID.
- Impact: Erhöhte Fehlzuordnung in Cross-Validation, geringere Reproduzierbarkeit bei agentischen Workflows.
- Mitigation:
  - Harmonisierte Scan-Felder: `signal_abbrev`, `signal_id`, `signal_type` in concise/detailed/fix_first.
  - Stabile Finding-ID im Scan-Output ergänzt: `fingerprint` (deterministisch über bestehende Baseline-Fingerprint-Logik).
  - Numerische Schweregradskalierung ergänzt: `severity_rank` je Finding.
  - Top-Level-Metadaten ergänzt: `cross_validation` mit Signalfeld-Mapping, Severity-Ranking und numerischer Score-Skala.
  - Regressionen ergänzt in `tests/test_scan_diversity.py`.
- Verification: `python -m pytest tests/test_scan_diversity.py tests/test_agent_native_cli.py -q --maxfail=1`
- Residual risk: Low; Änderung ist additiv und rückwärtskompatibel für bestehende Consumer, die unbekannte Felder ignorieren.

## 2026-04-05 - AVS/ECM/TPD Recall-Härtung auf Groß-Repositories (Issue #170)

- Risk ID: RISK-SIG-2026-04-05-170
- Component: src/drift/signals/architecture_violation.py, src/drift/signals/exception_contract_drift.py, src/drift/signals/test_polarity_deficit.py
- Type: Signal quality (false negatives / recall)
- Description: Drei unabhängige Recall-Lücken konnten auf großen Repositories zu systematischen 0-Finding-Ergebnissen führen: (1) AVS verlor interne Kanten bei relativen Imports, (2) ECM analysierte bei großen Kandidatmengen ein zu kleines Hot-File-Subset, (3) TPD erhielt bei globalem `**/tests/**`-Exclude keine Test-ParseResults.
- Trigger examples:
  - Relative Imports (`from .service import ...`) in Paketstrukturen mit starker interner Modulkopplung.
  - Repositories mit tausenden ECM-Kandidaten und hoher Commit-Konzentration auf wenigen Dateien.
  - Standard-Setups mit globalem Test-Exclude, bei denen TPD trotz aktivem Signal keine Testdateien sieht.
- Impact: Unterberichtete Architektur- und Testsignal-Befunde, reduzierte Signal-Glaubwürdigkeit bei Real-World-Scans.
- Mitigation:
  - AVS: relative Import-Kandidatenauflösung für interne Graph-Kanten ergänzt.
  - ECM: adaptive Kandidatenobergrenze (konfigurierter Floor, skalierender Cap bis 300) ergänzt.
  - TPD: Fallback-Testdatei-Discovery aus Repo-Dateisystem ergänzt, wenn ParseResults keine Tests enthalten.
  - Regressionen ergänzt in `tests/test_architecture_violation.py`, `tests/test_exception_contract_drift.py`, `tests/test_test_polarity_deficit.py`.
- Verification: `python -m pytest tests/test_architecture_violation.py tests/test_exception_contract_drift.py tests/test_test_polarity_deficit.py -q --maxfail=1`
- Residual risk: Medium-low; relative Importauflösung bleibt best-effort ohne expliziten AST-Level, und TPD-Fallback kann in exotischen Repo-Layouts zusätzliche Laufzeit verursachen.

## 2026-04-05 - MAZ decorator fallback recall calibration (Issue #169)

- Risk ID: RISK-SIG-2026-04-05-169
- Component: src/drift/signals/missing_authorization.py
- Type: Signal quality (false negatives / recall)
- Description: MAZ depended fully on `API_ENDPOINT` patterns. In files where ingestion did not emit endpoint patterns despite route decorators, MAZ returned no findings.
- Trigger examples:
  - Framework files with decorated handlers (`@router.get`, `@app.post`) and missing auth where pattern extraction under-detects endpoints.
  - Large repositories with mixed routing idioms where ingestion coverage is incomplete per file.
- Impact: Missing-authorization gaps can be silently under-reported, reducing trust in MAZ recall.
- Mitigation:
  - Added conservative decorator fallback endpoint inference in MAZ, activated only when a file has no `API_ENDPOINT` patterns.
  - Added auth-decorator suppression in fallback path.
  - Added regressions in tests/test_missing_authorization.py for fallback detection and auth-decorator suppression.
- Verification: `python -m pytest tests/test_missing_authorization.py -q --maxfail=1`
- Residual risk: Medium-low; fallback may still need marker tuning for rare decorator naming collisions, but scope is constrained and existing suppressions remain active.

## 2026-04-05 - BEM fallback-assignment and AVS src-root import false-negative mitigation (Issue #168)

- Risk ID: RISK-SIG-2026-04-05-168
- Component: src/drift/ingestion/ast_parser.py, src/drift/signals/broad_exception_monoculture.py, src/drift/signals/architecture_violation.py
- Type: Signal quality (false negatives / recall)
- Description: Two recall gaps reduced signal quality on large real-world repositories: (1) BEM did not treat broad-exception fallback assignments as swallowing handlers, and (2) AVS failed to resolve internal imports in source-root layouts (`src/`, `lib/`, `python/`) when imports omitted the source-root prefix.
- Trigger examples:
  - huggingface/transformers: repeated `except Exception: _available = False` style handlers in import utility modules.
  - src-root package imports such as `transformers.api.routes` resolving to `src/transformers/api/routes.py`.
- Impact: Under-reported high-signal architectural drift and exception monoculture findings, reducing trust in Drift recall.
- Mitigation:
  - Added `fallback_assign` handler action in AST fingerprinting and included it in BEM swallowing-action criteria.
  - Added AVS module alias resolution for common source-root prefixes when building the import graph.
  - Added targeted regressions in `tests/test_ast_parser.py`, `tests/test_consistency_proxies.py`, and `tests/test_architecture_violation.py`.
- Verification: `python -m pytest tests/test_ast_parser.py tests/test_consistency_proxies.py tests/test_architecture_violation.py -q --maxfail=1`
- Residual risk: Medium-low; alias resolution currently targets common source roots and may require extension for unusual repository layouts.

## 2026-04-05 - MAZ localhost CLI serving false-positive mitigation (Issue #167)

- Risk ID: RISK-SIG-2026-04-05-167
- Component: src/drift/signals/missing_authorization.py
- Type: Signal quality (false positives / context-sensitive suppression)
- Description: MAZ flagged local CLI serving endpoints (for example `src/transformers/cli/serving/server.py`) as missing authorization even when handlers are intended for localhost-oriented development tooling rather than production API exposure.
- Trigger examples:
  - huggingface/transformers: `cli/serving/server.py` handlers (`chat_completions`, `responses`, `load_model`, `list_models`, `generate`) reported as MAZ findings.
  - Similar repositories with route handlers embedded in CLI-local serving entry modules.
- Impact: Severe precision collapse in this context (reported 0%), high-priority triage noise, and risk of incorrect remediation guidance.
- Mitigation:
  - Added targeted MAZ suppression for CLI-local serving path context (`cli` + `serving/serve` markers).
  - Added Issue #167 regressions ensuring CLI-serving path is suppressed while non-CLI serving path remains reportable.
- Verification: `python -m pytest tests/test_missing_authorization.py -q`
- Residual risk: Medium-low; unusual production deployments using CLI-serving path conventions may be under-reported, but suppression remains tightly scoped.

## 2026-04-05 - HSC ML tokenizer constant false-positive mitigation (Issue #166)

- Risk ID: RISK-SIG-2026-04-05-166
- Component: src/drift/signals/hardcoded_secret.py
- Type: Signal quality (false positives / precision calibration)
- Description: HSC flagged ML tokenizer configuration constants as hardcoded secrets when symbol names contained `token` despite literals representing NLP metadata (for example `pad_token`, `cls_token`, `tokenizer_class_name`, `chat_template`).
- Trigger examples:
  - huggingface/transformers: tokenizer constants produced high FP volume in HSC findings.
  - Similar NLP repositories with tokenizer config objects and chat-template literals.
- Impact: Significant precision drop, high-severity triage noise, and reduced trust in HSC ranking.
- Mitigation:
  - Add tokenizer-context suppression for known tokenizer symbol names and token literal markers/template syntax.
  - Preserve high-confidence secret detection ordering (known token prefixes are evaluated before suppression).
  - Add targeted regressions for tokenizer constants, tokenizer keyword arguments, and guard test proving known-prefix secrets still fire.
- Verification: `python -m pytest tests/test_hardcoded_secret.py -q --maxfail=1`
- Residual risk: Medium-low; rare misuse of tokenizer-shaped symbols for real credentials may bypass generic detection, but known-prefix secret detection remains active.

## 2026-04-05 - NBV try_* attempt-semantics false-positive mitigation (Issue #165)

- Risk ID: RISK-SIG-2026-04-05-165
- Component: src/drift/signals/naming_contract_violation.py
- Type: Signal quality (false positives / precision calibration)
- Description: NBV flagged `try_*` helper functions as naming-contract violations when `try_` was used in natural "attempt/check" semantics (for example `try_neq_default`) without exception handling intent.
- Trigger examples:
  - langchain-ai/langchain: `libs/core/langchain_core/utils/function_calling.py::try_neq_default`
  - Similar utility/helper modules with comparison-oriented `try_*` functions.
- Impact: Medium-severity false positives, reduced trust in NBV signal, avoidable triage churn.
- Mitigation:
  - Added targeted suppression for `try_*` when body suggests comparison/check semantics (`ast.Compare`, `is None`, `isinstance`).
  - Added utility-context suppression via path tokens (`utils`, `helpers`, `common`).
  - Added regression tests for comparison-semantic and utility-context `try_*` helpers.
- Verification: `python -m pytest tests/test_naming_contract_violation.py -q --maxfail=1`
- Residual risk: Medium-low; some true try/except contract mismatches in helper paths may be under-reported, but suppression is scoped to `try_*` only.

## 2026-04-05 - DIA bootstrap-repo README false-positive mitigation

- Risk ID: RISK-SIG-2026-04-05-DIA-BOOTSTRAP
- Component: src/drift/signals/doc_impl_drift.py
- Type: Signal quality (false positives / actionability threshold)
- Description: `doc_impl_drift` reported `No README found` on bootstrap-sized repositories with zero or one parsed Python file, and on pure `__init__.py` package skeletons, even though the result was not actionable architectural drift for empty, single-file, or init-only repos.
- Trigger examples:
  - Temporary one-file scripts scanned via `drift.api.scan()`.
  - Minimal package skeletons containing only `__init__.py`.
- Impact: Medium-severity noise in baseline scans, lower trust in DIA, and misleading next-step guidance for repositories that are not yet architecturally shaped.
- Mitigation:
  - Suppress README-missing findings when `len(parse_results) <= 1` or all parsed files are named `__init__.py`.
  - Extend `tests/test_analysis_edge_cases.py` to assert zero findings for empty, single-file, and init-only repositories.
- Verification: `python -m pytest tests/test_analysis_edge_cases.py -q --maxfail=1`
- Residual risk: Low; very small repositories and pure package skeletons will no longer receive README nudges until they exceed bootstrap size, which is an acceptable tradeoff for signal credibility.

## 2026-04-05 - AVS lazy-import policy violation detection (Issue #146)

- Risk ID: RISK-SIG-2026-04-05-146
- Component: src/drift/signals/architecture_violation.py, src/drift/config.py, src/drift/ingestion/ast_parser.py, src/drift/models.py
- Type: Signal quality (false negatives / policy coverage)
- Description: AVS did not surface explicit lazy-import policy violations for heavy runtime libraries imported at module level, even when repository policy mandated lazy imports.
- Trigger examples:
  - mickg/Real-Time Fortnite Coach: module-level heavy import in perception detector path.
  - Similar ML/runtime-sensitive repositories with documented lazy-import conventions.
- Impact: Missed policy-level architecture findings, lower trust in AVS for enforcement-oriented workflows.
- Mitigation:
  - Added configurable `policies.lazy_import_rules` (`from`, `modules`, `module_level_only`) in config model/schema.
  - Added AVS check producing dedicated `avs_lazy_import_policy` findings.
  - Added import scope metadata (`ImportInfo.is_module_level`) to distinguish module-level from local lazy imports.
  - Added regressions for detection and local-import non-detection.
- Verification: `pytest tests/test_architecture_violation.py tests/test_ast_parser.py tests/test_config.py -q --maxfail=1` (37 passed).
- Residual risk: Medium-low; pattern-based module matching may require repo-specific tuning for unusual import aliasing conventions.

## 2026-04-05 - MDS package-level lazy __getattr__ false-positive mitigation (Issue #144)

- Risk ID: RISK-SIG-2026-04-05-144
- Component: src/drift/signals/mutant_duplicates.py
- Type: Signal quality (false positives / severity calibration)
- Description: `mutant_duplicate` flagged identical package-level `__getattr__` implementations in `__init__.py` as high-severity duplicates, even when this pattern is an intentional lazy-submodule loading idiom (PEP 562).
- Trigger examples:
  - mickg/Real-Time Fortnite Coach: multiple package `__init__.py` files with deliberate lazy-loading `__getattr__` implementation.
  - Similar Python package repos that expose lazy imports via package `__getattr__`.
- Impact: False-positive duplicate findings, inflated high-severity noise, reduced trust in MDS prioritization.
- Mitigation:
  - Add explicit `__getattr__` + `__init__.py` heuristic (`_is_package_lazy_getattr`) and exclude these functions from MDS duplicate candidate collection.
  - Keep duplicate detection active for non-package `__getattr__` implementations.
  - Add dedicated regression tests for both suppression and non-suppression cases.
- Verification: `pytest tests/test_mutant_duplicates_edge_cases.py -q --maxfail=1` (23 passed).
- Residual risk: Medium-low; rare repositories may hide truly problematic package-level `__getattr__` duplication, but this is generally intentional API plumbing.

## 2026-04-05 - TPD negative assertion undercount calibration (Issue #143)

- Risk ID: RISK-SIG-2026-04-05-143
- Component: src/drift/signals/test_polarity_deficit.py
- Type: Signal quality (false positives / polarity misclassification)
- Description: `test_polarity_deficit` undercounted negative assertions in Python tests, especially for expressive assert styles (`assert not ...`, `assert ... is False/None`) and functional negative helpers (`pytest.raises(...)`, `pytest.fail(...)`).
- Trigger examples:
  - mickg/Real-Time Fortnite Coach: `tests/biometric` reported as nearly all-positive despite many negative-path checks.
  - Similar repositories using assert-style failure checks instead of only context-manager `pytest.raises` patterns.
- Impact: False-positive happy-path-only findings, severity miscalibration, and reduced trust in test polarity diagnostics.
- Mitigation:
  - Added AST-aware assert polarity classification for negative assert forms.
  - Added conservative regex fallback for assert text variants not cleanly captured by AST heuristics.
  - Added explicit negative call detection for functional `raises`/`fail` patterns.
  - Added targeted regressions for mixed-polarity suites and functional raises/fail calls.
- Verification: `pytest tests/test_test_polarity_deficit.py -q --maxfail=1` (3 passed).
- Residual risk: Medium-low; heuristic classification may still need tuning for rare domain-specific assert semantics.

## 2026-04-05 - PFS framework-surface error-handling severity calibration (Issue #142)

- Risk ID: RISK-SIG-2026-04-05-142
- Component: src/drift/signals/pattern_fragmentation.py
- Type: Signal quality (false positives / severity calibration)
- Description: pattern_fragmentation over-prioritized error-handling variance in framework-facing application layers (for example routers/pages/server orchestration), where heterogeneity is often intentional.
- Trigger examples:
  - mickg/Real-Time Fortnite Coach: backend/api/routers, src/ui/pages, mcp_server
  - Similar monorepos with mixed framework boundaries and endpoint orchestration code
- Impact: High-severity false-positive clustering, reduced trust in PFS ranking, and avoidable remediation churn.
- Mitigation:
  - Add framework-surface heuristic hints (API endpoint co-location + path/file tokens such as router/page/controller/server).
  - Apply conservative score dampening for error_handling findings in framework-facing modules.
  - Prevent default HIGH severity for this context while preserving finding emission and explainability metadata.
  - Add targeted regressions for dampened framework modules and unchanged core-module behavior.
- Verification: pytest tests/test_pattern_fragmentation.py -q --maxfail=1
- Residual risk: Medium-low; heuristic hints may under-rank rare high-risk fragmentation at framework boundaries, but findings are still emitted with explicit context metadata.

## 2026-04-05 - drift_score scope disambiguation in machine outputs (Issue #159)

- Risk ID: RISK-OUT-2026-04-05-159
- Components: src/drift/api_helpers.py, src/drift/api.py, src/drift/output/json_output.py, src/drift/commands/analyze.py, src/drift/commands/check.py, src/drift/commands/baseline.py, src/drift/baseline.py, src/drift/output/agent_tasks.py, src/drift/copilot_context.py, src/drift/negative_context_export.py
- Type: Output contract clarity / agent decision safety
- Description: `drift_score` appeared with one key name across different execution scopes (repo, diff, baseline-filtered, fix-plan context), enabling incorrect cross-context comparisons by agents and CI orchestrators.
- Mitigation:
  - Added sibling field `drift_score_scope` to affected machine-readable payloads.
  - Introduced centralized scope builder (`build_drift_score_scope`) and signal-scope label helper (`signal_scope_label`) for deterministic descriptors.
  - Wired scope descriptors into analyze/check JSON, scan API, baseline outputs, fix-plan API, brief/negative-context payloads, copilot context payload, and agent-tasks JSON.
- Verification: `pytest tests/test_json_output.py tests/test_output_golden.py tests/test_scan_diversity.py tests/test_brief.py tests/test_mcp_copilot.py tests/test_baseline.py::TestBaselineIO tests/test_baseline.py::TestBaselineDiff -q --maxfail=1` (117 passed).
- Residual risk: Low; legacy consumers that ignore unknown fields remain compatible, while consumers that compare scores now have explicit scope metadata.

## 2026-04-05 - MAZ, AVS, EDS signal quality improvements (Issues #148, #149, #150, #151)

- Risk ID: RISK-SIG-2026-04-05-148-151
- Components: src/drift/signals/missing_authorization.py, src/drift/signals/architecture_violation.py, src/drift/signals/explainability_deficit.py, src/drift/models.py, src/drift/api_helpers.py, src/drift/config.py
- Type: Signal quality (precision, severity calibration, location completeness, sub-signal attribution)
- Description: Four signal quality issues addressed in a single batch:
  - #148: MAZ flagged intentionally public endpoints (anon, public, security_txt, etc.) and dev-tool paths as missing authorization. Estimated precision ~20%.
  - #149: Multiple signals produced findings with null start_line, making agent-driven fix workflows impossible.
  - #150: AVS scan output conflated co-change coupling, circular deps, blast radius, and other sub-checks under a single "AVS" signal abbreviation with no rule_id disambiguation.
  - #151: EDS severity was not calibrated to actual function complexity/LOC — trivial getters received the same HIGH rating as complex algorithms.
- Mitigations:
  - #148: Expanded default maz_public_endpoint_allowlist (+25 patterns: public, anon, security_txt, pricing, manifest, etc.) and added dev-tool path heuristic (maz_dev_tool_paths config with 7 defaults).
  - #149: Added start_line=1 fallback in Finding.__post_init__ when file_path is set but start_line is None, ensuring all findings have machine-readable location data.
  - #150: Added explicit rule_id to each AVS sub-check (avs_policy_boundary, avs_upward_import, avs_circular_dep, avs_blast_radius, avs_zone_of_pain, avs_god_module, avs_unstable_dep, avs_co_change). Exposed rule_id in concise scan output format.
  - #151: Added LOC-based dampening (loc_factor = loc/30) and private function visibility dampening (0.7×) to EDS severity calculation.
- Verification: 1903+ tests passed (excluding 1 pre-existing MCP schema type failure). New regression tests for MAZ allowlist, dev-tool path, and non-dev-path behavior.
- Residual risk: Low; allowlist-based pattern matching may need further tuning for unusual naming conventions.

## 2026-04-05 - HSC OAuth endpoint URL false-positive mitigation (Issue #161)

- Risk ID: RISK-SIG-2026-04-05-161
- Component: src/drift/signals/hardcoded_secret.py
- Type: Signal quality (false positives / precision calibration)
- Description: HSC flagged OAuth endpoint constants (for example `TOKEN_URL = "https://oauth2.googleapis.com/token"`) as hardcoded secrets when variable names matched secret-like tokens.
- Trigger examples:
  - onyx-dot-app/onyx: `backend/ee/onyx/server/oauth/google_drive.py` with `TOKEN_URL` endpoint constant.
  - Similar integration code with `AUTH_URL`/`TOKEN_URL` endpoint literals.
- Impact: High-severity false positives, lower trust in HSC results, and avoidable remediation work.
- Mitigation:
  - Add URL-aware suppression for plain HTTP(S) endpoint literals without embedded credentials.
  - Keep detection active for URLs with userinfo credentials (`username`/`password`) to avoid masking true secrets.
  - Add targeted regression tests for OAuth endpoint constants and credential-bearing URL literals.
- Verification: tests/test_hardcoded_secret.py (new Issue #161 regressions, suite green).
- Residual risk: Low; unusual credential encodings outside URL userinfo remain heuristic-driven.

## 2026-04-05 - HSC error-message constant false-positive mitigation (Issue #163)

- Risk ID: RISK-SIG-2026-04-05-163
- Component: src/drift/signals/hardcoded_secret.py
- Type: Signal quality (false positives / precision calibration)
- Description: HSC flagged natural-language error message constants (for example `_MAX_TOKENS_ERROR`) as hardcoded secrets because variable names matched secret-like tokens while the literal itself was plain-text guidance.
- Trigger examples:
  - langchain-ai/langchain: `_MAX_TOKENS_ERROR` in output parser module.
  - Similar repositories using UPPER_CASE `*_ERROR`/`*_WARNING`/`*_MESSAGE` constants.
- Impact: High-severity false positives, triage noise, reduced trust in HSC output.
- Mitigation:
  - Added message-constant suppression for variable suffixes `_ERROR`, `_WARNING`, `_MESSAGE` when the literal matches natural-language message characteristics.
  - Preserved higher-confidence detection order (known token prefixes and credential-bearing URLs are evaluated before suppression).
  - Added regression test in `tests/test_hardcoded_secret.py` for `_MAX_TOKENS_ERROR` style constants.
- Verification: `python -m pytest tests/test_hardcoded_secret.py -q --maxfail=1`
- Residual risk: Low; intentional misnaming of real credentials as message constants is rare, and high-confidence token-prefix checks still trigger before suppression.

## 2026-04-05 - MAZ documented public-safe publishable-key severity downgrade (Issue #162)

- Risk ID: RISK-SIG-2026-04-05-162
- Component: src/drift/signals/missing_authorization.py
- Type: Signal quality (severity calibration / false-positive reduction)
- Description: MAZ emitted HIGH severity for intentionally public-safe publishable-key endpoints where no authorization is expected by design.
- Trigger examples:
  - onyx-dot-app/onyx: `get_stripe_publishable_key` reported as MAZ HIGH despite explicit public-safe rationale in code documentation.
  - Similar endpoint families: publishable/public client key retrieval routes.
- Impact: Over-prioritized findings, reduced analyst trust, and avoidable remediation churn.
- Mitigation:
  - Add conservative public-safe heuristic for MAZ severity dampening.
  - Require both conditions for LOW downgrade: endpoint name marker (`publishable/public key`) + explicit function docstring.
  - Keep finding emitted (no suppression) and expose `public_safe_documented` metadata for explainability.
  - Add regression tests for downgraded documented case and non-documented HIGH case.
- Verification: tests/test_missing_authorization.py (new Issue #162 regressions).
- Residual risk: Medium-low; semantic naming/docstring heuristics may still need repository-specific tuning for edge cases.

## 2026-04-05 - AVS tiny foundational module over-severity recalibration (Issue #153)

- Risk ID: RISK-SIG-2026-04-05-153
- Component: src/drift/signals/architecture_violation.py
- Type: Signal quality (severity calibration / false positives)
- Description: AVS Zone-of-Pain scoring emitted HIGH findings for tiny, intentionally stable foundational modules (for example logger/base adapters) without sufficient coupling evidence.
- Trigger examples:
  - fastapi/fastapi: tiny foundation modules reported as "Zone of Pain" with HIGH severity.
  - Typical profile: low instability, high distance, small file size, low structural footprint.
- Impact: Over-prioritization of low-actionability findings, reduced trust in AVS severity guidance.
- Mitigation:
  - Add tiny-foundational dampening in Zone-of-Pain scoring (`line_count <= 20`, `entity_count <= 2`, `ce <= 1`).
  - Require stronger coupling evidence for HIGH (`ca >= 6` or `ca >= 4 and ce >= 2`).
  - Emit explainability metadata (`tiny_foundational_dampened`, `has_high_risk_evidence`, `line_count`, `entity_count`).
  - Add regression tests covering dampened tiny modules and strong-evidence HIGH cases.
- Verification: tests/test_architecture_violation.py (19 passed, includes new Issue #153 regressions).
- Residual risk: Medium-low; heuristics may still need profile tuning for unusually dense tiny modules.

## 2026-04-05 - DCA package public API false-positive mitigation (Issue #152)

- Risk ID: RISK-SIG-2026-04-05-152
- Component: src/drift/signals/dead_code_accumulation.py
- Type: Signal quality (false positives / recall balance)
- Description: DCA treated public exports in package-layout framework/library repositories as dead code when symbols are externally consumed but not internally imported.
- Trigger examples:
  - fastapi/applications.py and related package modules with externally used public symbols.
  - Aggregate finding title: "N potentially unused exports" in framework API files.
- Impact: High false-positive rate, reduced trust in DCA remediation guidance.
- Mitigation:
  - Add package-layout heuristic that suppresses dead-export reporting for likely public API modules.
  - Keep internal/private path tokens in scope to preserve internal dead-code detection.
  - Add dedicated regression tests for both suppression and internal-path coverage.
- Verification: tests/test_dead_code_accumulation.py (7 passed, including new Issue #152 regressions).
- Residual risk: Medium-low; path-based heuristics may still under-report edge-case internal modules in package roots.

## 2026-04-04 - MCP stdio deadlock hardening on Windows

- Risk ID: RISK-MCP-2026-04-04-STDIO
- Component: src/drift/mcp_server.py, src/drift/analyzer.py, src/drift/api.py, src/drift/incremental.py, src/drift/ingestion/git_history.py, src/drift/pipeline.py, src/drift/signals/exception_contract_drift.py
- Type: Runtime availability and transport safety
- Description: MCP tool calls could hang permanently on Windows when subprocesses inherited server stdin handles or when heavy C-extension modules were first imported from worker threads after event-loop startup.
- Trigger examples:
  - `subprocess.run(...)` without `stdin=subprocess.DEVNULL` inside MCP-invoked paths.
  - First-time lazy import of heavy dependencies (for example numpy/torch/faiss) during `asyncio.to_thread` execution.
- Impact: Tool invocation stalls, session instability, and reduced trust because MCP responses do not complete.
- Mitigation:
  - Add `stdin=subprocess.DEVNULL` to affected subprocess calls across analyzer/API/ingestion/signal paths.
  - Ensure MCP tools remain async and return structured error envelopes on exceptions.
  - Add eager imports before `mcp.run()` to avoid loader-lock deadlocks during threaded execution.
- Verification: tests/test_mcp_hardening.py, tests/test_nudge.py, quick no-smoke pytest suite.
- Residual risk: Low; remaining risk is limited to future regressions where new subprocess calls omit explicit stdin handling.

## 2026-04-03 - Parse I/O resilience and malformed trend history hardening

- Risk ID: RISK-ING-2026-04-03-RESILIENCE
- Component: src/drift/ingestion/ast_parser.py, src/drift/ingestion/ts_parser.py, src/drift/signals/_utils.py, src/drift/trend_history.py, src/drift/commands/trend.py
- Type: Ingestion robustness and result continuity
- Description: Transient file-system race conditions (file removed between discovery and parse) and malformed trend snapshots could raise unhandled exceptions or break CLI rendering.
- Trigger examples:
  - `FileNotFoundError` / `PermissionError` while reading discovered Python/TypeScript files.
  - History entries without numeric `drift_score` or missing `timestamp` fields.
- Impact: Analyzer interruption, reduced reproducibility, and unstable user feedback under non-deterministic file-system conditions.
- Mitigation:
  - Parse paths now return structured `ParseResult.parse_errors` on `OSError` instead of propagating exceptions.
  - Trend context and trend CLI now filter malformed snapshots and continue with valid entries.
  - TypeScript parse helper degrades cleanly when parser dependencies are unavailable and logs debug details for unexpected parser failures.
- Verification: tests/test_parse_file_resilience.py, tests/test_malformed_history.py, tests/test_brief.py.
- Residual risk: Low; malformed historical data is skipped, so derived trend depth may be lower than raw snapshot count.

## 2026-04-03 - PFS/NBV copilot-context actionability upgrade (Issue #125)

- Risk ID: RISK-SIG-2026-04-03-125
- Component: src/drift/signals/pattern_fragmentation.py, src/drift/signals/naming_contract_violation.py
- Type: Signal remediation quality (actionability / trust)
- Description: PFS and NBV remediation text was too generic for agent execution and lacked concrete location anchors.
- Trigger examples:
  - PFS: "Consolidate to the dominant pattern" without exemplar or line-level deviation refs.
  - NBV: generic "add missing behaviour" without contract-specific implementation direction.
- Impact: Higher manual triage effort, reduced confidence in AI-context guidance, delayed remediation.
- Mitigation:
  - PFS fix now includes canonical exemplar `file:line` and concrete deviation references.
  - NBV fix now includes `file:line` and prefix-specific suggestion (`validate_/check_`, `ensure_`, `is_/has_`, etc.).
- Verification: tests/test_pattern_fragmentation.py, tests/test_naming_contract_violation.py.
- Residual risk: Low; signals remain heuristic and may still need repo-specific interpretation.

## 2026-07-18 - Security audit: P0–P2 hardening

- Risk ID: RISK-SEC-2026-07-18-AUDIT
- Component: api.py, cache.py, signals/PFS+AVS+MDS, ingestion/file_discovery.py, negative_context.py
- Type: Security hardening + false-positive reduction
- Description: Multi-vector audit implementing path traversal prevention, config validation, test-file FP guards, OS error handling, and metadata injection sanitization.
- Changes:
  - P0: SignalCache pickle→JSON serialization (CWE-502 deserialization fix, previous session)
  - P0: _get_changed_files_from_git() returns None on failure with warning (previous session)
  - P1: _warn_config_issues() called after every DriftConfig.load() in scan/diff/fix_plan/nudge/negative_context
  - P1: Path sandbox validation for baseline_file and config_file parameters (CWE-22)
  - P2: is_test_file() guard added to PFS, AVS, MDS signals
  - P2: try/except OSError in file_discovery.py glob/stat/is_file operations
  - P2: _sanitize() strips control chars from metadata before f-string embedding in negative_context
- Verification: 1581 tests passed, mypy clean, ruff clean.
- Residual risk: Low; test-file guard is defense-in-depth (default exclude already covers most cases).

## 2026-04-03 - CSV output formatter (Issue #14)

- Risk ID: RISK-OUT-2026-04-03-014
- Component: src/drift/output/csv_output.py + CLI output format routing
- Type: Output channel integrity and consumer compatibility
- Description: New CSV serializer could introduce unstable ordering or malformed escaping, reducing trust in machine exports.
- Trigger examples: quoted titles, commas in title text, missing file/line values.
- Impact: Downstream ingestion can break or produce inconsistent triage tables.
- Mitigation: Use Python `csv` module, deterministic sorting key, and regression tests for header/order/escaping.
- Verification: tests/test_csv_output.py + tests/test_compat.py::TestOutputFormatAlias::test_csv_format_in_choices.
- Residual risk: Low; schema is intentionally minimal and additive.

## 2026-04-03 - DIA markdown slash-token FP reduction (Issue #121)

- Risk ID: RISK-DIA-2026-04-03-121
- Component: src/drift/signals/doc_impl_drift.py
- Type: Model quality (false positives)
- Description: DIA classified generic markdown slash tokens as missing directories.
- Trigger examples: async/, scan/, connectors/ in prose examples.
- Impact: Reduced signal credibility and remediation focus.
- Mitigation: Context-aware extraction with structural-keyword window and backtick-preserved refs.
- Verification: tests/test_dia_enhanced.py (new regression cases) + quick no-smoke suite pass.
- Residual risk: Low; uncommon prose phrasing without structural terms may still be filtered.

## 2026-04-09 - PHR Signal: Phantom Reference (ADR-033)

- Risk ID: RISK-PHR-2026-04-09-033
- Component: src/drift/signals/phantom_reference.py
- Type: New signal (report-only, weight 0.0)
- Description: PHR detects unresolvable function/class references in Python files — names used in call expressions that cannot be resolved against local definitions, imports, builtins, or the project-wide symbol table. Primary use case: detecting AI-hallucinated function references.
- FP mitigations:
  - Star-import files conservatively skipped (complete exclusion)
  - Module-level `__getattr__` files conservatively skipped
  - `_FRAMEWORK_GLOBALS` allowlist for common framework-injected names
  - Import-resolved names added to available set (root-name resolution)
  - Private names (`_prefix`) and dunder names excluded from flagging
  - TYPE_CHECKING blocks excluded from name collection
- FN acceptance:
  - `exec()`/`eval()` introduced names: static analysis limitation
  - `getattr(obj, "name")`: dynamic access invisible to AST
  - Decorator-only references: partially covered via _ScopeCollector
- Verification: 22 targeted tests (test_phantom_reference.py) + 6 ground-truth fixtures (2 TP, 4 TN/confounder) all passing. P=1.00 R=1.00 on fixture suite.
- Residual risk: Medium; report-only status (weight 0.0) prevents false positives from affecting composite scores. Real-world precision validation pending on external repos.

## 2026-04-10 - AST Logical Location Enrichment (ADR-039)

- Risk ID: RISK-LL-2026-04-10-039
- Component: src/drift/logical_location.py, src/drift/models.py, src/drift/pipeline.py, src/drift/output/json_output.py, src/drift/output/agent_tasks.py, src/drift/api_helpers.py
- Type: Output schema extension (additive field on Finding model)
- Description: Findings are enriched with AST-based logical locations (class, method, function, module) from existing ParseResult data. New `logical_location` object in JSON, `logicalLocations` in SARIF, and `logical_location` dict in AgentTask/API responses.
- Trigger examples: All findings emitted by any signal; enrichment is post-processing in ScoringPhase.
- Impact: Downstream consumers that strictly validate JSON schema may encounter unexpected new field. SARIF consumers gain richer location data.
- Mitigation: Field is optional (`None` when no match); existing fields unchanged; backward-compatible. Symbol backfill only when `Finding.symbol` was previously empty.
- Verification: tests/test_logical_location.py (22 tests), tests/test_precision_recall.py (no regression), full `make check`.
- Residual risk: Low; purely additive output with no signal logic changes.

## 2026-04-10 - Scoring Promotion: HSC, FOE, PHR (ADR-040)

- Risk ID: RISK-SCORE-2026-04-10-040
- Component: src/drift/config.py (SignalWeights), src/drift/signal_mapping.py
- Type: Scoring change (weight activation for 3 previously report-only signals)
- Description: HSC (hardcoded secrets), FOE (fan-out explosion), and PHR (phantom references) are promoted from report-only (weight 0.0) to scoring-active (HSC 0.02, FOE 0.01, PHR 0.02). This means findings from these signals now contribute to the composite drift score, affect module-level severity, and can trigger safe_to_commit blocking in agent loops.
- Trigger examples: Any codebase with hardcoded secrets (HSC), files with >15 imports (FOE), or unresolvable function references (PHR) will now see score impact.
- Impact: Composite scores may increase for affected modules. Agent loops (drift_nudge) will block commits when new HIGH-severity PHR/HSC findings appear.
- Mitigation:
  - Conservative weights (0.01–0.02) limit maximum score contribution per signal.
  - All three signals retain their existing FP-reduction heuristics.
  - 11 new ground-truth fixtures added (4 HSC, 3 FOE, 2 PHR supplement, 2 existing PHR TP).
  - Precision/recall validation on full fixture suite before merge.
  - PHR abbreviation mapping fix ensures drift_nudge/diff correctly reference PHR findings.
- Verification: `pytest tests/test_precision_recall.py -v` (all signals P=1.00 R=1.00), `make check` (full CI suite).
- Residual risk: Medium; real-world FP rates for scoring-active HSC/FOE/PHR not yet validated on external repos. Weight can be reverted to 0.0 without code changes if FP rate is unacceptable.

## 2026-04-12 - Signal type-safety and regression hardening (TVS/SMS/COD/CCC/EDS)

- Risk ID: RISK-SIG-2026-04-12-TYPE
- Component: src/drift/signals/temporal_volatility.py, src/drift/signals/system_misalignment.py, src/drift/signals/cohesion_deficit.py, src/drift/signals/co_change_coupling.py, src/drift/signals/explainability_deficit.py
- Type: Signal implementation robustness / static type safety / regression control
- Description: Optional datetime normalization and helper return typing caused CI mypy failures (`union-attr`, `no-any-return`); additional CI regressions surfaced around CCC helper call compatibility and EDS TS true-positive recall.
- Trigger examples:
  - `history.first_seen` or `history.last_modified` is `None` and timezone conversion is attempted.
  - Token extraction helper returns regex element inferred as `Any` despite `-> str` contract.
  - CCC helper `_resolve_relative_targets()` invoked without newly added `known_files` argument.
  - EDS TS signature dampening suppresses complex functions with explicitly missing tests.
- Impact: Pre-push and CI gate failures; reduced confidence in deterministic signal preprocessing.
- Mitigation:
  - Explicit `isinstance(datetime.datetime)` narrowing before calling `astimezone()`.
  - Explicit `str(...)` coercion in `_leading_token()` to satisfy return contract.
  - Backward-compatible optional `known_files` parameter in `_resolve_relative_targets()`.
  - Evidence-aware TS dampening in EDS (strong dampening only when tests exist, mild when unknown, none when tests missing).
- Verification: `.venv\\Scripts\\python.exe -m mypy src/drift` (green), `.venv\\Scripts\\python.exe -m ruff check src/ tests/` (green), targeted pytest regressions for CCC helper + EDS fixture (green).
- Residual risk: Low; changes are type-safety hardening with no intended heuristic/scoring behavior change.

## 2025-07-26 - ADR-066: Adaptive Recommendation Engine (ARE)

- Risk ID: RISK-ARE-2025-07-26-066
- Component: `src/drift/outcome_tracker.py`, `src/drift/reward_chain.py`, `src/drift/calibration/recommendation_calibrator.py`, `src/drift/recommendation_refiner.py`
- Type: New feature — recommendation quality feedback loop
- Description: ARE adds opt-in outcome tracking, reward scoring, effort calibration, and recommendation refinement. Findings are tracked across runs via JSONL; reward scores drive effort label recalibration and text refinement.
- Trigger: `recommendations.enabled: true` in drift.yaml; otherwise no behavioral change.
- Impact: Positive — recommendations improve over time; effort labels become project-specific. No changes to existing output schema or signal scoring.
- Mitigation:
  - Fully opt-in via config (`recommendations.enabled: false` by default).
  - No PII stored (no author names, emails, or commit hashes in outcome data).
  - Deterministic logic only — no LLM calls, no network requests.
  - Archive rotation (180 days) prevents unbounded file growth.
  - Min-sample threshold (10) prevents noisy calibration.
  - Confidence cap (<0.5) for findings without outcome data.
- Verification:
  - `.venv\Scripts\python.exe -m pytest tests/test_outcome_tracker.py tests/test_reward_chain.py tests/test_recommendation_calibrator.py tests/test_recommendation_refiner.py tests/test_are_integration.py -q --tb=short` (51 passed).
- Residual risk: Low. Fingerprint drift on symbol renames may fragment outcome history; mitigated by archive rotation. Cold-start bias mitigated by confidence cap.
