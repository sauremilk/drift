"""Decision-rule matching for Architecture Graph targets.

Phase D of the Architecture Runtime Blueprint.

``match_decisions`` evaluates which ``ArchDecision`` records apply to a given
target path using ``fnmatch``-style glob patterns.  Results are returned in
enforcement-priority order (block > warn > info).
"""

from __future__ import annotations

from fnmatch import fnmatch
from typing import Any

from drift.arch_graph._models import ArchDecision

# Enforcement severity (lower = higher priority)
_ENFORCEMENT_ORDER: dict[str, int] = {"block": 0, "warn": 1, "info": 2}


def match_decisions(
    decisions: list[ArchDecision],
    target: str,
    *,
    include_inactive: bool = False,
    enforcement: str | None = None,
) -> list[ArchDecision]:
    """Return decisions whose *scope* matches *target*.

    Parameters
    ----------
    decisions:
        All decisions from the ``ArchGraph``.
    target:
        A file path or module path to match against decision scopes.
    include_inactive:
        When *False* (default), decisions with ``active=False`` are excluded.
    enforcement:
        If set, only return decisions with this enforcement level.

    Returns
    -------
    list[ArchDecision]
        Matching decisions, sorted by enforcement severity (block first).
    """
    target_normalised = target.replace("\\", "/")

    matched: list[ArchDecision] = []
    for dec in decisions:
        if not include_inactive and not dec.active:
            continue
        if enforcement is not None and dec.enforcement != enforcement:
            continue
        if fnmatch(target_normalised, dec.scope):
            matched.append(dec)

    matched.sort(key=lambda d: _ENFORCEMENT_ORDER.get(d.enforcement, 99))
    return matched


def format_decision_constraints(
    decisions: list[ArchDecision],
) -> list[dict[str, Any]]:
    """Format matched decisions as JSON-safe constraint dicts for steer().

    Returns decisions sorted by enforcement priority (block > warn > info).
    """
    sorted_decisions = sorted(
        decisions,
        key=lambda d: _ENFORCEMENT_ORDER.get(d.enforcement, 99),
    )
    return [
        {
            "id": d.id,
            "scope": d.scope,
            "rule": d.rule,
            "enforcement": d.enforcement,
            "source": d.source,
        }
        for d in sorted_decisions
    ]
