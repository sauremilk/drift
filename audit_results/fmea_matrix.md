# FMEA Matrix

## 2026-04-12 - Issue #261: TVS burst dampening for mature extension workspaces

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| TVS | FP: coordinated churn in established `extensions/*`/`plugins/*` workspaces is still escalated as HIGH, while `workspace_burst_dampened` rarely activates | Coordinated-burst detection required a strict active-ratio condition and ignored workspace-level recency/mixed-age patterns common in mature monorepos | High-priority noise in extension-heavy repos, reduced trust in TVS fix-first ordering | New regression in `tests/test_coverage_pipeline_and_helpers.py` (`test_mature_workspace_coordinated_burst_is_dampened`) | Extend TVS workspace burst profile with bounded mature-workspace branch: require minimum active files plus recent-modified ratio and established-history guard; keep score cap (`<= 0.45`) and metadata (`workspace_burst_dampened`) | 7 | 8 | 2 | 112 | Mitigated |
| TVS | FN-risk: real instability inside mature plugin workspaces may be down-ranked | Expanded burst classification dampens more established extension workspaces during coordinated activity | Potential delayed prioritization of genuine hotspot files within active plugin packages | Existing non-plugin guard remains active (`test_non_plugin_outlier_keeps_high_severity`) | Keep dampening scope bounded to runtime plugin workspaces and require multiple simultaneous signals (size, active-count, active-ratio, recent-ratio, established-count); findings remain visible | 4 | 3 | 4 | 48 | Mitigated |

## 2026-04-12 - Issue #260: DCA false positives for plugin/extension workspace exports

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| DCA | FP: JS/TS exports in plugin/extension workspaces are reported as dead code with medium/high urgency although consumed by host runtime loading | DCA relied on static import references and only dampened narrow config/entrypoint filename subsets, missing broader workspace export surfaces (`extensions/*`, `plugins/*`, nested `.pi/extensions/*`) | Large false-positive clusters in plugin monorepos, inflated drift severity, reduced DCA trust/actionability | New regressions in `tests/test_dead_code_accumulation.py` (`test_extensions_non_config_file_is_dampened_to_low`, `test_nested_dotpi_extensions_file_is_dampened_to_low`) | Add bounded runtime plugin workspace heuristic for JS/TS source files under extension/plugin scopes; cap to LOW (`score <= 0.39`) and expose metadata (`runtime_plugin_workspace_heuristic_applied`) | 7 | 8 | 2 | 112 | Mitigated |
| DCA | FN-risk: genuine dead exports inside plugin workspaces are down-ranked too aggressively | New workspace heuristic applies context dampening to broader plugin-source paths | Potential delayed cleanup of real dead exports in plugin packages | Guard regression `test_non_plugin_file_keeps_high_without_workspace_heuristic` keeps non-plugin severity behavior unchanged | Keep findings visible (no suppression), bound heuristic to JS/TS files in extension/plugin workspace paths only, and retain stronger scoring outside that scope | 4 | 3 | 4 | 48 | Mitigated |

## 2026-04-12 - Issue #259: CXS false positives for config-default files

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| CXS | FP: TypeScript/JavaScript config-default resolver modules are reported with medium/high urgency although multi-branch fallback logic is expected in these files | CXS context dampening only recognized schema/migration patterns and did not include config-default filename conventions | Triage noise and urgency inflation in plugin/config-heavy repos; reduced trust in CXS prioritization | New regressions in `tests/test_cognitive_complexity.py` (`test_inherent_ts_complexity_context_matches_schema_and_migration_paths`, `test_cxs_dampens_schema_migration_and_config_defaults_context_to_info`) | Extend `_is_inherent_ts_complexity_context` with bounded config-default filename markers (`config-defaults`, `config.defaults`, `default-config`) and keep context findings capped to `INFO` (`score <= 0.19`) via `context_dampened` metadata | 7 | 8 | 2 | 112 | Mitigated |
| CXS | FN-risk: genuine complexity debt in config-default files may be down-ranked after context cap | Config-default context cap applies severity/score dampening for a broader set of TS/JS config files | Potential delayed remediation for truly problematic config-default control flow | Negative-path guard regression remains active (`test_inherent_ts_complexity_context_ignores_regular_files`) and findings are still emitted | Scope stays narrow to explicit config-default naming conventions; no finding suppression, only severity cap | 4 | 3 | 4 | 48 | Mitigated |

## 2026-04-12 - Issue #258: EDS TypeScript internal/UI high-severity cap

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| EDS | FP: grosse interne TS/TSX UI-Wiring-Funktionen ohne JSDoc werden als `HIGH` priorisiert | High-Eskalation in EDS basierte nur auf Defizitscore und Komplexitaet; TS-Kontext (internal + UI wiring) wurde in der finalen Severity-Stufe nicht gecappt | Severity-Inflation in UI-/DOM-lastigen TS-Repos, sinkende Glaubwuerdigkeit, erhoehte Triage-Last | Neue Regressionen in `tests/test_coverage_boost_15_signals_misc.py` (`test_exd_typescript_internal_ui_function_caps_high_to_medium`, `test_exd_typescript_exported_function_can_still_be_high`) | TS/TSX-High-Cap in EDS: bei internen (`is_exported=False`) oder UI-Implementierungs-Kontexten wird `HIGH` auf `MEDIUM` begrenzt (`score <= 0.69`) und ueber Metadata (`ts_ui_high_cap_applied`) nachvollziehbar markiert | 7 | 8 | 2 | 112 | Mitigated |
| EDS | FN-Risiko: echte kritische TS-Komplexitaetsdefizite werden durch den Cap unterpriorisiert | Neuer Cap greift auf nicht-exportierte/internal-UI-Heuristik und kann einzelne reale Hochrisiko-Faelle daempfen | Potenziell spaetere Priorisierung einzelner echter Refactoring-Bedarfe | Exported-Guard-Regression bleibt aktiv (`test_exd_typescript_exported_function_can_still_be_high`) | Cap ist auf TS/TSX begrenzt und verlangt Weak-Evidence-Kontext (kein Docstring, keine self-documenting signature); exported APIs bleiben voll eskalierbar | 4 | 3 | 4 | 48 | Mitigated |

## 2026-04-12 - Issue #256: EDS TypeScript test coverage mapping hardening

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| EDS | FP: TS/JS Funktionen werden als unzureichend erklaert priorisiert, obwohl passende Tests existieren (`foo.ts` neben `foo.test.ts`/`foo.spec.ts` oder `__tests__/`) | EDS leitete `has_test` primär aus geparsten Testfunktionen ab; durch Discovery-Excludes fuer `**/tests/**` fehlte diese Evidenz oft systematisch | Severity-Inflation bei TS/JS-Repos, sinkende Signal-Glaubwuerdigkeit und hohe Triage-Last | Neue Regressionen in `tests/test_coverage_boost_15_signals_misc.py` (`test_exd_typescript_colocated_test_file_counts_as_test`, `test_exd_typescript_dunder_tests_mapping_counts_as_test`) | Dateibasierte TS/JS-Testzuordnung in EDS: Mapping `source -> {*.test.*, *.spec.*, __tests__/*}` inkl. `src/... -> tests/...`-Variante; bestehende Funktionsziel-Heuristik bleibt erhalten | 7 | 8 | 2 | 112 | Mitigated |
| EDS | FP: Unbekannter Teststatus wird als „kein Test“ behandelt und erhoeht Defizitscore | Bisheriges Scoring benutzte festen Evidenz-Nenner inkl. Testanteil, auch wenn Teststatus nicht verifizierbar war | Unnoetige Priorisierung in Kontexten ohne verlaessliche Test-Detektion | Neue Regression `test_exd_typescript_unknown_test_status_is_neutral_without_repo_path` | Tri-State `has_test` (`True/False/None`) und neutrales Scoring bei `None` (Testanteil aus Nenner entfernt); Beschreibung/Metadata kennzeichnen Unknown-Zustand explizit | 6 | 6 | 2 | 72 | Mitigated |

## 2026-04-12 - Issue #255: CXS false positives for schema and migration files

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| CXS | FP: TypeScript/JavaScript schema validation and migration files are reported with medium/high urgency although high branching is expected in these contexts | CXS scored control-flow depth uniformly and did not model file-context intent for `.schema.*` and migration patterns | Triage noise (16+ findings in reported case), inflated score contribution, reduced trust in CXS for data-shape infrastructure code | New regressions in `tests/test_cognitive_complexity.py` (`test_inherent_ts_complexity_context_matches_schema_and_migration_paths`, `test_cxs_dampens_schema_and_migration_context_to_info`) | Add bounded TS/JS file-context heuristic (`_is_inherent_ts_complexity_context`) and cap context findings to `INFO` (`score <= 0.19`) with explicit metadata (`context_dampened`) | 7 | 8 | 2 | 112 | Mitigated |
| CXS | FN-risk: real complexity debt in migration/schema files may be under-prioritized after context cap | Severity cap for contextual files can down-rank genuine maintainability hotspots in those files | Potential delayed refactoring for truly problematic migration/schema control flow | Existing CXS behavior outside the bounded file patterns remains unchanged; context helper has explicit negative-path regression (`test_inherent_ts_complexity_context_ignores_regular_files`) | Scope remains narrow to TS/JS schema or migration path patterns; findings are retained (not suppressed), preserving visibility for manual review | 4 | 3 | 4 | 48 | Mitigated |

## 2026-04-12 - Issue #254: FOE plugin SDK sub-path import grouping

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| FOE | FP: plugin SDK sub-path imports (`openclaw/plugin-sdk/*`) are counted as many independent dependencies | FOE counted raw import specifiers instead of package-level dependency identity for JS/TS sub-path imports | Files with one coherent SDK appeared as fan-out hubs, generating medium-severity noise | New regressions in `tests/test_fan_out_explosion.py` (`test_plugin_sdk_subpaths_grouped_to_single_dependency`, `test_scoped_package_subpaths_grouped_to_scope_package`) | Normalize imports to dependency keys before counting: scoped packages use `@scope/pkg`, non-relative slash imports use `vendor/pkg`, Python keeps top-level package counting | 7 | 8 | 2 | 112 | Mitigated |
| FOE | FN-risk: real high fan-out may be under-counted when many independent `vendor/pkg/*` families share vendor prefix semantics | Grouping reduces granularity for sub-path-heavy code patterns | Potential under-prioritization of some true fan-out hotspots | Existing FOE TP score-growth tests remain active; new scoped-package regression ensures threshold behavior still triggers when enough distinct dependencies remain | Grouping is bounded to dependency identity only; relative imports remain file-granular and findings still trigger beyond threshold | 4 | 3 | 4 | 48 | Mitigated |

## 2026-04-12 - Issue #252: NBV TS method-context parsing for ensure_ delegation

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| NBV | FP: TypeScript class methods with `ensure_` delegation are flagged although contract is fulfilled via returned delegated call | Method source slices (for example `Class.method`) can be parsed without class context, so TS rule-check AST misses `return`/`throw` nodes | Medium-noise cluster in TS runtime/provider classes, reduced NBV credibility | New regression `test_ensure_ts_delegated_raise_contract_no_finding` in `tests/test_naming_contract_violation.py` and targeted repro from Issue #252 | Re-parse TS method snippets in synthetic class wrapper before running `_has_raise`/ensure checks so return/throw nodes are preserved | 7 | 7 | 2 | 98 | Mitigated |
| NBV | FN-risk: synthetic method wrapping could over-accept malformed method snippets | Fallback parser path prefers wrapped parse for dotted method names | Potential under-reporting for edge-case malformed snippets | Existing negative guard `test_ensure_without_throw_or_return_value_is_flagged` remains active | Fallback is bounded to dotted method names (`Class.method`) and keeps existing no-op ensure rejection behavior | 4 | 3 | 4 | 48 | Mitigated |

## 2026-04-12 - Issue #253: TVS FP bei aktiver Extension-Workspace-Entwicklung

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| TVS | FP: aktive `extensions/*`/`plugins/*` Workspaces werden als HIGH-Volatilitaet priorisiert, obwohl koordinierte Feature-Entwicklung vorliegt | TVS bewertet Datei-Volatilitaet repo-global als Outlier, ohne Workspace-Lebenszyklus (neu/koordiniert-burstig) zu beruecksichtigen | Hohe Finding-Menge in Plugin-Monorepos, sinkende Signal-Glaubwuerdigkeit und unnoetige Triage-Last | Neue Regressionen in `tests/test_coverage_pipeline_and_helpers.py` (`test_extension_workspace_burst_is_dampened`, `test_non_plugin_outlier_keeps_high_severity`) | Workspace-Heuristik in TVS: neue oder koordinierte aktive Plugin-Workspaces (`extensions/*`, `plugins/*`) werden score-seitig auf max 0.45 gecappt, mit `workspace_burst_dampened`-Metadata und begrenztem Scope | 7 | 8 | 2 | 112 | Mitigated |
| TVS | FN-Risiko: echte Instabilitaet innerhalb aktiver Plugin-Workspaces wird niedriger priorisiert | Neue TVS-Daempfung reduziert Severity in als burstig klassifizierten Workspaces | Potenziell spaetere Priorisierung realer Refactoring-Bedarfe in einzelnen aktiven Extensions | Gegenregression sichert unveraenderte HIGH-Erkennung ausserhalb Plugin-Workspaces | Daempfung ist auf klaren Workspace-Scope + Burst-Kriterien begrenzt; Findings bleiben sichtbar (keine Vollsuppression) | 4 | 3 | 4 | 48 | Mitigated |

## 2026-04-12 - Issue #249: COD FP bei Plugin-Registrierung und typed utility modules

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| COD | FP: `register*`-Pluginmodule sowie `format.ts`/`test-helpers.ts` in `extensions/*/src` werden als Cohesion Deficit gemeldet | COD gewichtet isolierte Token, aber beruecksichtigt action-prefix-Familien und dateinamensbasierte Domain-Kohasion unzureichend | Unnoetige LOW/MEDIUM-Findings und sinkende Signal-Glaubwuerdigkeit in plugin-lastigen TS-Monorepos | Neue Regressionen in `tests/test_cohesion_deficit.py` (`test_cod_plugin_register_family_module_is_not_flagged`, `test_cod_plugin_create_family_helpers_are_not_flagged`, `test_cod_filename_domain_token_dampens_format_module`) | Neue Daempfung ueber `shared_action_prefix_ratio`, `filename_token_cohesion_ratio` und zusaetzliche Plugin-Workspace-Daempfung fuer `extensions/*/src` | 7 | 8 | 2 | 112 | Mitigated |
| COD | FN-Risiko: echte Inkohaerenz in Plugin-/Utility-Modulen wird zu stark abgewertet | Neue Prefix-/Filename-Heuristik kann in Randfaellen auch problematische Module daempfen | Potenziell spaetere Priorisierung echter Refactorings in betroffenen Modulen | Bestehende COD-TP/TN- und Ground-Truth-Tests bleiben aktiv; neue Regressionen sichern den Zielscope | Daempfung ist eng begrenzt (`>=0.6` action-prefix, `>=0.5` filename cohesion) und nicht global suppressiv | 4 | 3 | 4 | 48 | Mitigated |

## 2026-04-12 - Issue #251: TSB/BAT FP-Reduktion fuer src-test-helper und SDK-EventEmitter-Muster

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| TSB/BAT | FP: `src/test-helpers.ts` und `src/**/test-*.ts` als Produktionsdateien bewertet (`finding_context=production`) | Zentrale Testdatei-Erkennung deckte Dateinamenmuster ohne `.test/.spec`-Suffix nicht ab | Hohe Severity-Noise in TS-Monorepos mit ko-lokierten Test-Utilities | Neue Regressionen in `tests/test_test_detection.py` und `tests/test_type_safety_bypass.py` (`test_src_test_helpers_and_test_prefixed_paths_are_skipped`) | `is_test_file` um dateibasierte Muster `test-helpers.*` und `test-*.{ts,js,tsx,jsx}` erweitert; TSB respektiert dadurch globales Test-Handling | 7 | 8 | 2 | 112 | Mitigated |
| TSB/BAT | FP: SDK-idiomatische EventEmitter-`!`-Aufrufe (`page.on!`, `off!`, `once!`) als vollwertige Type-Bypasses priorisiert | Alle `non_null_expression` wurden gleich gewichtet, auch bei bekannten Playwright/Discord SDK-Interop-Mustern | Ueberpriorisierte TSB-Befunde in Browser-/SDK-Interaktionsdateien | Neue Regression `test_sdk_event_emitter_non_null_assertions_are_dampened` in `tests/test_type_safety_bypass.py` | Neue TSB-Heuristik: bei bekannten SDK-Imports werden EventEmitter-Non-Null-Assertions als `non_null_assertion_sdk` markiert und fuer die Severity-Score-Berechnung mit reduziertem Gewicht beruecksichtigt | 7 | 7 | 2 | 98 | Mitigated |
| TSB/BAT | FN-Risiko: echte unsichere `!`-Nutzung in SDK-nahen Dateien wird zu stark abgeschwaecht | Neue Gewichtung reduziert den Einfluss bestimmter `!`-Muster auf den Score | Potenzielle Unterpriorisierung einzelner realer Defekte in SDK-Dateien | Vergleichsregression gegen nicht-SDK-Datei (`interactions.ts`) bleibt aktiv | Daempfung ist eng auf bekannte SDK-Importe + EventEmitter-Methoden (`on/off/once/addListener/removeListener`) begrenzt; andere Bypass-Arten (`as any`, directives) bleiben unveraendert gewichtet | 4 | 3 | 4 | 48 | Mitigated |

