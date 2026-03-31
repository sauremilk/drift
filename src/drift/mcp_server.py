"""Drift MCP server — exposes drift analysis as MCP tools for VS Code / Copilot.

Requires the optional ``mcp`` extra: ``pip install drift-analyzer[mcp]``

The server uses stdio transport (no network listener) and is started via
``drift mcp --serve``.  VS Code discovers it through ``.vscode/mcp.json``.

Tool surface (v2):
    drift_scan       — Full repo analysis (concise/detailed)
    drift_diff       — Diff-based change detection
    drift_explain    — Signal/rule/error explanations
    drift_fix_plan   — Prioritised repair tasks with constraints
    drift_validate   — Preflight config & environment check
"""

from __future__ import annotations

import json
from typing import Any

MCPFastMCPImpl: Any

try:
    from mcp.server.fastmcp import FastMCP as _ImportedFastMCP

    _MCP_AVAILABLE = True
    MCPFastMCPImpl = _ImportedFastMCP
except ImportError:
    _MCP_AVAILABLE = False

    class _FallbackFastMCP:
        """Minimal fallback so helper functions stay importable without mcp extra."""

        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def tool(self):
            def _decorator(func):
                return func

            return _decorator

        def run(self, **_kwargs: object) -> None:
            msg = "MCP server requires optional dependency 'mcp'."
            raise RuntimeError(msg)

    MCPFastMCPImpl = _FallbackFastMCP

# ---------------------------------------------------------------------------
# Server instance
# ---------------------------------------------------------------------------

mcp = MCPFastMCPImpl(
    "drift",
    instructions=(
        "Drift is a deterministic static analyzer that detects architectural "
        "erosion in Python codebases. Use these tools to analyze repositories "
        "for coherence problems like pattern fragmentation, layer violations, "
        "and near-duplicate code.\n\n"
        "Tool workflow:\n"
        "1. drift_validate — check config & environment before first analysis\n"
        "2. drift_scan — assess overall architectural health\n"
        "3. drift_diff — detect regressions in a PR or after changes\n"
        "4. drift_fix_plan — get actionable repair tasks with constraints\n"
        "5. drift_explain — understand unfamiliar signals or findings\n"
        "6. drift_nudge — get directional feedback after each file change "
        "(do not batch)\n\n"
        "IMPORTANT: After each file change, call drift_nudge for fast "
        "directional feedback. Use drift_diff for full regression analysis. "
        "Do not batch multiple file changes without checking drift impact. "
        "Every response includes an 'agent_instruction' field — follow it."
    ),
)


# ---------------------------------------------------------------------------
# MCP Tools — v2 agent-native surface
# ---------------------------------------------------------------------------


@mcp.tool()
def drift_scan(
    path: str = ".",
    target_path: str | None = None,
    since_days: int = 90,
    signals: str | None = None,
    max_findings: int = 10,
    response_detail: str = "concise",
) -> str:
    """Analyze a repository for architectural drift.

    Returns drift score, severity, top signals, fix-first queue,
    and findings sorted by impact.  Use this to assess overall health.

    Args:
        path: Repository path (default: current directory).
        target_path: Restrict analysis to a subdirectory.
        since_days: Days of git history to consider (default: 90).
        signals: Comma-separated signal IDs to include (e.g. "PFS,AVS").
        max_findings: Maximum findings to return (default: 10).
        response_detail: "concise" (token-sparing) or "detailed" (full fields).
    """
    from drift.api import scan

    signal_list = (
        [s.strip() for s in signals.split(",") if s.strip()]
        if signals
        else None
    )
    result = scan(
        path,
        target_path=target_path,
        since_days=since_days,
        signals=signal_list,
        max_findings=max_findings,
        response_detail=response_detail,
    )
    return json.dumps(result, default=str)


