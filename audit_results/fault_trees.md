# Fault Tree Analysis

## 2026-04-12 - Issue #271: DCA false positives for non-exported TS file-local declarations

### Top Event (TE-DCA-271)
DCA reports non-exported TypeScript file-local declarations (`type`/`interface`/`class`) as dead exports with inflated severity.

### FT-1: false-positive branch

```
          TE-FP: non-exported TS declaration reported as dead export
                         |
                      OR-Gate
               +---------+---------+
              IE-1      IE-2
```

- **IE-1 (MCS)**: TS parser emitted class-like declarations without explicit export metadata, so downstream signals could not distinguish file-local vs public declarations.
  - Mitigation: emit `is_exported` metadata for TS `class`, `interface`, and `type` declarations.
- **IE-2 (MCS)**: DCA class-path export candidate collection for TS/JS did not enforce export-state filtering.
  - Mitigation: only include TS/JS class-like declarations when `is_exported=True`.

### FT-2: false-negative guard

- **IE-3 (Guard)**: declaration-level export detection can miss split export-list patterns (`type X ...; export { X }`).
  - Mitigation: keep FP fix bounded now and track follow-up for export-list mapping if recall evidence appears.

## 2026-04-12 - Issue #272: DCA false positives on TypeScript testkit contract files

### Top Event (TE-DCA-272)
DCA reports exported testkit contract APIs (`*.testkit.ts`) as high-urgency dead code although they are intentionally consumed by downstream test suites.

### FT-1: false-positive branch

```
          TE-FP: testkit contract export reported as actionable dead code
                         |
                      OR-Gate
               +---------+---------+
              IE-1      IE-2
```

- **IE-1 (MCS)**: DCA static import evidence is intra-repo and cannot observe downstream/integration test harness consumers.
  - Mitigation: recognize explicit testkit contract naming (`*.testkit.*`) as bounded dynamic-consumption context.
- **IE-2 (MCS)**: Test-context dampening relied on path classification and did not cover source-located testkit modules under `src/**`.
  - Mitigation: apply dedicated testkit severity dampening (`LOW`, score multiplier `0.45`) with metadata traceability (`testkit_contract_heuristic_applied`).

### FT-2: false-negative guard

- **IE-3 (Guard)**: broad filename dampening may down-rank truly dead exports.
  - Mitigation: heuristic is constrained to explicit `.testkit.` filename token and keeps findings visible (no suppression), preserving reviewer override path.

## 2026-04-12 - Issue #270: MAZ false positives on localhost-only TypeScript servers

### Top Event (TE-MAZ-270)
MAZ reports loopback-only TypeScript endpoints as missing authorization with CRITICAL severity.

### FT-1: false-positive branch

```
          TE-FP: localhost-only route reported as missing authorization
                         |
                      OR-Gate
               +---------+---------+
              IE-1      IE-2
```

- **IE-1 (MCS)**: TS endpoint extraction emitted API patterns without listener host context, so local-only serving topology was invisible to MAZ.
  - Mitigation: detect explicit loopback `*.listen(...)` host literals and propagate `loopback_only` endpoint metadata.
- **IE-2 (MCS)**: MAZ treated all unauthenticated API endpoint patterns as network-exposed by default and escalated to CRITICAL.
  - Mitigation: suppress findings for endpoint patterns explicitly marked `loopback_only=True`.

### FT-2: false-negative guard

- **IE-3 (Guard)**: broad host heuristics could suppress real findings if non-loopback binds were misclassified.
  - Mitigation: only accept explicit loopback literals (`127.0.0.1`, `localhost`, `::1`) and keep non-loopback behavior unchanged.

## 2026-04-12 - Issue #269: MAZ false positives for app-level auth middleware in Express TS files

### Top Event (TE-MAZ-269)
MAZ reports secured Express endpoints as missing authorization because auth is implemented via app-level middleware rather than route-level middleware parameters.

### FT-1: false-positive branch

```
          TE-FP: route behind global auth middleware reported as missing authorization
                         |
                      OR-Gate
               +---------+---------+
              IE-1      IE-2
```

- **IE-1 (MCS)**: TS route extraction only considered route call args/decorators/inline handler guards and ignored file-level unscoped `*.use(...)` middleware chains.
  - Mitigation: add unscoped app/router-level middleware scan and treat auth-like middleware as route auth evidence.
- **IE-2 (MCS)**: MAZ consumed endpoint pattern `has_auth=False` values emitted by ingestion, so parser blind spots propagated into CRITICAL security findings.
  - Mitigation: propagate file-level middleware auth flag into per-endpoint `has_auth` fingerprinting before MAZ evaluation.

### FT-2: false-negative guard

- **IE-3 (Guard)**: treating scoped middleware (`app.use('/prefix', ...)`) as global would over-credit auth and hide real unauthenticated routes.
  - Mitigation: keep scoped middleware excluded until route-prefix matching is modeled explicitly; limit fix to unscoped middleware only.

## 2026-04-12 - Issue #268: TPD early-stage extension severity inflation

### Top Event (TE-TPD-268)
TPD reports prototype-stage extension/plugin test suites as high-severity happy-path deficits without lifecycle context.

### FT-1: false-positive branch

```
          TE-FP: early-stage extension happy-path coverage reported as HIGH drift
                         |
                      OR-Gate
               +---------+---------+
              IE-1      IE-2
```

- **IE-1 (MCS)**: TPD polarity scoring lacked runtime workspace lifecycle awareness (`extensions/<name>`, `plugins/<name>`).
  - Mitigation: derive runtime workspace keys from normalized path segments and identify newly introduced workspaces via file-history recency.
- **IE-2 (MCS)**: TPD did not distinguish small, early-stage module test suites from mature modules.
  - Mitigation: apply bounded cap when module test-file count is small (`<= 3`) inside newly introduced runtime workspaces; cap to LOW (`score <= 0.39`) with metadata traceability.

### FT-2: false-negative guard

- **IE-3 (Guard)**: broad dampening could under-prioritize genuine deficits in established extensions.
  - Mitigation: require both conditions (new workspace and small test-file count); keep established workspace behavior unchanged and covered by regression tests.

## 2026-04-12 - Issue #267: SMS extension-local dependencies over-prioritized in established workspaces

### Top Event (TE-SMS-267)
SMS reports extension/plugin-local novel dependencies with inflated urgency in established runtime workspaces, even when the dependencies are intentionally isolated to one workspace.

### FT-1: false-positive branch

```
          TE-FP: expected workspace-local dependency novelty reported as MEDIUM drift
                         |
                      OR-Gate
               +---------+---------+
              IE-1      IE-2
```

- **IE-1 (MCS)**: SMS novelty assessment was module-local and did not include package-to-workspace scope evidence for established runtime plugin layouts.
  - Mitigation: build runtime package scope index (`package -> {workspace}`) for `extensions/<name>` and `plugins/<name>` paths.
- **IE-2 (MCS)**: Existing suppression guarded only newly introduced workspaces and did not address mature extension packages with intentional local dependency stacks.
  - Mitigation: add bounded severity cap (`INFO`, `score <= 0.19`) when all novel packages are isolated to the same runtime workspace and annotate findings with `workspace_scoped_novel_capped` + `workspace_scope`.

### FT-2: false-negative guard

- **IE-3 (Guard)**: Over-broad workspace cap could hide genuine cross-workspace novelty drift.
  - Mitigation: cap is applied only when all novel packages resolve to exactly one workspace; if any package is shared across workspaces, normal SMS severity logic remains active.

## 2026-04-12 - Issue #266: PFS inter-extension boundary variation flagged as fragmentation

### Top Event (TE-PFS-266)
PFS reports high-urgency pattern fragmentation for API/error variants in extension monorepos where variation is expected across plugin boundaries.

### FT-1: false-positive branch

```
          TE-FP: intentional extension-boundary pattern diversity reported as actionable drift
                         |
                      OR-Gate
               +---------+---------+
              IE-1      IE-2
```

- **IE-1 (MCS)**: PFS variant scoring prioritizes count dispersion but lacks a dedicated cap for expected plugin-boundary API/error heterogeneity.
  - Mitigation: classify API/error categories in multi-plugin layouts as expected inter-plugin variation and apply informational severity cap.
- **IE-2 (MCS)**: Existing plugin dampener reduced urgency to LOW in many cases but still surfaced non-actionable fix pressure in large extension trees.
  - Mitigation: add explicit `plugin_boundary_variation_expected` metadata and cap these findings to INFO for traceable triage.

### FT-2: false-negative guard

- **IE-3 (Guard)**: Aggressive context dampening may hide true intra-extension fragmentation that is actionable.
  - Mitigation: bound heuristic to plugin layouts with at least three workspaces and keep findings visible with metadata for manual re-prioritization.

## 2026-04-12 - Issue #264: MDS absolute-path workspace detection gap

### Top Event (TE-MDS-264)
MDS reports cross-extension vendored duplicates as actionable high-severity clones because workspace isolation dampening does not activate for absolute file paths.

### FT-1: false-positive branch

```
          TE-FP: intentional cross-extension duplicate reported as HIGH/MEDIUM
                         |
                      OR-Gate
               +---------+---------+
              IE-1      IE-2
```

- **IE-1 (MCS)**: Workspace-scope helper required `extensions`/`plugins` as the first path segment and failed for absolute paths.
  - Mitigation: resolve workspace scope by scanning normalized path segments and extracting `extensions/<name>` or `plugins/<name>` anywhere in path.
- **IE-2 (MCS)**: Pair/group dampening depended on this scope helper, so cross-workspace caps were skipped in real repository layouts.
  - Mitigation: keep existing INFO cap logic but feed it robust scope resolution for both exact-group and near-duplicate pair paths.

### FT-2: false-negative guard

- **IE-3 (Guard)**: Segment-scan matching may accidentally classify unrelated paths that contain `extensions`/`plugins` as plain folder names.
  - Mitigation: require exact segment match plus immediate workspace name segment; preserve same-workspace and non-plugin negative-path regressions.

## 2026-04-12 - Issue #263: AVS unstable-dependency FP in intra-extension imports

### Top Event (TE-AVS-263)
AVS reports unstable-dependency findings for same-extension imports in monorepo extension workspaces where local wiring is expected.

### FT-1: false-positive branch

```
          TE-FP: intra-extension edge reported as unstable dependency smell
                         |
                      OR-Gate
               +---------+---------+
              IE-1      IE-2
```

- **IE-1 (MCS)**: AVS unstable-dependency check used file-level coupling and churn without considering extension package boundaries.
  - Mitigation: derive `extensions/<name>` workspace root for each edge and suppress same-workspace edges for `avs_unstable_dep`.
- **IE-2 (MCS)**: Composition-root/register/runtime files inside one extension naturally create high local instability signatures that are not cross-boundary architecture violations.
  - Mitigation: treat intra-extension edges as expected implementation detail; keep rule active for cross-extension edges.

### FT-2: false-negative guard

- **IE-3 (Guard)**: Suppression may hide real unstable dependency smells within one extension workspace.
  - Mitigation: bound suppression strictly to same `extensions/<name>` edges and retain cross-extension detection with dedicated regression coverage.

## 2026-04-12 - Issue #261: TVS mature extension workspace burst false positives

### Top Event (TE-TVS-261)
TVS reports coordinated active development in established plugin workspaces as high temporal instability because burst dampening does not activate reliably.

### FT-1: false-positive branch

```
          TE-FP: mature extension workspace churn reported as high instability
                         |
                      OR-Gate
               +---------+---------+
              IE-1      IE-2
```

- **IE-1 (MCS)**: Coordinated-burst detection relied on one strict active-ratio threshold, which under-fits mixed-age extension workspaces in large monorepos.
  - Mitigation: Add bounded mature-workspace burst branch that combines active-count, active-ratio, and recent-modified ratio.
- **IE-2 (MCS)**: Burst classifier did not use workspace-level recency density, so coordinated iteration windows with older files were interpreted as pure instability.
  - Mitigation: Include `last_modified` recency share and established-history guard in workspace profile before applying the existing TVS dampening cap.

### FT-2: false-negative guard

- **IE-3 (Guard)**: Broader burst detection could down-rank genuine instability in plugin workspaces.
  - Mitigation: Keep heuristic bounded to runtime plugin scopes and require multiple simultaneous criteria; keep findings visible (no suppression) and preserve non-plugin high-severity behavior.

## 2026-04-12 - Issue #260: DCA false positives for plugin/extension workspace exports

### Top Event (TE-DCA-260)
DCA reports plugin/extension workspace exports as dead code with inflated urgency despite runtime host/plugin consumption outside static import graphs.

### FT-1: false-positive branch

```
          TE-FP: plugin workspace export reported as actionable dead code
                         |
                      OR-Gate
               +---------+---------+
              IE-1      IE-2
```

- **IE-1 (MCS)**: Static import-only evidence cannot see runtime plugin loader boundaries, so extension exports appear unreferenced.
  - Mitigation: Add bounded runtime plugin workspace heuristic for JS/TS files under `extensions/*` and `plugins/*` (including nested path variants).
- **IE-2 (MCS)**: Existing DCA dampening only covered narrow filename subsets (`config*`, `components/plugin-sdk`) and missed broader plugin export surfaces.
  - Mitigation: Apply workspace-level LOW cap (`score <= 0.39`) with metadata traceability (`runtime_plugin_workspace_heuristic_applied`).

### FT-2: false-negative guard

- **IE-3 (Guard)**: Workspace dampening may down-rank genuinely dead exports in plugin packages.
  - Mitigation: Keep findings visible (no suppression), constrain heuristic to JS/TS plugin workspace paths, and keep non-plugin severity behavior unchanged via regression guard.

## 2026-04-12 - Issue #259: CXS false positives in config-default resolver files

### Top Event (TE-CXS-259)
CXS reports expected branching in TypeScript/JavaScript config-default resolver modules as actionable complexity debt.

### FT-1: false-positive branch

```
          TE-FP: inherent config-default branching reported as urgent complexity debt
                         |
                      OR-Gate
               +---------+---------+
              IE-1      IE-2
```

- **IE-1 (MCS)**: CXS context dampening classified only schema/migration patterns; config-default files were scored with the global severity map.
  - Mitigation: Extend inherent TS/JS context classification to bounded config-default filename markers (`config-defaults`, `config.defaults`, `default-config`).
- **IE-2 (MCS)**: Configuration default resolution code contains intentional fallback/merge/validation branching but was interpreted as generic business-logic complexity.
  - Mitigation: Reuse existing context cap path (`INFO`, `score <= 0.19`) and metadata trace (`context_dampened=True`) for those config-default contexts.

### FT-2: false-negative guard

- **IE-3 (Guard)**: Context cap may down-rank real maintainability debt in exceptional config-default files.
  - Mitigation: Keep findings visible (no suppression), limit heuristic scope to explicit filename conventions, and preserve standard scoring for non-matching files.

## 2026-04-12 - Issue #258: EDS high-severity inflation for TS internal/UI implementation functions

### Top Event (TE-EDS-258)
EDS escalates TypeScript/TSX internal UI implementation functions to `HIGH` despite bounded explainability expectations in this context.

### FT-1: false-positive branch

```
          TE-FP: internal TS/TSX UI wiring function reported as HIGH explainability deficit
                         |
                      OR-Gate
               +---------+---------+
              IE-1      IE-2
```

- **IE-1 (MCS)**: Severity escalation used global thresholds only; TS internal/UI context was not considered after score computation.
  - Mitigation: add TS/TSX high-cap when function is non-exported or path/name indicates UI implementation context.
- **IE-2 (MCS)**: Missing JSDoc in large UI event/render functions was interpreted as universally critical documentation debt.
  - Mitigation: cap capped findings to `MEDIUM` (`score <= 0.69`) and mark with `ts_ui_high_cap_applied` for transparent triage.

### FT-2: false-negative guard

