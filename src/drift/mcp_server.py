"""Drift MCP server — exposes drift analysis as MCP tools for VS Code / Copilot.

Requires the optional ``mcp`` extra: ``pip install drift-analyzer[mcp]``

The server uses stdio transport (no network listener) and is started via
``drift mcp --serve``.  VS Code discovers it through ``.vscode/mcp.json``.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from mcp.server.fastmcp import FastMCP

    _MCP_AVAILABLE = True
except ImportError:
    _MCP_AVAILABLE = False

    class FastMCP:  # type: ignore[override]
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

from drift.analyzer import analyze_diff, analyze_repo
from drift.config import DriftConfig
from drift.models import RepoAnalysis, SignalType
from drift.output.json_output import _finding_to_dict

# ---------------------------------------------------------------------------
# Server instance
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "drift",
    instructions=(
        "Drift is a deterministic static analyzer that detects architectural "
        "erosion in Python codebases. Use these tools to analyze repositories "
        "for coherence problems like pattern fragmentation, layer violations, "
        "and near-duplicate code."
    ),
)

# ---------------------------------------------------------------------------
# In-memory cache
# ---------------------------------------------------------------------------

_CACHE_TTL_SECONDS = 60

_cache: dict[str, tuple[float, RepoAnalysis]] = {}


def _get_cached(key: str) -> RepoAnalysis | None:
    entry = _cache.get(key)
    if entry is None:
        return None
    ts, analysis = entry
    if time.monotonic() - ts > _CACHE_TTL_SECONDS:
        del _cache[key]
        return None
    return analysis


def _set_cache(key: str, analysis: RepoAnalysis) -> None:
    _cache[key] = (time.monotonic(), analysis)


# ---------------------------------------------------------------------------
# Path validation
# ---------------------------------------------------------------------------


def _resolve_repo_path(path: str | None) -> Path:
    """Resolve and validate a repository path.

    Ensures the path exists and is a directory.  Does NOT allow traversal
    outside the resolved directory (``Path.resolve()`` removes ``..``).
    """
    resolved = Path(path).resolve() if path else Path.cwd().resolve()
    if not resolved.is_dir():
        msg = f"Repository path does not exist or is not a directory: {resolved}"
        raise ValueError(msg)
    return resolved


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _analysis_summary(analysis: RepoAnalysis, max_findings: int = 20) -> dict[str, Any]:
    """Build a JSON-serialisable summary dict from a RepoAnalysis."""
    findings_list = sorted(analysis.findings, key=lambda f: f.impact, reverse=True)[
        :max_findings
    ]
    result: dict[str, Any] = {
        "drift_score": analysis.drift_score,
        "severity": analysis.severity.value,
        "total_files": analysis.total_files,
        "total_functions": analysis.total_functions,
        "analysis_duration_seconds": analysis.analysis_duration_seconds,
        "findings_count": len(analysis.findings),
        "findings_returned": len(findings_list),
        "findings": [_finding_to_dict(f) for f in findings_list],
    }
    if analysis.trend:
        result["trend"] = {
            "direction": analysis.trend.direction,
            "delta": analysis.trend.delta,
            "previous_score": analysis.trend.previous_score,
        }
    return result


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def drift_analyze(
    path: str = ".",
    since_days: int = 90,
    target_path: str | None = None,
    max_findings: int = 20,
) -> str:
    """Run full architectural drift analysis on the repository.

    Returns drift score, severity, and top findings sorted by impact.

    Args:
        path: Repository path to analyze. Defaults to current directory.
        since_days: Days of git history to consider (default: 90).
        target_path: Optional subdirectory to restrict analysis to.
        max_findings: Maximum findings to return (default: 20).
    """
    repo_path = _resolve_repo_path(path)
    cache_key = f"repo:{repo_path}:{since_days}:{target_path or ''}"

    analysis = _get_cached(cache_key)
    if analysis is None:
        config = DriftConfig.load(repo_path)
        analysis = analyze_repo(
            repo_path,
            config=config,
            since_days=since_days,
            target_path=target_path,
        )
        _set_cache(cache_key, analysis)

    return json.dumps(_analysis_summary(analysis, max_findings), default=str)


@mcp.tool()
def drift_check_diff(
    path: str = ".",
    diff_ref: str = "HEAD~1",
) -> str:
    """Analyze only files changed since a git ref.

    Use this for checking current changes before commit. Fast because it
    only processes changed files.

    Args:
        path: Repository path. Defaults to current directory.
        diff_ref: Git ref to diff against (default: HEAD~1).
    """
    repo_path = _resolve_repo_path(path)
    config = DriftConfig.load(repo_path)
    analysis = analyze_diff(repo_path, config=config, diff_ref=diff_ref)
    return json.dumps(_analysis_summary(analysis), default=str)


@mcp.tool()
def drift_explain_finding(signal: str) -> str:
    """Get detailed explanation for a specific signal type.

    Returns detection logic, examples, weight, and remediation guidance.

    Args:
        signal: Signal type name (e.g. 'pattern_fragmentation').
    """
    # Validate signal name
    try:
        signal_type = SignalType(signal)
    except ValueError:
        valid = [s.value for s in SignalType]
        return json.dumps({"error": f"Unknown signal '{signal}'. Valid: {valid}"})

    # Import signal info from explain command
    from drift.commands.explain import _SIGNAL_INFO

    # Find matching entry by signal_type value
    info: dict[str, str] | None = None
    for _abbr, entry in _SIGNAL_INFO.items():
        if entry["signal_type"] == signal:
            info = entry
            break

    if info is None:
        return json.dumps({
            "signal": signal,
            "name": signal_type.value,
            "description": "No detailed explanation available for this signal.",
        })

    return json.dumps({
        "signal": signal,
        "name": info.get("name", signal),
        "weight": float(info.get("weight", "0")),
        "description": info.get("description", ""),
        "detection_logic": info.get("detects", ""),
        "example": info.get("example", ""),
        "remediation": info.get("fix_hint", ""),
    })


@mcp.tool()
def drift_file_findings(
    file_path: str,
    path: str = ".",
) -> str:
    """Get all drift findings for a specific file.

    Use when reviewing or editing a particular file to see its issues.

    Args:
        file_path: Relative path to the file within the repo.
        path: Repository root path. Defaults to current directory.
    """
    repo_path = _resolve_repo_path(path)
    cache_key = f"repo:{repo_path}:90:"

    analysis = _get_cached(cache_key)
    if analysis is None:
        config = DriftConfig.load(repo_path)
        analysis = analyze_repo(repo_path, config=config)
        _set_cache(cache_key, analysis)

    target = Path(file_path)
    matching = [
        _finding_to_dict(f)
        for f in analysis.findings
        if f.file_path and (f.file_path == target or f.file_path.as_posix() == file_path)
    ]

    return json.dumps({
        "file": file_path,
        "finding_count": len(matching),
        "findings": matching,
    }, default=str)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the drift MCP server on stdio transport."""
    if not _MCP_AVAILABLE:
        msg = "MCP server requires optional dependency 'mcp'."
        raise RuntimeError(msg)
    mcp.run(transport="stdio")
