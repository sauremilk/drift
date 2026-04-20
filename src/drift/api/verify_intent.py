"""API endpoint: verify_intent — check artifact against captured intent."""

from __future__ import annotations

import time as _time
from pathlib import Path
from typing import Any

from drift.api._config import _emit_api_telemetry, _log
from drift.intent._storage import load_intent  # drift:ignore[PHR]
from drift.intent.verify import verify_artifact


def verify_intent(*, intent_id: str, artifact_path: str, path: str) -> dict[str, Any]:
    """Verify that a build artifact fulfils a previously captured intent.

    Args:
        intent_id: The intent ID returned by capture_intent.
        artifact_path: Path to the built artifact (file or directory).
        path: Repo root path (used for intent storage lookup).

    Returns:
        A dict with status, confidence, missing[], agent_feedback,
        iteration, next_tool_call, agent_instruction.
    """
    t0 = _time.monotonic()
    repo_root = Path(path)
    error: Exception | None = None
    result: dict[str, Any] = {}
    try:
        intent = load_intent(intent_id, repo_root=repo_root)
        if intent is None:
            return {
                "error": f"Intent '{intent_id}' not found. Call capture_intent first.",
                "intent_id": intent_id,
            }
        verify_result = verify_artifact(
            intent=intent,
            artifact_path=Path(artifact_path),
        )
        result = verify_result.model_dump(mode="json")
        result["intent_id"] = intent_id
        if verify_result.status == "fulfilled":
            result["next_tool_call"] = "DONE — intent fulfilled, deliver result to user"
            result["agent_instruction"] = (
                "The build artifact fulfils the user's intent. "
                "Deliver the result to the user in plain language."
            )
        else:
            result["next_tool_call"] = (
                f"drift_feedback_for_agent(intent_id='{intent_id}')"
            )
            result["agent_instruction"] = (
                f"{len(verify_result.missing)} feature(s) missing. "
                "Call feedback_for_agent to get a prioritised action list, "
                "then fix and call verify_intent again."
            )
    except Exception as exc:
        error = exc
        _log.error("verify_intent failed: %s", exc)
        result = {"error": str(exc), "intent_id": intent_id}
    finally:
        elapsed = int((_time.monotonic() - t0) * 1000)
        _emit_api_telemetry(
            tool_name="verify_intent",
            params={"intent_id": intent_id, "artifact_path": artifact_path},
            status="error" if error else "ok",
            elapsed_ms=elapsed,
            result=result if not error else None,
            error=error,
            repo_root=repo_root if repo_root.exists() else None,
        )
    return result
