"""Tests for the `drift generate-skills` CLI command.

Covers:
- Default mode (rich preview, no write)
- --write mode: creates SKILL.md files on disk
- --dry-run flag: same as default (no write)
- --format json: outputs JSON
- --min-occurrences / --min-confidence options forwarded to API
- Error case: no graph available (status=error)
- --output flag: writes JSON to file
"""

from __future__ import annotations

import json

from click.testing import CliRunner

from drift.cli import main

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ok_response(count: int = 2) -> dict:
    return {
        "status": "ok",
        "skill_count": count,
        "skill_briefings": [
            {
                "name": "guard-src-api",
                "module_path": "src/api",
                "trigger_signals": ["EDS", "PFS"],
                "constraints": [
                    {"id": "c1", "rule": "No direct DB calls", "enforcement": "block"}
                ],
                "hotspot_files": ["src/api/routes.py"],
                "layer": "api",
                "neighbors": ["src/core"],
                "abstractions": ["BaseHandler"],
                "confidence": 0.85,
            },
            {
                "name": "guard-src-core",
                "module_path": "src/core",
                "trigger_signals": ["AVS"],
                "constraints": [],
                "hotspot_files": ["src/core/engine.py"],
                "layer": "core",
                "neighbors": [],
                "abstractions": [],
                "confidence": 0.72,
            },
        ],
        "agent_instruction": "Create 2 SKILL.md files.",
        "next_tool": "drift_steer",
        "done_when": "skills_created",
    }


def _error_response() -> dict:
    return {
        "status": "error",
        "error_code": "DRIFT-7003",
        "error": "No architecture graph available.",
        "recoverable": True,
    }


# ---------------------------------------------------------------------------
# Default mode (rich preview, no write)
# ---------------------------------------------------------------------------


class TestDefaultMode:
    def test_exits_zero_on_ok_response(self, monkeypatch, tmp_path):
        import drift.commands.generate_skills_cmd as cmd_mod

        monkeypatch.setattr(cmd_mod, "_api_generate_skills", lambda **kw: _ok_response())
        runner = CliRunner()
        result = runner.invoke(main, ["generate-skills", "--repo", str(tmp_path)])
        assert result.exit_code == 0

    def test_shows_skill_count(self, monkeypatch, tmp_path):
        import drift.commands.generate_skills_cmd as cmd_mod

        monkeypatch.setattr(cmd_mod, "_api_generate_skills", lambda **kw: _ok_response(2))
        runner = CliRunner()
        result = runner.invoke(main, ["generate-skills", "--repo", str(tmp_path)])
        assert "2" in result.output

    def test_shows_module_paths(self, monkeypatch, tmp_path):
        import drift.commands.generate_skills_cmd as cmd_mod

        monkeypatch.setattr(cmd_mod, "_api_generate_skills", lambda **kw: _ok_response())
        runner = CliRunner()
        result = runner.invoke(main, ["generate-skills", "--repo", str(tmp_path)])
        assert "src/api" in result.output
        assert "src/core" in result.output

    def test_does_not_write_files(self, monkeypatch, tmp_path):
        import drift.commands.generate_skills_cmd as cmd_mod

        monkeypatch.setattr(cmd_mod, "_api_generate_skills", lambda **kw: _ok_response())
        runner = CliRunner()
        runner.invoke(main, ["generate-skills", "--repo", str(tmp_path)])
        skills_dir = tmp_path / ".github" / "skills"
        assert not skills_dir.exists()

    def test_zero_briefings_shows_no_modules_message(self, monkeypatch, tmp_path):
        import drift.commands.generate_skills_cmd as cmd_mod

        monkeypatch.setattr(
            cmd_mod,
            "_api_generate_skills",
            lambda **kw: {
                "status": "ok",
                "skill_count": 0,
                "skill_briefings": [],
                "agent_instruction": "No skills needed.",
            },
        )
        runner = CliRunner()
        result = runner.invoke(main, ["generate-skills", "--repo", str(tmp_path)])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# --write mode
# ---------------------------------------------------------------------------


