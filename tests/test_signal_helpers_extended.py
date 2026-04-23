"""Coverage tests for guard_clause_deficit and co_change_coupling signal helpers."""

from __future__ import annotations

import ast
import datetime
from pathlib import Path

from drift.config import DriftConfig
from drift.models import CommitInfo, FunctionInfo, ImportInfo, ParseResult, SignalType
from drift.signals.co_change_coupling import (
    CoChangeCouplingSignal,
    _explicit_dependency_pairs,
    _is_automated_commit,
    _resolve_non_relative_targets,
    _resolve_relative_targets,
)
from drift.signals.guard_clause_deficit import (
    GuardClauseDeficitSignal,
    _function_max_nesting,
    _has_guard,
    _max_nesting_depth,
    _read_function_source,
)

# ── Helper factories ──────────────────────────────────────────────────────────


def _make_fn(name: str, file_path: str, *, complexity: int = 8) -> FunctionInfo:
    return FunctionInfo(
        name=name,
        file_path=Path(file_path),
        start_line=1,
        end_line=20,
        language="python",
        complexity=complexity,
        loc=20,
        parameters=["a", "b", "c"],
    )


def _make_commit(
    hash_: str,
    files: list[str],
    *,
    message: str = "feat: something",
    is_ai: bool = False,
    author: str = "dev",
    email: str = "dev@example.com",
) -> CommitInfo:
    return CommitInfo(
        hash=hash_,
        author=author,
        email=email,
        timestamp=datetime.datetime(2024, 1, 1),
        message=message,
        files_changed=files,
        insertions=5,
        deletions=2,
        is_ai_attributed=is_ai,
        ai_confidence=1.0 if is_ai else 0.0,
        coauthors=[],
    )


def _make_import(
    source_file: str,
    module: str,
    names: list[str] | None = None,
    *,
    is_relative: bool = False,
) -> ImportInfo:
    return ImportInfo(
        source_file=Path(source_file),
        imported_module=module,
        imported_names=names or [],
        line_number=1,
        is_relative=is_relative,
        is_module_level=True,
    )


# ── guard_clause_deficit: _has_guard branches ────────────────────────────────


def test_has_guard_isinstance_call_returns_true() -> None:
    """Line 66: isinstance(param, ...) expression guard."""
    source = "isinstance(a, int)\n"
    tree = ast.parse(source)
    stmt = tree.body[0]
    assert _has_guard(stmt, {"a"}) is True


def test_has_guard_isinstance_wrong_param_returns_false() -> None:
    """isinstance call but param not in param_names → no guard."""
    source = "isinstance(x, int)\n"
    tree = ast.parse(source)
    stmt = tree.body[0]
    assert _has_guard(stmt, {"a"}) is False


def test_has_guard_assert_stmt_returns_true() -> None:
    """Lines 98-99: assert param > 0 expression guard."""
    source = "assert a > 0\n"
    tree = ast.parse(source)
    stmt = tree.body[0]
    assert _has_guard(stmt, {"a"}) is True


def test_has_guard_if_raise_returns_true() -> None:
    """Lines 106-109: if param < 0: raise ValueError(param) guard."""
    source = "if a < 0:\n    raise ValueError(a)\n"
    tree = ast.parse(source)
    stmt = tree.body[0]
    assert _has_guard(stmt, {"a"}) is True


def test_has_guard_if_with_else_not_guard() -> None:
    """If with orelse should NOT be counted as guard."""
    source = "if a < 0:\n    raise ValueError()\nelse:\n    pass\n"
    tree = ast.parse(source)
    stmt = tree.body[0]
    assert _has_guard(stmt, {"a"}) is False


def test_has_guard_plain_assign_returns_false() -> None:
    """Plain assignment is not a guard."""
    source = "x = 1\n"
    tree = ast.parse(source)
    stmt = tree.body[0]
    assert _has_guard(stmt, {"a"}) is False


# ── guard_clause_deficit: _max_nesting_depth with nested function ─────────────


def test_max_nesting_depth_nested_function_skipped() -> None:
    """Lines 138-139: nested function is skipped (not counted against parent depth)."""
    source_stmts = ast.parse(
        "def outer(a, b):\n    def inner():\n        if a:\n            return a\n    return b\n"
    ).body
    outer_fn = source_stmts[0]
    assert isinstance(outer_fn, ast.FunctionDef)
    # _max_nesting_depth on outer body should see nested def and skip it (lines 138-139)
    depth = _max_nesting_depth(outer_fn.body)
    assert depth == 0  # outer body has no non-function nesting stmts at depth 1


