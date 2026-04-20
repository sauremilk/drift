"""API endpoint: capture_intent — extract and persist a structured intent."""

from __future__ import annotations

import time as _time
from pathlib import Path
from typing import Any

from drift.api._config import _emit_api_telemetry, _log
from drift.intent._storage import save_intent  # drift:ignore[PHR]
from drift.intent.capture import extract_intent  # drift:ignore[PHR]


def capture_intent(*, raw: str, path: str) -> dict[str, Any]:
    """Extract a structured intent from a raw user input string.

    Persists the intent to .drift/intents/<intent_id>.json under ``path``.

    Args:
        raw: The natural-language user input.
        path: Repo root path (used for local storage).

    Returns:
        A dict with intent_id, summary, required_features, output_type,
        confidence, clarification_needed, clarification_question,
        next_tool_call, agent_instruction.
    """
    if not raw or not raw.strip():
        return {"error": "raw must be a non-empty string"}
    if not path:
        return {"error": "path must be a non-empty string"}
    t0 = _time.monotonic()
    repo_root = Path(path)
    error: Exception | None = None
    result: dict[str, Any] = {}
    try:
        intent = extract_intent(raw)
        save_intent(intent, repo_root=repo_root)
        result = intent.model_dump(mode="json")
        result["next_tool_call"] = (
            f"drift_verify_intent(intent_id='{intent.intent_id}', artifact_path='<path-to-build>')"
        )
        result["agent_instruction"] = (
            "Intent captured and saved. "
            "Call verify_intent after the build is complete to check if the intent is fulfilled."
        )
        if intent.clarification_needed:
            result["agent_instruction"] = (
                f"Clarification needed before building: {intent.clarification_question}"
            )
    except Exception as exc:
        error = exc
        _log.error("capture_intent failed: %s", exc)
        result = {"error": str(exc)}
    finally:
        elapsed = int((_time.monotonic() - t0) * 1000)
        _emit_api_telemetry(
            tool_name="capture_intent",
            params={"raw_length": len(raw), "path": path},
            status="error" if error else "ok",
            elapsed_ms=elapsed,
            result=result if not error else None,
            error=error,
            repo_root=repo_root if repo_root.exists() else None,
        )
    return result
