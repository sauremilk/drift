"""Tests for AddDocstringWriter (EDS / add_docstring) — TDD RED-GREEN."""

from __future__ import annotations

from pathlib import Path

import pytest

from drift.fix_intent import EDIT_KIND_ADD_DOCSTRING
from drift.models import Finding, Severity
from drift.patch_writer import PatchResult, PatchResultStatus, get_writer
from tests.fixtures.patch_writer import (
    EDS_ALREADY_HAS_DOCSTRING,
    EDS_ASYNC_EXPECTED_WITH_DOCSTRING,
    EDS_ASYNC_MISSING_DOCSTRING,
    EDS_EXPECTED_WITH_DOCSTRING,
    EDS_MISSING_DOCSTRING_SOURCE,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.skipif(
    False, reason=""  # never skip — libcst required for these tests
)


def _make_finding(
    symbol: str = "compute_total",
    start_line: int = 1,
    file_path: str = "src/module.py",
    language: str = "python",
) -> Finding:
    return Finding(
        signal_type="explainability_deficit",
        severity=Severity.MEDIUM,
        score=0.6,
        title="Missing docstring",
        description="Function lacks docstring.",
        file_path=Path(file_path),
        start_line=start_line,
        symbol=symbol,
        language=language,
        metadata={"edit_kind": EDIT_KIND_ADD_DOCSTRING},
    )


# ---------------------------------------------------------------------------
# Registry lookup
# ---------------------------------------------------------------------------


def test_get_writer_returns_add_docstring_writer() -> None:
    writer = get_writer(EDIT_KIND_ADD_DOCSTRING)
    assert writer is not None
    assert writer.edit_kind == EDIT_KIND_ADD_DOCSTRING


def test_get_writer_unknown_edit_kind_returns_none() -> None:
    assert get_writer("unknown_edit_kind_xyz") is None


# ---------------------------------------------------------------------------
# can_write
# ---------------------------------------------------------------------------


def test_can_write_python_finding() -> None:
    writer = get_writer(EDIT_KIND_ADD_DOCSTRING)
    assert writer is not None
    finding = _make_finding(language="python")
    assert writer.can_write(finding) is True


def test_can_write_rejects_non_python() -> None:
    writer = get_writer(EDIT_KIND_ADD_DOCSTRING)
    assert writer is not None
    finding = _make_finding(language="typescript")
    assert writer.can_write(finding) is False


def test_can_write_rejects_missing_symbol() -> None:
    writer = get_writer(EDIT_KIND_ADD_DOCSTRING)
    assert writer is not None
    finding = _make_finding()
    finding.symbol = None  # type: ignore[assignment]
    assert writer.can_write(finding) is False


# ---------------------------------------------------------------------------
# generate_patch — GENERATED status
# ---------------------------------------------------------------------------


def test_generate_patch_inserts_docstring() -> None:
    writer = get_writer(EDIT_KIND_ADD_DOCSTRING)
    assert writer is not None
    finding = _make_finding(symbol="compute_total", start_line=1)

    result = writer.generate_patch(finding, EDS_MISSING_DOCSTRING_SOURCE)

    assert result.status == PatchResultStatus.GENERATED
    assert result.patched_source == EDS_EXPECTED_WITH_DOCSTRING
    assert "TODO: document compute_total" in (result.patched_source or "")
    assert result.diff  # non-empty diff


def test_generate_patch_inserts_docstring_async_function() -> None:
    writer = get_writer(EDIT_KIND_ADD_DOCSTRING)
    assert writer is not None
    finding = _make_finding(symbol="fetch_user", start_line=1)

    result = writer.generate_patch(finding, EDS_ASYNC_MISSING_DOCSTRING)

    assert result.status == PatchResultStatus.GENERATED
    assert result.patched_source == EDS_ASYNC_EXPECTED_WITH_DOCSTRING


def test_generate_patch_diff_is_unified_diff() -> None:
    writer = get_writer(EDIT_KIND_ADD_DOCSTRING)
    assert writer is not None
    finding = _make_finding(symbol="compute_total", start_line=1)

    result = writer.generate_patch(finding, EDS_MISSING_DOCSTRING_SOURCE)

    assert result.diff.startswith("---") or result.diff.startswith("@@")


# ---------------------------------------------------------------------------
# generate_patch — SKIPPED status (already has docstring)
# ---------------------------------------------------------------------------


def test_generate_patch_skipped_when_docstring_exists() -> None:
    writer = get_writer(EDIT_KIND_ADD_DOCSTRING)
    assert writer is not None
    finding = _make_finding(symbol="compute_total", start_line=1)

    result = writer.generate_patch(finding, EDS_ALREADY_HAS_DOCSTRING)

    assert result.status == PatchResultStatus.SKIPPED
    assert not result.diff


# ---------------------------------------------------------------------------
# generate_patch — UNSUPPORTED for non-Python
# ---------------------------------------------------------------------------


def test_generate_patch_unsupported_for_non_python() -> None:
    writer = get_writer(EDIT_KIND_ADD_DOCSTRING)
    assert writer is not None
    finding = _make_finding(language="typescript")

    result = writer.generate_patch(finding, "const x = 1;")

    assert result.status == PatchResultStatus.UNSUPPORTED


# ---------------------------------------------------------------------------
# PatchResult fields
# ---------------------------------------------------------------------------


def test_patch_result_preserves_original_source() -> None:
    writer = get_writer(EDIT_KIND_ADD_DOCSTRING)
    assert writer is not None
    finding = _make_finding(symbol="compute_total", start_line=1)

    result = writer.generate_patch(finding, EDS_MISSING_DOCSTRING_SOURCE)

    assert result.original_source == EDS_MISSING_DOCSTRING_SOURCE
    assert result.file_path == Path("src/module.py")
    assert result.edit_kind == EDIT_KIND_ADD_DOCSTRING
