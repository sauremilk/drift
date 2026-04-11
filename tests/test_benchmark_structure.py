"""Structural validation of the three-tier benchmark framework.

Tier A — Deterministic micro-fixtures (ground_truth.py)
Tier B — Controlled mutation benchmark (mutation_benchmark.py)
Tier C — Real-world gold-standard labels (evaluate_benchmark.py)

These tests verify the *structure* of each tier, not the analysis itself.
They ensure that every signal has coverage and that data models stay consistent.
"""

from __future__ import annotations

from drift.models import SignalType
from tests.fixtures.ground_truth import (
    ALL_FIXTURES,
    FIXTURES_BY_KIND,
    FIXTURES_BY_SIGNAL,
    FixtureKind,
)

# ── Tier A: Ground-truth fixture completeness ──────────────────────────────

# Core signals that MUST have both TP and TN fixtures.
_CORE_SIGNALS: frozenset[SignalType] = frozenset(
    {
        SignalType.PATTERN_FRAGMENTATION,
        SignalType.ARCHITECTURE_VIOLATION,
        SignalType.MUTANT_DUPLICATE,
        SignalType.EXPLAINABILITY_DEFICIT,
        SignalType.TEMPORAL_VOLATILITY,
        SignalType.SYSTEM_MISALIGNMENT,
        SignalType.DOC_IMPL_DRIFT,
        SignalType.BROAD_EXCEPTION_MONOCULTURE,
        SignalType.TEST_POLARITY_DEFICIT,
        SignalType.GUARD_CLAUSE_DEFICIT,
    }
)


def test_all_core_signals_have_tp_fixture() -> None:
    """Every core signal must have at least one TP ground-truth fixture."""
    for sig in _CORE_SIGNALS:
        fixtures = FIXTURES_BY_SIGNAL.get(sig, [])
        has_tp = any(f.tp_expectations for f in fixtures)
        assert has_tp, f"Signal {sig.value} has no TP fixture"


def test_all_core_signals_have_tn_fixture() -> None:
    """Every core signal must have at least one TN ground-truth fixture."""
    for sig in _CORE_SIGNALS:
        fixtures = FIXTURES_BY_SIGNAL.get(sig, [])
        has_tn = any(f.fp_expectations for f in fixtures)
        assert has_tn, f"Signal {sig.value} has no TN fixture"


def test_fixture_names_are_unique() -> None:
    """Fixture names must be unique across ALL_FIXTURES."""
    names = [f.name for f in ALL_FIXTURES]
    assert len(names) == len(set(names)), (
        f"Duplicate fixture names: {[n for n in names if names.count(n) > 1]}"
    )


def test_every_fixture_has_at_least_one_expectation() -> None:
    """A fixture without expectations is pointless; catch accidental empties."""
    for f in ALL_FIXTURES:
        assert f.expected, f"Fixture {f.name!r} has zero expectations"


def test_inferred_kind_matches_expectations() -> None:
    """When kind is not explicitly set, inferred_kind must be consistent."""
    for f in ALL_FIXTURES:
        kind = f.inferred_kind
        if kind == FixtureKind.POSITIVE:
            assert f.tp_expectations, (
                f"Fixture {f.name!r} inferred as POSITIVE but has no TP expectation"
            )
        elif kind == FixtureKind.NEGATIVE:
            assert not f.tp_expectations, (
                f"Fixture {f.name!r} inferred as NEGATIVE but has TP expectations"
            )


def test_fixture_kind_index_covers_all_fixtures() -> None:
    """FIXTURES_BY_KIND must include every fixture in ALL_FIXTURES."""
    indexed = sum(len(v) for v in FIXTURES_BY_KIND.values())
    assert indexed == len(ALL_FIXTURES), (
        f"FIXTURES_BY_KIND has {indexed} entries but ALL_FIXTURES has {len(ALL_FIXTURES)}"
    )


def test_boundary_and_confounder_fixtures_exist() -> None:
    """At least one boundary and one confounder fixture must exist."""
    assert len(FIXTURES_BY_KIND[FixtureKind.BOUNDARY]) >= 1, "No BOUNDARY fixtures registered"
    assert len(FIXTURES_BY_KIND[FixtureKind.CONFOUNDER]) >= 1, "No CONFOUNDER fixtures registered"


# ── Tier B: Mutation benchmark model consistency ────────────────────────────


def test_mutation_entity_model_importable() -> None:
    """MutationEntity dataclass must be importable."""
    from scripts.mutation_benchmark import MutationEntity

    m = MutationEntity(
        id="avs_001",
        signal="architecture_violation",
        description="test",
    )
    assert m.must_detect is True
    assert m.klass == "injected_positive"


def test_entity_id_generation() -> None:
    """_entity_id must produce stable abbreviation-based IDs."""
    from scripts.mutation_benchmark import _entity_id

    assert _entity_id("architecture_violation", 1) == "avs_001"
    assert _entity_id("pattern_fragmentation", 3) == "pfs_003"
    assert _entity_id("mutant_duplicate", 12) == "mds_012"


# ── Tier C: Label key stability ──────────────────────────────────────────


def test_finding_keys_v2_includes_signal_and_location() -> None:
    """Key v2 must contain signal + file + line for collision resistance."""
    from scripts.evaluate_benchmark import _finding_keys

    finding = {
        "signal": "pattern_fragmentation",
        "title": "Inconsistent error handling",
        "file_path": "services/handler.py",
        "line": 15,
    }
    keys = _finding_keys("myrepo", finding)
    v2 = keys[0]

    assert "pattern_fragmentation" in v2
    assert "services/handler.py" in v2
    assert ":15:" in v2


def test_finding_keys_v1_is_backward_compatible() -> None:
    """Key v1 must be the legacy repo::title format."""
    from scripts.evaluate_benchmark import _finding_keys

    finding = {"signal": "eds", "title": "Complex function", "file_path": "a.py"}
    keys = _finding_keys("repo", finding)
    assert keys[1] == "repo::Complex function"
