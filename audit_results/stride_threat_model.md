# STRIDE Threat Model

## 2025-07-27 - ADR-074: Patch Engine — transactional protocol for agent-driven code changes

- Scope: New API endpoints `patch_begin`, `patch_check`, `patch_commit` in [src/drift/api/patch.py](src/drift/api/patch.py). Three new MCP tools in [src/drift/mcp_server.py](src/drift/mcp_server.py). New CLI group `drift patch` in [src/drift/commands/patch_cmd.py](src/drift/commands/patch_cmd.py). New A2A skills in [src/drift/serve/a2a_router.py](src/drift/serve/a2a_router.py). Session extensions in [src/drift/session.py](src/drift/session.py).
- Input path changes: New: `task_id`, `declared_files`, `expected_outcome`, `blast_radius`, `forbidden_paths`, `max_diff_lines` as inputs. `declared_files` is a comma-separated file list from the agent.
- Output path changes: Additive. New `PatchIntent`, `PatchVerdict`, evidence records. All serialised as JSON dicts.
- External interface changes: Additive. Three new MCP tools (`drift_patch_begin`, `drift_patch_check`, `drift_patch_commit`), three new API functions, one new CLI group. Advisory only — no hard enforcement.
- Trust boundary: MCP tool inputs validated: `blast_radius` enum checked before API call. `declared_files` and `forbidden_paths` are path strings compared against git output; no file I/O performed on them.
- STRIDE review:
	- S (Spoofing): No new identity or authentication boundary. Patch tools use same session/repo resolution as existing tools.
	- T (Tampering): Low risk. `declared_files` is an advisory scope declaration by the agent. An agent could declare a wide scope to avoid scope violations; enforcement is advisory by design (ADR-074).
	- R (Repudiation): Improved traceability. Every patch produces an evidence record with intent, verdict, and diff metrics. `patch_history` in session provides audit trail.
	- I (Information Disclosure): Low risk. Diff metrics come from `git diff --numstat`; no new file content exposed beyond what git already reports.
	- D (Denial of Service): Low risk. `patch_check` runs `git diff` which is fast. No full `analyze_repo()` call. No heavy computation.
	- E (Elevation of Privilege): No privilege change. Advisory enforcement — patch verdicts are informational, not blocking.

## 2025-07-22 - ADR-064: Shadow-Verify fuer cross-file-risky edit_kinds

- Scope: Neuer API-Endpunkt [src/drift/api/shadow_verify.py](src/drift/api/shadow_verify.py), neues MCP-Tool `drift_shadow_verify` in [src/drift/mcp_server.py](src/drift/mcp_server.py), Erweiterung von `AgentTask` in [src/drift/models.py](src/drift/models.py), `_derive_task_contract` in [src/drift/api_helpers.py](src/drift/api_helpers.py), `_compute_shadow_verify_scope` in [src/drift/output/agent_tasks.py](src/drift/output/agent_tasks.py).
- Input path changes: Neu: `scope_files` als Eingabe für `drift_shadow_verify` (Comma-separated Dateilisten vom Agent).
- Output path changes: Yes - Tasks mit cross-file-risky edit_kind erhalten `shadow_verify=true` und `completion_evidence.tool="drift_shadow_verify"` im fix_plan-Output.
- External interface changes: Additiv. Neues MCP-Tool, neue API-Funktion, neue Felder in `AgentTask`. Bestehende Felder unveraendert.
- Trust boundary: Neues MCP-Tool-Eingangspfad für `scope_files`. Pfade werden durch `Path(path).resolve()` kanonisiert; Scope-Liste wird als Menge verarbeitet (keine Datei-I/O darauf).
- STRIDE review:
	- S (Spoofing): Kein neue Identitaets- oder Authentisierungsgrenze. `drift_shadow_verify` laedt Konfiguration aus dem Repo-Root wie alle anderen API-Endpunkte.
	- T (Tampering): Niedriges Risiko. `scope_files` beeinflusst nur den Filterbereich; `analyze_repo()` liest das Repo unveraendert. Ein Angreifer koennte den Scope einschraenken, nicht aber Findings faelschen.
	- R (Repudiation): Verbesserte Nachvollziehbarkeit durch explizite `scope_files`-Liste im Response und Telemetrie-Eintrag.
	- I (Information Disclosure): Niedriges Risiko. Findings aus dem Baseline-Store werden gefiltert auf `scope_files`; keine neuen externen Ausgabepfade.
	- D (Denial of Service): Mittleres Risiko. `shadow_verify` laedt eine volle `analyze_repo()`-Analyse. Bei grossen Repos und breitem Scope koennte dies langsam sein. Mitigiert: Scope ist durch Task-Graph-Nachbarn begrenzt; kein automatisches Auslösen ohne Agent-Aufruf.
	- E (Elevation of Privilege): Keine Privileg-Aenderung. Sandbox-Grenzen identisch zu `drift_nudge` und `drift_scan`.



- Scope: Additive Telemetrie-Erweiterung in [src/drift/analyzer.py](src/drift/analyzer.py), [src/drift/pipeline.py](src/drift/pipeline.py), [src/drift/output/json_output.py](src/drift/output/json_output.py), [src/drift/output/rich_output.py](src/drift/output/rich_output.py).
- Input path changes: No.
- Output path changes: Yes - JSON `summary.phase_timing` und Rich-Ausgabe enthalten jetzt standardmaessig Phasenzeiten (discover/parse/git/signals/output/total).
- External interface changes: Additive only. `analysis_duration_seconds` bleibt unveraendert bestehen.
- Trust boundary: Bestehende CLI/JSON-Consumer-Grenze bleibt; keine neue Netzwerk- oder Storage-Boundary.
- STRIDE review:
	- S (Spoofing): Keine neue Identitaets- oder Authentisierungsgrenze.
	- T (Tampering): Niedriges Risiko. Werte werden lokal aus `time.monotonic()` erzeugt; keine extern beschreibbare Datenquelle.
	- R (Repudiation): Verbesserte Nachvollziehbarkeit durch reproduzierbare Phasenaufschluesselung.
	- I (Information Disclosure): Niedriges Risiko. Es werden nur aggregierte Laufzeiten publiziert, keine sensiblen Nutzdaten.
	- D (Denial of Service): Niedriges Risiko. Messung ist O(1) und fuegt nur minimalen Overhead hinzu.
	- E (Elevation of Privilege): Keine Privileg-Aenderung.

