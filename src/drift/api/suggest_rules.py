"""Suggest Rules API — feedback-loop rule proposals for AI agents.

Analyses the persisted ``ArchGraph`` for recurring drift patterns and
proposes new ``ArchDecision`` rules that can be reviewed by maintainers.

Phase E of the Architecture Runtime Blueprint.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from drift.arch_graph import ArchGraphStore
from drift.arch_graph._feedback import propose_decisions
from drift.next_step_contract import _error_response, _next_step_contract
from drift.response_shaping import shape_for_profile
from drift.telemetry import timed_call

_log = logging.getLogger("drift")


def suggest_rules(
    path: str | Path = ".",
    *,
    cache_dir: str | None = None,
    min_occurrences: int = 4,
    response_profile: str | None = None,
) -> dict[str, Any]:
    """Propose architecture rules from recurring drift patterns.

    Reads the persisted ``ArchGraph``, detects recurring signal patterns
    in hotspots, and returns proposed ``ArchDecision`` rules.

    Parameters
    ----------
    path:
        Repository root path.
    cache_dir:
        Explicit cache directory for the ArchGraph store.
        If ``None``, defaults to ``{repo}/.drift-cache``.
    min_occurrences:
        Minimum signal recurrence in a module to trigger a proposal.
    response_profile:
        Optional profile for response shaping.

    Returns
    -------
    dict[str, Any]
        Structured response with proposals, agent instruction,
        and next-step contract.
    """
    repo_path = Path(path).resolve()
    elapsed_ms = timed_call()
    params: dict[str, Any] = {
        "path": str(path),
        "cache_dir": cache_dir,
        "min_occurrences": min_occurrences,
    }

    try:
        from drift.api._config import _emit_api_telemetry

        effective_cache = (
            Path(cache_dir) if cache_dir else repo_path / ".drift-cache"
        )
        store = ArchGraphStore(cache_dir=effective_cache)
        graph = store.load()

        if graph is None:
            return _error_response(
                "DRIFT-7002",
                "No architecture graph available. Run drift_scan or "
                "drift_map first to seed the graph.",
                recoverable=True,
            )

        proposals = propose_decisions(graph, min_occurrences=min_occurrences)
        proposal_dicts = [p.to_dict() for p in proposals]

        agent_instruction = _build_agent_instruction(proposals)

        result: dict[str, Any] = {
            "status": "ok",
            "proposals": proposal_dicts,
            "proposal_count": len(proposal_dicts),
            "agent_instruction": agent_instruction,
            **_next_step_contract(
                next_tool="drift_steer",
                done_when="proposals_reviewed",
                fallback_tool="drift_scan",
            ),
        }

        _emit_api_telemetry(
            tool_name="api.suggest_rules",
            params=params,
            status="ok",
            elapsed_ms=elapsed_ms(),
            result=result,
            error=None,
            repo_root=repo_path,
        )

        return shape_for_profile(result, response_profile)

    except Exception as exc:
        _log.debug("suggest_rules() error: %s", exc, exc_info=True)
        try:
            from drift.api._config import _emit_api_telemetry

            _emit_api_telemetry(
                tool_name="api.suggest_rules",
                params=params,
                status="error",
                elapsed_ms=elapsed_ms(),
                result=None,
                error=exc,
                repo_root=repo_path,
            )
        except Exception:
            pass
        return _error_response("DRIFT-7002", str(exc), recoverable=True)


def _build_agent_instruction(
    proposals: list[Any],
) -> str:
    """Build context-sensitive instruction for the agent."""
    if not proposals:
        return (
            "No recurring patterns detected. The codebase hotspots are "
            "below the proposal threshold. No new rules to suggest."
        )

    block_count = sum(
        1 for p in proposals if p.proposed_decision.enforcement == "block"
    )
    warn_count = sum(
        1 for p in proposals if p.proposed_decision.enforcement == "warn"
    )

    parts = [
        f"{len(proposals)} rule proposal(s) detected from recurring patterns.",
    ]

    if block_count:
        parts.append(
            f"{block_count} proposal(s) recommend BLOCK enforcement — "
            f"review these first."
        )
    if warn_count:
        parts.append(f"{warn_count} proposal(s) at WARN level.")

    parts.append(
        "Proposals require maintainer approval before activation. "
        "Review each proposal's evidence and confidence before accepting."
    )

    return " ".join(parts)