- **IE-3 (Guard)**: Cap may down-rank truly critical TS complexity debt in internal modules.
  - Mitigation: keep exported TS APIs eligible for `HIGH` and restrict cap to weak-evidence TS context (`no docstring` + `no self_documenting_signature`).

## 2026-04-12 - Issue #256: EDS TypeScript test-evidence false positives

### Top Event (TE-EDS-256)
EDS priorisiert TypeScript/JavaScript Funktionen als unzureichend erklaert, obwohl passende Tests vorhanden sind oder der Teststatus nicht verifizierbar ist.

### FT-1: false-positive branch

```
          TE-FP: TS/JS function reported with inflated explainability deficit
                         |
                      OR-Gate
               +---------+---------+
              IE-1      IE-2
```

- **IE-1 (MCS)**: EDS erhielt in TS/JS-Haeufungen keine Testfunktion-Evidenz aus `parse_results`, weil Discovery standardmaessig Testverzeichnisse ausnimmt.
  - Mitigation: dateibasiertes Test-Mapping in EDS (`*.test.*`, `*.spec.*`, `__tests__/*`, `src/... -> tests/...`).
- **IE-2 (MCS)**: Nicht verifizierbarer Teststatus wurde faktisch wie „kein Test“ behandelt und verschlechterte den Score.
  - Mitigation: Tri-State-Teststatus (`True/False/None`) mit neutraler Behandlung bei `None`.

### FT-2: false-negative guard

- **IE-3 (Guard)**: Zu breite Test-Mappings koennten echte Defizite in ungetesteten Dateien abschwaechen.
  - Mitigation: Mapping ist auf enge Namenskonventionen begrenzt und wirkt nur als positive Evidenz (keine Suppression, nur reduzierter Defizitscore).

## 2026-04-12 - Issue #255: CXS false positives in schema and migration code

### Top Event (TE-CXS-255)
CXS reports expected branching in schema validation and migration modules as actionable complexity debt.

### FT-1: false-positive branch

```
          TE-FP: inherent schema/migration branching reported as urgent complexity debt
                         |
                      OR-Gate
               +---------+---------+
              IE-1      IE-2
```

- **IE-1 (MCS)**: CXS applies one global severity mapping and treats schema validation branching as general business-logic complexity.
  - Mitigation: Add bounded context classification for TS/JS schema filenames (`*.schema.ts/js/...`) and cap severity to `INFO` for that context.
- **IE-2 (MCS)**: Migration files (`*migration*`, `*/migrations/*`) are write-once transformation code with intentionally exhaustive legacy branching, but were scored without context dampening.
  - Mitigation: Apply the same bounded context cap for migration path patterns and annotate findings with `context_dampened` metadata.

### FT-2: false-negative guard

- **IE-3 (Guard)**: Context cap may down-rank real complexity debt in exceptional migration/schema files.
  - Mitigation: Keep findings visible (no suppression), scope the cap to explicit TS/JS file patterns only, and preserve standard scoring for all other files.

## 2026-04-12 - Issue #254: FOE false positives for plugin SDK sub-path imports

### Top Event (TE-FOE-254)
FOE reports plugin/provider files as fan-out explosions because SDK sub-path imports are counted as separate dependencies.

### FT-1: false-positive branch

```
          TE-FP: coherent SDK usage reported as dependency explosion
                         |
                      OR-Gate
               +---------+---------+
              IE-1      IE-2
```

- **IE-1 (MCS)**: FOE counts raw JS/TS import specifiers, so `openclaw/plugin-sdk/a` and `openclaw/plugin-sdk/b` inflate unique dependency count.
  - Mitigation: Collapse JS/TS sub-path imports to stable dependency keys (`vendor/pkg`, `@scope/pkg`) before counting.
- **IE-2 (MCS)**: Package-export design (fine-grained sub-paths for tree-shaking) is interpreted as architecture fan-out rather than one SDK dependency.
  - Mitigation: Count package identity, not export-entry-point identity.

### FT-2: false-negative guard

- **IE-3 (Guard)**: Grouping may reduce sensitivity for edge cases with many sub-path imports.
  - Mitigation: Keep threshold logic unchanged, preserve file-granular handling for relative imports, and retain TP/score regression checks.

## 2026-04-12 - Issue #252: NBV false positive on TS ensure_ delegated class methods

### Top Event (TE-NBV-252)
NBV reports `ensure_*` TypeScript class methods as contract violations although the method fulfills the contract via delegated return path.

### FT-1: false-positive branch

```
          TE-FP: delegated TS ensure_* method reported as missing raise contract
                         |
                      OR-Gate
               +---------+---------+
              IE-1      IE-2
```

- **IE-1 (MCS)**: Method source is extracted without class wrapper, and tree-sitter parse misses return/throw structure needed by ensure-contract checks.
  - Mitigation: Re-parse dotted method sources (`Class.method`) in a synthetic class wrapper before checker execution.
- **IE-2 (MCS)**: Ensure-contract check relies on AST evidence (`throw`, return-value path, side effects); missing method context causes false negatives in evidence extraction.
  - Mitigation: Preserve existing ensure-contract logic, but feed it method-context-complete AST.

### FT-2: false-negative guard

- **IE-3 (Guard)**: Wrapped method parsing could make malformed snippets appear valid.
  - Mitigation: Scope wrapper fallback strictly to dotted method names and keep negative ensure regression (`ensure_*` without throw/return/side-effect is still flagged).

## 2026-04-12 - Issue #265: NBV false positives on TS predicate and assertion contracts

### Top Event (TE-NBV-265)
NBV reports TypeScript `is*`/`has*` predicate helpers and `ensure*` assertion-signature functions as naming-contract violations although language-conformant contracts are fulfilled.

### FT-1: false-positive branch

```
          TE-FP: valid TS predicate/assertion contracts reported as NBV violations
                         |
                      OR-Gate
               +---------+---------+
              IE-1      IE-2
```

- **IE-1 (MCS)**: Inferred TS predicate returns (for example delegated call results) are treated as non-bool when explicit return annotations are absent.
  - Mitigation: In `_ts_has_bool_return`, fail only on clear non-bool return evidence and treat unknown inferred-return expressions conservatively.
- **IE-2 (MCS)**: `ensure*` TS assertion signatures (`asserts ...`) are not recognized as valid ensure contracts when no local `throw`/value-return side effect is visible.
  - Mitigation: Accept assertion-signature return contracts explicitly in `_ts_check_rule` for `ensure_`.

### FT-2: false-negative guard

- **IE-3 (Guard)**: Conservative inferred-bool acceptance may hide some real predicate naming violations.
  - Mitigation: Keep explicit non-bool returns/signatures reportable and enforce negative regression tests for string/non-bool return scenarios.

## 2026-04-12 - Issue #253: TVS false positives in active extension/plugin workspaces

### Top Event (TE-TVS-253)
TVS reports coordinated active development in plugin workspaces as high-risk temporal instability.

### FT-1: false-positive branch

```
          TE-FP: active plugin workspace reported as architectural volatility hotspot
                         |
                      OR-Gate
               +---------+---------+
              IE-1      IE-2
```

- **IE-1 (MCS)**: TVS compares file churn against repo-wide baseline and does not consider plugin workspace lifecycle (new workspace bootstrap vs established maintenance churn).
  - Mitigation: Detect runtime plugin workspace scope (`extensions/<name>`, `plugins/<name>`) and classify workspace recency.
- **IE-2 (MCS)**: Coordinated feature bursts (many files in one workspace changing together) are interpreted as per-file instability outliers.
  - Mitigation: Detect coordinated workspace bursts and cap TVS score/severity impact (`score <= 0.45`) while preserving finding visibility.

### FT-2: false-negative guard

- **IE-3 (Guard)**: Dampening may lower urgency for genuine instability inside active plugin workspaces.
  - Mitigation: Apply bounded scope/burst criteria only, retain findings (no suppression), and keep non-plugin outlier behavior unchanged via regression guard.

## 2026-04-12 - Issue #249: COD false positives on plugin registration and typed utility modules

### Top Event (TE-COD-249)
COD reports intentional plugin/utility module patterns as semantic cohesion deficits.

### FT-1: false-positive branch

```
          TE-FP: plugin/utility module reported as cohesion deficit
                         |
                      OR-Gate
               +---------+---------+
              IE-1      IE-2
```

- **IE-1 (MCS)**: Action-family modules (`register*`, `format*`, `create*`) expose multiple subtargets but share one domain concern.
  - Mitigation: Add `shared_action_prefix_ratio` dampening for dominant action-prefix families.
- **IE-2 (MCS)**: Filename/domain-aligned utility modules (`format.ts`, `test-helpers.ts`) can look token-diverse despite cohesive module intent.
  - Mitigation: Add filename-token cohesion dampening and extra plugin-workspace dampening for `extensions/*/src`.

### FT-2: false-negative guard

- **IE-3 (Guard)**: New dampening can under-prioritize true cohesion deficits that match prefix/filename patterns accidentally.
  - Mitigation: Apply bounded thresholds (`>=0.6` action-prefix, `>=0.5` filename cohesion) and keep COD TP/TN and ground-truth regressions active.

## 2026-04-12 - Issue #251: TSB/BAT false positives in src test-helper naming and SDK event-emitter non-null assertions

### Top Event (TE-TSB-251)
TSB/BAT reports test-helper files or SDK-idiomatic EventEmitter `!` patterns as production type-safety bypass debt.

### FT-1: false-positive branch

```
          TE-FP: test-helper/SDK interop pattern reported as production bypass risk
                         |
                      OR-Gate
               +---------+---------+
              IE-1      IE-2
```

- **IE-1 (MCS)**: Test helper files under `src/` with names like `test-helpers.ts` or `test-http-response.ts` were not classified as test context.
  - Mitigation: Extend centralized `is_test_file` patterns for filename-based `test-helpers.*` and `test-*.{ts,js,tsx,jsx}` cases.
- **IE-2 (MCS)**: SDK event-emitter non-null assertions (`on!/off!/once!`) were scored like direct type bypasses.
  - Mitigation: Mark these patterns as `non_null_assertion_sdk` and apply reduced score weight while preserving finding traceability.

### FT-2: false-negative guard

- **IE-3 (Guard)**: Reduced weighting can under-prioritize genuine unsafe `!` usage in SDK-like files.
  - Mitigation: Scope dampening to known SDK imports (Playwright/Discord) and explicit EventEmitter member patterns; `as any`, double-cast, and ts-directive paths remain fully weighted.

## 2026-04-12 - Issue #250: MAZ outbound API-client false positives (TS unknown framework)

### Top Event (TE-MAZ-250)
MAZ reports outbound TypeScript API client helpers as inbound HTTP endpoints missing authorization.

### FT-1: false-positive branch

```
          TE-FP: outbound TS client helper reported as missing-auth endpoint
                         |
                      OR-Gate
               +---------+---------+
              IE-1      IE-2
```

- **IE-1 (MCS)**: Unknown-framework branch trusted route-like path strings (`/channels/...`) as sufficient endpoint evidence.
  - Mitigation: Keep strong route-path gate and add an inbound-handler-signature requirement for unknown TS/JS frameworks.
- **IE-2 (MCS)**: Function-level context (client-style parameters like `rest`, `payload`) was not used before emitting MAZ findings.
  - Mitigation: Require inbound-style parameter markers (`req/request/res/response/reply/ctx/context/next`) before reporting unknown-framework TS/JS findings.

### FT-2: false-negative guard

- **IE-3 (Guard)**: Unconventional inbound handlers without standard parameter names may be missed in unknown-framework contexts.
  - Mitigation: Scope is narrow to TS/JS unknown-framework branch; known framework detections remain unchanged and regressions keep route-like unknown-handler coverage active.

## 2026-04-12 - Issue #248: EDS false positives on typed TypeScript/TSX functions without JSDoc

### Top Event (TE-EDS-248)
EDS reports typed TS/TSX functions as unexplained complexity because Python-like doc requirements are applied.

### FT-1: false-positive branch

```
          TE-FP: typed TS/TSX function flagged as unexplained
                         |
                      OR-Gate
               +---------+---------+
              IE-1      IE-2
```

- **IE-1 (MCS)**: Missing JSDoc in TS/TSX was penalized even when the function signature already provides API intent.
  - Mitigation: Treat TS/TSX signatures with parameters as self-documenting evidence.
- **IE-2 (MCS)**: Missing explicit return annotation was penalized although TS often relies on inferred returns.
  - Mitigation: Add inferred-return evidence for self-documenting TS/TSX signatures and dampen score.

### FT-2: false-negative guard

- **IE-3 (Guard)**: Broad suppression could hide true explainability gaps in JavaScript or non-typed code.
  - Mitigation: Scope is bounded to TS/TSX signature heuristic; JS behavior remains explicitly regression-protected.

## 2026-04-12 - Issue #247: GCD false positives on declarative TS wrappers and strongly typed non-imperative functions

### Top Event (TE-GCD-247)
GCD reports declarative TypeScript wrappers and strongly typed non-imperative functions as guard-clause deficits.

### FT-1: false-positive branch

```
          TE-FP: declarative/typed TS wrappers reported as missing guards
                         |
                      OR-Gate
               +---------+---------+
              IE-1      IE-2
```

- **IE-1 (MCS)**: TS guard detection only accepted explicit early `if-throw/return` patterns, missing one-statement delegation wrappers.
  - Mitigation: Treat parameter-forwarding single-statement call-through wrappers as guarded.
- **IE-2 (MCS)**: Typed TS contracts in non-imperative functions were ignored, so statically constrained parameter contracts still counted as unguarded.
  - Mitigation: Treat strongly typed non-imperative TS functions as guarded when weak types are absent.

### FT-2: false-negative guard

- **IE-3 (Guard)**: New suppression could under-report true guard deficits in superficially simple wrappers.
  - Mitigation: Scope is bounded to call-through wrappers and non-imperative bodies; existing unguarded TS regression remains active.

## 2026-04-12 - Issue #246: SMS false positives in new extension/plugin workspaces

### Top Event (TE-SMS-246)
SMS reports expected dependency introduction in newly added plugin workspaces as system misalignment.

### FT-1: false-positive branch

```
          TE-FP: intentional new plugin dependencies reported as SMS drift
                         |
                      OR-Gate
               +---------+---------+
              IE-1      IE-2
```

- **IE-1 (MCS)**: SMS baseline is module-local and treats first-time plugin dependencies as novelty, even when the entire `extensions/<name>` or `plugins/<name>` workspace is new.
  - Mitigation: Detect newly introduced runtime plugin workspaces and suppress SMS novel-import findings inside those workspaces.
- **IE-2 (MCS)**: New plugin workspaces can introduce multiple domain packages at once, inflating score and severity despite expected architecture.
  - Mitigation: Workspace-level suppression for all-recent tracked files prevents severity inflation during initial plugin introduction.

### FT-2: false-negative guard

- **IE-3 (Guard)**: Suppression can hide real misalignment signals in the first iteration of a new workspace.
  - Mitigation: Scope is narrow (`extensions/*`, `plugins/*`) and conditioned on workspace recency; once a workspace has established history, SMS findings are emitted normally.

## 2026-04-12 - Issue #245: PFS cross-extension plugin diversity severity over-prioritization

### Top Event (TE-PFS-245)
PFS reports framework-facing plugin-boundary pattern diversity above informational severity in multi-plugin monorepos.

### FT-1: false-positive branch

```
          TE-FP: intentional cross-plugin diversity prioritized as drift urgency
                         |
                      OR-Gate
               +---------+---------+
              IE-1      IE-2
```

- **IE-1 (MCS)**: Framework-surface dampening and plugin-layout dampening were applied independently but did not force a final informational cap when both contexts were true.
  - Mitigation: Add combined-context terminal cap to `INFO` severity.
