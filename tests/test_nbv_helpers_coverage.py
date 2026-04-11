"""Coverage tests for naming_contract_violation pure helpers:
_bare_name, _has_rejection_path, _has_raise, _has_create_path,
_has_bool_return, _has_try_except, _is_utility_context,
_looks_like_comparison_semantics, _snake_to_camel_prefix,
_match_rule, _contract_suggestion."""

from __future__ import annotations

import ast
import textwrap
from pathlib import Path

from drift.models import FunctionInfo
from drift.signals.naming_contract_violation import (
    _bare_name,
    _contract_suggestion,
    _has_bool_return,
    _has_create_path,
    _has_raise,
    _has_rejection_path,
    _has_try_except,
    _is_bool_like_return_type,
    _is_utility_context,
    _looks_like_comparison_semantics,
    _match_rule,
    _snake_to_camel_prefix,
)


def _parse(source: str) -> ast.Module:
    return ast.parse(textwrap.dedent(source))


def _fn_info(return_type: str | None = None) -> FunctionInfo:
    return FunctionInfo(
        name="test_fn",
        file_path=Path("a.py"),
        start_line=1,
        end_line=3,
        language="python",
        complexity=1,
        loc=3,
        parameters=[],
        return_type=return_type,
        decorators=[],
        has_docstring=False,
        body_hash="abc",
        ast_fingerprint="def",
        is_exported=True,
    )


# -- _bare_name ---------------------------------------------------------------


class TestBareName:
    def test_no_dot(self):
        assert _bare_name("method") == "method"

    def test_single_dot(self):
        assert _bare_name("Class.method") == "method"

    def test_multi_dot(self):
        assert _bare_name("A.B.method") == "method"


# -- _has_rejection_path -------------------------------------------------------


class TestHasRejectionPath:
    def test_raise(self):
        tree = _parse("raise ValueError('bad')")
        assert _has_rejection_path(tree) is True

    def test_return_false(self):
        tree = _parse("return False")
        assert _has_rejection_path(tree) is True

    def test_return_none(self):
        tree = _parse("return None")
        assert _has_rejection_path(tree) is True

    def test_return_true_only(self):
        tree = _parse("return True")
        assert _has_rejection_path(tree) is False

    def test_empty_body(self):
        tree = _parse("pass")
        assert _has_rejection_path(tree) is False


# -- _has_raise ----------------------------------------------------------------


class TestHasRaise:
    def test_with_raise(self):
        assert _has_raise(_parse("raise RuntimeError")) is True

    def test_no_raise(self):
        assert _has_raise(_parse("x = 1")) is False


# -- _has_create_path ----------------------------------------------------------


class TestHasCreatePath:
    def test_if_then_assign(self):
        src = """\
        def get_or_create():
            if cond:
                obj = lookup()
            return create()
        """
        assert _has_create_path(_parse(src)) is True

    def test_if_else(self):
        src = """\
        def get_or_create():
            if found:
                pass
            else:
                obj = create()
        """
        assert _has_create_path(_parse(src)) is True

    def test_no_conditional(self):
        src = """\
        def get_or_create():
            return do_stuff()
        """
        assert _has_create_path(_parse(src)) is False


# -- _has_bool_return ----------------------------------------------------------


class TestHasBoolReturn:
    def test_annotation_bool(self):
        fn = _fn_info(return_type="bool")
        tree = _parse("pass")
        assert _has_bool_return(tree, fn) is True

    def test_annotation_builtins_bool(self):
        fn = _fn_info(return_type="builtins.bool")
        assert _has_bool_return(_parse("pass"), fn) is True

    def test_all_bool_returns(self):
        src = """\
        def is_valid():
            if cond:
                return True
            return False
        """
        fn = _fn_info(return_type=None)
        assert _has_bool_return(_parse(src), fn) is True

    def test_mixed_returns(self):
        src = """\
        def is_valid():
            if cond:
                return 42
            return True
        """
        fn = _fn_info(return_type=None)
        assert _has_bool_return(_parse(src), fn) is False

    def test_no_returns(self):
        src = """\
        def is_valid():
            pass
        """
        fn = _fn_info(return_type=None)
        assert _has_bool_return(_parse(src), fn) is False


