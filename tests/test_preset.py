"""Tests for drift preset command (C3)."""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner


class TestPresetListCommand:
    """Test the preset list CLI command."""

    def test_preset_list_shows_all_builtin(self) -> None:
        from drift.commands.preset import preset

        runner = CliRunner()
        result = runner.invoke(preset, ["list"])
        assert result.exit_code == 0
        assert "default" in result.output
        assert "vibe-coding" in result.output
        assert "strict" in result.output
        assert "fastapi" in result.output
        assert "library" in result.output
        assert "monorepo" in result.output

    def test_preset_list_json(self) -> None:
        from drift.commands.preset import preset

        runner = CliRunner()
        result = runner.invoke(preset, ["list", "--json"])
        assert result.exit_code == 0
        items = json.loads(result.output)
        names = {item["name"] for item in items}
        assert "default" in names
        assert "fastapi" in names
        assert "monorepo" in names
        assert all(item["source"] == "built-in" for item in items)

    def test_preset_list_json_has_required_fields(self) -> None:
        from drift.commands.preset import preset

        runner = CliRunner()
        result = runner.invoke(preset, ["list", "--json"])
        items = json.loads(result.output)
        for item in items:
            assert "name" in item
            assert "description" in item
            assert "source" in item


class TestPresetShowCommand:
    """Test the preset show CLI command."""

    def test_show_default(self) -> None:
        from drift.commands.preset import preset

        runner = CliRunner()
        result = runner.invoke(preset, ["show", "default"])
        assert result.exit_code == 0
        assert "default" in result.output
        assert "pattern_fragmentation" in result.output

    def test_show_fastapi(self) -> None:
        from drift.commands.preset import preset

        runner = CliRunner()
        result = runner.invoke(preset, ["show", "fastapi"])
        assert result.exit_code == 0
        assert "fastapi" in result.output
        assert "architecture_violation" in result.output

    def test_show_unknown_preset(self) -> None:
        from drift.commands.preset import preset

        runner = CliRunner()
        result = runner.invoke(preset, ["show", "nonexistent"])
        assert result.exit_code != 0


class TestProfileRegistry:
    """Test that all expected profiles are registered."""

    def test_all_profiles_registered(self) -> None:
        from drift.profiles import PROFILES

        expected = {"default", "vibe-coding", "strict", "fastapi", "library", "monorepo", "quick"}
        assert expected == set(PROFILES.keys())

    def test_fastapi_has_layer_policies(self) -> None:
        from drift.profiles import get_profile

        p = get_profile("fastapi")
        assert "layer_boundaries" in p.policies
        assert len(p.policies["layer_boundaries"]) == 2

    def test_library_upweights_api_quality(self) -> None:
        from drift.profiles import get_profile

        p = get_profile("library")
        assert p.weights["explainability_deficit"] > 0.10
        assert p.weights["naming_contract_violation"] > 0.05

    def test_monorepo_has_high_file_limit(self) -> None:
        from drift.profiles import get_profile

        p = get_profile("monorepo")
        assert p.thresholds["max_discovery_files"] == 20000

    def test_quick_disables_expensive_signals(self) -> None:
        from drift.profiles import get_profile

        p = get_profile("quick")
        assert p.weights["temporal_volatility"] == 0.0
        assert p.weights["co_change_coupling"] == 0.0
        assert p.thresholds["max_discovery_files"] == 2000
        assert p.auto_calibrate is False

    def test_get_profile_unknown_raises(self) -> None:
        from drift.profiles import get_profile

        with pytest.raises(KeyError, match="Unknown profile"):
            get_profile("unknown_profile_xyz")

    def test_list_profiles_returns_all(self) -> None:
        from drift.profiles import list_profiles

        profiles = list_profiles()
        assert len(profiles) >= 7
        names = [p.name for p in profiles]
        assert "fastapi" in names
