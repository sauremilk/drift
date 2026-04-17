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
    assert "**/*.pyi" in config.include
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


# ---------------------------------------------------------------------------
# ThresholdsConfig instantiation & defaults
# ---------------------------------------------------------------------------


def test_thresholds_defaults():
    from drift.config import ThresholdsConfig

    t = ThresholdsConfig()
    assert t.min_function_loc >= 1
    assert t.min_complexity >= 1
    assert 0.0 < t.similarity_threshold <= 1.0
    assert t.bem_min_handlers >= 1
    assert isinstance(t.bat_density_threshold, float)
    assert isinstance(t.dca_ignore_re_exports, bool)
    assert t.max_discovery_files > 0
    assert isinstance(t.maz_public_endpoint_allowlist, list)
    assert len(t.maz_public_endpoint_allowlist) > 0
    assert isinstance(t.maz_dev_tool_paths, list)
    assert "debug" in t.maz_dev_tool_paths


# ---------------------------------------------------------------------------
# SignalWeights.as_dict()
# ---------------------------------------------------------------------------


def test_signal_weights_as_dict():
    from drift.config import SignalWeights

    w = SignalWeights()
    d = w.as_dict()
    assert isinstance(d, dict)
    assert "pattern_fragmentation" in d
    assert d["pattern_fragmentation"] == 0.16


# ---------------------------------------------------------------------------
# PathOverride defaults
# ---------------------------------------------------------------------------


def test_path_override_defaults():
    from drift.config import PathOverride

    po = PathOverride()
    assert po.exclude_signals == []
    assert po.weights is None
    assert po.severity_gate is None


# ---------------------------------------------------------------------------
# DriftConfig._find_config_file — TOML fallbacks
# ---------------------------------------------------------------------------


def test_find_config_toml(tmp_path: Path):
    (tmp_path / "drift.toml").write_text(
        "[weights]\npattern_fragmentation = 0.3\n", encoding="utf-8"
    )
    found = DriftConfig._find_config_file(tmp_path)
    assert found is not None
    assert found.name == "drift.toml"


