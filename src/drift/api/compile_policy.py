"""compile_policy endpoint — task-specific operative policy for agents."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from drift.api._config import (
    _emit_api_telemetry,
    _load_config_cached,
    _warn_config_issues,
)
from drift.next_step_contract import (
    DONE_TASK_AND_NUDGE,
    _error_response,
    _next_step_contract,
)
from drift.response_shaping import _base_response, shape_for_profile
from drift.telemetry import timed_call

_log = logging.getLogger("drift")

DONE_POLICY_COMPILED = "compiled_policy.rules_count > 0 AND scope validated"


def compile_policy(
    path: str | Path = ".",
    *,
    task: str,
    task_spec_path: str | None = None,
    diff_ref: str | None = None,
    max_rules: int = 15,
    response_profile: str | None = None,
) -> dict[str, Any]:
    """Compile a task-specific policy package from repository state.

    Assembles scope boundaries, prohibitions, reuse targets, invariants,
    review triggers, and stop conditions into a compact, agentenlesbar
    policy that the agent applies before writing code.

    Parameters
    ----------
    path:
        Repository root directory.
    task:
        Natural-language task description.
    task_spec_path:
        Optional path to a TaskSpec YAML file for structured boundaries.
    diff_ref:
        Git ref for diff-based scope detection (e.g. ``"HEAD"``).
        If ``None``, git context is skipped.
    max_rules:
        Maximum number of rules in the output (default 15).
    response_profile:
        Optional profile for response shaping.

    Returns
    -------
    dict[str, Any]
        Structured response with compiled policy, agent instruction,
        and next-step contract.
    """
    from drift.policy_compiler import compile_policy as _compile
    from drift.policy_compiler import get_git_diff_paths

    repo_path = Path(path).resolve()
    elapsed_ms = timed_call()
    params: dict[str, Any] = {
        "path": str(path),
        "task": task,
        "task_spec_path": task_spec_path,
        "diff_ref": diff_ref,
        "max_rules": max_rules,
    }

    try:
        cfg = _load_config_cached(repo_path)
        _warn_config_issues(cfg)

        # --- Optional TaskSpec ---
        task_spec = None
        if task_spec_path:
            from drift.task_spec import TaskSpec

            task_spec = TaskSpec.from_yaml(Path(task_spec_path))

        # --- Optional git context ---
        git_diff_paths = None
        if diff_ref:
            git_diff_paths = get_git_diff_paths(repo_path, diff_ref)

        # --- Calibration data (best-effort) ---
        calibration_weights = None
        calibration_confidence = None
        try:
            cal_cfg = getattr(cfg, "calibration", None)
            if cal_cfg and getattr(cal_cfg, "enabled", False):
                from drift.calibration.profile_builder import build_profile

                profile = build_profile(repo_path, cfg)
                if profile:
                    cal_weights = getattr(profile, "calibrated_weights", None)
                    if cal_weights and hasattr(cal_weights, "as_dict"):
                        calibration_weights = cal_weights.as_dict()
                    calibration_confidence = getattr(
                        profile, "confidence_per_signal", None,
                    )
        except Exception:
            _log.debug("Calibration data not available — skipping")

        # --- Run compilation ---
        policy = _compile(
            task,
            repo_path,
            task_spec=task_spec,
            git_diff_paths=git_diff_paths,
            max_rules=max_rules,
            calibration_weights=calibration_weights,
            calibration_confidence=calibration_confidence,
        )

        # --- Build response ---
        policy_dict = policy.to_dict()
        has_rules = len(policy.rules) > 0

        result = _base_response(
            type="compile_policy",
            status="ok",
            **policy_dict,
        )

        # Next-step contract (ADR-024)
        if has_rules and any(r.enforcement == "block" for r in policy.rules):
            result.update(_next_step_contract(
                next_tool="drift_scan",
                done_when=DONE_TASK_AND_NUDGE,
                fallback_tool="drift_brief",
            ))
        else:
            result.update(_next_step_contract(
                next_tool="drift_negative_context",
                done_when=DONE_POLICY_COMPILED,
                fallback_tool="drift_nudge",
            ))

        _emit_api_telemetry(
            tool_name="api.compile_policy",
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
            tool_name="api.compile_policy",
            params=params,
            status="error",
            elapsed_ms=elapsed_ms(),
            result=None,
            error=exc,
            repo_root=repo_path,
        )
        return _error_response(
            "DRIFT-0099",
            f"Policy compilation failed: {exc}",
            recoverable=True,
        )