## 2026-04-11 - ADR-060: JSON response profiling for analyze output

- Scope: Additive output-shaping change in [src/drift/output/json_output.py](src/drift/output/json_output.py) and [src/drift/commands/analyze.py](src/drift/commands/analyze.py). JSON output now supports `response_detail` (`concise` or `detailed`) for finding payload materialization.
- Input path changes: No.
- Output path changes: Yes - `analysis_to_json` can emit slim or detailed `findings` payloads based on response profile.
- External interface changes: Additive only. New CLI option `--response-detail` for `drift analyze`; default remains `detailed`.
- Trust boundary: Existing CLI/JSON consumer boundary remains; no new storage or network boundary introduced.
- STRIDE review:
	- S (Spoofing): No identity/auth boundary change.
	- T (Tampering): Low risk. Output shaping remains deterministic and local; no writable external channel added.
	- R (Repudiation): Neutral. Output profile is explicit via CLI option and function parameter.
	- I (Information Disclosure): Low risk. `concise` profile reduces exposed detail fields; `detailed` preserves existing visibility.
	- D (Denial of Service): Low-positive. `concise` path reduces serializer work in default API flows.
	- E (Elevation of Privilege): No privilege change.

## 2026-04-11 - ADR-059: Persistenter Nudge-Baseline-Store

- Scope: Additive Persistenz-Erweiterung in [src/drift/incremental.py](src/drift/incremental.py) und [src/drift/api/nudge.py](src/drift/api/nudge.py). `nudge` kann Baselines aus `.drift-cache/nudge_baselines/baseline_<key>.json` laden und damit Full-Scans ueber Prozessgrenzen vermeiden.
- Input path changes: Yes - neuer lokaler Input-Pfad aus `.drift-cache/nudge_baselines/*.json`.
- Output path changes: Yes - neuer lokaler Output-Pfad in dieselben Baseline-Dateien (atomarer Write via temp file + replace).
- External interface changes: Additive only. API-Verhalten bleibt gleich; neu ist nur `baseline_refresh_reason=disk_warm_hit` bei erfolgreichem Persistenz-Hit.
- Trust boundary: Neue lokale Dateigrenze: drift process <-> repository-local nudge baseline artifacts.
- STRIDE review:
	- S (Spoofing): No identity/auth boundary change.
	- T (Tampering): Low-Medium risk. Baseline-Dateien koennen lokal manipuliert werden. Mitigation: key-bound Load (HEAD + config fingerprint + schema version), defensive Deserialisierung, hard invalidate via key mismatch.
	- R (Repudiation): Improved traceability via explicit refresh reason (`disk_warm_hit`) und key-gebundene Artefakte.
	- I (Information Disclosure): Low risk. Baseline speichert nur bereits vorhandene Analysemetadaten und Findings in repo-lokalem Cache.
	- D (Denial of Service): Low risk. Korrupte Baseline-Dateien koennen zu Cache-Miss fuehren, nicht zu Analyseabbruch; Fallback ist Full-Scan.
	- E (Elevation of Privilege): No privilege change. Dateizugriffe erfolgen mit denselben Rechten wie der Drift-Prozess.

## 2026-04-11 - ADR-058: Inkrementeller persistenter Git-History-Index

- Scope: Additive Ingestion-Performance-Erweiterung in [src/drift/ingestion/git_history.py](src/drift/ingestion/git_history.py) und [src/drift/pipeline.py](src/drift/pipeline.py). Bei aktiviertem Flag wird Commit-History aus lokalem Cache (`manifest.json` + `commits.jsonl`) gelesen und nur Delta-History seit letztem Head nachgeladen.
- Input path changes: Yes - neuer lokaler Input-Pfad aus `.drift-cache/<git_history_index_subdir>/manifest.json` und `.drift-cache/<git_history_index_subdir>/commits.jsonl`.
- Output path changes: Yes - neuer lokaler Output-Pfad in dieselben Cache-Dateien (Manifest rewrite, Commit-Append bei linearem Head-Fortschritt).
- External interface changes: Additive only. Neues Config-Flag `git_history_index_enabled` und `git_history_index_subdir`; Legacy-Pfad bleibt unveraendert bei deaktiviertem Flag.
- Trust boundary: Neue lokale Dateigrenze: drift process <-> repository-local history index artifacts.
- STRIDE review:
	- S (Spoofing): No identity/auth boundary change.
	- T (Tampering): Low-Medium risk. Lokale Cache-Dateien koennen manuell veraendert werden. Mitigation: Schema-/Repo-/Parameter-Validierung im Manifest, defensive Deserialisierung, ancestry-check (`merge-base --is-ancestor`) und Full-Rebuild-Fallback bei Inkonsistenz.
	- R (Repudiation): Improved traceability via manifest fields (`head`, `updated_at`, `params`) und deterministische Rebuild-Regeln.
	- I (Information Disclosure): Low risk. Persistiert nur Commit-Metadaten, die bereits ueber lokale Git-Historie verfuegbar sind.
	- D (Denial of Service): Low risk. Korrupte oder riesige Indexdateien koennen Warm-Path verlangsamen; Mitigation: parse-fallback + Full-Rebuild ohne Hard-Fail der Analyse.
	- E (Elevation of Privilege): No privilege change. Dateizugriffe laufen mit denselben Rechten wie der Drift-Prozess.

## 2026-04-11 - ADR-054: File-Discovery Manifest Cache (Hybrid Invalidation)

