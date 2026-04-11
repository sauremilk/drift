"""Negative context endpoint — anti-pattern warnings for agent consumption."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from drift.api._config import (
    _emit_api_telemetry,
    _load_config_cached,
    _warn_config_issues,
)
from drift.api_helpers import (
    DONE_NUDGE_SAFE,
    _error_response,
    _next_step_contract,
    build_drift_score_scope,
    shape_for_profile,
)


def negative_context(
    path: str | Path = ".",
    *,
    scope: str | None = None,
    target_file: str | None = None,
    max_items: int = 10,
    since_days: int = 90,
    disable_embeddings: bool = False,
    response_profile: str | None = None,
) -> dict[str, Any]:
    """Generate anti-pattern warnings from drift findings for agent consumption.

    Parameters
    ----------
    path:
        Repository root directory.
    scope:
        Filter by scope: ``"file"``, ``"module"``, or ``"repo"``.
    target_file:
        Restrict to items affecting a specific file (posix path).
    max_items:
        Maximum items to return (prioritized by severity).
    since_days:
        Days of git history to consider.
    disable_embeddings:
        Disable embedding-based analysis to keep response latency low.

    Returns
    -------
    dict
        Negative context response with anti-pattern items and agent instruction.
    """
    from drift.analyzer import analyze_repo
    from drift.negative_context import (
        findings_to_negative_context,
        negative_context_to_dict,
    )
    from drift.telemetry import timed_call

    repo_path = Path(path).resolve()
    elapsed_ms = timed_call()
    params: dict[str, Any] = {
        "path": str(path),
        "scope": scope,
        "target_file": target_file,
        "max_items": max_items,
        "disable_embeddings": disable_embeddings,
    }

    try:
        cfg = _load_config_cached(repo_path)
        _warn_config_issues(cfg)
        if disable_embeddings:
            cfg.embeddings_enabled = False
        analysis = analyze_repo(
            repo_path, config=cfg, since_days=since_days,
        )

        items = findings_to_negative_context(
            analysis.findings,
            scope=scope,
            target_file=target_file,
            max_items=max_items,
        )

        result: dict[str, Any] = {
            "status": "ok",
            "drift_score": round(analysis.drift_score, 3),
            "drift_score_scope": build_drift_score_scope(
                context=f"negative-context:{scope or 'repo'}",
                path=target_file,
            ),
            "items_returned": len(items),
            "items_total": len(analysis.findings),
            "scope_filter": scope,
            "target_file": target_file,
            "negative_context": [negative_context_to_dict(nc) for nc in items],
            "agent_instruction": (
                "These are known anti-patterns in this repository. "
                "Do NOT reproduce these patterns in new code. "
                "After generating code, call drift_nudge to verify "
                "you did not re-introduce any of these anti-patterns."
            ),
            **_next_step_contract(
                next_tool="drift_nudge",
                done_when=DONE_NUDGE_SAFE,
                fallback_tool="drift_scan",
                fallback_params={"response_detail": "concise"},
            ),
        }

        _emit_api_telemetry(
            tool_name="api.negative_context",
            params=params,
            status="ok",
            elapsed_ms=elapsed_ms(),
            result=result,
            error=None,
            repo_root=repo_path,
        )
        return shape_for_profile(result, response_profile)

    except Exception as exc:
        _emit_api_telemetry(
            tool_name="api.negative_context",
            params=params,
            status="error",
            elapsed_ms=elapsed_ms(),
            result=None,
            error=exc,
            repo_root=repo_path,
        )
        return _error_response("DRIFT-6001", str(exc), recoverable=True)
