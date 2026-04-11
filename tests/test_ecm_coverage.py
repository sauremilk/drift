"""Additional coverage tests for ExceptionContractDrift signal helpers."""

from __future__ import annotations

import ast
import textwrap

from drift.signals.exception_contract_drift import (
    _effective_candidate_limit,
    _extract_exception_profile,
    _extract_functions_from_source,
    _profiles_diverged,
)

# ---------------------------------------------------------------------------
# _extract_exception_profile
# ---------------------------------------------------------------------------


class TestExceptionProfile:
    def test_bare_raise(self):
        source = textwrap.dedent("""\
            def process(x):
                if not x:
                    raise
        """)
        tree = ast.parse(source)
        func = tree.body[0]
        profile = _extract_exception_profile(func)
        assert profile["has_bare_raise"] is True
        assert profile["raise_types"] == []

    def test_typed_raise(self):
        source = textwrap.dedent("""\
            def process(x):
                raise ValueError("bad value")
        """)
        tree = ast.parse(source)
        func = tree.body[0]
        profile = _extract_exception_profile(func)
        assert "ValueError" in profile["raise_types"]
        assert profile["has_bare_raise"] is False

    def test_name_raise_without_call(self):
        source = textwrap.dedent("""\
            def process(x):
                err = ValueError("bad")
                raise err
        """)
        tree = ast.parse(source)
        func = tree.body[0]
        profile = _extract_exception_profile(func)
        assert "err" in profile["raise_types"]

    def test_bare_except_handler(self):
        source = textwrap.dedent("""\
            def process(x):
                try:
                    pass
                except:
                    pass
        """)
        tree = ast.parse(source)
        func = tree.body[0]
        profile = _extract_exception_profile(func)
        assert profile["has_bare_except"] is True

    def test_typed_except_handler(self):
        source = textwrap.dedent("""\
            def process(x):
                try:
                    pass
                except (ValueError, TypeError):
                    pass
        """)
        tree = ast.parse(source)
        func = tree.body[0]
        profile = _extract_exception_profile(func)
        assert "ValueError" in profile["handler_types"]
        assert "TypeError" in profile["handler_types"]

    def test_no_exceptions(self):
        source = textwrap.dedent("""\
            def process(x):
                return x + 1
        """)
        tree = ast.parse(source)
        func = tree.body[0]
        profile = _extract_exception_profile(func)
        assert profile["raise_types"] == []
        assert profile["handler_types"] == []
        assert profile["has_bare_except"] is False
        assert profile["has_bare_raise"] is False


# ---------------------------------------------------------------------------
# _extract_functions_from_source
# ---------------------------------------------------------------------------


class TestExtractFunctionsFromSource:
    def test_public_functions_extracted(self):
        source = textwrap.dedent("""\
            def process(data, config):
                raise ValueError("no")

            def _private():
                pass
        """)
        funcs = _extract_functions_from_source(source)
        assert "process" in funcs
        assert "_private" not in funcs
        assert funcs["process"]["param_count"] == 2

    def test_syntax_error_returns_empty(self):
        funcs = _extract_functions_from_source("def broken(")
        assert funcs == {}

    def test_async_functions_extracted(self):
        source = textwrap.dedent("""\
            async def fetch(url, timeout):
                raise IOError("fail")
        """)
        funcs = _extract_functions_from_source(source)
        assert "fetch" in funcs
        assert funcs["fetch"]["param_count"] == 2
        assert "IOError" in funcs["fetch"]["profile"]["raise_types"]


# ---------------------------------------------------------------------------
# _profiles_diverged
# ---------------------------------------------------------------------------


class TestProfilesDiverged:
    def test_identical_profiles(self):
        p = {
            "raise_types": ["ValueError"],
            "handler_types": [],
            "has_bare_except": False,
            "has_bare_raise": False,
        }
        assert _profiles_diverged(p, p.copy()) is False

    def test_raise_types_changed(self):
        old = {
            "raise_types": ["ValueError"],
            "handler_types": [],
            "has_bare_except": False,
            "has_bare_raise": False,
        }
        new = {
            "raise_types": ["TypeError"],
            "handler_types": [],
            "has_bare_except": False,
            "has_bare_raise": False,
        }
        assert _profiles_diverged(old, new) is True

    def test_handler_types_changed(self):
        old = {
            "raise_types": [],
            "handler_types": ["ValueError"],
            "has_bare_except": False,
            "has_bare_raise": False,
        }
        new = {
            "raise_types": [],
            "handler_types": ["TypeError"],
            "has_bare_except": False,
            "has_bare_raise": False,
        }
        assert _profiles_diverged(old, new) is True

    def test_bare_except_added(self):
        old = {
            "raise_types": [],
            "handler_types": [],
            "has_bare_except": False,
            "has_bare_raise": False,
        }
        new = {
            "raise_types": [],
            "handler_types": [],
            "has_bare_except": True,
            "has_bare_raise": False,
        }
        assert _profiles_diverged(old, new) is True

    def test_bare_raise_changed(self):
        old = {
            "raise_types": [],
            "handler_types": [],
            "has_bare_except": False,
            "has_bare_raise": False,
        }
        new = {
            "raise_types": [],
            "handler_types": [],
            "has_bare_except": False,
            "has_bare_raise": True,
        }
        assert _profiles_diverged(old, new) is True


# ---------------------------------------------------------------------------
# _effective_candidate_limit
# ---------------------------------------------------------------------------


class TestEffectiveCandidateLimit:
    def test_small_repo_returns_count(self):
        assert _effective_candidate_limit(10, 50) == 10

    def test_medium_repo_returns_configured(self):
        assert _effective_candidate_limit(100, 50) == 50

    def test_large_repo_adaptive(self):
        result = _effective_candidate_limit(6000, 50)
        assert result == 300  # min(300, 6000//20) = 300

    def test_very_large_repo(self):
        result = _effective_candidate_limit(10000, 50)
        assert result == min(10000, max(50, min(300, 10000 // 20)))
