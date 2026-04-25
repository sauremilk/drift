from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    module_path = Path(__file__).resolve().parent.parent / "scripts" / "quality_scorecard.py"
    spec = importlib.util.spec_from_file_location("quality_scorecard", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_scorecard_contains_all_iso_dimensions() -> None:
    module = _load_module()

    scorecard = module.build_scorecard(module.REPO_ROOT)

    expected_dimensions = {
        "functional_suitability",
        "performance_efficiency",
        "usability",
        "reliability",
        "security",
        "compatibility",
        "maintainability",
        "portability",
    }

    dimensions = scorecard["dimensions"]
    assert set(dimensions) == expected_dimensions

    for name in expected_dimensions:
        entry = dimensions[name]
        assert 0.0 <= float(entry["score"]) <= 1.0
        assert isinstance(entry["confidence"], str)
        assert isinstance(entry["sources"], list)
        assert isinstance(entry["gaps"], list)


def test_build_scorecard_has_aggregate_scores() -> None:
    module = _load_module()

    scorecard = module.build_scorecard(module.REPO_ROOT)

    assert 0.0 <= float(scorecard["overall_score"]) <= 1.0
    assert 0.0 <= float(scorecard["coverage_ratio"]) <= 1.0