- **IE-2 (MCS)**: Multi-plugin extension layouts naturally produce API and error-handling variant diversity that is architecturally expected.
  - Mitigation: Preserve finding visibility in metadata while lowering urgency (`combined_plugin_framework_cap`).

### FT-2: false-negative guard

- **IE-3 (Guard)**: Combined-context cap could down-rank genuine local fragmentation inside extension API modules.
  - Mitigation: Cap only applies when both framework-facing and multi-plugin hints are active simultaneously; non-combined modules keep existing severity behavior.

## 2026-04-12 - Issue #244: MDS false positives on cross-plugin workspace duplication

### Top Event (TE-MDS-244)
MDS reports deliberate cross-plugin workspace duplicates as severe architectural drift.

### FT-1: false-positive branch

```
          TE-FP: intentional plugin/workspace duplication reported as severe drift
                         |
                      OR-Gate
               +---------+---------+
              IE-1      IE-2
```

- **IE-1 (MCS)**: Exact duplicate grouping marks copies in different `extensions/<name>` or `plugins/<name>` packages as `HIGH` by default.
  - Mitigation: Detect cross-workspace duplicate groups and cap to `INFO` with low score.
- **IE-2 (MCS)**: Near-duplicate path uses similarity-only severity assignment and ignores plugin isolation boundaries.
  - Mitigation: Apply cross-workspace pair heuristic and cap severity/score for these pairs.

### FT-2: false-negative guard

- **IE-3 (Guard)**: Broad suppression may hide real harmful duplication that should still be acted on.
  - Mitigation: Heuristic is strictly bounded to *different* plugin scopes; same-workspace duplicates remain actionable and covered by regression tests (`test_analyze_keeps_same_workspace_exact_duplicates_actionable_issue_244`).

## 2026-04-12 - Issue #243: CCC false positives for parallel implementations and explicit type imports

### Top Event (TE-CCC-243)
CCC reports expected parallel patterns or explicit type-import relationships as hidden coupling.

### FT-1: false-positive branch

```
          TE-FP: expected/explicit coupling reported as hidden coupling
                         |
                      OR-Gate
               +---------+---------+
              IE-1      IE-2
                         |
                        IE-3
```

- **IE-1 (MCS)**: Sibling runtime-variant files (`*-gateway`, `*-node`, etc.) co-change on shared contract updates without direct imports.
  - Mitigation: Runtime-variant suppression for same-directory sibling pairs with normalized variant-token stems.
- **IE-2 (MCS)**: Cross-extension plugin template entrypoints (`extensions/*/src/index.ts`) co-change by design when SDK contracts evolve.
  - Mitigation: Suppress cross-extension pairs only for identical template entrypoint suffixes (`src/index.{ts,js,tsx,jsx}`).
- **IE-3 (MCS)**: Relative TypeScript `import type` edges (e.g. `./types.js`) were unresolved by Python-centric relative resolver logic.
  - Mitigation: Relative resolver now normalizes relative paths and applies bounded JS-runtime -> TS-source extension aliases against known in-repo files.

### FT-2: false-negative guard

- **IE-4 (Guard)**: New pattern suppressions may hide real hidden coupling in edge cases that match variant/template shape.
  - Mitigation: Scope remains narrowly bounded; cross-extension non-template pairs stay reportable and are covered by regression tests.

## 2026-04-12 - Issue #242: DCA plugin entrypoint false positives

### Top Event (TE-DCA-242)
DCA reports plugin entrypoint exports (components/plugin-sdk) as dead code.

### FT-1: false-positive branch

```
          TE-FP: plugin entrypoint export reported as unused
                         |
                      OR-Gate
               +---------+---------+
              IE-1      IE-2
```

- **IE-1 (MCS)**: Static import graph cannot observe host-registry wiring or framework-driven dynamic rendering for plugin UI component modules.
  - Mitigation: Entrypoint dampening heuristic for `extensions/*` and `plugins/*` paths with `components` signals.
- **IE-2 (MCS)**: Plugin SDK entry modules (`plugin-sdk/*`) are consumed by external plugin hosts and are not always imported inside the same repository.
  - Mitigation: Entrypoint dampening for `plugin-sdk` path tokens plus explicit metadata marker.

### FT-2: false-negative guard

- **IE-3 (Guard)**: Dampening can under-prioritize truly unused exports in plugin entrypoint files.
  - Mitigation: Scope is bounded to extension/plugin entrypoint indicators only; findings are not fully suppressed (MEDIUM cap, no drop).

## 2026-04-12 - Issue #241: AVS hidden coupling FP on TypeScript ESM imports

### Top Event (TE-AVS-241)
AVS reports hidden coupling although a static import relationship exists in TypeScript ESM code.

### FT-1: false-positive branch

```
          TE-FP: hidden coupling reported despite real import edge
                         |
                      OR-Gate
               +---------+---------+
              IE-1      IE-2
```

- **IE-1 (MCS)**: Relative TS import specifier uses runtime extension (`../module.js`) while repository source file is `../module.ts`.
  - Mitigation: Extension alias candidates for relative ESM specifiers (`.js/.jsx/.mjs/.cjs` -> `.ts/.tsx/.mts/.cts`).
- **IE-2 (MCS)**: Resolver only checked module-like aliases and skipped normalized path-like lookups for relative imports.
  - Mitigation: Build and consult `path_to_file` index in `build_import_graph()` for normalized relative path candidates.

### FT-2: false-negative guard

- **IE-3 (Guard)**: Extension alias expansion could pick an unintended sibling file when multiple extension variants coexist.
  - Mitigation: Candidate resolution is limited to relative imports and known in-repo file paths; regression tests assert canonical `.js -> .ts` and `.mjs/.cjs -> .mts/.cts` mappings.

## 2026-04-12 - Issue #238: HSC false positives bei dynamischen Template-Literalen

### Top Event (TE-HSC-238)
HSC meldet dynamisch interpolierte Template-Literale als Hardcoded Secret.

### FT-1: false-positive branch

```
          TE-FP: runtime template token reported as hardcoded secret
                         |
                      OR-Gate
               +---------+---------+
              IE-1      IE-2
```

- **IE-1 (MCS)**: TS/JS-Literalerkennung extrahiert Inhalt zwischen Backticks und behandelt interpolierte Werte (`${...}`) wie statische String-Literale.
  - Mitigation: Fruehe Suppression fuer dynamische Template-Literale in `_evaluate_ts_assignment`.
- **IE-2 (MCS)**: Entropie-/Fallback-Pfad greift trotz runtime-Konstruktion und erzeugt HIGH/MEDIUM Findings.
  - Mitigation: Interpolierte Template-Literale werden vor Entropiepruefung ausgeschlossen.

### FT-2: false-negative guard

- **IE-3 (Guard)**: Echte Secrets, die zur Laufzeit per Template zusammengesetzt werden, koennen unterdrueckt werden.
  - Mitigation: Scope ist strikt auf interpolierte Templates begrenzt; statische Literale und bekannte Prefix-Tokens bleiben unveraendert detektierbar; neue Regressionen sichern OpenClaw-FP-Muster.

## 2026-04-12 - Issue #240: NBV TS try* nullable getter false positives

### Top Event (TE-NBV-240)
NBV meldet TypeScript `try*` nullable getter als Naming-Contract-Verletzung.

### FT-1: false-positive branch

```
          TE-FP: TS try* nullable getter reported as NBV violation
                         |
                      OR-Gate
               +---------+---------+
              IE-1      IE-2
```

- **IE-1 (MCS)**: `try_*`-Regel basiert auf Python-`try/except`-Erwartung und erkennt TS-Nullable-Getter-Semantik nicht.
  - Mitigation: TS-spezifische Contract-Erfuellung bei nullable Return-Signaturen (`|undefined`/`|null`).
- **IE-2 (MCS)**: Ohne nullable-Contract-Pfad wird best-effort Getter-Design als Defekt klassifiziert.
  - Mitigation: Prefix-begrenzte Heuristik nur fuer `try_*`; andere Regeln unveraendert.

### FT-2: false-negative guard

- **IE-3 (Guard)**: Nullable-Return-Signatur kann schwache `try*`-Implementierungen kaschieren.
  - Mitigation: Scope strikt auf `try_*` beschraenkt; bestehende Negativkontrollen fuer nicht-erfuellte Contracts bleiben aktiv.

## 2026-04-11 - Issue #237: DCA runtime plugin config false positives

### Top Event (TE-DCA-237)
DCA reports runtime-loaded plugin config exports as dead code.

### FT-1: false-positive branch

```
          TE-FP: runtime plugin config export reported as unused
                         |
                      OR-Gate
               +---------+---------+
              IE-1      IE-2
```

- **IE-1 (MCS)**: Static import graph cannot resolve dynamic plugin loading via runtime `import()` patterns.
  - Mitigation: Heuristic dampening for config-like files in `extensions/*` and `plugins/*`.
- **IE-2 (MCS)**: Config modules are over-prioritized with HIGH severity despite uncertain usage resolution.
  - Mitigation: Score dampening plus severity cap to MEDIUM and explicit metadata marker.

### FT-2: false-negative guard

- **IE-3 (Guard)**: Dampening may under-prioritize truly unused exports in plugin config modules.
  - Mitigation: Heuristic is scope-bounded (`extensions|plugins` + `config*`) and does not suppress findings completely.

## 2026-04-11 - Issue #235: CCC intra-package monorepo coupling false positives

### Top Event (TE-CCC-235)
CCC reports expected intra-package extension co-changes as hidden coupling.

### FT-1: false-positive branch

```
          TE-FP: expected extension-internal co-change reported as CCC finding
                         |
                      OR-Gate
               +---------+---------+
              IE-1      IE-2
```

- **IE-1 (MCS)**: Pair scoring had no package-boundary awareness and flagged co-change inside one extension package.
  - Mitigation: Suppress pairs sharing same monorepo subpackage scope.
- **IE-2 (MCS)**: Repositories without parseable in-scope package manifests still produced extension-internal FPs.
  - Mitigation: Fallback scope heuristic for `extensions/<name>/...`.

### FT-2: false-negative guard

- **IE-3 (Guard)**: Suppression could hide real accidental coupling within one extension.
  - Mitigation: Suppression remains strictly intra-subpackage; cross-extension pairs are still flagged and covered by regression tests.

## 2026-04-11 - Issue #236: HSC false positives fuer test-prefix secrets

### Top Event (TE-HSC-236)
HSC meldet testnahe Fixture-Strings als produktive Hardcoded Secrets.

### FT-1: false-positive branch

```
          TE-FP: test fixture constants reported as hardcoded secrets
                         |
                      OR-Gate
               +---------+---------+
              IE-1      IE-2
```

- **IE-1 (MCS)**: Secret-Variablen mit klaren Test-Praefixen (`TEST_*`, `MOCK_*`, ...) wurden im Known-Prefix-Pfad wie produktive Credentials behandelt.
  - Mitigation: Prefix-Suppression fuer explizit testmarkierte Variablennamen in allen HSC-Erkennungspfaden.
- **IE-2 (MCS)**: Test-helper-Pfade ausserhalb klassischer `tests/`-Muster (`*.test-helpers.*`) wurden nicht robust im HSC-Filter berücksichtigt.
  - Mitigation: Erweiterte HSC-Pfaderkennung fuer `test-helpers`/`test_helpers` und bestehende test-fixture Varianten.

### FT-2: false-negative guard

- **IE-3 (Guard)**: Test-Praefix-Suppression koennte in seltenen Faellen echte Leaks mit irrefuehrender Benennung unterdruecken.
  - Mitigation: Suppression ist strikt auf wenige explizite Prefixe begrenzt; bestehende Known-Prefix-Guards bleiben aktiv.

## 2026-04-11 - Issue #232: SMS test-only framework import false positives

### Top Event (TE-SMS-232)
SMS meldet Test-Framework-Imports aus Testdateien als produktive Novel Imports.

### FT-1: false-positive branch

```
          TE-FP: test-only imports reported as production novel imports
                         |
                      OR-Gate
               +---------+---------+
              IE-1      IE-2
```

- **IE-1 (MCS)**: `_module_imports` uebernimmt Testdatei-Imports in den Modulkontext und verfaelscht den Baseline-Vergleich.
  - Mitigation: Testdateien via zentrale `is_test_file`-Erkennung aus Baseline-Berechnung ausschliessen.
- **IE-2 (MCS)**: `_find_novel_imports` bewertet Imports aus `.test/.spec`-Dateien als produktive Neuimporte.
  - Mitigation: Testdateien vor Novel-Import-Erkennung filtern; Analyze-Pfad auf produktionsnahe Dateien begrenzen.

### FT-2: false-negative guard

- **IE-3 (Guard)**: Ueberbreiter Testdatei-Filter unterdrueckt echte produktive Novel Imports in Randfaellen.
  - Mitigation: Wiederverwendung der zentralen Testklassifikation (`ingestion/test_detection.py`) statt neuer SMS-Sonderregeln; Regressionstest fuer den konkreten vitest-Fall.

## 2026-04-11 - Issue #230: COD Logger-/Utility-FP-Reduktion

### Top Event (TE-COD-230)
COD klassifiziert Logger- und Utility-Module als starke Kohaesionsdefizite, obwohl deren Struktur absichtlich ist.

### FT-1: false-positive branch

```
          TE-FP: logger/utility module reported as COD deficit
                         |
                      OR-Gate
               +---------+---------+
              IE-1      IE-2
```

- **IE-1 (MCS)**: Log-Level-Fassaden (`trace/debug/info/warn/error`) haben absichtlich geringe paarweise Namensaehnlichkeit.
  - Mitigation: Logger-Mustererkennung ueber Dateiname (`logger`) oder >=50% logger-nahe Unit-Namen; starke Dempfung.
- **IE-2 (MCS)**: Utility-Dateien mit `utils/helpers/constants` werden ohne Kontext gleich streng bewertet wie heterogene Dump-Module.
  - Mitigation: Moderate Utility-Dateinamens-Dempfung, um erwartete Hilfsmodul-Varianz abzuschwaechen.

### FT-2: false-negative guard

- **IE-3 (Guard)**: Dempfung kann echte Inkohaerenz in Logger-Modulen teilweise verdecken.
  - Mitigation: Dempfung nur bei klaren Logger-Signalen; Utility-Dempfung bleibt begrenzt und bestehende COD-TP/TN-Regressionen bleiben aktiv.

## 2026-04-11 - Issue #231: DCA default-export helper false positives

### Top Event (TE-DCA-231)
DCA meldet modulinterne TS/JS Helper als dead code, obwohl sie vom default export aufgerufen werden.

### FT-1: false-positive branch

```
          TE-FP: module-internal helper reported as dead export
                         |
                      OR-Gate
               +---------+---------+
              IE-1      IE-2
```

- **IE-1 (MCS)**: DCA behandelt oeffentliche TS/JS Funktionen ohne Exportpruefung als exportiert.
  - Mitigation: In TS/JS nur Funktionen mit `is_exported=True` in den Exportkandidaten aufnehmen.
- **IE-2 (MCS)**: Dateien mit `export default` Facade + interne Helper erzeugen importbasierte Fehlklassifikation.
  - Mitigation: Nicht exportierte modulinterne Helper nicht als DCA-Ziel betrachten.

### FT-2: false-negative guard

- **IE-3 (Guard)**: Parser markiert Exportstatus falsch, dadurch koennen echte ungenutzte Exports entfallen.
  - Mitigation: Export-Detection Regressionstests fuer TS (`tests/test_ts_export_detection.py`) beibehalten und DCA-Verhalten gegenpruefen.

## 2026-04-11 - Issue #229: PFS Plugin-/Extension-Architektur FP-Reduktion

### Top Event (TE-PFS-229)
PFS bewertet absichtliche Plugin-Grenzvariation als HIGH-Drift in extension-basierten Repos.

### FT-1: false-positive branch