- Scope: Additive ingestion performance path in [src/drift/ingestion/file_discovery.py](src/drift/ingestion/file_discovery.py). Discovery results can be loaded from `.drift-cache/file_discovery_manifest.json` when invalidation state matches.
- Input path changes: Yes - new local cache input path. Discovery now reads a persisted JSON manifest from repository-local cache dir.
- Output path changes: Yes - discovery now writes a manifest file with cache entries, invalidator metadata, and serialized file descriptors.
- External interface changes: Additive only. Public discovery semantics and analyzer outputs remain unchanged.
- Trust boundary: New local file trust boundary: drift process <-> repository-local cache artifact (`.drift-cache/file_discovery_manifest.json`).
- STRIDE review:
	- S (Spoofing): No identity/auth boundary change.
	- T (Tampering): Low risk. Manifest may be modified manually or by tooling. Mitigation: strict schema/version checks, defensive deserialization, safe fallback to full re-scan on mismatch.
	- R (Repudiation): Improved operational traceability via explicit invalidator metadata (`git_head` or `mtime`).
	- I (Information Disclosure): Low risk. Manifest stores relative paths and file metadata already derivable from repository contents.
	- D (Denial of Service): Low risk. Corrupt/oversized manifest could force cache misses. Mitigation: bounded entry count and resilient fallback path.
	- E (Elevation of Privilege): No privilege change. Cache read/write uses the same filesystem permissions as the invoking user.

## 2026-06-15 — Phase 3: TypeScript Verständlichkeit & Einführbarkeit

- Scope: Four additive changes for TypeScript support visibility: (1) `language` field on Finding model with auto-inference from file extension, (2) `skipped_languages` in JSON summary + new Rich warning panel, (3) `ts_enabled` parameter on `discover_files()` wired to `DriftConfig.languages.typescript`, (4) `LanguagesConfig` sub-model in config. No signal or scoring changes.
- Input path changes: Yes — `discover_files()` gains `ts_enabled: bool = True` parameter. When False, removes "typescript" from supported-language set before scanning. No new external file input.
- Output path changes: Yes — (a) `_finding_to_dict()`, `_finding_compact_dict()` and `findings_to_sarif()` emit new `language` field from Finding model. (b) JSON summary gains `skipped_languages` dict. (c) Rich `render_summary()` gains a yellow warning line when `analysis.skipped_languages` is non-empty. All derived from existing in-process data.
- External interface changes: Additive only. New `language` field in JSON/SARIF output (nullable, backward-compatible). New `languages.typescript: bool` config key (defaults to `true`, backward-compatible). New `skipped_languages` in JSON summary (nullable). No existing field semantics changed.
- Trust boundary: No new trust boundary. `Finding.language` is derived from `file_path.suffix` via a hardcoded ClassVar dict — no user input. `LanguagesConfig.typescript` is a Pydantic-validated boolean from drift.yaml. Rich output warning uses `Text.assemble()` (no markup injection risk).
- STRIDE review:
	- S (Spoofing): No identity or authentication boundary change.
	- T (Tampering): No risk. Language inference is a pure suffix→string lookup. Config validation is Pydantic-enforced.
	- R (Repudiation): Improved — `language` field provides per-finding provenance of which parser was used.
	- I (Information Disclosure): No new data classes. `language` is a simple string derived from file path already visible in output.
	- D (Denial of Service): No risk. Suffix lookup is O(1); Rich warning is a single print call.
	- E (Elevation of Privilege): No privilege change.

## 2026-04-12 - ADR-053: External Report Import (drift import)

- Scope: New `drift import` CLI command reads external tool reports (SonarQube, pylint, CodeClimate) as JSON and compares findings side-by-side with Drift's own analysis. Read-only comparison — imported findings do NOT affect drift score or severity.
- Input path changes: Yes — new external file input path. `load_external_report()` in `src/drift/ingestion/external_report.py` reads user-supplied JSON files via `Path.read_text()` + `json.loads()`.
- Output path changes: Yes — new Rich comparison table and optional JSON comparison output via `drift import --json`.
- External interface changes: Additive only. New `drift import <report> --format <tool>` command. Existing commands and formats unchanged.
- Trust boundary: New trust boundary at external JSON file ingestion. User-supplied JSON is parsed by stdlib `json.loads()` (safe, no code execution). Parsed data flows through adapter functions that extract only expected fields with `.get()` defaults — no dynamic attribute access, no `eval`, no `exec`. Imported `Finding` objects have `score=0.0` and are never fed into scoring pipeline.
- STRIDE review:
	- S (Spoofing): No identity or authentication boundary change.
	- T (Tampering): Low risk. Malformed JSON could produce findings with misleading `file_path` values in comparison output. Mitigation: `file_path` is only used for set-intersection comparison, not for file I/O operations.
	- R (Repudiation): Improved — comparison output provides auditable evidence of what an external tool found vs. Drift's analysis.
	- I (Information Disclosure): No risk. External report content is shown in comparison output only. No data from external reports is persisted or transmitted.
	- D (Denial of Service): Low risk. Very large JSON files could consume memory. Mitigation: standard `json.loads()` has inherent memory limits; no recursion in adapter logic; finding lists are O(n).
	- E (Elevation of Privilege): No privilege change. Imported findings are read-only comparison data with `score=0.0`.

## 2026-04-11 - ADR-052: PR-Comment Output + SARIF Enrichment + Markdown Compact + CSV signal_label

