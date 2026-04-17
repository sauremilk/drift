"""Feedback loop — recurring pattern detection and rule proposals.

Phase E of the Architecture Runtime Blueprint.

Analyses ``ArchGraph`` hotspots to detect recurring drift signals and
proposes new ``ArchDecision`` rules that can be reviewed by maintainers.
"""

from __future__ import annotations

from collections import defaultdict

from drift.arch_graph._models import (
    ArchDecision,
    ArchGraph,
    PatternProposal,
)

# Signal categories that map to stronger enforcement recommendations
_BOUNDARY_SIGNALS: frozenset[str] = frozenset({
    "architecture_violation",
    "circular_import",
    "co_change_coupling",
    "fan_out_explosion",
})

# Default thresholds
_DEFAULT_MIN_OCCURRENCES = 4


# ---------------------------------------------------------------------------
# Pattern detection
# ---------------------------------------------------------------------------


def detect_recurring_patterns(
    graph: ArchGraph,
    *,
    min_occurrences: int = _DEFAULT_MIN_OCCURRENCES,
) -> list[PatternProposal]:
    """Detect recurring signal patterns from hotspots.

    Hotspots are aggregated by module (longest matching module path).
    Only signals meeting *min_occurrences* across a module's hotspots
    are promoted to proposals.

    Parameters
    ----------
    graph:
        A populated ``ArchGraph`` with hotspots.
    min_occurrences:
        Minimum total occurrences of a signal within a module to be
        considered a pattern.

    Returns
    -------
    list[PatternProposal]
        Detected patterns, each with a proposed ``ArchDecision``.
    """
    if not graph.hotspots:
        return []

    # Aggregate signals by module path
    # module_path -> signal_id -> (total_count, trend_set, evidence_files)
    module_signals: dict[str, dict[str, _AggregatedSignal]] = defaultdict(
        lambda: defaultdict(lambda: _AggregatedSignal())
    )

    for hs in graph.hotspots:
        module_path = _resolve_module_path(graph, hs.path)
        for signal_id, count in hs.recurring_signals.items():
            agg = module_signals[module_path][signal_id]
            agg.total += count
            agg.trends.add(hs.trend)
            agg.files.append(hs.path)

    # Generate proposals for qualifying patterns
    proposals: list[PatternProposal] = []
    counter = 0

    for module_path, signals in sorted(module_signals.items()):
        for signal_id, agg in sorted(signals.items()):
            if agg.total < min_occurrences:
                continue

            counter += 1
            is_degrading = "degrading" in agg.trends
            is_boundary = signal_id in _BOUNDARY_SIGNALS

            confidence = _compute_confidence(agg.total, min_occurrences, is_degrading)
            enforcement = _pick_enforcement(agg.total, is_degrading, is_boundary)
            pattern_type = (
                "boundary_violation" if is_boundary else "recurring_signal"
            )

            proposals.append(
                PatternProposal(
                    pattern_type=pattern_type,
                    module_path=module_path,
                    signal_id=signal_id,
                    occurrences=agg.total,
                    proposed_decision=ArchDecision(
                        id=f"PROP-{counter:03d}",
                        scope=f"{module_path}/**",
                        rule=_generate_rule_text(signal_id, module_path, agg.total),
                        enforcement=enforcement,
                    ),
                    confidence=confidence,
                    evidence_files=list(agg.files),
                )
            )

    return proposals


# ---------------------------------------------------------------------------
# Decision proposals (with deduplication)
# ---------------------------------------------------------------------------


def propose_decisions(
    graph: ArchGraph,
    *,
    min_occurrences: int = _DEFAULT_MIN_OCCURRENCES,
) -> list[PatternProposal]:
    """Detect patterns and filter out already-covered decisions.

    Parameters
    ----------
    graph:
        A populated ``ArchGraph`` with hotspots and existing decisions.
    min_occurrences:
        Minimum recurrence threshold for pattern detection.

    Returns
    -------
    list[PatternProposal]
        Proposals that don't duplicate existing decision rules.
    """
    patterns = detect_recurring_patterns(graph, min_occurrences=min_occurrences)
    if not patterns:
        return []

    existing_rules = {d.rule for d in graph.decisions}

    return [
        p for p in patterns
        if p.proposed_decision.rule not in existing_rules
    ]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


class _AggregatedSignal:
    """Mutable accumulator for per-module signal aggregation."""

    __slots__ = ("total", "trends", "files")

    def __init__(self) -> None:
        self.total: int = 0
        self.trends: set[str] = set()
        self.files: list[str] = []


def _resolve_module_path(graph: ArchGraph, file_path: str) -> str:
    """Map a file path to its enclosing module in the graph."""
    normalised = file_path.replace("\\", "/")
    best_match = ""
    for m in graph.modules:
        m_norm = m.path.replace("\\", "/")
        matches = normalised.startswith(m_norm + "/") or normalised == m_norm
        if matches and len(m_norm) > len(best_match):
            best_match = m_norm
    # Fallback: derive from first path segment pair
    if not best_match:
        parts = normalised.rsplit("/", 1)
        best_match = parts[0] if len(parts) > 1 else normalised
    return best_match


def _compute_confidence(
    total: int,
    min_occurrences: int,
    is_degrading: bool,
) -> float:
    """Compute a confidence score in [0.5, 1.0]."""
    # Base: how far above threshold (0.5 at threshold, approaches 1.0)
    ratio = min(total / max(min_occurrences * 3, 1), 1.0)
    base = 0.5 + ratio * 0.35

    # Degrading trend boosts confidence
    if is_degrading:
        base = min(base + 0.1, 1.0)

    return round(base, 2)


def _pick_enforcement(
    total: int,
    is_degrading: bool,
    is_boundary: bool,
) -> str:
    """Choose enforcement level based on severity signals."""
    if is_boundary and (total >= 5 or is_degrading):
        return "block"
    if is_degrading or total >= 6:
        return "warn"
    return "info"


_SIGNAL_RULE_TEMPLATES: dict[str, str] = {
    "pattern_fragmentation": (
        "Reduce pattern fragmentation in {module} ({count} recurring occurrences)"
    ),
    "architecture_violation": (
        "Enforce architecture boundaries in {module} ({count} violations detected)"
    ),
    "naming_contract_violation": "Enforce naming conventions in {module} ({count} violations)",
    "mutant_duplicate": "Eliminate near-duplicate code in {module} ({count} occurrences)",
    "doc_impl_drift": "Keep documentation in sync in {module} ({count} drift occurrences)",
    "circular_import": "Break circular imports in {module} ({count} occurrences)",
    "co_change_coupling": "Reduce implicit coupling in {module} ({count} co-change patterns)",
    "fan_out_explosion": "Reduce fan-out in {module} ({count} excessive dependencies)",
}

_DEFAULT_TEMPLATE = "Address recurring {signal} findings in {module} ({count} occurrences)"


def _generate_rule_text(signal_id: str, module_path: str, count: int) -> str:
    """Generate a human-readable rule from pattern data."""
    template = _SIGNAL_RULE_TEMPLATES.get(signal_id, _DEFAULT_TEMPLATE)
    return template.format(signal=signal_id, module=module_path, count=count)
