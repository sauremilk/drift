"""Regression tests for MCP client-disconnect handling (#376).

Verifies that in-flight _run_api_tool calls pass abandon_on_cancel=True so
that when an MCP client disconnects mid-call:
  1. The async coroutine receives CancelledError immediately (does not block
     the event loop waiting for the worker thread to finish).
  2. Session-state mutations after ``await _run_api_tool(...)`` are never
     reached, preventing half-applied state in a partially updated session.
"""

from __future__ import annotations

import asyncio
from unittest.mock import patch


class TestRunApiToolAbandonOnCancel:
    """_run_api_tool must pass abandon_on_cancel=True to _run_sync_in_thread."""

    def test_run_api_tool_uses_abandon_on_cancel_true(self) -> None:
        """CancelledError must propagate without waiting for the worker thread."""
        called_with: dict = {}

        async def _fake_run_sync_in_thread(fn, *, abandon_on_cancel=False):
            called_with["abandon_on_cancel"] = abandon_on_cancel
            return fn()

        with patch("drift.mcp_utils._run_sync_in_thread", _fake_run_sync_in_thread):
            from drift.mcp_utils import _run_api_tool
            asyncio.run(_run_api_tool("test_tool", lambda: {"ok": True}))

        assert called_with.get("abandon_on_cancel") is True, (
            "_run_api_tool must call _run_sync_in_thread with abandon_on_cancel=True "
            "so that client-disconnect CancelledError is raised immediately (#376)"
        )

    def test_cancelled_error_prevents_session_mutation(self) -> None:
        """Session.touch() must not be called when the task is cancelled."""
        session_touched = []

        class _FakeSession:
            last_scan_score = None

            def touch(self):
                session_touched.append(True)

        async def _task():
            import drift.mcp_utils as mu

            # Simulate: thread callable always raises CancelledError on the async side
            async def _cancelling_run_sync(fn, *, abandon_on_cancel=False):
                raise asyncio.CancelledError

            with patch("drift.mcp_utils._run_sync_in_thread", _cancelling_run_sync):
                # This mimics _run_api_tool raising CancelledError
                session = _FakeSession()
                try:
                    await mu._run_api_tool("drift_scan", lambda: {"score": 0.5})
                    # If we reach here, mutations would happen:
                    session.last_scan_score = 0.5
                    session.touch()
                except (asyncio.CancelledError, BaseException):
                    # CancelledError must NOT be swallowed
                    pass

        asyncio.run(_task())

        assert not session_touched, (
            "session.touch() must not be called when _run_api_tool raises CancelledError (#376)"
        )


class TestRunSyncInThreadSignature:
    """_run_sync_in_thread must accept and forward abandon_on_cancel keyword."""

    def test_accepts_abandon_on_cancel_keyword(self) -> None:
        """Verify that _run_sync_in_thread signature exposes abandon_on_cancel."""
        import inspect

        from drift.mcp_server import _run_sync_in_thread

        sig = inspect.signature(_run_sync_in_thread)
        params = sig.parameters
        assert "abandon_on_cancel" in params, (
            "_run_sync_in_thread must have an abandon_on_cancel parameter (#376)"
        )
        assert params["abandon_on_cancel"].default is False, (
            "abandon_on_cancel default must remain False to avoid breaking "
            "callers that intentionally want to wait for completion"
        )

    def test_abandon_on_cancel_true_runs_callable(self) -> None:
        """With abandon_on_cancel=True the callable must still execute normally."""
        from drift.mcp_server import _run_sync_in_thread

        result = asyncio.run(_run_sync_in_thread(lambda: 42, abandon_on_cancel=True))
        assert result == 42


class TestDriftFeedbackAndCalibrateAbandonOnCancel:
    """drift_feedback and drift_calibrate must also use abandon_on_cancel=True."""

    def _collect_abandon_flag(self, fn_name: str) -> bool | None:
        """Check that fn_name (or its router handler) passes abandon_on_cancel=True."""
        import ast
        from pathlib import Path

        # After the mcp_server refactor (#378), tool functions delegate to router
        # modules. Map the MCP tool name to the handler function in its router.
        _router_map = {
            "drift_feedback": ("src/drift/mcp_router_calibration.py", "run_feedback"),
            "drift_calibrate": ("src/drift/mcp_router_calibration.py", "run_calibrate"),
        }

        candidates = [("src/drift/mcp_server.py", fn_name)]
        if fn_name in _router_map:
            candidates.append(_router_map[fn_name])

        for src_path, search_fn in candidates:
            src = Path(src_path).read_text(encoding="utf-8")
            tree = ast.parse(src)

            for node in ast.walk(tree):
                is_fn = isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef))
                if is_fn and node.name == search_fn:
                    for sub in ast.walk(node):
                        if isinstance(sub, ast.Call):
                            func = sub.func
                            if isinstance(func, ast.Name) and func.id == "_run_sync_in_thread":
                                for kw in sub.keywords:
                                    if kw.arg == "abandon_on_cancel" and isinstance(  # noqa: SIM102
                                        kw.value, ast.Constant
                                    ):
                                        return kw.value.value
        return None

    def test_drift_feedback_uses_abandon_on_cancel_true(self) -> None:
        flag = self._collect_abandon_flag("drift_feedback")
        assert flag is True, (
            "drift_feedback._run_sync_in_thread call must pass abandon_on_cancel=True (#376)"
        )

    def test_drift_calibrate_uses_abandon_on_cancel_true(self) -> None:
        flag = self._collect_abandon_flag("drift_calibrate")
        assert flag is True, (
            "drift_calibrate._run_sync_in_thread call must pass abandon_on_cancel=True (#376)"
        )
