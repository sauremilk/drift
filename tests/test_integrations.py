"""Tests for the drift.integrations package.

Covers:
  - IntegrationResult / IntegrationContext construction
  - runner.run_command (timeout, missing cmd, success)
  - runner.parse_json_output (valid, trailing text, empty)
  - YamlIntegrationAdapter (hint tier, run tier mock)
  - SuperpowersAdapter (unavailable, mock subprocess)
  - Pipeline hook skipped when integrations.enabled=False
  - Config round-trip (IntegrationsGlobalConfig in DriftConfig)
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# base.py
# ---------------------------------------------------------------------------


class TestIntegrationBase:
    def test_integration_result_defaults(self) -> None:
        from drift.integrations.base import IntegrationResult

        r = IntegrationResult(source="test")
        assert r.findings == []
        assert r.summary is None
        assert r.hint_text is None
        assert r.metadata == {}

    def test_integration_context_fields(self, tmp_path: Path) -> None:
        from drift.integrations.base import IntegrationContext

        ctx = IntegrationContext(repo_path=tmp_path, findings=[], config=MagicMock())
        assert ctx.repo_path == tmp_path
        assert ctx.timeout_seconds == 30


# ---------------------------------------------------------------------------
# runner.parse_json_output
# ---------------------------------------------------------------------------


class TestParseJsonOutput:
    def test_parses_array(self) -> None:
        from drift.integrations.runner import parse_json_output

        raw = json.dumps([{"message": "hello"}])
        result = parse_json_output(raw)
        assert isinstance(result, list)
        assert result[0]["message"] == "hello"

    def test_parses_object(self) -> None:
        from drift.integrations.runner import parse_json_output

        raw = json.dumps({"key": "value"})
        result = parse_json_output(raw)
        assert isinstance(result, dict)

    def test_tolerates_trailing_text(self) -> None:
        from drift.integrations.runner import parse_json_output

        raw = '[{"msg": "ok"}] some trailing console output'
        result = parse_json_output(raw)
        assert result is not None
        assert isinstance(result, list)

    def test_returns_none_on_garbage(self) -> None:
        from drift.integrations.runner import parse_json_output

        assert parse_json_output("not json at all") is None

    def test_returns_none_on_empty(self) -> None:
        from drift.integrations.runner import parse_json_output

        assert parse_json_output("") is None
        assert parse_json_output("   ") is None


# ---------------------------------------------------------------------------
# runner.run_command
# ---------------------------------------------------------------------------


class TestRunCommand:
    def test_successful_command(self, tmp_path: Path) -> None:
        from drift.integrations.runner import run_command

        result = run_command(
            ["python", "-c", "print('hello')"],
            repo_path=tmp_path,
            timeout_seconds=10,
        )
        assert "hello" in result.stdout
        assert result.exit_code == 0
        assert not result.timed_out

    def test_repo_path_placeholder_substituted(self, tmp_path: Path) -> None:
        from drift.integrations.runner import run_command

        result = run_command(
            ["python", "-c", "import sys; print(sys.argv[1])", "{repo_path}"],
            repo_path=tmp_path,
            timeout_seconds=10,
        )
        assert str(tmp_path.resolve()) in result.stdout

    def test_missing_command_returns_127(self, tmp_path: Path) -> None:
        from drift.integrations.runner import run_command

        result = run_command(
            ["_nonexistent_cmd_xyz_"],
            repo_path=tmp_path,
            timeout_seconds=5,
        )
        assert result.exit_code == 127

    def test_timeout_returns_timed_out(self, tmp_path: Path) -> None:
        from drift.integrations.runner import run_command

        result = run_command(
            ["python", "-c", "import time; time.sleep(30)"],
            repo_path=tmp_path,
            timeout_seconds=1,
        )
        assert result.timed_out
        assert result.exit_code == -1


# ---------------------------------------------------------------------------
# YamlIntegrationAdapter — hint tier
# ---------------------------------------------------------------------------


class TestYamlHintAdapter:
    def _make_cfg(self, **overrides: object) -> MagicMock:
        cfg = MagicMock()
        cfg.name = overrides.get("name", "my_hint")
        cfg.tier = "hint"
        cfg.enabled = True
        cfg.trigger_signals = ["*"]
        cfg.command = []
        cfg.timeout_seconds = 30
        cfg.output_format = "json"
        cfg.hint_text = overrides.get("hint_text", "Run my-tool for details.")
        sev = MagicMock()
        sev.model_dump.return_value = {"error": "high", "warning": "medium", "info": "info"}
        cfg.severity_map = sev
        return cfg

    def test_is_available_always_true(self) -> None:
        from drift.integrations.registry import YamlIntegrationAdapter

        adapter = YamlIntegrationAdapter(self._make_cfg())
        assert adapter.is_available() is True

    def test_run_returns_hint_text(self, tmp_path: Path) -> None:
        from drift.integrations.registry import YamlIntegrationAdapter

        adapter = YamlIntegrationAdapter(self._make_cfg(hint_text="Use semgrep."))
        ctx = MagicMock()
        ctx.repo_path = tmp_path
        result = adapter.run(ctx)
        assert result.hint_text == "Use semgrep."
        assert result.findings == []


# ---------------------------------------------------------------------------
# SuperpowersAdapter
# ---------------------------------------------------------------------------


class TestSuperpowersAdapter:
    def test_is_available_false_when_not_in_path(self) -> None:
        from drift.integrations.builtin.superpowers import SuperpowersAdapter

        with patch("shutil.which", return_value=None):
            adapter = SuperpowersAdapter()
            assert adapter.is_available() is False

    def test_is_available_true_when_in_path(self) -> None:
        from drift.integrations.builtin.superpowers import SuperpowersAdapter

        with patch("shutil.which", return_value="/usr/bin/superpowers"):
            adapter = SuperpowersAdapter()
            assert adapter.is_available() is True

    def test_run_maps_json_findings(self, tmp_path: Path) -> None:
        from drift.integrations.builtin.superpowers import SuperpowersAdapter
        from drift.integrations.runner import SubprocessResult

        json_output = json.dumps(
            [
                {
                    "message": "Architectural issue",
                    "file": "src/foo.py",
                    "line": 42,
                    "severity": "error",
                }
            ]
        )
        mock_result = SubprocessResult(stdout=json_output, stderr="", exit_code=0)

        ctx = MagicMock()
        ctx.repo_path = tmp_path
        ctx.timeout_seconds = 30

        with patch("drift.integrations.runner.run_command", return_value=mock_result):
            adapter = SuperpowersAdapter()
            result = adapter.run(ctx)

        assert len(result.findings) == 1
        f = result.findings[0]
        assert f.signal_type == "superpowers"
        assert f.title == "Architectural issue"
        assert f.metadata["integration_source"] == "superpowers"

    def test_run_handles_command_not_found(self, tmp_path: Path) -> None:
        from drift.integrations.builtin.superpowers import SuperpowersAdapter
        from drift.integrations.runner import SubprocessResult

        mock_result = SubprocessResult(stdout="", stderr="not found", exit_code=127)
        ctx = MagicMock()
        ctx.repo_path = tmp_path
        ctx.timeout_seconds = 30

        with patch("drift.integrations.runner.run_command", return_value=mock_result):
            adapter = SuperpowersAdapter()
            result = adapter.run(ctx)

        assert result.findings == []
        assert result.summary is not None


# ---------------------------------------------------------------------------
# Config round-trip
# ---------------------------------------------------------------------------


class TestIntegrationsConfig:
    def test_default_disabled(self) -> None:
        from drift.config._schema import IntegrationsGlobalConfig

        cfg = IntegrationsGlobalConfig()
        assert cfg.enabled is False
        assert cfg.adapters == []

    def test_drift_config_has_integrations_field(self) -> None:
        from drift.config import DriftConfig

        cfg = DriftConfig()
        assert hasattr(cfg, "integrations")
        assert cfg.integrations.enabled is False

    def test_round_trip_with_adapter(self) -> None:
        from drift.config._schema import IntegrationsGlobalConfig

        raw = {
            "enabled": True,
            "adapters": [
                {
                    "name": "semgrep",
                    "tier": "hint",
                    "trigger_signals": ["hardcoded_secret"],
                    "hint_text": "Run semgrep.",
                }
            ],
        }
        cfg = IntegrationsGlobalConfig.model_validate(raw)
        assert cfg.enabled is True
        assert len(cfg.adapters) == 1
        adapter = cfg.adapters[0]
        assert adapter.name == "semgrep"
        assert adapter.tier == "hint"
        assert adapter.hint_text == "Run semgrep."

    def test_drift_config_integrations_round_trip(self) -> None:
        from drift.config import DriftConfig

        raw = {
            "integrations": {
                "enabled": True,
                "adapters": [
                    {
                        "name": "superpowers",
                        "tier": "run",
                        "command": ["superpowers", "check", "--format", "json", "{repo_path}"],
                    }
                ],
            }
        }
        cfg = DriftConfig.model_validate(raw)
        assert cfg.integrations.enabled is True
        assert cfg.integrations.adapters[0].name == "superpowers"


# ---------------------------------------------------------------------------
# Pipeline hook — skipped when disabled
# ---------------------------------------------------------------------------


class TestPipelineIntegrationHook:
    def test_hook_skipped_when_disabled(self, tmp_path: Path) -> None:
        """Integration hook must be a no-op when integrations.enabled=False."""
        from drift.integrations.runner import run_integrations

        cfg = MagicMock()
        cfg.integrations.enabled = False

        with patch("drift.integrations.registry.get_registry") as mock_registry:
            results = run_integrations(tmp_path, [], cfg)

        mock_registry.assert_not_called()
        assert results == []

    def test_hook_runs_when_enabled(self, tmp_path: Path) -> None:
        """Integration hook calls registry and returns results when enabled."""
        from drift.integrations.runner import run_integrations

        cfg = MagicMock()
        cfg.integrations.enabled = True

        mock_adapter = MagicMock()
        mock_adapter.enabled = True
        mock_adapter.trigger_signals = ["*"]
        mock_adapter.is_available.return_value = True
        mock_adapter.name = "fake"

        from drift.integrations.base import IntegrationResult

        mock_adapter.run.return_value = IntegrationResult(source="fake", summary="ok")

        with patch("drift.integrations.registry.get_registry", return_value=[mock_adapter]):
            results = run_integrations(tmp_path, [], cfg)

        assert len(results) == 1
        assert results[0].source == "fake"

    def test_disabled_adapter_skipped(self, tmp_path: Path) -> None:
        from drift.integrations.runner import run_integrations

        cfg = MagicMock()
        cfg.integrations.enabled = True

        mock_adapter = MagicMock()
        mock_adapter.enabled = False
        mock_adapter.name = "disabled_adapter"

        with patch("drift.integrations.registry.get_registry", return_value=[mock_adapter]):
            results = run_integrations(tmp_path, [], cfg)

        mock_adapter.run.assert_not_called()
        assert results == []
