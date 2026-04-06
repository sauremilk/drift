# Fault Tree Analysis

## 2026-04-06 - DCA script-context false positives (Issue #176)

### FT-1: False positives on executable Python script modules
- Top event: DCA emits dead-code findings for script helper functions that are used only by local control flow.
- Branch A: File is an executable script path (for example `.github/workflows/*`, `scripts/*`, `tools/*`, `bin/*`).
- Branch B: Symbol usage occurs through local function calls and script entrypoint execution, not via cross-file imports.
- Branch C: Export/import heuristic interprets public symbols as unused exports.
- Mitigation implemented: Skip export-based DCA evaluation for Python files in conservative script-context paths.

### FT-2: Under-reporting risk after script-context suppression
- Top event: True dead code within script-like paths is not surfaced by DCA.
- Branch A: Suppression triggers based on script-context path token.
- Branch B: File actually contains import-oriented module code despite script-like location.
- Mitigation implemented: Keep suppression narrow and path-scoped, preserve existing behavior for non-script module paths, and monitor future field reports.

## 2026-04-05 - HSC OpenTelemetry GenAI semconv false positives (Issue #175)

### FT-1: False positives on OpenTelemetry GenAI semconv constants
- Top event: HSC emits hardcoded-secret findings for observability constants (for example `INPUT_TOKENS`).
- Branch A: Variable-name heuristic matches `token` in metric constant symbol names.
- Branch B: Literal value is a semantic-convention key (`gen_ai.usage.input_tokens`) and not credential material.
- Branch C: Generic fallback path treats non-trivial string literals in secret-shaped variables as suspicious.
- Mitigation implemented: Add narrow suppression for OpenTelemetry GenAI semantic-convention literals (`gen_ai.*`) before generic fallback finding emission.

### FT-2: Under-reporting risk after semconv suppression
- Top event: Real credential literal may be missed when assigned to token-shaped observability symbols.
- Branch A: New semconv suppression path is active.
- Branch B: Credential-like value might resemble structured dotted literal format.
- Mitigation implemented: Keep high-confidence known-prefix detection (`ghp_`, `sk-`, `AKIA`, etc.) before semconv suppression and constrain suppression to conservative `gen_ai.<segment>.<segment...>` pattern.

## 2026-04-05 - AVS/ECM/TPD Recall-Härtung auf Groß-Repositories (Issue #170)

### FT-1: AVS interne Kanten gehen bei relativen Imports verloren
- Top event: AVS bleibt ohne Befunde trotz realer interner Architekturkopplung.
- Branch A: Codebasis nutzt relative Imports (`from .x import y`) intensiv.
- Branch B: Importgraph kann relative Imports nicht auf interne Dateien mappen.
- Branch C: Kanten werden als extern/unresolved geführt, Folgeprüfungen verlieren Signal.
- Mitigation implemented: Relative Kandidatenauflösung aus Quellpaketpfad + Importmodul/-namen ergänzt.

### FT-2: ECM sampling bias auf zu kleines Hot-File-Subset
- Top event: ECM liefert 0 Findings in sehr großen Repositories.
- Branch A: Kandidatenmenge ist sehr groß.
- Branch B: Starres Limit analysiert nur kleine Top-Commit-Teilmenge.
- Branch C: Contract-Drift liegt außerhalb des betrachteten Subsets.
- Mitigation implemented: Adaptive Kandidatenobergrenze (konfigurierter Floor, skaliertes Limit bis 300) ergänzt.

### FT-3: TPD ohne Beobachtungsbasis bei globalem Test-Exclude
- Top event: TPD liefert 0 Findings trotz vorhandener Tests.
- Branch A: Globales Discovery-Exclude enthält `**/tests/**`.
- Branch B: ParseResults enthalten keine Testdateien.
- Branch C: TPD-Analysepfad lief bisher ausschließlich über ParseResults.
- Mitigation implemented: Fallback-Testdatei-Discovery aus Repo-Dateisystem, aktiv nur wenn kein Test-Counter vorhanden ist.

