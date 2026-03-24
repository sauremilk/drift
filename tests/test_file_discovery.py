"""Tests for file discovery: glob matching, exclude patterns, edge cases.

Targeted gaps (file_discovery.py at 73%):
- _matches_any with **/pattern/** recursive directory patterns
- discover_files: symlinks skipped, oversized files skipped, deduplication,
  unsupported language skipping, language detection
- Glob patterns that match no files → empty result

These tests matter because file discovery bugs cause silent omissions —
files that should be analysed are skipped without warning.
"""

import os

import pytest

from drift.ingestion.file_discovery import (
    _matches_any,
    detect_language,
    discover_files,
)

# ── _matches_any: recursive directory patterns ────────────────────────────


class TestMatchesAny:
    def test_exact_match(self):
        assert _matches_any("__pycache__/foo.pyc", ["__pycache__/*"]) is True

    def test_recursive_dir_pattern(self):
        """**/dirname/** should match paths containing that directory."""
        assert _matches_any("src/venv/lib/site.py", ["**/venv/**"]) is True

    def test_recursive_dir_deeply_nested(self):
        assert _matches_any("a/b/c/node_modules/d/e.js", ["**/node_modules/**"]) is True

    def test_recursive_dir_not_matching(self):
        assert _matches_any("src/app/main.py", ["**/venv/**"]) is False

    def test_wildcard_extension_pattern(self):
        assert _matches_any("src/data.egg-info/top.txt", ["**/*.egg-info/**"]) is True

    def test_empty_patterns_no_match(self):
        assert _matches_any("any/path.py", []) is False

    def test_fnmatch_star_no_dir_separator(self):
        """Standard fnmatch * does not cross directory boundaries."""
        assert _matches_any("a/b/c.py", ["*.py"]) is False
        assert _matches_any("c.py", ["*.py"]) is True

    def test_multiple_patterns_first_matches(self):
        patterns = ["**/venv/**", "**/build/**"]
        assert _matches_any("venv/lib/a.py", patterns) is True

    def test_multiple_patterns_second_matches(self):
        patterns = ["**/venv/**", "**/build/**"]
        assert _matches_any("build/output/x.py", patterns) is True


# ── detect_language ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("suffix", "expected"),
    [
        (".py", "python"),
        (".ts", "typescript"),
        (".tsx", "tsx"),
        (".js", "javascript"),
        (".jsx", "jsx"),
        (".rs", None),
        (".go", None),
        ("", None),
    ],
)
def test_detect_language(suffix, expected, tmp_path):
    p = tmp_path / f"file{suffix}"
    assert detect_language(p) == expected


def test_detect_language_case_insensitive(tmp_path):
    p = tmp_path / "FILE.PY"
    assert detect_language(p) == "python"


# ── discover_files: integration with filesystem ──────────────────────────


class TestDiscoverFiles:
    def test_basic_discovery(self, tmp_path):
        (tmp_path / "main.py").write_text("x = 1")
        (tmp_path / "lib.py").write_text("y = 2")
        files = discover_files(tmp_path)
        assert len(files) == 2
        names = {f.path.name for f in files}
        assert names == {"main.py", "lib.py"}

    def test_exclude_venv(self, tmp_path):
        (tmp_path / "app.py").write_text("x = 1")
        venv = tmp_path / "venv" / "lib"
        venv.mkdir(parents=True)
        (venv / "internal.py").write_text("hidden = True")
        files = discover_files(tmp_path)
        paths = {f.path.as_posix() for f in files}
        assert "app.py" in paths
        assert all("venv" not in p for p in paths)

    def test_exclude_pycache(self, tmp_path):
        (tmp_path / "app.py").write_text("x = 1")
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        (cache / "app.cpython-311.pyc").write_text("")
        files = discover_files(tmp_path)
        assert all("__pycache__" not in f.path.as_posix() for f in files)

    def test_empty_directory(self, tmp_path):
        files = discover_files(tmp_path)
        assert files == []

    def test_non_python_files_ignored(self, tmp_path):
        (tmp_path / "readme.md").write_text("# Hello")
        (tmp_path / "data.csv").write_text("a,b,c")
        (tmp_path / "app.py").write_text("x = 1")
        files = discover_files(tmp_path)
        assert len(files) == 1
        assert files[0].path.name == "app.py"

    def test_custom_include_pattern(self, tmp_path):
        sub = tmp_path / "src"
        sub.mkdir()
        (sub / "mod.py").write_text("x = 1")
        (tmp_path / "root.py").write_text("y = 1")
        files = discover_files(tmp_path, include=["src/**/*.py"])
        assert len(files) == 1
        assert "mod.py" in files[0].path.as_posix()

    def test_oversized_file_skipped(self, tmp_path):
        """Files > 5 MB should be skipped."""
        big = tmp_path / "huge.py"
        # Write a 5.1 MB file
        big.write_bytes(b"x = 1\n" * 900_000)
        (tmp_path / "small.py").write_text("y = 1")
        files = discover_files(tmp_path)
        names = {f.path.name for f in files}
        assert "small.py" in names
        assert "huge.py" not in names

    def test_sorted_output(self, tmp_path):
        for name in ("z.py", "a.py", "m.py"):
            (tmp_path / name).write_text("x = 1")
        files = discover_files(tmp_path)
        paths = [f.path.as_posix() for f in files]
        assert paths == sorted(paths)

    def test_file_info_fields_populated(self, tmp_path):
        (tmp_path / "mod.py").write_text("x = 1\ny = 2\nz = 3\n")
        files = discover_files(tmp_path)
        assert len(files) == 1
        fi = files[0]
        assert fi.language == "python"
        assert fi.size_bytes > 0
        assert fi.line_count >= 0  # heuristic estimate

    @pytest.mark.skipif(os.name == "nt", reason="Symlinks require elevated privileges on Windows")
    def test_symlinks_skipped(self, tmp_path):
        """Symlinked files should be excluded to prevent loops."""
        real = tmp_path / "real.py"
        real.write_text("x = 1")
        link = tmp_path / "link.py"
        link.symlink_to(real)
        files = discover_files(tmp_path)
        names = {f.path.name for f in files}
        assert "real.py" in names
        assert "link.py" not in names

    def test_deduplication_with_overlapping_patterns(self, tmp_path):
        """Multiple include patterns matching same file → no duplicates."""
        (tmp_path / "app.py").write_text("x = 1")
        files = discover_files(tmp_path, include=["**/*.py", "*.py"])
        assert len(files) == 1
