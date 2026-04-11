"""Tests for ``drift init`` command and profile system."""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from click.testing import CliRunner

from drift.cli import main
from drift.commands import init_cmd as init_cmd_module
from drift.profiles import PROFILES, get_profile, list_profiles

# ---------------------------------------------------------------------------
# Profile registry tests
# ---------------------------------------------------------------------------


class TestProfiles:
    def test_default_profile_exists(self) -> None:
        assert "default" in PROFILES

    def test_vibe_coding_profile_exists(self) -> None:
        assert "vibe-coding" in PROFILES

    def test_strict_profile_exists(self) -> None:
        assert "strict" in PROFILES

    def test_get_profile_returns_correct(self) -> None:
        p = get_profile("vibe-coding")
        assert p.name == "vibe-coding"
        assert p.weights["mutant_duplicate"] == 0.20

    def test_get_profile_unknown_raises(self) -> None:
        import pytest

        with pytest.raises(KeyError, match="Unknown profile"):
            get_profile("nonexistent")

    def test_list_profiles_returns_all(self) -> None:
        profiles = list_profiles()
        names = {p.name for p in profiles}
        assert names >= {"default", "vibe-coding", "strict"}

    def test_vibe_coding_upweights_copy_paste(self) -> None:
        """Vibe-coding profile must upweight MDS and PFS vs default."""
        vc = get_profile("vibe-coding")
        default = get_profile("default")
        assert vc.weights["mutant_duplicate"] > default.weights["mutant_duplicate"]
        assert vc.weights["pattern_fragmentation"] > default.weights["pattern_fragmentation"]

    def test_vibe_coding_upweights_bypass(self) -> None:
        vc = get_profile("vibe-coding")
        default = get_profile("default")
        assert vc.weights["bypass_accumulation"] > default.weights["bypass_accumulation"]
        assert vc.weights["test_polarity_deficit"] > default.weights["test_polarity_deficit"]

    def test_vibe_coding_lower_thresholds(self) -> None:
        """Vibe-coding should have lower similarity threshold to catch more duplicates."""
        vc = get_profile("vibe-coding")
        default = get_profile("default")
        vc_sim = vc.thresholds["similarity_threshold"]
        default_sim = default.thresholds["similarity_threshold"]
        assert float(vc_sim) < float(default_sim)  # type: ignore[arg-type]

    def test_strict_fail_on_medium(self) -> None:
        strict = get_profile("strict")
        assert strict.fail_on == "medium"


# ---------------------------------------------------------------------------
# drift init command tests
# ---------------------------------------------------------------------------