```
           TE-FP: plugin architecture reported as severe PFS fragmentation
                         |
                      OR-Gate
               +---------+---------+
              IE-1      IE-2
```

- **IE-1 (MCS)**: Modulpfad liegt unter `extensions/<plugin>/...`, aber PFS behandelt Varianten ohne Plugin-Grenzkontext.
  - Mitigation: Plugin-Layout-Erkennung (`extensions`/`plugins`/`packages`) im PFS-Signal.
- **IE-2 (MCS)**: Mehrere Plugin-Namensraeume koexistieren (`>=3`), Severity bleibt dennoch hoch.
  - Mitigation: Starke Score-Dempfung + Severity-Cap `HIGH/MEDIUM -> LOW` bei Multi-Plugin-Surface.

### FT-2: false-negative guard

- **IE-3 (Guard)**: Dempfung versteckt echte Fragmentierung in Core-Modulen.
  - Mitigation: Guard bleibt auf Plugin-Kontext begrenzt; Core-Module ohne Plugin-Scope bleiben unveraendert (Regression `test_core_error_handling_is_not_dampened`).

## 2026-04-11 - Issue #227: HSC FP bei Prefix/Endpoint/Test-Fixture/Profile-ID

### Top Event (TE-HSC-227)
HSC meldet nicht-geheime Konfigurations- und Fixture-Konstanten als Hardcoded Secret.

### FT-1: false-positive branch

```
          TE-FP: non-secret constants reported as HSC finding
                         |
                      OR-Gate
            +------------+------------+------------+
           IE-1         IE-2         IE-3         IE-4
```

- **IE-1 (MCS)**: Known-prefix-Pfad meldet kurze Token-Prefix-Marker (`sk-ant-oat01-`) als echte Token.
  - Mitigation: Prefix-Marker-Filter fuer markerartige kurze Literale mit Trailing-Delimiter.
- **IE-2 (MCS)**: Endpoint-Template-Literale (`${ISSUER}/idp/token`) werden nicht als Endpoint-Metadaten erkannt.
  - Mitigation: Suppression fuer endpointartige Variablennamen mit URL-/Template-Endpunktliteral.
- **IE-3 (MCS)**: `test-fixture`-Pfadvarianten werden nicht als Testkontext behandelt.
  - Mitigation: Zusätzliche test-fixture-Pfaderkennung in HSC.
- **IE-4 (MCS)**: Profil-ID-Konstanten (`*_PROFILE_ID = "anthropic:qa-setup-token"`) werden als Secret-Werte interpretiert.
  - Mitigation: Suppression fuer config-/profile-id-Literale.

### FT-2: false-negative guard

- **IE-5 (Guard)**: Prefix-Marker-Suppression verdeckt echte Known-Prefix-Secrets.
  - Mitigation: Suppression nur fuer kurze markerartige Prefix-Literale; Guard-Test fuer volle Known-Prefix-Tokens bleibt aktiv.

## 2026-04-11 - Issue #219: NBV TS style-only findings and duplicate output

### Top Event (TE-NBV-219)
NBV emits non-actionable TypeScript naming findings and duplicate low-severity findings.

### FT-1: false-positive branch

```
           TE-FP: style-only or duplicate NBV finding emitted
                         |
                      OR-Gate
               +---------+---------+---------+
              IE-1      IE-2      IE-3
```

- **IE-1 (MCS)**: Interface naming style (`I*` vs no-prefix) interpreted as drift.
  - Mitigation: Remove interface I-prefix convention check from NBV.
- **IE-2 (MCS)**: Mixed generic naming (`T` with `TName`) interpreted as drift.
  - Mitigation: Remove generic naming-style mix check from NBV.
- **IE-3 (MCS)**: Duplicated TS naming-check blocks emit findings twice.
  - Mitigation: Consolidate TS naming checks into a single block and guard with strict regression expectations.

### FT-2: false-negative guard

- **IE-4 (Guard)**: Removing style checks could hide user-preferred style-consistency findings.
  - Mitigation: Accepted by design; NBV scope remains architectural naming-contract drift, while style enforcement belongs to linters/project style guides.

## 2026-04-11 - Issue #215: NBV TS is*/has* bool-return extraction + fallback heuristics

### Top Event (TE-NBV-215)
NBV emits false positives for TypeScript `is*`/`has*` functions because bool-return contracts are not recognized.

### FT-1: false-positive branch

```
           TE-FP: TS bool-contract helper flagged by NBV
                         |
                      OR-Gate
               +---------+---------+---------+
              IE-1      IE-2      IE-3
```

- **IE-1 (MCS)**: Typed-arrow declarator return type is not extracted (`const isX: (...) => boolean = ...`).
  - Mitigation: parser fallback extracts `function_type.return_type` from declarator type annotations.
- **IE-2 (MCS)**: Type-predicate annotation (`x is Foo`) not treated as bool-compatible return contract.
  - Mitigation: bool-like return-type matcher recognizes TS type predicates.
- **IE-3 (MCS)**: Unannotated bool expressions (`typeof`, comparisons, `instanceof`, `in`, `!`) are treated as non-bool.
  - Mitigation: bounded fallback expression heuristic in `_ts_has_bool_return`.

### FT-2: false-negative guard

- **IE-4 (Guard)**: Heuristic over-accepts non-bool truthy/falsy expressions.
  - Mitigation: restrict accepted fallback shapes to explicit bool indicators; retain negative controls for non-bool wrappers and bare returns.

## 2026-04-11 - Issue #218: Zentralisierte Testdatei-Erkennung und finding_context-Angleichung

### Top Event (TE-CTX-218)
Mehrere Signale behandeln Testdateien inkonsistent, wodurch FP-Cluster oder uneinheitliche Priorisierung entstehen.

### FT-1: false-positive branch

```
           TE-FP: Testcode als Produktionsdrift priorisiert
                         |
                      OR-Gate
               +---------+---------+
              IE-1      IE-2      IE-3
```

- **IE-1 (MCS)**: Signal-spezifische lokale Testpfad-Heuristiken weichen voneinander ab
  - Mitigation: zentrale Klassifikation in `ingestion/test_detection.py`.
- **IE-2 (MCS)**: Findings transportieren Kontext nur optional in `metadata`
  - Mitigation: Top-Level-Feld `Finding.finding_context` + Synchronisierung mit Metadata.
- **IE-3 (MCS)**: Test-Kontext wird nicht konsistent auf Score/Severity angewandt
  - Mitigation: globaler Schalter `test_file_handling` und signalseitige Standardstrategien (`exclude`/`reduce_severity`).

### FT-2: false-negative guard

- **IE-4 (Guard)**: Überbreite Testklassifikation suppresses produktionsnahe Fixture-Dateien
  - Mitigation: explizite Fixture-Ausnahme (`tests/fixtures`, `test/fixtures`) in der zentralen Erkennung und Regressionstests.

## 2026-04-11 - Issue #214: NBV TS/JS ensure_* side-effect FP reduction

### Top Event (TE-NBV-214)
NBV emits false positives for TS/JS `ensure_*` helpers that fulfill contracts via idempotent side-effects instead of throw/value return.

### FT-1: false-positive branch

```
            TE-FP: TS/JS ensure-by-side-effect flagged by NBV
                         |
                      OR-Gate
               +---------+---------+---------+
              IE-1      IE-2      IE-3
```

- **IE-1 (MCS)**: Ensure helper creates directories via `mkdir`/`mkdirSync` with `void` return and no throw.
  - Mitigation: Accept mutating call patterns in TS ensure contract checker.
- **IE-2 (MCS)**: Ensure helper initializes state via property/index assignment (`obj.key = ...`, `obj[key] ??= ...`) without value-returning contract.
  - Mitigation: Accept stateful assignment/update expressions as contract-fulfilling side-effects.
- **IE-3 (MCS)**: Ensure helper registers cache/registry entries (`set`, `register`, `push`) in guarded branch without throw.
  - Mitigation: Accept bounded mutator-call markers in TS ensure checker.

### FT-2: false-negative guard

- **IE-4 (Guard)**: No-op `ensure_*` function accidentally accepted after relaxation.
  - Mitigation: Keep strict negative control where functions without throw, value return, and side-effect indicators remain findings.

## 2026-04-11 - Issue #213: MAZ unknown-framework false-positive suppression

### Top Event (TE-MAZ-213)
MAZ reports non-endpoint TypeScript functions as missing-authorization route handlers when framework detection is unknown.

### FT-1: false-positive branch

```
           TE-FP: non-endpoint TS function flagged as MAZ finding
                         |
                      OR-Gate
               +---------+---------+
              IE-1      IE-2
```

- **IE-1 (MCS)**: Generic object method call (for example `cache.get("key")`) interpreted as API route
  - Mitigation: when `framework == unknown` and language is TS/JS, require route-path evidence (`route` starts with `/` or wildcard `*`) before emitting finding.
- **IE-2 (MCS)**: Intentionally public auth bootstrap routes (`/login`, `/oauth/callback`, `/webhook`) emitted despite public intent
  - Mitigation: apply allowlist not only to function names, but also to route-path metadata.

### FT-2: false-negative guard

- **IE-3 (Guard)**: Real unauthenticated route missed for unknown framework due stricter guard
  - Mitigation: clear HTTP-style paths (`/users`, `/admin/*`) remain detectable; regression test ensures route-like unknown-framework cases still emit findings.

## 2026-06-15 — Phase 4: Complex Signal Ports (HSC/CXS/ISD/MAZ for TypeScript)

### Top Event (TE-P4-TS)
Phase 4 TS signal ports produce false positives or miss real findings in TypeScript codebases.

### FT-1: HSC TypeScript false-positive branch

```
           TE-FP: Non-secret TS assignments flagged as HSC
                         |
                      OR-Gate
               +---------+---------+
              IE-1      IE-2      IE-3
```

- **IE-1 (MCS)**: `process.env.SECRET_KEY` assigned to variable misidentified as hardcoded secret
  - Mitigation: `_evaluate_ts_assignment()` checks for `process.env.` and `import.meta.env.` prefixes first.
- **IE-2 (MCS)**: Placeholder values (`changeme`, `TODO`, `xxx`) still flagged
  - Mitigation: `_is_placeholder()` suppression reused from Python path.
- **IE-3 (MCS)**: URL constants with `token` in variable name flagged
  - Mitigation: `_looks_like_url()` suppression reused from Python path.

### FT-2: CXS TypeScript false-positive / false-negative

```
           TE: CXS under-/over-counts TS cognitive complexity
                         |
                      OR-Gate
               +---------+---------+
              IE-1      IE-2
```

- **IE-1 (FP)**: JSX elements miscounted as nesting increments
  - Mitigation: `_TS_NESTING_TYPES` explicitly enumerates only language-level control flow types; JSX excluded.
- **IE-2 (FN)**: Arrow function without variable binding yields `<anonymous>` name
  - Mitigation: Functional — findings still emitted with `<anonymous>` name; no loss of detection.

### FT-3: ISD TypeScript false-positive / false-negative

```
           TE: ISD misclassifies TS security configs
                         |
                      OR-Gate
               +---------+---------+
              IE-1      IE-2
```

- **IE-1 (FP)**: `secure: false` in non-cookie object flagged as insecure cookie
  - Mitigation: Context keyword check (`cookie`, `session`, `express-session`) on same line.
- **IE-2 (FN)**: Dynamic CORS origin config (`origin: allowedOrigins`) not detected
  - Mitigation: Accepted risk — regex detection fundamentally limited to literal patterns.

### FT-4: MAZ TypeScript false-positive / false-negative

```
           TE: MAZ misclassifies TS endpoint auth status
                         |
                      OR-Gate
               +---------+---------+
              IE-1      IE-2
```

- **IE-1 (FP)**: Custom auth middleware with non-standard name not recognized
  - Mitigation: `_TS_AUTH_MARKERS` frozenset covers 30+ common auth identifiers; extensible.
- **IE-2 (FN)**: NestJS custom guard class not matched by `@UseGuards` decorator search
  - Mitigation: Accepted risk — decorator name matching covers standard patterns; custom guards documented as limitation.

## 2026-04-11 - Issue #212: HSC FP-Reduktion (Env-Name-/Marker-Konstanten)

### Top Event (TE-HSC-212)
HSC meldet nicht-geheime Konstanten (Env-Namen, Marker/Sentinels) als Hardcoded Secret.

### FT-1: false-positive branch

```
          TE-FP: non-secret constants reported as HSC finding
                         |
                      OR-Gate
               +---------+---------+
              IE-1      IE-2      IE-3
```

- **IE-1 (MCS)**: Env-Var-Namensliteral (`AWS_SECRET_ACCESS_KEY`) wird als Secret-Wert interpretiert
  - Mitigation: `_is_env_var_name_literal()` erkennt ALL_CAPS env-name Literale fuer env-benannte Variablen und suppresses.
- **IE-2 (MCS)**: Marker/Sentinel-Konstanten (`*_MARKER`, `*_PREFIX`, `*_ERROR_CODE`) triggern wegen secret-shapigem Variablennamen
  - Mitigation: `_is_marker_constant_name()` suppresses marker-/message-orientierte Konstantennamen.
- **IE-3 (MCS)**: Endpoint-/Metadata-Konstanten enthalten Token-Woerter, aber keine Credentials
  - Mitigation: bestehende URL- und Kontext-Suppressionspfade bleiben aktiv.

### FT-2: false-negative guard

- **IE-4 (Guard)**: neue Suppression maskiert echte Prefix-Secrets in env-/marker-benannten Variablen
  - Mitigation: Known-Prefix-Erkennung (`ghp_`, `sk-`, `AKIA`, ...) bleibt im Ablauf vor allen neuen Suppressionspfaden; Guard-Regressionen vorhanden.

## 2026-04-11 - Issue #211: TSB test/spec false-positive reduction

### Top Event (TE-TSB-211)
Type Safety Bypass (TSB) reports large false-positive volume from TypeScript test/spec and mock files.

### FT-1: false-positive branch

```
           TE-FP: test-only bypasses reported as production debt
                         |
                      OR-Gate
               +---------+---------+
              IE-1      IE-2      IE-3
```

- **IE-1 (MCS)**: `*.test.ts` / `*.spec.tsx` analyzed as regular source
  - Mitigation: suffix-based skip list in TSB signal.
- **IE-2 (MCS)**: `__tests__/` paths not excluded in TSB loop
  - Mitigation: explicit directory marker exclusion.
- **IE-3 (MCS)**: `__mocks__/` scaffold files treated as production findings
  - Mitigation: explicit directory marker exclusion.

### FT-2: false-negative guard

- **IE-4 (Guard)**: over-broad test-path regex suppresses real production files
  - Mitigation: narrow, explicit path rules + parametrized regression tests for allowed skip patterns only.

## 2026-04-11 - ADR-055: Dependency-aware Signal Cache Keying

### Top Event (TE-CACHE-055)
Signal cache returns stale or over-invalidated results after small repository edits.

### FT-1: stale cache reuse (false-negative equivalent)

```
           TE: stale findings reused after change
                         |
                      OR-Gate
               +---------+---------+
              IE-1      IE-2      IE-3
```

- **IE-1 (MCS)**: file_local key not bound to current file hash
  - Mitigation: per-file key uses current parse content hash.
- **IE-2 (MCS)**: git-dependent key omits commit/file-history dimensions
  - Mitigation: git-state fingerprint adds commit hashes and file-history metrics.
- **IE-3 (MCS)**: unknown cache scope falls through to unstable behavior
  - Mitigation: conservative fallback to `repo_wide` scope.

### FT-2: unnecessary invalidation (false-positive equivalent)

- **IE-4 (MCS)**: repo-wide hash used for all signals regardless of dependency scope
  - Mitigation: dependency-aware scope mapping + feature-flagged rollout.

## 2026-04-11 - Issue #210: NBV TS/JS ensure_* upsert FP reduction

