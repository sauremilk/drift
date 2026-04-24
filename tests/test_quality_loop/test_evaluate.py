"""Tests for scripts.quality_loop.evaluate — gate logic and aggregation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts.quality_loop.evaluate import (
    SeedResult,
    aggregate,
    compute_gate,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_seed_result(
    seed: int = 1,
    improvement: float = 0.02,
    baseline_ruff: int = 10,
    baseline_mypy: int = 5,
    baseline_drift: float = 0.30,
    final_ruff: int | None = None,
    final_mypy: int | None = None,
    final_drift: float | None = None,
    error: str | None = None,
) -> SeedResult:
    return SeedResult(
        seed=seed,
        improvement=improvement,
        baseline_ruff=baseline_ruff,
        baseline_mypy=baseline_mypy,
        baseline_drift=baseline_drift,
        final_ruff=final_ruff if final_ruff is not None else max(0, baseline_ruff - 1),
        final_mypy=final_mypy if final_mypy is not None else baseline_mypy,
        final_drift=final_drift if final_drift is not None else baseline_drift,
        applied=False,
        error=error,
    )


# ---------------------------------------------------------------------------
# compute_gate tests
# ---------------------------------------------------------------------------


class TestComputeGate:
    def test_all_pass(self) -> None:
        results = [_make_seed_result(seed=i, improvement=0.02) for i in range(5)]
        gate_pass, reasons = compute_gate(results)
        assert gate_pass is True
        assert reasons == []

    def test_median_below_threshold(self) -> None:
        results = [
            _make_seed_result(seed=1, improvement=0.005),
            _make_seed_result(seed=2, improvement=0.005),
            _make_seed_result(seed=3, improvement=0.005),
        ]
        gate_pass, reasons = compute_gate(results, min_median=0.01)
        assert gate_pass is False
        assert any("median_improvement" in r for r in reasons)

    def test_positive_seed_rate_below_threshold(self) -> None:
        results = [
            _make_seed_result(seed=1, improvement=0.02),
            _make_seed_result(seed=2, improvement=-0.01),
            _make_seed_result(seed=3, improvement=-0.01),
            _make_seed_result(seed=4, improvement=-0.01),
        ]
        gate_pass, reasons = compute_gate(results, min_positive_rate=0.70)
        assert gate_pass is False
        assert any("positive_seed_rate" in r for r in reasons)

    def test_ruff_regression_blocks_gate(self) -> None:
        results = [
            _make_seed_result(
                seed=1,
                improvement=0.02,
                baseline_ruff=10,
                final_ruff=12,  # regression!
            )
        ]
        gate_pass, reasons = compute_gate(results)
        assert gate_pass is False
        assert any("ruff_regressions" in r for r in reasons)

    def test_mypy_regression_blocks_gate(self) -> None:
        results = [
            _make_seed_result(
                seed=1,
                improvement=0.02,
                baseline_mypy=5,
                final_mypy=7,  # regression!
            )
        ]
        gate_pass, reasons = compute_gate(results)
        assert gate_pass is False
        assert any("mypy_regressions" in r for r in reasons)

    def test_drift_delta_above_tolerance(self) -> None:
        results = [
            _make_seed_result(
                seed=1,
                improvement=0.02,
                baseline_drift=0.30,
                final_drift=0.31,  # delta=0.01 > tolerance=0.005
            )
        ]
        gate_pass, reasons = compute_gate(results, drift_tolerance=0.005)
        assert gate_pass is False
        assert any("max_drift_delta" in r for r in reasons)

    def test_drift_delta_within_tolerance(self) -> None:
        results = [
            _make_seed_result(
                seed=1,
                improvement=0.02,
                baseline_drift=0.30,
                final_drift=0.3035,  # delta=0.0035 <= tolerance=0.005
            )
        ]
        gate_pass, reasons = compute_gate(results, drift_tolerance=0.005)
        assert gate_pass is True

    def test_all_seeds_errored(self) -> None:
        results = [
            SeedResult.from_error(seed=1, error="crash"),
            SeedResult.from_error(seed=2, error="timeout"),
        ]
        gate_pass, reasons = compute_gate(results)
        assert gate_pass is False
        assert any("no_valid_seeds" in r for r in reasons)

    def test_mixed_errors_partial_valid(self) -> None:
        results = [
            _make_seed_result(seed=1, improvement=0.02),
            _make_seed_result(seed=2, improvement=0.03),
            SeedResult.from_error(seed=3, error="crash"),
        ]
        # 2 valid seeds: both positive → rate=1.0, median=0.025
        gate_pass, reasons = compute_gate(results, min_median=0.01, min_positive_rate=0.70)
        assert gate_pass is True

    def test_multiple_failures_all_reported(self) -> None:
        results = [
            _make_seed_result(
                seed=1,
                improvement=0.005,  # below median threshold
                baseline_ruff=5,
                final_ruff=8,  # ruff regression
            )
        ]
        gate_pass, reasons = compute_gate(results, min_median=0.01)
        assert gate_pass is False
        assert len(reasons) >= 2


# ---------------------------------------------------------------------------
# aggregate tests
# ---------------------------------------------------------------------------


class TestAggregate:
    def test_basic_aggregation(self) -> None:
        results = [
            _make_seed_result(seed=1, improvement=0.01),
            _make_seed_result(seed=2, improvement=0.02),
            _make_seed_result(seed=3, improvement=0.03),
        ]
        ev = aggregate(
            results,
            src="src/drift",
            mode="mcts",
            seeds=[1, 2, 3],
        )
        assert ev.median_improvement == pytest.approx(0.02, abs=1e-6)
        assert ev.mean_improvement == pytest.approx(0.02, abs=1e-6)
        assert ev.positive_seed_rate == pytest.approx(1.0)
        assert ev.ruff_regressions == 0
        assert ev.mypy_regressions == 0

    def test_positive_seed_rate_calculation(self) -> None:
        results = [
            _make_seed_result(seed=1, improvement=0.02),
            _make_seed_result(seed=2, improvement=0.015),
            _make_seed_result(seed=3, improvement=-0.001),
            _make_seed_result(seed=4, improvement=0.01),
            _make_seed_result(seed=5, improvement=-0.005),
        ]
        ev = aggregate(results, src="src/drift", mode="mcts", seeds=[1, 2, 3, 4, 5])
        assert ev.positive_seed_rate == pytest.approx(3 / 5)

    def test_gate_pass_true_in_result(self) -> None:
        results = [_make_seed_result(seed=i, improvement=0.02) for i in range(5)]
        ev = aggregate(results, src="src/drift", mode="mcts", seeds=list(range(5)))
        assert ev.gate_pass is True
        assert ev.gate_failure_reasons == []

    def test_gate_fail_in_result(self) -> None:
        results = [_make_seed_result(seed=i, improvement=0.001) for i in range(5)]
        ev = aggregate(
            results,
            min_median=0.01,
            src="src/drift",
            mode="mcts",
            seeds=list(range(5)),
        )
        assert ev.gate_pass is False
        assert len(ev.gate_failure_reasons) >= 1

    def test_error_seeds_tracked(self) -> None:
        results = [
            _make_seed_result(seed=1, improvement=0.02),
            SeedResult.from_error(seed=2, error="crash"),
        ]
        ev = aggregate(results, src="src/drift", mode="mcts", seeds=[1, 2])
        assert 2 in ev.error_seeds

    def test_thresholds_stored_in_result(self) -> None:
        results = [_make_seed_result(seed=1)]
        ev = aggregate(
            results,
            min_median=0.02,
            min_positive_rate=0.80,
            drift_tolerance=0.003,
            src="src/drift",
            mode="mcts",
            seeds=[1],
        )
        assert ev.min_median == 0.02
        assert ev.min_positive_rate == 0.80
        assert ev.drift_tolerance == 0.003


# ---------------------------------------------------------------------------
# SeedResult contract tests
# ---------------------------------------------------------------------------


class TestSeedResult:
    def test_from_result_dict(self) -> None:
        d = {
            "improvement": 0.015,
            "baseline_ruff": 10,
            "baseline_mypy": 4,
            "baseline_drift": 0.35,
            "final_ruff": 9,
            "final_mypy": 4,
            "final_drift": 0.34,
            "applied": False,
        }
        sr = SeedResult.from_result_dict(seed=42, d=d)
        assert sr.seed == 42
        assert sr.improvement == pytest.approx(0.015)
        assert sr.baseline_ruff == 10
        assert sr.final_ruff == 9
        assert not sr.ruff_regression
        assert not sr.mypy_regression
        assert sr.drift_delta == pytest.approx(-0.01, abs=1e-6)

    def test_from_error(self) -> None:
        sr = SeedResult.from_error(seed=99, error="timeout")
        assert sr.seed == 99
        assert sr.error == "timeout"
        assert sr.improvement == 0.0

    def test_ruff_regression_detected(self) -> None:
        sr = SeedResult.from_result_dict(
            seed=1,
            d={
                "improvement": 0.01,
                "baseline_ruff": 5,
                "final_ruff": 8,
                "baseline_mypy": 2,
                "final_mypy": 2,
                "baseline_drift": 0.3,
                "final_drift": 0.3,
                "applied": False,
            },
        )
        assert sr.ruff_regression is True

    def test_mypy_regression_detected(self) -> None:
        sr = SeedResult.from_result_dict(
            seed=1,
            d={
                "improvement": 0.01,
                "baseline_ruff": 5,
                "final_ruff": 5,
                "baseline_mypy": 2,
                "final_mypy": 4,
                "baseline_drift": 0.3,
                "final_drift": 0.3,
                "applied": False,
            },
        )
        assert sr.mypy_regression is True


# ---------------------------------------------------------------------------
# JSON contract test
# ---------------------------------------------------------------------------


class TestJsonContract:
    REQUIRED_FIELDS = {
        "src",
        "mode",
        "seeds",
        "seed_details",
        "median_improvement",
        "mean_improvement",
        "positive_seed_rate",
        "ruff_regressions",
        "mypy_regressions",
        "max_drift_delta",
        "gate_pass",
        "gate_failure_reasons",
        "min_median",
        "min_positive_rate",
        "drift_tolerance",
        "evaluated_at",
        "error_seeds",
    }

    def test_all_required_fields_present(self) -> None:
        results = [_make_seed_result(seed=1, improvement=0.02)]
        ev = aggregate(results, src="src/drift", mode="mcts", seeds=[1])
        d = ev.to_dict()
        missing = self.REQUIRED_FIELDS - d.keys()
        assert not missing, f"Missing fields in EvaluationResult.to_dict(): {missing}"

    def test_json_round_trip(self, tmp_path: Path) -> None:
        results = [_make_seed_result(seed=i, improvement=0.02) for i in range(3)]
        ev = aggregate(results, src="src/drift", mode="mcts", seeds=[0, 1, 2])
        out = tmp_path / "eval.json"
        out.write_text(json.dumps(ev.to_dict(), indent=2), encoding="utf-8")
        loaded = json.loads(out.read_text(encoding="utf-8"))
        assert loaded["gate_pass"] == ev.gate_pass
        assert len(loaded["seed_details"]) == 3

    def test_seed_detail_fields(self) -> None:
        results = [_make_seed_result(seed=7, improvement=0.02)]
        ev = aggregate(results, src="src/drift", mode="mcts", seeds=[7])
        d = ev.to_dict()
        sd = d["seed_details"][0]
        for f in ("seed", "improvement", "baseline_ruff", "baseline_mypy",
                  "baseline_drift", "final_ruff", "final_mypy", "final_drift",
                  "applied", "error"):
            assert f in sd, f"seed_details missing field: {f}"