class TestWriteMode:
    def test_exits_zero(self, monkeypatch, tmp_path):
        import drift.commands.generate_skills_cmd as cmd_mod

        monkeypatch.setattr(cmd_mod, "_api_generate_skills", lambda **kw: _ok_response())
        runner = CliRunner()
        result = runner.invoke(
            main, ["generate-skills", "--repo", str(tmp_path), "--write"]
        )
        assert result.exit_code == 0

    def test_creates_skill_md_files(self, monkeypatch, tmp_path):
        import drift.commands.generate_skills_cmd as cmd_mod

        monkeypatch.setattr(cmd_mod, "_api_generate_skills", lambda **kw: _ok_response())
        runner = CliRunner()
        runner.invoke(main, ["generate-skills", "--repo", str(tmp_path), "--write"])
        assert (tmp_path / ".github" / "skills" / "guard-src-api" / "SKILL.md").exists()
        assert (tmp_path / ".github" / "skills" / "guard-src-core" / "SKILL.md").exists()

    def test_written_file_contains_module_path(self, monkeypatch, tmp_path):
        import drift.commands.generate_skills_cmd as cmd_mod

        monkeypatch.setattr(cmd_mod, "_api_generate_skills", lambda **kw: _ok_response())
        runner = CliRunner()
        runner.invoke(main, ["generate-skills", "--repo", str(tmp_path), "--write"])
        content = (
            tmp_path / ".github" / "skills" / "guard-src-api" / "SKILL.md"
        ).read_text(encoding="utf-8")
        assert "src/api" in content

    def test_written_file_contains_signals(self, monkeypatch, tmp_path):
        import drift.commands.generate_skills_cmd as cmd_mod

        monkeypatch.setattr(cmd_mod, "_api_generate_skills", lambda **kw: _ok_response())
        runner = CliRunner()
        runner.invoke(main, ["generate-skills", "--repo", str(tmp_path), "--write"])
        content = (
            tmp_path / ".github" / "skills" / "guard-src-api" / "SKILL.md"
        ).read_text(encoding="utf-8")
        assert "EDS" in content
        assert "PFS" in content

    def test_output_confirms_written_paths(self, monkeypatch, tmp_path):
        import drift.commands.generate_skills_cmd as cmd_mod

        monkeypatch.setattr(cmd_mod, "_api_generate_skills", lambda **kw: _ok_response())
        runner = CliRunner()
        result = runner.invoke(
            main, ["generate-skills", "--repo", str(tmp_path), "--write"]
        )
        assert "guard-src-api" in result.output or "SKILL.md" in result.output

    def test_does_not_overwrite_without_force(self, monkeypatch, tmp_path):
        import drift.commands.generate_skills_cmd as cmd_mod

        monkeypatch.setattr(cmd_mod, "_api_generate_skills", lambda **kw: _ok_response())
        skill_dir = tmp_path / ".github" / "skills" / "guard-src-api"
        skill_dir.mkdir(parents=True)
        existing = skill_dir / "SKILL.md"
        existing.write_text("EXISTING CONTENT", encoding="utf-8")

        runner = CliRunner()
        runner.invoke(main, ["generate-skills", "--repo", str(tmp_path), "--write"])
        assert existing.read_text(encoding="utf-8") == "EXISTING CONTENT"

    def test_force_overwrites_existing(self, monkeypatch, tmp_path):
        import drift.commands.generate_skills_cmd as cmd_mod

        monkeypatch.setattr(cmd_mod, "_api_generate_skills", lambda **kw: _ok_response())
        skill_dir = tmp_path / ".github" / "skills" / "guard-src-api"
        skill_dir.mkdir(parents=True)
        existing = skill_dir / "SKILL.md"
        existing.write_text("EXISTING CONTENT", encoding="utf-8")

        runner = CliRunner()
        runner.invoke(
            main, ["generate-skills", "--repo", str(tmp_path), "--write", "--force"]
        )
        assert existing.read_text(encoding="utf-8") != "EXISTING CONTENT"


# ---------------------------------------------------------------------------
# --dry-run flag (preview only, no write)
# ---------------------------------------------------------------------------


class TestDryRunMode:
    def test_dry_run_does_not_write(self, monkeypatch, tmp_path):
        import drift.commands.generate_skills_cmd as cmd_mod

        monkeypatch.setattr(cmd_mod, "_api_generate_skills", lambda **kw: _ok_response())
        runner = CliRunner()
        runner.invoke(
            main, ["generate-skills", "--repo", str(tmp_path), "--write", "--dry-run"]
        )
        assert not (
            tmp_path / ".github" / "skills" / "guard-src-api" / "SKILL.md"
        ).exists()

    def test_dry_run_shows_preview(self, monkeypatch, tmp_path):
        import drift.commands.generate_skills_cmd as cmd_mod

        monkeypatch.setattr(cmd_mod, "_api_generate_skills", lambda **kw: _ok_response())
        runner = CliRunner()
        result = runner.invoke(
            main, ["generate-skills", "--repo", str(tmp_path), "--write", "--dry-run"]
        )
        assert result.exit_code == 0
        assert "src/api" in result.output or "guard-src-api" in result.output


