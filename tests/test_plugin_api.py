"""Tests for the central signal metadata registry (drift.signal_registry)
and the plugin discovery module (drift.plugins).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from drift.config import DriftConfig, PluginConfig
from drift.signal_registry import (
    SignalMeta,
    _reset_registry,
    get_abbrev_map,
    get_all_meta,
    get_meta,
    get_signal_to_abbrev,
    get_signals_by_category,
    get_weight_defaults,
    register_signal_meta,
    resolve_abbrev,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_registry():
    """Reset plugin registrations after every test."""
    yield
    _reset_registry()


# ---------------------------------------------------------------------------
# signal_registry — core data tests
# ---------------------------------------------------------------------------


class TestSignalRegistryCore:
    def test_all_meta_returns_24_core_signals(self):
        meta = get_all_meta()
        assert len(meta) == 24

    def test_all_abbrevs_are_unique(self):
        abbrevs = [m.abbrev for m in get_all_meta()]
        assert len(abbrevs) == len(set(abbrevs)), "Duplicate abbreviations found"

    def test_all_signal_ids_are_unique(self):
        ids = [m.signal_id for m in get_all_meta()]
        assert len(ids) == len(set(ids)), "Duplicate signal IDs found"

    def test_get_abbrev_map_contains_known_entries(self):
        m = get_abbrev_map()
        assert m["PFS"] == "pattern_fragmentation"
        assert m["AVS"] == "architecture_violation"
        assert m["MDS"] == "mutant_duplicate"
        assert m["HSC"] == "hardcoded_secret"

    def test_get_abbrev_map_has_24_entries(self):
        assert len(get_abbrev_map()) == 24

    def test_get_signal_to_abbrev_reverses_abbrev_map(self):
        abbrev_map = get_abbrev_map()
        sig_to_abbrev = get_signal_to_abbrev()
        for abbrev, signal_id in abbrev_map.items():
            assert sig_to_abbrev[signal_id] == abbrev

    def test_get_weight_defaults_contains_known_weights(self):
        weights = get_weight_defaults()
        assert weights["pattern_fragmentation"] == pytest.approx(0.16)
        assert weights["temporal_volatility"] == pytest.approx(0.0)
        assert weights["hardcoded_secret"] == pytest.approx(0.0)

    def test_get_meta_known_signal(self):
        m = get_meta("pattern_fragmentation")
        assert m is not None
        assert m.abbrev == "PFS"
        assert m.category == "structural_risk"
        assert m.is_core is True

    def test_get_meta_unknown_signal_returns_none(self):
        assert get_meta("nonexistent_signal") is None

    def test_resolve_abbrev_case_insensitive(self):
        assert resolve_abbrev("pfs") == "pattern_fragmentation"
        assert resolve_abbrev("PFS") == "pattern_fragmentation"
        assert resolve_abbrev("Pfs") == "pattern_fragmentation"

    def test_resolve_abbrev_unknown_returns_none(self):
        assert resolve_abbrev("XYZ") is None

    def test_get_signals_by_category(self):
        security = get_signals_by_category("security")
        ids = {m.signal_id for m in security}
        assert "missing_authorization" in ids
        assert "insecure_default" in ids
        assert "hardcoded_secret" in ids

    def test_all_categories_are_known(self):
        known = {
            "structural_risk",
            "architecture_boundary",
            "style_hygiene",
            "security",
            "ai_quality",
        }
        for m in get_all_meta():
            assert m.category in known, f"{m.signal_id} has unknown category {m.category!r}"


# ---------------------------------------------------------------------------
# signal_registry — plugin registration tests
# ---------------------------------------------------------------------------


class TestPluginRegistration:
    def test_register_plugin_signal_meta(self):
        plugin_meta = SignalMeta(
            signal_id="my_custom_signal",
            abbrev="MCS",
            signal_name="My Custom Signal",
            category="structural_risk",
            default_weight=0.05,
            is_core=False,
        )
        register_signal_meta(plugin_meta)

        assert get_meta("my_custom_signal") is plugin_meta
        assert get_abbrev_map()["MCS"] == "my_custom_signal"
        assert len(get_all_meta()) == 25  # 24 core + 1 plugin

    def test_duplicate_registration_is_idempotent(self):
        plugin_meta = SignalMeta(
            signal_id="dup_signal",
            abbrev="DPS",
            signal_name="Dup Signal",
            category="style_hygiene",
            default_weight=0.0,
            is_core=False,
        )
        register_signal_meta(plugin_meta)
        register_signal_meta(plugin_meta)  # Second call — must not duplicate

        assert len(get_all_meta()) == 25
        assert list(get_all_meta()).count(plugin_meta) == 1

    def test_reset_removes_plugin_signal(self):
        plugin_meta = SignalMeta(
            signal_id="temp_signal",
            abbrev="TMP",
            signal_name="Temp",
            category="style_hygiene",
            default_weight=0.0,
            is_core=False,
        )
        register_signal_meta(plugin_meta)
        assert len(get_all_meta()) == 25

        _reset_registry()

        assert len(get_all_meta()) == 24
        assert get_meta("temp_signal") is None


# ---------------------------------------------------------------------------
# PluginConfig — config model tests
# ---------------------------------------------------------------------------


class TestPluginConfig:
    def test_plugin_config_default_empty(self):
        cfg = PluginConfig()
        assert cfg.disabled == []

    def test_drift_config_has_plugins_field(self):
        cfg = DriftConfig()
        assert isinstance(cfg.plugins, PluginConfig)
        assert cfg.plugins.disabled == []

    def test_plugin_config_can_disable_plugins(self):
        cfg = PluginConfig(disabled=["my_broken_plugin"])
        assert "my_broken_plugin" in cfg.disabled

    def test_drift_config_plugins_roundtrip(self):
        data = {"plugins": {"disabled": ["foo", "bar"]}}
        cfg = DriftConfig.model_validate(data)
        assert cfg.plugins.disabled == ["foo", "bar"]


# ---------------------------------------------------------------------------
# plugins — discovery with mocked entry points
# ---------------------------------------------------------------------------


class TestPluginDiscovery:
    def test_discover_signal_plugins_empty_when_no_entry_points(self):
        from drift.plugins import discover_signal_plugins

        with patch("drift.plugins.entry_points", return_value=[]):
            result = discover_signal_plugins()
        assert result == []

    def test_discover_signal_plugins_loads_valid_signal(self):
        """discover_signal_plugins should return a loaded BaseSignal subclass."""
        from drift.models import SignalType
        from drift.plugins import discover_signal_plugins
        from drift.signals.base import BaseSignal

        class _FakeSignal(BaseSignal):
            @property
            def signal_type(self):
                return SignalType.PATTERN_FRAGMENTATION

            @property
            def name(self):
                return "Fake"

            def analyze(self, pr, fh, cfg):
                return []

        fake_ep = MagicMock()
        fake_ep.value = "test_package:_FakeSignal"
        fake_ep.load.return_value = _FakeSignal

        with patch("drift.plugins.entry_points", return_value=[fake_ep]):
            result = discover_signal_plugins()

        assert _FakeSignal in result

    def test_discover_signal_plugins_skips_non_basesignal(self):
        from drift.plugins import discover_signal_plugins

        fake_ep = MagicMock()
        fake_ep.value = "test_package:NotASignal"
        fake_ep.load.return_value = int  # not a BaseSignal subclass

        with patch("drift.plugins.entry_points", return_value=[fake_ep]):
            result = discover_signal_plugins()

        assert result == []

    def test_discover_signal_plugins_skips_failed_load(self):
        from drift.plugins import discover_signal_plugins

        fake_ep = MagicMock()
        fake_ep.value = "broken_package:BrokenSignal"
        fake_ep.load.side_effect = ImportError("broken")

        with patch("drift.plugins.entry_points", return_value=[fake_ep]):
            result = discover_signal_plugins()

        assert result == []

    def test_discover_output_plugins_empty_when_no_entry_points(self):
        from drift.plugins import discover_output_plugins

        with patch("drift.plugins.entry_points", return_value=[]):
            result = discover_output_plugins()
        assert result == {}

    def test_discover_command_plugins_empty_when_no_entry_points(self):
        from drift.plugins import discover_command_plugins

        with patch("drift.plugins.entry_points", return_value=[]):
            result = discover_command_plugins()
        assert result == []
