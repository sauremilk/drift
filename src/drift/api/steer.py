"""Steer API — location-centric architecture context for AI agents.

Unlike ``brief()`` (task-centric: *what to do*) or ``nudge()`` (post-edit:
*what went wrong*), ``steer()`` is **pre-edit and location-centric**: given
a target file or module, it returns the architecture context that applies
*at that location* — layer, neighbors, reusable abstractions, hotspots,
and layer policies.

Design goals:
- Fast (<500 ms) — reads from the persisted ArchGraph, no full analysis.
- Deterministic — same graph + target = same result.
- Agent-consumable — returns a flat dict with ``agent_instruction``.

Phase B of the Architecture Runtime Blueprint.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from drift.arch_graph import ArchGraph, ArchGraphStore
from drift.arch_graph._decisions import format_decision_constraints, match_decisions
from drift.next_step_contract import _error_response, _next_step_contract
from drift.response_shaping import shape_for_profile
from drift.telemetry import timed_call

_log = logging.getLogger("drift")

# ---------------------------------------------------------------------------
# SteerContext — the value object returned by the core logic
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class SteerContext:
    """Architecture context for a target location."""

    target: str
    modules: list[dict[str, Any]] = field(default_factory=list)
    neighbors: list[str] = field(default_factory=list)
    abstractions: list[dict[str, Any]] = field(default_factory=list)
    hotspots: list[dict[str, Any]] = field(default_factory=list)
    layer_policies: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dict (JSON-safe)."""
        return {
            "target": self.target,
            "modules": list(self.modules),
            "neighbors": list(self.neighbors),
            "abstractions": list(self.abstractions),
            "hotspots": list(self.hotspots),
            "layer_policies": list(self.layer_policies),
        }


# ---------------------------------------------------------------------------
# Core logic (pure, no I/O)
# ---------------------------------------------------------------------------


def steer_from_graph(
    graph: ArchGraph,
    target: str,
    *,
    max_abstractions: int = 20,
) -> SteerContext:
    """Query *graph* for the architecture context at *target*.

    Parameters
    ----------
    graph:
        A populated ``ArchGraph`` (from cache or freshly seeded).
    target:
        Module path (e.g. ``"src/api"``) or file path
        (e.g. ``"src/api/auth.py"``).  File paths are resolved to their
        enclosing module via prefix match.
    max_abstractions:
        Cap on the number of abstractions returned.

    Returns
    -------
    SteerContext
        Fully populated context for the target location.
    """
    # Normalise target path separators
    target = target.replace("\\", "/").rstrip("/")

    # Resolve target to module(s) — exact match or file-inside-module
    matched_modules = _resolve_modules(graph, target)

    if not matched_modules:
        return SteerContext(target=target)

    # Module dicts for the response
    module_dicts = [
        {
            "path": m.path,
            "drift_score": m.drift_score,
            "file_count": m.file_count,
            "function_count": m.function_count,
            "layer": m.layer,
            "stability": m.stability,
            "languages": list(m.languages),
        }
        for m in matched_modules
    ]

    # Collect all neighbor module paths
    module_paths = {m.path for m in matched_modules}
    neighbor_paths: set[str] = set()
    for mp in module_paths:
        neighbor_paths.update(graph.neighbors(mp))
    neighbor_paths -= module_paths
    neighbors_sorted = sorted(neighbor_paths)

    # Abstractions: from target module(s) + neighbors
    relevant_module_paths = module_paths | neighbor_paths
    abstractions_raw = []
    for mp in relevant_module_paths:
        abstractions_raw.extend(graph.abstractions_in(mp))
    # Sort by usage_count desc, take top N
    abstractions_raw.sort(key=lambda a: a.usage_count, reverse=True)
    abstractions_raw = abstractions_raw[:max_abstractions]
    abstraction_dicts = [
        {
            "symbol": a.symbol,
            "kind": a.kind,
            "module_path": a.module_path,
            "file_path": a.file_path,
            "usage_count": a.usage_count,
            "is_exported": a.is_exported,
            "has_docstring": a.has_docstring,
        }
        for a in abstractions_raw
    ]

    # Hotspots: files within target module(s)
    hotspot_dicts = []
    for hs in graph.hotspots:
        hs_norm = hs.path.replace("\\", "/")
        if any(hs_norm.startswith(mp + "/") or hs_norm == mp for mp in module_paths):
            hotspot_dicts.append(
                {
                    "path": hs.path,
                    "recurring_signals": dict(hs.recurring_signals),
                    "trend": hs.trend,
                    "total_occurrences": hs.total_occurrences,
                }
            )

    # Layer policies: dependencies from target module(s) with a policy
    layer_policies = []
    for dep in graph.dependencies:
        if dep.from_module in module_paths and dep.policy:
            layer_policies.append(
                {
                    "from_module": dep.from_module,
                    "to_module": dep.to_module,
                    "policy": dep.policy,
                }
            )

    return SteerContext(
        target=target,
        modules=module_dicts,
        neighbors=neighbors_sorted,
        abstractions=abstraction_dicts,
        hotspots=hotspot_dicts,
        layer_policies=layer_policies,
    )


