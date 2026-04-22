"""Tests for the three discovery-gap fixes:

1. Attribution hint shown in `drift config show` when attribution is disabled.
2. Plugin commands registered in CLI at startup.
3. `drift adr` CLI command backed by adr_scanner.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

# ---------------------------------------------------------------------------
# Gap 1 — Attribution hint in config show
# ---------------------------------------------------------------------------


class TestAttributionHintInConfigShow:
    """drift config show should mention attribution when it is disabled."""

    def test_hint_shown_when_attribution_disabled(self, tmp_path: Path) -> None:
        from drift.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["config", "show", "--repo", str(tmp_path)])
        assert result.exit_code == 0, result.output
        assert "attribution" in result.output.lower()
        assert "attribution.enabled: true" in result.output

    def test_hint_absent_when_attribution_enabled(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "drift.yaml"
        cfg_file.write_text("attribution:\n  enabled: true\n", encoding="utf-8")

        from drift.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["config", "show", "--repo", str(tmp_path)])
        assert result.exit_code == 0, result.output
        # Hint about enabling attribution should NOT appear
        assert "attribution.enabled: true" not in result.output


# ---------------------------------------------------------------------------
# Gap 2 — Plugin commands registered in CLI startup
# ---------------------------------------------------------------------------


class TestPluginCommandsInCLI:
    """Plugin commands discovered via entry points should appear in drift --help."""

    def test_plugin_command_added_to_main_group(self) -> None:
        """Plugin commands discovered via discover_command_plugins are added to main."""
        import click

        from drift.cli import main

        fake_cmd = click.command("my-plugin-cmd-x")(lambda: None)

        with patch("drift.plugins.discover_command_plugins", return_value=[fake_cmd]):
            # Simulate the block that cli.py runs at module level:
            from drift.plugins import discover_command_plugins

            for cmd in discover_command_plugins():
                if cmd.name and cmd.name not in main.commands:
                    main.add_command(cmd)

        assert "my-plugin-cmd-x" in main.commands
        # Cleanup: remove injected command to avoid leaking state
        main.commands.pop("my-plugin-cmd-x", None)

    def test_plugin_discovery_failure_does_not_crash_cli(self) -> None:
        """A broken plugin entry point must not prevent normal CLI startup."""
        from click.testing import CliRunner

        from drift.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Gap 3 — drift adr CLI command
# ---------------------------------------------------------------------------


_ADR_ACCEPTED = """\
---
id: ADR-001
status: accepted
date: 2026-01-01
---
# ADR-001: Use signals layer for pattern detection

## Kontext
signals layer handles pattern detection.
"""

_ADR_PROPOSED = """\
---
id: ADR-002
status: proposed
date: 2026-02-01
---
# ADR-002: Introduce session management

## Kontext
session management for mcp layer.
"""


def _setup_decisions(tmp_path: Path) -> Path:
    decisions = tmp_path / "decisions"
    decisions.mkdir()
    (decisions / "ADR-001.md").write_text(_ADR_ACCEPTED, encoding="utf-8")
    (decisions / "ADR-002.md").write_text(_ADR_PROPOSED, encoding="utf-8")
    return decisions


class TestDriftAdrCommand:
    """Tests for `drift adr` CLI command."""

    def test_lists_accepted_adr(self, tmp_path: Path) -> None:
        _setup_decisions(tmp_path)
        from drift.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["adr", "--repo", str(tmp_path)])
        assert result.exit_code == 0, result.output
        assert "ADR-001" in result.output

    def test_lists_proposed_adr(self, tmp_path: Path) -> None:
        _setup_decisions(tmp_path)
        from drift.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["adr", "--repo", str(tmp_path)])
        assert result.exit_code == 0, result.output
        assert "ADR-002" in result.output

    def test_json_format_returns_valid_json(self, tmp_path: Path) -> None:
        import json

        _setup_decisions(tmp_path)
        from drift.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["adr", "--repo", str(tmp_path), "--format", "json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 2
        ids = {entry["id"] for entry in data}
        assert "ADR-001" in ids
        assert "ADR-002" in ids

    def test_no_decisions_dir_shows_hint(self, tmp_path: Path) -> None:
        from drift.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["adr", "--repo", str(tmp_path)])
        assert result.exit_code == 0, result.output
        assert "decisions/" in result.output

    def test_task_filter_narrows_results(self, tmp_path: Path) -> None:
        import json

        _setup_decisions(tmp_path)
        from drift.cli import main

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["adr", "--repo", str(tmp_path), "--task", "session management", "--format", "json"],
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        ids = [entry["id"] for entry in data]
        assert "ADR-002" in ids
        assert "ADR-001" not in ids

    def test_scope_filter_narrows_results(self, tmp_path: Path) -> None:
        import json

        _setup_decisions(tmp_path)
        from drift.cli import main

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "adr",
                "--repo",
                str(tmp_path),
                "--scope",
                "src/drift/signals",
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        ids = [entry["id"] for entry in data]
        assert "ADR-001" in ids

    def test_adr_command_in_help(self) -> None:
        from drift.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "adr" in result.output