@mcp.tool()
def drift_diff(
    path: str = ".",
    diff_ref: str = "HEAD~1",
    uncommitted: bool = False,
    staged_only: bool = False,
    baseline_file: str | None = None,
    max_findings: int = 10,
    response_detail: str = "concise",
) -> str:
    """Detect drift changes since a git ref or baseline.

    Use this for PR review, CI gating, or before/after comparison.
    Returns drift_detected flag, score delta, new and resolved findings.

    Args:
        path: Repository path (default: current directory).
        diff_ref: Git ref to diff against (default: HEAD~1).
        uncommitted: Compare current working-tree changes against HEAD.
        staged_only: Compare only staged changes.
        baseline_file: Path to .drift-baseline.json for comparison.
        max_findings: Maximum findings to return (default: 10).
        response_detail: "concise" or "detailed".
    """
    from drift.api import diff

    result = diff(
        path,
        diff_ref=diff_ref,
        uncommitted=uncommitted,
        staged_only=staged_only,
        baseline_file=baseline_file,
        max_findings=max_findings,
        response_detail=response_detail,
    )
    return json.dumps(result, default=str)


@mcp.tool()
def drift_explain(topic: str) -> str:
    """Explain a drift signal, rule, or error code.

    Use when you encounter an unfamiliar signal abbreviation (e.g. "PFS"),
    need to understand what a finding means, or want remediation guidance.

    Args:
        topic: Signal abbreviation ("PFS"), signal name
            ("pattern_fragmentation"), or error code ("DRIFT-1001").
    """
    from drift.api import explain

    return json.dumps(explain(topic), default=str)


@mcp.tool()
def drift_fix_plan(
    path: str = ".",
    signal: str | None = None,
    max_tasks: int = 5,
    automation_fit_min: str | None = None,
    target_path: str | None = None,
) -> str:
    """Generate prioritised repair tasks with constraints and success criteria.

    Use this after drift_scan identifies findings you want to fix.
    Each task includes action steps, do-not-over-fix constraints,
    machine-verifiable success criteria, and automation fitness rating.

    Args:
        path: Repository path (default: current directory).
        signal: Filter to a specific signal ("PFS", "AVS", etc.).
        max_tasks: Maximum tasks to return (default: 5).
        automation_fit_min: Minimum automation fitness: "low", "medium", or "high".
        target_path: Restrict tasks to findings inside this subpath.
    """
    from drift.api import fix_plan

    result = fix_plan(
        path,
        signal=signal,
        max_tasks=max_tasks,
        automation_fit_min=automation_fit_min,
        target_path=target_path,
    )
    return json.dumps(result, default=str)


@mcp.tool()
def drift_validate(
    path: str = ".",
    config_file: str | None = None,
) -> str:
    """Validate configuration and environment before running analysis.

    Use before first drift_scan or after config changes to verify
    that git is available, config is valid, and files are discoverable.

    Args:
        path: Repository path (default: current directory).
        config_file: Explicit config file path (auto-discovered if omitted).
    """
    from drift.api import validate

    result = validate(path, config_file=config_file)
    return json.dumps(result, default=str)


@mcp.tool()
def drift_nudge(
    path: str = ".",
    changed_files: str | None = None,
    uncommitted: bool = True,
) -> str:
    """Get directional feedback after a file change (experimental).

    Returns direction (improving/stable/degrading), safe_to_commit flag,
    and confidence per signal — without running a full scan.  Call this
    after every file edit instead of drift_diff for faster feedback.

    First call on a repository triggers a full baseline scan.  Subsequent
    calls only re-analyze changed files for file-local signals and carry
    forward cross-file results with estimated confidence.

    Args:
        path: Repository path (default: current directory).
        changed_files: Comma-separated list of changed file paths
            (posix, relative to repo root).  Auto-detected via git if omitted.
        uncommitted: When auto-detecting, use uncommitted working-tree
            changes (default) vs. staged-only.
    """
    from drift.api import nudge

    file_list: list[str] | None = None
    if changed_files is not None:
        file_list = [f.strip() for f in changed_files.split(",") if f.strip()]

    result = nudge(path, changed_files=file_list, uncommitted=uncommitted)
    return json.dumps(result, default=str)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the drift MCP server on stdio transport."""
    if not _MCP_AVAILABLE:
        msg = "MCP server requires optional dependency 'mcp'."
        raise RuntimeError(msg)
    mcp.run(transport="stdio")
