from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

from drift.api import diff, explain, scan
from drift.models import Severity, SignalType
from drift.telemetry import log_tool_event

# Resolve actual submodules (drift.api.__init__ shadows names with functions)
_scan_mod = sys.modules["drift.api.scan"]
_diff_mod = sys.modules["drift.api.diff"]


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_log_tool_event_writes_jsonl_when_enabled(
    monkeypatch,
    tmp_path: Path,
) -> None:
    out = tmp_path / "events.jsonl"
    monkeypatch.setenv("DRIFT_TELEMETRY_ENABLED", "1")
    monkeypatch.setenv("DRIFT_TELEMETRY_FILE", str(out))

    log_tool_event(
        tool_name="api.scan",
        params={"path": ".", "token": "secret-value"},
        status="ok",
        duration_ms=13,
        result={"drift_score": 0.42, "severity": "medium"},
        repo_root=tmp_path,
    )

    assert out.exists()
    rows = _read_jsonl(out)
    assert len(rows) == 1
    row = rows[0]
    assert row["event_type"] == "drift_tool_call"
    assert row["tool_name"] == "api.scan"
    assert row["status"] == "ok"
    assert row["params"]["token"] == "***REDACTED***"
    assert row["input_tokens_est"] >= 1
    assert row["output_tokens_est"] >= 1
    assert row["run_id"]


def test_log_tool_event_uses_explicit_run_id(monkeypatch, tmp_path: Path) -> None:
    out = tmp_path / "events.jsonl"
    monkeypatch.setenv("DRIFT_TELEMETRY_ENABLED", "1")
    monkeypatch.setenv("DRIFT_TELEMETRY_FILE", str(out))
    monkeypatch.setenv("DRIFT_TELEMETRY_RUN_ID", "agent-run-123")

    log_tool_event(
        tool_name="api.scan",
        params={"path": "."},
        status="ok",
        duration_ms=5,
        result={"drift_score": 0.1},
        repo_root=tmp_path,
    )

    row = _read_jsonl(out)[0]
    assert row["run_id"] == "agent-run-123"


def test_log_tool_event_sanitizes_home_directory_paths(monkeypatch, tmp_path: Path) -> None:
    out = tmp_path / "events.jsonl"
    fake_home = tmp_path / "home" / "testuser"
    fake_home.mkdir(parents=True)

    monkeypatch.setenv("DRIFT_TELEMETRY_ENABLED", "1")
    monkeypatch.setenv("DRIFT_TELEMETRY_FILE", str(out))
    monkeypatch.setattr("drift.telemetry.Path.home", classmethod(lambda cls: fake_home))

    log_tool_event(
        tool_name="api.validate",
        params={
            "path": str(fake_home / "repo"),
            "config_file": str(fake_home / "config" / "drift.yaml"),
            "baseline_file": str(fake_home),
        },
        status="ok",
        duration_ms=7,
        result={"ok": True},
        repo_root=tmp_path,
    )

    row = _read_jsonl(out)[0]
    params = row["params"]

    assert params["path"].startswith("~/")
    assert params["config_file"].startswith("~/")
    assert params["baseline_file"].startswith("~")
    assert "testuser" not in json.dumps(params)


def test_log_tool_event_disabled_writes_nothing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    out = tmp_path / "events.jsonl"
    monkeypatch.delenv("DRIFT_TELEMETRY_ENABLED", raising=False)
    monkeypatch.setenv("DRIFT_TELEMETRY_FILE", str(out))

    log_tool_event(
        tool_name="api.scan",
        params={"path": "."},
        status="ok",
        duration_ms=4,
        result={"drift_score": 0.1},
        repo_root=tmp_path,
    )

    assert not out.exists()


def test_api_explain_emits_telemetry(
    monkeypatch,
    tmp_path: Path,
) -> None:
    out = tmp_path / "api_events.jsonl"
    monkeypatch.setenv("DRIFT_TELEMETRY_ENABLED", "1")
    monkeypatch.setenv("DRIFT_TELEMETRY_FILE", str(out))

    result = explain("PFS")
    assert result["schema_version"] == "2.1"

    rows = _read_jsonl(out)
    assert len(rows) == 1
    row = rows[0]
    assert row["tool_name"] == "api.explain"
    assert row["status"] == "ok"
    assert row["params"]["topic"] == "PFS"
    assert row["result_summary"]["has_error"] is False


