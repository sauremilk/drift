"""Additional coverage tests for Mutant Duplicate Signal helpers."""

from __future__ import annotations

from pathlib import Path

from drift.models import FunctionInfo
from drift.signals.mutant_duplicates import (
    _is_package_lazy_getattr,
    _is_protocol_method_pair,
    _is_thin_wrapper,
    _is_tutorial_step_standalone_sample,
    _jaccard,
    _name_token_similarity,
    _structural_similarity,
    _tokenize_name,
)

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _make_fn(
    name: str = "process",
    file_path: str = "module.py",
    loc: int = 10,
    complexity: int = 3,
    ngrams: list | None = None,
    body_hash: str | None = None,
) -> FunctionInfo:
    fp = {"ngrams": ngrams or []}
    return FunctionInfo(
        name=name,
        file_path=Path(file_path),
        start_line=1,
        end_line=loc,
        language="python",
        loc=loc,
        complexity=complexity,
        has_docstring=False,
        decorators=[],
        return_type=None,
        ast_fingerprint=fp,
        body_hash=body_hash or "",
    )


# ---------------------------------------------------------------------------
# _tokenize_name / _name_token_similarity
# ---------------------------------------------------------------------------


class TestTokenizeName:
    def test_snake_case(self):
        assert _tokenize_name("process_user_input") == {"process", "user", "input"}

    def test_camel_case(self):
        tokens = _tokenize_name("processUserInput")
        assert "process" in tokens
        assert "user" in tokens

    def test_class_prefix_stripped(self):
        tokens = _tokenize_name("MyClass.my_method")
        assert "my" in tokens
        assert "method" in tokens
        assert "myclass" not in tokens


class TestNameTokenSimilarity:
    def test_identical(self):
        assert _name_token_similarity("process_data", "process_data") == 1.0

    def test_disjoint(self):
        assert _name_token_similarity("process_data", "fetch_results") == 0.0

    def test_partial_overlap(self):
        sim = _name_token_similarity("process_data", "process_results")
        assert 0.0 < sim < 1.0


# ---------------------------------------------------------------------------
# _is_tutorial_step_standalone_sample
# ---------------------------------------------------------------------------


class TestTutorialStep:
    def test_tutorial_step_dir(self):
        fn = _make_fn(file_path="tutorials/step-01/app.py")
        assert _is_tutorial_step_standalone_sample(fn) is True

    def test_example_with_numbered_dir(self):
        fn = _make_fn(file_path="examples/01-setup/main.py")
        assert _is_tutorial_step_standalone_sample(fn) is True

    def test_non_tutorial(self):
        fn = _make_fn(file_path="src/services/handler.py")
        assert _is_tutorial_step_standalone_sample(fn) is False

    def test_tutorial_without_step_dir(self):
        fn = _make_fn(file_path="tutorials/common/helpers.py")
        assert _is_tutorial_step_standalone_sample(fn) is False


# ---------------------------------------------------------------------------
# _is_package_lazy_getattr
# ---------------------------------------------------------------------------


class TestPackageLazyGetattr:
    def test_getattr_in_init(self):
        fn = _make_fn(name="__getattr__", file_path="pkg/__init__.py")
        assert _is_package_lazy_getattr(fn) is True

    def test_getattr_in_regular_module(self):
        fn = _make_fn(name="__getattr__", file_path="pkg/module.py")
        assert _is_package_lazy_getattr(fn) is False

    def test_non_getattr(self):
        fn = _make_fn(name="process", file_path="pkg/__init__.py")
        assert _is_package_lazy_getattr(fn) is False


# ---------------------------------------------------------------------------
# _is_protocol_method_pair
# ---------------------------------------------------------------------------


class TestProtocolMethodPair:
    def test_same_protocol_method_different_classes(self):
        a = _make_fn(name="FileHandler.serialize")
        b = _make_fn(name="DBHandler.serialize")
        assert _is_protocol_method_pair(a, b) is True

    def test_same_class(self):
        a = _make_fn(name="Handler.serialize")
        b = _make_fn(name="Handler.serialize")
        assert _is_protocol_method_pair(a, b) is False

    def test_different_method_names(self):
        a = _make_fn(name="Handler.serialize")
        b = _make_fn(name="Handler.deserialize")
        assert _is_protocol_method_pair(a, b) is False

    def test_non_protocol_name(self):
        a = _make_fn(name="Handler.custom_method")
        b = _make_fn(name="OtherHandler.custom_method")
        assert _is_protocol_method_pair(a, b) is False

    def test_bare_function_not_method(self):
        a = _make_fn(name="serialize")
        b = _make_fn(name="serialize")
        assert _is_protocol_method_pair(a, b) is False


# ---------------------------------------------------------------------------
# _is_thin_wrapper
# ---------------------------------------------------------------------------


class TestThinWrapper:
    def test_thin_wrapper_recognized(self):
        fn = _make_fn(loc=3, ngrams=[("Call",)])
        assert _is_thin_wrapper(fn) is True

    def test_too_long(self):
        fn = _make_fn(loc=10, ngrams=[("Call",)])
        assert _is_thin_wrapper(fn) is False

    def test_no_calls(self):
        fn = _make_fn(loc=3, ngrams=[("Assign",)])
        assert _is_thin_wrapper(fn) is False

    def test_empty_ngrams(self):
        fn = _make_fn(loc=3, ngrams=[])
        assert _is_thin_wrapper(fn) is False


# ---------------------------------------------------------------------------
# _structural_similarity / _jaccard
# ---------------------------------------------------------------------------


class TestStructuralSimilarity:
    def test_identical(self):
        ngrams = [("If", "Call"), ("Return",)]
        assert _structural_similarity(ngrams, ngrams) == 1.0

    def test_empty(self):
        assert _structural_similarity([], []) == 0.0
        assert _structural_similarity(None, [("If",)]) == 0.0

    def test_size_ratio_early_exit(self):
        small = [("If",)]
        big = [("If",)] * 20
        sim = _structural_similarity(small, big)
        assert sim <= 0.33


class TestJaccard:
    def test_identical(self):
        ngrams = [("If", "Call"), ("Return",)]
        assert _jaccard(ngrams, ngrams) == 1.0

    def test_disjoint(self):
        a = [("If", "Call")]
        b = [("While", "Return")]
        assert _jaccard(a, b) == 0.0

    def test_empty_lists(self):
        assert _jaccard([], []) == 1.0
        assert _jaccard([], [("If",)]) == 0.0