class TestIsBoolLikeReturnType:
    def test_plain_bool_types(self):
        assert _is_bool_like_return_type("bool") is True
        assert _is_bool_like_return_type("builtins.bool") is True
        assert _is_bool_like_return_type("boolean") is True

    def test_async_wrapper_bool_types(self):
        assert _is_bool_like_return_type("Promise<boolean>") is True
        assert _is_bool_like_return_type("PromiseLike<boolean>") is True
        assert _is_bool_like_return_type("Observable<boolean>") is True

    def test_nested_async_wrapper_bool_types(self):
        assert _is_bool_like_return_type("Promise<PromiseLike<boolean>>") is True

    def test_non_bool_wrapped_types(self):
        assert _is_bool_like_return_type("Promise<string>") is False
        assert _is_bool_like_return_type("Observable<number>") is False


# -- _has_try_except -----------------------------------------------------------


class TestHasTryExcept:
    def test_with_try(self):
        src = """\
        try:
            x = 1
        except Exception:
            pass
        """
        assert _has_try_except(_parse(src)) is True

    def test_without_try(self):
        assert _has_try_except(_parse("x = 1")) is False


# -- _is_utility_context -------------------------------------------------------


class TestIsUtilityContext:
    def test_utils_dir(self):
        assert _is_utility_context(Path("src/utils/helper.py")) is True

    def test_helper_stem(self):
        assert _is_utility_context(Path("src/core/helpers.py")) is True

    def test_common_dir(self):
        assert _is_utility_context(Path("common/base.py")) is True

    def test_non_utility(self):
        assert _is_utility_context(Path("src/core/main.py")) is False


# -- _looks_like_comparison_semantics -----------------------------------------


class TestLooksLikeComparisonSemantics:
    def test_with_compare(self):
        src = "x > 3"
        assert _looks_like_comparison_semantics(_parse(src), src) is True

    def test_with_isinstance(self):
        src = "isinstance(x, int)"
        assert _looks_like_comparison_semantics(_parse(src), src) is True

    def test_is_none(self):
        src = "x is None"
        assert _looks_like_comparison_semantics(_parse(src), src) is True

    def test_plain_assignment(self):
        src = "x = 1"
        assert _looks_like_comparison_semantics(_parse(src), src) is False


# -- _snake_to_camel_prefix ---------------------------------------------------


class TestSnakeToCamelPrefix:
    def test_single_word(self):
        assert _snake_to_camel_prefix("get_") == "get"

    def test_multi_word(self):
        assert _snake_to_camel_prefix("get_or_create_") == "getOrCreate"

    def test_two_parts(self):
        assert _snake_to_camel_prefix("validate_") == "validate"


# -- _match_rule ---------------------------------------------------------------


class TestMatchRule:
    def test_validate_prefix(self):
        result = _match_rule("validate_email")
        assert result is not None
        assert result[0] == "validate_"

    def test_check_prefix(self):
        result = _match_rule("check_access")
        assert result is not None
        assert result[0] == "check_"

    def test_is_prefix(self):
        result = _match_rule("is_valid")
        assert result is not None
        assert result[0] == "is_"

    def test_has_prefix(self):
        result = _match_rule("has_permission")
        assert result is not None
        assert result[0] == "has_"

    def test_ensure_prefix(self):
        result = _match_rule("ensure_connected")
        assert result is not None
        assert result[0] == "ensure_"

    def test_get_or_create_prefix(self):
        result = _match_rule("get_or_create_user")
        assert result is not None
        assert result[0] == "get_or_create_"

    def test_try_prefix(self):
        result = _match_rule("try_connect")
        assert result is not None
        assert result[0] == "try_"

    def test_camel_case_match(self):
        result = _match_rule("validateEmail")
        assert result is not None
        assert result[0] == "validate_"

    def test_no_match(self):
        assert _match_rule("do_stuff") is None

    def test_camel_case_needs_upper_after(self):
        # "validate" alone should not match camelCase rule
        assert _match_rule("validate") is None


# -- _contract_suggestion -------------------------------------------------------


class TestContractSuggestion:
    def test_validate(self):
        s = _contract_suggestion("validate_", "validate_email")
        assert "rejection" in s or "rename" in s

    def test_check(self):
        s = _contract_suggestion("check_", "check_email")
        assert "rejection" in s

    def test_ensure(self):
        s = _contract_suggestion("ensure_", "ensure_conn")
        assert "raise" in s

    def test_get_or_create(self):
        s = _contract_suggestion("get_or_create_", "get_or_create_user")
        assert "create" in s

    def test_is(self):
        s = _contract_suggestion("is_", "is_valid")
        assert "bool" in s

    def test_has(self):
        s = _contract_suggestion("has_", "has_perm")
        assert "bool" in s

    def test_try(self):
        s = _contract_suggestion("try_", "try_conn")
        assert "try" in s

    def test_fallback(self):
        s = _contract_suggestion("unknown_", "unknown_fn")
        assert "unknown_" in s