def _resolve_modules(
    graph: ArchGraph,
    target: str,
) -> list[Any]:
    """Resolve *target* (module path or file path) to ``ArchModule``(s).

    Tries exact match first, then longest-prefix match for file paths.
    """
    # Exact module match
    exact = graph.get_module(target)
    if exact is not None:
        return [exact]

    # File-inside-module: find the module whose path is a prefix
    candidates = []
    for m in graph.modules:
        m_norm = m.path.replace("\\", "/")
        if target.startswith(m_norm + "/"):
            candidates.append((len(m_norm), m))
    if candidates:
        # Longest prefix wins
        candidates.sort(key=lambda x: x[0], reverse=True)
        return [candidates[0][1]]

    return []


# ---------------------------------------------------------------------------
# Public API endpoint
# ---------------------------------------------------------------------------


def steer(
    path: str | Path = ".",
    *,
    target: str,
    cache_dir: str | None = None,
    max_abstractions: int = 20,
    include_reuse: bool = False,
    reuse_query: str | None = None,
    max_reuse_suggestions: int = 5,
    response_profile: str | None = None,
) -> dict[str, Any]:
    """Return architecture context for a target location.

    This endpoint is designed for speed: it reads from the persisted
    ``ArchGraph`` (built by ``seed_graph`` after a ``drift_map`` call)
    and does not re-run a full repository analysis.

    Parameters
    ----------
    path:
        Repository root path.
    target:
        File or module path to query context for.
    cache_dir:
        Explicit cache directory for the ArchGraph store.
        If ``None``, defaults to ``{repo}/.drift-cache``.
    max_abstractions:
        Cap on the number of abstractions returned.
    include_reuse:
        When ``True``, include reuse suggestions from the Abstraction
        Index (Phase C).  Requires *reuse_query*.
    reuse_query:
        Free-text description of what the agent intends to create.
        Used for ranking reuse suggestions.  Ignored when
        *include_reuse* is ``False``.
    max_reuse_suggestions:
        Cap on the number of reuse suggestions returned.
    response_profile:
        Optional profile for response shaping (``"planner"``,
        ``"coder"``, etc.).

    Returns
    -------
    dict[str, Any]
        Structured response with architecture context, agent instruction,
        and next-step contract.
    """
    repo_path = Path(path).resolve()
    elapsed_ms = timed_call()
    params: dict[str, Any] = {
        "path": str(path),
        "target": target,
        "cache_dir": cache_dir,
        "max_abstractions": max_abstractions,
        "include_reuse": include_reuse,
        "reuse_query": reuse_query,
    }

    try:
        from drift.api._config import _emit_api_telemetry

        # Load graph from cache
        effective_cache = (
            Path(cache_dir) if cache_dir else repo_path / ".drift-cache"
        )
        store = ArchGraphStore(cache_dir=effective_cache)
        graph = store.load()

        graph_available = graph is not None

        if graph is not None:
            ctx = steer_from_graph(
                graph,
                target=target,
                max_abstractions=max_abstractions,
            )
        else:
            ctx = SteerContext(target=target)

        ctx_dict = ctx.to_dict()

        # Reuse suggestions (Phase C)
        reuse_suggestions: list[dict[str, Any]] = []
        if include_reuse and graph is not None:
            from drift.arch_graph._reuse_index import suggest_reuse

            suggestions = suggest_reuse(
                graph,
                query=reuse_query or "",
                scope=target,
                max_suggestions=max_reuse_suggestions,
            )
            reuse_suggestions = [s.to_dict() for s in suggestions]

        # Decision constraints (Phase D)
        decision_constraints: list[dict[str, Any]] = []
        if graph is not None:
            matched_decisions = match_decisions(graph.decisions, target=target)
            decision_constraints = format_decision_constraints(matched_decisions)

        agent_instruction = _build_agent_instruction(
            ctx, graph_available, reuse_suggestions, decision_constraints
        )

        result: dict[str, Any] = {
            "status": "ok",
            "target": target,
            "graph_available": graph_available,
            **ctx_dict,
            "reuse_suggestions": reuse_suggestions,
            "decision_constraints": decision_constraints,
            "agent_instruction": agent_instruction,
            **_next_step_contract(
                next_tool="drift_nudge",
                done_when="done_task_and_nudge",
                fallback_tool="drift_scan",
            ),
        }

        _emit_api_telemetry(
            tool_name="api.steer",
            params=params,
            status="ok",
            elapsed_ms=elapsed_ms(),
            result=result,
            error=None,
            repo_root=repo_path,
        )

        return shape_for_profile(result, response_profile)

    except Exception as exc:
        _log.debug("steer() error: %s", exc, exc_info=True)
        try:
            from drift.api._config import _emit_api_telemetry

            _emit_api_telemetry(
                tool_name="api.steer",
                params=params,
                status="error",
                elapsed_ms=elapsed_ms(),
                result=None,
                error=exc,
                repo_root=repo_path,
            )
        except Exception:
            pass
        return _error_response("DRIFT-7001", str(exc), recoverable=True)


