"""Telemetry helpers for agent/tool usage tracking.

This module provides lightweight, file-based JSONL telemetry intended for
local evaluation and CI artifacts. Emission is opt-in via environment vars:

- DRIFT_TELEMETRY_ENABLED=1
- DRIFT_TELEMETRY_FILE=/path/to/events.jsonl (optional)

The payload intentionally captures only operational metadata and summary stats
(no source code blobs) to keep output compact and privacy-aware.
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_EVENT_SCHEMA_VERSION = "1.0"
_REDACT_KEYS = {"token", "password", "secret", "apikey", "api_key", "auth"}
_SESSION_RUN_ID: str | None = None


def _home_prefix_candidates() -> list[str]:
    """Return possible home-directory prefixes for path sanitization."""
    candidates = {str(Path.home())}

    for env_name in ("HOME", "USERPROFILE"):
        value = os.getenv(env_name, "").strip()
        if value:
            candidates.add(str(Path(value).expanduser()))

    home_drive = os.getenv("HOMEDRIVE", "").strip()
    home_path = os.getenv("HOMEPATH", "").strip()
    if home_drive and home_path:
        candidates.add(str(Path(f"{home_drive}{home_path}").expanduser()))

    out_set: set[str] = set()
    for candidate in candidates:
        trimmed = candidate.rstrip("\\/")
        if trimmed:
            out_set.add(trimmed)

    # Match the most specific home path first to avoid leaking deeper suffixes.
    return sorted(out_set, key=len, reverse=True)


def _mask_home_prefix(value: str) -> str:
    """Replace an absolute home-directory prefix with '~' for privacy."""
    for prefix in _home_prefix_candidates():
        parts = [p for p in re.split(r"[\\/]", prefix) if p]
        if not parts:
            continue
        pattern = r"^" + r"[\\/]+".join(re.escape(part) for part in parts) + r"(?=$|[\\/])"
        match = re.match(pattern, value, flags=re.IGNORECASE)
        if not match:
            continue

        suffix = value[match.end() :].lstrip("\\/")
        if not suffix:
            return "~"
        return "~/" + suffix.replace("\\", "/")

    return value


def _env_truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def telemetry_enabled() -> bool:
    """Return whether telemetry emission is enabled."""
    return _env_truthy("DRIFT_TELEMETRY_ENABLED")


def _default_telemetry_file(repo_root: Path | None = None) -> Path:
    base = repo_root if repo_root is not None else Path.cwd()
    return base / ".drift" / "agent_usage.jsonl"


def telemetry_file(repo_root: Path | None = None) -> Path:
    """Resolve telemetry output path from env or default location."""
    custom = os.getenv("DRIFT_TELEMETRY_FILE", "").strip()
    if custom:
        return Path(custom).expanduser().resolve()
    return _default_telemetry_file(repo_root)


def current_run_id() -> str:
    """Return a stable run id for the current process or configured env value."""
    global _SESSION_RUN_ID

    explicit = os.getenv("DRIFT_TELEMETRY_RUN_ID", "").strip()
    if explicit:
        return explicit
    if _SESSION_RUN_ID is None:
        _SESSION_RUN_ID = str(uuid.uuid4())
    return _SESSION_RUN_ID


def estimate_tokens(value: Any) -> int:
    """Approximate token count using a stable char/4 heuristic."""
    try:
        text = json.dumps(value, sort_keys=True, default=str)
    except Exception:
        text = str(value)
    return max(1, (len(text) + 3) // 4)


def _sanitize(value: Any) -> Any:
    """Recursively redact sensitive keys and trim overly long strings."""
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, inner in value.items():
            lowered = key.lower()
            if any(s in lowered for s in _REDACT_KEYS):
                out[key] = "***REDACTED***"
            else:
                out[key] = _sanitize(inner)
        return out
    if isinstance(value, list):
        return [_sanitize(v) for v in value]
    if isinstance(value, str):
        value = _mask_home_prefix(value)
        return value if len(value) <= 240 else value[:237] + "..."
    return value


def log_tool_event(
    *,
    tool_name: str,
    params: dict[str, Any],
    status: str,
    duration_ms: int,
    result: dict[str, Any] | None = None,
    error: str | None = None,
    repo_root: Path | None = None,
    run_id: str | None = None,
) -> None:
    """Append one telemetry event to JSONL file.

    This function must never raise to callers.
    """
    if not telemetry_enabled():
        return

    try:
        ts = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        safe_params = _sanitize(params)
        safe_result = _sanitize(result) if result is not None else None

        event = {
            "schema_version": _EVENT_SCHEMA_VERSION,
            "event_type": "drift_tool_call",
            "event_id": str(uuid.uuid4()),
            "run_id": run_id or current_run_id(),
            "timestamp": ts,
            "tool_name": tool_name,
            "status": status,
            "duration_ms": duration_ms,
            "params": safe_params,
            "input_tokens_est": estimate_tokens(safe_params),
            "output_tokens_est": estimate_tokens(safe_result) if safe_result is not None else 0,
            "result_summary": {
                "keys": sorted(safe_result.keys())[:20] if isinstance(safe_result, dict) else [],
                "has_error": bool(
                    isinstance(safe_result, dict) and safe_result.get("type") == "error"
                ),
            },
            "error": error,
        }

        out_file = telemetry_file(repo_root)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        with out_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True, default=str) + "\n")
    except Exception:
        # Telemetry should never impact core analyzer behavior.
        return


def timed_call() -> Callable[[], int]:
    """Return a closure that computes elapsed milliseconds."""
    started = time.perf_counter()

    def _elapsed_ms() -> int:
        return int((time.perf_counter() - started) * 1000)

    return _elapsed_ms