### Top Event (TE-NBV-210)
NBV emits false positives for TypeScript/JavaScript `ensure_*` helpers that guarantee existence via upsert/get-or-create patterns.

### FT-1: False positive branch - TS/JS upsert semantics treated as Python ensure semantics

```
            TE-FP: TS/JS ensure_* upsert flagged by NBV
                         |
                      OR-Gate
               +---------+---------+
              IE-1      IE-2      IE-3
```

- **IE-1 (MCS)**: TS/JS `ensure_*` checker required `throw` unconditionally
  - Mitigation: language-aware ensure checker accepts `throw` OR value-returning `return`
- **IE-2 (MCS)**: Return-value guarantee paths (`return obj`) were not recognized as contract-satisfying
  - Mitigation: explicit `_ts_has_return_value()` helper added
- **IE-3 (MCS)**: Upsert branch (`if missing -> create -> return`) interpreted as violation despite guarantee semantics
  - Mitigation: TS/JS ensure path validated by throw/value-return semantics instead of Python-only raise rule

### FT-2: False negative guard

- **IE-4 (Guard)**: Bare `return;` in TS/JS `ensure_*` is incorrectly accepted
  - Mitigation: rule requires value-returning return; bare return remains a violation (regression test added)

## 2026-04-11 - Issue #209: NBV TypeScript async bool-wrapper FP reduction

### Top Event (TE-NBV-209)
NBV emits false positives for TypeScript is_*/has_* functions that return async bool wrappers.

### FT-1: False positive branch — async bool wrapper classified as non-bool

```
            TE-FP: async bool wrapper flagged by NBV
                         |
                      OR-Gate
               +---------+---------+
              IE-1      IE-2      IE-3
```

- **IE-1 (MCS)**: Return annotation `Promise<boolean>` not unwrapped before bool contract check
  - Mitigation: recursive wrapper unwrapping accepts terminal boolean
- **IE-2 (MCS)**: Return annotation `PromiseLike<boolean>` not recognized as bool-compatible wrapper
  - Mitigation: wrapper allowlist expanded (`Promise`, `PromiseLike`, `Observable`)
- **IE-3 (MCS)**: Nested wrappers (`Promise<PromiseLike<boolean>>`) stop at first generic layer
  - Mitigation: bounded recursive unwrapping (max depth 6)

### FT-2: False negative guard

- **IE-4 (Guard)**: Non-bool payloads in wrappers (e.g. `Promise<string>`) accepted by mistake
  - Mitigation: terminal type must exactly match `bool`/`builtins.bool`/`boolean`; regression test keeps `Promise<string>` as finding

## 2026-04-13 - ADR-047–051: Actionability Hardening (MAZ/EDS/PFS/AVS/CCC)

### Top Event (TE-AVS-050)
AVS blast-radius churn guard produces false negatives (stable-but-dangerous modules skipped).

### FT-1: False negative — high-blast-radius module silently skipped

```
        TE-FN: module with br > threshold skipped due to churn guard
                            |
                         OR-Gate
              +-------------+-------------+
             IE-1           IE-2          IE-3
```

- **IE-1 (MCS)**: `change_frequency_30d = 0` for a module that changed once 31 days ago (outside window)
  - Mitigation: Accept; 30-day window is consistent with TVS convention; very-recently-destabilized modules trigger churn > 1.0
- **IE-2 (MCS)**: `blast_radius = 50` exactly — dual guard applies, module is skipped
  - Mitigation: Threshold set at `<= 50` — blast_radius > 50 alone bypasses the guard regardless of churn
- **IE-3 (MCS)**: `file_histories` is empty (non-git context) → default churn = 0 → guard may suppress
  - Mitigation: Non-git repos by definition have no commit-churn data; existing AVS findings retain scoring

### Top Event (TE-PFS-049, TE-EDS-048, TE-MAZ-047, TE-CCC-051)
Other hardening signals produce false negatives due to threshold or filter changes.

```
        TE-FN: finding suppressed by new filter/threshold
                            |
                         OR-Gate
              +-------+-------+-------+-------+
             EDS-1  PFS-1  MAZ-1  CCC-1
```

- **EDS-1**: Private helper at weighted_score 0.40–0.44 suppressed by 0.45 threshold
  - Mitigation: Defect-correlated override reduces threshold to 0.30; test coverage for correlated helpers retained
- **PFS-1**: canonical_ratio < 0.10 → HIGH→MEDIUM severity downgrade misses critical fragmentation
  - Mitigation: Downgrade bounded (never skips LOW); raw `frag_score` in metadata allows manual triage
- **MAZ-1**: CRITICAL severity bump may cause CI gate failures in repos where MAZ findings were previously HIGH
  - Mitigation: A2A exemption note in fix text; users can `drift:ignore` intentional public endpoints
- **CCC-1**: 60-char message truncation hides key co-change reason
  - Mitigation: Accept; 3-sample window + intentional/accidental branch template provides sufficient context

## 2026-04-11 - ADR-041: PHR Runtime Import Attribute Validation

### Top Event (TE-PHR-041)
PHR runtime attribute check produces false positives or misses real missing attributes.

### FT-1: False positive branch — runtime attribute FP

```
          TE-FP: hasattr returns False for valid attribute
                        |
                     OR-Gate
              +------+------+
             IE-1   IE-2   IE-3
```

- **IE-1 (MCS)**: Version mismatch — module installed but attribute removed/renamed in current version
  - Mitigation: metadata `runtime_validated: true`; finding includes module and attribute name for triage
- **IE-2 (MCS)**: Module `__getattr__` not invoked by `hasattr` (lazy module proxy)
  - Mitigation: `hasattr()` does invoke `__getattr__` per Python data model; no known stdlib/popular package breaks this
- **IE-3 (MCS)**: Import timeout → attribute check skipped, Phase B phantom stands
  - Mitigation: Configurable timeout (5s default); daemon thread; sys.modules fast path

### FT-2: False negative branch — missed missing attribute

```
          TE-FN: real missing attribute not detected
                        |
                     OR-Gate
              +------+------+
             IE-4   IE-5   IE-6
```

- **IE-4 (MCS)**: Module raises exception on import → `_import_module_safe` returns None
  - Accept: Broken packages cannot be validated; Phase B finding unchanged
- **IE-5 (MCS)**: Platform-conditional attribute (exists on Linux, absent on Windows)
  - Accept: Same limitation as Phase B; analysis reflects host environment
- **IE-6 (MCS)**: Feature disabled (opt-in default) → no runtime check runs
  - Accept: By design; users must explicitly enable `phr_runtime_validation: true`

## 2026-04-10 - ADR-040: PHR Third-Party Import Resolver

### Top Event (TE-PHR-040)
PHR third-party import check produces false positives or misses real phantom imports.

### FT-1: False positive branch — third-party import FP

```
            TE-FP: find_spec flags valid import as phantom
                        |
                     OR-Gate
         +------+------+------+
        IE-1   IE-2   IE-3   IE-4
```

- **IE-1 (MCS)**: Package installed in CI but not in local venv → `find_spec` returns None
  - Mitigation: metadata hint `confidence: env_dependent`; documentation guidance
- **IE-2 (MCS)**: Conditional import (`try/except ImportError`) not recognized
  - Mitigation: `_is_in_try_except_import_error()` AST guard
- **IE-3 (MCS)**: TYPE_CHECKING import not recognized
  - Mitigation: `_collect_type_checking_import_ids()` pre-pass
- **IE-4 (MCS)**: Namespace package without `__init__.py`
  - Mitigation: `find_spec` handles PEP 420 namespace packages natively

### FT-2: False negative branch — missed phantom import

```
            TE-FN: real phantom import not flagged
                        |
                     OR-Gate
              +------+------+
             IE-5   IE-6   IE-7
```

- **IE-5 (MCS)**: Dynamic import via `importlib.import_module(variable)`
  - Accept: Not statically resolvable
- **IE-6 (MCS)**: Package installed but wrong version (missing class/function)
  - Accept: Phase C (ADR-041) will address attribute-level validation
- **IE-7 (MCS)**: String-based plugin loaders
  - Accept: Not statically resolvable

## 2026-06-14 - ADR-039: Signal Activation (MAZ/PHR/HSC/ISD/FOE)

### Top Event (TE-0)
Newly scoring signals produce unacceptable false positive rates or composite score inflation after activation.

### FT-1: False positive branch — individual signal FP

```
            TE-FP: scoring signal emits low-value finding
                        |
                     OR-Gate
         +------+------+------+------+
        IE-1   IE-2   IE-3   IE-4   IE-5
        MAZ:    ISD:    HSC:   PHR:   FOE:
        dev-    dev-    templ  3rd-   barrel
        handler config  value  party  file
```

- MCS-1 (MAZ): Dev-server handler without auth decorator → suppressed by CLI-path/dev-path fence
- MCS-2 (ISD): Dev-only `DEBUG=True` → suppressed by `drift:ignore-security` directive
- MCS-3 (HSC): Template placeholder matches entropy heuristic → suppressed by `_is_safe_value`
- MCS-4 (PHR): Third-party import not in project tree → suppressed by known-module allowlist
- MCS-5 (FOE): Re-export barrel file → suppressed by barrel-file detection

### FT-2: Score inflation branch — composite score distortion

```
            TE-SCORE: composite score breaks comparability
                        |
                     AND-Gate
         +--------------+--------------+
   IE-1: multiple new          IE-2: combined weight
   signals fire on same        contribution exceeds
   module simultaneously       recalibration tolerance
```

- MCS-1: All 5 signals fire simultaneously AND total weight (0.065) shifts score significantly → bounded by conservative weights and module-level aggregation
- Mitigation: Baseline comparison via `drift_diff`; weight sum is ~6.5% of total

### Verification
- Ground-truth: 5 ISD fixtures, 1 MAZ TN, 6 HSC, 3 FOE, 17 PHR (all passing)
- Precision/recall: `pytest tests/test_precision_recall.py -v`
- Baseline diff: `drift analyze --repo . --format json --exit-zero`

## 2026-04-10 - TS Type-Safety-Bypass detection path

### Top Event (TE-0)
Type-safety bypass in TypeScript files is not reported or is over-reported after signal expansion.

### FT-1: False negative branch

```
        TE-FN: real TS bypass missed
           |
            AND-Gate
       +-----------+-----------+
      IE-1: AST form not       IE-2: bypass syntax
        matched by rule           present only in
        matcher                    unsupported variant
```

- MCS-1: unsupported AST variant + bypass expression present -> FN
- Mitigation: add variant fixtures and keep AST walker coverage broad across TS and TSX.

### FT-2: False positive branch

```
        TE-FP: intentional TS escape flagged
           |
            AND-Gate
       +-----------+-----------+
      IE-1: project allows     IE-2: expression matches
        controlled escapes       generic bypass rule
```

- MCS-1: controlled migration escape + generic pattern match -> FP
- Mitigation: low severity defaults, metadata detail for quick triage, fixture coverage for clean/moderate/severe examples.

## 2026-04-13 - ADR-036/037/038: AVS/DIA/MDS FP-Reduction

### Top Event (TE-0)
FP-reduction logic incorrectly suppresses a true positive finding for AVS, DIA, or MDS.

### FT-1: AVS models Omnilayer false negative

```
                         TE-AVS: real models/ violation missed
                                      |
                                   AND-Gate
                         +------------+------------+
                   IE-1: models/ is      IE-2: project uses models/
                   in _OMNILAYER_DIRS    as strict DB layer (rare)
```

- MCS-1: `models` in Omnilayer AND project treats it as strict layer → FN
- Mitigation: configurable `omnilayer_dirs` — user can remove `models` if their project needs strict layer enforcement

### FT-2: MDS protocol skip false negative

```
                         TE-MDS: real protocol duplication missed
                                      |
                                   AND-Gate
                         +------------+------------+
                   IE-1: function name   IE-2: classes have genuinely
                   in _PROTOCOL_METHOD_  duplicated non-trivial body
                   NAMES                 beyond protocol interface
```

- MCS-1: Protocol-method name match AND genuine duplication → FN
- Mitigation: protocol set is narrow (20 names); only bare-name + different-class qualifies

### FT-3: MDS thin-wrapper false negative

```
                         TE-MDS: wrapper with real behavior missed
                                      |
                                   AND-Gate
                         +------------+------------+
                   IE-1: LOC <= 5        IE-2: wrapper adds
                                         meaningful transform
                                         (not just delegation)
```

- MCS-1: Short function with single Call AND meaningful transform → FN
- Mitigation: `_is_thin_wrapper` requires exactly 1 Call node; any additional logic breaks the gate

### Verification
- Ground-truth fixtures: `AVS_MODELS_OMNILAYER_TN`, `MDS_CONFOUNDER_PROTOCOL_METHODS_TN`, `MDS_CONFOUNDER_THIN_WRAPPER_TN`, `MDS_CONFOUNDER_NAME_DIVERSE_TN`
- Precision/recall test: `pytest tests/test_precision_recall.py -v`

## 2026-04-12 - ADR-035: PHR calibration over-suppression risk

### Top Event (TE-0)
`phantom_reference` emits no actionable finding for a real unresolved reference in a repository where calibration data is present, due to over-aggressive per-repo dampening.

### FT-1: TE-0 <- AND-Gate

```
                    TE-0: real PHR miss after calibration
                               |
                            AND-Gate
                   +-----------+-----------+
              IE-1: calibration active   IE-2: dampening weight
                    for current repo            too high for this case
```

- IE-1 causes:
  - repository fingerprint matches a stored calibration profile
  - calibration file is valid and loaded successfully
- IE-2 causes:
  - repeated FP feedback for similar references biases local pattern score
  - conservative floor is not reached before severity tier shifts below reporting threshold

### Minimal Cut Set
| MCS | Basis-Ereignis | SPOF | Mitigation |
|---|---|---|---|
| MCS-1 | Valid local calibration profile + biased FP-heavy feedback cluster for matching PHR pattern | Nein (AND path) | Cap dampening, enforce minimum evidence threshold, fallback to default weights when confidence is low |

### Verification
- `tests/test_calibration.py` validates calibration loading, bounds, and safe fallback behavior.
- `tests/test_phantom_reference.py` validates calibrated vs uncalibrated reporting behavior.
- Benchmark evidence for ADR-035 captured in versioned feature-evidence artifact.

## 2026-04-07 - PFS FTA v1: pfs_002 recall = 0 (RETURN_PATTERN SPOF)

### Top Event (TE-0)
`PatternFragmentationSignal.analyze()` liefert kein Finding für pfs_002 ("return_pattern: 3 Varianten in models/user.py"), obwohl `must_detect=true` gilt — beobachtbar als `detected=0`, Gesamt-PFS-Recall = 0.5.

### FT-1: TE-0 ← AND-Gate (beide Bedingungen gleichzeitig wahr)

```
                    TE-0: pfs_002 — kein Finding
                             │
                          AND-Gate
                    ┌────────┴────────┐
               IE-1: pr.patterns = []      IE-2: all_patterns kein
               für models/user.py          RETURN_PATTERN-Key
                    │                      (Konsequenz aus IE-1)
                 AND-Gate
        ┌──────────┴────────────┐
  BE-A1-T: kein             BE-B1-P: kein
  Extraktions-              RETURN_PATTERN
  Pfad in _process_function im PatternCategory-Enum
```

### Minimal Cut Set
| MCS | Basis-Ereignis | SPOF | Recall-Impact | Status |
|-----|---------------|------|---------------|--------|
| MCS-1 | BE-A1-T: kein Return-Extraktionspfad in `_process_function()` | Ja | 0.5 → 1.0 | **Mitigated** — `_fingerprint_return_strategy()` + `PatternCategory.RETURN_PATTERN` |

### Verification
- `test_return_strategy_mutation_benchmark_scenario` — exact pfs_002 scenario
- `test_return_pattern_two_variants_detected` — PFS integration
- `PFS_RETURN_PATTERN_TP` ground-truth fixture
- Mutation benchmark: pfs detected=2/2, recall=1.0

