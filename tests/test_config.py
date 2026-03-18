"""Tests for configuration loading."""

from pathlib import Path

from drift.config import DriftConfig


def test_default_config():
    config = DriftConfig()
    assert config.fail_on == "high"
    assert config.weights.pattern_fragmentation == 0.20
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
    assert abs(total - 1.0) < 0.01