## 2026-04-12 - Issue #250: MAZ FP bei outbound API-Client-Funktionen (TS unknown framework)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| MAZ | FP: outbound API-Client-Helper (`rest.put/get/delete`, SDK-Wrapper) als ungeschuetzte Inbound-Endpunkte gemeldet | Bei `framework=unknown` reichte route-aehnlicher Pfad (`/channels/...`) als Endpoint-Indiz; Inbound-Handler-Signatur wurde nicht geprueft | Security-Noise (teils CRITICAL) in Extension-/Plugin-Clients, reduzierte Glaubwuerdigkeit von MAZ | Neue Regression in `tests/test_missing_authorization.py` (`test_typescript_unknown_framework_skips_outbound_api_client_signature`) | Zusaetzliche Unknown-Framework-Grenze: MAZ meldet TS/JS nur noch mit route-aehnlichem Pfad **und** inbound-typischer Handler-Signatur (`req/request/res/response/reply/ctx/context/next`) | 7 | 8 | 2 | 112 | Mitigated |
| MAZ | FN-Risiko: echte unbekannte TS-Endpunkte ohne typische Handler-Parameter werden nicht gemeldet | Neue Signatur-Grenze priorisiert Praezision in Unknown-Framework-Faellen | Potenziell spaetere Priorisierung einzelner unkonventioneller Handler-Signaturen | Bestehende Guard-Regression `test_typescript_unknown_framework_keeps_route_like_path` wurde auf `req/res` angepasst und bleibt aktiv | Scope ist auf TS/JS mit `framework=unknown` begrenzt; bekannte Framework-Pfade und Python bleiben unveraendert | 4 | 3 | 4 | 48 | Mitigated |

## 2026-04-12 - Issue #248: EDS FP-Reduktion fuer typisierte TypeScript/TSX-Funktionen ohne JSDoc

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| EDS | FP: typisierte TS/TSX-Funktionen ohne JSDoc als Explainability Deficit priorisiert | EDS behandelte fehlende Docstring-/Return-Type-Evidenz sprachunabhaengig wie Python und bewertete TS-Signaturen nicht als Erklaerungsbeleg | Dominante Finding-Mengen in TS-Monorepos, reduzierte Glaubwuerdigkeit und Triage-Last | Neue Regressionen in `tests/test_coverage_boost_15_signals_misc.py` (`test_exd_typescript_typed_signature_not_flagged_without_jsdoc`, `test_exd_typescript_inferred_return_not_penalized`) | TS/TSX-Heuristik: signaturbasierte Erklaerungs-Evidenz (`self_documenting_signature`), inferierte Return-Typen akzeptieren, score-daempfung und sprachspezifische Description/Fix-Hinweise | 7 | 8 | 2 | 112 | Mitigated |
| EDS | FN-Risiko: reale Explainability-Defizite in TS/TSX werden zu stark abgeschwaecht | Neue TS-Signatur-Heuristik kann schlecht benannte, aber typisierte Helfer niedriger priorisieren | Potenziell spaetere Priorisierung einzelner echter EDS-Befunde in TS-Modulen | Guard-Regression `test_exd_javascript_still_requires_explainability_evidence` sichert, dass nur TS/TSX betroffen ist | Heuristik ist eng auf TS/TSX mit vorhandenen Parametern begrenzt; JS/Python-Logik bleibt unveraendert | 4 | 3 | 4 | 48 | Mitigated |

## 2026-04-12 - Issue #247: GCD FP bei deklarativen Plugin-Methoden und stark typisierten TS-Wrappern

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| GCD | FP: deklarative TS-Delegationsfunktionen ohne inhaltliche Guard-Logik als Defizit gemeldet | Bisherige TS-Heuristik erkannte nur explizite `if-throw/return` Guards und behandelte Call-through-Wrapper pauschal als unguarded | Ueberpriorisierte GCD-Findings in Plugin-Registrierungs-/Adaptercode, reduzierte Signal-Glaubwuerdigkeit | Neue Regressionen in `tests/test_ts_signals_phase2.py` (`test_ts_single_delegation_wrappers_are_treated_as_guarded`) | Wrapper-Heuristik: einzeilige TS-Call-through-Funktionen, die Parameter weiterreichen, gelten als guarded | 7 | 8 | 2 | 112 | Mitigated |
| GCD | FP: stark typisierte TS-Funktionen ohne imperativen Kontrollfluss als fehlende Guards gemeldet | TypeScript-Vertragsinformation (nicht-`any` Parameter) wurde nicht als Eingabevalidierungs-Signal gewertet | Noise in statisch sicherem Adapter-/Transformationscode, unnoetige Triage | Neue Regression `test_ts_strongly_typed_non_imperative_functions_are_treated_as_guarded` | Zusatzheuristik: voll typisierte TS-Parameter ohne weak types (`any`, `unknown`, `object`, `null`, `undefined`) und ohne imperativen Kontrollfluss werden als guarded bewertet | 6 | 6 | 3 | 108 | Mitigated |
| GCD | FN-Risiko: reale Guard-Defizite in einfach wirkenden Wrappern werden abgeschwaecht | Neue Wrapper-/Typed-Suppression kann in Randfaellen semantisch schwache Validierungsmuster zu niedrig priorisieren | Potenziell spaetere Priorisierung einzelner echter Defekte | Bestehende Negativregression fuer unguarded TS-Funktionen bleibt aktiv (`test_ts_unguarded_functions_triggers`) | Heuristiken sind eng auf Call-through-Pattern und non-imperative, stark typisierte TS-Funktionen begrenzt | 4 | 3 | 4 | 48 | Mitigated |

## 2026-04-12 - Issue #246: SMS FP bei neuen Extension-Abhaengigkeiten

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| SMS | FP: novel dependencies in neuen `extensions/*`/`plugins/*` Workspaces als Drift priorisiert | SMS bewertet neue Third-Party-Imports module-lokal ohne Beruecksichtigung, dass ein komplett neuer Plugin-Workspace seine eigenen Domain-Abhaengigkeiten bewusst einfuehrt | Hohe Finding-Menge und unnoetige MEDIUM/LOW-Priorisierung bei legitimer Erweiterung | Neue Regressionen in `tests/test_coverage_signals.py` (`test_sms_suppresses_novel_imports_in_new_extension_workspace`, `test_sms_still_reports_novel_imports_for_existing_extension_workspace`) | Workspace-Heuristik: neue Runtime-Plugin-Workspaces (alle getrackten Dateien nur recent) werden fuer SMS-Novel-Import-Erkennung unterdrueckt; etablierte Workspaces bleiben analysiert | 7 | 8 | 2 | 112 | Mitigated |
| SMS | FN-Risiko: echte Fehlanpassung in ganz neuem Workspace wird nicht sofort gemeldet | Suppression reduziert SMS-Sichtbarkeit waehrend der initialen Einfuehrungsphase eines neuen Plugins | Potenziell spaetere Erkennung echter Architekturabweichungen in Erst-Commits | Guard-Regression fuer etablierte Workspaces bleibt aktiv; bestehende allgemeine SMS-Detektion ausserhalb neuer Workspaces unveraendert | Heuristik ist eng auf `extensions/<name>` und `plugins/<name>` mit rein recent Historie begrenzt; nach Etablierung greift SMS wieder normal | 4 | 3 | 4 | 48 | Mitigated |

## 2026-04-12 - Issue #245: PFS cap to INFO for combined framework+plugin context

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| PFS | FP: Cross-extension plugin diversity still prioritized above informational context | Existing dampening reduced severity but did not enforce a terminal cap when both framework-facing and multi-plugin context were detected together | Medium/low findings still consumed triage budget in intentional plugin architectures | New regression `test_combined_framework_and_plugin_dampening_caps_to_info` in `tests/test_pattern_fragmentation.py` | Add combined dampening cap: when `framework_context_dampened` and `plugin_context_dampened` are both true, severity is forced to `INFO` and metadata marks `combined_plugin_framework_cap` | 7 | 7 | 2 | 98 | Mitigated |
| PFS | FN-Risk: Real intra-module fragmentation in plugin API modules may be under-prioritized | INFO cap for combined contexts can down-rank some true issues in extension-local API layers | Potentially slower remediation for genuine inconsistency in plugin surfaces | Core/no-plugin and plugin-only dampening tests remain active; new test is scoped to combined context only | Cap is bounded to simultaneous framework+multi-plugin hints; non-combined paths keep existing severity logic and score visibility | 4 | 3 | 4 | 48 | Mitigated |

## 2026-04-12 - Issue #244: MDS FP bei absichtlicher Cross-Plugin-Duplikation

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| MDS | FP: identische/nahe Duplikate ueber verschiedene `extensions/*` oder `plugins/*` als HIGH/MEDIUM gemeldet | MDS behandelte absichtliche Workspace-Isolation wie gewoehnliches Copy-Paste und kannte keine Plugin-Scope-Heuristik | Hohe Noise-Last und sinkende Glaubwuerdigkeit in Plugin-Monorepos | Neue Regressionen in `tests/test_mutant_duplicates_edge_cases.py` (`test_analyze_caps_cross_plugin_exact_duplicates_to_info_issue_244`) | Neue Workspace-Isolation-Heuristik: Cross-Plugin-Paare/-Gruppen werden auf INFO + niedrigen Score gecappt und mit Metadata markiert | 7 | 8 | 2 | 112 | Mitigated |
| MDS | FN-Risiko: echte, schaedliche Duplikation zwischen Plugins wird niedriger priorisiert | INFO-Cap fuer Cross-Plugin-Scope kann reale Kopplungsprobleme zwischen Plugins abschwaechen | Potenziell spaetere Priorisierung echter Cross-Plugin-Refactorings | Gegenregression fuer gleiches Workspace-Paket bleibt HIGH (`test_analyze_keeps_same_workspace_exact_duplicates_actionable_issue_244`) | Heuristik ist eng auf unterschiedliche Plugin-Scopes begrenzt; intra-workspace und nicht-plugin Pfade bleiben unveraendert; verifiziert mit `pytest tests/test_mutant_duplicates_edge_cases.py -q` | 4 | 3 | 4 | 48 | Mitigated |

## 2026-04-12 - Issue #243: CCC FP bei Parallel-Implementierungen und expliziten type-imports

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| CCC | FP: legitime Parallel-Implementierungen als hidden coupling gemeldet (`*-gateway` <-> `*-node`, `extensions/*/src/index.ts`) | CCC unterscheidet nicht zwischen impliziter Kopplung und absichtlicher Contract-Parallelitaet (Runtime-Varianten, Plugin-Template-Entrypoints) | Hohe FP-Rate in Plugin-/Agenten-Repos, reduzierte Glaubwuerdigkeit und Triage-Last | Neue Regressionen in `tests/test_co_change_coupling.py` (`test_parallel_runtime_variants_are_suppressed`, `test_cross_extension_template_entrypoints_are_suppressed`) | Gezielte Suppression fuer Runtime-Variant-Paare im gleichen Ordner und fuer cross-extension `src/index.{ts,js,tsx,jsx}` Template-Entrypoints | 7 | 8 | 2 | 112 | Mitigated |
| CCC | FP: explizite TS `import type`-Kopplung als hidden coupling gemeldet (`./types.js` -> `types.ts`) | Relative Import-Aufloesung war Python-zentriert und mappt TS/JS Runtime-Specifier nicht robust auf In-Repo-Quellen | Sichtbare, explizite Abhaengigkeiten werden faelschlich als versteckte Kopplung klassifiziert | Neue Regression `test_relative_type_import_counts_as_explicit_dependency` | Relative Resolver erweitert: normierte relative Pfade + Extension-Alias fuer `.js/.jsx/.mjs/.cjs` -> `.ts/.tsx` bei bekannten In-Repo-Dateien | 7 | 7 | 2 | 98 | Mitigated |
| CCC | FN-Risiko: echte hidden coupling zwischen aehnlichen Varianten oder Plugin-Entrypoints bleibt ungemeldet | Neue Suppressionen koennen Randfaelle mit realer Architektur-Erosion in denselben Mustern reduzieren | Potenzielle Unterberichtung einzelner echter Defekte | Bestehender Guard-Test fuer cross-extension non-template Paar bleibt aktiv (`test_monorepo_cross_extension_pair_still_detects_hidden_coupling`) | Suppression eng begrenzt auf definierte Muster (runtime-token sibling variants, `extensions/*/src/index.*`), sonst unveraenderte CCC-Logik | 4 | 3 | 4 | 48 | Mitigated |

## 2026-04-12 - Issue #242: DCA FP bei Plugin-Entrypoints (components/plugin-sdk)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| DCA | FP: Plugin-Entrypoint-Exporte (`components`, `plugin-sdk`) als ungenutzt gemeldet | DCA nutzt statischen Importgraph; Host-Registry-/Framework-Wiring fuer Extension-Komponenten und SDK-Entrypoints ist oft indirekt und statisch nicht aufloesbar | Kritische/hohe Noise-Findings in Plugin-Monorepos, reduzierte Signal-Glaubwuerdigkeit | Neue Regressionen in `tests/test_dead_code_accumulation.py` (`TestDCARuntimePluginEntrypointHeuristic`) | Erweiterte Entrypoint-Heuristik fuer `extensions|plugins` + `components`/`plugin-sdk`-Pfade mit Score-Daempfung und Severity-Cap auf MEDIUM; Metadata-Flag zur Nachvollziehbarkeit | 7 | 8 | 2 | 112 | Mitigated |
| DCA | FN-Risiko: echte ungenutzte Exporte in Plugin-Entrypoints werden niedriger priorisiert | Heuristische Daempfung greift auf dateipfadbasierten Entrypoint-Signalen und kann reale Dead-Exports abschwaechen | Potenziell spaetere Bereinigung einzelner echter Dead-Exports in Plugin-Entrypoints | Bestehende Gegenregression fuer Nicht-Entrypoint-Dateien (`test_extensions_non_config_file_is_not_dampened`) bleibt aktiv | Scope bleibt auf `extensions|plugins` mit `components`/`plugin-sdk`-Indikatoren begrenzt; keine komplette Suppression, nur Daempfung/Cap | 4 | 3 | 4 | 48 | Mitigated |

## 2026-04-12 - Issue #241: AVS TS ESM relative import extension mapping

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| AVS | FP: hidden coupling finding emitted although static import exists (`../x.js` from `.ts`) | Import resolver treated TS ESM runtime extension specifier literally and failed to map to source file extension (`.js` vs `.ts`) | False architectural drift findings and reduced AVS credibility in modern NodeNext/Node16 TS repos | New regressions in `tests/test_architecture_violation.py` for `.js -> .ts` and `.mjs/.cjs -> .mts/.cts` | Add relative path candidate resolver with extension alias mapping and path-index lookup in `build_import_graph()` | 7 | 8 | 2 | 112 | Mitigated |
| AVS | FN-risk: wrong sibling file could be resolved under broad aliasing | Multiple similarly named files with mixed extensions may compete for one import specifier | Potential under-reporting if edge resolves to an unintended file | Existing AVS co-change and import-edge tests remain active; mappings constrained to known file index | Keep mapping bounded to relative imports and explicit extension aliases only; no global non-relative rewrite | 4 | 3 | 4 | 48 | Mitigated |