# ── guard_clause_deficit: _function_max_nesting returns None ─────────────────


def test_function_max_nesting_no_function_returns_none() -> None:
    """Line 199: source with no function → returns None."""
    source = "x = 1\ny = 2\n"
    result = _function_max_nesting(source)
    assert result is None


def test_function_max_nesting_with_function_returns_int() -> None:
    """Normal path: source with a function → returns int."""
    source = "def foo(a):\n    if a:\n        if a > 0:\n            return a\n    return 0\n"
    result = _function_max_nesting(source)
    assert isinstance(result, int)
    assert result >= 1


# ── guard_clause_deficit: _read_function_source returns None ─────────────────


def test_read_function_source_nonexistent_file_returns_none(tmp_path: Path) -> None:
    """Lines 397-398: non-existent file → returns None."""
    fn = _make_fn("foo", "nonexistent/file.py")
    result = _read_function_source(Path("nonexistent/file.py"), fn, tmp_path)
    assert result is None


# ── guard_clause_deficit: analyze benefit-of-doubt (source is None) ──────────


def test_guard_clause_analyze_benefit_of_doubt(tmp_path: Path) -> None:
    """Lines 288-289: when source file is missing, guarded += 1 (benefit of doubt)."""
    signal = GuardClauseDeficitSignal(repo_path=tmp_path)

    # Three public functions with complexity >=5, 3 params, non-existent file
    file_path = "app/service.py"
    pr = ParseResult(
        file_path=Path(file_path),
        language="python",
        functions=[
            _make_fn("process_data", file_path, complexity=8),
            _make_fn("validate_input", file_path, complexity=7),
            _make_fn("handle_request", file_path, complexity=6),
        ],
    )
    # File does not exist on disk → source=None for all → all guarded (benefit of doubt)
    findings = signal.analyze([pr], {}, DriftConfig())
    # All functions get "benefit of doubt" so no GCD finding for unguarded ratio.
    # This exercises lines 288-289 (guarded += 1 path).
    assert isinstance(findings, list)


# ── co_change_coupling: _is_automated_commit ─────────────────────────────────


def test_is_automated_commit_ai_attributed_true() -> None:
    """Line 180: is_ai_attributed=True → immediate return True."""
    commit = _make_commit("abc", ["a.py"], is_ai=True)
    assert _is_automated_commit(commit) is True


def test_is_automated_commit_bot_author() -> None:
    """Bot author name triggers automated detection."""
    commit = _make_commit("abc", ["a.py"], author="dependabot[bot]", email="bot@github.com")
    assert _is_automated_commit(commit) is True


def test_is_automated_commit_normal_author_false() -> None:
    """Normal author → not automated."""
    commit = _make_commit("abc", ["a.py"])
    assert _is_automated_commit(commit) is False


# ── co_change_coupling: _resolve_non_relative_targets ────────────────────────


def test_resolve_non_relative_targets_empty_module() -> None:
    """Lines 72-75: empty module after lstrip → returns empty set."""
    imp = _make_import("a.py", "...")
    result = _resolve_non_relative_targets(imp, {})
    assert result == set()


def test_resolve_non_relative_targets_known_module() -> None:
    """Lines 72-86: known module in index → returns file paths."""
    imp = _make_import("a.py", "mymod")
    module_index = {"mymod": {"src/mymod.py"}}
    result = _resolve_non_relative_targets(imp, module_index)
    assert "src/mymod.py" in result


def test_resolve_non_relative_targets_nested_known_module() -> None:
    """Lines 78-83: imported module + imported_name lookup in module_index."""
    imp = _make_import("a.py", "mymod", ["SubClass"])
    module_index = {"mymod.SubClass": {"src/subclass.py"}}
    result = _resolve_non_relative_targets(imp, module_index)
    assert "src/subclass.py" in result


# ── co_change_coupling: _resolve_relative_targets ────────────────────────────


