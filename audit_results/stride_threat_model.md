# STRIDE Threat Model

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
