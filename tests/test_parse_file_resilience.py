"""Tests for file parsing resilience against I/O failures.

Validates that ``parse_python_file``, ``parse_typescript_file``, and
``_parse_typescript_stub`` handle files that disappear or become
unreadable between discovery and parsing (race condition) by returning
a valid ParseResult with error information instead of propagating an
unhandled exception through the pipeline.
"""

from __future__ import annotations

from pathlib import Path

from drift.ingestion.ast_parser import _parse_typescript_stub, parse_python_file
from drift.ingestion.ts_parser import parse_typescript_file


class TestParsePythonFileIOResilience:
    """parse_python_file must not crash on missing/unreadable files."""

    def test_file_deleted_between_discovery_and_parse(self, tmp_path: Path) -> None:
        """File discovered but deleted before parsing → ParseResult with error."""
        repo_path = tmp_path
        file_path = Path("vanished.py")
        # File does NOT exist at repo_path / file_path
        result = parse_python_file(file_path, repo_path)

        assert result.file_path == file_path
        assert result.language == "python"
        assert result.line_count == 0
        assert result.functions == []
        assert result.classes == []
        assert result.imports == []
        assert len(result.parse_errors) >= 1
        error_msg = result.parse_errors[0]
        assert "FileNotFoundError" in error_msg or "No such file" in error_msg

    def test_file_is_directory(self, tmp_path: Path) -> None:
        """Path points to a directory instead of a file → ParseResult with error."""
        repo_path = tmp_path
        dir_path = tmp_path / "not_a_file.py"
        dir_path.mkdir()
        file_path = Path("not_a_file.py")

        result = parse_python_file(file_path, repo_path)

        assert result.file_path == file_path
        assert len(result.parse_errors) >= 1

    def test_valid_file_still_works(self, tmp_path: Path) -> None:
        """Normal file parsing is unaffected by the error handling."""
        repo_path = tmp_path
        (tmp_path / "valid.py").write_text("def hello():\n    pass\n", encoding="utf-8")
        file_path = Path("valid.py")

        result = parse_python_file(file_path, repo_path)

        assert result.file_path == file_path
        assert result.language == "python"
        assert result.parse_errors == []
        assert len(result.functions) == 1


class TestParseTypescriptFileIOResilience:
    """parse_typescript_file must not crash on missing files."""

    def test_ts_file_deleted_between_discovery_and_parse(self, tmp_path: Path) -> None:
        """TS file discovered but deleted → ParseResult with error."""
        result = parse_typescript_file(Path("vanished.ts"), tmp_path)

        assert result.file_path == Path("vanished.ts")
        assert result.line_count == 0
        assert len(result.parse_errors) >= 1
        assert "FileNotFoundError" in result.parse_errors[0]

    def test_ts_stub_file_deleted(self, tmp_path: Path) -> None:
        """TS stub parser also handles missing file gracefully."""
        result = _parse_typescript_stub(Path("gone.tsx"), tmp_path)

        assert result.file_path == Path("gone.tsx")
        assert result.line_count == 0
        assert len(result.parse_errors) >= 1
        assert "FileNotFoundError" in result.parse_errors[0]

    def test_ts_valid_file_stub(self, tmp_path: Path) -> None:
        """Normal TS file via stub is unaffected by error handling."""
        (tmp_path / "app.ts").write_text('import { foo } from "./bar";\n', encoding="utf-8")
        result = _parse_typescript_stub(Path("app.ts"), tmp_path)

        assert result.file_path == Path("app.ts")
        assert result.parse_errors == []
        assert result.line_count == 1