## 2026-04-12 - Issue #238: HSC FP bei dynamischen Template-Literalen

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| HSC | FP: interpolierte Template-Literale (`token = `${a}:${b}``) werden als hardcoded secret gemeldet | TS/JS-Pfad bewertet den extrahierten Template-String wie ein statisches Literal und laesst Entropie-/Literal-Regeln greifen | Security-Noise (teils HIGH) bei runtime-generierten Token/ID/Display-Werten | Neue Regressionen in `tests/test_hardcoded_secret.py` fuer randomUUID-, display- und JWT-Template-Faelle | Suppression fuer dynamische Template-Literale (`quote == \`` und `${` im Wert) vor Entropiepfad in `_evaluate_ts_assignment` | 6 | 8 | 2 | 96 | Mitigated |
| HSC | FN-Risiko: echte Secrets, die erst per Template zusammengebaut werden, werden nicht mehr gemeldet | Neue Suppression akzeptiert alle interpolierten Template-Literale unabhaengig vom konkreten Ausdruck | Potenzielle Unterberichtung bei bewusst zusammengesetzten Secrets | Bestehende Known-Prefix-Regressionen und statische Literal-TPs bleiben aktiv; Full test suite gruen | Scope bleibt auf interpolierte Templates begrenzt; statische Literale und Known-Prefix-Strings sind unveraendert detektierbar | 5 | 3 | 4 | 60 | Mitigated |

## 2026-04-12 - Issue #240: NBV TS naming-contract precision hardening (is*/has*/try*/ensure*)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| NBV | FP: `try*` TypeScript nullable getter als Contract-Verletzung gemeldet | `try_*` wurde primär als Python-`try/except`-Konvention interpretiert; TS-Nullable-Getter (`T \| undefined/null`) nicht als gueltiger Versuchsvertrag erkannt | Hohe FP-Quote in TS-Runtime-Helpern, reduzierte Glaubwuerdigkeit des NBV-Signals | Neue Regression `test_try_ts_nullable_getter_contract_no_finding` in `tests/test_naming_contract_violation.py` | TS-spezifische `try_*`-Contract-Erfuellung bei nullable Return-Signaturen (`|undefined`/`|null`) plus bestehende graceful-failure Heuristiken | 7 | 7 | 2 | 98 | Mitigated |
| NBV | FN-Risiko: zu weite Nullable-Akzeptanz koennte echte try*-Verletzungen verdecken | Nullable-Union allein kann semantisch schwache Implementierungen legitimieren | Potenzielle Unterberichtung einzelner schwacher `try*`-Implementierungen | Bestehende Negativtests fuer nicht-erfuellte Vertrage bleiben aktiv; bool/ensure/testfaelle weiterhin regressionsgesichert | Regel auf `try_*` und explizite nullable Return-Typen begrenzt; andere Prefix-Regeln unveraendert | 4 | 3 | 4 | 48 | Mitigated |

## 2026-04-11 - Issue #237: DCA FP bei runtime-geladenen plugin config exports

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| DCA | FP: config-exports in `extensions/*`/`plugins/*` als ungenutzt gemeldet, obwohl runtime geladen | DCA basiert auf statischem Importgraph; dynamische `import()`-Ladepfade fuer Plugin-Configs sind nicht aufloesbar | Hohe DCA-Noise in Plugin-Architekturen, ueberschaetzte Severity (teilweise HIGH) | Neue Regressionen in `tests/test_dead_code_accumulation.py` (`TestDCARuntimePluginConfigHeuristic`) | Kontextheuristik fuer plugin-config-Dateien (`config*`) mit Score-Daempfung und Severity-Cap auf MEDIUM; Marker in Metadata | 7 | 8 | 2 | 112 | Mitigated |
| DCA | FN-Risiko: echte ungenutzte Exports in plugin-config-Dateien werden niedriger priorisiert | Daempfung greift auf Dateipfad/Filename-Heuristik und kann reale Dead-Exports abschwaechen | Potenziell spaetere Bereinigung von echten Dead-Exports in Plugin-Configs | Gegenregression fuer Nicht-Config-Dateien in `extensions/*` bleibt HIGH (`test_extensions_non_config_file_is_not_dampened`) | Scope eng auf `extensions|plugins` + `config*` begrenzt; kein Suppress, nur Daempfung/Cap mit nachvollziehbarem Metadata-Flag | 4 | 3 | 4 | 48 | Mitigated |

## 2026-04-11 - Issue #235: CCC monorepo intra-package co-change FP reduction

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| CCC | FP: intra-package co-change in monorepo extension reported as hidden coupling | CCC lacked package-boundary awareness and treated all repeated co-change pairs equally when no explicit import edge was found | High false-positive volume in `extensions/<name>/...` structures and reduced signal trust | New regressions in `tests/test_co_change_coupling.py` (`test_monorepo_intra_extension_pair_is_suppressed`) | Suppress pairs that share same monorepo subpackage scope (nearest subpackage `package.json` below repo root, fallback: `extensions/<name>/`) | 7 | 8 | 2 | 112 | Mitigated |
| CCC | FN risk: true hidden coupling inside same extension package is suppressed | Intra-package suppression can hide accidental coupling within one extension boundary | Potential under-reporting for poor internal module boundaries inside one package | Regression `test_monorepo_cross_extension_pair_still_detects_hidden_coupling` keeps cross-package detection active | Scope is intentionally bounded to same subpackage only; cross-extension coupling remains reportable | 4 | 3 | 4 | 48 | Mitigated |

## 2026-04-11 - Issue #236: HSC FP bei testnahen Secret-Fixtures mit TEST_/MOCK_-Praefix

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| HSC | FP: testnahe Fixture-Konstanten (`TEST_*`, `MOCK_*`, `FAKE_*`, `DUMMY_*`, `STUB_*`) als Hardcoded Secret gemeldet | Known-prefix- und secret-var Erkennung unterschied nicht zwischen produktiven Variablen und explizit testmarkierten Fixture-Konstanten | Security-Noise in Test-/Fixture-nahem Code, reduzierte Signal-Glaubwuerdigkeit | Neue Regressionen in `tests/test_hardcoded_secret.py` fuer Prefix- und test-helper-Faelle | Prefix-Suppression fuer testmarkierte Variablennamen + erweiterte test-helper/test-fixture Pfadbehandlung in HSC | 6 | 7 | 2 | 84 | Mitigated |
| HSC | FN-Risiko: zu breite Prefix-Suppression koennte echte Leaks mit testaehnlichem Namen maskieren | Prefix-Regel greift kontextunabhaengig auf Variablennamen | Potenzielle Unterberichtung in seltenen Fehlbenennungen | Guard ueber bestehende bekannte-prefix True-Positive-Regressionen + gezielte Negativtests | Regel auf explizite Start-Praefixe begrenzt (`TEST_`, `MOCK_`, `FAKE_`, `DUMMY_`, `STUB_`); keine globale Secret-Pattern-Abschwaechung | 5 | 2 | 4 | 40 | Mitigated |

## 2026-04-11 - Issue #234: Testkontext-Erkennung fuer test-harness/test-helpers erweitert

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| ALL (context-driven) | FP: testnahe Dateien als Produktionscode klassifiziert (`finding_context=production`) | Zentrale Erkennung kannte Konventionen `*.test-harness.*`, `*.test-helpers.*`, `test-support/`, `test-helpers/` nicht | Stark erhoehte Finding-Mengen und Severity-Noise ueber mehrere Signale | Regressionen in `tests/test_test_detection.py` fuer Datei- und Verzeichnismuster | Erweiterung der zentralen Muster in `is_test_file`; keine signal-spezifischen Sonderregeln notwendig | 7 | 8 | 2 | 112 | Mitigated |
| ALL (context-driven) | FN-Risiko: produktive Dateien mit helper/support-Namen werden als Testcode gewertet | Neue Verzeichnisregeln sind konservativ, aber breiter als vorher | Potenzielle Unterberichtung in Randfaellen | Bestehende Klassifikations-Tests + unveraenderte Fixture-Ausnahmen | Regeln auf klar benannte Testkonventionen beschraenkt; Fixture-Ausnahmen bleiben aktiv | 4 | 3 | 4 | 48 | Mitigated |

## 2026-04-11 - Issue #232: SMS test-only framework imports counted as production novel imports

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| SMS | FP: test-only framework imports (z. B. `vitest`) als produktive Novel Imports gemeldet | SMS beruecksichtigte `.test/.spec`-Dateien in Baseline und Novel-Import-Erkennung | Hohe Noise-Last in Repos mit co-lokierten Tests, reduzierte Signal-Glaubwuerdigkeit | Neue Regression `test_find_novel_imports_ignores_test_only_framework_imports` in `tests/test_coverage_signals.py` | Testdateien werden ueber zentrale Erkennung (`is_test_file`) in `_module_imports`, `_find_novel_imports` und Analyze-Filter ausgeschlossen | 7 | 8 | 2 | 112 | Mitigated |
| SMS | FN-Risiko: produktionsnahe Dateien mit testaehnlichem Namensmuster werden ausgeschlossen | Testpfadklassifizierung kann Randfaelle als Testkontext einstufen | Unterberichtung einzelner echter Novel-Import-Faelle | Bestehende zentrale Testdatei-Erkennungsregeln und Signal-Regressionen | Nutzung der bereits etablierten zentralen Testklassifikation statt signal-spezifischer Sonderheuristik; bestehende Fixture-Ausnahmen bleiben aktiv | 4 | 3 | 4 | 48 | Mitigated |

## 2026-04-11 - Issue #230: COD FP-Reduktion fuer Logger- und Utility-Module

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| COD | FP: Logger-Fassaden als Cohesion Deficit gemeldet | COD bewertet niedrige paarweise Namensaehnlichkeit bei Log-Level-Funktionen (`trace/debug/info/warn/error`) als Isolation, obwohl diese Entry-Points absichtlich parallel sind | Hohe FP-Last in Logger-Modulen und sinkende Signal-Glaubwuerdigkeit | Neue Regression `test_cod_logger_module_is_not_flagged` + `tests/test_precision_recall.py` | Logger-Modulerkennung (`logger`-Dateiname oder >=50% logger-/log-level-nahe Unit-Namen) mit starker Muster-Dempfung (`module_pattern_dampening=0.35`) | 7 | 8 | 3 | 168 | Mitigated |
| COD | FP: Utility-Dateien mit erwarteter Funktionsvielfalt zu streng priorisiert | Dateinamen mit `utils/helpers/constants` erhalten bisher keine Kontextdifferenzierung | Unnoetig hohe COD-Scores bei Hilfsmodulen | Regression `test_cod_utility_filename_still_flags_clear_deficit` verifiziert bounded behavior | Utility-Dateinamens-Hinweise fuehren zu moderater Dempfung (`module_pattern_dampening=0.8`), ohne klare Defizite komplett zu unterdruecken | 5 | 6 | 3 | 90 | Mitigated |
| COD | FN-Risiko: echte Inkohaerenz in Logger-Dateien wird unterdrueckt | Logger-Musterdempfung kann in Randfaellen auch problematische Logger-Module entschaerfen | Potenziell spaetere Erkennung realer Refactoring-Bedarfe in Logger-Modulen | Guard ueber bestehende COD-TP/TN-Suite + Ground-Truth-Lauf | Dempfung nur bei klaren Logger-Signalen; Utility-Dempfung bleibt konservativ und behaelt klare Defizite detektierbar | 4 | 3 | 4 | 48 | Mitigated |

## 2026-04-11 - Issue #231: DCA TS helper FP bei default export

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| DCA | FP: modulinterne TS/JS Helper als dead export gemeldet | DCA behandelte oeffentliche Funktionen in TS/JS pauschal als exportiert, auch wenn `is_exported=False` | Hohe Noise-Last in Facade-/Plugin-Modulen mit `export default` Einstiegspunkt | Regression in `tests/test_ts_export_detection.py::test_non_exported_ts_functions_are_not_treated_as_exports` | TS/JS-Pfad nutzt nur tatsaechlich exportierte Funktionen (`FunctionInfo.is_exported`) als DCA-Kandidaten | 7 | 8 | 2 | 112 | Mitigated |
| DCA | FN-Risiko: ungenaue Exportmarkierung im Parser unterdrueckt echte DCA-Faelle | Falls `is_exported` in Ingestion falsch gesetzt ist, koennen ungenutzte Exports uebersehen werden | Unterberichtung in einzelnen TS/JS-Dateien | Bestehende Export-Erkennungs-Tests (`tests/test_ts_export_detection.py`) + DCA Export-Testfall | Parser-Exporttests beibehalten; DCA-Logik bleibt fuer Python unveraendert | 4 | 3 | 4 | 48 | Mitigated |

## 2026-04-11 - Issue #229: PFS FP-Reduktion fuer Plugin-/Extension-Architekturen

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| PFS | FP: Plugin-spezifische API-Varianten als kritische Fragmentierung gemeldet | PFS bewertet starke Variantenvielfalt innerhalb `extensions/<plugin>/src` ohne Beruecksichtigung mehrerer koexistierender Plugin-Grenzen | Hohe Noise-Last (viele HIGH-Findings) und sinkende Glaubwuerdigkeit in Plugin-basierten Repos | Neue Regression `test_plugin_architecture_api_fragmentation_is_dampened_to_low` | Plugin-Layout-Heuristik (`extensions`/`plugins`/`packages` + >=3 Plugin-Namen) aktiviert starke Dempfung und Severity-Cap auf LOW; Kontext-Hinweise in Metadata | 7 | 8 | 3 | 168 | Mitigated |
| PFS | FN: Echte Fragmentierung in Plugin-Modulen wird zu stark abgewertet | Neue Dempfung kann auch reale Inkonsistenz innerhalb eines Plugins abschwaechen | Potenziell spaetere Erkennung echter Refactoring-Bedarfe | Bestehende Core-Regression `test_core_error_handling_is_not_dampened` bleibt aktiv | Dempfung greift nur bei klarer Multi-Plugin-Struktur; nicht in zentralen Core-Modulen ohne Plugin-Kontext | 5 | 3 | 4 | 60 | Mitigated |

## 2026-04-11 - Issue #227: HSC FP-Reduktion (Token-Prefixe, Endpoint-Templates, Test-Fixtures, Profile-IDs)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| HSC | FP: Prefix-Konstanten wie `*_TOKEN_PREFIX = "sk-...-"` als Secret gemeldet | Known-prefix-Pfad meldete bisher auch kurze Prefix-Marker-Literale | Hohe Noise-Quote bei Setup-/Validierungs-Konstanten, sinkendes Signal-Vertrauen | Neue Regression `test_token_prefix_constant_not_flagged_when_literal_is_only_prefix` | Known-prefix-Detection ignoriert Marker-Variablen, wenn Literal klar wie Prefix-Marker aussieht (kurz + endet auf `-`/`_`) | 6 | 8 | 3 | 144 | Mitigated |
| HSC | FP: TS Endpoint-Templates (`${ISSUER}/idp/token`) als Secret gemeldet | Endpoint-URL-Suppression deckte interpolierte Template-Literale nicht ab | OAuth-Konstanten erzeugen unnoetige Security-Findings | Neue Regression `test_ts_token_endpoint_template_constant_not_flagged` | Neue Suppression fuer Endpoint-/Issuer-Template-Literale bei endpointartigen Variablennamen | 5 | 7 | 3 | 105 | Mitigated |
| HSC | FP: Test-Fixture-Platzhalter in `test-fixture`-Dateien als Secret gemeldet | Zentrale Testdatei-Erkennung deckte `test-fixture`/`test_fixture`-Pfadvarianten nicht vollstaendig ab | Testdatenrauschen dominiert HSC-Ausgabe in Monorepos | Neue Regression `test_ts_test_fixture_placeholder_not_flagged` | Zusatzregel fuer test-fixture-Pfade im HSC-Analyze-Loop | 4 | 6 | 3 | 72 | Mitigated |
| HSC | FN-Risiko: echte Known-Prefix-Secrets koennten durch neue Prefix-Marker-Suppression verdeckt werden | Zu aggressive Suppression koennte auch volle Tokenwerte treffen | Unterberichtung echter Secret-Leaks | Bestehende Guard-Regression `test_marker_suppression_does_not_hide_known_prefix` bleibt gruen | Prefix-Suppression nur fuer markerartige kurze Literale mit Trailing-Delimiter; volle Tokens bleiben detektierbar | 8 | 2 | 3 | 48 | Mitigated |

## 2026-04-11 - Issue #219: NBV TS style-check FP and duplicate finding reduction

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| NBV | FP: TypeScript style conventions reported as drift (`I*` interfaces, mixed `T`/`TName` generics) | Style-oriented TS naming heuristics treated as architecture contract violations | High low-value noise and reduced trust in NBV findings | Regression updates in `tests/test_ts_naming_consistency.py` (`test_dominant_i_prefix_does_not_flag_outliers`, `test_mixed_generics_not_flagged`) | Remove style-only TS naming checks from NBV and keep architecture-relevant checks only | 7 | 8 | 2 | 112 | Mitigated |
| NBV | FP amplification: duplicate findings for same TS pattern/file | Duplicated TS naming-check blocks in NBV analyze path emitted findings twice | Inflated finding counts, triage fatigue, misleading severity distribution | Regression hardening in `tests/test_ts_naming_consistency.py` (`test_mixed_enum_casing_flagged` now expects exactly one finding) | Consolidate TS naming check path to one block | 6 | 7 | 2 | 84 | Mitigated |

