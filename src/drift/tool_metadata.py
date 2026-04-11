"""Static metadata for MCP tools — cost, risk, latency, and JIT context hints.

Used by the MCP server to enrich tool responses and provide
just-in-time guidance to consuming agents.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ToolCostMetadata:
    """Static cost/risk profile for a single MCP tool.

    All values are estimates for agent planning — not runtime measurements.

    Attributes:
        cost: Relative computational cost (low / medium / high).
        risk: Risk of destructive or irreversible side effects (none / low / medium).
        typical_latency_ms: Typical wall-clock time in milliseconds.
        token_estimate: Approximate response size in tokens (order of magnitude).
    """

    cost: str  # "low" | "medium" | "high"
    risk: str  # "none" | "low" | "medium"
    typical_latency_ms: int
    token_estimate: int


@dataclass(frozen=True, slots=True)
class ToolContextHint:
    """Just-in-time context hint for a single MCP tool.

    Attributes:
        when_to_use: Short guidance on when this tool is appropriate.
        when_not_to_use: Short guidance on when to prefer a different tool.
        prerequisite_tools: Tools that should typically run before this one.
        follow_up_tools: Tools that typically follow this one.
    """

    when_to_use: str
    when_not_to_use: str = ""
    prerequisite_tools: tuple[str, ...] = ()
    follow_up_tools: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ToolMetadataEntry:
    """Combined metadata entry for a single MCP tool.

    Attributes:
        name: Tool function name (e.g. ``drift_scan``).
        cost: Cost/risk profile.
        context: JIT context hint.
        phases: Session phases where this tool is recommended.
    """

    name: str
    cost: ToolCostMetadata
    context: ToolContextHint
    phases: tuple[str, ...] = ()


def _build_catalog() -> dict[str, ToolMetadataEntry]:
    """Build the immutable tool metadata catalog."""
    entries: list[ToolMetadataEntry] = [
        # --- Validation & Setup ---
        ToolMetadataEntry(
            name="drift_validate",
            cost=ToolCostMetadata("low", "none", 200, 150),
            context=ToolContextHint(
                when_to_use="First call in any session to check environment.",
                when_not_to_use="Already validated in this session.",
                follow_up_tools=("drift_brief",),
            ),
            phases=("init",),
        ),
        ToolMetadataEntry(
            name="drift_brief",
            cost=ToolCostMetadata("low", "none", 500, 400),
            context=ToolContextHint(
                when_to_use="Before implementing a task — get scope-aware guardrails.",
                when_not_to_use="After scan results are already available.",
                prerequisite_tools=("drift_validate",),
                follow_up_tools=("drift_scan",),
            ),
            phases=("init", "scan"),
        ),
        ToolMetadataEntry(
            name="drift_negative_context",
            cost=ToolCostMetadata("low", "none", 300, 300),
            context=ToolContextHint(
                when_to_use="Get anti-patterns to avoid before writing new code.",
                when_not_to_use="When you need positive guidance (use drift_brief).",
                prerequisite_tools=("drift_validate",),
            ),
            phases=("init", "scan"),
        ),
        # --- Analysis ---
        ToolMetadataEntry(
            name="drift_scan",
            cost=ToolCostMetadata("high", "none", 3000, 2000),
            context=ToolContextHint(
                when_to_use="Full architectural health assessment.",
                when_not_to_use="Between small edits (use drift_nudge instead).",
                prerequisite_tools=("drift_validate",),
                follow_up_tools=("drift_fix_plan", "drift_explain"),
            ),
            phases=("scan",),
        ),
        ToolMetadataEntry(
            name="drift_nudge",
            cost=ToolCostMetadata("low", "none", 200, 200),
            context=ToolContextHint(
                when_to_use="Fast directional feedback after a file edit (~0.2s).",
                when_not_to_use="Before any scan has run (need baseline).",
                prerequisite_tools=("drift_scan",),
                follow_up_tools=("drift_nudge", "drift_diff"),
            ),
            phases=("fix",),
        ),
        ToolMetadataEntry(
            name="drift_diff",
            cost=ToolCostMetadata("high", "none", 3000, 1500),
            context=ToolContextHint(
                when_to_use="Full verification after completing a batch of fixes.",
                when_not_to_use="After every single edit (use drift_nudge).",
                prerequisite_tools=("drift_scan",),
                follow_up_tools=("drift_session_end",),
            ),
            phases=("verify",),
        ),
        ToolMetadataEntry(
            name="drift_explain",
            cost=ToolCostMetadata("low", "none", 300, 500),
            context=ToolContextHint(
                when_to_use="Understand unfamiliar signals or findings.",
                when_not_to_use="When you already understand the finding.",
                prerequisite_tools=("drift_scan",),
            ),
            phases=("scan", "fix"),
        ),
        ToolMetadataEntry(
            name="drift_fix_plan",
            cost=ToolCostMetadata("medium", "none", 500, 800),
            context=ToolContextHint(
                when_to_use="Get actionable repair tasks from scan results.",
                when_not_to_use="Before a scan has run.",
                prerequisite_tools=("drift_scan",),
                follow_up_tools=("drift_nudge",),
            ),
            phases=("scan", "fix"),
        ),
        # --- Session management ---
        ToolMetadataEntry(
            name="drift_session_start",
            cost=ToolCostMetadata("medium", "none", 4000, 2000),
            context=ToolContextHint(
                when_to_use="Start a multi-step session (with autopilot=true).",
                when_not_to_use="For single one-off queries.",
                follow_up_tools=("drift_fix_plan",),
            ),
            phases=("init",),
        ),
        ToolMetadataEntry(
            name="drift_session_status",
            cost=ToolCostMetadata("low", "none", 50, 200),
            context=ToolContextHint(
                when_to_use="Check current session state and progress.",
            ),
            phases=("init", "scan", "fix", "verify", "done"),
        ),
        ToolMetadataEntry(
            name="drift_session_update",
            cost=ToolCostMetadata("low", "none", 50, 100),
            context=ToolContextHint(
                when_to_use="Update session scope or defaults mid-session.",
                when_not_to_use="When session hasn't been started.",
                prerequisite_tools=("drift_session_start",),
            ),
            phases=("scan", "fix"),
        ),
        ToolMetadataEntry(
            name="drift_session_end",
            cost=ToolCostMetadata("low", "none", 100, 300),
            context=ToolContextHint(
                when_to_use="After all tasks are done — get summary and cleanup.",
                prerequisite_tools=("drift_diff",),
            ),
            phases=("done",),
        ),
        # --- Task queue ---
        ToolMetadataEntry(
            name="drift_task_claim",
            cost=ToolCostMetadata("low", "none", 50, 150),
            context=ToolContextHint(
                when_to_use="Claim the next task from the fix-plan queue.",
                prerequisite_tools=("drift_fix_plan",),
                follow_up_tools=("drift_nudge", "drift_task_complete"),
            ),
            phases=("fix",),
        ),
        ToolMetadataEntry(
            name="drift_task_renew",
            cost=ToolCostMetadata("low", "none", 50, 50),
            context=ToolContextHint(
                when_to_use="Extend lease on a long-running claimed task.",
                prerequisite_tools=("drift_task_claim",),
            ),
            phases=("fix",),
        ),
        ToolMetadataEntry(
            name="drift_task_release",
            cost=ToolCostMetadata("low", "none", 50, 50),
            context=ToolContextHint(
                when_to_use="Release a claimed task you cannot complete.",
                prerequisite_tools=("drift_task_claim",),
            ),
            phases=("fix",),
        ),
        ToolMetadataEntry(
            name="drift_task_complete",
            cost=ToolCostMetadata("low", "none", 50, 50),
            context=ToolContextHint(
                when_to_use="Mark a claimed task as completed.",
                prerequisite_tools=("drift_task_claim",),
                follow_up_tools=("drift_nudge", "drift_task_claim"),
            ),
            phases=("fix",),
        ),
        ToolMetadataEntry(
            name="drift_task_status",
            cost=ToolCostMetadata("low", "none", 50, 100),
            context=ToolContextHint(
                when_to_use="Check status of a specific task (claimed/expired/etc.).",
                prerequisite_tools=("drift_fix_plan",),
            ),
            phases=("fix",),
        ),
    ]
    return {e.name: e for e in entries}


TOOL_CATALOG: dict[str, ToolMetadataEntry] = _build_catalog()
"""Immutable metadata catalog keyed by tool function name."""


# Session phases in order — used by progressive disclosure logic.
SESSION_PHASES: tuple[str, ...] = ("init", "scan", "fix", "verify", "done")


def tools_for_phase(phase: str) -> list[str]:
    """Return tool names recommended for the given session phase."""
    if phase not in SESSION_PHASES:
        return list(TOOL_CATALOG.keys())
    return [name for name, entry in TOOL_CATALOG.items() if phase in entry.phases]


def metadata_as_dict(entry: ToolMetadataEntry) -> dict[str, object]:
    """Serialize a single entry to a plain dict for JSON responses."""
    return {
        "name": entry.name,
        "cost": entry.cost.cost,
        "risk": entry.cost.risk,
        "typical_latency_ms": entry.cost.typical_latency_ms,
        "token_estimate": entry.cost.token_estimate,
        "when_to_use": entry.context.when_to_use,
        "when_not_to_use": entry.context.when_not_to_use,
        "prerequisite_tools": list(entry.context.prerequisite_tools),
        "follow_up_tools": list(entry.context.follow_up_tools),
        "phases": list(entry.phases),
    }
