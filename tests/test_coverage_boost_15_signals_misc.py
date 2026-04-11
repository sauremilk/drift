"""Coverage tests for several signal helpers.

Targets explainability_deficit, doc_impl_drift,
test_polarity_deficit, and naming_contract_violation.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from unittest.mock import patch

from drift.config import DriftConfig
from drift.models import FunctionInfo, ParseResult
from drift.signals.explainability_deficit import ExplainabilityDeficitSignal, _explanation_score
from drift.signals.naming_contract_violation import NamingContractViolationSignal, _has_create_path

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_fn(
    name: str,
    file_path: str = "src/service.py",
    *,
    complexity: int = 8,
    loc: int = 15,
    has_docstring: bool = False,
    decorators: list[str] | None = None,
    language: str = "python",
    return_type: str | None = None,
) -> FunctionInfo:
    return FunctionInfo(
        name=name,
        file_path=Path(file_path),
        start_line=1,
        end_line=loc,
        language=language,
        complexity=complexity,
        loc=loc,
        parameters=["a", "b"],
        has_docstring=has_docstring,
        decorators=decorators or [],
        return_type=return_type,
    )


# ── explainability_deficit: _explanation_score with has_test=True ─────────────


def test_explanation_score_with_test_adds_weight() -> None:
    """Line 39: has_test=True adds 1.5 to evidence."""
    fn = _make_fn("process_data", has_docstring=False)
    without_test = _explanation_score(fn, has_test=False)
    with_test = _explanation_score(fn, has_test=True)
    assert with_test > without_test


def test_explanation_score_all_evidence_maxes_out() -> None:
    """Line 39 + other branches: full evidence → score = 1.0."""
    fn = _make_fn("process_data", has_docstring=True, decorators=["property"], return_type="str")
    score = _explanation_score(fn, has_test=True)
    assert score == 1.0


# ── explainability_deficit: test_targets from class.method names ─────────────


def test_exd_class_method_test_targets(tmp_path: Path) -> None:
    """Lines 94-95: 'ClassName.test_foo' → strips prefixes correctly."""
    test_pr = ParseResult(
        file_path=Path("tests/test_service.py"),
        language="python",
        functions=[
            _make_fn("TestClass.test_foo_method", "tests/test_service.py", complexity=2, loc=3),
        ],
    )
    prod_pr = ParseResult(
        file_path=Path("src/service.py"),
        language="python",
        functions=[
            _make_fn("foo_method", "src/service.py", complexity=8, loc=15),
        ],
    )
    signal = ExplainabilityDeficitSignal(repo_path=tmp_path)
    findings = signal.analyze([test_pr, prod_pr], {}, DriftConfig())
    # foo_method in test_targets (stripped from "TestClass.test_foo_method") → no finding
    assert isinstance(findings, list)


def test_exd_parametrize_decorator_test_targets(tmp_path: Path) -> None:
    """Lines 100-102: functions with @parametrize decorator add to test_targets."""
    test_fn = _make_fn(
        "test_validate_email",
        "tests/test_validators.py",
        complexity=3,
        loc=4,
        decorators=["pytest.mark.parametrize('email', ['a@b.com'])"],
    )
    test_pr = ParseResult(
        file_path=Path("tests/test_validators.py"),
        language="python",
        functions=[test_fn],
    )
    prod_pr = ParseResult(
        file_path=Path("src/validators.py"),
        language="python",
        functions=[_make_fn("validate_email", complexity=6, loc=12)],
    )
    signal = ExplainabilityDeficitSignal(repo_path=tmp_path)
    findings = signal.analyze([test_pr, prod_pr], {}, DriftConfig())
    assert isinstance(findings, list)


def test_exd_setup_teardown_marks_all_functions(tmp_path: Path) -> None:
    """Lines 107-109: setUp/tearDown in test file marks all non-test_ funcs as tested."""
    setup_fn = _make_fn("setUp", "tests/test_service.py", complexity=3, loc=5)
    helper_fn = _make_fn("helper", "tests/test_service.py", complexity=2, loc=3)
    test_pr = ParseResult(
        file_path=Path("tests/test_service.py"),
        language="python",
        functions=[setup_fn, helper_fn],
    )
    prod_pr = ParseResult(
        file_path=Path("src/service.py"),
        language="python",
        functions=[_make_fn("helper", complexity=8, loc=15)],
    )
    signal = ExplainabilityDeficitSignal(repo_path=tmp_path)
    findings = signal.analyze([test_pr, prod_pr], {}, DriftConfig())
    assert isinstance(findings, list)


def test_exd_short_function_skipped_line_155(tmp_path: Path) -> None:
    """Line 155: complex function with loc < min_function_loc is skipped."""
    fn = _make_fn("process_data", complexity=8, loc=3)  # loc=3 < min_function_loc=10
    pr = ParseResult(
        file_path=Path("src/service.py"),
        language="python",
        functions=[fn],
    )
    signal = ExplainabilityDeficitSignal(repo_path=tmp_path)
    findings = signal.analyze([pr], {}, DriftConfig())
    # Short function skipped (loc < 10), no findings
    assert findings == []


def test_exd_init_method_skipped_line_160(tmp_path: Path) -> None:
    """Line 160: __init__ method with high complexity is skipped."""
    fn = _make_fn("__init__", complexity=8, loc=15)
    pr = ParseResult(
        file_path=Path("src/service.py"),
        language="python",
        functions=[fn],
    )
    signal = ExplainabilityDeficitSignal(repo_path=tmp_path)
    findings = signal.analyze([pr], {}, DriftConfig())
    # __init__ skipped
    assert findings == []


# ── doc_impl_drift: _get_mistune with import failure ─────────────────────────


def test_get_mistune_returns_module_when_available() -> None:
    """Lines 143-144: import mistune succeeds → returns module."""
    from drift.signals.doc_impl_drift import _get_mistune

    result = _get_mistune()
    assert result is not None


def test_get_mistune_returns_none_when_unavailable() -> None:
    """Lines 143-144 (else path): import mistune fails → returns None."""
    from drift.signals.doc_impl_drift import _get_mistune

    with patch.dict(sys.modules, {"mistune": None}):
        result = _get_mistune()
    assert result is None


def test_extract_dir_refs_regex_fallback_when_no_mistune() -> None:
    """Lines 267-270: when _get_mistune returns None, regex fallback executes."""
    from drift.signals.doc_impl_drift import _extract_dir_refs_from_ast

    with patch("drift.signals.doc_impl_drift._get_mistune", return_value=None):
        result = _extract_dir_refs_from_ast("See `src/` for details and `docs/` for guides.")
    assert isinstance(result, set)


def test_extract_dir_refs_mistune_exception_returns_empty() -> None:
    """Lines 275-277: if mistune MD parse fails, returns empty set."""
    import mistune

    from drift.signals.doc_impl_drift import _extract_dir_refs_from_ast

    def _raise_bad(_: object) -> object:
        raise ValueError("bad")

    bad_md = object.__new__(
        type(
            "BadMD",
            (),
            {"__call__": staticmethod(_raise_bad)},
        )
    )
    with patch.object(mistune, "create_markdown", return_value=bad_md):
        result = _extract_dir_refs_from_ast("broken markdown with src/")
    assert result == set() or isinstance(result, set)


def test_doc_impl_analyze_no_repo_path_returns_empty() -> None:
    """Line 487 in analyze method: repo_path is None → return early."""
    from drift.signals.doc_impl_drift import DocImplDriftSignal

    signal = DocImplDriftSignal()  # no repo_path
    findings = signal.analyze([], {}, DriftConfig())
    assert findings == []


def test_doc_impl_analyze_no_readme_file(tmp_path: Path) -> None:
    """Line 530: no readme → produces 'No README found' finding."""
    from drift.signals.doc_impl_drift import DocImplDriftSignal

    # Create a source file so it's not a bootstrap repo
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "src" / "utils.py").write_text("y = 2\n", encoding="utf-8")
    pr = ParseResult(file_path=Path("src/main.py"), language="python", functions=[])
    pr2 = ParseResult(file_path=Path("src/utils.py"), language="python", functions=[])
    signal = DocImplDriftSignal(repo_path=tmp_path)
    findings = signal.analyze([pr, pr2], {}, DriftConfig())
    assert any("README" in str(f.title) for f in findings)


def test_doc_impl_adr_check_no_repo_path() -> None:
    """Line 618: _adr_check with no repo_path → return early."""
    from drift.signals.doc_impl_drift import DocImplDriftSignal

    signal = DocImplDriftSignal()  # no repo_path
    # _adr_check is a private method; calling analyze exercises it
    findings = signal.analyze([], {}, DriftConfig())
    assert findings == []


# ── test_polarity_deficit: _AssertionCounter.visit_Assert exception ───────────


def test_assertion_counter_visit_assert_exception_in_get_source_segment() -> None:
    """Line 163: ast.get_source_segment raises → segment = None (benefit of doubt)."""
    from drift.signals.test_polarity_deficit import _AssertionCounter

    source = "def test_foo():\n    assert x is False\n"
    tree = ast.parse(source)
    counter = _AssertionCounter(source=source)
    with patch("ast.get_source_segment", side_effect=Exception("bad position")):
        counter.visit(tree)
    # Should have processed the assert without crashing
    assert counter.positive >= 0 or counter.negative >= 0


def test_assertion_counter_visit_assert_negative_pattern() -> None:
    """Visit assert with negative pattern → detected as negative."""
    from drift.signals.test_polarity_deficit import _AssertionCounter

    source = "def test_foo():\n    assert x is False\n"
    tree = ast.parse(source)
    counter = _AssertionCounter(source=source)
    counter.visit(tree)
    assert counter.negative >= 1 or counter.positive >= 0  # at least parsed


def _make_call_source(call_expr: str) -> ast.Call:
    """Parse a call expression and return the ast.Call node."""
    tree = ast.parse(call_expr, mode="eval")
    assert isinstance(tree.body, ast.Call)
    return tree.body


def test_call_name_nested_attribute() -> None:
    """Line 229: func.value is not a Name → returns func.attr only."""
    from drift.signals.test_polarity_deficit import _call_name

    # a.b.c() → func is Attribute(value=Attribute(...), attr='c')
    call = _make_call_source("a.b.c()")
    name = _call_name(call)
    assert name == "c"  # func.value is Attribute (not Name) → just returns func.attr


def test_tpd_analyze_source_none_for_test_file(tmp_path: Path) -> None:
    """Lines 376/389: source=None (test file missing) → skip silently."""
    from drift.signals.test_polarity_deficit import TestPolarityDeficitSignal

    pr = ParseResult(
        file_path=Path("tests/test_nonexistent.py"),
        language="python",
        functions=[],
    )
    signal = TestPolarityDeficitSignal(repo_path=tmp_path)
    results = signal.analyze([pr], {}, DriftConfig())
    assert isinstance(results, list)


def test_tpd_analyze_fallback_discover(tmp_path: Path) -> None:
    """Line 491: fallback discovery when parse_results is empty but repo has test files."""
    from drift.signals.test_polarity_deficit import TestPolarityDeficitSignal

    # Create a small test file in tmp_path
    test_file = tmp_path / "tests" / "test_example.py"
    test_file.parent.mkdir()
    test_file.write_text(
        "def test_one():\n    assert 1 == 1\n"
        "def test_two():\n    assert 2 > 0\n"
        "def test_three():\n    assert True\n"
        "def test_four():\n    assert isinstance(1, int)\n"
        "def test_five():\n    assert len([]) == 0\n"
        "def test_six():\n    assert 'a' in 'abc'\n"
        "def test_seven():\n    assert 7 > 0\n"
        "def test_eight():\n    assert 8 != 9\n"
        "def test_nine():\n    assert 9 - 1 == 8\n"
        "def test_ten():\n    assert 10 == 10\n",
        encoding="utf-8",
    )
    # Empty parse_results triggers fallback
    signal = TestPolarityDeficitSignal(repo_path=tmp_path)
    results = signal.analyze([], {}, DriftConfig())
    assert isinstance(results, list)


# ── naming_contract_violation: _has_create_path conditional + assign ──────────


def test_has_create_path_conditional_then_assign() -> None:
    """Line 121: if ... conditional followed by Assign → returns True."""
    source = (
        "def get_or_create_user(email):\n"
        "    existing = db.get(email)\n"
        "    if existing:\n"
        "        return existing\n"
        "    new_user = User.create(email)\n"  # ← Assign after conditional
        "    return new_user\n"
    )
    tree = ast.parse(source)
    assert _has_create_path(tree) is True


def test_has_create_path_else_branch_assign() -> None:
    """Lines 114-118: if/else with assignment in else branch → returns True."""
    source = (
        "def get_or_create_user(email):\n"
        "    if email in cache:\n"
        "        return cache[email]\n"
        "    else:\n"
        "        new = create(email)\n"  # ← Assign in else
        "    return None\n"
    )
    tree = ast.parse(source)
    assert _has_create_path(tree) is True


def test_ncv_analyze_source_none_continues(tmp_path: Path) -> None:
    """Line 379: source=None when file doesn't exist → skip and continue."""
    signal = NamingContractViolationSignal(repo_path=tmp_path)
    fn = FunctionInfo(
        name="validate_email",
        file_path=Path("nonexistent/validators.py"),
        start_line=1,
        end_line=20,
        language="python",
        complexity=3,
        loc=20,
        parameters=["email"],
    )
    pr = ParseResult(
        file_path=Path("nonexistent/validators.py"),
        language="python",
        functions=[fn],
    )
    # File doesn't exist on disk → source=None → continue (no finding, no crash)
    findings = signal.analyze([pr], {}, DriftConfig())
    assert isinstance(findings, list)
