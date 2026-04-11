"""Coverage tests for mutant_duplicates helpers:
_jaccard, _structural_similarity, _tokenize_name,
_name_token_similarity, _is_protocol_method_pair, _is_thin_wrapper."""

from __future__ import annotations

from pathlib import Path

from drift.models import FunctionInfo
from drift.signals.mutant_duplicates import (
    _is_protocol_method_pair,
    _is_thin_wrapper,
    _jaccard,
    _name_token_similarity,
    _structural_similarity,
    _tokenize_name,
)


def _fn(
    name: str = "func",
    loc: int = 10,
    ast_fingerprint: dict | None = None,
) -> FunctionInfo:
    return FunctionInfo(
        name=name,
        file_path=Path("a.py"),
        start_line=1,
        end_line=loc,
        language="python",
        complexity=1,
        loc=loc,
        parameters=[],
        return_type=None,
        decorators=[],
        has_docstring=False,
        body_hash="h",
        ast_fingerprint=ast_fingerprint or {},
        is_exported=True,
    )


# -- _jaccard ------------------------------------------------------------------


class TestJaccard:
    def test_identical(self):
        a = [("A", "B"), ("C",)]
        assert _jaccard(a, a) == 1.0

    def test_disjoint(self):
        a = [("A",)]
        b = [("B",)]
        assert _jaccard(a, b) == 0.0

    def test_partial_overlap(self):
        a = [("A",), ("B",)]
        b = [("A",), ("C",)]
        sim = _jaccard(a, b)
        assert 0.0 < sim < 1.0

    def test_both_empty(self):
        assert _jaccard([], []) == 1.0

    def test_one_empty(self):
        assert _jaccard([("A",)], []) == 0.0


# -- _structural_similarity ----------------------------------------------------


class TestStructuralSimilarity:
    def test_none_input(self):
        assert _structural_similarity(None, [("A",)]) == 0.0

    def test_empty_input(self):
        assert _structural_similarity([], [("A",)]) == 0.0

    def test_identical(self):
        a = [("A", "B"), ("C",)]
        assert _structural_similarity(a, a) == 1.0

    def test_size_ratio_early_exit(self):
        a = [("A",)]
        b = [("A",), ("B",), ("C",), ("D",)]
        sim = _structural_similarity(a, b)
        assert sim == 0.25  # 1/4

    def test_normal_comparison(self):
        a = [("A",), ("B",), ("C",)]
        b = [("A",), ("B",), ("D",)]
        sim = _structural_similarity(a, b)
        assert 0.0 < sim < 1.0


# -- _tokenize_name ------------------------------------------------------------


class TestTokenizeName:
    def test_snake_case(self):
        assert _tokenize_name("get_user_name") == {"get", "user", "name"}

    def test_camel_case(self):
        assert _tokenize_name("getUserName") == {"get", "user", "name"}

    def test_class_prefix(self):
        tokens = _tokenize_name("MyClass.get_data")
        assert "get" in tokens
        assert "data" in tokens

    def test_single_word(self):
        assert _tokenize_name("run") == {"run"}


# -- _name_token_similarity ----------------------------------------------------


class TestNameTokenSimilarity:
    def test_identical(self):
        assert _name_token_similarity("get_user", "get_user") == 1.0

    def test_different(self):
        assert _name_token_similarity("get_user", "set_role") == 0.0

    def test_partial(self):
        sim = _name_token_similarity("get_user_name", "get_user_id")
        assert 0.0 < sim < 1.0

    def test_both_empty(self):
        assert _name_token_similarity("", "") == 1.0


# -- _is_protocol_method_pair -------------------------------------------------


class TestIsProtocolMethodPair:
    def test_same_method_different_classes(self):
        a = _fn(name="ClassA.serialize")
        b = _fn(name="ClassB.serialize")
        assert _is_protocol_method_pair(a, b) is True

    def test_same_class(self):
        a = _fn(name="ClassA.serialize")
        b = _fn(name="ClassA.serialize")
        assert _is_protocol_method_pair(a, b) is False

    def test_different_method_names(self):
        a = _fn(name="ClassA.serialize")
        b = _fn(name="ClassB.deserialize")
        assert _is_protocol_method_pair(a, b) is False

    def test_not_protocol_method(self):
        a = _fn(name="ClassA.custom_op")
        b = _fn(name="ClassB.custom_op")
        assert _is_protocol_method_pair(a, b) is False

    def test_no_class_prefix(self):
        a = _fn(name="serialize")
        b = _fn(name="serialize")
        assert _is_protocol_method_pair(a, b) is False


# -- _is_thin_wrapper ----------------------------------------------------------


class TestIsThinWrapper:
    def test_thin(self):
        fn = _fn(loc=3, ast_fingerprint={"ngrams": [("Call",)]})
        assert _is_thin_wrapper(fn) is True

    def test_too_long(self):
        fn = _fn(loc=10, ast_fingerprint={"ngrams": [("Call",)]})
        assert _is_thin_wrapper(fn) is False

    def test_no_ngrams(self):
        fn = _fn(loc=3, ast_fingerprint={})
        assert _is_thin_wrapper(fn) is False

    def test_multiple_calls(self):
        fn = _fn(loc=3, ast_fingerprint={"ngrams": [("Call",), ("Call",)]})
        assert _is_thin_wrapper(fn) is False
