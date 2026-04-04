"""CLI tests for ``drift patterns`` command branches."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from drift.cli import main
from drift.models import PatternCategory, PatternInstance


def _pattern(
    category: PatternCategory,
    file_path: str,
    function_name: str,
    start_line: int,
    end_line: int,
    variant: str = "",
) -> PatternInstance:
    return PatternInstance(
        category=category,
        file_path=Path(file_path),
        function_name=function_name,
        start_line=start_line,
        end_line=end_line,
        variant_id=variant,
    )


def test_patterns_json_output_file_and_target_path_passthrough(monkeypatch, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    output_file = tmp_path / "patterns.json"
    calls: dict[str, object] = {}

    fake_catalog = {
        PatternCategory.ERROR_HANDLING: [
            _pattern(
                PatternCategory.ERROR_HANDLING,
                "src/service.py",
                "handle",
                10,
                20,
                "v1",
            )
        ],
        PatternCategory.DATA_ACCESS: [
            _pattern(
                PatternCategory.DATA_ACCESS,
                "src/repo.py",
                "load",
                5,
                8,
            )
        ],
    }

    fake_analysis = type("A", (), {"pattern_catalog": fake_catalog})()
    monkeypatch.setattr("drift.config.DriftConfig.load", lambda r: object())

    def _fake_analyze(repo_path: Path, cfg: object, target_path: str | None = None):
        calls["args"] = (repo_path, target_path)
        return fake_analysis

    monkeypatch.setattr("drift.analyzer.analyze_repo", _fake_analyze)

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "patterns",
            "--repo",
            str(repo),
            "--target-path",
            "src",
            "--format",
            "json",
            "--category",
            "error_handling",
            "--output",
            str(output_file),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Output written to" in result.output
    assert calls["args"] == (repo, "src")
    payload = output_file.read_text(encoding="utf-8")
    assert '"error_handling"' in payload
    assert '"data_access"' not in payload
    assert '"variant": "v1"' in payload


def test_patterns_rich_output_empty_catalog_prints_no_patterns(monkeypatch, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    fake_analysis = type("A", (), {"pattern_catalog": {}})()

    monkeypatch.setattr("drift.config.DriftConfig.load", lambda r: object())
    monkeypatch.setattr("drift.analyzer.analyze_repo", lambda *args, **kwargs: fake_analysis)

    runner = CliRunner()
    result = runner.invoke(main, ["patterns", "--repo", str(repo)])

    assert result.exit_code == 0, result.output
    assert "No patterns detected." in result.output
