"""Tests for RepairTemplateRegistry (ADR-065)."""

from __future__ import annotations

import json
import pytest
from pathlib import Path

from drift.models import RegressionPattern, RegressionReasonCode
from drift.repair_template_registry import (
    MIN_OUTCOMES_FOR_CONFIDENCE,
    RepairTemplateEntry,
    RepairTemplateRegistry,
    _entry_from_dict,
    _entry_to_dict,
    _regression_pattern_from_dict,
    _regression_pattern_to_dict,
    get_registry,
    reset_registry,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset the module-level singleton before and after each test."""
    reset_registry()
    yield
    reset_registry()


@pytest.fixture
def empty_registry():
    r = RepairTemplateRegistry()
    r.load(seed_path=Path("/does/not/exist"), outcomes_path=Path("/does/not/exist"))
    return r


@pytest.fixture
def seed_file(tmp_path: Path) -> Path:
    data = {
        "entries": [
            {
                "signal": "mutant_duplicate",
                "edit_kind": "merge_function_body",
                "context_class": "production",
                "improving_count": 5,
                "stable_count": 0,
                "regressing_count": 1,
                "regression_patterns": [
                    {
                        "edit_kind": "rename_symbol",
                        "context_feature": "no_body_change",
                        "reason_code": "cosmetic_only",
                    }
                ],
                "evidence_sources": ["benchmark_results/repair/summary.json"],
                "last_updated": "2026-04-12T00:00:00+00:00",
            },
            {
                "signal": "pattern_fragmentation",
                "edit_kind": "normalize_pattern",
                "context_class": "production",
                "improving_count": 4,
                "stable_count": 0,
                "regressing_count": 0,
                "regression_patterns": [],
                "evidence_sources": [],
                "last_updated": "2026-04-12T00:00:00+00:00",
            },
        ]
    }
    p = tmp_path / "templates.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


@pytest.fixture
def outcomes_file(tmp_path: Path) -> Path:
    return tmp_path / "outcomes.jsonl"


# ---------------------------------------------------------------------------
# Serialization round-trip
# ---------------------------------------------------------------------------


def test_regression_pattern_roundtrip():
    rp = RegressionPattern(
        edit_kind="rename_symbol",
        context_feature="no_body_change",
        reason_code=RegressionReasonCode.COSMETIC_ONLY,
    )
    d = _regression_pattern_to_dict(rp)
    restored = _regression_pattern_from_dict(d)
    assert restored.edit_kind == rp.edit_kind
    assert restored.context_feature == rp.context_feature
    assert restored.reason_code == rp.reason_code


def test_entry_roundtrip():
    entry = RepairTemplateEntry(
        signal="mutant_duplicate",
        edit_kind="merge_function_body",
        context_class="production",
        improving_count=5,
        regressing_count=1,
        regression_patterns=[
            RegressionPattern(
                edit_kind="rename_symbol",
                context_feature="no_body_change",
                reason_code=RegressionReasonCode.COSMETIC_ONLY,
            )
        ],
    )
    d = _entry_to_dict(entry)
    restored = _entry_from_dict(d)
    assert restored.signal == entry.signal
    assert restored.edit_kind == entry.edit_kind
    assert restored.context_class == entry.context_class
    assert restored.improving_count == entry.improving_count
    assert restored.regressing_count == entry.regressing_count
    assert len(restored.regression_patterns) == 1
    assert restored.regression_patterns[0].reason_code == RegressionReasonCode.COSMETIC_ONLY


# ---------------------------------------------------------------------------
# Load seed
# ---------------------------------------------------------------------------


def test_load_seed(seed_file: Path):
    r = RepairTemplateRegistry()
    r.load(seed_path=seed_file, outcomes_path=Path("/does/not/exist"))

    entry = r.lookup("mutant_duplicate", "merge_function_body", "production")
    assert entry is not None
    assert entry.improving_count == 5
    assert entry.regressing_count == 1
    assert len(entry.regression_patterns) == 1
    assert entry.regression_patterns[0].reason_code == RegressionReasonCode.COSMETIC_ONLY


def test_load_missing_seed_does_not_raise():
    r = RepairTemplateRegistry()
    r.load(seed_path=Path("/nonexistent/path.json"), outcomes_path=Path("/nonexistent/outcomes.jsonl"))
    # No exception, empty registry
    assert r.lookup("any_signal", "any_edit_kind") is None


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------


def test_lookup_exact_match(seed_file: Path):
    r = RepairTemplateRegistry()
    r.load(seed_path=seed_file, outcomes_path=Path("/does/not/exist"))

    entry = r.lookup("pattern_fragmentation", "normalize_pattern", "production")
    assert entry is not None
    assert entry.improving_count == 4


def test_lookup_missing_returns_none(seed_file: Path):
    r = RepairTemplateRegistry()
    r.load(seed_path=seed_file, outcomes_path=Path("/does/not/exist"))

    assert r.lookup("nonexistent_signal", "some_edit", "production") is None


def test_lookup_wildcard_fallback(tmp_path: Path):
    """An entry with context_class='*' should be returned as fallback."""
    data = {
        "entries": [
            {
                "signal": "guard_clause_deficit",
                "edit_kind": "add_guard_clause",
                "context_class": "*",
                "improving_count": 3,
                "stable_count": 0,
                "regressing_count": 0,
                "regression_patterns": [],
                "evidence_sources": [],
                "last_updated": "",
            }
        ]
    }
    seed = tmp_path / "seed.json"
    seed.write_text(json.dumps(data), encoding="utf-8")
    r = RepairTemplateRegistry()
    r.load(seed_path=seed, outcomes_path=Path("/does/not/exist"))

    entry = r.lookup("guard_clause_deficit", "add_guard_clause", "production")
    assert entry is not None
    assert entry.improving_count == 3


# ---------------------------------------------------------------------------
# Confidence
# ---------------------------------------------------------------------------


def test_confidence_none_below_threshold():
    r = RepairTemplateRegistry()
    entry = RepairTemplateEntry(
        signal="s", edit_kind="e", context_class="production",
        improving_count=2, regressing_count=0,
    )
    # 2 < MIN_OUTCOMES_FOR_CONFIDENCE → None
    assert r.confidence(entry) is None


def test_confidence_none_at_threshold_minus_one():
    r = RepairTemplateRegistry()
    entry = RepairTemplateEntry(
        signal="s", edit_kind="e", context_class="production",
        improving_count=MIN_OUTCOMES_FOR_CONFIDENCE - 1,
        regressing_count=0,
    )
    assert r.confidence(entry) is None


def test_confidence_returns_value_at_threshold(seed_file: Path):
    r = RepairTemplateRegistry()
    r.load(seed_path=seed_file, outcomes_path=Path("/does/not/exist"))
    entry = r.lookup("mutant_duplicate", "merge_function_body", "production")
    assert entry is not None
    conf = r.confidence(entry)
    assert conf is not None
    # 5 improving, 1 regressing → 5/6 ≈ 0.833
    assert abs(conf - round(5 / 6, 3)) < 1e-9



def test_confidence_all_improving():
    r = RepairTemplateRegistry()
    entry = RepairTemplateEntry(
        signal="s", edit_kind="e", context_class="production",
        improving_count=5, regressing_count=0,
    )
    conf = r.confidence(entry)
    # total = 5 >= 3 → not None
    assert conf == 1.0


def test_confidence_all_regressing():
    r = RepairTemplateRegistry()
    entry = RepairTemplateEntry(
        signal="s", edit_kind="e", context_class="production",
        improving_count=0, regressing_count=3,
    )
    conf = r.confidence(entry)
    assert conf == 0.0


def test_confidence_50_50():
    r = RepairTemplateRegistry()
    entry = RepairTemplateEntry(
        signal="s", edit_kind="e", context_class="production",
        improving_count=3, regressing_count=3,
    )
    conf = r.confidence(entry)
    assert conf == 0.5


def test_confidence_stable_count_not_used():
    """stable_count must not affect the confidence denominator."""
    r = RepairTemplateRegistry()
    # 3 improving, 0 regressing, 100 stable — stable must be ignored
    entry = RepairTemplateEntry(
        signal="s", edit_kind="e", context_class="production",
        improving_count=3, regressing_count=0, stable_count=100,
    )
    conf = r.confidence(entry)
    # total (improving+regressing) = 3 → exactly threshold → not None
    assert conf == 1.0


# ---------------------------------------------------------------------------
# record_outcome
# ---------------------------------------------------------------------------


def test_record_outcome_improving_appends_to_file(tmp_path: Path, seed_file: Path):
    outcomes = tmp_path / "outcomes.jsonl"
    r = RepairTemplateRegistry()
    r.load(seed_path=seed_file, outcomes_path=outcomes)

    r.record_outcome(
        signal="pattern_fragmentation",
        edit_kind="normalize_pattern",
        context_class="production",
        direction="improving",
        score_delta=-0.03,
        outcomes_path=outcomes,
    )

    assert outcomes.exists()
    line = outcomes.read_text(encoding="utf-8").strip()
    rec = json.loads(line)
    assert rec["signal"] == "pattern_fragmentation"
    assert rec["edit_kind"] == "normalize_pattern"
    assert rec["direction"] == "improving"


def test_record_outcome_regressing_appends(tmp_path: Path, seed_file: Path):
    outcomes = tmp_path / "outcomes.jsonl"
    r = RepairTemplateRegistry()
    r.load(seed_path=seed_file, outcomes_path=outcomes)

    r.record_outcome(
        signal="mutant_duplicate",
        edit_kind="rename_symbol",
        context_class="production",
        direction="regressing",
        score_delta=0.05,
        outcomes_path=outcomes,
    )

    line = outcomes.read_text(encoding="utf-8").strip()
    rec = json.loads(line)
    assert rec["direction"] == "regressing"


def test_record_outcome_stable_not_recorded(tmp_path: Path, seed_file: Path):
    outcomes = tmp_path / "outcomes.jsonl"
    r = RepairTemplateRegistry()
    r.load(seed_path=seed_file, outcomes_path=outcomes)

    r.record_outcome(
        signal="pattern_fragmentation",
        edit_kind="normalize_pattern",
        context_class="production",
        direction="stable",
        score_delta=0.0,
        outcomes_path=outcomes,
    )

    # File must NOT be created (stable is silently ignored)
    assert not outcomes.exists()


def test_record_outcome_updates_in_memory(tmp_path: Path, seed_file: Path):
    outcomes = tmp_path / "outcomes.jsonl"
    r = RepairTemplateRegistry()
    r.load(seed_path=seed_file, outcomes_path=outcomes)

    # Seed has pattern_fragmentation/normalize_pattern with improving_count=4
    entry_before = r.lookup("pattern_fragmentation", "normalize_pattern", "production")
    assert entry_before is not None
    count_before = entry_before.improving_count

    r.record_outcome(
        signal="pattern_fragmentation",
        edit_kind="normalize_pattern",
        context_class="production",
        direction="improving",
        outcomes_path=outcomes,
    )

    entry_after = r.lookup("pattern_fragmentation", "normalize_pattern", "production")
    assert entry_after is not None
    assert entry_after.improving_count == count_before + 1


def test_record_outcome_creates_new_entry_for_unknown(tmp_path: Path, seed_file: Path):
    outcomes = tmp_path / "outcomes.jsonl"
    r = RepairTemplateRegistry()
    r.load(seed_path=seed_file, outcomes_path=outcomes)

    r.record_outcome(
        signal="brand_new_signal",
        edit_kind="some_edit",
        context_class="production",
        direction="improving",
        outcomes_path=outcomes,
    )

    entry = r.lookup("brand_new_signal", "some_edit", "production")
    assert entry is not None
    assert entry.improving_count == 1


def test_record_outcome_multiple_appends(tmp_path: Path, seed_file: Path):
    outcomes = tmp_path / "outcomes.jsonl"
    r = RepairTemplateRegistry()
    r.load(seed_path=seed_file, outcomes_path=outcomes)

    for _ in range(3):
        r.record_outcome(
            signal="pattern_fragmentation",
            edit_kind="normalize_pattern",
            context_class="production",
            direction="improving",
            outcomes_path=outcomes,
        )

    lines = [l for l in outcomes.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 3


# ---------------------------------------------------------------------------
# Load outcomes from file
# ---------------------------------------------------------------------------


def test_load_outcomes_merges_counts(seed_file: Path, tmp_path: Path):
    """Outcomes file should accumulate on top of seed counts."""
    outcomes = tmp_path / "outcomes.jsonl"
    # Write 2 improving outcomes for PFS
    records = [
        json.dumps({"signal": "pattern_fragmentation", "edit_kind": "normalize_pattern",
                    "context_class": "production", "direction": "improving", "score_delta": -0.01})
    ] * 2
    outcomes.write_text("\n".join(records) + "\n", encoding="utf-8")

    r = RepairTemplateRegistry()
    r.load(seed_path=seed_file, outcomes_path=outcomes)

    entry = r.lookup("pattern_fragmentation", "normalize_pattern", "production")
    assert entry is not None
    # Seed: 4 improving. Plus 2 from outcomes = 6
    assert entry.improving_count == 6


def test_load_outcomes_skips_invalid_lines(seed_file: Path, tmp_path: Path):
    """Malformed lines in outcomes.jsonl must not raise; valid lines still apply."""
    outcomes = tmp_path / "outcomes.jsonl"
    outcomes.write_text(
        '{"signal": "pattern_fragmentation", "edit_kind": "normalize_pattern", '
        '"context_class": "production", "direction": "improving"}\n'
        "NOT VALID JSON\n"
        '{"signal": "pattern_fragmentation", "edit_kind": "normalize_pattern", '
        '"context_class": "production", "direction": "improving"}\n',
        encoding="utf-8",
    )

    r = RepairTemplateRegistry()
    r.load(seed_path=seed_file, outcomes_path=outcomes)

    # Seed=4, valid outcomes=2 → 6
    entry = r.lookup("pattern_fragmentation", "normalize_pattern", "production")
    assert entry is not None
    assert entry.improving_count == 6


# ---------------------------------------------------------------------------
# rebuild_seed
# ---------------------------------------------------------------------------


def test_rebuild_seed_aggregates_correctly(seed_file: Path, tmp_path: Path):
    outcomes = tmp_path / "outcomes.jsonl"
    r = RepairTemplateRegistry()
    r.load(seed_path=seed_file, outcomes_path=outcomes)

    # Record new improving outcome
    r.record_outcome(
        signal="brand_new_signal",
        edit_kind="extract_module",
        context_class="production",
        direction="improving",
        outcomes_path=outcomes,
    )

    new_seed = tmp_path / "new_seed.json"
    # Pass both paths so rebuild_seed re-loads from the same sources
    r.rebuild_seed(seed_path=new_seed, outcomes_path=outcomes)

    data = json.loads(new_seed.read_text(encoding="utf-8"))
    keys = {f"{e['signal']}:{e['edit_kind']}:{e['context_class']}" for e in data["entries"]}
    assert "brand_new_signal:extract_module:production" in keys


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------


def test_get_registry_returns_singleton(seed_file: Path):
    r1 = get_registry()
    r2 = get_registry()
    assert r1 is r2


def test_reset_registry_clears_singleton():
    r1 = get_registry()
    reset_registry()
    r2 = get_registry()
    # Must be a different object after reset
    assert r1 is not r2


# ---------------------------------------------------------------------------
# AgentTask enrichment (integration-style)
# ---------------------------------------------------------------------------


def test_agent_task_template_confidence_none_by_default():
    """AgentTask.template_confidence defaults to None."""
    from drift.models import AgentTask, Severity
    task = AgentTask(
        id="t1",
        signal_type="mutant_duplicate",
        severity=Severity.HIGH,
        priority=1,
        title="Fix duplicate",
        description="",
        action="",
        file_path="foo.py",
    )
    assert task.template_confidence is None
    assert task.regression_guidance == []


def test_agent_task_regression_guidance_field():
    """AgentTask.regression_guidance stores RegressionPattern objects."""
    from drift.models import AgentTask, Severity
    rp = RegressionPattern(
        edit_kind="rename_symbol",
        context_feature="nothing_else_changed",
        reason_code=RegressionReasonCode.COSMETIC_ONLY,
    )
    task = AgentTask(
        id="t1",
        signal_type="mutant_duplicate",
        severity=Severity.HIGH,
        priority=1,
        title="Fix duplicate",
        description="",
        action="",
        file_path="foo.py",
        template_confidence=0.833,
        regression_guidance=[rp],
    )
    assert task.template_confidence == pytest.approx(0.833)
    assert len(task.regression_guidance) == 1
    assert task.regression_guidance[0].reason_code == RegressionReasonCode.COSMETIC_ONLY
