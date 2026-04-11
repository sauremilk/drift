"""Runtime-aware situational hints for MCP tool responses.

Complements the static ``ToolContextHint`` catalog in ``tool_metadata.py``
with hints derived from the current session state: open tasks, quality
trajectory, diagnostic hypotheses, and plan staleness.

Each hint is a short, actionable English sentence injected into the
``session_block["situational_hint"]`` field and — when present — appended
to ``agent_instruction``.  Hints are soft guidance only; they never block
a tool call.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_situational_hint(tool_name: str, session: Any) -> str | None:
    """Return a situational hint for *tool_name* given current *session* state.

    Returns ``None`` when no situational guidance applies.  The function is
    pure (no side effects) and safe to call on every tool invocation.
    """
    if session is None:
        return None

    for rule in _RULES:
        hint: str | None = rule(tool_name, session)
        if hint:
            return hint
    return None


# ---------------------------------------------------------------------------
# Individual rule functions
# ---------------------------------------------------------------------------


def _sh001_scan_with_open_tasks(tool_name: str, session: Any) -> str | None:
    """SH-001: drift_scan called while fix tasks are still pending."""
    if tool_name != "drift_scan":
        return None
    remaining = session.tasks_remaining()
    if remaining <= 0:
        return None
    return (
        f"{remaining} open task(s) remain — drift_nudge per changed file is"
        " faster than a full rescan."
    )


def _sh002_top_signal_not_in_plan(tool_name: str, session: Any) -> str | None:
    """SH-002: fix_plan has no task for the top scan signal."""
    if tool_name != "drift_fix_plan":
        return None
    top_signals = session.last_scan_top_signals
    if not top_signals:
        return None
    tasks = session.selected_tasks
    if not tasks:
        return None
    task_signals = {t.get("signal", t.get("signal_abbrev", "")) for t in tasks}
    for sig in top_signals[:3]:
        sig_name = sig.get("signal", sig.get("abbrev", ""))
        if sig_name and sig_name not in task_signals:
            return (
                f"Top signal '{sig_name}' has no corresponding task in the fix"
                " plan — check target_path or signals filter."
            )
    return None


def _sh003_consecutive_nudge_degradations(
    tool_name: str, session: Any
) -> str | None:
    """SH-003: 3+ consecutive degrading nudges detected."""
    if tool_name != "drift_nudge":
        return None
    count = session.consecutive_nudge_degradations()
    if count < 3:
        return None
    return (
        f"Last {count} nudges show degradation — consider reverting the"
        " recent change or running drift_explain for root-cause analysis."
    )


def _sh004_session_end_with_active_leases(
    tool_name: str, session: Any
) -> str | None:
    """SH-004: drift_session_end while tasks are still leased."""
    if tool_name != "drift_session_end":
        return None
    active = len(getattr(session, "active_leases", None) or {})
    if active == 0:
        return None
    return (
        f"{active} task(s) still actively leased — call drift_task_release"
        " before ending the session."
    )


def _sh005_nudge_with_unresolved_blocker(
    tool_name: str, session: Any
) -> str | None:
    """SH-005: nudge on a file whose task has unresolved blockers."""
    if tool_name != "drift_nudge":
        return None
    tasks = session.selected_tasks
    if not tasks:
        return None
    completed = set(session.completed_task_ids)
    for t in tasks:
        tid = t.get("id", t.get("task_id", ""))
        if tid in completed:
            continue
        deps = t.get("depends_on", [])
        unresolved = [d for d in deps if d not in completed]
        if unresolved:
            return (
                f"Task '{tid}' depends on unresolved blocker(s)"
                f" {', '.join(unresolved)} — fix the blocker first."
            )
    return None


def _sh006_sustained_quality_degradation(
    tool_name: str, session: Any
) -> str | None:
    """SH-006: Score degrading over 3+ consecutive run_history snapshots."""
    history = session.run_history
    if len(history) < 3:
        return None
    # Check last 3 entries for monotonically decreasing scores
    recent = history[-3:]
    scores = [h.get("score") for h in recent]
    if any(s is None for s in scores):
        return None
    if scores[0] > scores[1] > scores[2]:
        delta = round(scores[0] - scores[2], 2)
        return (
            f"Score dropped by {delta} over last 3 snapshots — current fixes"
            " are degrading architecture quality. Consider reverting."
        )
    return None


def _sh007_repeated_plan_staleness(tool_name: str, session: Any) -> str | None:
    """SH-007: fix_plan called after 2+ plan-stale events in this session."""
    if tool_name != "drift_fix_plan":
        return None
    stale_count = session.plan_stale_count()
    if stale_count < 2:
        return None
    return (
        f"Fix-plan went stale {stale_count} times — use a narrower"
        " target_path to reduce git-HEAD interference."
    )


# Rule registry — order matters: first matching rule wins.
_RULES: list[Any] = [
    _sh001_scan_with_open_tasks,
    _sh005_nudge_with_unresolved_blocker,
    _sh003_consecutive_nudge_degradations,
    _sh006_sustained_quality_degradation,
    _sh004_session_end_with_active_leases,
    _sh002_top_signal_not_in_plan,
    _sh007_repeated_plan_staleness,
]
