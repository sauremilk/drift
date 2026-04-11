"""Signal identity mapping — abbreviations, canonical names, and scope labels.

Provides the foundational signal-name vocabulary consumed by API response
shaping, finding rendering, and task-graph construction.
"""

from __future__ import annotations

from drift.models import SignalType

_ABBREV_TO_SIGNAL: dict[str, SignalType] = {
    "PFS": SignalType.PATTERN_FRAGMENTATION,
    "AVS": SignalType.ARCHITECTURE_VIOLATION,
    "MDS": SignalType.MUTANT_DUPLICATE,
    "TVS": SignalType.TEMPORAL_VOLATILITY,
    "EDS": SignalType.EXPLAINABILITY_DEFICIT,
    "SMS": SignalType.SYSTEM_MISALIGNMENT,
    "DIA": SignalType.DOC_IMPL_DRIFT,
    "BEM": SignalType.BROAD_EXCEPTION_MONOCULTURE,
    "TPD": SignalType.TEST_POLARITY_DEFICIT,
    "GCD": SignalType.GUARD_CLAUSE_DEFICIT,
    "NBV": SignalType.NAMING_CONTRACT_VIOLATION,
    "BAT": SignalType.BYPASS_ACCUMULATION,
    "ECM": SignalType.EXCEPTION_CONTRACT_DRIFT,
    "COD": SignalType.COHESION_DEFICIT,
    "CCC": SignalType.CO_CHANGE_COUPLING,
    "TSA": SignalType.TS_ARCHITECTURE,
    "CXS": SignalType.COGNITIVE_COMPLEXITY,
    "FOE": SignalType.FAN_OUT_EXPLOSION,
    "CIR": SignalType.CIRCULAR_IMPORT,
    "DCA": SignalType.DEAD_CODE_ACCUMULATION,
    "MAZ": SignalType.MISSING_AUTHORIZATION,
    "ISD": SignalType.INSECURE_DEFAULT,
    "HSC": SignalType.HARDCODED_SECRET,
    "PHR": SignalType.PHANTOM_REFERENCE,
}

_SIGNAL_TO_ABBREV: dict[str, str] = {str(v): k for k, v in _ABBREV_TO_SIGNAL.items()}

VALID_SIGNAL_IDS = sorted(_ABBREV_TO_SIGNAL.keys())


def signal_abbrev_map() -> dict[str, str]:
    """Return stable abbreviation -> canonical signal_type mapping."""
    return {abbrev: str(signal_type) for abbrev, signal_type in sorted(_ABBREV_TO_SIGNAL.items())}


def resolve_signal(name: str) -> SignalType | None:
    """Resolve a signal abbreviation or full name to ``SignalType``."""
    upper = name.upper()
    if upper in _ABBREV_TO_SIGNAL:
        return _ABBREV_TO_SIGNAL[upper]
    try:
        return SignalType(name)
    except ValueError:
        return None


def signal_abbrev(signal_type: str) -> str:
    """Return the short abbreviation for a signal type string."""
    return _SIGNAL_TO_ABBREV.get(str(signal_type), str(signal_type)[:3].upper())


def signal_scope_label(
    *,
    selected: list[str] | None = None,
    ignored: list[str] | None = None,
) -> str:
    """Build a compact label describing which signals contributed to a score."""
    if selected:
        normalized = sorted({item.strip().upper() for item in selected if item.strip()})
        if normalized:
            return "+".join(normalized)
    if ignored:
        normalized = sorted({item.strip().upper() for item in ignored if item.strip()})
        if normalized:
            return f"all-minus:{'+'.join(normalized)}"
    return "all"
