"""MCP session orchestration, guardrails, hypothesis management and pre-call advisory.

Extracted from ``mcp_server.py`` to separate session-management logic from
MCP tool registration and transport wiring.

Decision: ADR-022
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Session helpers — resolve session defaults and enrich responses
# ---------------------------------------------------------------------------


def _resolve_session(session_id: str | None) -> Any:
    """Look up an active session. Returns ``DriftSession`` or ``None``."""
    if not session_id:
        return None
    from drift.session import SessionManager

    session = SessionManager.instance().get(session_id)
    if session is not None:
        session.begin_call()
    return session


def _session_defaults(session: Any, kwargs: dict[str, Any]) -> dict[str, Any]:
    """Apply session scope defaults for params that the caller omitted."""
    if session is None:
        return kwargs
    out = dict(kwargs)
    if not out.get("path") or out["path"] == ".":
        out["path"] = session.repo_path
    if out.get("signals") is None and session.signals:
        out["signals"] = session.signals
    if out.get("exclude_signals") is None and session.exclude_signals:
        out["exclude_signals"] = session.exclude_signals
    if out.get("target_path") is None and session.target_path:
        out["target_path"] = session.target_path
    return out


def _update_session_from_scan(session: Any, result: dict[str, Any]) -> None:
    """Push scan results into the session state."""
    if session is None:
        return
    session.last_scan_score = result.get("drift_score")
    session.last_scan_top_signals = result.get("top_signals")
    finding_count = result.get("finding_count")
    if finding_count is None:
        findings = result.get("findings")
        if isinstance(findings, list):
            finding_count = len(findings)
    session.last_scan_finding_count = finding_count
    if session.score_at_start is None:
        session.score_at_start = result.get("drift_score")
    # Agent-effectiveness: record snapshot for quality-drift detection
    score = result.get("drift_score")
    if score is not None and finding_count is not None:
        session.snapshot_run(score, finding_count)
    # Auto-advance phase from init → scan
    if session.phase == "init":
        session.advance_phase("scan")
    session.touch()


def _update_session_from_fix_plan(session: Any, result: dict[str, Any]) -> None:
    """Push fix-plan tasks into the session state."""
    if session is None:
        return
    tasks = result.get("tasks")
    if tasks:
        session.selected_tasks = tasks
    # Auto-advance phase from scan → fix
    if session.phase in ("init", "scan"):
        session.advance_phase("fix")
    session.touch()


def _update_session_from_brief(session: Any, result: dict[str, Any]) -> None:
    """Push brief guardrails into the session state."""
    if session is None:
        return
    session.guardrails = result.get("guardrails")
    session.guardrails_prompt_block = result.get("guardrails_prompt_block")
    session.touch()


def _update_session_from_diff(session: Any, result: dict[str, Any]) -> None:
    """Track score delta from diff results."""
    if session is None:
        return
    score_after = result.get("score_after")
    if score_after is not None:
        session.last_scan_score = score_after
    # Auto-advance phase to verify
    if session.phase in ("fix",):
        session.advance_phase("verify")
    # Record snapshot for quality-drift detection
    finding_count = result.get("findings_after_count")
    if score_after is not None and finding_count is not None:
        session.snapshot_run(score_after, finding_count)
    session.touch()


def _update_session_from_verification_result(session: Any, result: dict[str, Any]) -> None:
    """Record outcome-centric verification KPIs in session metrics.

    Duplicate payloads are ignored to keep counters deterministic when callers
    retry with identical verification data.
    """
    if session is None or not isinstance(result, dict):
        return

    changed_files = result.get("changed_files")
    changed_file_count = result.get("changed_file_count")
    if changed_file_count is None and isinstance(changed_files, list):
        changed_file_count = len(changed_files)

    payload_fingerprint = json.dumps(
        {
            "changed_files": (
                sorted(changed_files)
                if isinstance(changed_files, list)
                else changed_files
            ),
            "changed_file_count": changed_file_count,
            "changed_loc": result.get("changed_loc", result.get("loc_changed", 0)),
            "resolved_count": result.get("resolved_count", 0),
            "new_finding_count": result.get("new_finding_count", 0),
        },
        sort_keys=True,
        default=str,
    )

    seen = getattr(session, "_seen_verification_payload_hashes", None)
    if isinstance(seen, set):
        if payload_fingerprint in seen:
            return
        seen.add(payload_fingerprint)

    metrics = getattr(session, "metrics", None)
    if metrics is None or not hasattr(metrics, "record_verification"):
        return

    metrics.record_verification(
        changed_file_count=int(changed_file_count or 0),
        loc_changed=int(result.get("changed_loc", result.get("loc_changed", 0)) or 0),
        resolved_count=int(result.get("resolved_count", 0) or 0),
        new_finding_count=int(result.get("new_finding_count", 0) or 0),
    )
    session.touch()


def _session_called_tools(session: Any) -> set[str]:
    """Return tools already executed or inferable from session state."""
    if session is None:
        return set()

    called = {
        str(item.get("tool"))
        for item in (session.trace or [])
        if isinstance(item, dict) and item.get("tool")
    }

    # Inference fallback for sessions where not all steps are traced
    # (e.g. session_start autopilot or out-of-band updates).
    if session.phase != "init":
        called.add("drift_validate")
    if session.guardrails is not None:
        called.add("drift_brief")
    if session.last_scan_score is not None or session.last_scan_finding_count is not None:
        called.add("drift_scan")
    if session.selected_tasks:
        called.add("drift_fix_plan")

    return called


def _effective_profile(session: Any, explicit_profile: str | None) -> str | None:
    """Resolve response profile from explicit input or session phase."""
    if explicit_profile:
        return explicit_profile
    if session is None:
        return None

    phase = getattr(session, "phase", None)
    if not isinstance(phase, str):
        return None
    phase_map: dict[str, str] = {
        "init": "planner",
        "scan": "planner",
        "fix": "coder",
        "verify": "verifier",
        "done": "merge_readiness",
    }
    return phase_map.get(phase)


# ---------------------------------------------------------------------------
# Semantic pre-call advisory (SA-001 .. SA-004)
# ---------------------------------------------------------------------------


def _semantic_pre_call_advisory(tool_name: str, session: Any) -> str:
    """Return semantic, workflow-aware advisory hints (SA-001..SA-004)."""
    selected_tasks = getattr(session, "selected_tasks", None) or []
    completed_task_ids = set(getattr(session, "completed_task_ids", []) or [])

    # SA-001: blocker-awareness for unresolved dependencies.
    if tool_name in {"drift_nudge", "drift_task_complete"} and selected_tasks:
        unresolved: list[str] = []
        for task in selected_tasks:
            for dep in task.get("depends_on", []) or []:
                if dep not in completed_task_ids:
                    unresolved.append(str(dep))
        if unresolved:
            uniq = sorted(set(unresolved))
            return f"Unresolved dependency detected: {', '.join(uniq)}."

    trace = getattr(session, "trace", None) or []

    # SA-002: repeated scan in fix phase deviates from canonical flow.
    if tool_name == "drift_scan" and getattr(session, "phase", "") == "fix":
        repeated_fix_scan = any(
            isinstance(entry, dict)
            and entry.get("tool") == "drift_scan"
            and entry.get("phase") == "fix"
            for entry in trace
        )
        if repeated_fix_scan:
            return (
                "Canonical-pattern deviation: repeated scan in fix phase. "
                "Prefer drift_nudge for inner-loop feedback."
            )

    # SA-003: changed files outside diagnostic hypotheses.
    if tool_name == "drift_nudge":
        hypotheses = getattr(session, "diagnostic_hypotheses", {}) or {}
        if hypotheses:
            allowed_files: set[str] = set()
            for hyp in hypotheses.values():
                if isinstance(hyp, dict):
                    for path in hyp.get("affected_files", []) or []:
                        allowed_files.add(str(path))

            changed_files: set[str] = set()
            for entry in reversed(trace):
                if not isinstance(entry, dict):
                    continue
                raw_changed = entry.get("changed_files")
                if isinstance(raw_changed, str) and raw_changed:
                    changed_files.add(raw_changed)
                elif isinstance(raw_changed, list):
                    changed_files.update(str(item) for item in raw_changed)
                if changed_files:
                    break

            if changed_files and allowed_files and any(
                changed not in allowed_files for changed in changed_files
            ):
                return (
                    "Hypothesis scope creep detected: changed file outside "
                    "diagnostic hypothesis."
                )

    # SA-004: warn on potential rework against completed task files.
    if tool_name == "drift_nudge" and completed_task_ids and selected_tasks:
        completed_files: set[str] = set()
        for task in selected_tasks:
            task_id = task.get("id", task.get("task_id", ""))
            if task_id in completed_task_ids:
                if task.get("file"):
                    completed_files.add(str(task["file"]))
                for path in task.get("affected_files_for_pattern", []) or []:
                    completed_files.add(str(path))
        if completed_files:
            return "Potential rework on completed task files detected."

    return ""


# ---------------------------------------------------------------------------
# Diagnostic hypothesis management
# ---------------------------------------------------------------------------

_DIAGNOSTIC_REQUIRED_FIELDS = (
    "affected_files",
    "suspected_root_cause",
    "minimal_intended_change",
    "non_goals",
)


def _requires_diagnostic_hypothesis(session: Any) -> bool:
    """Return True when the session is in a batch-fix verification context."""
    if session is None:
        return False
    selected_tasks = getattr(session, "selected_tasks", None) or []
    return any(bool(task.get("batch_eligible")) for task in selected_tasks)


def _validate_diagnostic_hypothesis_payload(payload: Any) -> list[str]:
    """Validate diagnostic hypothesis payload contract and return field errors."""
    if not isinstance(payload, dict):
        return ["diagnostic_hypothesis must be an object"]

    errors: list[str] = []
    affected_files = payload.get("affected_files")
    if not isinstance(affected_files, list) or not affected_files:
        errors.append("affected_files (non-empty list[str])")
    elif not all(isinstance(item, str) and item.strip() for item in affected_files):
        errors.append("affected_files items must be non-empty strings")

    root_cause = payload.get("suspected_root_cause")
    if not isinstance(root_cause, str) or not root_cause.strip():
        errors.append("suspected_root_cause (non-empty string)")

    intended_change = payload.get("minimal_intended_change")
    if not isinstance(intended_change, str) or not intended_change.strip():
        errors.append("minimal_intended_change (non-empty string)")

    non_goals = payload.get("non_goals")
    if not isinstance(non_goals, list) or not non_goals:
        errors.append("non_goals (non-empty list[str])")
    elif not all(isinstance(item, str) and item.strip() for item in non_goals):
        errors.append("non_goals items must be non-empty strings")

    return errors


def _derive_diagnostic_hypothesis_id(payload: dict[str, Any]) -> str:
    """Create a stable hypothesis ID from normalized payload content."""
    normalized = {
        "affected_files": sorted(
            [str(item).strip() for item in payload.get("affected_files", [])]
        ),
        "suspected_root_cause": str(payload.get("suspected_root_cause", "")).strip(),
        "minimal_intended_change": str(
            payload.get("minimal_intended_change", "")
        ).strip(),
        "non_goals": sorted([str(item).strip() for item in payload.get("non_goals", [])]),
    }
    digest = hashlib.sha1(  # noqa: S324
        json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:12]
    return f"hyp-{digest}"


def _diagnostic_hypothesis_block_response(
    *,
    tool_name: str,
    session: Any,
    reason: str,
    details: list[str] | None = None,
    missing_hypothesis_id: str | None = None,
) -> str:
    """Build a structured MCP error envelope for missing/invalid hypotheses."""
    from drift.api_helpers import _error_response

    message = (
        f"{tool_name} requires a linked diagnostic hypothesis in batch-fix context."
    )
    if reason == "unknown_hypothesis_id":
        message = (
            f"{tool_name} received unknown hypothesis_id '{missing_hypothesis_id}'. "
            "Register the full diagnostic_hypothesis first."
        )

    payload: dict[str, Any] = {
        "blocked_tool": tool_name,
        "reason": reason,
        "required_fields": list(_DIAGNOSTIC_REQUIRED_FIELDS),
    }
    if details:
        payload["validation_errors"] = details
    if missing_hypothesis_id:
        payload["hypothesis_id"] = missing_hypothesis_id

    response = _error_response(
        "DRIFT-6003",
        message,
        recoverable=True,
        suggested_fix=payload,
        recovery_tool_call={
            "tool": tool_name,
            "params": {
                "session_id": session.session_id if session is not None else "",
                "diagnostic_hypothesis": {
                    "affected_files": ["src/example.py"],
                    "suspected_root_cause": "Short root-cause hypothesis",
                    "minimal_intended_change": "Minimal, bounded code change",
                    "non_goals": ["No unrelated refactor", "No scoring changes"],
                },
            },
        },
    )
    if session is not None:
        response["session_id"] = session.session_id
        session.record_trace(
            tool_name,
            advisory=f"diagnostic_hypothesis_block:{reason}",
            metadata={"diagnostic_hypothesis_reason": reason},
        )
        session.touch()
    response["blocked_tool"] = tool_name
    response["diagnostic_hypothesis_reason"] = reason
    response["agent_instruction"] = (
        "Provide diagnostic_hypothesis with required fields or a known hypothesis_id, "
        "then retry the blocked tool."
    )
    return json.dumps(response, default=str)


def _resolve_diagnostic_hypothesis_context(
    *,
    tool_name: str,
    session: Any,
    hypothesis_id: str | None,
    diagnostic_hypothesis: dict[str, Any] | None,
) -> dict[str, Any]:
    """Resolve and validate hypothesis context for nudge/diff tools."""
    requires_hypothesis = _requires_diagnostic_hypothesis(session)

    # Register payload-based hypothesis when provided.
    if diagnostic_hypothesis is not None:
        errors = _validate_diagnostic_hypothesis_payload(diagnostic_hypothesis)
        if errors:
            return {
                "blocked_response": _diagnostic_hypothesis_block_response(
                    tool_name=tool_name,
                    session=session,
                    reason="invalid_diagnostic_hypothesis",
                    details=errors,
                )
            }

        resolved_id = (hypothesis_id or diagnostic_hypothesis.get("hypothesis_id") or "").strip()
        if not resolved_id:
            resolved_id = _derive_diagnostic_hypothesis_id(diagnostic_hypothesis)

        if session is not None:
            session.register_diagnostic_hypothesis(resolved_id, diagnostic_hypothesis)

        return {
            "required": requires_hypothesis,
            "hypothesis_id": resolved_id,
            "hypothesis": diagnostic_hypothesis,
        }

    # Resolve ID-only reference against session state.
    if hypothesis_id:
        stored = session.get_diagnostic_hypothesis(hypothesis_id) if session is not None else None
        if stored is None and requires_hypothesis:
            return {
                "blocked_response": _diagnostic_hypothesis_block_response(
                    tool_name=tool_name,
                    session=session,
                    reason="unknown_hypothesis_id",
                    missing_hypothesis_id=hypothesis_id,
                )
            }
        return {
            "required": requires_hypothesis,
            "hypothesis_id": hypothesis_id,
            "hypothesis": stored,
        }

    if requires_hypothesis:
        return {
            "blocked_response": _diagnostic_hypothesis_block_response(
                tool_name=tool_name,
                session=session,
                reason="missing_diagnostic_hypothesis",
            )
        }

    return {"required": False, "hypothesis_id": None, "hypothesis": None}


def _trace_meta_from_hypothesis_result(
    tool_name: str,
    raw_json: str,
) -> dict[str, Any] | None:
    """Extract hypothesis and verification evidence for trace entries."""
    try:
        parsed = json.loads(raw_json)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(parsed, dict):
        return None

    hypothesis_id = parsed.get("hypothesis_id")
    verification = parsed.get("verification_evidence")
    if not hypothesis_id and not verification:
        return None

    trace_meta: dict[str, Any] = {"tool": tool_name}
    if hypothesis_id:
        trace_meta["hypothesis_id"] = hypothesis_id
    if verification and isinstance(verification, dict):
        trace_meta["verification_evidence"] = verification
    return trace_meta


# ---------------------------------------------------------------------------
# Strict guardrails enforcement
# ---------------------------------------------------------------------------


def _strict_guardrails_enabled(session: Any) -> bool:
    """Return True when agent.strict_guardrails is enabled in drift config."""
    if session is None:
        return False

    cached = getattr(session, "_strict_guardrails_enabled_cache", None)
    if isinstance(cached, bool):
        return cached

    from drift.config import DriftConfig

    enabled = False
    try:
        cfg = DriftConfig.load(Path(session.repo_path))
    except Exception:
        enabled = False
    else:
        agent_cfg = getattr(cfg, "agent", None)
        enabled = bool(getattr(agent_cfg, "strict_guardrails", False))

    # Cache once per session to avoid repeated config parsing on every tool call.
    session._strict_guardrails_enabled_cache = enabled
    return enabled


def _strict_guardrail_violations(tool_name: str, session: Any) -> list[dict[str, Any]]:
    """Return deterministic strict-guardrail violations for a tool transition."""
    if session is None:
        return []

    called_tools = _session_called_tools(session)
    violations: list[dict[str, Any]] = []

    if tool_name == "drift_fix_plan":
        if "drift_brief" not in called_tools:
            violations.append({
                "rule_id": "SG-001",
                "reason": "missing_brief",
                "message": "drift_fix_plan requires drift_brief in strict mode.",
                "required": ["drift_brief"],
                "observed": sorted(called_tools),
            })
        if "drift_scan" not in called_tools:
            violations.append({
                "rule_id": "SG-002",
                "reason": "missing_diagnosis",
                "message": "drift_fix_plan requires drift_scan diagnosis in strict mode.",
                "required": ["drift_scan"],
                "observed": sorted(called_tools),
            })

    if tool_name in {"drift_nudge", "drift_diff"} and "drift_scan" not in called_tools:
        violations.append({
            "rule_id": "SG-003",
            "reason": "missing_scan_baseline",
            "message": f"{tool_name} requires a prior drift_scan baseline in strict mode.",
            "required": ["drift_scan"],
            "observed": sorted(called_tools),
        })

    if tool_name == "drift_session_end" and session.tasks_remaining() > 0:
        violations.append({
            "rule_id": "SG-004",
            "reason": "open_tasks_remaining",
            "message": "drift_session_end is blocked while fix-plan tasks remain open.",
            "required": ["session.tasks_remaining == 0"],
            "observed": {"tasks_remaining": session.tasks_remaining()},
        })

    return violations


def _strict_guardrail_recovery_tool_call(
    violations: list[dict[str, Any]],
    session: Any,
) -> dict[str, Any]:
    """Return deterministic next-step hint for strict-guardrail blocks."""
    reason_ids = {v.get("reason") for v in violations}
    session_id = session.session_id

    if "missing_brief" in reason_ids:
        return {
            "tool": "drift_brief",
            "params": {
                "session_id": session_id,
                "task": "continue strict orchestration workflow",
            },
        }
    if "missing_diagnosis" in reason_ids or "missing_scan_baseline" in reason_ids:
        return {
            "tool": "drift_scan",
            "params": {"session_id": session_id},
        }
    if "open_tasks_remaining" in reason_ids:
        return {
            "tool": "drift_task_status",
            "params": {"session_id": session_id},
        }
    return {
        "tool": "drift_session_status",
        "params": {"session_id": session_id},
    }


def _strict_guardrail_block_response(tool_name: str, session: Any) -> str | None:
    """Return an MCP error envelope when strict guardrails block a transition."""
    if session is None or not _strict_guardrails_enabled(session):
        return None

    violations = _strict_guardrail_violations(tool_name, session)
    if not violations:
        return None

    from drift.api_helpers import _error_response

    recovery = _strict_guardrail_recovery_tool_call(violations, session)
    message = (
        f"Strict guardrails blocked '{tool_name}' because required orchestration "
        "preconditions were not met."
    )
    response = _error_response(
        "DRIFT-6002",
        message,
        recoverable=True,
        suggested_fix={
            "strict_guardrails": True,
            "blocked_tool": tool_name,
            "block_reasons": violations,
        },
        recovery_tool_call=recovery,
    )
    response["session_id"] = session.session_id
    response["blocked_tool"] = tool_name
    response["block_reasons"] = violations
    response["agent_instruction"] = (
        "Follow recovery_tool_call exactly, then retry the blocked tool."
    )

    advisory = (
        f"strict_guardrail_block:{tool_name};"
        + ",".join(str(v.get("reason")) for v in violations)
    )
    session.record_trace(tool_name, advisory=advisory)
    session.touch()
    return json.dumps(response, default=str)


# ---------------------------------------------------------------------------
# Pre-call advisory (soft guidance, not blocking)
# ---------------------------------------------------------------------------


def _pre_call_advisory(tool_name: str, session: Any) -> str:
    """Generate a lightweight pre-call advisory for the given tool.

    Returns an advisory string (empty if no concerns). This does NOT
    block the call — it provides soft guidance to the consuming agent.
    """
    if session is None:
        return ""

    from drift.tool_metadata import TOOL_CATALOG

    entry = TOOL_CATALOG.get(tool_name)
    if entry is None:
        return ""

    parts: list[str] = []

    semantic_advisory = _semantic_pre_call_advisory(tool_name, session)
    if semantic_advisory:
        parts.append(semantic_advisory)

    # Phase mismatch — tool not recommended for current phase
    if entry.phases and session.phase not in entry.phases:
        parts.append(
            f"'{tool_name}' is typically used in phase(s) {', '.join(entry.phases)}"
            f" but session is in phase '{session.phase}'."
        )

    # Redundancy check — warn if this exact tool was called recently
    recent_tools = [t["tool"] for t in session.trace[-3:]] if session.trace else []
    recent_count = recent_tools.count(tool_name)
    if recent_count >= 2:
        parts.append(
            f"'{tool_name}' was called {recent_count} times in last 3 calls."
            " Consider a different tool."
        )

    # Prerequisite check
    if entry.context.prerequisite_tools and not semantic_advisory:
        called_tools = _session_called_tools(session)
        missing = [p for p in entry.context.prerequisite_tools if p not in called_tools]
        if missing:
            parts.append(
                f"Prerequisite tool(s) not yet called: {', '.join(missing)}."
            )

    if _strict_guardrails_enabled(session):
        violations = _strict_guardrail_violations(tool_name, session)
        if violations:
            reason_ids = ", ".join(str(v.get("reason")) for v in violations)
            parts.append(
                "Strict guardrails are enabled; this transition requires hard"
                f" preconditions ({reason_ids})."
            )

    return " ".join(parts)