## 2026-04-05 - MAZ decorator fallback recall calibration (Issue #169)

### FT-1: False negatives when endpoint ingestion misses decorator-defined routes
- Top event: MAZ emits zero findings although an unauthenticated route handler exists.
- Branch A: File contains route decorators (for example `@router.get`, `@app.post`).
- Branch B: Pattern ingestion contributes no `API_ENDPOINT` instance for that file.
- Branch C: Prior MAZ logic required `API_ENDPOINT` pattern presence for all findings.
- Mitigation implemented: add conservative decorator-based endpoint fallback that activates only when no `API_ENDPOINT` pattern is present.

### FT-2: Precision regression risk from decorator fallback
- Top event: MAZ emits finding for non-endpoint decorator usage in edge contexts.
- Branch A: Decorator token overlaps with HTTP marker names.
- Branch B: File has no `API_ENDPOINT` pattern, so fallback path is active.
- Mitigation implemented: conservative decorator marker set, explicit auth-decorator suppression, and unchanged allowlist/dev-path/CLI-local suppression guards.

## 2026-04-05 - BEM fallback-assignment recall + AVS src-root import resolution (Issue #168)

### FT-1: BEM false negatives on fallback assignment handlers
- Top event: BEM emits zero findings although a module repeatedly uses `except Exception: <flag> = False`.
- Branch A: AST error-handling fingerprint emits generic `other` action for assignment handlers.
- Branch B: BEM swallowing gate accepts only pass/log/print.
- Branch C: Broadness threshold is met but swallowing ratio remains below threshold.
- Mitigation implemented: classify handler assignments as `fallback_assign` and include this action in BEM swallowing criteria.

### FT-2: AVS false negatives on src-root package imports
- Top event: AVS misses internal edges and produces no upward-import findings in repositories with `src/` layout.
- Branch A: File module key is stored as `src.<package>.<module>`.
- Branch B: Source imports use canonical package path without source-root prefix (`<package>.<module>`).
- Branch C: Exact module lookup fails, edge is marked external/unresolved.
- Mitigation implemented: add source-root alias resolution (`src`/`lib`/`python`) in import-graph module mapping.

## 2026-04-05 - MAZ localhost CLI serving false positives (Issue #167)

### FT-1: False positives on local CLI serving modules
- Top event: MAZ emits missing-authorization findings for local CLI serving endpoints that are not production-facing APIs.
- Branch A: Endpoint patterns are detected from framework routes (for example FastAPI handlers).
- Branch B: File path indicates CLI serving context (`cli/serving/server.py`-style layout).
- Branch C: Prior MAZ logic had no local CLI deployment-context suppression.
- Mitigation implemented: Add targeted path heuristic that suppresses MAZ finding emission when path contains `cli` and `serving`/`serve` markers.

### FT-2: Under-reporting risk after CLI-serving suppression
- Top event: A genuinely externally exposed endpoint under a CLI-marked serving path is not reported.
- Branch A: Repository uses `cli/serving/*` path tokens for production-exposed handlers.
- Branch B: New suppression triggers before finding emission.
- Mitigation implemented: Keep suppression scoped to combined markers only and retain MAZ detection for serving paths without CLI marker; regression verifies non-CLI serving path still emits findings.

## 2026-04-05 - HSC ML tokenizer constant false positives (Issue #166)

### FT-1: False positives on ML tokenizer constants
- Top event: HSC emits hardcoded-secret findings for tokenizer metadata constants in ML code.
- Branch A: Variable-name heuristic matches secret-shaped token terms (`token`, `*_token`, `*_token_id`).
- Branch B: Literal is tokenizer metadata (`<|pad|>`, `[CLS]`, chat template, tokenizer class name).
- Branch C: Generic fallback path treats non-trivial string literals as credential candidates.
- Mitigation implemented: add tokenizer-context suppression for known tokenizer symbol names, special-token literal markers, and template syntax before generic fallback finding emission.

