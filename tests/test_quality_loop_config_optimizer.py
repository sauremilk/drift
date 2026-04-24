"""Tests for the MCTS config-space optimizer components.

Covers:
- ConfigAction: apply() returns new immutable DriftConfig
- ConfigMCTSSearch: runs without error, result fields present
- ConfigSearchResult.to_dict(): expected keys
- ALL_TRANSFORMS: non-empty, all names unique
"""

from __future__ import annotations

import pytest
from scripts.quality_loop.config_mcts import (
    ConfigMCTSSearch,
    ConfigSearchResult,
    _ArmStats,
)
from scripts.quality_loop.config_transforms import ALL_TRANSFORMS

from drift.config import DriftConfig

# ---------------------------------------------------------------------------
# ConfigAction
# ---------------------------------------------------------------------------


class TestConfigAction:
    def test_apply_returns_new_object(self):
        action = ALL_TRANSFORMS[0]
        config = DriftConfig()
        result = action.apply(config)
        assert result is not config

    def test_apply_does_not_mutate_original(self):
        action = ALL_TRANSFORMS[0]
        config = DriftConfig()
        original_thresh = config.thresholds.model_dump()
        action.apply(config)
        assert config.thresholds.model_dump() == original_thresh

    def test_all_transforms_have_unique_names(self):
        names = [t.name for t in ALL_TRANSFORMS]
        assert len(names) == len(set(names))

    def test_all_transforms_non_empty(self):
        assert len(ALL_TRANSFORMS) > 0


# ---------------------------------------------------------------------------
# _ArmStats / UCB1
# ---------------------------------------------------------------------------


class TestArmStats:
    def test_ucb1_unvisited_returns_inf(self):
        arm = _ArmStats()
        assert arm.ucb1(total_visits=1) == float("inf")

    def test_ucb1_after_update(self):
        arm = _ArmStats()
        arm.update(0.5)
        val = arm.ucb1(total_visits=1)
        assert isinstance(val, float)
        assert val > 0

    def test_update_increments_visits(self):
        arm = _ArmStats()
        arm.update(0.3)
        arm.update(0.1)
        assert arm.visits == 2
        assert abs(arm.total_reward - 0.4) < 1e-9


# ---------------------------------------------------------------------------
# ConfigSearchResult
# ---------------------------------------------------------------------------


class TestConfigSearchResult:
    def test_to_dict_has_required_keys(self):
        result = ConfigSearchResult(
            best_config=DriftConfig(),
            best_score=0.9,
            baseline_score=0.8,
            iterations=5,
            transform_path=["thresh_sim_up"],
        )
        d = result.to_dict()
        for key in ("best_score", "baseline_score", "improvement", "iterations",
                    "transform_path", "best_config_thresholds", "best_config_weights"):
            assert key in d, f"Missing key: {key}"

    def test_improvement_computed_correctly(self):
        result = ConfigSearchResult(
            best_config=DriftConfig(),
            best_score=0.95,
            baseline_score=0.80,
            iterations=10,
        )
        d = result.to_dict()
        assert abs(d["improvement"] - 0.15) < 0.01


# ---------------------------------------------------------------------------
# ConfigMCTSSearch — smoke test with stub metric
# ---------------------------------------------------------------------------


class _ConstMetric:
    """Always returns a fixed score regardless of config."""

    def __init__(self, score: float = 0.75) -> None:
        self._score = score

    def measure(self, config: DriftConfig) -> float:  # noqa: ARG002
        return self._score


class TestConfigMCTSSearch:
    def test_run_returns_result(self):
        metric = _ConstMetric(0.75)
        search = ConfigMCTSSearch(metric=metric, budget=5, seed=42)
        result = search.run()
        assert isinstance(result, ConfigSearchResult)
        assert result.iterations == 5

    def test_no_improvement_when_all_same_score(self):
        metric = _ConstMetric(0.75)
        search = ConfigMCTSSearch(metric=metric, budget=5, seed=42)
        result = search.run()
        # All arms return same score → reward = 0 → no config promotion
        assert result.best_score == pytest.approx(0.75)
        assert result.baseline_score == pytest.approx(0.75)

    def test_improvement_detected_with_varying_metric(self):
        """Metric returns higher score on second call (simulates improvement)."""
        scores = iter([0.70, 0.80, 0.70, 0.70, 0.70, 0.70])

        class _VaryingMetric:
            def measure(self, config: DriftConfig) -> float:  # noqa: ARG002
                return next(scores, 0.70)

        search = ConfigMCTSSearch(metric=_VaryingMetric(), budget=5, seed=0)
        result = search.run()
        assert result.best_score >= result.baseline_score

    def test_custom_transforms_subset(self):
        subset = ALL_TRANSFORMS[:3]
        metric = _ConstMetric(0.6)
        search = ConfigMCTSSearch(metric=metric, budget=3, transforms=subset, seed=1)
        result = search.run()
        assert isinstance(result, ConfigSearchResult)
