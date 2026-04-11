"""File 18: Coverage boost for pipeline cache pruning, api/diff baseline path,
analyzer delegates, guard_clause helpers, and negative_context.py standalone generators.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from unittest.mock import patch

from drift.config import DriftConfig
from drift.models import (
    Finding,
    NegativeContextScope,
    RepoAnalysis,
    Severity,
    SignalType,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_finding(
    signal_type: SignalType = SignalType.PATTERN_FRAGMENTATION,
    file_path: Path | None = Path("src/a.py"),
    related_files: list[str] | None = None,
    metadata: dict | None = None,
) -> Finding:
    return Finding(
        signal_type=signal_type,
        severity=Severity.MEDIUM,
        score=0.5,
        title="Test finding",
        description="desc",
        file_path=file_path,
        related_files=related_files or [],
        metadata=metadata or {},
    )


def _make_blank_repo_analysis(repo_path: Path) -> RepoAnalysis:
    import datetime

    return RepoAnalysis(
        repo_path=repo_path,
        analyzed_at=datetime.datetime.now(tz=datetime.UTC),
        drift_score=0.0,
    )


# ---------------------------------------------------------------------------
# pipeline._prune_git_history_cache — lines 268, 272
# ---------------------------------------------------------------------------


def test_prune_git_history_cache_stale_entries() -> None:
    """Line 268: pop stale entries from _GIT_HISTORY_CACHE."""
    from drift.pipeline import _GIT_HISTORY_CACHE, _prune_git_history_cache

    _GIT_HISTORY_CACHE.clear()
    # Insert a stale entry (700 seconds old, TTL is 600s)
    stale_key = "__test_stale__"
    _GIT_HISTORY_CACHE[stale_key] = (time.time() - 700, [], {})

    _prune_git_history_cache(time.time())

    assert stale_key not in _GIT_HISTORY_CACHE
    _GIT_HISTORY_CACHE.clear()


def test_prune_git_history_cache_max_entries() -> None:
    """Line 272: evict oldest when cache exceeds _GIT_HISTORY_CACHE_MAX_ENTRIES."""
    from drift.pipeline import (
        _GIT_HISTORY_CACHE,
        _GIT_HISTORY_CACHE_MAX_ENTRIES,
        _prune_git_history_cache,
    )

    _GIT_HISTORY_CACHE.clear()
    now = time.time()
    # Fill to MAX + 2 with fresh (non-stale) entries having varying timestamps
    for i in range(_GIT_HISTORY_CACHE_MAX_ENTRIES + 2):
        _GIT_HISTORY_CACHE[f"__test_max_{i}__"] = (now - i, [], {})

    _prune_git_history_cache(now)

    assert len(_GIT_HISTORY_CACHE) <= _GIT_HISTORY_CACHE_MAX_ENTRIES
    _GIT_HISTORY_CACHE.clear()


# ---------------------------------------------------------------------------
# api/diff.py baseline_file path — lines 167+, 176, 185, 199-205
# ---------------------------------------------------------------------------


def test_diff_baseline_file_outside_repo(tmp_path: Path) -> None:
    """Line 176: baseline_file resolves outside repo_root → error response."""
    from drift.api.diff import diff

    # A path that is the PARENT of tmp_path — definitely outside
    outside_baseline = str(tmp_path.parent / "unrelated_baseline.json")

    mock_analysis = _make_blank_repo_analysis(tmp_path)
    mock_analysis.findings = []

    with (
        patch("drift.analyzer.analyze_diff", return_value=mock_analysis),
        patch("drift.api.diff._load_config_cached", return_value=DriftConfig()),
    ):
        result = diff(str(tmp_path), baseline_file=outside_baseline)

    # Should return an error response (DRIFT-1003 path traversal)
    assert result.get("error_code") == "DRIFT-1003" or "error" in str(result).lower()


def test_diff_baseline_file_inside_repo(tmp_path: Path) -> None:
    """Lines 185-205: baseline_file inside repo → load and diff findings."""
    from drift.api.diff import diff

    baseline_f = tmp_path / "baseline.json"
    baseline_f.write_text("[]", encoding="utf-8")

    mock_analysis = _make_blank_repo_analysis(tmp_path)
    mock_analysis.findings = []

    with (
        patch("drift.analyzer.analyze_diff", return_value=mock_analysis),
        patch("drift.api.diff._load_config_cached", return_value=DriftConfig()),
        patch("drift.baseline.load_baseline", return_value=[]),
        patch("drift.baseline.baseline_diff", return_value=([], [])),
    ):
        result = diff(str(tmp_path), baseline_file=str(baseline_f))

    # Should succeed and return a valid response
    assert result is not None
    assert "error" not in result.get("status", "ok").lower() or result.get("status") == "ok"


# ---------------------------------------------------------------------------
# analyzer.py wrappers — lines 59, 69
# ---------------------------------------------------------------------------


def test_analyzer_is_git_repo_wrapper(tmp_path: Path) -> None:
    """Line 59: _is_git_repo delegates to is_git_repo."""
    from drift.analyzer import _is_git_repo

    result = _is_git_repo(tmp_path)
    assert isinstance(result, bool)


def test_analyzer_fetch_git_history_wrapper(tmp_path: Path) -> None:
    """Line 69: _fetch_git_history delegates to fetch_git_history."""
    from drift.analyzer import _fetch_git_history

    commits, histories = _fetch_git_history(tmp_path, 90, set())
    assert isinstance(commits, list)
    assert isinstance(histories, dict)


# ---------------------------------------------------------------------------
# analyzer.analyze_repo with on_progress — line 211
# ---------------------------------------------------------------------------


def test_analyze_repo_with_on_progress_callback(tmp_path: Path) -> None:
    """Line 211: on_progress callback invoked during analyze_repo."""
    from drift.analyzer import analyze_repo

    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")

    progress_calls: list[tuple] = []

    analyze_repo(
        tmp_path,
        config=DriftConfig(),
        on_progress=lambda msg, done, total: progress_calls.append((msg, done, total)),
    )

    # At least the "Discovering files" callback should have been invoked
    assert len(progress_calls) >= 1
    assert any(
        "Discovering" in c[0] or "Analyzing" in c[0] or "Signal" in c[0] or "Scoring" in c[0]
        for c in progress_calls
    )


# ---------------------------------------------------------------------------
# analyzer.analyze_diff exception fallback — lines 272+
# ---------------------------------------------------------------------------


def test_analyze_diff_subprocess_failure_fallback(tmp_path: Path) -> None:
    """Lines 272+: subprocess.run raises → fallback to analyze_repo."""
    from drift.analyzer import analyze_diff

    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")

    fallback_analysis = _make_blank_repo_analysis(tmp_path)

    with (
        patch("subprocess.run", side_effect=subprocess.CalledProcessError(128, "git")),
        patch("drift.analyzer.analyze_repo", return_value=fallback_analysis),
    ):
        result = analyze_diff(tmp_path, config=DriftConfig(), diff_ref="HEAD~999")

    assert result is fallback_analysis
    # Should be marked degraded
    assert result.analysis_status == "degraded" or result.degradation_causes


# ---------------------------------------------------------------------------
# signals/guard_clause_deficit helpers
# ---------------------------------------------------------------------------


def test_function_is_guarded_no_function(tmp_path: Path) -> None:
    """Line 109: source has no FunctionDef → return True (benefit of doubt)."""
    from drift.models import FunctionInfo
    from drift.signals.guard_clause_deficit import _function_is_guarded

    fn = FunctionInfo(
        name="placeholder",
        file_path=tmp_path / "x.py",
        start_line=1,
        end_line=1,
        language="python",
        complexity=1,
        loc=1,
        parameters=["a", "b"],
        body_hash="abc",
        ast_fingerprint="def",
    )

    # Source without any FunctionDef → should return True (benefit of doubt)
    result = _function_is_guarded("x = 1\ny = 2\n", fn, {"a", "b"})
    assert result is True


def test_max_nesting_depth_nested_function() -> None:
    """Lines 138-139: nested function inside body → pass (don't count inner body)."""
    import ast

    from drift.signals.guard_clause_deficit import _max_nesting_depth

    source = """
def outer(a, b):
    def inner():
        pass
    if a:
        return b
"""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "outer":
            depth = _max_nesting_depth(node.body)
            assert isinstance(depth, int)
            break


def test_function_max_nesting_syntax_error() -> None:
    """Lines 148-149: SyntaxError in source → returns None."""
    from drift.signals.guard_clause_deficit import _function_max_nesting

    result = _function_max_nesting("def f(:\n    pass\n")
    assert result is None


def test_function_max_nesting_no_function() -> None:
    """Line 153: no function in source → returns None."""
    from drift.signals.guard_clause_deficit import _function_max_nesting

    result = _function_max_nesting("x = 1\n")
    assert result is None


# ---------------------------------------------------------------------------
# negative_context.py standalone — scope and generator branches
# ---------------------------------------------------------------------------


def test_scope_from_finding_module_scope_standalone() -> None:
    """Line 136: related_files > 2 → MODULE scope (standalone negative_context.py)."""
    from drift.negative_context import _scope_from_finding

    finding = _make_finding(
        file_path=Path("src/a.py"),
        related_files=["src/b.py", "src/c.py", "src/d.py"],
    )
    result = _scope_from_finding(finding)
    assert result == NegativeContextScope.MODULE


def test_scope_from_finding_repo_scope_standalone() -> None:
    """Line 139: no file_path, no related_files → REPO scope."""
    from drift.negative_context import _scope_from_finding

    finding = _make_finding(file_path=None, related_files=[])
    result = _scope_from_finding(finding)
    assert result == NegativeContextScope.REPO


def test_gen_maz_non_string_auth_mech_standalone() -> None:
    """Line 242: auth_mechs[0] is not a string → str() conversion."""
    from drift.negative_context import findings_to_negative_context

    finding = _make_finding(
        signal_type=SignalType.MISSING_AUTHORIZATION,
        metadata={
            "auth_mechanisms_in_module": [42],  # non-string
            "framework": "django",
            "endpoint": "/api/users",
        },
    )
    result = findings_to_negative_context([finding])
    assert any("42" in r.description for r in result)


def test_gen_ecd_with_diverged_fns_and_comparison_ref() -> None:
    """Lines 385-399, 413-415: ECD generator with diverged_fns and comparison_ref."""
    from drift.negative_context import findings_to_negative_context

    finding = _make_finding(
        signal_type=SignalType.EXCEPTION_CONTRACT_DRIFT,
        metadata={
            "module": "payment",
            "exception_types": ["ValueError", "RuntimeError"],
            "diverged_functions": ["process_payment", "refund"],
            "divergence_count": 2,
            "module_function_count": 5,
            "comparison_ref": "HEAD~5",
        },
    )
    result = findings_to_negative_context([finding])
    assert len(result) > 0
    assert any("payment" in r.description for r in result)


def test_gen_avs_with_blast_radius_and_import_path() -> None:
    """Lines 466, 473: AVS generator with blast_radius and import_path metadata."""
    from drift.negative_context import findings_to_negative_context

    finding = _make_finding(
        signal_type=SignalType.ARCHITECTURE_VIOLATION,
        metadata={
            "src_layer": "presentation",
            "dst_layer": "data",
            "boundary_rule": "no-direct-db-access",
            "blast_radius": 7,
            "import_path": "data.repositories.UserRepository",
            "instability": 0.85,
        },
    )
    result = findings_to_negative_context([finding])
    assert len(result) > 0


def test_gen_ccc_with_co_change_weight_and_commit_samples() -> None:
    """Lines 551, 562-563, 571-579: CCC generator with co_change_weight and commit_samples."""
    from drift.negative_context import findings_to_negative_context

    finding = _make_finding(
        signal_type=SignalType.CO_CHANGE_COUPLING,
        metadata={
            "file_a": "src/payment.py",
            "file_b": "src/billing.py",
            "co_change_weight": 12.5,
            "confidence": 0.85,
            "commit_samples": ["abc1234", "def5678", "ghi9012"],
            "coupled_files": ["src/invoice.py"],
        },
    )
    result = findings_to_negative_context([finding])
    assert len(result) > 0
    assert any("payment.py" in r.description for r in result)


def test_gen_hsc_api_token_rule() -> None:
    """Line 626: HARDCODED_SECRET with rule_id='hardcoded_api_token'."""
    from drift.negative_context import findings_to_negative_context

    finding = _make_finding(
        signal_type=SignalType.HARDCODED_SECRET,
        metadata={
            "variable": "API_KEY",
            "rule_id": "hardcoded_api_token",
            "cwe": "CWE-798",
        },
    )
    result = findings_to_negative_context([finding])
    assert len(result) > 0
    assert any("API token" in r.description for r in result)


def test_gen_hsc_placeholder_secret_rule() -> None:
    """Lines 631-633: HARDCODED_SECRET with rule_id='placeholder_secret'."""
    from drift.negative_context import findings_to_negative_context

    finding = _make_finding(
        signal_type=SignalType.HARDCODED_SECRET,
        metadata={
            "variable": "SECRET",
            "rule_id": "placeholder_secret",
            "cwe": "CWE-798",
        },
    )
    result = findings_to_negative_context([finding])
    assert len(result) > 0
    assert any("placeholder" in r.description.lower() for r in result)


def test_gen_hsc_default_rule() -> None:
    """Line 638: HARDCODED_SECRET with default rule_id."""
    from drift.negative_context import findings_to_negative_context

    finding = _make_finding(
        signal_type=SignalType.HARDCODED_SECRET,
        metadata={
            "variable": "PASSWD",
            "rule_id": "some_other_rule",
            "cwe": "CWE-798",
        },
    )
    result = findings_to_negative_context([finding])
    assert len(result) > 0


def test_findings_to_nc_invalid_scope_filter() -> None:
    """Lines 1234-1235: invalid scope value → ValueError caught silently."""
    from drift.negative_context import findings_to_negative_context

    finding = _make_finding(signal_type=SignalType.PATTERN_FRAGMENTATION)
    # "invalid_scope_xyz" is not a valid NegativeContextScope value
    result = findings_to_negative_context([finding], scope="invalid_scope_xyz")
    # Should not raise; may return empty or filtered list
    assert isinstance(result, list)


def test_findings_to_nc_target_file_filter_excludes() -> None:
    """Line 1239: target_file not in affected_files → continue (skip item)."""
    from drift.negative_context import findings_to_negative_context

    finding = _make_finding(signal_type=SignalType.PATTERN_FRAGMENTATION)
    # Filter by a file that won't be in affected_files
    result = findings_to_negative_context(
        [finding],
        target_file="src/nonexistent_file_xyz.py",
    )
    assert result == []
