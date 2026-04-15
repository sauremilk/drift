"""Central signal metadata registry.

Single source of truth for signal IDs, abbreviations, display names,
categories, default weights, and **repair coverage** for all core signals.

Plugin signals can register themselves at import time via
``register_signal_meta()``. The registry is intentionally kept free of
heavy imports (no AST, no config loading) so that it can be imported
early in the module graph.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

# ---------------------------------------------------------------------------
# Repair-level type (lightweight alias — authoritative enum lives in models)
# ---------------------------------------------------------------------------

RepairLevelLiteral = Literal["diagnosis", "plannable", "example_based", "verifiable"]
"""Repair-coverage maturity level for a signal.

* ``diagnosis``     – Finding description only, no actionable repair hints.
* ``plannable``     – Structured recommendation (effort/impact), no code examples.
* ``example_based`` – Exemplary fix snippets or code-level suggestions.
* ``verifiable``    – Repair + machine-executable verification plan.
"""

# ---------------------------------------------------------------------------
# Metadata dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SignalMeta:
    """Static metadata for a single Drift signal."""

    signal_id: str
    """Stable string key matching SignalType value, e.g. 'pattern_fragmentation'."""

    abbrev: str
    """Short uppercase abbreviation, e.g. 'PFS'."""

    signal_name: str
    """Human-readable display name."""

    category: str
    """Grouping category: 'structural_risk', 'architecture_boundary',
    'style_hygiene', or 'security'."""

    default_weight: float
    """Default composite-score weight (0.0 = report-only)."""

    description: str = ""
    """Optional one-sentence description."""

    is_core: bool = True
    """False for plugin-provided signals."""

    # -- Repair coverage metadata ------------------------------------------

    repair_level: RepairLevelLiteral = "diagnosis"
    """Repair-coverage maturity level (see ``RepairLevelLiteral`` docstring)."""

    has_recommender: bool = False
    """True when ``recommendations.py`` has a dedicated ``_recommend_*`` function."""

    has_fix_field: bool = False
    """True when the signal populates ``Finding.fix`` with actionable text."""

    has_verify_plan: bool = False
    """True when ``agent_tasks.py`` generates a signal-specific verify_plan."""

    benchmark_coverage: Literal["strong", "moderate", "limited", "none"] = "none"
    """Strength of repair-benchmark evidence (real-world + mutation tests)."""


# ---------------------------------------------------------------------------
# Core signal table
# ---------------------------------------------------------------------------

_CORE_SIGNALS: Final[list[SignalMeta]] = [
    # ── structural_risk ───────────────────────────────────────────────────
    SignalMeta(
        "pattern_fragmentation", "PFS", "Pattern Fragmentation",
        "structural_risk", 0.16,
        "Detects inconsistent structural patterns across similar files.",
        repair_level="verifiable",
        has_recommender=True, has_fix_field=True, has_verify_plan=True,
        benchmark_coverage="moderate",
    ),
    SignalMeta(
        "mutant_duplicate", "MDS", "Mutant Duplicate",
        "structural_risk", 0.13,
        "Detects near-duplicate functions that diverged over time.",
        repair_level="verifiable",
        has_recommender=True, has_fix_field=True, has_verify_plan=True,
        benchmark_coverage="strong",
    ),
    SignalMeta(
        "temporal_volatility", "TVS", "Temporal Volatility",
        "structural_risk", 0.0,
        "Measures churn-based instability (report-only, weight=0).",
        repair_level="plannable",
        has_recommender=True, has_fix_field=True, has_verify_plan=True,
        benchmark_coverage="none",
    ),
    SignalMeta(
        "system_misalignment", "SMS", "System Misalignment",
        "structural_risk", 0.08,
        "Detects structural inconsistencies across subsystem boundaries.",
        repair_level="plannable",
        has_recommender=True, has_fix_field=True, has_verify_plan=True,
        benchmark_coverage="none",
    ),
    SignalMeta(
        "test_polarity_deficit", "TPD", "Test Polarity Deficit",
        "structural_risk", 0.04,
        "Detects missing negative test coverage.",
        repair_level="example_based",
        has_recommender=False, has_fix_field=True, has_verify_plan=True,
        benchmark_coverage="none",
    ),
    SignalMeta(
        "bypass_accumulation", "BAT", "Bypass Accumulation",
        "structural_risk", 0.03,
        "Detects accumulation of bypass patterns (noqa, pragma, type: ignore).",
        repair_level="example_based",
        has_recommender=False, has_fix_field=True, has_verify_plan=True,
        benchmark_coverage="none",
    ),
    SignalMeta(
        "exception_contract_drift", "ECM", "Exception Contract Drift",
        "structural_risk", 0.03,
        "Detects inconsistent exception handling contracts across the codebase.",
        repair_level="plannable",
        has_recommender=False, has_fix_field=True, has_verify_plan=True,
        benchmark_coverage="none",
    ),
    SignalMeta(
        "ts_architecture", "TSA", "TS Architecture",
        "structural_risk", 0.0,
        "TypeScript-specific architecture signals (report-only).",
        repair_level="plannable",
        has_recommender=False, has_fix_field=True, has_verify_plan=True,
        benchmark_coverage="none",
    ),
    # ── architecture_boundary ─────────────────────────────────────────────
    SignalMeta(
        "architecture_violation", "AVS", "Architecture Violation",
        "architecture_boundary", 0.16,
        "Detects imports that cross declared architecture layer boundaries.",
        repair_level="plannable",
        has_recommender=True, has_fix_field=False, has_verify_plan=True,
        benchmark_coverage="limited",
    ),
    SignalMeta(
        "circular_import", "CIR", "Circular Import",
        "architecture_boundary", 0.0,
        "Detects circular import chains (report-only).",
        repair_level="plannable",
        has_recommender=False, has_fix_field=False, has_verify_plan=True,
        benchmark_coverage="none",
    ),
    SignalMeta(
        "co_change_coupling", "CCC", "Co-Change Coupling",
        "architecture_boundary", 0.005,
        "Detects files that always change together, indicating hidden coupling.",
        repair_level="verifiable",
        has_recommender=True, has_fix_field=True, has_verify_plan=True,
        benchmark_coverage="moderate",
    ),
    SignalMeta(
        "cohesion_deficit", "COD", "Cohesion Deficit",
        "architecture_boundary", 0.01,
        "Detects modules with low internal cohesion.",
        repair_level="example_based",
        has_recommender=True, has_fix_field=True, has_verify_plan=False,
        benchmark_coverage="none",
    ),
    SignalMeta(
        "fan_out_explosion", "FOE", "Fan-Out Explosion",
        "architecture_boundary", 0.005,
        "Detects modules with excessive outgoing dependencies.",
        repair_level="plannable",
        has_recommender=False, has_fix_field=True, has_verify_plan=True,
        benchmark_coverage="none",
    ),
    # ── style_hygiene ─────────────────────────────────────────────────────
    SignalMeta(
        "naming_contract_violation", "NBV", "Naming Contract Violation",
        "style_hygiene", 0.04,
        "Detects naming inconsistencies and contract violations.",
        repair_level="example_based",
        has_recommender=False, has_fix_field=True, has_verify_plan=True,
        benchmark_coverage="none",
    ),
    SignalMeta(
        "doc_impl_drift", "DIA", "Doc/Impl Drift",
        "style_hygiene", 0.04,
        "Detects divergence between docstrings and implementation.",
        repair_level="verifiable",
        has_recommender=True, has_fix_field=False, has_verify_plan=False,
        benchmark_coverage="strong",
    ),
    SignalMeta(
        "explainability_deficit", "EDS", "Explainability Deficit",
        "style_hygiene", 0.09,
        "Detects under-documented complex code.",
        repair_level="plannable",
        has_recommender=True, has_fix_field=False, has_verify_plan=False,
        benchmark_coverage="moderate",
    ),
    SignalMeta(
        "broad_exception_monoculture", "BEM", "Broad Exception Monoculture",
        "style_hygiene", 0.04,
        "Detects overuse of broad exception catches.",
        repair_level="example_based",
        has_recommender=False, has_fix_field=True, has_verify_plan=True,
        benchmark_coverage="none",
    ),
    SignalMeta(
        "guard_clause_deficit", "GCD", "Guard Clause Deficit",
        "style_hygiene", 0.03,
        "Detects missing guard clauses in complex functions.",
        repair_level="example_based",
        has_recommender=False, has_fix_field=True, has_verify_plan=True,
        benchmark_coverage="none",
    ),
    SignalMeta(
        "dead_code_accumulation", "DCA", "Dead Code Accumulation",
        "style_hygiene", 0.0,
        "Detects unused code accumulation (report-only).",
        repair_level="verifiable",
        has_recommender=False, has_fix_field=True, has_verify_plan=True,
        benchmark_coverage="limited",
    ),
    SignalMeta(
        "cognitive_complexity", "CXS", "Cognitive Complexity",
        "style_hygiene", 0.0,
        "Detects high cognitive complexity (report-only).",
        repair_level="example_based",
        has_recommender=False, has_fix_field=True, has_verify_plan=True,
        benchmark_coverage="none",
    ),
    # ── security ──────────────────────────────────────────────────────────
    SignalMeta(
        "missing_authorization", "MAZ", "Missing Authorization",
        "security", 0.02,
        "Detects endpoints or functions lacking authorization checks.",
        repair_level="example_based",
        has_recommender=False, has_fix_field=True, has_verify_plan=True,
        benchmark_coverage="none",
    ),
    SignalMeta(
        "insecure_default", "ISD", "Insecure Default",
        "security", 0.01,
        "Detects insecure default configurations.",
        repair_level="example_based",
        has_recommender=False, has_fix_field=True, has_verify_plan=False,
        benchmark_coverage="none",
    ),
    SignalMeta(
        "hardcoded_secret", "HSC", "Hardcoded Secret",
        "security", 0.01,
        "Detects hardcoded secrets and credentials.",
        repair_level="example_based",
        has_recommender=False, has_fix_field=True, has_verify_plan=True,
        benchmark_coverage="none",
    ),
    # ── ai_quality ────────────────────────────────────────────────────────
    SignalMeta(
        "phantom_reference", "PHR", "Phantom Reference",
        "ai_quality", 0.02,
        "Detects unresolvable function/class references (AI hallucination indicator).",
        repair_level="example_based",
        has_recommender=False, has_fix_field=True, has_verify_plan=True,
        benchmark_coverage="none",
    ),
    # ── typescript_quality ────────────────────────────────────────────────
    SignalMeta(
        "type_safety_bypass", "TSB", "Type Safety Bypass",
        "style_hygiene", 0.0,
        "Detects patterns that bypass TypeScript's type system (as any, @ts-ignore, double casts).",
        repair_level="example_based",
        has_recommender=False, has_fix_field=True, has_verify_plan=True,
        benchmark_coverage="moderate",
    ),
]

# ---------------------------------------------------------------------------
# Registry store
# ---------------------------------------------------------------------------

# signal_id → SignalMeta
_REGISTRY: dict[str, SignalMeta] = {m.signal_id: m for m in _CORE_SIGNALS}

# abbrev → signal_id (upper case keys only)
_ABBREV_MAP: dict[str, str] = {m.abbrev: m.signal_id for m in _CORE_SIGNALS}


def register_signal_meta(meta: SignalMeta) -> None:
    """Register metadata for a plugin signal.

    Call this from your plugin's top-level module before Drift initialises.
    Duplicate registrations for the same ``signal_id`` are silently ignored
    to keep import-order idempotent.

    Raises:
        ValueError: If ``meta.abbrev`` is already claimed by a different signal.
            Plugin signals must use unique abbreviations that do not collide
            with core or other plugin abbreviations.
    """
    if meta.signal_id in _REGISTRY:
        return  # Already registered — core or duplicate plugin
    if meta.abbrev in _ABBREV_MAP:
        existing_id = _ABBREV_MAP[meta.abbrev]
        raise ValueError(
            f"Abbreviation {meta.abbrev!r} is already registered for signal "
            f"{existing_id!r}. Plugin signal {meta.signal_id!r} must use a "
            f"unique abbreviation."
        )
    _REGISTRY[meta.signal_id] = meta
    _ABBREV_MAP[meta.abbrev] = meta.signal_id


# ---------------------------------------------------------------------------
# Accessor helpers (public API)
# ---------------------------------------------------------------------------


def get_all_meta() -> list[SignalMeta]:
    """Return metadata for all registered signals (core + plugins)."""
    return list(_REGISTRY.values())


def get_meta(signal_id: str) -> SignalMeta | None:
    """Return metadata for a single signal by its ID, or None."""
    return _REGISTRY.get(signal_id)


def get_abbrev_map() -> dict[str, str]:
    """Return map of abbreviation → signal_id for all registered signals.

    Keys are uppercase abbreviations (e.g. 'PFS', 'AVS').
    """
    return dict(_ABBREV_MAP)


def get_signal_to_abbrev() -> dict[str, str]:
    """Return map of signal_id → abbreviation for all registered signals."""
    return {m.signal_id: m.abbrev for m in _REGISTRY.values()}


def get_weight_defaults() -> dict[str, float]:
    """Return map of signal_id → default_weight for all registered signals."""
    return {m.signal_id: m.default_weight for m in _REGISTRY.values()}


def get_signals_by_category(category: str) -> list[SignalMeta]:
    """Return all signals belonging to the given category."""
    return [m for m in _REGISTRY.values() if m.category == category]


def resolve_abbrev(abbrev: str) -> str | None:
    """Resolve an abbreviation to its signal_id, case-insensitive."""
    return _ABBREV_MAP.get(abbrev.upper())


def get_repair_coverage_summary() -> dict[str, dict[str, object]]:
    """Return repair-coverage metadata for every registered signal.

    Returns a dict keyed by ``signal_id``, each value containing the
    repair-level classification and capability flags.  Used by the
    coverage-matrix generator and by ``agent_tasks`` to derive
    ``repair_maturity``.
    """
    return {
        m.signal_id: {
            "abbrev": m.abbrev,
            "signal_name": m.signal_name,
            "category": m.category,
            "repair_level": m.repair_level,
            "has_recommender": m.has_recommender,
            "has_fix_field": m.has_fix_field,
            "has_verify_plan": m.has_verify_plan,
            "benchmark_coverage": m.benchmark_coverage,
        }
        for m in _REGISTRY.values()
    }


# ---------------------------------------------------------------------------
# Test helpers (not part of the stable public API)
# ---------------------------------------------------------------------------

# Cache of plugin-registered signal IDs so tests can reset state
_PLUGIN_SIGNAL_IDS: list[str] = []


def _reset_registry() -> None:
    """Reset plugin registrations. For use in tests only."""
    global _REGISTRY, _ABBREV_MAP  # noqa: PLW0603
    # Restore core signals only
    _REGISTRY = {m.signal_id: m for m in _CORE_SIGNALS}
    _ABBREV_MAP = {m.abbrev: m.signal_id for m in _CORE_SIGNALS}
    _PLUGIN_SIGNAL_IDS.clear()