def _build_agent_instruction(
    ctx: SteerContext,
    graph_available: bool,
    reuse_suggestions: list[dict[str, Any]] | None = None,
    decision_constraints: list[dict[str, Any]] | None = None,
) -> str:
    """Build a context-sensitive agent instruction."""
    if not graph_available:
        return (
            "No architecture graph is available. Run drift_scan or drift_map "
            "first to seed the architecture graph, then call drift_steer again."
        )

    parts = [
        f"Architecture context for '{ctx.target}'.",
    ]

    if ctx.modules:
        layer = ctx.modules[0].get("layer", "unknown")
        parts.append(f"This module is in the '{layer}' layer.")

    if ctx.layer_policies:
        forbidden = [p for p in ctx.layer_policies if p["policy"] == "forbidden"]
        if forbidden:
            targets = ", ".join(p["to_module"] for p in forbidden)
            parts.append(
                f"CONSTRAINT: Direct imports from {targets} are forbidden "
                f"by layer policy."
            )

    if ctx.hotspots:
        degrading = [h for h in ctx.hotspots if h["trend"] == "degrading"]
        if degrading:
            files = ", ".join(h["path"] for h in degrading[:3])
            parts.append(
                f"WARNING: {files} show degrading drift trends — "
                f"extra care required."
            )

    if ctx.abstractions:
        parts.append(
            f"{len(ctx.abstractions)} reusable abstractions are available "
            f"from this module and its neighbors. Prefer reuse over duplication."
        )

    if reuse_suggestions:
        top = reuse_suggestions[0]
        parts.append(
            f"REUSE SUGGESTION: Consider '{top['symbol']}' in "
            f"{top['file_path']} (used by {top['usage_count']} consumers) "
            f"before creating a new implementation."
        )

    if decision_constraints:
        block_rules = [
            d for d in decision_constraints if d["enforcement"] == "block"
        ]
        warn_rules = [
            d for d in decision_constraints if d["enforcement"] == "warn"
        ]
        if block_rules:
            rules_text = "; ".join(d["rule"] for d in block_rules)
            parts.append(f"BLOCK: {rules_text}")
        if warn_rules:
            rules_text = "; ".join(d["rule"] for d in warn_rules)
            parts.append(f"WARN: {rules_text}")

    return " ".join(parts)
