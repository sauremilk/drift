# Fault Tree Analysis

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
