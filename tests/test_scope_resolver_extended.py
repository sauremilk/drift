"""Extended coverage tests for scope_resolver — _module_to_path_candidates,
_collect_scope_files, expand_scope_imports, _collect_symbols edge cases."""

from __future__ import annotations

from pathlib import Path

from drift.scope_resolver import (
    ResolvedScope,
    _collect_scope_files,
    _collect_symbols,
    _module_to_path_candidates,
    expand_scope_imports,
)

# ---------------------------------------------------------------------------
# _module_to_path_candidates
# ---------------------------------------------------------------------------


class TestModuleToPathCandidates:
    def test_simple_module(self):
        result = _module_to_path_candidates("foo.bar")
        assert "foo/bar.py" in result
        assert "foo/bar/__init__.py" in result

    def test_single_component(self):
        result = _module_to_path_candidates("utils")
        assert "utils.py" in result
        assert "utils/__init__.py" in result

    def test_deep_module(self):
        result = _module_to_path_candidates("a.b.c.d")
        assert "a/b/c/d.py" in result
        assert "a/b/c/d/__init__.py" in result


# ---------------------------------------------------------------------------
# _collect_scope_files
# ---------------------------------------------------------------------------


class TestCollectScopeFiles:
    def test_empty_paths(self, tmp_path: Path):
        assert _collect_scope_files([], tmp_path) == []

    def test_single_file(self, tmp_path: Path):
        f = tmp_path / "src" / "a.py"
        f.parent.mkdir(parents=True)
        f.write_text("x = 1", encoding="utf-8")
        result = _collect_scope_files(["src/a.py"], tmp_path)
        assert len(result) == 1
        assert result[0].name == "a.py"

    def test_directory(self, tmp_path: Path):
        d = tmp_path / "pkg"
        d.mkdir()
        (d / "mod.py").write_text("x = 1", encoding="utf-8")
        (d / "sub.py").write_text("y = 2", encoding="utf-8")
        result = _collect_scope_files(["pkg"], tmp_path)
        assert len(result) == 2

    def test_nonexistent_path(self, tmp_path: Path):
        result = _collect_scope_files(["no/such/path"], tmp_path)
        assert result == []

    def test_non_py_file_skipped(self, tmp_path: Path):
        f = tmp_path / "src" / "readme.md"
        f.parent.mkdir(parents=True)
        f.write_text("# readme", encoding="utf-8")
        result = _collect_scope_files(["src/readme.md"], tmp_path)
        assert result == []


# ---------------------------------------------------------------------------
# _collect_symbols edge cases
# ---------------------------------------------------------------------------


class TestCollectSymbolsEdge:
    def test_max_files_zero(self, tmp_path: Path):
        d = tmp_path / "pkg"
        d.mkdir()
        (d / "a.py").write_text("class Foo: pass", encoding="utf-8")
        result = _collect_symbols(tmp_path, max_files=0)
        assert result == {}

    def test_skips_root_level_files(self, tmp_path: Path):
        # Root-level files (rel_dir == ".") should be skipped
        (tmp_path / "root_mod.py").write_text("class RootClass: pass", encoding="utf-8")
        result = _collect_symbols(tmp_path)
        assert "rootclass" not in result

    def test_first_seen_wins(self, tmp_path: Path):
        d1 = tmp_path / "pkg1"
        d1.mkdir()
        (d1 / "a.py").write_text("class Shared: pass", encoding="utf-8")
        d2 = tmp_path / "pkg2"
        d2.mkdir()
        (d2 / "b.py").write_text("class Shared: pass", encoding="utf-8")
        result = _collect_symbols(tmp_path)
        # Just verify the key exists once
        assert "shared" in result


# ---------------------------------------------------------------------------
# expand_scope_imports
# ---------------------------------------------------------------------------


class TestExpandScopeImports:
    def test_empty_scope(self, tmp_path: Path):
        scope = ResolvedScope(paths=[], confidence=1.0, method="test")
        result = expand_scope_imports(scope, tmp_path)
        assert result == []

    def test_no_py_files(self, tmp_path: Path):
        d = tmp_path / "pkg"
        d.mkdir()
        scope = ResolvedScope(paths=["pkg"], confidence=1.0, method="test")
        result = expand_scope_imports(scope, tmp_path)
        assert result == []

    def test_resolves_import(self, tmp_path: Path):
        # Create importing module
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "main.py").write_text("from util.helpers import do_thing\n", encoding="utf-8")
        # Create the imported module
        util = tmp_path / "util"
        util.mkdir()
        (util / "helpers.py").write_text("def do_thing(): pass\n", encoding="utf-8")

        scope = ResolvedScope(paths=["pkg"], confidence=1.0, method="test")
        result = expand_scope_imports(scope, tmp_path)
        assert "util" in result

    def test_skips_root_level_imports(self, tmp_path: Path):
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "a.py").write_text("import os\n", encoding="utf-8")

        scope = ResolvedScope(paths=["pkg"], confidence=1.0, method="test")
        result = expand_scope_imports(scope, tmp_path)
        # os is a stdlib root-level import and doesn't resolve to a repo file
        assert result == []

    def test_no_duplicates_with_existing(self, tmp_path: Path):
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "a.py").write_text("from pkg.b import x\n", encoding="utf-8")
        (pkg / "b.py").write_text("x = 1\n", encoding="utf-8")

        scope = ResolvedScope(paths=["pkg"], confidence=1.0, method="test")
        result = expand_scope_imports(scope, tmp_path)
        # "pkg" is already in scope, should not be in result
        assert "pkg" not in result