def test_api_diff_returns_acceptance_fields(monkeypatch) -> None:
    import drift.analyzer as analyzer_module
    from drift.config import DriftConfig

    finding = SimpleNamespace(
        severity=Severity.HIGH,
        signal_type=SignalType.PATTERN_FRAGMENTATION,
        title="Fragmented validation pattern",
        file_path=Path("src/example.py"),
        start_line=12,
        impact=0.9,
        fix="Consolidate validation flow.",
    )
    analysis = SimpleNamespace(
        findings=[finding],
        drift_score=0.45,
        severity=Severity.HIGH,
        trend=SimpleNamespace(previous_score=0.2),
        is_degraded=False,
        total_files=12,
    )

    monkeypatch.setattr(DriftConfig, "load", staticmethod(lambda *args, **kwargs: object()))
    monkeypatch.setattr(analyzer_module, "analyze_diff", lambda *args, **kwargs: analysis)
    monkeypatch.setattr(_diff_mod, "_finding_concise", lambda f: {"title": f.title})
    monkeypatch.setattr(_diff_mod, "_emit_api_telemetry", lambda **kwargs: None)

    result = diff(Path("."))

    assert result["accept_change"] is False
    assert result["score_regressed"] is True
    assert result["new_high_or_critical"] == 1
    assert "new_high_or_critical_findings" in result["blocking_reasons"]
    assert "drift_score_regressed" in result["blocking_reasons"]
    assert result["decision_reason_code"] == "rejected_in_scope_blockers"
    assert "in-scope" in result["decision_reason"]
    assert "rejected" in result["agent_instruction"].lower()
    assert "safe to proceed" not in result["agent_instruction"].lower()


def test_api_diff_scopes_decision_logic_to_target_path(monkeypatch) -> None:
    import drift.analyzer as analyzer_module
    from drift.config import DriftConfig

    in_scope = SimpleNamespace(
        severity=Severity.MEDIUM,
        signal_type=SignalType.PATTERN_FRAGMENTATION,
        title="In scope",
        file_path=Path("src/app/service.py"),
        start_line=10,
        impact=0.3,
        fix="Consolidate",
    )
    out_scope = SimpleNamespace(
        severity=Severity.HIGH,
        signal_type=SignalType.PATTERN_FRAGMENTATION,
        title="Out of scope",
        file_path=Path("tests/test_app.py"),
        start_line=20,
        impact=0.8,
        fix="Consolidate",
    )
    analysis = SimpleNamespace(
        findings=[in_scope, out_scope],
        drift_score=0.45,
        severity=Severity.HIGH,
        trend=SimpleNamespace(previous_score=0.45),
        is_degraded=False,
        total_files=12,
    )

    monkeypatch.setattr(DriftConfig, "load", staticmethod(lambda *args, **kwargs: object()))
    monkeypatch.setattr(analyzer_module, "analyze_diff", lambda *args, **kwargs: analysis)
    monkeypatch.setattr(_diff_mod, "_finding_concise", lambda f: {"title": f.title})
    monkeypatch.setattr(_diff_mod, "_emit_api_telemetry", lambda **kwargs: None)

    result = diff(Path("."), target_path="src/app")

    assert result["new_finding_count"] == 1
    assert result["new_high_or_critical"] == 0
    assert result["out_of_scope_new_count"] == 1
    assert result["target_path"] == "src/app"
    assert "out_of_scope_diff_noise" in result["blocking_reasons"]
    assert result["decision_reason_code"] == "rejected_out_of_scope_noise_only"
    assert "out-of-scope" in result["decision_reason"]
    assert "in_scope_accept" in result["agent_instruction"]
    assert "safe to proceed" not in result["agent_instruction"].lower()


def test_api_diff_recommends_baseline_for_large_working_tree(monkeypatch) -> None:
    import drift.analyzer as analyzer_module
    import drift.api as api_module
    from drift.config import DriftConfig

    analysis = SimpleNamespace(
        findings=[],
        drift_score=0.45,
        severity=Severity.LOW,
        trend=SimpleNamespace(previous_score=0.45),
        is_degraded=False,
        total_files=120,
    )

    monkeypatch.setattr(DriftConfig, "load", staticmethod(lambda *args, **kwargs: DriftConfig()))
    monkeypatch.setattr(analyzer_module, "analyze_diff", lambda *args, **kwargs: analysis)
    monkeypatch.setattr(api_module, "_emit_api_telemetry", lambda **kwargs: None)

    result = diff(Path("."))

    assert result["baseline_recommended"] is True
    assert result["baseline_reason"] == "large_working_tree"
    assert any("drift baseline save" in action for action in result["recommended_next_actions"])