class TestInitCommand:
    def test_init_creates_drift_yaml(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["init", "--repo", str(tmp_path)])
        assert result.exit_code == 0
        config_path = tmp_path / "drift.yaml"
        assert config_path.exists()
        data = yaml.safe_load(config_path.read_text())
        assert "weights" in data
        assert "include" in data

    def test_init_default_profile(self, tmp_path: Path) -> None:
        runner = CliRunner()
        runner.invoke(main, ["init", "--repo", str(tmp_path)])
        data = yaml.safe_load((tmp_path / "drift.yaml").read_text())
        assert data["weights"]["mutant_duplicate"] == 0.13  # default weight

    def test_init_default_excludes_non_operational_paths(self, tmp_path: Path) -> None:
        """Generated config should not broaden scope vs baseline defaults."""
        runner = CliRunner()
        result = runner.invoke(main, ["init", "--repo", str(tmp_path)])
        assert result.exit_code == 0

        data = yaml.safe_load((tmp_path / "drift.yaml").read_text())
        excludes = set(data["exclude"])

        assert "**/docs/**" in excludes
        assert "**/docs_src/**" in excludes
        assert "**/examples/**" in excludes
        assert "**/tests/**" in excludes
        assert "**/scripts/**" in excludes
        assert "**/site/**" in excludes

    def test_init_vibe_coding_profile(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["init", "--profile", "vibe-coding", "--repo", str(tmp_path)])
        assert result.exit_code == 0
        data = yaml.safe_load((tmp_path / "drift.yaml").read_text())
        assert data["weights"]["mutant_duplicate"] == 0.20
        assert data["weights"]["bypass_accumulation"] == 0.06
        assert data["thresholds"]["similarity_threshold"] == 0.75

    def test_init_strict_profile(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["init", "--profile", "strict", "--repo", str(tmp_path)])
        assert result.exit_code == 0
        data = yaml.safe_load((tmp_path / "drift.yaml").read_text())
        assert data["fail_on"] == "medium"

    def test_init_ci_creates_workflow(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["init", "--ci", "--repo", str(tmp_path)])
        assert result.exit_code == 0
        wf = tmp_path / ".github" / "workflows" / "drift.yml"
        assert wf.exists()
        content = wf.read_text()
        assert "mick-gsk/drift@v1" in content
        assert "fetch-depth: 0" in content

    def test_init_hooks_creates_pre_push(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["init", "--hooks", "--repo", str(tmp_path)])
        assert result.exit_code == 0
        hook = tmp_path / ".githooks" / "drift-pre-push"
        assert hook.exists()
        content = hook.read_text()
        assert "drift check" in content
        assert "DRIFT_SKIP_CHECK" in content

    def test_init_mcp_creates_vscode_config(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["init", "--mcp", "--repo", str(tmp_path)])
        assert result.exit_code == 0
        mcp_path = tmp_path / ".vscode" / "mcp.json"
        assert mcp_path.exists()
        data = json.loads(mcp_path.read_text())
        assert "drift" in data["servers"]

    def test_init_claude_creates_config_snippet(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["init", "--claude", "--repo", str(tmp_path)])
        assert result.exit_code == 0
        claude_path = tmp_path / "claude_desktop_config.json"
        assert claude_path.exists()
        data = json.loads(claude_path.read_text())
        assert "drift" in data["mcpServers"]
        command = data["mcpServers"]["drift"]["command"]
        args = data["mcpServers"]["drift"]["args"]

        if command == "drift":
            assert args == ["mcp", "--serve"]
        else:
            assert args == ["-m", "drift", "mcp", "--serve"]

    def test_init_claude_dry_run_lists_snippet(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["init", "--claude", "--dry-run", "--repo", str(tmp_path)])
        assert result.exit_code == 0
        assert "claude_desktop_config.json" in result.output
        assert not (tmp_path / "claude_desktop_config.json").exists()

    def test_init_full_json_includes_claude_snippet(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["init", "--full", "--json", "--repo", str(tmp_path)])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        paths = {item["path"] for item in payload["would_create"]}
        assert "claude_desktop_config.json" in paths

    def test_init_dry_run_marks_existing_files_as_skip(self, tmp_path: Path) -> None:
        runner = CliRunner()
        runner.invoke(main, ["init", "--claude", "--repo", str(tmp_path)])

        result = runner.invoke(main, ["init", "--claude", "--dry-run", "--repo", str(tmp_path)])
        assert result.exit_code == 0
        assert "skip" in result.output.lower()
        assert "would skip" in result.output.lower()

    def test_init_full_json_marks_existing_files_as_skip(self, tmp_path: Path) -> None:
        runner = CliRunner()
        runner.invoke(main, ["init", "--full", "--repo", str(tmp_path)])

        result = runner.invoke(main, ["init", "--full", "--json", "--repo", str(tmp_path)])
        assert result.exit_code == 0

        payload = json.loads(result.output)
        drift_yaml = next(item for item in payload["would_create"] if item["path"] == "drift.yaml")
        assert drift_yaml["action"] == "skip"
        assert drift_yaml["would_skip"] is True
        assert drift_yaml["would_overwrite"] is False

    def test_init_claude_falls_back_to_current_python(self, monkeypatch, tmp_path: Path) -> None:
        runner = CliRunner()
        monkeypatch.setattr(init_cmd_module.shutil, "which", lambda _name: None)
        monkeypatch.setattr(init_cmd_module.sys, "executable", "C:/Python311/python.exe")

        result = runner.invoke(main, ["init", "--claude", "--repo", str(tmp_path)])
        assert result.exit_code == 0

        data = json.loads((tmp_path / "claude_desktop_config.json").read_text())
        assert data["mcpServers"]["drift"]["command"] == "C:/Python311/python.exe"
        assert data["mcpServers"]["drift"]["args"] == ["-m", "drift", "mcp", "--serve"]
        assert "current Python" in result.output
        assert "interpreter" in result.output

    def test_init_mcp_prefers_console_script_when_available(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        runner = CliRunner()

        def _fake_which(name: str) -> str | None:
            return "C:/Tools/drift.exe" if name == "drift" else None

        monkeypatch.setattr(init_cmd_module.shutil, "which", _fake_which)
        result = runner.invoke(main, ["init", "--mcp", "--repo", str(tmp_path)])
        assert result.exit_code == 0

        data = json.loads((tmp_path / ".vscode" / "mcp.json").read_text())
        assert data["servers"]["drift"]["command"] == "drift"
        assert data["servers"]["drift"]["args"] == ["mcp", "--serve"]

    def test_init_mcp_and_claude_share_launcher(self, monkeypatch, tmp_path: Path) -> None:
        runner = CliRunner()
        monkeypatch.setattr(init_cmd_module.shutil, "which", lambda _name: None)
        monkeypatch.setattr(init_cmd_module.sys, "executable", "C:/Python311/python.exe")

        result = runner.invoke(main, ["init", "--mcp", "--claude", "--repo", str(tmp_path)])
        assert result.exit_code == 0

        vscode_data = json.loads((tmp_path / ".vscode" / "mcp.json").read_text())
        claude_data = json.loads((tmp_path / "claude_desktop_config.json").read_text())
        assert (
            vscode_data["servers"]["drift"]["command"]
            == claude_data["mcpServers"]["drift"]["command"]
        )
        assert vscode_data["servers"]["drift"]["args"] == claude_data["mcpServers"]["drift"]["args"]

    def test_init_full_creates_all(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            main, ["init", "--full", "-p", "vibe-coding", "--repo", str(tmp_path)]
        )
        assert result.exit_code == 0
        assert (tmp_path / "drift.yaml").exists()
        assert (tmp_path / ".github" / "workflows" / "drift.yml").exists()
        assert (tmp_path / ".githooks" / "drift-pre-push").exists()
        assert (tmp_path / ".vscode" / "mcp.json").exists()
        assert (tmp_path / "claude_desktop_config.json").exists()

    def test_init_skips_existing_files(self, tmp_path: Path) -> None:
        """Running init twice should not overwrite existing files."""
        runner = CliRunner()
        runner.invoke(main, ["init", "--repo", str(tmp_path)])
        original = (tmp_path / "drift.yaml").read_text()

        result = runner.invoke(main, ["init", "--repo", str(tmp_path)])
        assert result.exit_code == 0
        assert "already exists" in result.output
        assert (tmp_path / "drift.yaml").read_text() == original

    def test_init_yaml_is_valid(self, tmp_path: Path) -> None:
        """Generated YAML must be loadable by DriftConfig."""
        from drift.config import DriftConfig

        runner = CliRunner()
        runner.invoke(main, ["init", "-p", "vibe-coding", "--repo", str(tmp_path)])
        cfg = DriftConfig.load(tmp_path, tmp_path / "drift.yaml")
        assert cfg.weights.mutant_duplicate == 0.20
        assert cfg.thresholds.similarity_threshold == 0.75

    def test_init_vibe_coding_has_policies(self, tmp_path: Path) -> None:
        runner = CliRunner()
        runner.invoke(main, ["init", "-p", "vibe-coding", "--repo", str(tmp_path)])
        data = yaml.safe_load((tmp_path / "drift.yaml").read_text())
        assert "policies" in data
        assert len(data["policies"]["layer_boundaries"]) >= 2

    def test_init_workflow_strict_uses_medium(self, tmp_path: Path) -> None:
        runner = CliRunner()
        runner.invoke(main, ["init", "-p", "strict", "--ci", "--repo", str(tmp_path)])
        wf = (tmp_path / ".github" / "workflows" / "drift.yml").read_text()
        assert 'fail-on: "medium"' in wf

    def test_init_output_mentions_next_steps(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["init", "--repo", str(tmp_path)])
        assert "drift analyze" in result.output

    def test_init_claude_output_mentions_merge_target(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["init", "--claude", "--repo", str(tmp_path)])
        assert "claude_desktop_config.json" in result.output
        assert "%APPDATA%\\Claude\\claude_desktop_config.json" in result.output

    def test_init_vibe_coding_mentions_escalation(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["init", "-p", "vibe-coding", "--repo", str(tmp_path)])
        assert "fail_on" in result.output or "escalate" in result.output.lower()