def test_find_config_pyproject(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text('[tool.drift]\nfail_on = "low"\n', encoding="utf-8")
    found = DriftConfig._find_config_file(tmp_path)
    assert found is not None
    assert found.name == "pyproject.toml"


def test_find_config_returns_none(tmp_path: Path):
    found = DriftConfig._find_config_file(tmp_path)
    assert found is None


# ---------------------------------------------------------------------------
# DriftConfig.load — TOML loading
# ---------------------------------------------------------------------------


def test_load_drift_toml(tmp_path: Path):
    (tmp_path / "drift.toml").write_text(
        "[weights]\npattern_fragmentation = 0.30\n\n[thresholds]\n",
        encoding="utf-8",
    )
    config = DriftConfig.load(tmp_path)
    assert config.weights.pattern_fragmentation == 0.30


def test_load_pyproject_toml_with_tool_drift(tmp_path: Path):
    content = '[tool.drift]\nfail_on = "low"\n'
    (tmp_path / "pyproject.toml").write_text(content, encoding="utf-8")
    config = DriftConfig.load(tmp_path)
    assert config.fail_on == "low"


def test_load_pyproject_toml_without_drift_section(tmp_path: Path):
    content = '[tool.other]\nfoo = "bar"\n'
    (tmp_path / "pyproject.toml").write_text(content, encoding="utf-8")
    config = DriftConfig.load(tmp_path)
    assert config.fail_on == "high"  # defaults


def test_load_toml_validation_error(tmp_path: Path):
    content = '[weights]\npattern_fragmentation = "not_a_number"\n'
    (tmp_path / "drift.toml").write_text(content, encoding="utf-8")
    with pytest.raises(DriftConfigError, match="DRIFT-1001"):
        DriftConfig.load(tmp_path)


# ---------------------------------------------------------------------------
# DriftConfig.load — YAML parse error
# ---------------------------------------------------------------------------


def test_load_yaml_parse_error(tmp_path: Path):
    (tmp_path / "drift.yaml").write_text("fail_on: [\n", encoding="utf-8")
    with pytest.raises(DriftConfigError, match="DRIFT-1002"):
        DriftConfig.load(tmp_path)


# ---------------------------------------------------------------------------
# _apply_extends — preset merging
# ---------------------------------------------------------------------------


def test_apply_extends_with_valid_preset():
    data = {"extends": "default", "fail_on": "critical"}
    result = DriftConfig._apply_extends(data)
    assert result["fail_on"] == "critical"
    assert "weights" in result
    assert result["extends"] == "default"


def test_apply_extends_without_extends():
    data = {"fail_on": "low"}
    result = DriftConfig._apply_extends(data)
    assert result == data


def test_apply_extends_non_dict_raises():
    with pytest.raises(DriftConfigError, match="DRIFT-1001"):
        DriftConfig._apply_extends("not a dict")


def test_apply_extends_unknown_preset_raises():
    with pytest.raises(DriftConfigError, match="Unknown preset"):
        DriftConfig._apply_extends({"extends": "nonexistent_preset_xyz"})


def test_apply_extends_deep_merge():
    data = {
        "extends": "default",
        "weights": {"pattern_fragmentation": 0.99},
    }
    result = DriftConfig._apply_extends(data)
    assert result["weights"]["pattern_fragmentation"] == 0.99
    assert "architecture_violation" in result["weights"]


# ---------------------------------------------------------------------------
# build_config_json_schema
# ---------------------------------------------------------------------------


def test_build_config_json_schema():
    from drift.config import build_config_json_schema

    schema = build_config_json_schema()
    assert "$schema" in schema
    assert "properties" in schema


# ---------------------------------------------------------------------------
# resolve_signal_names & apply_signal_filter
# ---------------------------------------------------------------------------


def test_resolve_signal_names_abbreviations():
    from drift.config import resolve_signal_names

    result = resolve_signal_names("PFS,AVS")
    assert "pattern_fragmentation" in result
    assert "architecture_violation" in result


def test_resolve_signal_names_full_names():
    from drift.config import resolve_signal_names

    result = resolve_signal_names("pattern_fragmentation")
    assert result == ["pattern_fragmentation"]


def test_resolve_signal_names_unknown_raises():
    from drift.config import resolve_signal_names

    with pytest.raises(ValueError, match="Unknown signal"):
        resolve_signal_names("INVALID_SIGNAL_XYZ")


def test_apply_signal_filter_select():
    from drift.config import apply_signal_filter

    cfg = DriftConfig()
    apply_signal_filter(cfg, select="PFS,AVS", ignore=None)
    assert cfg.weights.pattern_fragmentation > 0.0
    assert cfg.weights.architecture_violation > 0.0
    assert cfg.weights.mutant_duplicate == 0.0
    assert cfg.weights.doc_impl_drift == 0.0


def test_apply_signal_filter_ignore():
    from drift.config import apply_signal_filter

    cfg = DriftConfig()
    apply_signal_filter(cfg, select=None, ignore="PFS")
    assert cfg.weights.pattern_fragmentation == 0.0
    assert cfg.weights.architecture_violation > 0.0


def test_apply_signal_filter_select_and_ignore():
    from drift.config import apply_signal_filter

    cfg = DriftConfig()
    apply_signal_filter(cfg, select="PFS,AVS", ignore="AVS")
    assert cfg.weights.pattern_fragmentation > 0.0
    assert cfg.weights.architecture_violation == 0.0


# ---------------------------------------------------------------------------
# Sub-config models
# ---------------------------------------------------------------------------


def test_calibration_config_defaults():
    from drift.config import CalibrationConfig

    c = CalibrationConfig()
    assert c.fn_boost_factor == 0.1


def test_attribution_config_defaults():
    from drift.config import AttributionConfig

    a = AttributionConfig()
    assert a.cache_enabled is True
    assert a.max_parallel_workers == 4


def test_plugin_config_defaults():
    from drift.config import PluginConfig

    p = PluginConfig()
    assert p.disabled == []


def test_brief_config_defaults():
    from drift.config import BriefConfig

    b = BriefConfig()
    assert b.scope_aliases == {}


def test_agent_objective_defaults():
    from drift.config import AgentObjective

    a = AgentObjective()
    assert a.goal == ""


def test_agent_effectiveness_thresholds_defaults():
    from drift.config import AgentEffectivenessThresholds

    t = AgentEffectivenessThresholds()
    assert t.low_effect_resolved_per_changed_file == 0.25
    assert t.high_churn_min_changed_files == 5


# ---------------------------------------------------------------------------
# _default_includes with mocked tree-sitter availability
# ---------------------------------------------------------------------------


def test_default_includes_without_tree_sitter(monkeypatch):
    import importlib.util

    from drift import config as config_mod

    original_find_spec = importlib.util.find_spec

    def mock_find_spec(name, *args, **kwargs):
        if name == "tree_sitter":
            return None
        return original_find_spec(name, *args, **kwargs)

    monkeypatch.setattr(importlib.util, "find_spec", mock_find_spec)
    patterns = config_mod._default_includes()
    assert "**/*.py" in patterns
    assert "**/*.ts" not in patterns


def test_load_yaml_with_extends(tmp_path: Path):
    yaml_content = """\
extends: default
fail_on: critical
"""
    (tmp_path / "drift.yaml").write_text(yaml_content, encoding="utf-8")
    config = DriftConfig.load(tmp_path)
    assert config.fail_on == "critical"
    assert config.extends == "default"


def test_load_yaml_validation_error_with_context(tmp_path: Path):
    yaml_content = """\
fail_on: critical
thresholds:
  bad_field: not_valid
"""
    (tmp_path / "drift.yaml").write_text(yaml_content, encoding="utf-8")
    with pytest.raises(DriftConfigError, match="DRIFT-1001"):
        DriftConfig.load(tmp_path)


def test_config_with_agent_and_effectiveness_thresholds(tmp_path: Path):
    yaml_content = """\
agent:
  goal: "Migrate payment module"
  effectiveness_thresholds:
    low_effect_resolved_per_changed_file: 0.5
"""
    (tmp_path / "drift.yaml").write_text(yaml_content, encoding="utf-8")
    config = DriftConfig.load(tmp_path)
    assert config.agent is not None
    assert config.agent.goal == "Migrate payment module"
    assert config.agent.effectiveness_thresholds.low_effect_resolved_per_changed_file == 0.5


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
