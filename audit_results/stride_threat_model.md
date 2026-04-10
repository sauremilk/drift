# STRIDE Threat Model

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