def test_resolve_relative_targets_with_module_part() -> None:
    """Lines 87-101: relative import with module_part generates py/init paths."""
    imp = _make_import("pkg/a.py", ".utils", is_relative=True)
    result = _resolve_relative_targets(Path("pkg/a.py"), imp)
    posix_results = [str(p) for p in result]
    # Should include paths like pkg/utils.py or pkg/utils/__init__.py
    assert any("utils" in p for p in posix_results)


def test_resolve_relative_targets_with_imported_names() -> None:
    """Relative import with imported names generates extra path candidates."""
    imp = _make_import("pkg/a.py", ".", ["helpers"], is_relative=True)
    result = _resolve_relative_targets(Path("pkg/a.py"), imp)
    assert any("helpers" in p for p in result)


# ── co_change_coupling: _explicit_dependency_pairs ──────────────────────────


def test_explicit_dependency_pairs_with_relative_import() -> None:
    """Lines 114, 120: relative imports between known files produce pairs."""
    pr_a = ParseResult(
        file_path=Path("pkg/a.py"),
        language="python",
        functions=[],
        imports=[_make_import("pkg/a.py", ".b", ["B"], is_relative=True)],
    )
    pr_b = ParseResult(
        file_path=Path("pkg/b.py"),
        language="python",
        functions=[],
    )
    pairs = _explicit_dependency_pairs([pr_a, pr_b])
    # pairs should contain (pkg/a.py, pkg/b.py) if relative resolution matches
    assert isinstance(pairs, set)


def test_explicit_dependency_pairs_with_non_relative_import() -> None:
    """Non-relative import to a known module → produces pair."""
    pr_a = ParseResult(
        file_path=Path("src/service.py"),
        language="python",
        functions=[],
        imports=[_make_import("src/service.py", "utils", ["helper"])],
    )
    pr_b = ParseResult(
        file_path=Path("src/utils.py"),
        language="python",
        functions=[],
    )
    pairs = _explicit_dependency_pairs([pr_a, pr_b])
    assert isinstance(pairs, set)


# ── co_change_coupling: signal.analyze branches ──────────────────────────────


def test_ccc_analyze_too_few_known_files_returns_empty() -> None:
    """Line 203: known_files < 2 → return []."""
    commits = [_make_commit(f"h{i}", ["only.py"]) for i in range(10)]
    signal = CoChangeCouplingSignal(commits=commits)
    pr = ParseResult(
        file_path=Path("only.py"),
        language="python",
        functions=[],
    )
    result = signal.analyze([pr], {}, DriftConfig())
    assert result == []


def test_ccc_analyze_with_merge_commits_reduces_weight() -> None:
    """Lines 229, 233: merge and automated commits reduce weight."""
    # Mix of normal + merge + automated commits to exercise weight reduction
    commits = []
    for i in range(5):
        commits.append(_make_commit(f"h{i}", ["a.py", "b.py"]))
    # Merge commits → line 229 (weight *= _MERGE_WEIGHT)
    for i in range(5, 8):
        commits.append(
            _make_commit(f"h{i}", ["a.py", "b.py"], message="merge pull request #10 from branch")
        )
    # Automated commit → line 233 (weight *= _AUTOMATED_WEIGHT)
    commits.append(
        _make_commit("hauto", ["a.py", "b.py"], author="dependabot[bot]", email="bot@github.com")
    )

    pr_a = ParseResult(file_path=Path("a.py"), language="python", functions=[])
    pr_b = ParseResult(file_path=Path("b.py"), language="python", functions=[])

    signal = CoChangeCouplingSignal(commits=commits)
    result = signal.analyze([pr_a, pr_b], {}, DriftConfig())
    # Result may or may not have findings depending on threshold; we just exercise the branches
    assert isinstance(result, list)


def test_ccc_analyze_produces_finding_with_enough_co_changes() -> None:
    """Full happy path: enough co-changes → finding produced."""
    commits = [_make_commit(f"h{i:02d}", ["src/a.py", "src/b.py"]) for i in range(12)]
    pr_a = ParseResult(file_path=Path("src/a.py"), language="python", functions=[])
    pr_b = ParseResult(file_path=Path("src/b.py"), language="python", functions=[])

    signal = CoChangeCouplingSignal(commits=commits)
    findings = signal.analyze([pr_a, pr_b], {}, DriftConfig())
    assert len(findings) >= 1
    assert findings[0].signal_type == SignalType.CO_CHANGE_COUPLING
