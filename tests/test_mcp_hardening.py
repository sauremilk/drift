"""Regression tests for MCP/API hardening changes."""

from __future__ import annotations

import asyncio
import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


def _run_tool(result: object) -> object:
    """Transparently await async MCP tool results in sync test context."""
    if inspect.isawaitable(result):
        return asyncio.run(result)
    return result


class TestApiInputValidation:
    def test_diff_rejects_option_like_diff_ref(self) -> None:
        from drift.api import diff

        result = diff(Path("."), diff_ref="--help")

        assert result["type"] == "error"
        assert result["error_code"] == "DRIFT-1003"
        assert result["invalid_fields"][0]["field"] == "diff_ref"
        assert result.get("pass") is None

    def test_fix_plan_rejects_unknown_automation_fit(self) -> None:
        from drift.api import fix_plan

        result = fix_plan(Path("."), automation_fit_min="urgent")

        assert result["type"] == "error"
        assert result["error_code"] == "DRIFT-1003"
        assert result["invalid_fields"][0]["field"] == "automation_fit_min"
        assert result.get("pass") is None


class TestMcpErrorEnvelope:
    def test_drift_scan_wraps_unhandled_exceptions(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from drift import mcp_server

        def _broken_scan(*_args, **_kwargs):
            raise RuntimeError("boom")

        monkeypatch.setattr("drift.api.scan", _broken_scan)

        result = json.loads(_run_tool(mcp_server.drift_scan(path=".")))

        assert result["type"] == "error"
        assert result["error_code"] == "DRIFT-5001"
        assert result["tool"] == "drift_scan"
        assert result.get("pass") is None


class TestMcpRouterScanGuardrails:
    def test_drift_scan_honors_router_guardrail_block(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from drift import mcp_server

        blocked = json.dumps(
            {
                "type": "error",
                "error_code": "DRIFT-6002",
                "blocked_tool": "drift_scan",
            }
        )

        monkeypatch.setattr(
            "drift.mcp_router_analysis._strict_guardrail_block_response",
            lambda *_a, **_k: blocked,
        )

        def _scan_should_not_run(*_args: object, **_kwargs: object) -> None:
            raise AssertionError("drift.api.scan should not run when strict guardrail blocks")

        monkeypatch.setattr("drift.api.scan", _scan_should_not_run)

        raw = _run_tool(mcp_server.drift_scan(path="."))

        assert raw == blocked


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


class TestMcpToolAsyncInvariant:
    """All MCP tool functions must be async to avoid blocking the event loop."""

    def test_all_exported_mcp_tools_are_async(self) -> None:
        from drift.mcp_server import _EXPORTED_MCP_TOOLS

        for tool in _EXPORTED_MCP_TOOLS:
            assert inspect.iscoroutinefunction(tool), (
                f"{tool.__name__} must be async def — sync tool functions "
                f"block the MCP event loop and cause session hangs"
            )


class TestMcpToolErrorEnvelopes:
    """Every MCP tool must return a JSON error envelope on exception, never propagate."""

    @pytest.mark.parametrize(
        "tool_name",
        ["drift_diff", "drift_explain", "drift_validate", "drift_nudge"],
    )
    def test_tool_wraps_exception_in_error_envelope(
        self, monkeypatch: pytest.MonkeyPatch, tool_name: str
    ) -> None:
        from drift import mcp_server

        api_func_map = {
            "drift_diff": "drift.api.diff",
            "drift_explain": "drift.api.explain",
            "drift_validate": "drift.api.validate",
            "drift_nudge": "drift.api.nudge",
        }

        def _boom(*_a: object, **_kw: object) -> None:
            raise RuntimeError("injected failure")

        monkeypatch.setattr(api_func_map[tool_name], _boom)

        tool_fn = getattr(mcp_server, tool_name)
        kwargs: dict[str, object] = (
            {"path": "."} if tool_name != "drift_explain" else {"topic": "PFS"}
        )
        raw = _run_tool(tool_fn(**kwargs))
        result = json.loads(raw)

        assert result["type"] == "error", f"{tool_name} did not return error envelope"
        assert result["error_code"] == "DRIFT-5001"
        assert result["tool"] == tool_name
        assert result.get("pass") is None


class TestMcpStdioTransportSafety:
    """Regression tests for MCP stdio transport deadlocks on Windows.

    Root causes fixed:
    1. subprocess.run() without stdin=DEVNULL inherits MCP stdin handle →
       Windows IOCP deadlock.
    2. First-time import of C-extension modules (numpy/torch/faiss) from a
       worker thread while the IOCP proactor is active → DLL loader lock
       deadlock.  Fixed by eager imports before the event loop starts.
    """

    def test_subprocess_calls_use_devnull_stdin(self) -> None:
        """Every subprocess.run in src/drift must set stdin=DEVNULL.

        When the MCP server runs on stdio transport, child processes must
        not inherit the server's stdin handle.  Without stdin=DEVNULL,
        Windows IOCP causes an unrecoverable deadlock.
        """
        import ast

        src = Path(__file__).resolve().parent.parent / "src" / "drift"
        violations: list[str] = []

        for py_file in sorted(src.rglob("*.py")):
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                # Match subprocess.run(...)
                func = node.func
                is_subprocess_run = False
                if (
                    isinstance(func, ast.Attribute)
                    and func.attr == "run"
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "subprocess"
                ):
                    is_subprocess_run = True

                if not is_subprocess_run:
                    continue

                # Check keywords for stdin= or input= (input= implies stdin=PIPE)
                kw_names = {kw.arg for kw in node.keywords if kw.arg}
                if "stdin" in kw_names or "input" in kw_names:
                    continue

                rel = py_file.relative_to(src.parent.parent)
                violations.append(f"{rel}:{node.lineno}")

        assert not violations, (
            "subprocess.run() without stdin=DEVNULL or input= found "
            "(would deadlock MCP stdio on Windows):\n" + "\n".join(f"  - {v}" for v in violations)
        )

    def test_eager_imports_called_before_event_loop(self) -> None:
        """main() must call _eager_imports() before mcp.run()."""
        from drift.mcp_server import _eager_imports, main

        # _eager_imports must exist and be callable
        assert callable(_eager_imports)

        # Verify main() source contains _eager_imports() call before mcp.run()
        import inspect

        source = inspect.getsource(main)
        idx_eager = source.find("_eager_imports()")
        idx_run = source.find("mcp.run(")
        assert idx_eager != -1, "_eager_imports() call missing from main()"
        assert idx_run != -1, "mcp.run() call missing from main()"
        assert idx_eager < idx_run, (
            "_eager_imports() must be called BEFORE mcp.run() to avoid "
            "Windows DLL loader lock deadlock with IOCP"
        )


class TestMcpSessionIntegration:
    """Regression tests for MCP session management (ADR-022)."""

    @pytest.fixture(autouse=True)
    def _reset_sessions(self):
        from drift.session import SessionManager

        SessionManager.reset_instance()
        yield
        SessionManager.reset_instance()

    def test_session_start_returns_session_id(self) -> None:
        from drift import mcp_server

        raw = _run_tool(mcp_server.drift_session_start(path="/tmp/test"))
        result = json.loads(raw)
        assert result["status"] == "ok"
        assert len(result["session_id"]) == 32

    def test_session_start_non_autopilot_returns_session_block(self) -> None:
        """Non-autopilot session start must still include enriched session metadata."""
        from drift import mcp_server

        raw = _run_tool(
            mcp_server.drift_session_start(
                path="/tmp/test",
                autopilot=False,
            )
        )
        result = json.loads(raw)

        assert result["status"] == "ok"
        assert "session" in result
        assert result["session"]["session_id"] == result["session_id"]
        assert "next_tools" in result["session"]

    def test_session_status_returns_summary(self) -> None:
        from drift import mcp_server

        start = json.loads(_run_tool(mcp_server.drift_session_start(path="/tmp/test")))
        sid = start["session_id"]

        raw = _run_tool(mcp_server.drift_session_status(session_id=sid))
        result = json.loads(raw)
        assert result["session_id"] == sid
        assert result["valid"] is True

    def test_session_end_returns_summary_and_removes(self) -> None:
        from drift import mcp_server

        start = json.loads(_run_tool(mcp_server.drift_session_start(path="/tmp/test")))
        sid = start["session_id"]

        end = json.loads(_run_tool(mcp_server.drift_session_end(session_id=sid)))
        assert end["session_id"] == sid
        assert "duration_seconds" in end

        # Session should be gone
        status = json.loads(_run_tool(mcp_server.drift_session_status(session_id=sid)))
        assert status["type"] == "error"
        assert status.get("pass") is None

    def test_invalid_session_id_returns_error(self) -> None:
        from drift import mcp_server

        raw = _run_tool(mcp_server.drift_session_status(session_id="nonexistent"))
        result = json.loads(raw)
        assert result["type"] == "error"
        assert result["error_code"] == "DRIFT-6001"
        assert result.get("pass") is None

    def test_session_tools_are_in_exported_list(self) -> None:
        from drift.mcp_server import _EXPORTED_MCP_TOOLS

        names = {t.__name__ for t in _EXPORTED_MCP_TOOLS}
        assert "drift_session_start" in names
        assert "drift_session_status" in names
        assert "drift_session_update" in names
        assert "drift_session_end" in names

    def test_all_original_tools_accept_session_id(self) -> None:
        """Every non-session MCP tool should accept an optional session_id param."""
        from drift.mcp_server import _EXPORTED_MCP_TOOLS

        session_tools = {
            "drift_session_start",
            "drift_session_status",
            "drift_session_update",
            "drift_session_end",
        }

        for tool in _EXPORTED_MCP_TOOLS:
            if tool.__name__ in session_tools:
                continue
            sig = inspect.signature(tool)
            assert "session_id" in sig.parameters, (
                f"{tool.__name__} must accept session_id parameter (ADR-022)"
            )

    def test_scan_with_session_updates_state(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from drift import mcp_server
        from drift.session import SessionManager

        fake_scan = {
            "drift_score": 35.5,
            "findings": [{"name": "PFS"}, {"name": "AVS"}],
            "signal_scores": {"PFS": 0.8, "AVS": 0.5},
        }
        monkeypatch.setattr("drift.api.scan", lambda *a, **kw: fake_scan)

        start = json.loads(_run_tool(mcp_server.drift_session_start(path="/tmp/test")))
        sid = start["session_id"]

        _run_tool(mcp_server.drift_scan(path="/tmp/test", session_id=sid))

        session = SessionManager.instance().get(sid)
        assert session is not None
        assert session.last_scan_score == 35.5
        assert session.last_scan_finding_count == 2
        assert session.tool_calls > 0

    def test_tools_without_session_unchanged(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Calling tools without session_id still works (backward compat)."""
        from drift import mcp_server

        fake_scan = {"drift_score": 40.0, "findings": []}
        monkeypatch.setattr("drift.api.scan", lambda *a, **kw: fake_scan)

        raw = _run_tool(mcp_server.drift_scan(path="."))
        result = json.loads(raw)

        # Should not contain session block
        assert "session" not in result
        assert result["drift_score"] == 40.0

    def test_session_start_autopilot_reuses_single_analysis(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Autopilot must not run duplicate full analyses for scan and fix_plan."""
        import drift.analyzer as analyzer_module
        from drift import mcp_server

        monkeypatch.setattr(
            "drift.api.validate",
            lambda *a, **kw: {"status": "ok", "type": "validate"},
        )
        monkeypatch.setattr(
            "drift.api.brief",
            lambda *a, **kw: {"status": "ok", "type": "brief"},
        )

        calls = {"count": 0}
        original_analyze_repo = analyzer_module.analyze_repo

        def _counting_analyze_repo(*args: object, **kwargs: object):
            calls["count"] += 1
            return original_analyze_repo(*args, **kwargs)

        monkeypatch.setattr(analyzer_module, "analyze_repo", _counting_analyze_repo)

        # Ensure the temporary repo has analyzable content.
        (tmp_path / "module.py").write_text("def ping() -> int:\n    return 1\n", encoding="utf-8")

        raw = _run_tool(
            mcp_server.drift_session_start(
                path=str(tmp_path),
                autopilot=True,
                autopilot_payload="full",
            )
        )
        result = json.loads(raw)

        assert result["status"] == "ok"
        assert "autopilot" in result
        assert "scan" in result["autopilot"]
        assert "fix_plan" in result["autopilot"]
        assert calls["count"] == 1

    def test_session_start_autopilot_uses_running_loop(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Autopilot must resolve the currently running loop in async context."""
        from drift import mcp_server

        (tmp_path / "module.py").write_text("def ping() -> int:\n    return 1\n", encoding="utf-8")

        monkeypatch.setattr(
            asyncio,
            "get_event_loop",
            lambda: (_ for _ in ()).throw(AssertionError("get_event_loop must not be used")),
        )

        raw = _run_tool(
            mcp_server.drift_session_start(
                path=str(tmp_path),
                autopilot=True,
                autopilot_payload="summary",
            )
        )
        result = json.loads(raw)

        assert result["status"] == "ok"

    def test_session_start_autopilot_defaults_to_summary_payload(
        self,
        tmp_path: Path,
    ) -> None:
        """Autopilot defaults to compact summary payload with previews and refs."""
        from drift import mcp_server

        (tmp_path / "module.py").write_text("def ping() -> int:\n    return 1\n", encoding="utf-8")

        raw = _run_tool(
            mcp_server.drift_session_start(
                path=str(tmp_path),
                autopilot=True,
            )
        )
        result = json.loads(raw)

        assert result["status"] == "ok"
        autopilot = result["autopilot"]
        assert autopilot["mode"] == "summary"
        assert "scan" not in autopilot
        assert "fix_plan" not in autopilot
        assert "drift_score" in autopilot
        assert "task_count" in autopilot
        assert "top_signals" in autopilot
        assert autopilot["next_tool_call"]["tool"] == "drift_fix_plan"
        assert (
            autopilot["findings_preview"]["total_available"]
            >= autopilot["findings_preview"]["count"]
        )
        assert autopilot["tasks_preview"]["total_available"] >= autopilot["tasks_preview"]["count"]
        assert set(autopilot["payload_refs"].keys()) == {"validate", "brief", "scan", "fix_plan"}
        for ref in autopilot["payload_refs"].values():
            assert isinstance(ref["checksum"], str)
            assert len(ref["checksum"]) == 16

    def test_session_start_autopilot_rejects_invalid_payload_mode(
        self,
        tmp_path: Path,
    ) -> None:
        """Invalid autopilot_payload value returns structured input error."""
        from drift import mcp_server

        raw = _run_tool(
            mcp_server.drift_session_start(
                path=str(tmp_path),
                autopilot=True,
                autopilot_payload="compact",
            )
        )
        result = json.loads(raw)

        assert result["type"] == "error"
        assert result["error_code"] == "DRIFT-1003"
        assert result["invalid_fields"][0]["field"] == "autopilot_payload"
        assert result.get("pass") is None

    def test_session_start_returns_structured_error_when_capacity_reached(self) -> None:
        from drift import mcp_server
        from drift.session import SessionManager

        mgr = SessionManager(max_sessions=1)
        first = mgr.create("/tmp/test")
        assert first

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("drift.session.SessionManager.instance", lambda: mgr)
            raw = _run_tool(mcp_server.drift_session_start(path="/tmp/test"))

        result = json.loads(raw)
        assert result["type"] == "error"
        assert result["error_code"] == "DRIFT-4000"
        assert result.get("pass") is None

    def test_session_start_autopilot_surfaces_intent_capture_for_high_ai_ratio(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Autopilot result must include intent_capture_hint when ai_ratio > 0.7."""
        import drift.analyzer as analyzer_module
        from drift import mcp_server

        (tmp_path / "module.py").write_text(
            "def ping() -> int:\n    return 1\n", encoding="utf-8"
        )

        original_analyze_repo = analyzer_module.analyze_repo

        def _high_ai_analyze_repo(*args: object, **kwargs: object):
            result = original_analyze_repo(*args, **kwargs)
            result.ai_attributed_ratio = 0.85
            return result

        monkeypatch.setattr(analyzer_module, "analyze_repo", _high_ai_analyze_repo)

        raw = _run_tool(
            mcp_server.drift_session_start(
                path=str(tmp_path),
                autopilot=True,
                autopilot_payload="full",
            )
        )
        result = json.loads(raw)

        assert result["status"] == "ok"
        assert "intent_capture_hint" in result, (
            "Expected intent_capture_hint for high AI ratio"
        )
        hint = result["intent_capture_hint"]
        assert hint["reason"] == "high_ai_attributed_ratio"
        assert hint["ai_attributed_ratio"] == pytest.approx(0.85, abs=0.01)
        assert hint["suggested_tool"] == "drift_capture_intent"
        assert "drift_capture_intent" in result["agent_instruction"]
        assert result["recommended_next_actions"][0].startswith("drift_capture_intent")


class TestMcpStrictGuardrails:
    """Regression tests for opt-in strict MCP orchestration guardrails (#202)."""

    @pytest.fixture(autouse=True)
    def _reset_sessions(self):
        from drift.session import SessionManager

        SessionManager.reset_instance()
        yield
        SessionManager.reset_instance()

    @staticmethod
    def _write_agent_config(repo_path: Path, *, strict: bool) -> None:
        strict_value = "true" if strict else "false"
        (repo_path / "drift.yaml").write_text(
            f'agent:\n  goal: "strict orchestration test"\n  strict_guardrails: {strict_value}\n',
            encoding="utf-8",
        )

    @pytest.mark.parametrize(
        ("tool_name", "expected_recovery_tool", "expected_reason"),
        [
            ("drift_fix_plan", "drift_brief", "missing_diagnosis"),
            ("drift_diff", "drift_scan", "missing_scan_baseline"),
            ("drift_nudge", "drift_scan", "missing_scan_baseline"),
        ],
    )
    def test_strict_mode_blocks_unsafe_orchestration_paths(
        self,
        tmp_path: Path,
        tool_name: str,
        expected_recovery_tool: str,
        expected_reason: str,
    ) -> None:
        from drift import mcp_server
        from drift.session import SessionManager

        self._write_agent_config(tmp_path, strict=True)
        start = json.loads(_run_tool(mcp_server.drift_session_start(path=str(tmp_path))))
        sid = start["session_id"]

        if tool_name == "drift_fix_plan":
            raw = _run_tool(mcp_server.drift_fix_plan(session_id=sid))
        elif tool_name == "drift_diff":
            raw = _run_tool(mcp_server.drift_diff(session_id=sid))
        else:
            raw = _run_tool(mcp_server.drift_nudge(session_id=sid))

        result = json.loads(raw)
        assert result["type"] == "error"
        assert result["error_code"] == "DRIFT-6002"
        assert result["blocked_tool"] == tool_name
        assert result["session_id"] == sid
        assert isinstance(result["block_reasons"], list)
        assert result["block_reasons"]

        reasons = {r["reason"] for r in result["block_reasons"]}
        assert expected_reason in reasons
        assert "recovery_tool_call" in result
        assert result["recovery_tool_call"]["tool"] == expected_recovery_tool
        assert result["recovery_tool_call"]["params"]["session_id"] == sid

        session = SessionManager.instance().get(sid)
        assert session is not None
        assert any(
            t.get("tool") == tool_name and "strict_guardrail_block" in str(t.get("advisory", ""))
            for t in session.trace
        )

    def test_soft_mode_keeps_backwards_compatible_behavior(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        from drift import mcp_server

        self._write_agent_config(tmp_path, strict=False)
        monkeypatch.setattr(
            "drift.api.diff",
            lambda *_a, **_kw: {"status": "ok", "drift_detected": False},
        )

        start = json.loads(_run_tool(mcp_server.drift_session_start(path=str(tmp_path))))
        sid = start["session_id"]

        result = json.loads(_run_tool(mcp_server.drift_diff(session_id=sid)))

        assert result.get("error_code") != "DRIFT-6002"
        assert result.get("status") == "ok"
        assert result.get("pass") is None

    def test_strict_mode_config_change_is_applied_during_active_session(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Changing agent.strict_guardrails during a live session must take effect (#488)."""
        from drift import mcp_server

        self._write_agent_config(tmp_path, strict=False)
        monkeypatch.setattr(
            "drift.api.diff",
            lambda *_a, **_kw: {"status": "ok", "drift_detected": False},
        )

        start = json.loads(_run_tool(mcp_server.drift_session_start(path=str(tmp_path))))
        sid = start["session_id"]

        first = json.loads(_run_tool(mcp_server.drift_diff(session_id=sid)))
        assert first.get("status") == "ok"
        assert first.get("error_code") != "DRIFT-6002"
        assert first.get("pass") is None

        self._write_agent_config(tmp_path, strict=True)

        second = json.loads(_run_tool(mcp_server.drift_diff(session_id=sid)))
        assert second["type"] == "error"
        assert second["error_code"] == "DRIFT-6002"
        assert second["blocked_tool"] == "drift_diff"
        assert any(r["reason"] == "missing_scan_baseline" for r in second["block_reasons"])

    def test_strict_mode_blocks_session_end_with_open_tasks(self, tmp_path: Path) -> None:
        from drift import mcp_server
        from drift.session import SessionManager

        self._write_agent_config(tmp_path, strict=True)
        start = json.loads(_run_tool(mcp_server.drift_session_start(path=str(tmp_path))))
        sid = start["session_id"]

        session = SessionManager.instance().get(sid)
        assert session is not None
        session.selected_tasks = [{"id": "T-1", "title": "dummy"}]

        result = json.loads(_run_tool(mcp_server.drift_session_end(session_id=sid)))

        assert result["type"] == "error"
        assert result["error_code"] == "DRIFT-6002"
        assert result["blocked_tool"] == "drift_session_end"
        assert any(r["reason"] == "open_tasks_remaining" for r in result["block_reasons"])
        assert result["recovery_tool_call"]["tool"] == "drift_task_status"
        assert result.get("pass") is None