---

## 2026-04-07 - SMS FTA v1: sms_001 recall = 0 (2 independent SPOFs)

### Top Event (TE-0)
`SystemMisalignmentSignal.analyze()` liefert `[]` für Mutation `sms_001` im `_mutation_benchmark.py`-Lauf (synthetisches Python-Web-App-Repo), obwohl `outlier_module.py` domain-fremde Imports in einen HTTP-Handler-Kontext einschleust und `must_detect=true` gilt.
Evidence: `"detected": 0`, `"recall": 0.0` in `benchmark_results/mutation_benchmark.json` (vor Fix, 2026-04-07).
Systemgrenze: `SystemMisalignmentSignal.analyze()` von Eingabe `parse_results`/`file_histories` bis Rückgabewert `[]`.

### FT-1: TE-0 ← OR-Gate (2 unabhängige Äste)

#### Ast A: 10%-Guard bricht Analyse ab (AND-Gate)
Bedingung A1: `established_count / len(parse_results) < 0.10`
- A1a: Alle Baseline-Dateien teilen Initial-Commit-Timestamp „heute“ → kein Datei-last_modified < cutoff (14-Tage-Fenster).
  - BE-A1a-T: Benchmark-Skript schreibt alle Dateien vor `git init` in denselben Commit ohne explizite Datumssetzung.
  - BE-A1a-P: Keine Datum-Spreizung für Baseline-Dateien im Corpus-Setup vorgesehen.
  - BE-A1a-H: Guard-Threshold 0.10 für shallow-clone-Schutz konzipiert, nicht für synthetische Repos ohne temporale Streuung.
- A1b: ~25 Python-Dateien insgesamt (`len(parse_results)` groß).
Bedingung A2: `recency_days = 14` (Standardwert, kein thresholds-Override).
**MCS-2 (SPOF):** `{ established_count = 0 } ∧ { len(parse_results) > 10 }` → Guard feuert, `return []`.

#### Ast B: `_find_novel_imports()` gibt leere Liste zurück (AND über alle 7 Imports)
Alle 7 Imports in `outlier_module.py` (`ast`, `dis`, `ctypes`, `struct`, `mmap`, `multiprocessing`, `xml.etree.ElementTree`) ∈ `_STDLIB_MODULES` → `_is_stdlib_import()` = True → skip.
- BE-B1-T: `_STDLIB_MODULES` ist bewusst vollständig — verhindert FP, macht stdlib-Injection unsichtbar.
- BE-B1-P: Fixture beschreibt „Novel dependencies“, injiziert aber ausschließlich stdlib — konzeptuell falsche Kategorie.
- BE-B1-H: Fixture-Autor verstand „novel“ als „domain-unüblich“; Signal definiert „novel“ als „nicht im Third-Party-Baseline“ — Begriffskonflikt undokumentiert.
**MCS-1 (SPOF):** Alle Imports stdlib → leere Novel-Liste → `[]`.

### Common Cause Failure
Die Fixture-Generierung legt alle Baseline-Dateien ohne explizites Datum an: aktiviert gleichzeitig Ast A (`established_count = 0`) und stellt sicher, das Ast B nicht durch nachträglichen recency-Check korrigiert werden kann. Dieselbe Design-Entscheidung im Corpus-Builder triggert beide Fehlerkanäle.

### Minimal Cut Sets
| MCS | Bedingung | SPOF | Behoben durch |
|-----|-----------|------|---------------|
| MCS-1 | Alle 7 Imports ∈ `_STDLIB_MODULES` | Ja | Fixture: Third-Party-Imports (`numpy`, `cffi`, `msgpack`) |
| MCS-2 | `established_count = 0` bei großem `parse_results` | Ja | Initial-Commits auf Feb 2026 zurückdatiert |

### Verification
- Mutation benchmark post-fix: `sms_001` detected = 1, recall = 100%, Gesamt-Recall 16/17 = 94%.
- 2056/2056 Test-Suite grün nach Fix.
- Fix in `scripts/_mutation_benchmark.py` (kein Signal-Code geändert).

---

## 2026-04-07 - AVS FTA v1: co-change precision failure (3 primary MCS, 1 latent MCS)

### Top Event (TE)
`avs_co_change` emittiert ein `Finding[architecture_violation]` für ein Datei-Paar `(file_a, file_b)` innerhalb der Drift-Analysemaschine, obwohl kein strukturelles Koppelungsproblem besteht — beobachtbar als Disputed/FP-Label in der Ground-Truth-Auswertung, ausgelöst wenn `_check_co_change` auf Repos mit Flat-Package-Struktur, Test-Source-Ko-Evolution oder Bulk-Commit-Mustern angewendet wird.
Evidence: 10/10 Disputed-Fälle in `drift_self`-Stichprobe, `precision_strict = 0.3`, n=20, 2026-03-25.
Scope: Nur `avs_co_change` (rule_id). Sub-Checks `avs_circular_dep` und `avs_blast_radius` produzieren in der Stichprobe ausschließlich TPs.

### FT-1: avs_co_change = False/Disputed positive (OR-Gate)
Gate: OR — jeder der drei Äste reicht allein aus.

#### IE-1: Same-Package-Ko-Evolution (AND-Gate)
Beide Bedingungen müssen gleichzeitig gelten.
- IE-1a [Technical]: `build_co_change_pairs` liefert Paar mit `co_change_count ≥ threshold` und `confidence > 0.2` für Geschwisterdateien im selben Paketverzeichnis.
  - BE-1a-T: `_check_co_change` enthält keine Guard-Condition `os.path.dirname(file_a) != os.path.dirname(file_b)` — fehlende Guard auf Code-Ebene (`architecture_violation.py:1029-1063`).
  - BE-1a-P: Kalibrierung erfolgte auf MVC-Repos mit expliziten Layer-Directories; Flat-Package-Tools nicht als Validierungsfall getestet.
  - BE-1a-H: AVS-Anforderung "hidden logical dependencies not visible in the import graph" schließt sister-module co-evolution nicht aus — Ambiguität bei Formulierung der Signal-Semantik.
- IE-1b [Technical]: `graph.has_edge(file_a, file_b) = False`, weil Geschwister-Signaldateien keine direkte Import-Abhängigkeit benötigen (Kopplung via `@register_signal`-Registry, nicht via Import).
  - BE-1b-T: `@register_signal`-Dekorator bindert Klasse über globale Map ohne Import-Edge; `build_import_graph` folgt keine Dekorator-Calls.
  - BE-1b-P: Einziger Suppressor in `_check_co_change` ist direkter Import-Edge; kein Proxy-Coupling-Check (Registry, shared base class) vorhanden.
  - BE-1b-H: Design-Annahme "kein Import-Edge → hidden coupling" war für Legacy-MVC valide, wurde für Plugin/Registry-Pattern vor Deployment nicht getestet.

#### IE-2: Test-Source-Filtering-Inkonsistenz (AND-Gate)
- IE-2a [Technical]: `known_files` enthält Testdateien, weil es aus ungefilterten `parse_results` gebaut wird: `known = {pr.file_path.as_posix() for pr in parse_results}` (Common Cause CC-1).
  - BE-2a-T: Einzelne inkonsistente Variable-Zuweisung in `analyze()` — `parse_results` statt `filtered_prs` für `known`; der Graph wird korrekt aus `filtered_prs` gebaut, `known` nicht.
  - BE-2a-P: Kein Test prüft, dass `avs_co_change` für `(tests/test_foo.py, src/foo.py)` mit hoher Co-Change-Frequenz kein Finding emittiert.
  - BE-2a-H: Der Scope der `filtered_prs`-Entscheidung (Testdateien aus Graph-Analyse) wurde nicht als relevant für den `has_edge`-Suppressor dokumentiert; Engineer verwendete `parse_results` ohne Downstream-Konsequenz zu erkennen.
- IE-2b [Technical]: `graph` enthält keine Testdateien → `has_edge` für Test-Source-Kante strukturell immer False; Suppressor ist blind für Test-Source-Paare.

#### IE-3: Bulk-Commit-Inflation (AND-Gate)
- IE-3a [Technical]: Commit berührt ≥ N Dateien gleichzeitig (Release-Commit, FMEA-Sweep, Score-Update).
  - BE-3a-T: `build_co_change_pairs` hat keine Commit-Größen-Normalisierung; ein Commit mit 30 Dateien zählt gleich wie einer mit 2.
  - BE-3a-P: Drift selbst produziert regelmäßige "all-signals-sweep"-Commits, die alle Signaldateien gemeinsam berühren — systematische Inflation in der Selbstanalyse.
  - BE-3a-H: Confidence-Metrik wurde für Branching-Workflow (ein Issue → wenige Dateien) konzipiert; Trunk-based Development mit Sweep-Commits nicht als Kalibrierungsfall berücksichtigt.
- IE-3b [Technical]: `confidence`-Formel gewichtet nach Commit-Anzahl, nicht nach Commit-Größe — kein Diskontierungsfaktor für Bulk-Commits in `CoChangePair.confidence`.

### FT-2: Mitigation trade-off risk (FN potential)
- Top event: Gegenmaßnahmen für FT-1 können legitime Hidden-Coupling-Findings unterdrücken.
- Branch A (MCS-1 Fix: same-directory guard): Echte Cross-Boundary-Paare in Repos, die alle Module im selben Root-Directory halten (seltenes Anti-Pattern), werden unterdrückt. Risiko: sehr niedrig — strukturell saubere Repos haben Layer-Directories.
- Branch B (MCS-2 Fix: test-file filter auf `known`): Echtes Test-Source-Coupling (z.B. ein Test, der ein Modul über reflection steuert) wird nicht mehr als co_change gemeldet. Risiko: negligible — solche Fälle sind in Import-Graph-Analyse bereits sichtbar.
- Branch C (MCS-3 Fix: Commit-Größen-Diskontierung): Legitimes Co-Change-Pattern in großen Commits wird nicht erkannt wenn der Schwellwert zu aggressiv ist. Risiko: mittel — erfordert sorgfältige Kalibrierung des Diskontierungsfaktors.

### Common Causes
| ID | Ursache | Betroffene MCS |
|----|---------|----------------|
| CC-1 | `known_files` und `filtered_prs` divergieren durch inkonsistente Filter-Anwendung in `analyze()` | MCS-1, MCS-2 |
| CC-2 | `_check_co_change` kennt keinen Package/Namespace-Kontext für Dateipaare | MCS-1, MCS-3 |

### Minimal Cut Sets
| MCS | Basis-Ereignisse | Wahrscheinlichkeit | Evidenz | FP-Reduktion |
|-----|------------------|--------------------|---------|--------------|
| MCS-1 | BE-1a-T: same-directory pair, kein guard | Hoch | 7/10 Disputed: beide in `signals/` | −7 |
| MCS-2 | BE-2a-T: test-file in `known_files`, nicht im graph | Mittel | `config.py ↔ test_config.py` Disputed | −1 |
| MCS-3 | BE-3a-T + BE-3b: bulk-commit ohne Diskontierung | Mittel | Drift sweep-commits | −2 (geschätzt) |
| MCS-4 (latent) | `_infer_layer(models.py) = 2` + models.py cross-cuttend importiert + kein omnilayer-match | Niedrig | Kein Disputed bisher (avs_upward_import) | TBD |

SPOF-Diagnose: MCS-1 und MCS-2 werden jeweils durch eine einzige fehlende Code-Bedingung ausgelöst.

### Barriers (implemented 2026-04-07, ADR-018)

| MCS | Barrier | Implementation | Test |
|-----|---------|----------------|------|
| MCS-1 | Same-directory guard in `_check_co_change` | `PurePosixPath(pair.file_a).parent == PurePosixPath(pair.file_b).parent and parent != "."` → `continue` | `test_co_change_same_directory_suppressed` + `test_co_change_root_level_not_suppressed` (FN guard) |
| MCS-2 | `known` built from `filtered_prs` instead of `parse_results` | `known = {pr.file_path.as_posix() for pr in filtered_prs}` in `analyze()` | `test_co_change_test_source_pair_suppressed` |
| MCS-3 | Commit-size discount in `build_co_change_pairs` | `weight = 1.0 / max(1, len(files) - 1)`; pair_counts/file_commit_counts accumulate float weights | `test_co_change_bulk_commits_discounted` |

**Post-fix RPNs:** MCS-1: 144→24, MCS-2: 60→10, MCS-3: 120→30. MCS-4 unchanged (48, latent).

### Operationelle Tests (pro MCS)
- MCS-1: Fixture `signals/foo_signal.py` + `signals/bar_signal.py` mit `@register_signal`, Mock-History 6 Co-Changes, kein Import-Edge → `avs_co_change` darf kein Finding emittieren.
- MCS-2: Fixture `tests/test_cfg.py` + `src/cfg.py`, Mock-History 8 Co-Changes → kein `avs_co_change`-Finding.
- MCS-3: Mock-Commits mit 20 Dateien pro Commit, `file_a` und `file_b` immer gemeinsam → confidence nach Diskontierung < 0.2.
- MCS-4: `commands/cli.py` importiert `models/config.py` in einer CLI-Architektur → kein `avs_upward_import`, wenn `models` in Omnilayer-Whitelist.

---

## 2026-04-07 - DIA FTA v2: deep false-positive reduction (6 MCS, 16 basis events)

### FT-1: DIA Finding = False Positive (Top Event)
- Top event: DIA emits a finding for a directory reference that does not represent a real architecture problem.
- Gate: OR (any of IE-1 … IE-7 sufficient)

#### IE-1: Regex extracts non-directory slash token (Common Cause CC-1: `_PROSE_DIR_RE` flat iterator)
- BE-1: Language keyword compound `try/except`, `match/case` — regex matches `word/` without checking continuation.
- BE-2: Prose slash-as-separator `parent/tree` — slash used as concept separator, not path separator.
- BE-3: Multi-segment path decomposition `src/drift/output/csv_output.py` — each intermediate `word/` extracted as separate ref.
- BE-4: URL owner/repo in non-link text `mick-gsk/drift` — GitHub handle extracted as dir ref.
- **FIX (P5):** Negative lookahead `(?!\w)` on `_PROSE_DIR_RE` — blocks all four sub-causes.

#### IE-2: URL path segments escape blacklist
- BE-5: URL appears as plain text (not markdown link) — regex applied to URL path segments.
- BE-6: URL trailing slash `https://github.com/some-org/` → `some-org` extracted.
- **FIX (P3):** `_strip_urls()` removes URLs before regex application.

#### IE-3: Dotfile path stripping
- BE-7: `.drift-cache/history.json` → leading dot stripped → `drift-cache/` extracted → existence check fails (`.drift-cache` not checked).
- **FIX (P6):** `_ref_exists_in_repo()` also checks `repo_path / f".{ref}"`.

#### IE-4: Auxiliary directory not documented (Common Cause CC-2)
- BE-8: `tests/`, `scripts/`, `benchmarks/` etc. contain .py files → `_source_directories()` includes them → README doesn't mention them → undocumented-dir finding emitted.
- BE-8a (added 2026-04-08): `work_artifacts/`, `artifacts/` — CI/build artifact and working directories with ad-hoc .py scripts.
- **FIX (P1):** `_AUXILIARY_DIRS` frozenset skips conventional project directories. Extended 2026-04-08 with `artifacts`, `work_artifacts`.

#### IE-5: Codespan without context (addressed in FTA v1)
- BE-9: Inline codespan consumed with `allow_without_context=True` — REST path or example code.
- FIX (CS-1 from FTA v1): Sibling-context keyword gate.

