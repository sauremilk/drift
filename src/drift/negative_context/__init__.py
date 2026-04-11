"""Negative context generation — translates drift findings into anti-pattern warnings.

This package converts :class:`~drift.models.Finding` objects into structured
:class:`~drift.models.NegativeContext` items that AI coding agents can use
as negative constraints ("do NOT reproduce this pattern").

Public API
----------
- :func:`findings_to_negative_context` — main entry point
- :func:`negative_context_to_dict` — serialization helper
"""

from __future__ import annotations

from typing import Any

# Import generators module to trigger @_register side effects
import drift.negative_context.generators as _generators_mod  # noqa: F401
from drift.models import (
    Finding,
    NegativeContext,
    NegativeContextScope,
    Severity,
)
from drift.negative_context.core import (
    _FALLBACK_ONLY_SIGNALS,
    _GENERATORS,
    _SEVERITY_SCORE,
    _neg_id,
    _policy_covered_signal_types,
    _policy_uncovered_signal_types,
)

# Re-export the fallback generator for direct use in the public function
_gen_fallback = _generators_mod._gen_fallback

__all__ = [
    "findings_to_negative_context",
    "negative_context_to_dict",
    # Backward compatibility — used by tests and internal code
    "_FALLBACK_ONLY_SIGNALS",
    "_GENERATORS",
    "_neg_id",
    "_policy_covered_signal_types",
    "_policy_uncovered_signal_types",
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def findings_to_negative_context(
    findings: list[Finding],
    *,
    scope: str | None = None,
    target_file: str | None = None,
    max_items: int = 50,
    min_score: float = 0.0,
) -> list[NegativeContext]:
    """Convert drift findings into negative context items for agents.

    Parameters
    ----------
    findings:
        List of Finding objects from a drift analysis.
    scope:
        Filter by scope: "file", "module", or "repo".  None = all.
    target_file:
        Filter to items affecting a specific file path.
    max_items:
        Maximum items to return (prioritized by severity).
    min_score:
        Skip findings below this score unless they are HIGH/CRITICAL
        severity.  Reduces noise from low-confidence structural matches.
    """
    items: list[NegativeContext] = []
    seen_ids: set[str] = set()

    for finding in findings:
        # S3: skip low-score findings unless high severity
        if (
            min_score > 0.0
            and finding.score < min_score
            and finding.severity not in (Severity.CRITICAL, Severity.HIGH)
        ):
            continue

        generator = _GENERATORS.get(str(finding.signal_type), _gen_fallback)
        generated = generator(finding)

        for item in generated:
            if item.anti_pattern_id in seen_ids:
                continue
            seen_ids.add(item.anti_pattern_id)

            # Filter by scope
            if scope:
                try:
                    requested = NegativeContextScope(scope)
                    if item.scope != requested:
                        continue
                except ValueError:
                    pass

            # Filter by target file
            if target_file and target_file not in item.affected_files:
                continue

            items.append(item)

    # Sort by severity (highest first), then confidence
    items.sort(
        key=lambda nc: (-_SEVERITY_SCORE.get(nc.severity, 0), -nc.confidence),
    )

    return items[:max_items]


def negative_context_to_dict(nc: NegativeContext) -> dict[str, Any]:
    """Serialize a NegativeContext to a JSON-compatible dict."""
    return {
        "anti_pattern_id": nc.anti_pattern_id,
        "category": nc.category.value,
        "source_signal": nc.source_signal,
        "severity": nc.severity.value,
        "scope": nc.scope.value,
        "description": nc.description,
        "forbidden_pattern": nc.forbidden_pattern,
        "canonical_alternative": nc.canonical_alternative,
        "affected_files": nc.affected_files,
        "confidence": nc.confidence,
        "rationale": nc.rationale,
        "metadata": nc.metadata,
    }