def test_api_diff_does_not_recommend_baseline_when_baseline_is_provided(monkeypatch) -> None:
    import drift.analyzer as analyzer_module
    import drift.api as api_module
    import drift.baseline as baseline_module
    from drift.config import DriftConfig

    analysis = SimpleNamespace(
        findings=[],
        drift_score=0.45,
        severity=Severity.LOW,
        trend=SimpleNamespace(previous_score=0.45),
        is_degraded=False,
        total_files=120,
    )

    monkeypatch.setattr(DriftConfig, "load", staticmethod(lambda *args, **kwargs: DriftConfig()))
    monkeypatch.setattr(analyzer_module, "analyze_diff", lambda *args, **kwargs: analysis)
    monkeypatch.setattr(baseline_module, "load_baseline", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(baseline_module, "baseline_diff", lambda findings, _fps: (findings, []))
    monkeypatch.setattr(api_module, "_emit_api_telemetry", lambda **kwargs: None)

    result = diff(Path("."), baseline_file=".drift-baseline.json")

    assert result["baseline_recommended"] is False
    assert result["baseline_reason"] == "none"


def test_api_diff_uncommitted_mode_passed_to_analyzer(monkeypatch) -> None:
    import drift.analyzer as analyzer_module
    import drift.api as api_module
    from drift.config import DriftConfig

    captured: dict[str, object] = {}
    analysis = SimpleNamespace(
        findings=[],
        drift_score=0.2,
        severity=Severity.LOW,
        trend=SimpleNamespace(previous_score=0.2),
        is_degraded=False,
        total_files=1,
    )

    def _fake_analyze_diff(*args, **kwargs):
        captured.update(kwargs)
        return analysis

    monkeypatch.setattr(DriftConfig, "load", staticmethod(lambda *args, **kwargs: object()))
    monkeypatch.setattr(analyzer_module, "analyze_diff", _fake_analyze_diff)
    monkeypatch.setattr(api_module, "_emit_api_telemetry", lambda **kwargs: None)

    result = diff(Path("."), uncommitted=True)

    assert captured["diff_mode"] == "uncommitted"
    assert result["diff_mode"] == "uncommitted"


def test_api_diff_rejects_conflicting_mode_flags(monkeypatch) -> None:
    import drift.api as api_module
    from drift.config import DriftConfig

    monkeypatch.setattr(DriftConfig, "load", staticmethod(lambda *args, **kwargs: object()))
    monkeypatch.setattr(api_module, "_emit_api_telemetry", lambda **kwargs: None)

    try:
        diff(Path("."), uncommitted=True, staged_only=True)
        raise AssertionError("Expected ValueError for conflicting diff mode flags.")
    except ValueError as exc:
        assert "mutually exclusive" in str(exc)


def test_api_diff_staged_only_reports_zero_staged_files(monkeypatch) -> None:
    import drift.analyzer as analyzer_module
    import drift.api as api_module
    from drift.config import DriftConfig

    analysis = SimpleNamespace(
        findings=[],
        drift_score=0.0,
        severity=Severity.LOW,
        trend=SimpleNamespace(previous_score=0.0),
        is_degraded=False,
        total_files=0,
    )

    monkeypatch.setattr(DriftConfig, "load", staticmethod(lambda *args, **kwargs: object()))
    monkeypatch.setattr(analyzer_module, "analyze_diff", lambda *args, **kwargs: analysis)
    monkeypatch.setattr(api_module, "_emit_api_telemetry", lambda **kwargs: None)

    result = diff(Path("."), staged_only=True)

    assert result["diff_mode"] == "staged"
    assert result["staged_file_count"] == 0
    assert result["no_staged_files"] is True
    assert "No staged files were analyzed" in result["agent_instruction"]
    assert "Safe to proceed" not in result["agent_instruction"]


def test_api_scan_returns_acceptance_fields(monkeypatch) -> None:
    import drift.analyzer as analyzer_module
    from drift.config import DriftConfig

    finding = SimpleNamespace(
        severity=Severity.HIGH,
        signal_type=SignalType.PATTERN_FRAGMENTATION,
        score=0.8,
        title="Fragmented validation pattern",
        file_path=Path("src/example.py"),
        start_line=12,
        impact=0.9,
        fix="Consolidate validation flow.",
        metadata={},
    )
    analysis = SimpleNamespace(
        findings=[finding],
        drift_score=0.45,
        severity=Severity.HIGH,
        total_files=12,
        total_functions=50,
        ai_attributed_ratio=0.1,
        trend=SimpleNamespace(direction="degrading", previous_score=0.2, delta=0.25),
    )

    monkeypatch.setattr(DriftConfig, "load", staticmethod(lambda *args, **kwargs: object()))
    monkeypatch.setattr(analyzer_module, "analyze_repo", lambda *args, **kwargs: analysis)
    monkeypatch.setattr(_scan_mod, "_emit_api_telemetry", lambda **kwargs: None)
    monkeypatch.setattr(_scan_mod, "_finding_concise", lambda f: {"title": f.title})
    monkeypatch.setattr(_scan_mod, "_top_signals", lambda analysis, **_kw: [])
    monkeypatch.setattr(_scan_mod, "_fix_first_concise", lambda analysis, max_items=5: [])

    result = scan(Path("."))

    assert result["accept_change"] is False
    assert result["critical_count"] == 0
    assert result["high_count"] == 1
    assert "existing_high_or_critical_findings" in result["blocking_reasons"]
    assert "drift_trend_degrading" in result["blocking_reasons"]