## 2026-04-11 - Issue #215: NBV TS is*/has* bool-return extraction + fallback heuristics

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| NBV | FP: `is*`/`has*` TS functions flagged despite boolean contract | Parser missed return type from typed-arrow declarators and type predicates; metadata frequently `return_type: N/A` | High FP volume and reduced trust/actionability for NBV | Added parser + signal regressions (`test_extract_return_type_from_typed_arrow_declarator`, `test_type_predicate_return_type_no_finding`, `test_typed_arrow_declarator_return_type_no_finding`) | Add declarator-aware return type extraction and treat TS type-predicate annotations as bool-compatible | 8 | 8 | 3 | 192 | Mitigated |
| NBV | FN: fallback heuristic may over-accept non-bool return semantics | Relaxed fallback could infer bool from broad expression classes | Potential under-reporting of naming violations in edge cases | Negative controls keep non-bool wrappers and bare returns flagged; helper-level tests for bool-like classification | Keep heuristic bounded to explicit bool-indicator expressions (`!`, comparisons, `instanceof`, `in`, `Boolean(...)`) and avoid generic truthy/falsy acceptance | 5 | 3 | 4 | 60 | Mitigated |

## 2026-04-11 - Issue #218: Zentralisierte Testdatei-Erkennung und finding_context-Angleichung

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| TSB/MAZ/DCA/CCC/EDS | FP: Testcode wird als Produktionsdrift priorisiert | Heterogene lokale Testpfadregeln und fehlende gemeinsame Kontextnormalisierung | Hohe Triage-Last, sinkende Actionability | Neue Regressionstests in `tests/test_*` inkl. Kontext-Assertions (`finding_context == test`) | Zentrale `classify_file_context`-Nutzung + einheitliche `test_file_handling`-Strategie pro Signal | 6 | 7 | 3 | 126 | Mitigated |
| TSB/MAZ/DCA/CCC/EDS | FN: Reale Produktionsbefunde werden unterdrückt | Zu breite Testpfadklassifizierung (z. B. Fixture-/Sample-Pfade) | Unterberichtung in produktionsnahen Dateipfaden | Fixture-Regressionsfälle (u. a. `tests/fixtures/...`) in Zieltestsuite | Fixture-Ausnahme in zentraler Erkennung + konfigurierbarer globaler Override | 5 | 3 | 4 | 60 | Mitigated |
| ALL | Inconsistency: Kontext nur in `metadata`, nicht im Top-Level-Feld | Uneinheitliche Model-Nutzung in Signalimplementierungen | Erschwerte Downstream-Auswertung (JSON/SARIF/Tooling) | Modelltests + neue signalnahe Assertions auf `finding_context` | `Finding.finding_context` eingeführt und mit `metadata['finding_context']` synchronisiert | 4 | 4 | 3 | 48 | Mitigated |

## 2026-04-11 - Issue #214: NBV TS/JS ensure_* side-effect FP reduction

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| NBV | FP: TS/JS `ensure_*` idempotent init helpers flagged as violations | TS ensure contract recognized only `throw` or value-returning `return`; common ensure-by-side-effect (`mkdir`, `set`, property assignment) remained unrecognized | High FP clusters in initialization/bootstrap code, lower signal trust and actionability | Added regressions in `tests/test_naming_contract_violation.py` (`test_ensure_idempotent_mkdir_side_effect_no_finding`, `test_ensure_property_assignment_side_effect_no_finding`, `test_ensure_registry_set_side_effect_no_finding`) | Extend `_ts_has_ensure_contract()` to accept idempotent side-effect patterns while keeping no-op `ensure_*` functions (no throw/value/side-effect) reportable | 7 | 7 | 3 | 147 | Mitigated |
| NBV | FN: relaxed side-effect acceptance may over-accept weak `ensure_*` functions | Heuristic could classify broad mutation-like calls as contract fulfillment in edge cases | Potential under-reporting for truly weak ensure contracts | Existing negative control `test_ensure_without_throw_or_return_value_is_flagged` remains; requires explicit side-effect shape | Keep acceptance bounded to explicit assignment/update/mutating-call indicators and preserve strict no-op rejection path | 4 | 3 | 4 | 48 | Mitigated |

## 2026-04-11 - Issue #213: MAZ unknown-framework false-positive suppression

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| MAZ | FP: ordinary TS helpers flagged as missing-auth route handlers | Framework detection returned `unknown`, but MAZ trusted generic API pattern matches from method names like `get()` | Large false-positive clusters in utility/cache/store modules and lower triage trust | Regression tests in `tests/test_missing_authorization.py` (`test_typescript_unknown_framework_suppresses_non_route_like_pattern`, `test_typescript_unknown_framework_keeps_route_like_path`) | For TS/JS with `framework=unknown`, require strong route evidence (`route` looks like HTTP path) before flagging; add route-path public allowlist handling (e.g. `/oauth/callback`) | 7 | 8 | 3 | 168 | Mitigated |

## 2026-06-15 — Phase 4: Complex Signal Ports (HSC/CXS/ISD/MAZ for TypeScript)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| HSC | FP: TS environment reads (`process.env.X`) flagged as hardcoded secret | Regex `_VAR_ASSIGN_RE` captures assignment RHS including env reads | False triaging of env-based config as leaked secrets | Ground-truth TN fixture `hsc_ts_env_read_tn` + suppression tests | `_evaluate_ts_assignment()` suppresses `process.env.*` and `import.meta.env.*` prefixes before score evaluation | 6 | 3 | 3 | 54 | Mitigated |
| HSC | FN: TS secret with non-standard quoting not detected | Regex requires `"` or `'` delimited string values; template literals not covered | Potential under-reporting on template-literal secrets | Ground-truth TP fixture `hsc_ts_github_token_tp` validates direct string assignment detection | Regex covers both quote styles and all `const/let/var` forms; template-literal gap documented | 5 | 2 | 4 | 40 | Accepted |
| CXS | FP: Simple TS function reported as high cognitive complexity | tree-sitter nesting model may over-count in JSX-heavy components | Over-reporting on idiomatic React patterns | Ground-truth TN fixture `cxs_ts_flat_code_tn` with flat functions | `_ts_cc_recurse()` only counts language-level nesting types, not JSX elements | 5 | 2 | 3 | 30 | Mitigated |
| CXS | FN: TS function with deep ternary chains not detected | Threshold at 15 may miss moderate-complexity functions | Under-reporting of moderately complex TS code | Ground-truth TP fixture `cxs_ts_deep_nesting_tp` with nested if/for/switch at CC>15 | Threshold consistent with Python CXS; validated by TP fixture | 4 | 3 | 3 | 36 | Mitigated |
| ISD | FP: TS `secure: false` in non-cookie context flagged | Regex `_TS_COOKIE_INSECURE_RE` matches any `secure: false` line | Over-reporting on non-session configuration | Context keyword check (`cookie`, `session`, `express-session`) on same line | Only fires when cookie/session context keyword found on same line | 5 | 3 | 3 | 45 | Mitigated |
| ISD | FN: CORS misconfiguration in dynamic config not detected | Regex-based detection misses computed or variable-based origins | Under-reporting of dynamic CORS bypasses | Ground-truth TP fixtures `isd_ts_cors_wildcard_tp` and `isd_ts_reject_unauth_tp` | Regex patterns cover most common literal patterns; dynamic configs require runtime analysis | 4 | 4 | 4 | 64 | Accepted |
| MAZ | FP: TS Express route with middleware auth not recognized | `_has_auth_in_call_args()` may miss custom auth middleware names | Over-reporting on properly secured endpoints | Ground-truth TN fixture `maz_ts_express_auth_tn` with named middleware | `_TS_AUTH_MARKERS` covers 30+ common auth identifiers; middleware arg positions checked | 5 | 3 | 3 | 45 | Mitigated |
| MAZ | FN: NestJS decorator-based auth not detected | `_has_auth_decorator_ts()` may miss custom guard class names | Under-reporting on NestJS apps with custom guards | `@UseGuards` detection via sibling decorator search on class methods | Covers `UseGuards`, `Authenticated`, and 10+ common decorator names | 4 | 3 | 4 | 48 | Accepted |

## 2026-04-11 - Issue #212: HSC FP-Reduktion (Env-Name-/Marker-Konstanten)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| HSC | FP: Env-Var-Namenskonstanten als Hardcoded-Secret gemeldet | Secret-shapiger Variablenname (`*_SECRET_*`, `*_TOKEN_*`) + ALL_CAPS env-name literal (`AWS_SECRET_ACCESS_KEY`) wurde als Geheimniswert interpretiert | Hohe Triage-Last in TS/Python-Konstantenmodulen und geringere Signal-Glaubwuerdigkeit | Neue Regressionen in `tests/test_hardcoded_secret.py` (`test_env_var_name_constant_not_flagged`, `test_env_var_name_with_var_suffix_not_flagged`) | Suppression fuer Env-Name-Literale: ALL_CAPS_SNAKE + Secret-Terme + env-name-typischer Variablenname (`*_ENV`, `*_ENV_KEY`, `*_KEY_ENV`, `*_VAR`, `_ENV`) | 6 | 7 | 3 | 126 | Mitigated |
| HSC | FP: Marker/Sentinel-Konstanten als Hardcoded-Secret gemeldet | Marker- und Message-Konstanten enthalten Token/Secret-Woerter im Namen, aber nur Marker- oder Error-Code-Literale im Wert | Rauschen in Setup-/Runtime-/Error-Konstanten reduziert Actionability | Neue Regression `test_marker_and_message_constants_not_flagged` + Helper-Tests fuer `_is_marker_constant_name` | Suppression auf Variablennamenebene fuer `MARKER`, `PREFIX`, `ALPHABET`, `MESSAGE`, `ERROR_CODE` | 5 | 7 | 3 | 105 | Mitigated |
| HSC | FN: Neue Suppression verdeckt echte API-Token mit Known Prefix | Suppressionen koennten versehentlich vor Prefix-Erkennung greifen | Realer Secret-Leak bleibt ungemeldet | Guard-Regressionen `test_env_var_name_suppression_does_not_hide_known_prefix` und `test_marker_suppression_does_not_hide_known_prefix` | Bekannte Prefix-Detektion (`ghp_`, `sk-`, `AKIA`, ...) bleibt vor Suppression priorisiert | 8 | 2 | 3 | 48 | Mitigated |

## 2026-04-11 - Issue #211: TSB exclude test/spec and mock paths

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| TSB | FP: test/spec files flagged as production type-safety debt | Signal analyzed TS test fixtures and mock scaffolding (`*.test.ts`, `*.spec.tsx`, `__tests__`, `__mocks__`) like production code | Dominant false-positive cluster, lower triage trust, reduced actionability | `tests/test_type_safety_bypass.py::test_test_and_mock_paths_are_skipped` | Skip known test/spec/mock path patterns in TSB analysis loop before parsing/counting bypasses | 7 | 8 | 2 | 112 | Mitigated |
| TSB | FN risk: production files accidentally skipped due over-broad path matching | Path classifier could suppress real findings when non-test files resemble test naming | Potential under-reporting in edge naming cases | Parametrized regression cases limited to explicit suffixes/dirs | Restrict skip rule to exact suffix set (`.test.ts/.spec.ts/.test.tsx/.spec.tsx`) and explicit dirs (`__tests__`, `__mocks__`) | 4 | 2 | 4 | 32 | Mitigated |

## 2026-04-11 - ADR-055: Dependency-aware Signal Cache Keying

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| CACHE | FP-equivalent: stale findings reused for changed file | file_local cache key not tied to per-file content hash | Outdated findings after local edits | `test_signal_phase_file_local_dependency_cache_reruns_only_changed_file` | file_local path hashes keyed per file + targeted rerun on miss | 7 | 2 | 3 | 42 | Mitigated |
| CACHE | FN-equivalent: needless cache invalidation for unaffected files | global content hash invalidates entire signal cache | Performance degradation and lower incremental usability | pipeline component tests + cache-key unit tests | dependency-aware keying (`file_local/module_wide/repo_wide/git_dependent`) behind feature flag | 4 | 6 | 2 | 48 | Mitigated |
| CACHE | Stale git-dependent cache entry after commit churn | git-dependent key ignores commit/file-history changes | Drift findings lag behind repository history | `test_signal_cache_git_state_fingerprint_changes_with_commit_hash` | git-state fingerprint includes commit hashes + file-history stats | 6 | 2 | 3 | 36 | Mitigated |

## 2026-04-11 - Phase 2 TS Parity: BEM/EDS/MDS/PFS TypeScript validation

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| BEM | FP: TS bare catch flagged when handler performs typed re-throw | tree-sitter catch clause without type annotation classified as "bare" even when throw follows | Over-reporting on idiomatic TS error handling | Ground-truth TN fixture `bem_ts_tn` with typed re-throws | BEM already checks for re-throw actions; TS TN fixture validates | 5 | 3 | 3 | 45 | Mitigated |
| BEM | FN: TS catch with `console.error` only not detected | TS parser may not classify `console.error` as log action | Under-reporting of swallowed exceptions | Ground-truth TP fixture `bem_ts_tp` with console.error handlers | ts_parser extracts `log` action for console.error; validated | 4 | 2 | 3 | 24 | Mitigated |
| EDS | FP: Simple TS function with JSDoc flagged as unexplained | JSDoc detection in tree-sitter might miss block comments | Over-reporting on documented functions | Ground-truth TN fixture `eds_ts_tn` with JSDoc | ts_parser detects `/** */` comments as docstrings; validated | 5 | 2 | 3 | 30 | Mitigated |
| EDS | FN: Complex TS function without docs not detected | Complexity heuristic may under-count TS branching constructs | Under-reporting of hard-to-understand TS code | Ground-truth TP fixture `eds_ts_tp` with deep nesting | ts_parser counts if/for/while/switch/ternary; validated | 4 | 3 | 3 | 36 | Mitigated |
| MDS | FP: Distinct TS functions flagged as duplicates | n-gram overlap on small functions with common patterns | Over-reporting of non-duplicate code | Ground-truth TN fixture `mds_ts_tn` with distinct functions | MDS Jaccard threshold + LOC bucket + name-diversity filters | 5 | 3 | 3 | 45 | Mitigated |
| MDS | FN: Copy-paste TS functions not detected | ts_parser n-gram normalization differs from Python ast | Under-reporting of cloned TS code | Ground-truth TP fixture `mds_ts_tp` + mutation benchmark | ts_parser `_compute_ts_ast_ngrams` produces comparable n-grams; validated | 4 | 2 | 3 | 24 | Mitigated |
| PFS | FP: Consistent TS error handling flagged as fragmented | Fingerprint normalization may not fully equalize TS patterns | Over-reporting on consistent codebases | Ground-truth TN fixture `pfs_ts_tn` with uniform AppError pattern | PFS `_normalize_fingerprint` removes async/sync; consistent patterns pass | 5 | 2 | 3 | 30 | Mitigated |
| PFS | FN: Fragmented TS error patterns not detected | TS error-handling fingerprints may not distinguish patterns | Under-reporting of inconsistent error handling | Ground-truth TP fixture `pfs_ts_tp` with 3 different patterns | ts_parser extracts distinct handler fingerprints; validated | 4 | 3 | 3 | 36 | Mitigated |

## 2026-04-11 - Issue #210: NBV TS/JS ensure_* upsert FP reduction

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| NBV | FP: TypeScript/JavaScript `ensure_*` upsert helpers flagged as contract violation | TS path reused Python `ensure_*` contract (`throw` required) and ignored value-returning guarantee semantics | Large FP volume on TS/JS repos and reduced NBV trust | Added TS regression tests in `tests/test_naming_contract_violation.py` and TN ground-truth fixture `nbv_ts_ensure_upsert_tn` | Added language-aware TS/JS ensure contract: satisfy when function has `throw` OR a value-returning `return` path | 7 | 7 | 3 | 147 | Mitigated |
| NBV | FN: TS/JS `ensure_*` may be over-accepted by relaxed rule | Relaxation could accept weak functions that return arbitrary values without true guarantee | Potential under-reporting in edge cases | Negative control regression: `ensureReady` with bare `return;` remains flagged | Contract only accepts value-returning `return` or `throw`; bare return is explicitly not sufficient | 4 | 3 | 4 | 48 | Mitigated |

