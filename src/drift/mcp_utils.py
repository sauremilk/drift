"""Shared utility functions used by all MCP tool routers.

This module consolidates helpers that were previously duplicated across
mcp_server.py, mcp_router_analysis.py, mcp_router_repair.py, and
mcp_router_session.py.  Import from here instead of defining local copies.
"""

from __future__ import annotations

import asyncio
import contextlib
import io
import json
import logging
import uuid
from typing import Any, cast

try:
    import anyio

    _ANYIO_AVAILABLE = True
except ImportError:
    anyio = None  # type: ignore[assignment]
    _ANYIO_AVAILABLE = False

# ---------------------------------------------------------------------------
# Enum / constant sets for parameter validation
# ---------------------------------------------------------------------------

_RESPONSE_DETAIL_VALUES = frozenset({"concise", "detailed"})
_RESPONSE_PROFILE_VALUES = frozenset({"planner", "coder", "verifier", "merge_readiness"})
_FAIL_ON_VALUES = frozenset({"critical", "high", "medium", "low", "none"})
_AUTOMATION_FIT_MIN_VALUES = frozenset({"low", "medium", "high"})

logger = logging.getLogger("drift")


# ---------------------------------------------------------------------------
# CSV parsing
# ---------------------------------------------------------------------------


def _parse_csv_ids(raw: str | None) -> list[str] | None:
    """Split a comma-separated string into a list of non-empty stripped values."""
    if not raw:
        return None
    values = [part.strip() for part in raw.split(",") if part.strip()]
    return values or None


# ---------------------------------------------------------------------------
# Async thread helpers (anyio-aware for proper MCP client cancellation)
# ---------------------------------------------------------------------------


async def _run_sync_in_thread(
    fn: Any,
    *args: object,
    abandon_on_cancel: bool = False,
) -> Any:
    """Run a sync callable in a worker thread with optional anyio support.

    When ``abandon_on_cancel=True``, a disconnecting MCP client triggers
    CancelledError immediately instead of blocking the event loop until the
    worker thread finishes.
    """
    if _ANYIO_AVAILABLE and anyio is not None:
        return await anyio.to_thread.run_sync(fn, *args, abandon_on_cancel=abandon_on_cancel)
    return await asyncio.to_thread(fn, *args)


async def _run_sync_with_timeout(
    fn: Any,
    timeout_seconds: float,
    *args: object,
) -> Any:
    """Run a sync callable with timeout, even when anyio is unavailable."""
    if _ANYIO_AVAILABLE and anyio is not None:
        with anyio.fail_after(timeout_seconds):
            return await anyio.to_thread.run_sync(fn, *args, abandon_on_cancel=True)
    return await asyncio.wait_for(
        asyncio.to_thread(fn, *args),
        timeout=timeout_seconds,
    )


def _is_broken_internal_drift_module(exc: BaseException) -> bool:
    """Return True when an ImportError refers to an internal drift.* module.

    This distinguishes broken-installation errors (e.g. ``No module named
    'drift.output'``) from missing-optional-extra errors (e.g. ``No module
    named 'mcp'``) so callers can produce a more actionable message.
    """
    if not isinstance(exc, ImportError):
        return False
    missing = getattr(exc, "name", None) or ""
    return missing.startswith("drift.") or missing == "drift"


def _broken_internal_module_error(tool_name: str, exc: ImportError) -> dict[str, Any]:
    """Build a user-friendly DRIFT-5001 payload for a broken internal module."""
    from drift.api_helpers import _error_response

    missing = getattr(exc, "name", None) or str(exc)
    error = _error_response(
        "DRIFT-5001",
        (
            f"Drift installation appears incomplete: module '{missing}' "
            f"is not importable. "
            f"Please reinstall: pip install --upgrade 'drift-analyzer[mcp]'"
        ),
        recoverable=False,
    )
    error["tool"] = tool_name
    error["broken_module"] = missing
    error["agent_instruction"] = (
        f"The tool '{tool_name}' failed because a required Drift internal module "
        f"('{missing}') could not be imported. "
        "Ask the user to reinstall Drift: pip install --upgrade 'drift-analyzer[mcp]'"
    )
    return error


async def _run_api_tool(tool_name: str, api_fn: Any, **kwargs: Any) -> str:
    """Run an API function in a thread and return a JSON string.

    Uses abandon_on_cancel so MCP client disconnects propagate immediately.
    """

    request_id = str(uuid.uuid4())
    logger.debug("[%s] %s called params=%s", request_id, tool_name, kwargs)

    def _sync() -> str:
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                result = api_fn(**kwargs)
            if isinstance(result, dict):
                result.setdefault("request_id", request_id)
            else:
                result = {
                    "type": "ok",
                    "tool": tool_name,
                    "request_id": request_id,
                    "result": result,
                }
            return json.dumps(result, default=str)
        except Exception as exc:
            from drift.api_helpers import _error_response

            logger.warning(
                "[%s] DRIFT-5001 from %s: %r",
                request_id,
                tool_name,
                exc,
                exc_info=True,
            )
            error = _error_response("DRIFT-5001", str(exc), recoverable=True)
            error["tool"] = tool_name
            error["request_id"] = request_id
            return json.dumps(error, default=str)

    return cast(str, await _run_sync_in_thread(_sync, abandon_on_cancel=True))


# ---------------------------------------------------------------------------
# Parameter validation
# ---------------------------------------------------------------------------


def _validate_enum_param(
    param_name: str,
    value: str | None,
    valid_values: frozenset[str],
    tool_name: str,
    *,
    required: bool = False,
) -> dict[str, Any] | None:
    """Validate a single enum parameter at the MCP tool boundary.

    Returns a structured DRIFT-1003 error dict if invalid, or None if valid.
    Allows None when ``required=False``.
    """
    if value is None:
        if required:
            from drift.api_helpers import _error_response

            return _error_response(
                "DRIFT-1003",
                f"Missing required parameter '{param_name}' in {tool_name}",
                invalid_fields=[
                    {
                        "field": param_name,
                        "value": None,
                        "reason": f"Required. Expected one of: {', '.join(sorted(valid_values))}",
                    }
                ],
                suggested_fix={
                    "action": f"Supply a valid value for '{param_name}'.",
                    "valid_values": sorted(valid_values),
                },
            )
        return None
    normalised = str(value).strip().lower()
    if normalised not in valid_values:
        from drift.api_helpers import _error_response

        return _error_response(
            "DRIFT-1003",
            f"Invalid value '{value}' for '{param_name}' in {tool_name}",
            invalid_fields=[
                {
                    "field": param_name,
                    "value": value,
                    "reason": f"Expected one of: {', '.join(sorted(valid_values))}",
                }
            ],
            suggested_fix={
                "action": f"Use a supported value for '{param_name}'.",
                "valid_values": sorted(valid_values),
                "example_call": {
                    "tool": tool_name,
                    "params": {param_name: next(iter(sorted(valid_values)))},
                },
            },
        )
    return None