### FT-2: Under-reporting risk after tokenizer suppression
- Top event: Real credential assigned to tokenizer-shaped symbols is not reported.
- Branch A: Tokenizer-context suppression applies to variable names such as `pad_token`.
- Branch B: Credential-like literal appears in tokenizer symbol assignment.
- Mitigation implemented: keep known-prefix detection (`ghp_`, `sk-`, `AKIA`, etc.) before tokenizer suppression and add regression coverage to ensure high-confidence secrets are still emitted.

## 2026-04-05 - NBV try_* attempt-semantics false positives (Issue #165)

### FT-1: False positive on comparison-style try_* helper
- Top event: NBV emits "Naming contract violation" for `try_*` function that expresses "attempt/check" semantics rather than exception-handling intent.
- Branch A: Function name starts with `try_`.
- Branch B: Body has no explicit `try/except` block.
- Branch C: Existing rule assumes `try_*` always implies exception contract.
- Mitigation implemented: suppress `try_*` finding when body indicates comparison/check semantics (`ast.Compare`, `is None`, `isinstance`) or file path indicates utility/helper context.

### FT-2: Under-reporting risk after suppression
- Top event: A real exception-handling contract mismatch in a utility module is not emitted.
- Branch A: Function path matches utility/helper tokens.
- Branch B: Function name starts with `try_` and lacks `try/except`.
- Branch C: Suppression triggers before finding emission.
- Mitigation implemented: scope change strictly to `try_*`; keep existing behavior for all other naming contracts and preserve baseline regression for non-utility/non-comparison `try_*` violations.

## 2026-04-05 - DIA bootstrap-repo README false positives

### FT-1: False positive README drift on tiny bootstrap repositories
- Top event: DIA emits `No README found` for a repository that is too small for the finding to be actionable architectural drift.
- Branch A: Repository has zero or one parsed Python file, or all parsed files are `__init__.py` skeleton modules.
- Branch B: README lookup fails.
- Branch C: Previous DIA logic emitted the same medium-severity finding regardless of repository footprint.
- Mitigation implemented: Return no DIA finding when the repo is bootstrap-sized (`len(parse_results) <= 1`) or a pure `__init__.py` skeleton and README is absent.

### FT-2: Under-reporting risk after bootstrap suppression
- Top event: A tiny repository that should still be nudged to add documentation does not receive a README finding.
- Branch A: Repository remains at bootstrap size (`<= 1` parsed file) or contains only `__init__.py` package skeleton files.
- Branch B: Missing README is intentionally tolerated to avoid noise.
- Mitigation implemented: Keep suppression narrowly scoped to bootstrap-sized or init-only repos and preserve normal README finding behavior for larger repositories.

## 2026-04-05 - AVS lazy-import policy violation detection (Issue #146)

### FT-1: False negative chain for heavy module-level imports
- Top event: Drift does not report a documented lazy-import policy violation for heavy libraries.
- Branch A: Repository policy requires lazy import for runtime-heavy modules (`onnxruntime`, `torch`, `cv2`).
- Branch B: Import exists at module scope in production path.
- Branch C: AVS has no dedicated rule that maps this policy to a finding.
- Mitigation implemented: Add configurable `policies.lazy_import_rules` in AVS with dedicated rule_id `avs_lazy_import_policy`.

### FT-2: False positive chain after policy enforcement
- Top event: Local in-function lazy imports are incorrectly flagged as policy violations.
- Branch A: Import metadata does not distinguish module-level versus local scope.
- Branch B: Rule matching triggers solely on module name/pattern.
- Mitigation implemented: Add `ImportInfo.is_module_level` from AST parsing, enforce `module_level_only=true` by default, and add regression tests for local-import suppression.

## 2026-04-05 - MDS package-level lazy __getattr__ false positives (Issue #144)