- Scope: Four additive output-layer improvements: (1) new `--format pr-comment` formatter generating compact Markdown for PR comments/Slack, (2) SARIF `message.text` enriched with `generate_recommendation()` title and rule `help` field, (3) `analysis_to_markdown()` gains `include_modules`/`include_signal_coverage` params wired to `--compact` CLI flag, (4) CSV output gains `signal_label` column (breaking column-index change). No signal, scoring, or ingestion changes.
- Input path changes: No — all changes are pure output composition using existing in-process `RepoAnalysis`.
- Output path changes: Yes — new formatter `pr_comment.py` and enriched SARIF/CSV/Markdown output paths.
- External interface changes: Additive (`--format pr-comment`) plus breaking CSV column-index change (documented in CHANGELOG). JUnit/LLM/SARIF/Markdown choices unchanged in semantics.
- Trust boundary: No new trust boundary. `analysis_to_pr_comment()` calls `generate_recommendation()` and `get_meta()` — both pure in-process lookups with no I/O, no sys.path manipulation, no external calls. SARIF `help` field populates from the same recommender dictionary. CSV and Markdown formatters remain pure string composition.
- STRIDE review:
	- S (Spoofing): No identity or authentication boundary change.
	- T (Tampering): No risk. All outputs are derived from pre-computed in-process analysis data. `generate_recommendation()` is a pure lookup with no side effects.
	- R (Repudiation): Improved — PR-comment format provides a shareable, auditable snapshot of analysis state for PR review workflows.
	- I (Information Disclosure): No new data classes exposed. PR-comment renders same finding fields (signal_type, severity, score, file_path, title, fix) already present in JSON/markdown output. SARIF rule `help.markdown` renders only recommender description text, no internal state.
	- D (Denial of Service): No risk. All formatters are pure string/list composition with no external calls, no recursion, and O(n) complexity on findings list.
	- E (Elevation of Privilege): No privilege change.


- Scope: Five additive DX features: (1) `drift completions` generates shell completion scripts, (2) `--format junit` JUnit XML output, (3) `--format llm` token-efficient AI output, (4) `drift ci` zero-config CI command with auto-environment detection, (5) `drift gate` alias for `drift check`. No signal, scoring, or ingestion changes.
- Input path changes: Yes — `drift ci` reads CI environment variables (`GITHUB_ACTIONS`, `GITLAB_CI`, `CIRCLECI`, `BUILD_BUILDID`, `CI`) for auto-detection. No user-supplied file input.
- Output path changes: Yes — two new output formatters (`junit_output.py`, `llm_output.py`) and one new CLI dispatch path (`ci.py`). All consume existing in-process `RepoAnalysis` data.
- External interface changes: Additive only. New `--format junit` and `--format llm` choices in `analyze` + `check`. New `drift ci`, `drift completions`, `drift gate` commands. Existing formats and commands unchanged.
- Trust boundary: No new trust boundary. CI env-var reading uses `os.getenv()` only. Output formatters are pure string/XML composition with no external calls. Completions use Click's built-in `shell_complete` template — no shell execution.
- STRIDE review:
	- S (Spoofing): No identity or authentication boundary change. CI env vars are read-only and not trusted for security decisions.
	- T (Tampering): No risk. All outputs are derived from existing pre-computed analysis data. JUnit uses `xml.etree.ElementTree` with proper escaping.
	- R (Repudiation): Improved — JUnit and LLM outputs provide additional audit-compatible formats for CI and agent workflows.
	- I (Information Disclosure): No new data classes exposed. JUnit/LLM render same finding fields as existing JSON/CSV/SARIF outputs.
	- D (Denial of Service): No risk. All formatters are pure computation, no external calls, no file reads beyond existing analysis.
	- E (Elevation of Privilege): No privilege change. CI detection is purely informational.

## 2026-04-11 - ADR-046: Markdown CLI format + Guidance footer

- Scope: `drift analyze --format markdown` wires the existing `analysis_to_markdown()` formatter to CLI output. Rich output gains a "What's Next?" guidance footer for unconfigured repos. No new input paths, no scoring changes.
- Input path changes: No.
- Output path changes: Yes — one new CLI format target (markdown via `_emit_machine_output`), one new Rich panel (`_render_guidance_footer`) appended to `render_full_report`.
- External interface changes: Additive only. New `--format markdown` choice value. Existing formats and `--quiet` behavior unchanged.
- Trust boundary: No new trust boundary. Markdown formatter renders in-process analysis data exclusively. No external calls, no file reads beyond what `analyze_repo` already performs.
- STRIDE review:
	- S (Spoofing): No identity or authentication boundary change.
	- T (Tampering): No risk. Output-only addition using existing pre-computed analysis data.
	- R (Repudiation): Improved — markdown output provides shareable, self-contained audit artifact for PR comments and wikis.
	- I (Information Disclosure): No new data classes exposed. Markdown report renders same fields as Rich and JSON outputs.
	- D (Denial of Service): No risk. Formatter is pure string composition with no external calls.
	- E (Elevation of Privilege): No privilege change.

## 2026-04-11 - ADR-041: PHR Runtime Import Attribute Validation

- Scope: Optional runtime attribute validation for the Phantom Reference Signal (PHR). When `phr_runtime_validation: true`, PHR calls `importlib.import_module()` followed by `hasattr(mod, name)` to verify that `from X import Y` targets an existing attribute on an installed third-party module. Gated behind opt-in config flag (default: false). No scoring or output changes.
- Input path changes: Yes — new runtime import path. `import_module()` executes third-party package `__init__.py` code to load the module into the analysis process.
- Output path changes: No — findings use existing PHR finding structure with an additional `runtime_validated` metadata flag.
- External interface changes: Additive only. New config key `thresholds.phr_runtime_validation` (default false). Existing behavior unchanged when disabled.
- Trust boundary: **New trust boundary**: drift analysis process ↔ third-party package code via `importlib.import_module()`. Unlike `find_spec()` (Phase B, ADR-040) which only checks metadata, `import_module()` actually executes module initialization code.
- STRIDE review:
	- S (Spoofing): No identity or authentication boundary change.
	- T (Tampering): **Medium risk**. A malicious or compromised third-party package could execute arbitrary code during `import_module()`. Mitigations: (1) opt-in only — disabled by default, (2) daemon thread with 5s timeout, (3) no `exec`/`eval`/`compile` in drift's own code, (4) skips project-internal and TYPE_CHECKING imports, (5) sys.modules fast path avoids re-import of already-loaded modules. Residual risk accepted because the user explicitly opts in and the imported packages are already present in the analyzed project's dependency tree.
	- R (Repudiation): Improved — runtime validation provides ground-truth evidence for phantom reference findings, reducing false positives from version-mismatch scenarios.
	- I (Information Disclosure): Low risk. Module import may trigger side effects that log or transmit data, but this is inherent to the package being analyzed and already occurs when the project runs normally.
	- D (Denial of Service): Low risk. Daemon thread with configurable timeout (default 5s) prevents hanging imports from blocking analysis. Module imports that exceed the timeout return None and the attribute check is skipped gracefully.
	- E (Elevation of Privilege): No privilege change. Import runs with same OS-level permissions as drift CLI user. No subprocess or network calls initiated by drift itself.