#### IE-5a (added 2026-04-08): ADR illustrative example in codespan
- BE-9a: ADR *about* DIA uses illustrative path refs (e.g. `services/`) in inline codespans as examples. ADR scanning's `trust_codespans=True` extracts them as phantom refs.
- **FIX:** Move illustrative examples to fenced code blocks. DIA's AST walker already skips `block_code` tokens.

#### IE-6: Directory under different prefix (addressed in FTA v1)
- BE-10: `src/services/` exists but root-anchored check fails.
- FIX (CS-2 from FTA v1): Container-prefix existence check.

#### IE-7: ADR historically correct but stale (addressed in FTA v1)
- BE-11: ADR describes pre-refactoring state; paths no longer exist.
- FIX (CS-3 from FTA v1): ADR status parsing + skip.

### FT-2: Mitigation trade-off risk (FN potential)
- Top event: FP-reduction mitigations may suppress legitimate true positives.
- Branch A (P5): Negative lookahead `(?!\w)` only extracts terminal path segments — may miss structure refs in `src/drift/` style paths. Risk: low — terminal segment is always the meaningful claim.
- Branch B (P3): URL stripping may accidentally remove non-URL text matching `https?://\S+`. Risk: negligible — no legitimate dir ref starts with `http`.
- Branch C (P6): Dotfile prefix check may match coincidental `.{name}` dirs. Risk: very low — dotfile naming convention is intentional.
- Branch D (P1): Auxiliary dir exclusion may hide genuinely undocumented custom dirs. Risk: low — only well-known convention names excluded.
- Mutation benchmark verification: DIA recall 3/3 = 100% (no FN regression).

### Common Causes
| ID | Cause | Affected MCS | Fix |
|---|---|---|---|
| CC-1 | `_PROSE_DIR_RE` flat iterator (no continuation check) | MCS-1, MCS-2, MCS-4, MCS-5 | P5: `(?!\w)` negative lookahead |
| CC-2 | Missing undocumented-dir convention filter | MCS-1 | P1: `_AUXILIARY_DIRS` |
| CC-3 | ADR `trust_codespans=True` bypass | MCS-3, MCS-6 | Addressed in FTA v1 (CS-1 + CS-3) |

### Minimal Cut Sets
| MCS | Basis Events | Probability | Fix | FP Reduction |
|---|---|---|---|---|
| MCS-1 | BE-8 (auxiliary dirs) | High | P1: `_AUXILIARY_DIRS` | −4 (ground truth) |
| MCS-2 | BE-4 + BE-5 (URL in plain text) | Medium | P3: `_strip_urls()` + P5 | −2 |
| MCS-3 | BE-1 (keyword compounds via codespan) | Medium | P5: `(?!\w)` | −2 |
| MCS-4 | BE-2 (prose slash-separator) | Medium | P5: `(?!\w)` | −1 |
| MCS-5 | BE-7 (dotfile path) | Low | P5 + P6 | −1 |
| MCS-6 | BE-3 (multi-segment decomposition) | Medium | P5: `(?!\w)` | −1 |

## 2026-04-07 - DIA FTA v1: initial false-positive reduction (3 cut sets)

### FT-1: DIA Finding = False Positive (Top Event)
- Top event: DIA emits a finding for a directory reference that does not represent a real architecture problem.
- Gate: OR (any of IE-1, IE-2, IE-3 sufficient)

#### IE-1: Reference is not a directory (never was)
- Branch BE-1: URL path segment escapes `_URL_PATH_SEGMENTS` blacklist (enumerative, not structural).
- Branch BE-2: Inline `codespan` token extracted with `allow_without_context=True` — REST path or example code like `` `auth/callback` `` passes without structure-keyword context.
- Branch BE-3: Foreign-repo example in README (e.g. `django/core`) passes `_is_likely_proper_noun()` because it's lowercase.
- Branch BE-4: Prose word with slash (e.g. "services/as concept") extracted from codespan without nearby keyword.

#### IE-2: Directory exists but under different path
- Branch BE-5: `src/services/` exists but `_source_directories()` only records `src` as top-level; `services/` not in `source_dirs`.
- Branch BE-6: `app/controllers/` exists but root-anchored check fails for `controllers/`.

#### IE-3: ADR reference is historically correct but stale
- Branch BE-7: ADR describes pre-refactoring state as context; paths no longer exist.
- Branch BE-8: ADR describes target architecture (not yet built); paths don't exist yet.

### FT-2: Mitigation trade-off risk (FN potential)
- Top event: FP-reduction mitigations may suppress legitimate true positives.
- Branch A: Codespan context gate suppresses dir refs in paragraphs without structure keywords (e.g. "use `services/` for the API logic") — risk: low, such sentences rarely constitute structure claims.
- Branch B: Container-prefix existence check masks phantom dirs that coincidentally exist under `src/` — risk: low, existence under common prefixes is strong non-staleness evidence.
- Branch C: ADR status skip (`superseded`/`deprecated`/`rejected`) hides phantom dirs still referenced in obsolete ADRs — risk: acceptable, superseded ADRs are not authoritative.
- Mitigation implemented: Conservative defaults (only curated container prefixes, only 3 skip statuses), "architecture"/"component" added to context keywords, `trust_codespans=True` for ADR files.

### Cut Sets
| Cut Set | Base Events | Probability | Fix |
|---|---|---|---|
| CS-1 | BE-2 (codespan + allow_without_context) | High | Sibling-context keyword gate |
| CS-2 | BE-5 + BE-6 (path normalization) | Medium | Container-prefix existence check |
| CS-3 | BE-7 or BE-8 (ADR status ignored) | Medium | ADR status parsing + skip |

## 2026-04-07 - MAZ/ISD/HSC wave-2 calibration

### FT-1: Security findings lose credibility through wrapper and directive edge-cases
- Top event: Security signal output is incomplete or overly noisy in realistic endpoint/config patterns.
- Branch A: MAZ fallback misses auth-context parameters that are camelCase or composed names.
- Branch B: ISD file-level ignore is triggered by similar but unintended marker strings.
- Branch C: HSC misses known token prefixes when literals are wrapped as auth headers.
- Mitigation implemented: MAZ parameter normalization + conservative auth regexes, strict ISD ignore directive parsing, and HSC wrapper normalization before prefix checks.

### FT-2: Precision/recall trade-off after wave-2 hardening
- Top event: Mitigations may under- or over-suppress findings in edge naming styles.
- Branch A: MAZ auth-like regex may suppress rare non-auth business parameters.
- Branch B: ISD stricter directive can surface findings where teams previously relied on loose comments.
- Branch C: HSC wrapper normalization can increase sensitivity on synthetic token-like literals.
- Mitigation implemented: Added targeted TP/TN regressions and kept conservative matcher scope with existing safe-value checks.

## 2026-04-06 - MAZ/ISD/HSC scoring-readiness calibration

### FT-1: Security readiness blocked by recall/precision imbalance
- Top event: Security signals are not credible enough for scoring-promotion decisions.
- Branch A: MAZ fallback reports unauthenticated endpoints although auth context is injected via parameters.
- Branch B: ISD treats localhost `verify=False` with full severity, reducing local-dev signal actionability.
- Branch C: HSC misses high-confidence prefixed token literals when variable names are generic.
- Mitigation implemented: Fallback auth-like parameter suppression (MAZ), loopback severity downgrade with explicit rule (ISD), and prefix-first literal detection independent of variable names (HSC).

### FT-2: Trade-off risk after precision-first calibration
- Top event: Calibrations introduce selective under- or over-reporting in edge contexts.
- Branch A: MAZ auth-like parameter suppression can hide rare real auth gaps with misleading names.
- Branch B: ISD loopback downgrade can under-prioritize misuse if host classification is overly permissive.
- Branch C: HSC prefix-first logic can increase sensitivity on synthetic or template-like token strings.
- Mitigation implemented: Conservative marker sets, strict loopback host checks, and expanded TP/TN regression coverage in per-signal tests and precision/recall fixtures.

## 2026-04-06 - MDS precision-first scoring-readiness calibration

### FT-1: MDS scoring noise from semantic and intentional-variant matches
- Top event: MDS contributes low-actionability findings that distort scoring trust.
- Branch A: Semantic-only matching reports same-file conceptual similarity that is not duplicate drift.
- Branch B: Sync/async API variants with same function names are interpreted as copy-paste drift.
- Branch C: Hybrid threshold below AST threshold admitted borderline pairs.
- Mitigation implemented: Raise semantic gate strictness, suppress same-file semantic pairs,
	suppress sync/async variant pairs, and enforce precision-first hybrid threshold.

### FT-2: Recall trade-off after precision-focused suppression
- Top event: Some real duplicates in sync/async ecosystems are not emitted by MDS.
- Branch A: File-path token heuristic classifies pair as intentional variant.
- Branch B: Duplicate is real but follows sync/async naming conventions.
- Mitigation implemented: Keep suppression conservative (same bare function name + sync/async path markers)
	and retain control regression for non-variant exact duplicate detection.

## 2026-04-06 - TPD unexpected source-segment exception hardening (Issue #184)

### FT-1: TPD signal skip due to unexpected source-segment exception
- Top event: TPD is skipped during context export because exception escapes assert polarity classification.
- Branch A: Repository contains assert/source combinations that trigger an internal exception in source-segment extraction.
- Branch B: Exception type is outside previously handled cases.
- Branch C: Exception propagates to signal execution boundary, causing skip.
- Mitigation implemented: Broaden source-segment guard to treat any extraction exception as missing segment and continue.

### FT-2: Partial under-reporting risk on malformed per-file AST paths
- Top event: A malformed file reduces local TPD coverage.
- Branch A: `ast.parse` or AST visitor path fails unexpectedly for one file.
- Branch B: Signal-level execution would otherwise abort.
- Mitigation implemented: Per-file parse/visit guards skip only the failing file and preserve analysis continuity for remaining files.

## 2026-04-06 - HSC YAML env-template variable-name false positives (Issue #181)

### FT-1: False positives on YAML templates that reference environment placeholders
- Top event: HSC emits hardcoded-secret findings for configuration template constants.
- Branch A: Variable-name heuristic matches secret-like symbols (`*_API_KEY`, `*_TOKEN`).
- Branch B: Assigned value is a multi-line configuration template with `${ENV_VAR}` placeholders.
- Branch C: Generic fallback treats non-trivial string literals as suspicious despite env indirection.
- Mitigation implemented: Add narrow suppression for configuration-style multi-line literals that contain `${...}` placeholders.

### FT-2: Under-reporting risk after template suppression
- Top event: Real secret in a template-like literal is not emitted.
- Branch A: New template suppression path is active.
- Branch B: Literal combines template placeholders and accidental credential value.
- Mitigation implemented: Keep high-confidence known-prefix detection before suppression and constrain suppression to multi-line key/value templates with `${...}` markers.

## 2026-04-06 - TPD ast.get_source_segment crash guard (Issue #180)

### FT-1: TPD runtime abort on malformed AST source-position metadata
- Top event: TPD stops analysis due to uncaught exception while classifying assert polarity.
- Branch A: A parsed `ast.Assert` node carries out-of-range line metadata.
- Branch B: `ast.get_source_segment(source, node)` raises `IndexError` or `ValueError`.
- Branch C: Exception propagates out of `_AssertionCounter.visit_Assert` and aborts TPD scan path.
- Mitigation implemented: Guard source-segment extraction with exception handling and continue with AST-only polarity fallback.

### FT-2: Under-classification risk after crash hardening
- Top event: Some malformed-node asserts are classified without regex-text fallback.
- Branch A: Source-segment extraction fails and returns no segment.
- Branch B: Negative regex fallback cannot be evaluated for that node.
- Mitigation implemented: Keep conservative AST-based negative polarity detection active and limit fallback skip to malformed metadata cases only.

## 2026-04-06 - MDS numbered sample-step duplicate calibration (Issue #179)

### FT-1: False positives on numbered tutorial/sample progression directories
- Top event: MDS emits exact-duplicate findings for intentionally repeated helpers in numbered sample directories.
- Branch A: Repository uses pedagogical sample progression paths (for example `samples/.../01_single_agent`, `02_multi_agent`).
- Branch B: Path contains tutorial/sample marker but no `step*` token, so previous suppression does not trigger.
- Branch C: Exact body-hash grouping escalates duplicates to high severity.
- Mitigation implemented: Extend tutorial-step suppression to include conservative numbered sample-step directory pattern.

### FT-2: Under-reporting risk after numbered-step suppression
- Top event: True architectural duplication in numbered sample step paths is not emitted by MDS.
- Branch A: Suppression triggers for tutorial/sample/example context combined with numbered-step folder shape.
- Branch B: Project uses numbered directories in production path conventions.
- Mitigation implemented: Keep suppression strictly context-gated (tutorial/sample/example marker required) and preserve detection in non-step sample paths.

## 2026-04-06 - MDS tutorial-step sample duplicate calibration (Issue #177)

### FT-1: False positives on intentional tutorial step duplicates
- Top event: MDS emits exact-duplicate findings for pedagogical step directories where code is intentionally repeated.
- Branch A: Repository contains tutorial/sample/example paths with step-specific standalone modules.
- Branch B: Helper implementation is intentionally copied across `step*` directories to keep each step runnable.
- Branch C: Hash-based exact duplicate grouping escalates these to high-severity findings.
- Mitigation implemented: Exclude functions in conservative tutorial-step sample path context from MDS candidate collection.

### FT-2: Under-reporting risk after tutorial-step suppression
- Top event: True architectural duplication in tutorial-step paths is not emitted by MDS.
- Branch A: Suppression triggers for `tutorial/sample/example` + `step*` path context.
- Branch B: Repository uses step-style directory names for production code.
- Mitigation implemented: Keep suppression narrowly scoped to explicit tutorial/sample/example contexts and preserve detection for non-step duplicates.

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

## 2026-04-07 - PFS FTA v1: recall deficit (Mutation Benchmark Recall = 0.5, 2 strukturell unabhängige Failure Paths)

### Top Event (TE-0)
`PatternFragmentationSignal.analyze()` liefert kein Finding für Mutation `pfs_002` ("return_pattern: 3 Varianten in `models/user.py`"), obwohl `must_detect=true` gilt und drei strukturell verschiedene Rückgabestrategien (`return None`, `raise ValueError`, `return (value, None)`) in derselben Datei injiziert sind — Systemgrenze: `PatternFragmentationSignal.analyze()` von Eingabe `parse_results`/`file_histories` bis Rückgabewert `findings`; Auslöser: `scripts/_mutation_benchmark.py`; beobachtbar als `detected=0, recall=0.0` für `pfs_002`, Gesamt-PFS-Recall = 0.5.
Evidenz: `"pattern_fragmentation": {"injected": 2, "detected": 1, "recall": 0.5}` in `benchmark_results/mutation_benchmark.json`.

---

### FT-1: TE-0 ← kausale Kette (alle Teilbedingungen gleichzeitig wahr)

Das Top Event tritt ein, weil `all_patterns` im Signal für die Kategorie `return_pattern` leer ist. Es gibt eine einzige kausale Kette, die das vollständig erklärt.

#### IE-1: `parse_result.patterns` enthält keine PatternInstances für `models/user.py` [SPOF]

`_ASTVisitor._process_function()` (ast_parser.py:425–455) erzeugt `PatternInstance`-Objekte ausschließlich für `ast.Try`-Blöcke (`ERROR_HANDLING`) und API-Endpoint-Dekoratoren (`API_ENDPOINT`). `models/user.py` enthält weder `Try`-Blöcke noch Endpoint-Dekoratoren — daher gilt `pr.patterns = []` nach dem Parse-Durchlauf.

**IE-1 tritt ein durch AND-Gate (beide Teilbedingungen müssen gleichzeitig fehlen):**

