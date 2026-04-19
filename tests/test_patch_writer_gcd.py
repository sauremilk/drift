"""Tests for AddGuardClauseWriter (GCD / add_guard_clause) — TDD RED-GREEN."""

from __future__ import annotations

from pathlib import Path

import pytest

from drift.fix_intent import EDIT_KIND_ADD_GUARD_CLAUSE
from drift.models import Finding, Severity
from drift.patch_writer import PatchResult, PatchResultStatus, get_writer
from tests.fixtures.patch_writer import (
    GCD_EXPECTED_WITH_GUARD_BOTH,
    GCD_EXPECTED_WITH_GUARD_ORDER,
    GCD_MISSING_GUARD_SOURCE,
    GCD_PARTIAL_EXPECTED_SECOND_GUARD,
    GCD_PARTIAL_GUARD,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_finding(
    symbol: str = "process_order",
    start_line: int = 1,
    file_path: str = "src/orders.py",
    language: str = "python",
    guard_params: list[str] | None = None,
) -> Finding:
    return Finding(
        signal_type="guard_clause_deficit",
        severity=Severity.MEDIUM,
        score=0.5,
        title="Missing guard clauses",
        description="Function lacks input validation.",
        file_path=Path(file_path),
        start_line=start_line,
        symbol=symbol,
        language=language,
        metadata={
            "edit_kind": EDIT_KIND_ADD_GUARD_CLAUSE,
            "guard_params": guard_params if guard_params is not None else ["order"],
        },
    )


# ---------------------------------------------------------------------------
# Registry lookup
# ---------------------------------------------------------------------------


def test_get_writer_returns_add_guard_clause_writer() -> None:
    writer = get_writer(EDIT_KIND_ADD_GUARD_CLAUSE)
    assert writer is not None
    assert writer.edit_kind == EDIT_KIND_ADD_GUARD_CLAUSE


# ---------------------------------------------------------------------------
# can_write
# ---------------------------------------------------------------------------


def test_can_write_python_finding() -> None:
    writer = get_writer(EDIT_KIND_ADD_GUARD_CLAUSE)
    assert writer is not None
    assert writer.can_write(_make_finding()) is True


def test_can_write_rejects_non_python() -> None:
    writer = get_writer(EDIT_KIND_ADD_GUARD_CLAUSE)
    assert writer is not None
    assert writer.can_write(_make_finding(language="typescript")) is False


def test_can_write_rejects_missing_symbol() -> None:
    writer = get_writer(EDIT_KIND_ADD_GUARD_CLAUSE)
    assert writer is not None
    f = _make_finding()
    f.symbol = None  # type: ignore[assignment]
    assert writer.can_write(f) is False


def test_can_write_rejects_no_guard_params() -> None:
    writer = get_writer(EDIT_KIND_ADD_GUARD_CLAUSE)
    assert writer is not None
    f = _make_finding(guard_params=[])
    assert writer.can_write(f) is False


# ---------------------------------------------------------------------------
# generate_patch — GENERATED for first param
# ---------------------------------------------------------------------------


def test_generate_patch_inserts_guard_for_one_param() -> None:
    writer = get_writer(EDIT_KIND_ADD_GUARD_CLAUSE)
    assert writer is not None
    finding = _make_finding(guard_params=["order"])

    result = writer.generate_patch(finding, GCD_MISSING_GUARD_SOURCE)

    assert result.status == PatchResultStatus.GENERATED
    assert result.patched_source == GCD_EXPECTED_WITH_GUARD_ORDER
    assert result.diff


def test_generate_patch_inserts_guards_for_two_params() -> None:
    writer = get_writer(EDIT_KIND_ADD_GUARD_CLAUSE)
    assert writer is not None
    finding = _make_finding(guard_params=["order", "user"])

    result = writer.generate_patch(finding, GCD_MISSING_GUARD_SOURCE)

    assert result.status == PatchResultStatus.GENERATED
    assert result.patched_source == GCD_EXPECTED_WITH_GUARD_BOTH


# ---------------------------------------------------------------------------
# generate_patch — partial guard (one param already guarded)
# ---------------------------------------------------------------------------


def test_generate_patch_adds_missing_guard_when_one_exists() -> None:
    writer = get_writer(EDIT_KIND_ADD_GUARD_CLAUSE)
    assert writer is not None
    finding = _make_finding(guard_params=["user"])

    result = writer.generate_patch(finding, GCD_PARTIAL_GUARD)

    assert result.status == PatchResultStatus.GENERATED
    assert result.patched_source == GCD_PARTIAL_EXPECTED_SECOND_GUARD


# ---------------------------------------------------------------------------
# generate_patch — SKIPPED when all params already guarded
# ---------------------------------------------------------------------------


def test_generate_patch_skipped_when_all_params_guarded() -> None:
    writer = get_writer(EDIT_KIND_ADD_GUARD_CLAUSE)
    assert writer is not None
    finding = _make_finding(guard_params=["order"])

    # GCD_PARTIAL_GUARD already has a guard for "order"
    result = writer.generate_patch(finding, GCD_PARTIAL_GUARD)

    assert result.status == PatchResultStatus.SKIPPED
    assert not result.diff


# ---------------------------------------------------------------------------
# generate_patch — UNSUPPORTED for non-Python
# ---------------------------------------------------------------------------


def test_generate_patch_unsupported_for_non_python() -> None:
    writer = get_writer(EDIT_KIND_ADD_GUARD_CLAUSE)
    assert writer is not None
    finding = _make_finding(language="typescript")

    result = writer.generate_patch(finding, "function foo(x) { return x; }")

    assert result.status == PatchResultStatus.UNSUPPORTED


# ---------------------------------------------------------------------------
# PatchResult fields
# ---------------------------------------------------------------------------


def test_patch_result_has_original_source() -> None:
    writer = get_writer(EDIT_KIND_ADD_GUARD_CLAUSE)
    assert writer is not None
    finding = _make_finding(guard_params=["order"])

    result = writer.generate_patch(finding, GCD_MISSING_GUARD_SOURCE)

    assert result.original_source == GCD_MISSING_GUARD_SOURCE
    assert result.file_path == Path("src/orders.py")
    assert result.edit_kind == EDIT_KIND_ADD_GUARD_CLAUSE
