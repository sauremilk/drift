"""Coverage-Boost: negative_context.py — _scope_from_finding, _gen_ecd, _gen_hsc etc."""
from __future__ import annotations

from pathlib import Path

from drift.models import (
    Finding,
    NegativeContextScope,
    Severity,
    SignalType,
)
from drift.negative_context import (
    findings_to_negative_context,
)
from drift.negative_context.core import _scope_from_finding


def _make_finding(
    signal: SignalType = SignalType.EXCEPTION_CONTRACT_DRIFT,
    severity: Severity = Severity.MEDIUM,
    file_path: str | None = "src/foo.py",
    related_files: list[str] | None = None,
    metadata: dict | None = None,
    symbol: str | None = None,
) -> Finding:
    return Finding(
        signal_type=signal,
        severity=severity,
        score=0.5,
        title="Test finding",
        description="desc",
        file_path=Path(file_path) if file_path else None,
        start_line=10,
        end_line=15,
        fix="Fix it",
        related_files=[Path(f) for f in (related_files or [])],
        metadata=metadata or {},
        symbol=symbol,
    )


# ---------------------------------------------------------------------------
# _scope_from_finding
# ---------------------------------------------------------------------------

def test_scope_from_finding_file_when_has_file_path() -> None:
    # The core _scope_from_finding returns FILE when file_path is set
    f = _make_finding(file_path="src/foo.py")
    scope = _scope_from_finding(f)
    assert scope == NegativeContextScope.FILE


def test_scope_from_finding_module_when_no_file_path() -> None:
    f = _make_finding(file_path=None, related_files=[])
    scope = _scope_from_finding(f)
    assert scope == NegativeContextScope.MODULE


# ---------------------------------------------------------------------------
# _gen_ecd — exception_contract_drift with diverged_functions
# ---------------------------------------------------------------------------

def test_gen_ecd_with_diverged_functions() -> None:
    f = _make_finding(
        signal=SignalType.EXCEPTION_CONTRACT_DRIFT,
        metadata={
            "module": "src.my_module",
            "exception_types": ["ValueError", "RuntimeError"],
            "diverged_functions": ["do_thing", "do_other"],
            "divergence_count": 2,
            "module_function_count": 5,
            "comparison_ref": "HEAD~1",
        },
    )
    results = findings_to_negative_context([f])
    assert len(results) >= 1
    nc = results[0]
    assert "do_thing" in nc.description or "do_thing" in (nc.forbidden_pattern or "")
    assert "HEAD~1" in nc.description or "HEAD~1" in (nc.forbidden_pattern or "")


def test_gen_ecd_without_diverged_functions() -> None:
    f = _make_finding(
        signal=SignalType.EXCEPTION_CONTRACT_DRIFT,
        metadata={
            "module": "src.other_module",
            "exception_types": ["ValueError"],
        },
    )
    results = findings_to_negative_context([f])
    assert len(results) >= 1
    nc = results[0]
    assert nc.source_signal == SignalType.EXCEPTION_CONTRACT_DRIFT


# ---------------------------------------------------------------------------
# _gen_hsc — hardcoded_secret with placeholder_secret rule_id
# ---------------------------------------------------------------------------

def test_gen_hsc_placeholder_secret_rule() -> None:
    f = _make_finding(
        signal=SignalType.HARDCODED_SECRET,
        metadata={
            "rule_id": "placeholder_secret",
            "variable": "API_KEY",
            "cwe": "CWE-798",
        },
    )
    results = findings_to_negative_context([f])
    assert len(results) >= 1
    nc = results[0]
    assert nc.source_signal == SignalType.HARDCODED_SECRET
    assert "placeholder" in nc.description.lower() or "placeholder" in (
        nc.forbidden_pattern or ""
    ).lower()


def test_gen_hsc_hardcoded_api_token_rule() -> None:
    f = _make_finding(
        signal=SignalType.HARDCODED_SECRET,
        metadata={
            "rule_id": "hardcoded_api_token",
            "variable": "SECRET_KEY",
            "cwe": "CWE-798",
        },
    )
    results = findings_to_negative_context([f])
    assert len(results) >= 1
    nc = results[0]
    assert "api token" in nc.description.lower() or "token" in (nc.forbidden_pattern or "").lower()


def test_gen_hsc_default_rule() -> None:
    f = _make_finding(
        signal=SignalType.HARDCODED_SECRET,
        metadata={
            "rule_id": "generic_secret",
            "variable": "DB_PASSWORD",
        },
    )
    results = findings_to_negative_context([f])
    assert len(results) >= 1
    nc = results[0]
    assert nc.source_signal == SignalType.HARDCODED_SECRET


# ---------------------------------------------------------------------------
# scope filtering in findings_to_negative_context
# ---------------------------------------------------------------------------

def test_scope_filter_returns_only_matching_scope() -> None:
    f = _make_finding(
        signal=SignalType.EXCEPTION_CONTRACT_DRIFT,
        file_path="src/foo.py",
        related_files=[],
        metadata={"module": "src.m", "exception_types": ["E"]},
    )
    results = findings_to_negative_context([f], scope="file")
    # All returned items should be FILE scope
    file_results = [r for r in results if r.scope == NegativeContextScope.FILE]
    assert len(file_results) == len(results)


def test_scope_filter_invalid_scope_ignored() -> None:
    f = _make_finding(
        signal=SignalType.EXCEPTION_CONTRACT_DRIFT,
        metadata={"module": "src.m", "exception_types": ["E"]},
    )
    results = findings_to_negative_context([f], scope="unknown_scope_xyz")
    # Invalid scope is ignored — results not filtered out
    assert len(results) >= 1


# ---------------------------------------------------------------------------
# target_file filtering
# ---------------------------------------------------------------------------

def test_target_file_filter_keeps_matching() -> None:
    f = _make_finding(
        signal=SignalType.EXCEPTION_CONTRACT_DRIFT,
        file_path="src/foo.py",
        metadata={"module": "src.m", "exception_types": ["E"]},
    )
    results = findings_to_negative_context([f], target_file="src/foo.py")
    # Result should include items where src/foo.py is in affected_files
    assert all("src/foo.py" in r.affected_files for r in results)


def test_target_file_filter_removes_nonmatching() -> None:
    f = _make_finding(
        signal=SignalType.EXCEPTION_CONTRACT_DRIFT,
        file_path="src/other.py",
        metadata={"module": "src.m", "exception_types": ["E"]},
    )
    results = findings_to_negative_context([f], target_file="src/totally_different.py")
    # No results because target_file doesn't match
    assert len(results) == 0


# ---------------------------------------------------------------------------
# deduplication (seen_ids)
# ---------------------------------------------------------------------------

def test_deduplication_drops_duplicate_findings() -> None:
    f = _make_finding(
        signal=SignalType.EXCEPTION_CONTRACT_DRIFT,
        metadata={"module": "src.m", "exception_types": ["E"]},
    )
    # Duplicate finding is identical → same anti_pattern_id
    results = findings_to_negative_context([f, f])
    assert len(results) == 1