**Ast A: Fehlender Code-Pfad für Return-Strategie-Extraktion [Technical — direkte Ursache]**
- BE-A1-T: `_process_function()` prüft in der Schleife `for child in self._walk_excluding_nested(node)` ausschließlich `isinstance(child, ast.Try)`. Kein Ast für `ast.Return`-Varianten, Early-Return-Guards (`ast.If` mit `return`-Body) oder Result-Type-Signaling. `models/user.py`-Funktionen verwenden ausschließlich verschiedene `ast.Return`-Formen ohne Try-Block.
- BE-A1-P: Benchmark-Mutation `pfs_002` beschreibt `"return_pattern"` als Kategoriename ohne vorherige Prüfung, ob der Parser diese Kategorie jemals extrahiert — kein Alignment-Gate zwischen Mutations-Rationale und `PatternCategory`-Enum in der Benchmark-Erstellung.
- BE-A1-H: Signal-Spec beschreibt PFS als "multiple incompatible variants of any coding pattern"; der Parser-Scope wurde bei der Implementierung implizit auf try/except + API-Endpoints begrenzt; kein negativer Akzeptanztest existiert, der prüft "emittiert PFS ein Finding für Return-Strategie-Variationen?" — die Scope-Diskrepanz blieb unerkannt.

**Ast B: `PatternCategory` Enum enthält keinen `RETURN_PATTERN`-Wert [Technical — strukturelle Vorbedingung]**
- BE-B1-T: `models.py:52–61` definiert exakt 8 Kategorien (`ERROR_HANDLING`, `DATA_ACCESS`, `API_ENDPOINT`, `CACHING`, `LOGGING`, `TESTING`, `AUTHENTICATION`, `VALIDATION`). `RETURN_PATTERN` fehlt vollständig; ein Extraktionsversuch ohne diesen Enum-Wert würde `ValueError` auslösen.
- BE-B1-P: Die Benchmark-Fixture-Entwicklung enthält keine Überprüfung gegen `PatternCategory`-Member; `pfs_002` wurde geschrieben ohne Enum-Membership zu validieren.
- BE-B1-H: Enum-Wert und Parser-Code wurden parallel mit dem Signal entwickelt; ein Scope-Review des Parsers bei neuen PFS-Testfall-Erstellungen war kein definierter Prozessschritt.

**Common Cause CC-1 (Ast A + Ast B):** Beide Basis-Ereignisse teilen dieselbe Upstream-Design-Entscheidung: Return-Strategie-Variationen wurden beim Entwurf des Extraktions-Subsystems nicht als erkennbare Pattern-Klasse vorgesehen. Ast A (fehlender Code-Pfad) und Ast B (fehlender Enum-Wert) sind zwei Manifestationen derselben konzeptionellen Lücke — weder in `models.py` noch in `ast_parser.py` ist die Abstraktion verankert.

#### IE-2: PFS iteriert über `all_patterns.items()` — RETURN_PATTERN-Key existiert nie [Konsequenz aus IE-1]

Weil kein `PatternInstance` mit `category=PatternCategory.RETURN_PATTERN` erzeugt wird, enthält `all_patterns` diesen Key nie. Der Signal-Code iteriert ausschließlich über vorhandene Keys (`category, patterns in all_patterns.items()`) und erreicht die Fragmentation-Logik für Varianten aus `models/user.py` strukturell nie. Dies ist eine direkte Konsequenz aus IE-1, kein unabhängiger Fehlerast.

---

### FT-2: Variant-Undercount in pfs_001 — Partielle Charakterisierungslücke (nicht TE-0, aber latentes Qualitätsrisiko)

**Top Event FT-2:** `PatternFragmentationSignal.analyze()` berichtet "2 Varianten" für `handlers/` statt der 4 injizierten Fehlerbehandlungsansätze (`try/except`, Custom Exception, result-dict, assert). Ursache: `_process_function()` extrahiert ausschließlich `ast.Try`-basierte Patterns.

**Evidenz:** Finding-Titel `"error_handling: 2 variants in src/myapp/handlers/"` — `auth.py` (try/except ValueError/Exception) und `orders.py` (try/except KeyError|TypeError) sind die einzigen Try-Block-Träger und erzeugen zwei distinguierbare Fingerprints. `payments.py` (result-dict) und `notifications.py` (assert) erzeugen keine PatternInstances.

**FT-2 Gate: OR (jede Extraktionslücke allein reicht, den jeweiligen Varianten-Ast zu unterdrücken)**

#### IE-2a: `payments.py` (result-dict error handling) → kein PatternInstance [Technical]
- BE-2a-T: Guard-Condition-basierte Fehlerbehandlung verwendet `ast.If` + `ast.Return` mit `result["error"] = "..."` — kein `ast.Try`-Node vorhanden → kein `PatternInstance(ERROR_HANDLING, ...)` erzeugt. Die Fehlerbehandlungssemantik (error-return via result-object) ist strukturell nicht von normaler Kontrollfluss-Logik unterscheidbar ohne domänenspezifische Heuristik.
- BE-2a-P: Benchmark definiert result-dict als "error_handling"-Variante; der Parser definiert `ERROR_HANDLING` operativ als "enthält einen `ast.Try`-Block" — Definitionskonflikt ist in keiner Dokumentation explizit ausgewiesen.
- BE-2a-H: Kein Alignment-Test existiert, der `payments.py`-Stil gegen PFS laufen lässt und explizit prüft "wird diese Variante als PatternInstance extrahiert?"

#### IE-2b: `notifications.py` (assert-based error handling) → kein PatternInstance [Technical]
- BE-2b-T: `ast.Assert`-Statements werden in `_process_function()` nicht betrachtet; assert als Fehlerbehandlungsstrategie (precondition enforcement) ist für den Parser vollständig unsichtbar.
- BE-2b-P: Gleicher Definitionskonflikt wie IE-2a.
- BE-2b-H: Kein negativer Akzeptanztest für "assert-only handler erzeugt PatternInstance" — Annahme war implizit falsch.

**FT-2 Mitigation-Risiko (FN nach möglichem Fix):**
- Guard-Return (`ast.If` + early `return`) als ERROR_HANDLING-Variante: Utility-Funktionen mit mehreren Rückgabepfaden würden als fragmentiert gelten können. Risiko: mittel — erfordert Threshold-Kalibrierung und semantischen Guard (nur wenn Rückgabewert Error-Indikator trägt).
- `ast.Assert` als ERROR_HANDLING-Variante: Test-Bodies (`is_test_file()` filtert bereits) sind kein Risiko; nicht-defensive Asserts in Produktionscode könnten fälschlich klassifiziert werden. Risiko: gering mit konservativem Scope.

---

### Common Causes

| ID | Ursache | Betroffene Ereignisse |
|----|---------|----------------------|
| CC-1 | Return-Strategie-Variationen wurden nie als Parser-Zielklasse definiert — gleiche Design-Entscheidung löst Ast A (fehlender Code-Pfad) und Ast B (fehlender Enum-Wert) aus | IE-1 Ast A, IE-1 Ast B |
| CC-2 | Pattern-Extraktion ist auf `ast.Try` beschränkt — alle nicht-try Fehlerbehandlungsparadigmen (Guard-Return, Assert, Result-Type) sind für `PatternCategory.ERROR_HANDLING` unsichtbar | IE-2a, IE-2b, IE-1 Ast A (mittelbar) |
| CC-3 | Kein Alignment-Gate zwischen Mutation-Fixture-Design und `PatternCategory`-Enum während Benchmark-Erstellung | BE-B1-P (IE-1 Ast B), BE-2a-P (IE-2a), BE-2b-P (IE-2b) |

---

### Minimal Cut Sets

| MCS | Basis-Ereignisse | SPOF | Evidenz | Recall-Impact |
|-----|-----------------|------|---------|---------------|
| MCS-1 | BE-A1-T: `_process_function()` enthält keinen Return-Strategie-Extraktionspfad | **Ja** | `pfs_002` detected=0; `models/user.py` → pr.patterns=[] | −1 Finding (Recall 0.5 → 1.0) |
| MCS-2 | BE-2a-T: Guard-Return (`ast.If`/result-dict) nicht als ERROR_HANDLING registriert | Ja (Variantencount pfs_001) | Finding "2 variants" statt "4 variants" in handlers/ | −1 Variante (Severity-Unterabschätzung) |
| MCS-3 | BE-2b-T: `ast.Assert` nicht als ERROR_HANDLING registriert | Ja (Variantencount pfs_001) | Gleiche Evidenz wie MCS-2 | −1 Variante (kombiniert mit MCS-2) |
| MCS-4 (Prozess/latent) | BE-B1-P (CC-3): Kein Enum-Alignment-Gate in Fixture-Entwicklung | Nein (prozessual) | Keine technische Blockade, aber zukünftige blinde Mutationen wahrscheinlich | Präventiv |

**SPOF-Diagnose:** MCS-1 ist ein Single-Point-of-Failure für TE-0 (pfs_002 vollständig verpasst) — eine einzige fehlende Feature-Implementierung im Parser ist hinreichend. MCS-2 und MCS-3 gemeinsam reduzieren die Charakterisierungsqualität von pfs_001 (nur 2 statt 4 Varianten), verhindern aber die Detektion nicht.

---

### Operationelle Tests (pro MCS)

- **MCS-1:** `models/user.py` mit drei Funktionen und verschiedenen Return-Strategien (None, raise, tuple) → nach Implementierung eines Return-Strategy-Extractors: `pr.patterns` muss ≥ 3 PatternInstances unter einer Return-Kategorie enthalten; PFS muss Finding emittieren. Negativtest (aktueller Stand): `pr.patterns == []` ist dokumentiertes Verhalten, nicht Silent Failure des Signals selbst.
- **MCS-2:** `handlers/payments.py` mit Guard-Return/result-dict → nach Implementierung: `PatternInstance(ERROR_HANDLING, ...)` muss vorhanden sein. Testbarkeitsnachweis: Fixture mit `if cond: return {"error": ...}` als einzige Fehlerbehandlung.
- **MCS-3:** `handlers/notifications.py` mit assert-Statements → nach Implementierung: `PatternInstance(ERROR_HANDLING, ...)` unter assert-Fingerprint. Testbarkeitsnachweis: Fixture mit `assert cond, "msg"` als Fehler-Guard.
- **MCS-4 (Prozess):** Neues Skript oder assert in `_mutation_benchmark.py`, das beim Erstellen einer Mutation prüft: `"signal_category" in [m.value for m in PatternCategory]` — verhindert blinde Fixturing für nicht-extrahierbare Kategorien.

---

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

---

## PHR — Phantom Reference (ADR-033)

### FT-1: False Positive — name flagged as phantom but actually available
- Top event: PHR emits finding for a name that IS available at runtime.
- Branch A: Name provided by star import (`from X import *`).
  - Mitigation: Conservative skip — files with star imports excluded entirely.
- Branch B: Name provided by module-level `__getattr__`.
  - Mitigation: Conservative skip — files with `__getattr__` at module level excluded.
- Branch C: Name is a third-party library name not in project symbol table.
  - Mitigation: Import-resolved names added to available set; root-name resolution covers `import X; X.call()`.
- Branch D: Name is a framework-injected global (e.g. pytest fixtures).
  - Mitigation: `_FRAMEWORK_GLOBALS` allowlist for common framework names.
- Branch E: Name introduced by `exec()`/`eval()` at runtime.
  - Mitigation: `_has_exec_eval` flag detected (logged); accept as static analysis limitation.

### FT-2: False Negative — phantom name not detected
- Top event: PHR misses a genuinely unresolvable reference.
- Branch A: Name retrieved via `getattr(obj, "name")` — dynamic access invisible to AST.
  - Accept: static analysis cannot resolve runtime string-based attribute access.
- Branch B: Name used in decorator context but not in call expression.
  - Accept: current heuristic focuses on call targets; decorator names tracked via _ScopeCollector.
- Branch C: Name used only in type annotations (not at runtime).
  - Mitigation: TYPE_CHECKING blocks skipped; annotation-only names not collected.

## 2026-04-10 - Scoring Promotion: HSC, FOE, PHR (ADR-040)

### FT-1: HSC Finding = False Positive (Top Event)
- Top event: HSC emits a hardcoded-secret finding for a value that is not actually a secret.
- Gate: OR (any of IE-1, IE-2, IE-3 sufficient)

#### IE-1: Value is a placeholder or example
- Branch BE-1: Variable name matches secret pattern but value is a known placeholder (`changeme`, `xxx-*`, `PLACEHOLDER`, `<YOUR_*_HERE>`).
  - Mitigation: Placeholder allowlist in HSC heuristics.
- Branch BE-2: Value is a documentation example or test fixture string.
  - Mitigation: Low-entropy threshold (3.5 bits) filters short/simple strings.

#### IE-2: Secret is externalized but variable name triggers detection
- Branch BE-3: RHS is `os.environ["KEY"]` or `os.getenv("KEY")` call.
  - Mitigation: AST check recognizes os.environ/os.getenv as safe sourcing.
- Branch BE-4: Value loaded from config file or environment variable via framework.
  - Mitigation: Partial — only stdlib os.environ recognized; framework-specific patterns accepted as residual risk.

#### IE-3: ML/data constants with high entropy
- Branch BE-5: Hex tokenizer vocabulary or model hash strings.
  - Mitigation: Context-aware skip for known ML file patterns.

### FT-2: FOE Finding = False Positive (Top Event)
- Top event: FOE emits a fan-out finding for a file that legitimately needs many imports.
- Gate: OR (any of IE-1, IE-2 sufficient)

#### IE-1: File is a barrel/re-export module
- Branch BE-1: `__init__.py` re-exports names from submodules.
  - Mitigation: `__init__.py` excluded from FOE detection.

#### IE-2: File is a test module
- Branch BE-2: Test files import many fixtures/helpers/mocks.
  - Mitigation: `is_test_file()` guard excludes test files.

### FT-3: Scoring-promotion risk — FP affects composite score
- Top event: Previously report-only FP now inflates composite drift score.
- Branch A: HSC false positive (weight 0.02) adds ≤0.02 to module score.
  - Mitigation: Low weight limits impact; existing FP guards active.
- Branch B: FOE false positive (weight 0.01) adds ≤0.01 to module score.
  - Mitigation: Low weight + `__init__.py` exclusion + test-file guard.
- Branch C: PHR false positive (weight 0.02) adds ≤0.02 to module score.
  - Mitigation: Existing PHR FP mitigations (star-import skip, __getattr__ skip, framework allowlist).

## 2026-04-12 - Type-safety hardening for TVS/SMS/COD

### FT-1: CI/type-gate failure in signal preprocessing paths
- Top event: Typecheck fails on optional datetime normalization and helper return contracts.
- Branch A: `first_seen` can be `None`, yet `astimezone()` is invoked through loose attribute probing.
- Branch B: `last_modified` can be `None`, yet timezone conversion is attempted without strict narrowing.
- Branch C: Helper function with `-> str` returns a value inferred as `Any` from regex capture list.
- Mitigation implemented: Replace dynamic attribute checks with `isinstance(datetime.datetime)` guards and cast regex token output to `str` before normalization.

### FT-2: Residual FN/FP impact after hardening
- Top event: Behavioral drift in findings due to defensive typing changes.
- Branch A: Overly strict type guard could skip valid datetime normalization.
- Branch B: String-cast could alter prefix extraction semantics.
- Branch C: Helper signature change without compatibility default causes invocation failures.
- Branch D: TS signature dampening suppresses valid no-test findings.
- Mitigation implemented: Logic remains semantically equivalent (only type narrowing and coercion); verified by local `ruff` and `mypy` green runs.

### FT-3: Regression control for newly observed CI failures
- Top event: Post-fix CI remains red due newly surfaced regression tests.
- Branch A: `_resolve_relative_targets()` callsites/tests still use legacy 2-arg invocation.
- Branch B: EDS TS dampening reduces score below detection threshold despite explicit missing tests.
- Mitigation implemented: Backward-compatible optional parameter in CCC helper and conditional dampening in EDS based on test evidence state.
