"""Guardrail generation — transform findings into copy-pastable prompt constraints.

Reuses the existing ``negative_context`` generators (18 signal types) and adds
a formatting layer that produces structured, agent-ready guardrails.

Architecture::

    Finding → NegativeContext (via negative_context.py) → Guardrail (this module)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from drift.api_helpers import signal_abbrev
from drift.models import (
    Finding,
    NegativeContext,
    Severity,
    SignalType,
)
from drift.negative_context import findings_to_negative_context

# ---------------------------------------------------------------------------
# Public data model
# ---------------------------------------------------------------------------

_SEVERITY_ORDER = {
    Severity.CRITICAL: 0,
    Severity.HIGH: 1,
    Severity.MEDIUM: 2,
    Severity.LOW: 3,
    Severity.INFO: 4,
}

# Pre-task relevance factor per signal (spec §3.2)
_PRE_TASK_RELEVANCE: dict[SignalType, float] = {
    # Critical
    SignalType.ARCHITECTURE_VIOLATION: 1.0,
    SignalType.PATTERN_FRAGMENTATION: 1.0,
    SignalType.MUTANT_DUPLICATE: 1.0,
    # High
    SignalType.CO_CHANGE_COUPLING: 0.7,
    SignalType.CIRCULAR_IMPORT: 0.7,
    SignalType.FAN_OUT_EXPLOSION: 0.7,
    # Medium
    SignalType.BROAD_EXCEPTION_MONOCULTURE: 0.4,
    SignalType.EXCEPTION_CONTRACT_DRIFT: 0.4,
    SignalType.EXPLAINABILITY_DEFICIT: 0.4,
    SignalType.COHESION_DEFICIT: 0.4,
    # Low
    SignalType.TEST_POLARITY_DEFICIT: 0.1,
    SignalType.GUARD_CLAUSE_DEFICIT: 0.1,
    SignalType.NAMING_CONTRACT_VIOLATION: 0.1,
    SignalType.DOC_IMPL_DRIFT: 0.1,
}

# Constraint class templates per signal
_CONSTRAINT_TEMPLATES: dict[SignalType, str] = {
    SignalType.ARCHITECTURE_VIOLATION: "ARCHITECTURE",
    SignalType.PATTERN_FRAGMENTATION: "PATTERN",
    SignalType.MUTANT_DUPLICATE: "DEDUP",
    SignalType.CO_CHANGE_COUPLING: "CO_CHANGE",
    SignalType.CIRCULAR_IMPORT: "CYCLE",
    SignalType.FAN_OUT_EXPLOSION: "DEPENDENCY",
    SignalType.BROAD_EXCEPTION_MONOCULTURE: "ERROR_HANDLING",
    SignalType.EXCEPTION_CONTRACT_DRIFT: "ERROR_HANDLING",
    SignalType.COHESION_DEFICIT: "COHESION",
    SignalType.EXPLAINABILITY_DEFICIT: "COMPLEXITY",
}


@dataclass(slots=True)
class Guardrail:
    """A single prompt constraint derived from a drift finding."""

    id: str
    signal: str
    constraint_class: str
    severity: str
    constraint: str
    forbidden: str
    reason: str
    affected_files: list[str] = field(default_factory=list)
    prompt_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "id": self.id,
            "signal": self.signal,
            "constraint_class": self.constraint_class,
            "severity": self.severity,
            "constraint": self.constraint,
            "forbidden": self.forbidden,
            "reason": self.reason,
            "affected_files": self.affected_files,
            "prompt_text": self.prompt_text,
        }


def pre_task_relevance(signal_type: SignalType) -> float:
    """Return the pre-task relevance factor for a signal type."""
    return _PRE_TASK_RELEVANCE.get(signal_type, 0.0)


# ---------------------------------------------------------------------------
# NegativeContext → Guardrail transformation
# ---------------------------------------------------------------------------


def _nc_to_guardrail(nc: NegativeContext, idx: int) -> Guardrail:
    """Transform a single NegativeContext item into a Guardrail."""
    abbrev = signal_abbrev(nc.source_signal)
    constraint_class = _CONSTRAINT_TEMPLATES.get(nc.source_signal, "GENERAL")

    # Build concise constraint text from the NC description
    constraint = nc.description
    forbidden = nc.forbidden_pattern.split("\n")[0] if nc.forbidden_pattern else ""
    reason = nc.rationale.split(".")[0] + "." if nc.rationale else ""

    gid = f"GR-{abbrev}-{idx:03d}"

    prompt_line = f"CONSTRAINT [{abbrev}]: {constraint}"
    if forbidden:
        # Extract just the key message, not the code block
        forbidden_short = forbidden.replace("# ANTI-PATTERN:", "").strip()
        if forbidden_short:
            prompt_line += f" Do NOT: {forbidden_short}."

    return Guardrail(
        id=gid,
        signal=abbrev,
        constraint_class=constraint_class,
        severity=nc.severity.value,
        constraint=constraint,
        forbidden=forbidden,
        reason=reason,
        affected_files=nc.affected_files,
        prompt_text=prompt_line,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_guardrails(
    findings: list[Finding],
    *,
    max_guardrails: int = 10,
    min_severity: Severity = Severity.LOW,
) -> list[Guardrail]:
    """Generate prioritised guardrails from drift findings.

    Parameters
    ----------
    findings:
        Findings typically scoped to the resolved task scope.
    max_guardrails:
        Maximum number of guardrails to return.
    min_severity:
        Minimum severity threshold for guardrails.
    """
    # Generate negative context items from findings
    nc_items = findings_to_negative_context(
        findings,
        max_items=max_guardrails * 3,  # over-generate, then prioritise
    )

    # Filter by minimum severity
    min_rank = _SEVERITY_ORDER.get(min_severity, 4)
    nc_items = [
        nc for nc in nc_items
        if _SEVERITY_ORDER.get(nc.severity, 4) <= min_rank
    ]

    # Sort by: severity (desc), pre-task relevance (desc), confidence (desc)
    nc_items.sort(
        key=lambda nc: (
            _SEVERITY_ORDER.get(nc.severity, 4),
            -_PRE_TASK_RELEVANCE.get(nc.source_signal, 0.0),
            -nc.confidence,
        ),
    )

    # Deduplicate by signal + first affected file
    seen: set[tuple[str, str]] = set()
    unique: list[NegativeContext] = []
    for nc in nc_items:
        key = (nc.source_signal.value, nc.affected_files[0] if nc.affected_files else "")
        if key not in seen:
            seen.add(key)
            unique.append(nc)

    # Transform to guardrails
    guardrails = [_nc_to_guardrail(nc, i + 1) for i, nc in enumerate(unique[:max_guardrails])]

    return guardrails


def guardrails_to_prompt_block(guardrails: list[Guardrail]) -> str:
    """Format guardrails as a copy-pastable text block for agent prompts.

    Returns
    -------
    A markdown-flavoured string suitable for direct injection into agent
    system prompts.
    """
    if not guardrails:
        return ""

    lines = [
        "## Structural Constraints (generated by drift brief)",
        "",
        "The following constraints are derived from static analysis of the target scope.",
        "Violating these constraints will likely degrade architectural coherence.",
        "",
    ]
    for i, gr in enumerate(guardrails, start=1):
        lines.append(f"{i}. {gr.prompt_text}")

    return "\n".join(lines)