# ---------------------------------------------------------------------------
# --format json
# ---------------------------------------------------------------------------


class TestJsonFormat:
    def test_outputs_valid_json(self, monkeypatch, tmp_path):
        import drift.commands.generate_skills_cmd as cmd_mod

        monkeypatch.setattr(cmd_mod, "_api_generate_skills", lambda **kw: _ok_response())
        runner = CliRunner()
        result = runner.invoke(
            main, ["generate-skills", "--repo", str(tmp_path), "--format", "json"]
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["status"] == "ok"

    def test_json_contains_skill_briefings(self, monkeypatch, tmp_path):
        import drift.commands.generate_skills_cmd as cmd_mod

        monkeypatch.setattr(cmd_mod, "_api_generate_skills", lambda **kw: _ok_response())
        runner = CliRunner()
        result = runner.invoke(
            main, ["generate-skills", "--repo", str(tmp_path), "--format", "json"]
        )
        payload = json.loads(result.output)
        assert "skill_briefings" in payload
        assert len(payload["skill_briefings"]) == 2


# ---------------------------------------------------------------------------
# Option forwarding
# ---------------------------------------------------------------------------


class TestOptionForwarding:
    def test_min_occurrences_forwarded(self, monkeypatch, tmp_path):
        import drift.commands.generate_skills_cmd as cmd_mod

        captured: dict = {}

        def fake_api(**kw):
            captured.update(kw)
            return _ok_response()

        monkeypatch.setattr(cmd_mod, "_api_generate_skills", fake_api)
        runner = CliRunner()
        runner.invoke(
            main,
            ["generate-skills", "--repo", str(tmp_path), "--min-occurrences", "7"],
        )
        assert captured.get("min_occurrences") == 7

    def test_min_confidence_forwarded(self, monkeypatch, tmp_path):
        import drift.commands.generate_skills_cmd as cmd_mod

        captured: dict = {}

        def fake_api(**kw):
            captured.update(kw)
            return _ok_response()

        monkeypatch.setattr(cmd_mod, "_api_generate_skills", fake_api)
        runner = CliRunner()
        runner.invoke(
            main,
            ["generate-skills", "--repo", str(tmp_path), "--min-confidence", "0.8"],
        )
        assert abs(captured.get("min_confidence", 0) - 0.8) < 0.001


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def test_error_response_exits_nonzero(self, monkeypatch, tmp_path):
        import drift.commands.generate_skills_cmd as cmd_mod

        monkeypatch.setattr(
            cmd_mod, "_api_generate_skills", lambda **kw: _error_response()
        )
        runner = CliRunner()
        result = runner.invoke(main, ["generate-skills", "--repo", str(tmp_path)])
        assert result.exit_code != 0

    def test_error_response_json_exits_nonzero(self, monkeypatch, tmp_path):
        import drift.commands.generate_skills_cmd as cmd_mod

        monkeypatch.setattr(
            cmd_mod, "_api_generate_skills", lambda **kw: _error_response()
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["generate-skills", "--repo", str(tmp_path), "--format", "json"],
        )
        assert result.exit_code != 0

    def test_error_shown_to_user(self, monkeypatch, tmp_path):
        import drift.commands.generate_skills_cmd as cmd_mod

        monkeypatch.setattr(
            cmd_mod, "_api_generate_skills", lambda **kw: _error_response()
        )
        runner = CliRunner()
        result = runner.invoke(main, ["generate-skills", "--repo", str(tmp_path)])
        output = result.output + (result.output or "")
        assert "error" in output.lower() or "DRIFT-7003" in output


# ---------------------------------------------------------------------------
# --output flag
# ---------------------------------------------------------------------------


class TestOutputFlag:
    def test_output_writes_json_to_file(self, monkeypatch, tmp_path):
        import drift.commands.generate_skills_cmd as cmd_mod

        monkeypatch.setattr(cmd_mod, "_api_generate_skills", lambda **kw: _ok_response())
        out_file = tmp_path / "skills.json"
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "generate-skills",
                "--repo",
                str(tmp_path),
                "--format",
                "json",
                "--output",
                str(out_file),
            ],
        )
        assert result.exit_code == 0
        assert out_file.exists()
        payload = json.loads(out_file.read_text(encoding="utf-8"))
        assert payload["status"] == "ok"