### FT-1: False positive duplicate finding for intentional package lazy loading
- Top event: MDS emits HIGH exact-duplicate finding for package `__init__.py` `__getattr__` implementations.
- Branch A: Candidate collection includes package-level `__getattr__` functions.
- Branch B: Multiple packages intentionally share the same lazy-loading export bridge code.
- Branch C: Body-hash grouping escalates these to exact duplicate findings.
- Mitigation implemented: Exclude package-level `__getattr__` in `__init__.py` from MDS candidate set.

### FT-2: Under-reporting risk for rare problematic package __getattr__ duplication
- Top event: A truly harmful package-level `__getattr__` duplication does not surface via MDS.
- Branch A: New suppression heuristic intentionally skips package `__init__.py` `__getattr__`.
- Branch B: Repository uses package-level `__getattr__` for non-standard heavy logic.
- Mitigation implemented: Keep suppression narrowly scoped (`__getattr__` + `__init__.py`), retain detection for non-package `__getattr__`, and monitor field reports.

## 2026-04-05 - TPD negative assertion undercount (Issue #143)

### FT-1: False happy-path-only finding despite negative coverage
- Top event: `test_polarity_deficit` reports a module as happy-path-only although tests include negative-path checks.
- Branch A: Bare `assert` expressions were counted as positive without polarity interpretation.
- Branch B: Negative assert idioms (`assert not`, `assert ... is False`, `assert ... is None`) were not recognized.
- Branch C: Functional negative calls (`pytest.raises(...)`, `pytest.fail(...)`) were not consistently counted.
- Mitigation implemented: Add AST-based negative assert classification, regex fallback for assert text variants, and explicit negative call handling for raises/fail patterns.

### FT-2: Over-classification of ambiguous asserts as negative
- Top event: TPD under-reports true happy-path-only modules by over-counting negative assertions.
- Branch A: Heuristic polarity logic can misclassify unusual assert constructs.
- Branch B: Regex fallback may classify non-failure semantics in edge wording.
- Mitigation implemented: Limit negative heuristics to conservative patterns (`not`, `False`, `None`, explicit fail/raises calls) and keep ratio + test-count gates unchanged.

## 2026-04-05 - PFS framework-surface error-handling calibration (Issue #142)

### FT-1: False HIGH severity on framework-facing error-handling diversity
- Top event: pattern_fragmentation emits HIGH urgency for router/page/server modules where error behavior differences are framework-idiomatic.
- Branch A: PFS computes fragmentation from variant count and spread only.
- Branch B: Framework boundary modules naturally encode heterogeneous error contracts.
- Branch C: No context-aware dampening in previous logic.
- Mitigation implemented: Add framework-surface hints (API endpoint co-location + path/file tokens) and apply conservative score/urgency dampening for error_handling context.

### FT-2: Under-ranked true boundary fragmentation after dampening
- Top event: A genuinely harmful framework-boundary fragmentation case is ranked below expected urgency.
- Branch A: Heuristic hints classify module as framework-facing.
- Branch B: Context dampening reduces score and suppresses default HIGH severity.
- Mitigation implemented: Keep findings emitted (no suppression), limit dampening to hint-matched context only, and expose framework hint metadata for explicit reviewer escalation.

## 2026-04-05 - HSC OAuth endpoint URL false positives (Issue #161)

### FT-1: False positive on OAuth endpoint constants
- Top event: Hardcoded-Secret finding is emitted for a provider endpoint URL constant (for example `TOKEN_URL`).
- Branch A: Variable-name heuristic matches secret-like tokens (`token`, `auth`).
- Branch B: Literal value is a static HTTP(S) endpoint URL.
- Branch C: Existing logic classifies non-short string literals as potential credentials.
- Mitigation implemented: Add endpoint-URL suppression for plain HTTP(S) URLs without userinfo credentials.

### FT-2: False negative risk after URL suppression
- Top event: Credential-bearing URL literal is not surfaced as HSC finding.
- Branch A: URL suppression applies to all HTTP(S) literals without credential checks.
- Branch B: Literal contains embedded username/password (`user:pass@host`).
- Mitigation implemented: Suppression excludes URL literals with username/password so these remain detectable.

