"""Edge-case repository shape tests for public scan API."""

from __future__ import annotations

from pathlib import Path

from drift.api import scan


def test_scan_empty_repo_returns_informational_empty_result(tmp_path: Path) -> None:
    result = scan(path=tmp_path)

    assert isinstance(result["drift_score"], float)
    assert result["drift_score"] == 0.0
    assert result["severity"] == "info"
    assert result["finding_count"] == 0
    assert result["findings"] == []


def test_scan_single_file_repo_returns_valid_analysis(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("def hello() -> int:\n    return 1\n")

    result = scan(path=tmp_path)

    assert isinstance(result["drift_score"], float)
    assert result["severity"] == "info"
    assert result["total_files"] == 1
    assert result["finding_count"] == 0


def test_scan_init_only_repo_returns_valid_analysis(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")

    result = scan(path=tmp_path)

    assert isinstance(result["drift_score"], float)
    assert result["severity"] == "info"
    assert result["total_files"] == 1
    assert result["total_functions"] == 0
    assert result["finding_count"] == 0