## 2026-04-10 - Output channel extension: session report + TUI visualize

- Scope: Additive CLI output surfaces for session effectiveness rendering (`drift session-report`) and optional interactive dashboard rendering (`drift visualize`) via `textual`.
- Input path changes: No new external input boundary. `session-report` reads local `.drift-session-*.json` files already produced by drift workflows.
- Output path changes: Yes - new terminal rendering paths via `session_renderer.py` and `tui_renderer.py`.
- External interface changes: Additive only. Existing analyze/check/scan output contracts remain unchanged.
- Trust boundary: No new network or privilege boundary. Optional dependency loading (`textual`) occurs in-process and is explicitly guarded.
- STRIDE review:
	- S (Spoofing): No identity or authentication boundary change.
	- T (Tampering): Low risk. Renderers consume in-process analysis/session data and local files; malformed session files are handled with explicit parse errors.
	- R (Repudiation): Improved readability of session KPI/audit context, no change to provenance model.
	- I (Information Disclosure): No new data classes. Outputs display existing drift/session fields only.
	- D (Denial of Service): Low risk. TUI path is optional and user-invoked; non-availability of `textual` fails fast with a clear message.
	- E (Elevation of Privilege): No privilege boundary change.

## 2026-04-10 - ADR-043: Shared First-Run Summary Contract

- Scope: Additive first-run guidance block shared by `drift analyze --format json`, Rich terminal output, and `drift status`. The change introduces a common prioritization helper in `finding_rendering.py`, a new `first_run` top-level JSON block in `json_output.py`, and a `Start Here` / `Starte hier` panel in `rich_output.py`. `status.py` now reuses the same prioritized findings and next-step summary instead of local sorting.
- Input path changes: None.
- Output path changes: Yes - existing CLI JSON, Rich terminal output, and guided status JSON gain additive guidance fields derived from existing findings.
- External interface changes: Additive only. Existing findings, fix_first, and status fields remain; new fields are `first_run` in analyze JSON plus `why_this_matters` / `next_step` in status JSON.
- Trust boundary: No new trust boundary. All new text is derived deterministically from existing in-process analysis data; no new network, subprocess, or filesystem write path introduced.
- STRIDE review:
	- S (Spoofing): No identity or authentication boundary change.
	- T (Tampering): Low risk. Guidance is derived from existing findings and deterministic prioritization rules. A malicious change would need to tamper with the underlying repository analysis data already in scope.
	- R (Repudiation): Improved. `analyze`, `status`, and JSON consumers now point to the same first recommended action instead of command-specific heuristics, reducing ambiguity in follow-up decisions.
	- I (Information Disclosure): No new sensitive data classes. The new block only reshapes existing finding metadata and recommendations.
	- D (Denial of Service): Negligible overhead. The helper performs bounded in-memory sorting/deduplication over the already-produced finding list.
	- E (Elevation of Privilege): No privilege boundary change.

## 2026-06-01 - ADR-042: Schema Evolution and Finding-ID Promotion

- Scope: Output schema unification (`OUTPUT_SCHEMA_VERSION` in `models.py`) from split "1.1"/"2.0" to unified "2.1". Promotion of `finding_id` (16-char SHA256 fingerprint) into all output channels: CLI JSON (`json_output.py`), SARIF (`findings_to_sarif`), API helpers (`api_helpers.py`), and agent tasks. Extension of `drift explain` and MCP `drift_explain` to accept finding fingerprints for finding-level drill-down. New `drift.output.schema.json` published for agent-side contract validation.
- Input path changes: Yes — `explain()` in `src/drift/api/explain.py` now accepts fingerprint strings as `topic`, triggering a repo scan to resolve the finding.
- Output path changes: Yes — all JSON/SARIF/API outputs gain a `finding_id` field; `schema_version` changes from "1.1"/"2.0" to "2.1"; new `drift.output.schema.json` file.
- External interface changes: Additive. `finding_id` is a new field; `schema_version` bumped; no fields removed or renamed.
- Trust boundary: No new trust boundary. Fingerprint-based explain reuses existing `analyze_repo()` pipeline and config loading. No new subprocess, network, or filesystem access patterns.
- STRIDE review:
	- S (Spoofing): No risk change. Finding fingerprints are deterministic content hashes — no identity or authentication boundary involved.
	- T (Tampering): Low risk. Fingerprints are SHA256-derived from `(signal_type, file_path, start_line, end_line, title)` — content-based and deterministic. An attacker would need to modify repository content to alter fingerprints.
	- R (Repudiation): Improved. Stable `finding_id` enables cross-run finding correlation, baseline tracking, and audit trails. Agents can reference specific findings unambiguously.
	- I (Information Disclosure): No new data classes. `finding_id` is derived from already-public finding fields. The explain endpoint returns the same finding data already available in scan output.
	- D (Denial of Service): Low risk. Fingerprint-based explain triggers a full `analyze_repo()` call — same cost as a normal scan. No amplification vector beyond existing scan behavior.
	- E (Elevation of Privilege): No privilege change. All operations run with the same OS-level permissions.

## 2026-04-12 - ADR-034: Causal Attribution via Git Blame

