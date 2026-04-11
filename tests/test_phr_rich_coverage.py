"""Coverage tests for phantom_reference helpers and rich_output helpers."""

from __future__ import annotations

import ast
import textwrap
from pathlib import Path

import pytest
from rich.text import Text

from drift.output.rich_output import _score_bar, _sparkline
from drift.signals.phantom_reference import (
    _collect_type_checking_import_ids,
    _is_in_try_except_import_error,
    _path_to_module,
)

# ── _is_in_try_except_import_error ───────────────────────────────


class TestIsInTryExceptImportError:
    def test_guarded_import(self):
        src = textwrap.dedent("""\
        try:
            import optional_lib
        except ImportError:
            optional_lib = None
        """)
        tree = ast.parse(src)
        # Find the import node in the try body
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert _is_in_try_except_import_error(node, tree) is True
                return
        pytest.fail("no import node found")

    def test_unguarded_import(self):
        src = "import os"
        tree = ast.parse(src)
        import_node = tree.body[0]
        assert _is_in_try_except_import_error(import_node, tree) is False

    def test_bare_except_guard(self):
        src = textwrap.dedent("""\
        try:
            import foo
        except:
            foo = None
        """)
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert _is_in_try_except_import_error(node, tree) is True
                return

    def test_wrong_exception_type(self):
        src = textwrap.dedent("""\
        try:
            import foo
        except ValueError:
            foo = None
        """)
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert _is_in_try_except_import_error(node, tree) is False
                return

    def test_module_not_found_error(self):
        src = textwrap.dedent("""\
        try:
            import foo
        except ModuleNotFoundError:
            foo = None
        """)
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert _is_in_try_except_import_error(node, tree) is True
                return


# ── _collect_type_checking_import_ids ────────────────────────────


class TestCollectTypeCheckingImportIds:
    def test_type_checking_block(self):
        src = textwrap.dedent("""\
        from __future__ import annotations
        TYPE_CHECKING = False
        if TYPE_CHECKING:
            import typing
        """)
        tree = ast.parse(src)
        ids = _collect_type_checking_import_ids(tree)
        assert len(ids) >= 1

    def test_no_type_checking(self):
        src = "import os"
        tree = ast.parse(src)
        ids = _collect_type_checking_import_ids(tree)
        assert len(ids) == 0


# ── _path_to_module ──────────────────────────────────────────────


class TestPathToModule:
    def test_simple(self):
        assert _path_to_module(Path("pkg/module.py")) == "pkg.module"

    def test_init(self):
        assert _path_to_module(Path("pkg/__init__.py")) == "pkg"

    def test_strip_src(self):
        assert _path_to_module(Path("src/pkg/module.py")) == "pkg.module"

    def test_strip_lib(self):
        assert _path_to_module(Path("lib/pkg/module.py")) == "pkg.module"

    def test_empty(self):
        assert _path_to_module(Path("")) == ""


# ── _score_bar ───────────────────────────────────────────────────


class TestScoreBar:
    def test_low_green(self):
        bar = _score_bar(0.2)
        assert isinstance(bar, Text)
        plain = bar.plain
        assert "0.20" in plain

    def test_mid_yellow(self):
        bar = _score_bar(0.5)
        assert "0.50" in bar.plain

    def test_high_red(self):
        bar = _score_bar(0.9)
        assert "0.90" in bar.plain

    def test_zero(self):
        bar = _score_bar(0.0)
        assert "0.00" in bar.plain

    def test_custom_width(self):
        bar = _score_bar(0.5, width=10)
        assert isinstance(bar, Text)


# ── _sparkline ───────────────────────────────────────────────────


class TestSparkline:
    def test_empty(self):
        assert _sparkline([]) == ""

    def test_single(self):
        result = _sparkline([0.5])
        assert len(result) == 1

    def test_ascending(self):
        result = _sparkline([0.0, 0.5, 1.0])
        assert len(result) == 3
        # First should be lowest char, last highest
        assert result[0] < result[-1]

    def test_flat(self):
        result = _sparkline([0.5, 0.5, 0.5])
        # All same value
        assert len(set(result)) == 1

    def test_width_clamp(self):
        values = list(range(50))
        result = _sparkline([float(v) for v in values], width=10)
        assert len(result) == 10
