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
    assert "**/.conda/**" in config.exclude
    assert "**/.env/**" in config.exclude
    assert "**/.nox/**" in config.exclude
    assert "**/.tmp_*venv*/**" in config.exclude
    assert "**/site-packages/**" in config.exclude
    assert "**/.pixi/**" in config.exclude
    assert "**/tests/**" in config.exclude
    assert "**/scripts/**" in config.exclude


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


def test_load_yaml_lazy_import_rules(tmp_path: Path):
    yaml_content = """\
policies:
  lazy_import_rules:
    - name: heavy_runtime_libs
      from: src/perception/*.py
      modules:
        - onnxruntime
        - torch
      module_level_only: true
"""
    (tmp_path / "drift.yaml").write_text(yaml_content)
    config = DriftConfig.load(tmp_path)

    assert len(config.policies.lazy_import_rules) == 1
    rule = config.policies.lazy_import_rules[0]
    assert rule.from_pattern == "src/perception/*.py"
    assert rule.modules == ["onnxruntime", "torch"]
    assert rule.module_level_only is True


def test_weight_sum_with_report_only_signals_remains_reasonable():
    w = DriftConfig().weights
    total = sum(w.as_dict().values())
    # Some signals can be intentionally report-only (weight=0.0), so the
    # default sum need not be exactly 1.0 but should stay in a stable range.
    assert 0.85 <= total <= 1.05


def test_load_yaml_unknown_top_level_key_raises(tmp_path: Path):
    (tmp_path / "drift.yaml").write_text("unknown_key: true\n", encoding="utf-8")

    with pytest.raises(DriftConfigError, match="DRIFT-1001"):
        DriftConfig.load(tmp_path)


def test_load_yaml_unknown_nested_key_raises(tmp_path: Path):
    # Plugin-weights (unknown keys in 'weights') are now accepted by the Plugin API.
    # This test verifies that unknown keys in other strict sections still raise errors.
    yaml_content = """\
thresholds:
  unknown_threshold_key: 42
"""
    (tmp_path / "drift.yaml").write_text(yaml_content, encoding="utf-8")

    with pytest.raises(DriftConfigError, match="DRIFT-1001"):
        DriftConfig.load(tmp_path)


def test_toml_parse_error_message_is_not_yaml_specific(tmp_path: Path):
    (tmp_path / "drift.toml").write_text(
        "[weights\npattern_fragmentation = 0.30\n",
        encoding="utf-8",
    )

    with pytest.raises(DriftConfigError) as exc_info:
        DriftConfig.load(tmp_path)

    message = str(exc_info.value)
    assert "DRIFT-1002" in message
    assert "Parse error:" in message
    assert "YAML" not in message
