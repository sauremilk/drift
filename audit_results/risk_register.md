# Risk Register

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
