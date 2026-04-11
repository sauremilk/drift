"""Coverage tests for guard_clause_deficit and exception_contract_drift helpers."""

from __future__ import annotations

import ast
import textwrap

from drift.signals.exception_contract_drift import (
    _extract_exception_profile,
    _extract_functions_from_source,
)
from drift.signals.guard_clause_deficit import (
    _function_max_nesting,
    _has_guard,
    _max_nesting_depth,
    _references_param,
)


def _parse_func(src: str) -> ast.FunctionDef:
    tree = ast.parse(textwrap.dedent(src))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            return node
    raise ValueError("no function found")


def _parse_stmts(src: str) -> list[ast.stmt]:
    return ast.parse(textwrap.dedent(src)).body


# ── _extract_exception_profile ───────────────────────────────────


class TestExtractExceptionProfile:
    def test_raise_value_error(self):
        func = _parse_func("""\
        def validate(x):
            raise ValueError("bad")
        """)
        profile = _extract_exception_profile(func)
        assert "ValueError" in profile["raise_types"]

    def test_bare_except(self):
        func = _parse_func("""\
        def handle():
            try:
                pass
            except:
                pass
        """)
        profile = _extract_exception_profile(func)
        assert profile["has_bare_except"] is True

    def test_bare_raise(self):
        func = _parse_func("""\
        def reraise():
            try:
                pass
            except Exception:
                raise
        """)
        profile = _extract_exception_profile(func)
        assert profile["has_bare_raise"] is True

    def test_handler_types(self):
        func = _parse_func("""\
        def handle():
            try:
                pass
            except (ValueError, TypeError):
                pass
        """)
        profile = _extract_exception_profile(func)
        assert "ValueError" in profile["handler_types"]
        assert "TypeError" in profile["handler_types"]

    def test_no_exceptions(self):
        func = _parse_func("""\
        def clean():
            return 42
        """)
        profile = _extract_exception_profile(func)
        assert profile["raise_types"] == []
        assert profile["handler_types"] == []
        assert profile["has_bare_except"] is False
        assert profile["has_bare_raise"] is False


# ── _extract_functions_from_source ───────────────────────────────


class TestExtractFunctionsFromSource:
    def test_two_public_functions(self):
        src = textwrap.dedent("""\
        def foo(x, y):
            raise ValueError

        def bar(z):
            pass
        """)
        result = _extract_functions_from_source(src)
        assert "foo" in result
        assert "bar" in result
        assert result["foo"]["param_count"] == 2

    def test_private_skipped(self):
        src = "def _helper(): pass"
        result = _extract_functions_from_source(src)
        assert "_helper" not in result

    def test_syntax_error(self):
        result = _extract_functions_from_source("def (broken")
        assert result == {}


# ── _references_param ────────────────────────────────────────────


class TestReferencesParam:
    def test_name_match(self):
        node = ast.parse("x > 0").body[0].value  # type: ignore[attr-defined]
        assert _references_param(node, {"x"}) is True

    def test_no_match(self):
        node = ast.parse("y > 0").body[0].value  # type: ignore[attr-defined]
        assert _references_param(node, {"x"}) is False


# ── _has_guard ───────────────────────────────────────────────────


class TestHasGuard:
    def test_if_raise(self):
        stmts = _parse_stmts("if x: raise ValueError")
        assert _has_guard(stmts[0], {"x"}) is True

    def test_if_with_else(self):
        stmts = _parse_stmts("if x:\n    raise ValueError\nelse:\n    pass")
        # Has else branch — not a single-branch guard
        assert _has_guard(stmts[0], {"x"}) is False

    def test_assert(self):
        stmts = _parse_stmts("assert x is not None")
        assert _has_guard(stmts[0], {"x"}) is True

    def test_no_guard(self):
        stmts = _parse_stmts("y = 1")
        assert _has_guard(stmts[0], {"x"}) is False


# ── _max_nesting_depth ───────────────────────────────────────────


class TestMaxNestingDepth:
    def test_flat(self):
        stmts = _parse_stmts("x = 1\ny = 2")
        assert _max_nesting_depth(stmts) == 0

    def test_single_if(self):
        stmts = _parse_stmts("if True:\n    x = 1")
        assert _max_nesting_depth(stmts) == 1

    def test_nested(self):
        src = """\
        if True:
            for i in range(10):
                if i > 5:
                    pass
        """
        stmts = _parse_stmts(src)
        assert _max_nesting_depth(stmts) == 3

    def test_nested_function_not_counted(self):
        src = """\
        def outer():
            def inner():
                if True:
                    pass
        """
        stmts = _parse_stmts(src)
        # Nested function body not counted against parent
        assert _max_nesting_depth(stmts) == 0


# ── _function_max_nesting ────────────────────────────────────────


class TestFunctionMaxNesting:
    def test_simple(self):
        src = "def f():\n    if True:\n        for x in y:\n            pass"
        assert _function_max_nesting(src) == 2

    def test_flat(self):
        src = "def f():\n    return 42"
        assert _function_max_nesting(src) == 0

    def test_syntax_error(self):
        assert _function_max_nesting("def (broken") is None

    def test_no_function(self):
        assert _function_max_nesting("x = 1") is None
