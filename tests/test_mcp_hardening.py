"""Regression tests for MCP/API hardening changes."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest


class TestApiInputValidation:
    def test_diff_rejects_option_like_diff_ref(self) -> None:
        from drift.api import diff

        result = diff(Path("."), diff_ref="--help")

        assert result["type"] == "error"
        assert result["error_code"] == "DRIFT-1003"
        assert result["invalid_fields"][0]["field"] == "diff_ref"

    def test_fix_plan_rejects_unknown_automation_fit(self) -> None:
        from drift.api import fix_plan

        result = fix_plan(Path("."), automation_fit_min="urgent")

        assert result["type"] == "error"
        assert result["error_code"] == "DRIFT-1003"
        assert result["invalid_fields"][0]["field"] == "automation_fit_min"


class TestMcpErrorEnvelope:
    def test_drift_scan_wraps_unhandled_exceptions(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from drift import mcp_server

        def _broken_scan(*_args, **_kwargs):
            raise RuntimeError("boom")

        monkeypatch.setattr("drift.api.scan", _broken_scan)

        result = json.loads(mcp_server.drift_scan(path="."))

        assert result["type"] == "error"
        assert result["error_code"] == "DRIFT-5001"
        assert result["tool"] == "drift_scan"


class TestValidateProgressMetrics:
    def test_validate_reports_resolved_count_from_fingerprint_delta(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        import drift.api as api_module
        from drift.api import validate
        from drift.config import DriftConfig

        baseline_file = tmp_path / ".drift-baseline.json"
        baseline_file.write_text('{"drift_score": 0.4}', encoding="utf-8")

        finding = SimpleNamespace(name="k1")
        analysis = SimpleNamespace(findings=[finding])

        monkeypatch.setattr(DriftConfig, "load", staticmethod(lambda *a, **kw: DriftConfig()))
        monkeypatch.setattr(DriftConfig, "_find_config_file", staticmethod(lambda *_a, **_kw: None))
        monkeypatch.setattr(
            "drift.ingestion.file_discovery.discover_files",
            lambda *a, **kw: [],
        )
        monkeypatch.setattr(api_module, "scan", lambda *a, **kw: {"drift_score": 0.5})
        monkeypatch.setattr("drift.baseline.load_baseline", lambda *_a, **_kw: {"k1", "k2", "k3"})
        monkeypatch.setattr("drift.analyzer.analyze_repo", lambda *a, **kw: analysis)
        monkeypatch.setattr(
            "drift.baseline.baseline_diff",
            lambda findings, baseline: ([], [finding]),
        )
        monkeypatch.setattr("drift.baseline.finding_fingerprint", lambda _f: "k1")
        monkeypatch.setattr(api_module, "_emit_api_telemetry", lambda **kw: None)

        result = validate(tmp_path, baseline_file=str(baseline_file))

        assert result["progress"]["resolved_count"] == 2
        assert result["progress"]["known_count"] == 1
        assert result["progress"]["new_count"] == 0