## 2026-04-11 - Issue #209: NBV TypeScript async bool-wrapper FP reduction

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| NBV | FP: is_*/has_* with PromiseLike<boolean>/Observable<boolean> flagged as non-bool | `_ts_has_bool_return` only accepted literal `boolean` and did not unwrap generic wrappers | High FP volume on TypeScript repos and reduced trust in NBV | Added regression tests in `tests/test_naming_contract_violation.py` and helper coverage in `tests/test_nbv_helpers_coverage.py`; ground-truth TN fixture `nbv_ts_async_bool_tn` | Added `_is_bool_like_return_type()` with recursive unwrapping of `Promise`, `PromiseLike`, and `Observable`; reused in Python/TS bool-check path | 7 | 6 | 3 | 126 | Mitigated |
| NBV | FN: permissive wrapper handling may incorrectly accept non-bool wrapped types | Generic unwrapping logic could classify wrappers too broadly | Real naming violations might be missed for non-bool payloads | Negative control test `Promise<string>` remains a finding | Unwrapping is strict and only accepts terminal `bool`/`builtins.bool`/`boolean` | 4 | 2 | 4 | 32 | Mitigated |

## 2026-04-13 - ADR-047–051: Actionability Hardening (MAZ/EDS/PFS/AVS/CCC)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| MAZ | FP: intentionally public A2A agent card endpoint flagged as CRITICAL missing-auth | CRITICAL severity may alarm users whose agent card URL is deliberately unauthenticated | False alarm for A2A/multi-agent repos; trust erosion | `maz_tn_cli_serving_path` and A2A-aware fixtures | Fix text explicitly notes A2A/public exemption; users can label via `drift:ignore` | 5 | 3 | 3 | 45 | Mitigated |
| MAZ | FN: score bump 0.7→0.85 does not change detection logic; no new FN scenarios | Threshold change is output-only | No new FN risk | Existing MAZ TP/TN fixtures | N/A | 1 | 1 | 1 | 1 | N/A |
| EDS | FP: private function that is genuinely complex but not defect-correlated now requires 0.45 threshold | Raises bar for private helpers — legitimate complex private code less likely to appear | Under-reporting for complex-but-valid private helpers | Ground-truth fixtures include private complex function TPs | Default 0.45 is conservative; `defect_correlated` override at 0.30 preserves coverage for risky code | 4 | 3 | 4 | 48 | Open (bounded) |
| EDS | FN: defect_correlated flag depends on `defect_correlated_commits` in FileHistory; absent outside git context | Non-git repos always have `defect_correlated = False`, no threshold reduction | Private helpers in non-git repos may be under-filtered | `history is not None and history.defect_correlated_commits > 0` guard | Accept: non-git repos have no commit context by design; threshold falls back to default | 3 | 3 | 5 | 45 | Accepted |
| PFS | FP: canonical snippet exposes sensitive code in on-screen output | Canonical snippet (~8 lines) appended to Finding shown in Rich terminal output | Potential credential/proprietary-code exposure in terminal | Snippet limited to 400 chars via `[:400]`; `show_code=False` in security section | No secret scanning on snippets; recommend combining with `drift:ignore` for sensitive exemplars | 4 | 2 | 5 | 40 | Open (bounded) |
| PFS | FN: canonical_ratio < 0.10 severity downgrade may suppress a valid high-severity fragmentation | If only few instances exist of dominant pattern, severity is lowered to MEDIUM | Real fragmentation in small module may be missed at original severity | PFS TP fixtures include small-module fragmentation cases | Downgrade is two-step bounded (HIGH→MED never jumps to LOW in single step); metadata retains raw frag_score | 4 | 2 | 4 | 32 | Open (bounded) |
| AVS | FP: module that was historically stable but recently became active bypasses churn guard | `change_frequency_30d` reflects last 30 days only; new activity not yet reflected | Recent high-blast-radius change velocity not flagged | AVS TP fixtures + precision/recall run | 30-day rolling window is current convention across all signals; consistent with TVS behavior | 3 | 3 | 5 | 45 | Accepted |
| AVS | FN: churn guard drops finding for a high-impact but stable module (churn ≤ 1.0, br ≤ 50) | Dual condition means a module with blast_radius=50 and 1 change/week is skipped | Low-churn high-blast-radius module not flagged | AVS threshold: br > 50 OR churn > 1.0 is required to escape guard | Guard only applies when BOTH conditions hold; br > 50 alone escapes the guard | 4 | 2 | 4 | 32 | Accepted |
| CCC | FP: commit messages expose internal implementation detail or sensitive info in on-screen output | `commit_messages` metadata (3 × 60-char truncated message strings) visible in JSON/Rich output | Internal commit message leakage if running on proprietary repo | Messages truncated at 60 chars; only top-3 samples | Accept: commit messages already visible in git log; no additional exposure beyond existing git ingestion | 2 | 2 | 5 | 20 | Accepted |
| CCC | FN: commit message truncation at 60 chars may hide actionable context string | Long messages with key co-change reason after 60 chars are cut | Less informative context for accidental-coupling diagnosis | 60 chars typically covers the conventional commit type+scope prefix | Accept: 60 chars captures `feat(scope): ` style; 3-sample window provides adequate context | 2 | 3 | 5 | 30 | Accepted |

## 2026-04-11 - ADR-041: PHR Runtime Import Attribute Validation

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| PHR | FP: version-mismatch → attribute existed in older version | Module installed but different version than project expects; `hasattr` returns False for removed/renamed attribute | False phantom for version-transitional APIs | `phr_runtime_valid_attr_tn` fixture + metadata `runtime_validated: true` | Confidence metadata; users can suppress via `drift:ignore`; opt-in only | 4 | 3 | 5 | 60 | Open (bounded) |
| PHR | FP: import timeout → attribute check skipped, phantom stands | Slow module init exceeds 5s daemon thread timeout | Existing Phase B finding stays unvalidated (no false-positive added, but no FP removed) | Timeout logged; metadata shows `runtime_validated: false` | Configurable timeout via daemon thread; sys.modules fast path for cached imports | 3 | 2 | 3 | 18 | Mitigated |
| PHR | FN: module raises on import → attribute not checkable | Third-party package has broken `__init__.py` or missing dependency | Real missing attribute not detected via runtime path | N/A (inherent limitation of import-based validation) | Graceful fallback: import failure returns None, Phase B finding unchanged | 3 | 2 | 5 | 30 | Accepted |
| PHR | FN: platform-conditional attribute absent on analysis host | Attribute exists on Linux but not Windows (or vice versa) | Under-reporting on cross-platform projects when analysis runs on different OS | N/A (inherent environment dependency) | Accept: same limitation as Phase B env-dependency; metadata `confidence: env_dependent` | 3 | 3 | 7 | 63 | Accepted |

## 2026-04-10 - ADR-040: PHR Third-Party Import Resolver

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| PHR | FP: package in CI but not in local venv → false phantom | `find_spec` depends on environment; dev/CI mismatch | False finding for correctly-imported packages | `phr_stdlib_import_tn` + `phr_optional_dep_tn` fixtures | metadata `confidence: env_dependent`; users can suppress via `drift:ignore` | 4 | 3 | 6 | 72 | Open (bounded) |
| PHR | FP: conditional import not recognized as guarded | AST walk misidentifies try/except block structure | False phantom for optional dependency imports | `phr_optional_dep_tn` + `phr_module_not_found_error_tn` fixtures | `_is_in_try_except_import_error` checks ImportError + ModuleNotFoundError + bare except | 5 | 2 | 3 | 30 | Mitigated |
| PHR | FN: dynamically imported module not detected | `importlib.import_module(var)` not statically resolvable | Missed phantom for dynamic plugin loading | N/A (inherent static analysis limitation) | Accept: scope is static AST-based; dynamic imports require runtime analysis | 3 | 4 | 8 | 96 | Accepted |
| PHR | FN: installed package with missing attribute not detected | `find_spec` checks module existence only, not API surface | Under-reporting for version-mismatched dependencies | N/A (Phase C: runtime validation planned) | Accept: Phase B scope is module existence; attribute validation deferred to Phase C (ADR-041) | 4 | 3 | 8 | 96 | Accepted |

## 2026-06-14 - ADR-039: Activate MAZ/PHR/HSC/ISD/FOE for Scoring

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| MAZ | FP: localhost/dev-tool handlers flagged for missing auth | Handler serves local development traffic only; MAZ fallback sees decorated handler without auth markers | Triage noise in CLI-tool/dev-server repositories | `maz_tn_cli_serving_path` fixture + existing MAZ precision suite | Low weight (0.02); existing CLI-path/dev-path suppression; localhost false-positive fence already hardened | 4 | 3 | 3 | 36 | Mitigated |
| MAZ | FN: real unauthenticated endpoint ignored due conservative fallback | Expanded auth-parameter matching may suppress true missing-auth findings | Under-reporting for unusual parameter naming conventions | Existing MAZ TP fixtures + precision/recall run | Keep auth-marker set narrow; fallback-scoped only; existing decorator/allowlist guards retained | 5 | 3 | 5 | 75 | Open (bounded) |
| ISD | FP: debug/test configuration files flagged despite being non-production | ISD checks all non-test Python files; local-dev settings with `DEBUG=True` may be intentional | Developer-facing noise in projects with explicit dev configs | `isd_ignore_directive_tn` fixture; `drift:ignore-security` directive | `is_test_file()` gate + `drift:ignore-security` directive; low weight (0.01) bounds impact | 4 | 4 | 3 | 48 | Mitigated |
| ISD | FN: insecure defaults in non-Python config formats missed | ISD is AST-only Python; YAML/JSON/TOML configs not scanned | Under-reporting for polyglot projects | N/A (scope limitation) | Accept: Phase 1 scope is Python-only; future extension possible | 3 | 5 | 7 | 105 | Accepted |
| HSC | FP: template/placeholder values trigger secret detection | Generic variable names with template-like values may match entropy heuristics | Triage noise in scaffold/template repositories | Existing `hsc_placeholder_tn` fixture + env-template suppression | `_is_safe_value` checks, known-prefix ordering, env-template suppression already active | 4 | 3 | 3 | 36 | Mitigated |
| HSC | FN: obfuscated or encoded secrets missed | Base64-encoded or split credentials bypass literal matching | Under-reporting for sophisticated secret embedding | N/A (inherent static analysis limitation) | Accept: HSC targets plain-text literals; obfuscated secrets require runtime/entropy analysis | 5 | 3 | 7 | 105 | Accepted |
| PHR | FP: third-party module import flagged as phantom | PHR only resolves project-internal modules; valid third-party imports not in project tree | False phantom reference in stdlib/vendor import contexts | Existing `phr_builtin_tn` + `phr_star_import_tn` fixtures | Known-module allowlist, `__all__` resolution, star-import handling; weight 0.02 bounds impact | 4 | 3 | 3 | 36 | Mitigated |
| FOE | FP: barrel files flagged as high fan-out despite being re-export modules | `__init__.py` with many re-exports triggers import count threshold | Low-value finding for package index files | `foe_barrel_file_tn` fixture | Barrel-file suppression in FOE signal; very low weight (0.005) bounds score impact | 3 | 3 | 3 | 27 | Mitigated |
| ALL | Score inflation from 5 newly-scoring signals | Combined weight addition (+0.065) may inflate composite scores for repos triggering multiple signals | Score comparability break vs. pre-activation baselines | Baseline diff after activation; `drift_diff` verification | Conservative weights (total +0.065 out of ~1.0); gradual activation allows recalibration | 5 | 3 | 4 | 60 | Open (bounded) |

## 2026-04-10 - TypeScript signal expansion: TSB + NCV TS checks

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| TSB | FP: intentional TypeScript escape hatch flagged as architectural bypass | `as any`, non-null assertions, or `@ts-ignore` used intentionally in migration or framework boundary code | Extra noise in TS-heavy repositories and lower prioritization trust | Dedicated fixtures in `tests/fixtures/typescript/type_safety_bypass/` and `tests/test_type_safety_bypass.py` | Keep severity bounded and rely on focused evidence in metadata for triage | 5 | 4 | 4 | 80 | Open (bounded) |
| TSB | FN: bypass pattern missed in nested or syntax-variant cast forms | AST shape variance across TS/TSX files or parser edge cases | Real type-safety erosion is under-reported | Parser and signal tests across clean/moderate/severe fixtures | Keep detection logic AST-based and add regression fixtures for new syntax variants | 7 | 3 | 4 | 84 | Open (bounded) |
| NCV | FP: mixed naming conventions reported in codebases with deliberate multi-style boundaries | Cross-team or generated-code coexistence intentionally mixes interface/generic conventions | Increased low-severity findings and possible alert fatigue | `tests/test_ts_naming_consistency.py` + fixture matrix | Low severity, convention ratio thresholds, and file-level context in findings | 4 | 5 | 4 | 80 | Mitigated |

## 2026-04-13 - ADR-036/037/038: AVS/DIA/MDS FP-Reduction

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| AVS | FN: models/ cross-layer import no longer detected | `models` moved to `_OMNILAYER_DIRS` — genuine layer violations from models/ are suppressed | Under-reporting for projects using models/ as a strict DB layer | `avs_models_omnilayer_tn` fixture + precision/recall run | Configurable `omnilayer_dirs` allows reversal; `models` is cross-cutting in >80% of observed repos | 4 | 2 | 4 | 32 | Open (bounded) |
| AVS | FP: custom omnilayer_dirs config too broad | User adds too many dirs → most imports become omnilayer → signal degrades | AVS produces very few findings → loss of signal value | Config validation at load time (empty default) | Conservative default (empty list); documentation explains risk | 3 | 2 | 5 | 30 | Mitigated |
| DIA | FN: custom auxiliary dir hides real undocumented source dir | `extra_auxiliary_dirs` config skips a dir that should be documented | Genuine documentation gap not reported | Default is empty (no dirs skipped by default) | Only user-configured dirs are skipped; no default change to _AUXILIARY_DIRS | 3 | 2 | 5 | 30 | Mitigated |
| MDS | FN: protocol-method skip suppresses real duplication | Two classes implement same protocol method with genuinely duplicated non-trivial logic | Real near-duplication in protocol implementations not detected | Protocol-method set is narrow (20 names); only same-name different-class skipped | Only exact bare-name match + different class qualifies; body similarity not checked for skip | 4 | 2 | 5 | 40 | Open (bounded) |
| MDS | FN: thin-wrapper gate suppresses refactoring opportunity | Wrapper function with LOC ≤ 5 that adds real behavior flagged as thin wrapper | Missed consolidation opportunity | `_is_thin_wrapper` checks for exactly 1 Call node in AST | Single-call heuristic is conservative; complex wrappers with conditions still detected | 3 | 2 | 4 | 24 | Mitigated |
| MDS | FP: name-token similarity inflates score for same-named functions | Two unrelated functions with similar names get bonus from name similarity | Unrelated functions flagged as near-duplicates | Name component is only 10% of hybrid formula | 10% weight limits maximum name-only inflation to 0.10 total similarity | 3 | 2 | 3 | 18 | Mitigated |

## 2026-04-12 - ADR-035: PHR per-repository calibration

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| PHR | FN: relevant phantom reference finding down-ranked too strongly | Repository feedback history contains biased/incorrect "false positive" labels for structurally valid PHR cases | Under-prioritized remediation for real reference drift in calibrated repository | `tests/test_calibration.py`, `tests/test_phantom_reference.py`, precision/recall run | Bound dampening factors, confidence weighting, and default fallback when calibration confidence is low | 7 | 4 | 4 | 112 | Open (bounded) |
| PHR | FP: calibration not applied although repository has repeat FP pattern | Missing or stale `data/negative-patterns/` calibration snapshot, repo fingerprint mismatch, or cache invalidation | Repeated noisy PHR findings persist and reduce actionability | CLI calibration tests + snapshot persistence checks | Explicit calibrate/feedback commands, deterministic repo fingerprinting, lazy reload on changed calibration file | 5 | 3 | 4 | 60 | Mitigated |
| PHR | Integrity risk: malformed calibration payload influences scoring path | External/manual edits to calibration JSON introduce invalid schema/value ranges | Runtime errors or unstable score adjustments | `tests/test_task_spec.py`, schema validation in calibration loading path | Strict validation + safe defaults on parse/validation failure; ignore invalid entries | 6 | 2 | 3 | 36 | Mitigated |