- Scope: New optional enrichment pipeline (`src/drift/attribution.py`, `src/drift/ingestion/git_blame.py`) that executes `git blame --porcelain` as a subprocess to attribute findings to commits, authors, and branches. Opt-in via `attribution.enabled: true` in config. No signal, scoring, or ingestion logic changes — purely post-scoring enrichment.
- Input path changes: Yes — new subprocess input path. `git blame --porcelain` and `git log --format=%s` are invoked per analyzed file via `subprocess.run()` with `capture_output=True`.
- Output path changes: Yes — `Finding.attribution` field serialized in JSON (`attribution` dict), SARIF (`drift:attribution` property), and Rich terminal output (footer line).
- External interface changes: Additive only; existing findings structure unchanged. New `attribution` field is null when feature is disabled.
- Trust boundary: drift process ↔ git subprocess. Relies on repository path integrity (same trust boundary as existing `git log` calls in `src/drift/ingestion/git_history.py`).
- STRIDE review:
	- S (Spoofing): Low risk. Git blame output reflects repository history which may contain spoofed author identities (standard git limitation). No new authentication boundary.
	- T (Tampering): Low risk. Subprocess invoked with explicit arguments, no shell=True. File paths come from existing ingestion pipeline (already validated). Timeout enforced per file (default 3s).
	- R (Repudiation): Improved — attribution provides commit-level provenance for each finding, enabling audit trail.
	- I (Information Disclosure): Low risk. Author names and emails are already in git history; attribution surfaces them in analysis output. Users opt in explicitly.
	- D (Denial of Service): Low risk. ThreadPoolExecutor capped at 4 workers, per-file timeout of 3s, in-memory LRU cache (500 entries). Large monorepo performance bounded.
	- E (Elevation of Privilege): No privilege change. Git subprocess runs with same OS-level permissions as drift CLI user.

## 2026-04-09 - ADR-029: Preflight diagnosis and markdown report export

- Scope: Additiver Output-Pfad fuer vorstrukturierte Preflight-Diagnosen und den Markdown-Report-Export (`src/drift/preflight.py`, `src/drift/output/markdown_report.py`) inklusive zugehoeriger Agent-Hinweisaufbereitung.
- Input path changes: Nein (nutzt bestehende Analyseeingaben).
- Output path changes: Ja (zusatzlicher menschenlesbarer Report-Kanal).
- External interface changes: Additiv; bestehende JSON/CLI-Ausgaben bleiben unveraendert.
- STRIDE review:
	- S (Spoofing): Keine neue Identitaets- oder Authentisierungsgrenze.
	- T (Tampering): Niedriges Risiko; Report-Inhalte werden deterministisch aus bestehenden Findings aufgebaut.
	- R (Repudiation): Verbesserte Nachvollziehbarkeit durch explizite Diagnose-/Naechste-Schritte-Sektionen im Report.
	- I (Information Disclosure): Kein neuer Datentyp; der Report repraesentiert vorhandene Analyseinformationen in anderer Form.
	- D (Denial of Service): Geringer Overhead durch zusaetzliches Rendering im Vergleich zur bestehenden Analysepipeline.
	- E (Elevation of Privilege): Keine Privileggrenze geaendert.

## 2026-04-08 - ADR-026: A2A Agent Card and HTTP Serve Endpoint

- Scope: New optional HTTP server (`drift serve`) exposing `GET /.well-known/agent-card.json` (A2A v1.0 Agent Card) and `POST /a2a/v1` (JSON-RPC 2.0 skill dispatch). Backed by FastAPI + uvicorn as optional dependencies (`pip install drift-analyzer[serve]`). 8 core analysis skills exposed: scan, diff, explain, fix_plan, validate, nudge, brief, negative_context. No signal, scoring, or ingestion changes.
- Input path changes: Yes — new HTTP input path. Clients send JSON-RPC 2.0 requests with repo paths and skill parameters over HTTP.
- Output path changes: Yes — new HTTP output path. Analysis results returned as JSON-RPC responses over HTTP. Agent card returned as A2A JSON.
- External interface changes: Entirely new, additive. No existing CLI/MCP/API interfaces changed.
- Trust boundary: HTTP client ↔ drift serve process. First network-accessible trust boundary in drift.
- STRIDE review:
	- S (Spoofing): Medium risk. No authentication in v1 — any client that can reach the HTTP port can invoke analysis. Mitigation: default bind to `127.0.0.1` (localhost-only); network exposure only via explicit `--host 0.0.0.0`. Users must deploy behind authenticating reverse proxy for production network exposure.
	- T (Tampering): Medium risk. `path` parameter in A2A requests could be used for path traversal. Mitigation: `_validate_repo_path()` resolves via `os.path.realpath(os.path.normpath(...))` and verifies `os.path.isdir()` before passing to any API function. Only existing directories are accepted.
	- R (Repudiation): Low risk. JSON-RPC responses include request IDs for correlation. No authentication means no attributable identity for requests.
	- I (Information Disclosure): Medium risk. Scan results, findings, anti-patterns, and fix plans are exposed over HTTP. Mitigation: localhost-only default prevents remote information leakage. Sensitive repository analysis data stays on the local machine unless intentionally exposed.
	- D (Denial of Service): Low risk. Full drift analysis is CPU-intensive — an attacker on the network could trigger repeated scans. Mitigation: localhost-only default; no concurrent request protection in v1 (acceptable for single-user localhost usage).
	- E (Elevation of Privilege): Low risk. Server runs with the same OS-level privileges as the drift CLI user. No privilege escalation path. `_validate_repo_path()` prevents analysis of arbitrary filesystem paths (must be existing directories).

## 2026-04-11 - ADR-024: Machine-Readable Next-Step Contracts

