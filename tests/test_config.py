"""Tests for configuration loading."""

from pathlib import Path

import pytest

from drift.config import DriftConfig
from drift.errors import DriftConfigError


def test_default_config():
    config = DriftConfig()
    assert config.fail_on == "high"
    assert config.weights.pattern_fragmentation == 0.16
    assert config.weights.doc_impl_drift == 0.04
    assert config.auto_calibrate is True
    assert "**/*.py" in config.include
    assert "**/__pycache__/**" in config.exclude


def test_load_missing_file(tmp_path: Path):
    config = DriftConfig.load(tmp_path)
    assert config.fail_on == "high"


def test_load_yaml(tmp_path: Path):
    yaml_content = """\
fail_on: critical
weights:
  pattern_fragmentation: 0.30
  architecture_violation: 0.25
policies:
  max_pattern_variants:
    error_handling: 2
"""
    (tmp_path / "drift.yaml").write_text(yaml_content)
    config = DriftConfig.load(tmp_path)
    assert config.fail_on == "critical"
    assert config.weights.pattern_fragmentation == 0.30
    assert config.weights.architecture_violation == 0.25
    assert config.policies.max_pattern_variants == {"error_handling": 2}


def test_weight_sum_approximately_one():
    w = DriftConfig().weights
    total = sum(w.as_dict().values())
    assert abs(total - 1.0) < 0.02


def test_load_yaml_unknown_top_level_key_raises(tmp_path: Path):
    (tmp_path / "drift.yaml").write_text("unknown_key: true\n", encoding="utf-8")

    with pytest.raises(DriftConfigError, match="DRIFT-1001"):
        DriftConfig.load(tmp_path)


def test_load_yaml_unknown_nested_key_raises(tmp_path: Path):
    yaml_content = """\
weights:
  pattern_fragmentation: 0.30
  unknown_weight: 0.25
"""
    (tmp_path / "drift.yaml").write_text(yaml_content, encoding="utf-8")

    with pytest.raises(DriftConfigError, match="DRIFT-1001"):
        DriftConfig.load(tmp_path)
