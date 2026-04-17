"""Bounded-context router for calibration MCP tool implementations.

Handles the business logic for ``drift_feedback`` and ``drift_calibrate``
tools, keeping them out of the transport/registration layer in mcp_server.py.
"""

from __future__ import annotations

import json

from drift.mcp_enrichment import _enrich_response_with_session
from drift.mcp_orchestration import _resolve_session
from drift.mcp_utils import _run_sync_in_thread


async def run_feedback(
    *,
    signal: str,
    file_path: str,
    verdict: str,
    reason: str,
    start_line: int,
    path: str,
    session_id: str,
) -> str:
    """Record TP/FP/FN feedback for a finding to improve signal calibration."""
    from pathlib import Path as _Path

    from drift.api_helpers import _error_response
    from drift.calibration.feedback import FeedbackEvent, record_feedback, resolve_feedback_paths
    from drift.config import SIGNAL_ABBREV, DriftConfig

    session = _resolve_session(session_id)

    def _sync() -> str:
        repo = _Path(path).resolve()
        cfg = DriftConfig.load(repo)
        resolved = SIGNAL_ABBREV.get(signal.upper(), signal)
        v = verdict.lower().strip()
        if v not in ("tp", "fp", "fn"):
            error = _error_response(
                "DRIFT-1003",
                f"Invalid verdict '{verdict}'. Use tp, fp, or fn.",
                invalid_fields=[
                    {
                        "field": "verdict",
                        "value": verdict,
                        "expected": ["tp", "fp", "fn"],
                    }
                ],
                suggested_fix={
                    "verdict": "tp",
                    "valid_values": ["tp", "fp", "fn"],
                },
                recoverable=True,
            )
            error["tool"] = "drift_feedback"
            return json.dumps(error)
        event = FeedbackEvent(
            signal_type=resolved,
            file_path=file_path,
            verdict=v,  # type: ignore[arg-type]
            source="user",
            start_line=start_line if start_line > 0 else None,
            evidence={"reason": reason} if reason else {},
        )
        feedback_path, _local_feedback_path, _shared_feedback_path = resolve_feedback_paths(
            repo, cfg
        )
        record_feedback(feedback_path, event)
        return json.dumps({
            "status": "recorded",
            "signal": resolved,
            "file": file_path,
            "verdict": v,
            "finding_id": event.finding_id,
        })

    raw = await _run_sync_in_thread(_sync, abandon_on_cancel=True)
    if session:
        session.touch()
    return _enrich_response_with_session(raw, session, "drift_feedback")


async def run_calibrate(
    *,
    path: str,
    dry_run: bool,
    session_id: str,
) -> str:
    """Compute calibrated signal weights from accumulated feedback evidence."""
    from pathlib import Path as _Path

    from drift.calibration.feedback import load_feedback, resolve_feedback_paths
    from drift.calibration.profile_builder import build_profile
    from drift.config import DriftConfig, SignalWeights

    session = _resolve_session(session_id)

    def _sync() -> str:
        repo = _Path(path).resolve()
        cfg = DriftConfig.load(repo)
        feedback_path, _local_feedback_path, _shared_feedback_path = resolve_feedback_paths(
            repo, cfg
        )
        events = load_feedback(feedback_path)

        if not events:
            return json.dumps({
                "status": "no_data",
                "message": "No feedback evidence found. Use drift_feedback to record evidence.",
                "agent_instruction": "Record TP/FP/FN feedback for findings before calibrating.",
            })

        result = build_profile(
            events,
            cfg.weights,
            min_samples=cfg.calibration.min_samples,
            fn_boost_factor=cfg.calibration.fn_boost_factor,
        )
        diff = result.weight_diff(SignalWeights())

        if not dry_run and diff:
            import yaml as _yaml  # type: ignore[import-untyped]

            config_path = DriftConfig._find_config_file(repo) or repo / "drift.yaml"
            if config_path.exists():
                data = _yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            else:
                data = {}
            default_dict = SignalWeights().as_dict()
            custom: dict[str, float] = {}
            for key, val in result.calibrated_weights.as_dict().items():
                if abs(val - default_dict.get(key, 0.0)) > 0.0001:
                    custom[key] = round(val, 6)
            if custom:
                data["weights"] = custom
            config_path.write_text(
                _yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )

        return json.dumps(
            {
                "status": "calibrated" if diff else "no_change",
                "total_events": result.total_events,
                "signals_with_data": result.signals_with_data,
                "weight_changes": diff,
                "dry_run": dry_run,
                "written": not dry_run and bool(diff),
                "agent_instruction": (
                    "Review the weight changes. Use dry_run=false to apply, "
                    "or record more feedback for higher confidence."
                    if dry_run
                    else "Weights written to drift.yaml."
                ),
            },
            default=str,
        )

    raw = await _run_sync_in_thread(_sync, abandon_on_cancel=True)
    if session:
        session.touch()
    return _enrich_response_with_session(raw, session, "drift_calibrate")