- Scope: Three additive JSON fields (`next_tool_call`, `fallback_tool_call`, `done_when`) on every agent-oriented API response (scan, diff, fix_plan, nudge, brief, negative_context). MCP session enrichment injects `session_id` into contract params. Error responses gain optional `recovery_tool_call`. No signal, scoring, or ingestion changes.
- Input path changes: None.
- Output path changes: Yes (six API responses gain three additive fields; MCP `_enrich_response_with_session` propagates `session_id` into contract params; `_error_response` gains optional `recovery_tool_call`; `drift_session_start` gains contract fields).
- External interface changes: Additive only; `schema_version` remains "2.0", no fields removed/renamed.
- STRIDE review:
	- S (Spoofing): No identity or trust-boundary change. Contracts reference existing tool names only.
	- T (Tampering): Low risk; contract fields are deterministic, derived from response state (finding count, degradation status, batch eligibility). Agents remain advisory consumers — contract execution is not enforced server-side.
	- R (Repudiation): Improved traceability — each contract encodes the exact tool + params the API recommends, replacing ambiguous freeform text.
	- I (Information Disclosure): No new data classes exposed; `session_id` is already present in session-enriched responses.
	- D (Denial of Service): Negligible; three small dict fields per response, constant-time construction.
	- E (Elevation of Privilege): No privilege boundary change. Contracts suggest tool calls but do not execute them.

## 2026-04-08 - ADR-023: Canonical Examples in Agent-Output (fix_plan + brief)

- Scope: Additive output fields in guardrails (`preferred_pattern`) and fix_plan tasks (`canonical_refs`). No signal, scoring, or ingestion changes. Data sourced from existing NegativeContext.canonical_alternative and Finding.metadata.canonical_exemplar.
- Input path changes: None.
- Output path changes: Yes (brief guardrails gain `preferred_pattern` field and optional `PREFERRED:` prompt line; fix_plan tasks gain `canonical_refs` array).
- External interface changes: Additive only; `schema_version` remains "2.0", no fields removed/renamed.
- STRIDE review:
	- S (Spoofing): No identity or trust-boundary change.
	- T (Tampering): No risk; new fields are derived deterministically from existing analysis data. Comment-prefix stripping uses bounded substring operations only.
	- R (Repudiation): Improved traceability — each canonical_ref carries `source_signal` attribution.
	- I (Information Disclosure): No new data classes exposed; `canonical_exemplar` already present in Finding.metadata, `canonical_alternative` already in NegativeContext serialization.
	- D (Denial of Service): Negligible; max 3 refs per task, preferred_pattern capped at 200 chars.
	- E (Elevation of Privilege): No privilege boundary change.

## 2026-04-09 - ADR-021: Batch-Dominant Fix-Loop Orchestration

- Scope: Agent instruction text alignment across scan, fix_plan, diff, nudge API responses and MCP `_BASE_INSTRUCTIONS`. No structural, scoring, or schema changes — only `agent_instruction` plaintext strings modified.
- Input path changes: None.
- Output path changes: Yes (agent_instruction text content changed in scan, fix_plan, diff, nudge responses and MCP system prompt).
- External interface changes: None; `schema_version` remains "2.0", no fields added/removed.
- STRIDE review:
	- S (Spoofing): No identity or trust-boundary change.
	- T (Tampering): No risk change; instruction texts are non-binding agent guidance.
	- R (Repudiation): No change; all instructions traceable to source code constants.
	- I (Information Disclosure): No new data exposed; instructions reference existing API concepts (batch_eligible, nudge, diff).
	- D (Denial of Service): No risk; text-only changes with no computational impact.
	- E (Elevation of Privilege): No privilege boundary change.

## 2026-04-08 - Agent Repair Workflow Quick Wins (V-3a/V-5/V-6/V-8a/V-13)

- Scope: Additive output enhancements for agent repair workflows: `finding_count_by_signal` in scan, `expected_score_delta` in fix_plan tasks, `dependency_depth` metadata in tasks, `signals`/`exclude_signals` params on nudge, increased negative-context depth (3→5), baseline-warming docs in MCP prompt.
- Input path changes: None (nudge gains optional filter params — existing calls unaffected).
- Output path changes: Yes (scan, fix_plan, and nudge JSON payloads gain additive fields).
- External interface changes: Additive only; existing fields and semantics stay intact.
- STRIDE review:
	- S (Spoofing): No identity or trust-boundary change.
	- T (Tampering): No risk change; all new fields are derived from existing analysis data.
	- R (Repudiation): Improved traceability through per-signal finding counts and score-delta attribution.
	- I (Information Disclosure): No new sensitive data; fields expose pre-existing analysis metrics.
	- D (Denial of Service): Negligible overhead (Counter aggregation, BFS depth on small task graphs).
	- E (Elevation of Privilege): No privilege boundary change.

## 2026-04-06 - Stable signal_abbrev_map in scan/analyze JSON (Issue #183)

- Scope: Additive output metadata field `signal_abbrev_map` in both `scan` and
  `analyze --format json` payloads for stable abbreviation-to-canonical mapping.
- Input path changes: None.
- Output path changes: Yes (existing JSON payloads gain one additive top-level field).
- External interface changes: Additive only; existing fields and semantics stay intact.
- STRIDE review:
	- S (Spoofing): No identity or trust-boundary change.
	- T (Tampering): Risk decreases because consumers can verify mapping from tool output
	  instead of maintaining mutable external tables.
	- R (Repudiation): Improved traceability of signal joins across commands.
	- I (Information Disclosure): No new sensitive data; mapping is static taxonomy metadata.
	- D (Denial of Service): Negligible overhead (small constant-size dictionary).
	- E (Elevation of Privilege): No privilege boundary change.

## 2026-04-05 - Scan Cross-Validation Output Metadata (Issue #171)

- Scope: Additive Felder im `scan`-Output für stabile Cross-Validation (`signal_id`, `signal_abbrev`, `signal_type`, `severity_rank`, `fingerprint`) sowie Top-Level-Block `cross_validation`.
- Input path changes: None.
- Output path changes: Yes (bestehende Scan-JSON-Payloads erhalten additive Felder).
- External interface changes: Additiv; bestehende Felder bleiben unverändert.
- STRIDE review:
	- S (Spoofing): Keine Identitätsgrenze geändert.
	- T (Tampering): Risiko sinkt durch deterministischen `fingerprint` und explizites Feld-Mapping für maschinelle Korrelation.
	- R (Repudiation): Verbesserte Nachvollziehbarkeit durch stabile Finding-Identifikation und Severity-Ranking.
	- I (Information Disclosure): Keine neuen sensitiven Daten; nur abgeleitete Metadaten aus bestehenden Findings.
	- D (Denial of Service): Kein relevanter Einfluss; nur konstante Zusatzfelder pro Finding.
	- E (Elevation of Privilege): Keine Privileggrenze geändert.

