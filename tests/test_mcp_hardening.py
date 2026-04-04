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

        result = json.loads(_run_tool(mcp_server.drift_scan(path=".")))

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


class TestMcpToolAsyncInvariant:
    """All MCP tool functions must be async to avoid blocking the event loop."""

    def test_all_exported_mcp_tools_are_async(self) -> None:
        from drift.mcp_server import _EXPORTED_MCP_TOOLS

        for tool in _EXPORTED_MCP_TOOLS:
            assert inspect.iscoroutinefunction(tool), (
                f"{tool.__name__} must be async def — sync tool functions "
                f"block the MCP event loop and cause session hangs"
            )

    def test_all_tools_use_anyio_not_asyncio_to_thread(self) -> None:
        """MCP tools must use anyio.to_thread.run_sync, not asyncio.to_thread.

        asyncio.to_thread is not compatible with trio and breaks the
        transport-agnostic contract of the MCP server.
        """
        from drift.mcp_server import _EXPORTED_MCP_TOOLS

        for tool in _EXPORTED_MCP_TOOLS:
            source = inspect.getsource(tool)
            assert "asyncio.to_thread" not in source, (
                f"{tool.__name__} uses asyncio.to_thread — "
                f"must use anyio.to_thread.run_sync for backend portability"
            )


class TestMcpToolErrorEnvelopes:
    """Every MCP tool must return a JSON error envelope on exception, never propagate."""

    @pytest.mark.parametrize(
        "tool_name",
        [
            "drift_diff",
            "drift_explain",
            "drift_validate",
            "drift_nudge",
            "drift_fix_plan",
            "drift_negative_context",
        ],
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
            "drift_fix_plan": "drift.api.fix_plan",
            "drift_negative_context": "drift.api.negative_context",
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
            "(would deadlock MCP stdio on Windows):\n"
            + "\n".join(f"  - {v}" for v in violations)
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

    def test_anyio_import_guarded_for_optional_dependency(self) -> None:
        """anyio must not be imported at module level outside the try/except guard.

        ``import anyio`` must live inside the same try/except that guards
        the ``mcp`` import.  Otherwise ``drift mcp --list`` and
        ``drift mcp --schema`` crash with ``ModuleNotFoundError`` when the
        ``mcp`` extra is not installed, instead of using the fallback.
        """
        import ast

        src_file = Path(__file__).resolve().parent.parent / "src" / "drift" / "mcp_server.py"
        tree = ast.parse(src_file.read_text(encoding="utf-8"), filename=str(src_file))

        for node in ast.iter_child_nodes(tree):
            # Bare `import anyio` at module level is forbidden
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name != "anyio", (
                        f"mcp_server.py:{node.lineno} — bare `import anyio` at module level "
                        "breaks --list/--schema without MCP extra; "
                        "must be inside the try/except ImportError guard"
                    )