## 2026-04-05 - MAZ documented public-safe endpoint severity calibration (Issue #162)

### FT-1: False HIGH severity on intentionally public publishable-key endpoint
- Top event: Missing-Authorization finding is emitted as HIGH for an endpoint intentionally exposed for non-sensitive publishable key retrieval.
- Branch A: Endpoint has no auth check by design.
- Branch B: Existing MAZ logic does not consider explicit in-code public-safe documentation.
- Branch C: Endpoint name semantics indicate publishable/public key intent, but this context is not used.
- Mitigation implemented: Severity is downgraded to LOW when endpoint is documented (`has_docstring`) and function name matches conservative publishable/public-key markers.

### FT-2: Under-ranked true auth gap after severity dampening
- Top event: A genuinely sensitive unauthenticated endpoint receives lower severity due name-based heuristic.
- Branch A: Endpoint name includes marker token used by dampening heuristic.
- Branch B: Endpoint includes a docstring but still returns sensitive material.
- Mitigation implemented: Finding is still emitted (not suppressed), dampening is limited to a conservative marker set + documentation requirement, and metadata explicitly flags the downgrade path for reviewer audit.

## 2026-04-05 - HSC error-message constant false positives (Issue #163)

### FT-1: False positive on natural-language message constants
- Top event: HSC emits a hardcoded-secret finding for a plain-text error/warning/message constant.
- Branch A: Variable-name heuristic matches secret-like tokens (for example `token`, `secret`).
- Branch B: Variable name ends with message suffix (`_ERROR`, `_WARNING`, `_MESSAGE`).
- Branch C: Literal value is human-readable sentence text, not credential material.
- Mitigation implemented: Suppress findings when suffix indicates message constant and literal matches natural-language message heuristic.

### FT-2: Under-reporting risk after message-constant suppression
- Top event: A real credential assigned to a `*_ERROR`/`*_WARNING`/`*_MESSAGE` symbol is not reported.
- Branch A: New suffix-based suppression path is active.
- Branch B: Credential string could be mistaken for message-like text.
- Mitigation implemented: Execute high-confidence checks (known token prefixes, URL userinfo credentials) before suppression and constrain suppression with minimum length and word-count heuristic.

## 2026-04-05 - AVS tiny foundational module severity recalibration (Issue #153)

### FT-1: False HIGH severity on tiny foundational modules
- Top event: Zone-of-Pain finding is emitted as HIGH for a tiny, intentionally stable adapter/base module.
- Branch A: Distance-from-main-sequence metric is high due to low abstraction and stability.
- Branch B: Module structural footprint is tiny (few lines, few entities).
- Branch C: Coupling evidence is present but not strong enough to justify HIGH action urgency.
- Mitigation implemented: Tiny-foundational dampening plus explicit high-risk evidence requirement before HIGH severity.

### FT-2: Over-dampening hides true tiny high-impact modules
- Top event: Tiny foundational module with truly broad impact is under-ranked.
- Branch A: Dampening logic applies based on module size and low efferent coupling.
- Branch B: Strong blast-impact indicators are not considered.
- Mitigation implemented: Keep HIGH when coupling evidence is strong (`ca >= 6` or `ca >= 4 and ce >= 2`) and expose metadata for auditability.

## 2026-04-05 - DCA framework/library public API suppression (Issue #152)

### FT-1: False Positive chain for package public APIs
- Top event: Dead-code finding recommends removing symbols that are part of external framework/library API.
- Branch A: DCA infers usage only from intra-repo imports.
- Branch B: Public symbols are consumed by downstream users, not imported internally.
- Branch C: Aggregate finding reports large unused-export clusters on API modules.
- Mitigation implemented: Detect package-layout public API modules and suppress dead-export aggregation for those paths.