## 2026-04-07 - PFS FTA v1: RETURN_PATTERN extraction (MCS-1 recall fix)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| PFS | FN: return-strategy diversity not detected | No `RETURN_PATTERN` enum value; no extraction path in `_process_function()` | pfs_002 recall = 0; overall PFS recall = 0.5 | `test_return_strategy_mutation_benchmark_scenario`, `test_return_pattern_two_variants_detected` | `PatternCategory.RETURN_PATTERN` + `_fingerprint_return_strategy()` in ast_parser.py | 7 | 8 | 2 | 112 | **Mitigated** |
| PFS | FP: intentional return-strategy overloading flagged | Module deliberately offers get/get_or_raise/get_result patterns | Low-value finding on API-convenience modules | `test_return_pattern_single_variant_no_finding`; ≥2 strategies threshold | Per-function ≥2-strategy gate; PFS aggregates per-module (canonical dominance dampens) | 3 | 3 | 7 | 63 | Accepted |
| PFS | FN: dynamic/callback returns not classifiable | Return strategy determined at runtime via callback or config | Under-reporting for indirection-heavy code | N/A — static analysis limitation | Accept: AST-level analysis cannot resolve runtime dispatch | 2 | 4 | 8 | 64 | Accepted |
| PFS | FP: nested function returns leak into outer fingerprint | `_fingerprint_return_strategy` walks into nested defs | Inflated strategy set for outer function | `test_return_strategy_ignores_nested_functions` | Queue-based walk skips `FunctionDef`/`AsyncFunctionDef`/`ClassDef` children | 5 | 2 | 2 | 20 | **Mitigated** |

## 2026-04-07 - AVS FTA v1: co-change precision failure (3 primary MCS) — MITIGATED 2026-04-07

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| AVS | FP/Disputed: same-package sibling files flagged as hidden coupling | `_check_co_change` has no same-directory guard; sibling signal files co-change naturally via shared registry without import edge | 7/10 Disputed in drift_self sample; precision_strict 0.3 for avs_co_change | MCS-1 operationell test: `test_co_change_same_directory_suppressed` — PASSING | Same-directory guard via `PurePosixPath.parent` comparison with root-level exception (`!= "."`) in `_check_co_change` | 6 | 2 | 2 | 24 | **Mitigated** |
| AVS | FP/Disputed: test↔source pairs flagged as hidden coupling | `known_files` uses unfiltered `parse_results`; graph uses `filtered_prs` → `has_edge` always False for test-source pairs | Test-source co-evolution misreported as architectural violation (e.g. `config.py ↔ test_config.py` Disputed) | MCS-2 operationell test: `test_co_change_test_source_pair_suppressed` — PASSING | `known` now built from `filtered_prs` (consistent with graph): `known = {pr.file_path.as_posix() for pr in filtered_prs}` | 5 | 1 | 2 | 10 | **Mitigated** |
| AVS | FP/Disputed: bulk-commit sweep inflates co_change_count without semantic coupling | Release/FMEA-sweep commits touch all signal files simultaneously; `CoChangePair.confidence` counts all commits equally regardless of commit size | Inflated confidence scores for signal-file pairs that co-change only in sweep commits | MCS-3 operationell test: `test_co_change_bulk_commits_discounted` — PASSING | Commit-size discount `weight = 1.0 / max(1, len(files) - 1)` in `build_co_change_pairs`; hard >20 cut retained | 5 | 2 | 3 | 30 | **Mitigated** |
| AVS | Latent FP: `models.py` assigned to layer 2, imported cross-cuttingly | `_DEFAULT_LAYERS` maps `models` → 2 (DB layer); drift-style DTO/config models are cross-cutting and should be omnilayer | Potential `avs_upward_import` FPs in CLI-architecture repos (not yet observed in ground truth) | No Disputed avs_upward_import in current sample; latent risk | Add `models` to `_OMNILAYER_DIRS` or add default `allowed_cross_layer` pattern for `**/models.py` | 4 | 2 | 6 | 48 | Open (latent) |
| AVS | FN: same-directory guard suppresses cross-boundary findings in flat-root repos | After MCS-1 fix, repos with all modules in root dir will have same-directory pairs suppressed | Real hidden coupling in flat repos not reported | FN-guard test: `test_co_change_root_level_not_suppressed` — PASSING | Guard only applies when parent dir != "." (root-level files pass through) | 4 | 2 | 6 | 48 | Accepted |
| AVS | FN: test-file filter on `known` suppresses test-orchestrated cross-module coupling | After MCS-2 fix, test files are no longer candidates for co-change pairs | Rarely relevant (test files rarely cause architectural coupling concerns) | N/A — test files already excluded from import-graph analysis | Accept: test-source co-change is expected behavior, not a finding target for AVS | 2 | 1 | 8 | 16 | Accepted |

## 2026-04-07 - DIA FTA v2: deep false-positive reduction (6 MCS)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| DIA | FP: language keyword compounds (`try/except`, `match/case`) extracted as dir refs | `_PROSE_DIR_RE` matches `word/` without checking if next char continues the token | Python syntax patterns produce phantom-dir findings in ADR codespans | P5 regression tests: `test_try_except_not_extracted`, `test_match_case_not_extracted` | P5: Negative lookahead `(?!\w)` on `_PROSE_DIR_RE` — only matches when slash is followed by non-word char or EOL | 5 | 6 | 2 | 60 |
| DIA | FP: prose slash-separator (`parent/tree`) extracted as dir ref | Slash used as concept separator in prose, not path separator | Non-directory tokens produce phantom-dir findings | P5 regression test: `test_parent_tree_not_extracted` | P5: `(?!\w)` negative lookahead blocks `word/word` continuations | 4 | 5 | 2 | 40 |
| DIA | FP: multi-segment path decomposes into intermediate refs | `src/drift/output/csv_output.py` → `output/` extracted as separate ref | Intermediate path segments produce phantom-dir findings | P5 regression tests: `test_multisegment_path_extracts_terminal_only`, `test_multisegment_trailing_slash_extracts_last` | P5: `(?!\w)` ensures only terminal segment (before whitespace/EOL) is extracted | 5 | 5 | 2 | 50 |
| DIA | FP: GitHub URL owner/repo in plain text | `mick-gsk/drift` in non-link text passes regex; URL path segments extracted | GitHub handles produce phantom-dir findings | P3 + P5 regression tests: `test_github_url_not_extracted` | P3: `_strip_urls()` removes URLs before regex; P5: `(?!\w)` blocks `mick-gsk/d` | 4 | 4 | 2 | 32 |
| DIA | FP: dotfile path produces phantom ref | `.drift-cache/history.json` → `drift-cache/` extracted → existence check fails | Dotfile-prefixed dirs not recognized by `_ref_exists_in_repo()` | P6 regression tests: `test_dotfile_prefix_found`, `test_dotfile_must_be_dir` | P6: Check `repo_path / f".{ref}"` in `_ref_exists_in_repo()`; P5 also blocks `drift-cache/h` | 3 | 3 | 2 | 18 |
| DIA | FP: auxiliary dirs (`tests/`, `scripts/`, `benchmarks/`) flagged as undocumented | `_source_directories()` includes all dirs with .py files; conventional dirs rarely in README | Low-value findings for universally understood directories | P1 regression tests: `test_tests_dir_not_flagged`, `test_nonaux_dir_still_flagged` | P1: `_AUXILIARY_DIRS` frozenset excludes conventional project directory names | 3 | 8 | 2 | 48 |
| DIA | FN: P5 lookahead may miss intermediate path segments | Only terminal segment of multi-segment path extracted (e.g. `src/drift/` → only `drift`) | Intermediate segments not checked for existence | Mutation benchmark DIA recall 3/3 = 100% | Terminal segment is always the meaningful claim target; intermediate segments rarely the intent | 3 | 3 | 5 | 45 |
| DIA | FN: P1 auxiliary set may exclude non-standard dir with conventional name | Project-specific dir named `test` or `scripts` would be excluded | Under-reporting if such a dir has genuine documentation gap | `test_nonaux_dir_still_flagged` verifies non-aux dirs still reported | Only well-known convention names in set; `artifacts`/`work_artifacts` added 2026-04-08 | 3 | 2 | 5 | 30 |
| DIA | FP: ADR example refs extracted via `trust_codespans=True` | ADR text about DIA uses illustrative path refs in inline codespans | Illustrative examples produce phantom-dir findings on own repo | `test_fenced_block_services_not_extracted` regression test | Move illustrative examples to fenced code blocks (DIA skips `block_code` tokens) | 2 | 2 | 2 | 8 |
| DIA | FP: `work_artifacts/` flagged as undocumented source dir | Working/artifact dirs with ad-hoc .py scripts not in `_AUXILIARY_DIRS` | Low-value finding for non-architectural scratch directory | `test_artifacts_dir_not_flagged` regression test | P1: Extended `_AUXILIARY_DIRS` with `artifacts`, `work_artifacts` | 2 | 3 | 2 | 12 |

## 2026-04-07 - DIA FTA v1: initial false-positive reduction (3 cut sets)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| DIA | FP: codespan directory refs extracted without structure context | `_walk_tokens()` set `allow_without_context=True` for all `codespan` tokens regardless of surrounding prose | REST paths, inline code examples, foreign-repo refs emitted as phantom-dir findings | New CS-1 regression tests (no-keyword codespan → no finding, keyword present → finding kept) | Sibling-context keyword gate: collect text-children from parent paragraph/heading, only trust codespans when structure keywords present; `trust_codespans=True` for ADR files | 5 | 7 | 3 | 105 |
| DIA | FN: codespan context gate may suppress legit structure refs in keyword-free prose | Paragraphs without structure keywords (e.g. "use `services/` for the logic") are no longer extracted | Potential under-reporting of phantom dirs in informal prose | Ground-truth regression for `dia_adr_mismatch_tp` + keyword set includes "architecture", "component" | Conservative keyword list covering common README section headings; running context propagation across siblings (heading → list) | 4 | 3 | 5 | 60 |
| DIA | FP: phantom dir finding when directory exists under src/ or lib/ prefix | `_source_directories()` only records `parts[0]`; `src/services/` yields `src` not `services` | README ref `services/` flagged as missing despite `src/services/` existing | New CS-2 regression tests (src/services/ exists → no finding; tests/services/ → finding stays) | Container-prefix existence check: `_ref_exists_in_repo()` checks direct path + curated prefix set (`src`, `lib`, `app`, `pkg`, `packages`, `libs`, `internal`) | 5 | 4 | 3 | 60 |
| DIA | FN: container-prefix check may mask phantom dirs existing only under src/ | If README claims top-level `services/` but only `src/services/` exists (unrelated context) | Phantom dir not reported | Regression test verifies `tests/services/` (non-container) still triggers finding | Curated prefix set excludes `tests`, `benchmarks`, `docs` etc.; only production-code containers | 4 | 2 | 5 | 40 |
| DIA | FP: superseded/deprecated ADR references flagged as phantom dirs | `_scan_adr_files()` treated all ADRs identically regardless of lifecycle status | Pre-refactoring or rejected ADRs produce stale-reference findings | New CS-3 regression tests (superseded → skip, accepted → finding, no status → finding) | Parse YAML frontmatter + MADR freetext status; skip `superseded`/`deprecated`/`rejected` | 5 | 4 | 3 | 60 |
| DIA | FN: skipped ADR may still reference a real phantom dir | Superseded ADR with coincidentally valid phantom-dir ref is not scanned | Under-reporting for edge case | N/A (superseded ADRs are not authoritative per policy) | Only skip 3 statuses; `proposed`/`accepted`/no-status continue to be scanned | 3 | 2 | 6 | 36 |

## 2026-04-07 - MAZ/ISD/HSC wave-2 calibration

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| MAZ | FN: auth-injected endpoints still flagged due narrow parameter normalization | Fallback previously matched only exact parameter markers and missed camelCase/composed auth-context names | Reduced precision and noisy missing-auth findings in decorator-only fallback contexts | New MAZ regressions for camelCase and access-token parameter variants | Normalize snake/camel/non-alnum parameter names and apply conservative auth-context regex patterns in fallback-only path | 6 | 4 | 4 | 96 |
| MAZ | FN: broad auth-parameter patterns may hide real unauthenticated routes | Expanded auth-like parameter matching can classify rare business params as auth context | Potential under-reporting in edge naming conventions | Control regression keeps plain path params reportable | Keep patterns conservative and fallback-scoped; retain existing auth-decorator/allowlist guards | 5 | 3 | 6 | 90 |
| ISD | FN: insecure defaults can be accidentally suppressed by loose ignore substring | Header check accepted any line containing `drift:ignore-security` substring | Entire-file skip in unintended comment variants, reducing signal trust | New regressions for valid directive vs similar invalid marker | Require explicit comment directive with word boundary in first header lines | 6 | 3 | 4 | 72 |
| HSC | FN: wrapped credential literals (for example `Bearer sk-...`) bypass known-prefix detection | Prefix detection expected token prefix at string start only | Missed high-confidence secret findings in auth-header style assignments | New regression for Bearer-wrapped prefix literal | Normalize common wrappers (`Bearer `, `token `) before known-prefix checks | 7 | 4 | 4 | 112 |

## 2026-04-06 - MAZ/ISD/HSC scoring-readiness calibration

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| MAZ | FP: decorator fallback flags routes that already carry injected auth context | Fallback previously treated all decorated handlers without auth decorators as unauthenticated, even when parameters indicated injected identity context | Reduced triage trust and lower actionability for missing-auth findings | New fallback regressions for auth-like and non-auth-like parameters | Skip fallback findings when conservative auth-like parameter markers are present; keep path-parameter control test | 6 | 4 | 4 | 96 |
| MAZ | FN: auth-like parameter suppression can hide real unauthenticated routes | Endpoint parameter names may overlap with auth-like marker tokens in edge naming conventions | Some true missing-auth findings may be delayed | Control regression keeps `user_id` path parameter reportable | Keep marker set conservative and scoped to fallback-only path; preserve allowlist/dev-path/auth-decorator checks | 5 | 3 | 6 | 90 |
| ISD | FP-severity: localhost `verify=False` is ranked too harshly for local-dev context | Previous rule emitted full `insecure_ssl_verify` severity without distinguishing loopback targets | Lower perceived signal credibility for local testing scenarios | New regression for localhost downgrade path | Keep finding visible but downgrade to `insecure_ssl_verify_localhost` with lower score for loopback/localhost URLs | 5 | 5 | 4 | 100 |
| ISD | FN-severity: non-loopback misuse could be downgraded if target classification is too broad | Loopback detection heuristic may overmatch unusual host strings | Real TLS verification misuse may be under-prioritized | Precision/recall suite plus localhost-specific regression | Restrict downgrade to first-argument literal HTTP(S) URLs with strict loopback host matching | 6 | 2 | 5 | 60 |
| HSC | FN: known API-token prefixes in generic variable names are missed | Previous detection depended heavily on secret-shaped variable names before high-confidence literal cues | High-confidence secret leaks remained undetected in generic config names | New regressions for generic variable and keyword-argument cases | Evaluate known-prefix literals before name-shaped fallback to emit `hardcoded_api_token` deterministically | 8 | 4 | 4 | 128 |
| HSC | FP: known-prefix expansion may flag benign placeholder-like values | Prefix-first detection increases sensitivity when generic names carry token-like literals | Potential triage noise in synthetic/template contexts | Existing TN fixtures + new template confounder in ground truth | Keep `_is_safe_value` checks and minimum literal length gate; retain TN fixture coverage in precision/recall suite | 5 | 3 | 6 | 90 |

## 2026-04-06 - MDS precision-first scoring-readiness calibration

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| MDS | FP: semantic-only and intentional variant pairs inflate scoring noise | Semantic-only matching accepted same-file conceptual similarity; sync/async intentional variants looked like duplicates; hybrid threshold was looser than AST threshold | Reduced confidence in MDS as scoring input and lower actionability of findings | Live-scan triage + targeted edge-case regression tests | Precision-first hybrid threshold, sync/async variant suppression, stricter semantic gate, same-file semantic suppression | 6 | 5 | 4 | 120 |
| MDS | FN: true duplicates in sync/async ecosystems may be suppressed | New suppression treats same-name sync/async path variants as intentional by default | Potential under-reporting of some real copy-paste drift patterns | Control regression keeps non-variant exact duplicates detectable | Conservative path-token gating and regression coverage for non-variant duplicate detection | 4 | 3 | 6 | 72 |

## 2026-04-06 - TPD unexpected source-segment exception hardening (Issue #184)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| TPD | FN: signal execution aborts and gets skipped | `ast.get_source_segment` can raise unexpected exception types in edge AST/source-position scenarios, and the previous guard covered only selected exception classes | Missing TPD findings in export-context/cross-signal analysis and reduced trust in context completeness | Field-test report + targeted runtime-exception regression | Broaden source-segment exception guard to fail-safe behavior and add per-file analyze guards for parse/AST visit | 8 | 3 | 4 | 96 |
| TPD | FN: single malformed file can suppress module-level coverage | Unexpected AST parse/visit errors may occur on isolated files | Reduced per-module signal coverage (partial under-reporting) | New regression plus debug logging path for skipped files | Skip only failing file, continue analysis for remaining module files, keep deterministic thresholds | 5 | 3 | 5 | 75 |

