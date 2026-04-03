# STRIDE Threat Model

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
