"""API endpoint: feedback_for_agent — prioritised action list from verify state."""

from __future__ import annotations

import time as _time
from pathlib import Path
from typing import Any

from drift.api._config import _emit_api_telemetry, _log
from drift.intent._storage import load_intent  # drift:ignore[PHR]
from drift.intent.feedback import generate_feedback
from drift.intent.verify import verify_artifact


def feedback_for_agent(*, intent_id: str, path: str, artifact_path: str) -> dict[str, Any]:
    """Return a prioritised action list based on the current verify state.

    Re-runs verify_artifact internally so callers get fresh, consistent feedback.

    Args:
        intent_id: The intent ID returned by capture_intent.
        path: Repo root path.
        artifact_path: Path to the current build artifact.

    Returns:
        A dict with actions[], estimated_complexity, intent_id,
        next_tool_call, agent_instruction.
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
        verify_result = verify_artifact(intent=intent, artifact_path=Path(artifact_path))
        feedback = generate_feedback(verify_result)
        result = feedback.model_dump(mode="json")
        result["intent_id"] = intent_id
        result["verify_status"] = verify_result.status
        result["missing"] = verify_result.missing
        result["next_tool_call"] = (
            f"drift_verify_intent(intent_id='{intent_id}', artifact_path='{artifact_path}')"
        )
        result["agent_instruction"] = (
            f"Apply the {len(feedback.actions)} action(s) listed, then call verify_intent again."
            if feedback.actions
            else "Intent already fulfilled — no actions needed."
        )
    except Exception as exc:
        error = exc
        _log.error("feedback_for_agent failed: %s", exc)
        result = {"error": str(exc), "intent_id": intent_id}
    finally:
        elapsed = int((_time.monotonic() - t0) * 1000)
        _emit_api_telemetry(
            tool_name="feedback_for_agent",
            params={"intent_id": intent_id, "path": path},
            status="error" if error else "ok",
            elapsed_ms=elapsed,
            result=result if not error else None,
            error=error,
            repo_root=repo_root if repo_root.exists() else None,
        )
    return result
