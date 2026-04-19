"""Edge-case tests for empty repos and minimal projects (Issue #13).

Validates that ``drift.api.scan()`` handles degenerate repository shapes
gracefully:
- An empty repository (no Python files)
- A single-file project (one ``.py`` file)
- A repository consisting only of ``__init__.py`` files
"""

from __future__ import annotations

from pathlib import Path

import pytest

from drift.api import scan

VALID_SEVERITIES = {"critical", "high", "medium", "low", "info"}


class TestEmptyRepo:
    """Empty repository — no Python files at all."""

    def test_empty_repo_no_crash(self, tmp_path: Path) -> None:
        """An empty directory should not raise."""
        result = scan(tmp_path)
        assert isinstance(result, dict)
        assert result.get("error_code") is None

    def test_empty_repo_score_is_float(self, tmp_path: Path) -> None:
        result = scan(tmp_path)
        assert isinstance(result["drift_score"], (int, float))
        assert result.get("error_code") is None

    def test_empty_repo_severity_valid(self, tmp_path: Path) -> None:
        result = scan(tmp_path)
        assert result["severity"] in VALID_SEVERITIES
        assert result.get("error_code") is None

    def test_empty_repo_findings_are_valid(self, tmp_path: Path) -> None:
        result = scan(tmp_path)
        assert isinstance(result["finding_count"], int)
        assert isinstance(result["findings"], list)
        assert result["finding_count"] == 0
        assert result["findings"] == []
        assert result.get("error_code") is None


class TestSingleFileProject:
    """Repository with a single Python file."""

    @pytest.fixture
    def single_file_repo(self, tmp_path: Path) -> Path:
        (tmp_path / "main.py").write_text(
            'def hello() -> str:\n    """Say hello."""\n    return "Hello, World!"\n',
            encoding="utf-8",
        )
        return tmp_path

    def test_single_file_no_crash(self, single_file_repo: Path) -> None:
        result = scan(single_file_repo)
        assert isinstance(result, dict)
        assert result.get("error_code") is None

    def test_single_file_score_is_float(self, single_file_repo: Path) -> None:
        result = scan(single_file_repo)
        assert isinstance(result["drift_score"], (int, float))
        assert result.get("error_code") is None

    def test_single_file_severity_valid(self, single_file_repo: Path) -> None:
        result = scan(single_file_repo)
        assert result["severity"] in VALID_SEVERITIES
        assert result.get("error_code") is None

    def test_single_file_total_files(self, single_file_repo: Path) -> None:
        result = scan(single_file_repo)
        assert result["total_files"] >= 1
        assert result.get("error_code") is None

    def test_single_file_has_no_bootstrap_readme_finding(
        self,
        single_file_repo: Path,
    ) -> None:
        result = scan(single_file_repo)

        assert result["finding_count"] == 0
        assert result["findings"] == []
        assert result.get("error_code") is None


class TestInitOnlyRepo:
    """Repository with only ``__init__.py`` files."""

    @pytest.fixture
    def init_only_repo(self, tmp_path: Path) -> Path:
        (tmp_path / "__init__.py").write_text("", encoding="utf-8")
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        sub = pkg / "sub"
        sub.mkdir()
        (sub / "__init__.py").write_text("", encoding="utf-8")
        return tmp_path

    def test_init_only_no_crash(self, init_only_repo: Path) -> None:
        result = scan(init_only_repo)
        assert isinstance(result, dict)
        assert result.get("error_code") is None

    def test_init_only_score_is_float(self, init_only_repo: Path) -> None:
        result = scan(init_only_repo)
        assert isinstance(result["drift_score"], (int, float))
        assert result.get("error_code") is None

    def test_init_only_severity_valid(self, init_only_repo: Path) -> None:
        result = scan(init_only_repo)
        assert result["severity"] in VALID_SEVERITIES
        assert result.get("error_code") is None

    def test_init_only_findings_are_valid(self, init_only_repo: Path) -> None:
        result = scan(init_only_repo)
        assert isinstance(result["finding_count"], int)
        assert isinstance(result["findings"], list)
        assert result["finding_count"] == 0
        assert result["findings"] == []
        assert result.get("error_code") is None