## 2026-04-06 - HSC YAML env-template variable-name false positives (Issue #181)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| HSC | FP: multi-line YAML templates with `${ENV_VAR}` placeholders are flagged as hardcoded secrets | Secret-shaped variable names (`*_API_KEY`, `*_TOKEN`) trigger generic fallback although string literal is a configuration template referencing env injection | High-severity triage noise and reduced trust in HSC precision for framework/sample repos | Field report on microsoft/agent-framework + targeted HSC regressions | Suppress configuration-style multi-line literals containing env placeholders (`${...}`) before generic fallback detection while preserving known-prefix checks first | 6 | 5 | 4 | 120 |
| HSC | FN: credentials embedded in template-like literals could be under-reported | New suppression path could hide mixed literals that include both template markers and real credentials | Delayed remediation in rare misuse cases | Regression ensures known-prefix secrets are still emitted before suppression | Keep suppression narrow (multi-line + `${...}` + key/value template markers), preserve known-prefix detection ordering, monitor precision/recall deltas | 5 | 2 | 6 | 60 |

## 2026-04-06 - TPD ast.get_source_segment crash guard (Issue #180)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| TPD | FN: signal execution aborts with uncaught exception | `ast.get_source_segment` raises `IndexError`/`ValueError` when AST node position metadata references out-of-range lines | TPD findings are entirely absent for affected repositories | Deterministic field crash report + targeted regression on malformed assert node metadata | Wrap source-segment extraction in exception-safe fallback (`segment=None`) and continue counting | 8 | 4 | 4 | 128 |
| TPD | FN/precision drift risk on malformed nodes | Regex-based negative-assert fallback cannot run when source segment extraction fails | Individual assert polarity may rely only on AST heuristic in edge metadata cases | New regression validates graceful continuation without crash | Keep conservative AST polarity rules active and bypass only regex fallback for malformed nodes | 4 | 3 | 5 | 60 |

## 2026-04-06 - MDS numbered sample-step duplicate calibration (Issue #179)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| MDS | FP: numbered sample step directories are flagged as high-severity exact duplicates | Tutorial-step suppression required `step*` token and missed numbered step dirs such as `01_single_agent`/`02_multi_agent` | High-severity noise on pedagogical repos using numbered sample progression and reduced trust in MDS precision | Field test on microsoft/agent-framework + targeted MDS regressions for numbered sample dirs | Extend tutorial-step suppression to also match conservative numbered sample-step directory pattern (`^\d{1,3}[-_].+`) under tutorial/sample/example context | 6 | 5 | 4 | 120 |
| MDS | FN: harmful duplicates in numbered tutorial steps can be under-reported | Numbered-step suppression now excludes more educational sample directories from duplicate analysis | Rare actionable refactoring opportunities in tutorial samples may be missed | Regression keeps non-step sample duplicates detectable | Keep suppression gated by tutorial/sample/example path marker plus conservative numbered-step folder shape | 4 | 3 | 6 | 72 |

## 2026-04-06 - MDS tutorial-step sample duplicate calibration (Issue #177)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| MDS | FP: tutorial step samples are flagged as high-severity exact duplicates | Candidate collection treats intentional standalone tutorial-step helper copies as architectural drift | High-severity noise on pedagogical repositories and reduced trust in MDS precision | Field test on microsoft/agent-framework + targeted MDS regressions | Suppress MDS candidates in conservative tutorial-step sample path context (`tutorial/sample/example` + `step*`) | 6 | 6 | 4 | 144 |
| MDS | FN: harmful duplication in tutorial-step contexts can be under-reported | New path heuristic skips duplicate analysis for functions in tutorial step sample trees | Rare true refactoring opportunities in tutorial steps may not be surfaced | Regression keeps non-step sample duplicates detectable | Keep heuristic narrow to explicit step-marker directories and tutorial/sample/example path context | 4 | 3 | 6 | 72 |

## 2026-04-06 - DCA script-context false positives (Issue #176)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| DCA | FP: executable Python scripts are flagged for unused exports | DCA infers usage primarily from cross-file imports and treats script helpers as library exports | CI/utility scripts get noisy dead-code recommendations and DCA trust drops | Field test on microsoft/agent-framework + targeted DCA regression | Suppress export-based DCA evaluation for Python files in script-like path contexts (`.github/workflows`, `scripts`, `tools`, `bin`) | 6 | 5 | 4 | 120 |
| DCA | FN: true dead exports in script-like paths can be under-reported | Path-based script-context suppression bypasses report generation for those files | Some actionable cleanup candidates in script directories may be missed | Regression keeps non-script contexts unchanged | Keep suppression conservative and path-scoped to executable-context locations only | 4 | 3 | 6 | 72 |

## 2026-04-05 - HSC OpenTelemetry GenAI semconv false positives (Issue #175)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| HSC | FP: OpenTelemetry GenAI metric/attribute constants are flagged as hardcoded secrets | Variable-name heuristic matches `token` in telemetry symbols (`INPUT_TOKENS`), while literal values are semantic-convention keys (for example `gen_ai.usage.input_tokens`) | High-severity triage noise in observability modules and reduced confidence in HSC precision | Field test on microsoft/agent-framework + targeted HSC regressions | Suppress OpenTelemetry GenAI semantic-convention literals (`gen_ai.*`) before generic fallback detection while keeping known-prefix secret checks first | 6 | 6 | 4 | 144 |
| HSC | FN: real credentials could be under-reported if they resemble semconv literals | New semconv suppression could hide unusual dotted lowercase literals under secret-shaped variables | Rare credential leakage may be delayed | Regression verifies known-prefix secrets remain detectable before suppression | Keep suppression narrow to `gen_ai.<segment>.<segment...>` pattern, preserve high-confidence prefix detection ordering, monitor field deltas | 5 | 2 | 6 | 60 |

## 2026-04-05 - AVS/ECM/TPD Recall-Härtung auf Groß-Repositories (Issue #170)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| AVS | FN: interne Abhängigkeitskanten aus relativen Imports fehlen | Relative `ImportFrom`-Information war für Graph-Auflösung unterbestimmt; unverknüpfte Kanten wurden als extern behandelt | Upward/Cycle/Blast-Radius-Befunde bleiben aus trotz realer Kopplung | Neuer Regressionstest für relative Import-Kantenauflösung in AVS-Graph | Best-effort relative Kandidatenauflösung aus Quellpfad + Importmodul/Namen ergänzt | 7 | 5 | 4 | 140 |
| ECM | FN: Exception-Drift bleibt unentdeckt in sehr großen Repos | Starre Kandidatenbegrenzung (`ecm_max_files`) fokussiert zu stark auf kleines Hot-File-Subset | Module mit realer Contract-Drift werden nicht verglichen | Neuer Regressionstest für adaptive Limit-Berechnung | Adaptive Kandidatenobergrenze mit konfiguriertem Floor und skaliertem Cap (max 300) ergänzt | 6 | 5 | 4 | 120 |
| TPD | FN: 0 Findings trotz testlastigem Repo | Globale Exclude-Regeln können Testdateien vor Signalphase entfernen | TPD verliert seine gesamte Beobachtungsbasis | Neuer Regressionstest mit leerem ParseResult-Input und Repo-Fallback | Fallback-Testdatei-Discovery direkt aus Repo-Dateisystem ergänzt (nur wenn keine Test-Counter vorhanden) | 6 | 6 | 3 | 108 |

## 2026-04-05 - MAZ decorator fallback recall calibration (Issue #169)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| MAZ | FN: route handlers are missed when API endpoint ingestion emits no API_ENDPOINT patterns | MAZ relied exclusively on ingestion patterns and had no conservative fallback for decorator-defined route handlers | Missing-authorization gaps stay unreported in framework files where pattern extraction under-detects endpoints | Field report on transformers + targeted MAZ regression for patternless decorated routes | Add conservative decorator fallback (`route`/HTTP method decorators) only when no API_ENDPOINT pattern exists in file | 7 | 5 | 4 | 140 |
| MAZ | FP: non-endpoint decorated functions could be misclassified as API routes by fallback | Decorator names like `get`/`post` might appear in non-web utility contexts | Additional triage noise and reduced precision in edge repositories | New regression verifies auth-decorated routes are suppressed in fallback path | Keep fallback gated (only when no API patterns), use conservative decorator marker set, skip auth-decorated functions, keep allowlist and dev-path suppressions active | 5 | 3 | 5 | 75 |

## 2026-04-05 - BEM fallback-assignment recall + AVS src-root import resolution (Issue #168)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| BEM | FN: broad `except Exception` fallback assignments are missed | Error-handler fingerprint classified `except ...: flag = False` as generic `other`, while BEM swallowing ratio accepted only pass/log/print | Clear monoculture cases (for example optional dependency probes) are under-reported | Field report on `huggingface/transformers` + targeted parser/BEM regressions | Classify assignment handlers as `fallback_assign` and include in BEM swallowing actions | 7 | 6 | 4 | 168 |
| AVS | FN: internal imports in src-root repos are treated as external/unresolved | Import graph module lookup only matched exact file module path (`src.pkg.mod`) and missed import aliases without source-root prefix (`pkg.mod`) | Upward import and related AVS checks silently miss valid internal edges | Field report on `huggingface/transformers` + targeted AVS regression | Add module alias resolution for common source roots (`src`, `lib`, `python`) when building module-to-file mapping | 7 | 5 | 4 | 140 |

## 2026-04-05 - MAZ localhost CLI serving false positives (Issue #167)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| MAZ | FP: localhost CLI serving tool endpoints flagged as missing authorization | MAZ classified API endpoints by route/auth markers only and lacked deployment-context heuristics for local CLI serving modules (`cli/serving/*`) | 0% precision in this context, high-severity triage noise, and reduced trust in MAZ ranking | Field report on `huggingface/transformers` + targeted MAZ regressions for `cli/serving/server.py` | Suppress MAZ findings for CLI-local serving paths (`cli` + `serving/serve` path markers) while keeping standard endpoint checks elsewhere | 7 | 6 | 4 | 168 |
| MAZ | FN: true production auth gaps could be under-reported in CLI-marked serving modules | New path-based suppression may hide real externally exposed endpoints located under `cli/serving/*` | Delayed remediation for rare production deployments that reuse CLI serving path conventions | Regression test ensures serving paths without CLI marker are still flagged | Keep suppression narrow to combined markers (`cli` plus `serving/serve`), preserve non-CLI serving detection, and monitor precision/recall deltas from field reports | 6 | 2 | 6 | 72 |

## 2026-04-05 - HSC ML tokenizer constant false positives (Issue #166)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| HSC | FP: ML tokenizer metadata constants are flagged as hardcoded secrets | Variable-name heuristic matches `token` in NLP tokenizer terms (`pad_token`, `cls_token`, `tokenizer_class_name`, `chat_template`) without domain context | High-severity noise, poor precision on ML repositories, reduced trust in HSC prioritization | Field report on `huggingface/transformers` + targeted HSC regressions | Suppress tokenizer-context literals for known tokenizer symbol names and token markers/templates while preserving high-confidence prefix detection | 7 | 7 | 4 | 196 |
| HSC | FN: real credentials could be under-reported when assigned to tokenizer-shaped symbols | New tokenizer-context suppression can bypass generic fallback detection for misused tokenizer variable names | Rare secret leakage under tokenizer symbol names may be delayed | Regression keeps known-prefix detection active even on tokenizer symbols | Keep suppression narrow (known tokenizer symbols/patterns), run known-prefix checks before suppression, and monitor field precision/recall deltas | 5 | 2 | 6 | 60 |

## 2026-04-05 - NBV try_* attempt-semantics false positives (Issue #165)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| NBV | FP: `try_*` utility/comparison helpers are flagged as missing try/except | Prefix rule treated every `try_*` as exception-handling contract, ignoring common "attempt/check" semantics | Medium-severity noise and lower trust in NBV findings on helper-heavy repos | Field test on langchain (`try_neq_default`) + targeted regressions | Suppress `try_*` findings when function body shows comparison/checking semantics or when file path indicates utility/helper context | 6 | 6 | 4 | 144 |
| NBV | FN: genuine missing try/except in utility paths may be under-reported | New suppression allows utility context and comparison-like helpers to bypass try/except contract | Some real error-handling contract mismatches can receive lower visibility | Existing regressions keep non-utility/non-comparison `try_*` violations detectable | Keep suppression scoped to `try_*` only; preserve other naming contracts and default checks for non-matching contexts | 5 | 3 | 6 | 90 |

## 2026-04-05 - DIA bootstrap-repo README false positives

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| DIA | FP: Tiny bootstrap repositories are flagged with `No README found` | DIA treated missing README as actionable architectural drift even when the repository contains zero or one parsed Python file, or only `__init__.py` skeleton modules | Noise on empty, single-file, and init-only repos; lower trust in baseline scan output | Reproduced on minimal repos + strengthened edge-case regression tests | Suppress missing-README finding for repositories with `len(parse_results) <= 1` or all parsed files named `__init__.py`; keep normal README requirement for larger repos | 4 | 6 | 3 | 72 |
| DIA | FN: Minimal but intentionally documented bootstrap repos receive no README reminder | New bootstrap guard suppresses README guidance for tiny repos and pure package skeletons that may still benefit from documentation | Slightly lower README enforcement on very small repositories | Existing README presence still prevents finding; guard only applies to bootstrap-sized or init-only footprints | Keep threshold narrow (`<= 1` parsed file or all `__init__.py`), emit normal README finding as soon as repository shape exceeds bootstrap size | 2 | 3 | 6 | 36 |

## 2026-04-05 - AVS lazy-import policy violation detection (Issue #146)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| AVS | FN: policy-relevant heavy module-level imports are not surfaced | AVS had boundary and inferred-layer checks, but no dedicated lazy-import policy rule for heavy runtime libraries | Documented architecture policy violations (for example `onnxruntime`/`torch` at module scope) are missed | Field report from Real-Time Fortnite Coach + targeted AVS/parser/config regressions | Add configurable `policies.lazy_import_rules` with module-level enforcement and explicit `avs_lazy_import_policy` findings | 7 | 5 | 4 | 140 |
| AVS | FP: legitimate local lazy imports are flagged as violations | Import analysis lacks scope distinction between module-level and function-local imports | Noisy triage and reduced trust in policy findings | Regression case with local `import torch` in function scope | Extend `ImportInfo` with `is_module_level`, default rule `module_level_only=true`, and test coverage for scope-aware suppression | 5 | 3 | 4 | 60 |

## 2026-04-05 - MDS package-level lazy __getattr__ false positives (Issue #144)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| MDS | FP: package `__init__.py` lazy-loading `__getattr__` functions reported as high-severity exact duplicates | Duplicate detector treated intentional PEP 562 package plumbing as copy-paste drift | High-priority triage noise and lower confidence in MDS findings | Field-test issue report + dedicated regression tests | Exclude package-level `__getattr__` in `__init__.py` from MDS candidate set; keep non-package `__getattr__` detection active | 5 | 6 | 4 | 120 |
| MDS | FN: true architectural duplication in package-level `__getattr__` can be under-reported | New suppression heuristic intentionally skips this idiom by default | Rare real duplication problems may be surfaced later by reviewers instead of MDS | Regression guard for non-`__init__.py` `__getattr__` duplicates | Scope suppression strictly to `__init__.py` + `__getattr__` only | 4 | 2 | 6 | 48 |

## 2026-04-05 - TPD negative assertion undercount calibration (Issue #143)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| TPD | FP: happy-path-only finding emitted despite meaningful negative tests | Python `assert` statements were treated as positive by default; negative forms like `assert not ...`, `assert ... is False/None`, and functional `pytest.raises`/`pytest.fail` were undercounted | Inflated TPD score, noisy findings, and reduced trust in polarity diagnostics | Field report on Real-Time Fortnite Coach + new focused regressions | AST-aware assert polarity classification, regex fallback for assert text variants, and explicit negative call handling for raises/fail patterns | 6 | 6 | 4 | 144 |
| TPD | FN risk: weak assertions could be over-counted as negative | Heuristic classification may treat some non-failure semantics as negative in ambiguous assert expressions | True happy-path-only suites may be under-reported in edge cases | Regression coverage for mixed positive/negative suites and explicit call-pattern checks | Keep heuristics conservative (`not`, `False`, `None`, explicit fail/raises calls), preserve ratio threshold gate, and monitor future field reports | 5 | 2 | 6 | 60 |