## 2026-04-05 - drift_score_scope output metadata (Issue #159)

- Scope: Additive machine-output field `drift_score_scope` next to `drift_score` across scan/analyze/check/baseline and related API payloads.
- Input path changes: None.
- Output path changes: Yes (existing JSON payloads include one additional descriptive field).
- External interface changes: Output schema is additive; existing `drift_score` field remains unchanged.
- STRIDE review:
	- S (Spoofing): No identity boundary change.
	- T (Tampering): Mitigated by explicit scope descriptor; reduces semantic misuse of unchanged numeric values across contexts.
	- R (Repudiation): Improved auditability because score provenance is explicit in payloads.
	- I (Information Disclosure): No new sensitive data; field contains only scope metadata.
	- D (Denial of Service): No meaningful runtime impact (constant-size string generation).
	- E (Elevation of Privilege): No privilege boundary change.

## 2026-07-18 - Security audit: path traversal + input validation

- Scope: API parameter validation for baseline_file and config_file in diff() and validate().
- Input path changes: Yes — baseline_file and config_file now validated against repo root boundary.
- Output path changes: None.
- External interface changes: diff() and validate() now return DRIFT-1003 error for out-of-scope paths.
- STRIDE review:
	- S (Spoofing): No identity boundary change.
	- T (Tampering): Path sandbox prevents reading files outside repository root via crafted paths.
	- R (Repudiation): Error response logs invalid path attempt in telemetry.
	- I (Information Disclosure): Mitigated — prevents reading arbitrary files via ../../ traversal in baseline_file/config_file.
	- D (Denial of Service): No change.
	- E (Elevation of Privilege): No privilege boundary change.

## 2026-07-18 - Security audit: file_discovery OS error handling

- Scope: ingestion/file_discovery.py glob and stat operations.
- Input path changes: None (same file system traversal).
- Output path changes: None.
- External interface changes: discover_files() now gracefully degrades on inaccessible paths instead of crashing.
- STRIDE review:
	- S/T/R/I/E: No change.
	- D (Denial of Service): Mitigated — broken symlinks or permission-denied entries no longer crash discovery; logged and skipped.

## 2026-04-03 - CSV output channel added (Issue #14)

- Scope: New machine-readable output path via `--format csv`.
- Input path changes: None.
- Output path changes: Yes (stdout/file sink now supports CSV serialization).
- External interface changes: CLI now accepts `csv` for analyze/check output format.
- STRIDE review:
	- S (Spoofing): No new identity boundary.
	- T (Tampering): Output content is derived from existing findings only; no new write target type.
	- R (Repudiation): Deterministic row ordering improves reproducibility of exported evidence.
	- I (Information Disclosure): No additional sensitive fields beyond existing machine outputs.
	- D (Denial of Service): O(n) serialization, equivalent class to existing JSON/SARIF exporters.
	- E (Elevation of Privilege): No privilege boundary change.

## 2026-04-03 - Baseline

No new trust-boundary changes introduced by Issue #121.

- Scope: Internal DIA markdown parsing heuristics only.
- Input path changes: None.
- Output path changes: None.
- External interface changes: None.

## 2026-04-10 - AST-based logical location in findings (ADR-039)

- Scope: New `logical_location` field on Finding model, exposed in JSON, SARIF, and AgentTask outputs.
- Input path changes: None (uses existing ParseResult data from AST parsing).
- Output path changes: Yes — JSON findings include new `logical_location` object; SARIF results include `logicalLocations` array per §3.33; AgentTask/fix_plan/nudge responses include `logical_location` dict.
- External interface changes: Output schema is additive; all existing fields remain unchanged. No field removals.
- STRIDE review:
        - S (Spoofing): No identity boundary change.
        - T (Tampering): No new write targets; output is derived from existing parsed AST data.
        - R (Repudiation): Improved — findings carry richer provenance (class/method/module context).
        - I (Information Disclosure): No new sensitive data; field contains only structural code identifiers already visible in source.
        - D (Denial of Service): Negligible runtime impact — interval-index lookup is O(n) over existing ParseResult.
        - E (Elevation of Privilege): No privilege boundary change.

## 2025-07-26 - ARE: Adaptive Recommendation Engine (ADR-066)

- Scope: New opt-in subsystem — outcome tracking (JSONL), reward chain, effort calibration, recommendation refinement. New CLI subcommands under `drift calibrate`. New `RecommendationsConfig` in config model. Integration hook in `analyze` command.
- STRIDE review:
        - S (Spoofing): No identity boundary change. Outcomes contain only structural fingerprints, not user identities.
        - T (Tampering): New write target: `.drift/outcomes.jsonl` and `.drift/effort_calibration.json`. Both are local, repo-scoped files with append-only (JSONL) or overwrite (JSON) semantics. No remote writes.
        - R (Repudiation): Outcomes carry ISO-8601 timestamps for reported_at and resolved_at. Calibration entries carry calibrated_at timestamp. Sufficient for audit trail.
        - I (Information Disclosure): No PII stored — no author names, emails, commit hashes, or file content. Only signal types, fingerprints (SHA-256 of structural identifiers), and timing data.
        - D (Denial of Service): Outcome file grows linearly with findings × runs. Archive rotation (180 days) bounds growth. Calibration is O(n) over resolved outcomes, bounded by min_samples threshold.
        - E (Elevation of Privilege): No privilege boundary change. All operations are local filesystem reads/writes within the repo working directory.
