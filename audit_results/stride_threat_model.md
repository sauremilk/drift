# STRIDE Threat Model

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
