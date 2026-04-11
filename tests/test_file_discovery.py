"""Tests for file discovery: glob matching, exclude patterns, edge cases.

Targeted gaps (file_discovery.py at 73%):
- _matches_any with **/pattern/** recursive directory patterns
- discover_files: symlinks skipped, oversized files skipped, deduplication,
  unsupported language skipping, language detection
- Glob patterns that match no files → empty result

These tests matter because file discovery bugs cause silent omissions —
files that should be analysed are skipped without warning.
"""

import json

import pytest

from drift.ingestion.file_discovery import (
    _matches_any,
    _prepare_patterns,
    detect_language,
    discover_files,
)

# ── _matches_any: recursive directory patterns ────────────────────────────


class TestMatchesAny:
    def test_prepare_patterns_is_cached(self):
        key = ("**/venv/**", "**/build/**")
        first = _prepare_patterns(key)
        second = _prepare_patterns(key)
        assert first is second

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

    @pytest.mark.parametrize("env_dir", [".conda", ".env", ".nox", ".tox", ".pixi"])
    def test_exclude_environment_directories(self, tmp_path, env_dir):
        (tmp_path / "app.py").write_text("x = 1")
        env_lib = tmp_path / env_dir / "lib"
        env_lib.mkdir(parents=True)
        (env_lib / "internal.py").write_text("hidden = True")

        files = discover_files(tmp_path)
        paths = {f.path.as_posix() for f in files}

        assert "app.py" in paths
        assert all(not p.startswith(f"{env_dir}/") for p in paths)

    def test_exclude_tmp_launch_virtualenv_directories(self, tmp_path):
        (tmp_path / "app.py").write_text("x = 1")
        tmp_venv_lib = tmp_path / ".tmp_launch_venv_local" / "Lib" / "site-packages" / "pkg"
        tmp_venv_lib.mkdir(parents=True)
        (tmp_venv_lib / "vendored.py").write_text("hidden = True")

        files = discover_files(tmp_path)
        paths = {f.path.as_posix() for f in files}

        assert "app.py" in paths
        assert all(not p.startswith(".tmp_launch_venv_local/") for p in paths)

    def test_exclude_site_packages(self, tmp_path):
        (tmp_path / "app.py").write_text("x = 1")
        sp = tmp_path / "lib" / "python3.11" / "site-packages" / "pkg"
        sp.mkdir(parents=True)
        (sp / "mod.py").write_text("vendored = True")

        files = discover_files(tmp_path)
        paths = {f.path.as_posix() for f in files}

        assert "app.py" in paths
        assert all("site-packages" not in p for p in paths)

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

    def test_symlinks_skipped(self, tmp_path):
        """Symlinked files should be excluded to prevent loops."""
        real = tmp_path / "real.py"
        real.write_text("x = 1")
        link = tmp_path / "link.py"
        try:
            link.symlink_to(real)
        except (OSError, NotImplementedError):
            pytest.skip(
                "Symlink creation not available in this environment"
                " (requires elevated privileges on Windows)"
            )
        files = discover_files(tmp_path)
        names = {f.path.name for f in files}
        assert "real.py" in names
        assert "link.py" not in names

    def test_deduplication_with_overlapping_patterns(self, tmp_path):
        """Multiple include patterns matching same file → no duplicates."""
        (tmp_path / "app.py").write_text("x = 1")
        files = discover_files(tmp_path, include=["**/*.py", "*.py"])
        assert len(files) == 1

    def test_max_discovery_files_caps_result(self, tmp_path):
        for i in range(5):
            (tmp_path / f"f{i}.py").write_text("x = 1")

        files = discover_files(tmp_path, max_files=3)

        assert len(files) == 3

    def test_default_include_adds_ts_when_supported(self, tmp_path, monkeypatch):
        (tmp_path / "app.py").write_text("x = 1")
        (tmp_path / "app.ts").write_text("export const x = 1;")

        monkeypatch.setattr(
            "drift.ingestion.file_discovery._detect_supported_languages",
            lambda: {"python", "typescript", "tsx", "javascript", "jsx"},
        )

        files = discover_files(tmp_path)
        paths = {f.path.as_posix() for f in files}
        assert "app.py" in paths
        assert "app.ts" in paths

    def test_supported_languages_detected_once(self, tmp_path, monkeypatch):
        (tmp_path / "app.py").write_text("x = 1")

        calls = {"count": 0}

        def _fake_supported() -> set[str]:
            calls["count"] += 1
            return {"python"}

        monkeypatch.setattr(
            "drift.ingestion.file_discovery._detect_supported_languages",
            _fake_supported,
        )

        files = discover_files(tmp_path)

        assert len(files) == 1
        assert calls["count"] == 1

    def test_discovery_cache_hit_skips_glob(self, tmp_path, monkeypatch):
        (tmp_path / "a.py").write_text("x = 1")
        monkeypatch.setattr(
            "drift.ingestion.file_discovery._current_git_head",
            lambda _repo: "head-a",
        )

        first = discover_files(tmp_path, cache_dir=".drift-cache")
        assert {f.path.as_posix() for f in first} == {"a.py"}

        def _fail_glob(self, _pattern):
            raise AssertionError("glob should not run on discovery cache hit")

        monkeypatch.setattr("pathlib.Path.glob", _fail_glob)
        second = discover_files(tmp_path, cache_dir=".drift-cache")
        assert {f.path.as_posix() for f in second} == {"a.py"}

    def test_discovery_cache_invalidates_on_head_change(self, tmp_path, monkeypatch):
        (tmp_path / "a.py").write_text("x = 1")
        heads = iter(["head-a", "head-b"])
        monkeypatch.setattr(
            "drift.ingestion.file_discovery._current_git_head",
            lambda _repo: next(heads),
        )

        first = discover_files(tmp_path, cache_dir=".drift-cache")
        assert {f.path.as_posix() for f in first} == {"a.py"}

        (tmp_path / "b.py").write_text("y = 2")
        second = discover_files(tmp_path, cache_dir=".drift-cache")
        assert {f.path.as_posix() for f in second} == {"a.py", "b.py"}

    def test_discovery_cache_recovers_from_corrupt_manifest(self, tmp_path, monkeypatch):
        (tmp_path / "a.py").write_text("x = 1")
        cache_dir = tmp_path / ".drift-cache"
        cache_dir.mkdir()
        manifest = cache_dir / "file_discovery_manifest.json"
        manifest.write_text("{invalid json", encoding="utf-8")

        monkeypatch.setattr(
            "drift.ingestion.file_discovery._current_git_head",
            lambda _repo: "head-a",
        )

        files = discover_files(tmp_path, cache_dir=".drift-cache")
        assert {f.path.as_posix() for f in files} == {"a.py"}
        loaded = json.loads(manifest.read_text(encoding="utf-8"))
        assert loaded["version"] == 1

    def test_discovery_cache_uses_mtime_fallback_without_git(self, tmp_path, monkeypatch):
        (tmp_path / "a.py").write_text("x = 1")
        monkeypatch.setattr(
            "drift.ingestion.file_discovery._current_git_head",
            lambda _repo: None,
        )

        first = discover_files(tmp_path, cache_dir=".drift-cache")
        assert {f.path.as_posix() for f in first} == {"a.py"}

        (tmp_path / "b.py").write_text("y = 2")
        second = discover_files(tmp_path, cache_dir=".drift-cache")
        assert {f.path.as_posix() for f in second} == {"a.py", "b.py"}