### FT-2: False Negative chain after suppression
- Top event: Real dead symbols in library repos are not reported.
- Branch A: Suppression boundary too broad and includes internal implementation modules.
- Branch B: Internal modules with no external API contract lose dead-export visibility.
- Mitigation implemented: Keep internal/private path tokens out of suppression scope and validate with regression tests.

## 2026-04-04 - MCP stdio deadlock hardening on Windows

### FT-1: Tool call blocks on subprocess stdin inheritance
- Top event: MCP tool call does not return when child process is spawned.
- Branch A: Tool path invokes `subprocess.run(...)` without explicit stdin handling.
- Branch B: Child process inherits stdio handle from MCP server transport.
- Branch C: Windows IOCP path enters blocking state and call never completes.
- Mitigation implemented: Explicit `stdin=subprocess.DEVNULL` in affected subprocess paths plus regression test to prevent omissions.

### FT-2: Threaded first import deadlock with C-extension modules
- Top event: MCP request hangs during `asyncio.to_thread` execution.
- Branch A: Heavy module import (for example numpy/torch/faiss) occurs first time inside worker thread.
- Branch B: Event loop already owns IOCP resources.
- Branch C: DLL loader lock contention causes deadlock.
- Mitigation implemented: `_eager_imports()` called before `mcp.run()` so heavy imports happen before threaded tool execution.

## 2026-04-03 - PFS/NBV low-actionability output paths (Issue #125)

### FT-1: PFS remediation cannot be applied directly
- Top event: Agent receives PFS finding but cannot perform a targeted refactor.
- Branch A: Dominant pattern named but not exemplified.
- Branch B: Deviating locations do not include stable line-level anchors.
- Branch C: Context window does not include the relevant source bodies.
- Mitigation implemented: PFS fix embeds canonical exemplar `file:line` and concrete deviation refs.

### FT-2: NBV remediation path is ambiguous
- Top event: Agent applies wrong fix (rename vs behavior) for naming-contract finding.
- Branch A: Rule semantics (`validate_`, `ensure_`, `is_`) not reflected in suggestion.
- Branch B: No concrete location anchor to patch first.
- Branch C: Generic wording interpreted inconsistently by different agents.
- Mitigation implemented: NBV fix uses prefix-specific suggestion plus `file:line` location.

## 2026-07-18 - Security audit: test-file FP in PFS/AVS/MDS

### FT-1: False Positive from test files bypassing exclude patterns
- Top event: PFS/AVS/MDS produce findings on test files when user overrides default exclude.
- Branch A: User removes `**/tests/**` from exclude list in drift.yaml.
- Branch B: Signals iterate all parse_results without checking is_test_file().
- Branch C: Test file patterns/imports/duplicates generate false findings.
- Mitigation implemented: Defense-in-depth is_test_file() check in each signal's analyze() method.

### FT-2: File discovery crash on broken FS entries
- Top event: discover_files() raises unhandled OSError on inaccessible paths.
- Branch A: glob() encounters permission-denied or broken symlink targets.
- Branch B: stat() fails on locked/deleted file between enumeration and access.
- Mitigation implemented: try/except OSError around glob(), is_file()/is_symlink(), and stat() calls.

## 2026-04-03 - DIA FP cluster for markdown slash tokens (Issue #121)

### FT-1: False Positive escalation in Doc-Implementation Drift
- Top event: README/ADR missing-directory findings are noisy and misleading.
- Branch A: Directory-like token extracted from plain prose.
- Branch B: Token has no structural context (not backticked, no directory/folder/path semantics nearby).
- Branch C: Repository has no corresponding directory, causing DIA finding emission.
- Mitigation implemented: Gate extraction by structural context and preserve explicit code-span path mentions.

### FT-2: False Negative risk after FP mitigation
- Top event: Legitimate plain-prose directory mention is ignored.
- Branch A: Mention not backticked.
- Branch B: Structural cue absent from local context window.
- Mitigation implemented: Add keyword-based structural context and targeted tests for positive prose context.