## 2026-04-05 - PFS framework-surface error-handling calibration (Issue #142)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| PFS | FP-severity: framework-facing modules reported as HIGH for expected error-handling variance | Context-agnostic fragmentation scoring treated endpoint/orchestration diversity as structural drift | Triage noise, lower trust, and over-prioritized low-actionability work | Field test report + targeted PFS regressions | Framework-surface heuristic hints + score dampening + HIGH-to-MEDIUM cap for error_handling in framework context | 6 | 6 | 4 | 144 |
| PFS | FN-severity: truly harmful framework-boundary fragmentation may be under-ranked | Dampening heuristic can lower urgency in edge cases where variance is actually risky | Delayed remediation for rare high-impact boundary inconsistencies | Regression control test on non-framework core modules | Keep finding emission (no suppression), apply dampening only with explicit hints, expose metadata hints for reviewer override | 6 | 2 | 6 | 72 |

## 2026-04-05 - MAZ, AVS, EDS signal quality batch (Issues #148, #149, #150, #151)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| MAZ | FP: intentionally public endpoints flagged as missing auth | Allowlist too narrow — common public patterns (anon, pricing, security_txt) not covered; dev-tool paths not excluded | ~20% precision, triage noise, trust erosion | Quality audit benchmark + new regression tests | Expanded allowlist (+25 patterns) + dev-tool path heuristic (7 defaults) | 6 | 6 | 3 | 108 |
| MAZ | FN: real auth gap missed due to expanded allowlist | Over-broad substring matching could suppress genuine missing-auth endpoints | Delayed remediation for true auth gaps | Regression test: non-dev-path still flagged | Conservative substring matching, keep finding emitted, metadata for auditability | 7 | 2 | 5 | 70 |
| EDS | FP-severity: trivial getters rated HIGH same as complex algorithms | No LOC or visibility weighting — severity derived from raw complexity ratio only | LOW-complexity findings clutter HIGH-priority triage | Field comparison across benchmark repos | LOC-based dampening (loc/30) + private-function visibility dampening (0.7×) | 5 | 5 | 3 | 75 |
| EDS | FN-severity: meaningful private complex function under-ranked | Private visibility factor always 0.7× even for high-complexity functions | Delayed remediation for complex private code | Test: complexity-20 private function still emitted as HIGH | Visibility dampening is mild (0.7×), only reduces not suppresses | 5 | 2 | 5 | 50 |
| AVS | Attribution: all sub-checks conflated under "AVS" abbreviation | No rule_id on 8 AVS sub-checks (boundary, upward-import, circular-dep, etc.) | Impossible to filter or distinguish sub-signals in scan output | Quality audit issue #150 | Added explicit rule_id per sub-check, exposed in concise output | 4 | 7 | 2 | 56 |
| All | Location gap: findings with null start_line | Signals emit findings without start_line when AST node unavailable | Agent fix workflows cannot navigate to finding location | Automated field check across all 9 signal files | Finding.__post_init__ fallback: start_line=1 when file_path is set | 4 | 5 | 2 | 40 |

## 2026-04-05 - HSC OAuth endpoint URL false positives (Issue #161)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| HSC | FP: OAuth endpoint constants are flagged as hardcoded secrets | Variable-name heuristic matches `TOKEN_URL`/`AUTH_URL`; endpoint URLs are treated like credential literals | High-severity triage noise and reduced trust in HSC findings | Field test on onyx-dot-app/onyx + targeted HSC regressions | Suppress plain HTTP(S) endpoint URLs without embedded credentials (userinfo) | 6 | 5 | 4 | 120 |
| HSC | FN: Credential-bearing URL literal could be under-reported after suppression | Over-broad URL suppression in secret-sensitive variables | Real secret material in URL userinfo may be missed | Regression test with `https://user:secret@...` | Keep detection active when URL contains username/password and retain known-prefix checks | 7 | 2 | 5 | 70 |

## 2026-04-05 - HSC error-message constant false positives (Issue #163)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| HSC | FP: Natural-language error/warning/message constants are flagged as hardcoded secrets | Secret-shaped variable names (`token`, `secret`) matched without checking if literal is a human-readable message constant (for example `_MAX_TOKENS_ERROR`) | High-severity triage noise and lower trust in HSC findings | Field test on langchain + new regression test for `_MAX_TOKENS_ERROR`-style constant | Suppress literals when variable name suffix indicates message constant (`_ERROR`, `_WARNING`, `_MESSAGE`) and content looks like natural-language message text | 6 | 6 | 4 | 144 |
| HSC | FN: Real credential assigned to `*_ERROR`/`*_WARNING`/`*_MESSAGE` may be under-reported | New suppression heuristic can treat malformed or unusual credential strings as messages | Rare real secret leaks in misnamed constants may be delayed | Existing token-prefix and URL-userinfo detections still fire before suppression | Keep suppression narrow: suffix + natural-language heuristic (minimum length, word count, whitespace) and preserve high-confidence prefix checks | 5 | 2 | 6 | 60 |

## 2026-04-05 - MAZ documented public-safe endpoint severity calibration (Issue #162)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| MAZ | FP-severity: intentionally public publishable-key endpoint is emitted as HIGH | MAZ considered only missing auth marker and endpoint naming allowlist, but not explicit documented public-safe intent | High-priority triage noise, reduced trust in MAZ findings | Field report on onyx-dot-app/onyx + targeted regression test | Downgrade to LOW when endpoint name indicates publishable/public key semantics and function is explicitly documented (docstring present) | 6 | 5 | 4 | 120 |
| MAZ | FN risk: real sensitive endpoint under-ranked due heuristic dampening | Over-broad public-safe matching could hide materially risky unauthenticated endpoints | Delayed remediation for true auth gaps | Regression test for same endpoint name without docstring (remains HIGH) | Keep finding emitted (no suppression), require docstring + conservative marker set, attach metadata for auditability | 7 | 2 | 6 | 84 |

## 2026-04-05 - AVS tiny foundational module severity calibration (Issue #153)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| AVS (Zone of Pain) | FP-severity: tiny foundational modules are emitted as HIGH without sufficient evidence | Severity derived mainly from distance metric; tiny module structure and coupling evidence not considered | Triage noise, low-actionability work prioritized too high, trust erosion | Field test on fastapi/fastapi + targeted regressions | Tiny-foundational dampening and explicit high-risk evidence gate for HIGH severity | 6 | 6 | 4 | 144 |
| AVS (Zone of Pain) | FN-severity: meaningful tiny modules may be under-ranked after dampening | Over-conservative tiny-module dampening thresholds | Real high-impact foundation risks may be delayed in remediation order | Regression test for tiny module with strong coupling evidence (HIGH retained) | High-risk evidence override (`ca >= 6` or `ca >= 4 and ce >= 2`) plus metadata for observability | 5 | 3 | 5 | 75 |

## 2026-04-05 - DCA framework/library public API suppression (Issue #152)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| DCA | FP: Public framework/library exports are flagged as unused dead code | Internal-import-only heuristic cannot observe external consumers of package APIs | Trust erosion, noisy findings, misprioritized cleanup work | Field report on fastapi/fastapi + regression test on package-layout API modules | Suppress dead-export findings for package-layout public API modules in framework/library profile | 6 | 6 | 4 | 144 |
| DCA | FN: Internal dead exports may be missed after public API suppression | Over-broad package-level suppression can hide true dead symbols | Reduced dead-code recall in library repositories | Added regression test for internal path token handling | Restrict suppression to package public API paths and keep internal/private path tokens reportable | 5 | 3 | 5 | 75 |

## 2026-04-04 - MCP stdio deadlock hardening on Windows

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| ECD and git-backed analysis paths | MCP call hangs while invoking git subprocesses | `subprocess.run` inherits MCP stdin handle when `stdin` is not explicitly set | Stalled tool call, no actionable result returned | Regression test scans all `subprocess.run` calls in `src/drift` for `stdin`/`input` | Enforce `stdin=subprocess.DEVNULL` for affected subprocess calls | 8 | 3 | 3 | 72 |
| MCP tool execution pipeline | Deadlock during first threaded import of heavy C-extension modules | Lazy first import happens inside worker thread after event loop starts | Session teardown risk and non-deterministic hangs on Windows | Regression test asserts `_eager_imports()` is called before `mcp.run()` | Eager-import heavy modules before event loop startup | 8 | 2 | 4 | 64 |

## 2026-04-03 - PFS/NBV copilot-context actionability (Issue #125)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| PFS | Finding text too vague to execute | Fix text omitted canonical exemplar and line-level deviation anchors | Agents must open multiple files to infer next step, reducing trust and speed | Issue report + regression test assertions | Include canonical exemplar `file:line` and explicit deviation refs in fix text | 5 | 6 | 3 | 90 |
| NBV | Contract violation guidance not specific enough | Generic fix text ignored matched naming rule semantics | Incorrect or delayed implementation choices (rename vs behavior change) | Issue report + regression test assertions | Prefix-specific suggestions plus location anchor `file:line` in fix text | 5 | 5 | 3 | 75 |

## 2026-07-18 - Security audit: is_test_file guard for PFS/AVS/MDS

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| PFS | FP: Test file pattern variants reported as fragmentation | No is_test_file() guard; test helpers use intentionally varied patterns | Inflated fragmentation scores, noise in fix_first | Regression tests + default exclude covers most cases | Added is_test_file() skip in pattern collection loop | 3 | 3 | 3 | 27 |
| AVS | FP: Test imports flagged as layer violations | Tests legitimately import across all layers | False architecture violation findings | Regression tests + default exclude covers most cases | Added is_test_file() filter before import graph construction | 4 | 3 | 3 | 36 |
| MDS | FP: Test helper duplicates flagged as mutant clones | Test files often contain intentional near-duplicates | Noise in duplicate detection results | Regression tests + default exclude covers most cases | Added is_test_file() skip in function collection loop | 3 | 3 | 3 | 27 |

## 2026-07-18 - Security audit: negative_context metadata injection

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| AVS/NBV | Output injection: Crafted metadata values could inject fake code blocks in negative context output | Unsanitized metadata strings embedded in f-string code templates | Agent could execute injected instructions from negative context | Manual code review | Added _sanitize() helper stripping control chars/newlines from metadata before f-string embedding | 5 | 2 | 4 | 40 |

## 2026-04-03 - DIA Markdown slash-token false positives (Issue #121)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| DIA | FP: Generic prose tokens (e.g. async/, scan/, connectors/) reported as missing directories | Slash-token extraction without structural context in markdown prose | Trust erosion, noisy findings, reduced actionability | User report + regression test in tests/test_dia_enhanced.py | Context-aware extraction: accept only backticked refs or nearby structural keywords; keep code-span refs | 5 | 6 | 4 | 120 |
| DIA | FN: Real directory mention in plain prose filtered too aggressively | Context window misses valid wording | Missed drift signal | DIA regression tests for context-positive phrases | Structural keyword list + explicit backtick acceptance | 4 | 3 | 5 | 60 |

## 2026-04-09 - PHR Signal: Phantom Reference (ADR-033)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| PHR | FP: star-import file references name provided by star | Star imports (`from X import *`) inject unknown names into scope | False phantom finding for names actually available via star import | `phr_star_import_tn` fixture | Conservative skip: files with star imports are excluded from PHR analysis | 4 | 3 | 2 | 24 | **Mitigated** |
| PHR | FP: module __getattr__ provides dynamic names | Module-level `__getattr__` makes any attribute access valid | False phantom finding for dynamically provided names | `phr_dynamic_tn` fixture | Conservative skip: files with module-level `__getattr__` are excluded | 4 | 2 | 2 | 16 | **Mitigated** |
| PHR | FP: plugin/extension names resolved at runtime | Plugin systems register names dynamically via entry points or registries | False positive for intentionally late-bound names | Manual review | `_FRAMEWORK_GLOBALS` allowlist covers common framework names; further refinement via config | 3 | 3 | 5 | 45 | Accepted |
| PHR | FN: exec/eval introduce names not visible to AST | `exec()` or `eval()` can inject names into scope at runtime | Phantom names created by exec/eval not detected as defined | `_has_exec_eval` detection flag (logged, not yet used for suppression) | Accept: static analysis limitation; exec/eval usage is rare in well-structured code | 3 | 2 | 8 | 48 | Accepted |
| PHR | FN: getattr-based access not tracked | `getattr(obj, "name")` resolves names at runtime | Under-reporting for highly dynamic codebases | N/A — static analysis limitation | Accept: getattr patterns are intentionally dynamic | 2 | 3 | 8 | 48 | Accepted |
| PHR | FP: third-party library names not in project symbol table | Names from installed packages (e.g. `requests.get`) not tracked | False positive for external dependency calls | Project-wide symbol table includes import-resolved names | Import-tracked names are added to available set; root name resolution covers `import X; X.call()` | 5 | 4 | 3 | 60 | **Mitigated** |

## 2026-04-10 - Scoring Promotion: HSC, FOE, PHR (ADR-040)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| HSC | FP: non-secret config value in secret-free file | Variable names like DB_HOST, API_TIMEOUT don't match secret patterns | No false trigger expected | `hsc_placeholder_tn` fixture | Variable-name heuristic requires known secret-indicating patterns | 2 | 1 | 2 | 4 | **Mitigated** |
| HSC | FP: environment-read variable flagged as hardcoded | Variable name matches secret pattern but value is `os.environ[...]` call | False finding on properly externalized secrets | `hsc_env_read_tn` fixture | AST check: RHS is `os.environ`/`os.getenv` call → skip | 5 | 3 | 2 | 30 | **Mitigated** |
| HSC | FN: obfuscated secret not detected | Secret is base64-encoded, split across variables, or loaded from non-standard path | Missed hardcoded credential | Manual review | Accept: HSC is first-pass static heuristic; obfuscated secrets require dedicated secret scanning tools | 6 | 3 | 7 | 126 | Accepted |
| HSC | FP: ML tokenizer/model constants flagged | High-entropy hex strings in ML vocabulary files match secret heuristic | False finding on legitimate ML constants | `hsc_tn_ml_tokenizer_constants` fixture | Context-aware skip for known ML file patterns | 4 | 2 | 2 | 16 | **Mitigated** |
| FOE | FP: barrel/re-export __init__.py flagged | `__init__.py` files re-export many names from submodules | False fan-out finding on standard package pattern | `foe_barrel_file_tn` fixture | `__init__.py` files excluded from FOE detection | 3 | 4 | 2 | 24 | **Mitigated** |
| FOE | FN: high fan-out via dynamic imports | `importlib.import_module()` or `__import__()` used to load modules | Under-reporting for dynamically assembled modules | N/A — static analysis limitation | Accept: dynamic imports are invisible to AST-based import counting | 3 | 2 | 8 | 48 | Accepted |
| FOE | FP: test file with many test-helper imports | Test files often import many fixtures, helpers, and mocks | False finding on standard test organization | `is_test_file()` guard | Test files excluded via file-discovery filter | 3 | 3 | 2 | 18 | **Mitigated** |
| PHR | Scoring promotion: FP in composite score | PHR false positive now affects composite drift score (weight 0.02) instead of being report-only | Slightly inflated drift score for affected modules | Precision/recall suite + `phr_conditional_import_tn`, `phr_framework_decorator_tn` fixtures | Low weight (0.02) limits score impact; existing FP mitigations remain active | 5 | 3 | 3 | 45 | **Mitigated** |

## 2026-04-12 - Type-safety hardening for TVS/SMS/COD execution paths

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| TVS | Runtime/type mismatch when `first_seen` is null-like | Optional datetime values were timezone-normalized via dynamic attribute checks | CI mypy failures and potential brittle timezone normalization path | CI mypy (`union-attr`) and local reproduction | Replace dynamic attribute probing with explicit `isinstance(datetime.datetime)` guards before `astimezone()` | 3 | 4 | 2 | 24 |
| SMS | Runtime/type mismatch for `first_seen` / `last_modified` normalization | Optional datetime values converted without strict type narrowing | CI mypy failures and reduced confidence in static safety | CI mypy (`union-attr`) and local reproduction | Add explicit datetime type checks before timezone conversion in workspace recency logic | 3 | 4 | 2 | 24 |
| COD | Implicit `Any` return in token extraction helper | Regex match list element propagated as `Any` to a `-> str` function | CI mypy failure (`no-any-return`) and weaker contract guarantees | CI mypy and local reproduction | Enforce concrete `str(...)` conversion in `_leading_token()` before normalization | 2 | 3 | 2 | 12 |
| CCC | Helper API drift: tests/callers omit new argument | Internal helper gained a required `known_files` argument without backward-compatible default | Test/runtime `TypeError` and failed CI execution path validation | Pytest failure in helper coverage suite | Make `known_files` optional and preserve previous conservative behavior when omitted | 4 | 3 | 2 | 24 |
| EDS | FN: complex TS function suppressed when docs/tests are both missing | Signature-based dampening applied uniformly, over-penalizing missing-test cases | Precision/recall regression (`eds_ts_tp` false negative) | Precision/recall suite + targeted fixture | Apply weaker/no dampening when TS signature exists but test evidence is explicitly missing | 5 | 3 | 3 | 45 |
