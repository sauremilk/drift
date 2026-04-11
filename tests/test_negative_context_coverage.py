"""Coverage tests for negative_context generators and helpers."""

from __future__ import annotations

from pathlib import Path

# Re-import the generators indirectly to trigger registration
import drift.negative_context  # noqa: F401
from drift.models import Finding, Severity, SignalType
from drift.negative_context import (
    _neg_id,
    findings_to_negative_context,
)
from drift.negative_context.core import (
    _affected,
    _scope_from_finding,
)

# ---------------------------------------------------------------------------
# Finding factory
# ---------------------------------------------------------------------------


def _finding(
    signal: str = SignalType.ARCHITECTURE_VIOLATION,
    *,
    file_path: str | None = "src/foo.py",
    related: list[str] | None = None,
    metadata: dict | None = None,
    score: float = 0.7,
    severity: Severity = Severity.HIGH,
    symbol: str | None = None,
    title: str = "test finding",
    description: str = "desc",
    fix: str | None = None,
    start_line: int | None = None,
) -> Finding:
    return Finding(
        signal_type=signal,
        severity=severity,
        score=score,
        title=title,
        description=description,
        file_path=Path(file_path) if file_path else None,
        related_files=[Path(r) for r in related] if related else [],
        metadata=metadata or {},
        symbol=symbol,
        fix=fix,
        start_line=start_line,
    )


# ---------------------------------------------------------------------------
# _neg_id
# ---------------------------------------------------------------------------


class TestNegId:
    def test_deterministic(self):
        f = _finding()
        assert _neg_id("AVS", f) == _neg_id("AVS", f)

    def test_different_signal_different_id(self):
        f = _finding()
        assert _neg_id("AVS", f) != _neg_id("XYZ", f)

    def test_no_file_path(self):
        f = _finding(file_path=None)
        result = _neg_id("AVS", f)
        assert result.startswith("neg-AVS-")

    def test_format(self):
        f = _finding()
        result = _neg_id("AVS", f)
        assert result.startswith("neg-AVS-")
        # hash part is 10 chars
        assert len(result.split("-", 2)[-1]) == 10


# ---------------------------------------------------------------------------
# _affected
# ---------------------------------------------------------------------------


class TestAffected:
    def test_file_path_only(self):
        f = _finding(file_path="src/a.py")
        assert _affected(f) == ["src/a.py"]

    def test_with_affected_files_metadata(self):
        f = _finding(
            file_path="src/a.py",
            metadata={"affected_files": ["src/b.py", "src/c.py"]},
        )
        result = _affected(f)
        assert result == ["src/a.py", "src/b.py", "src/c.py"]

    def test_no_file_path(self):
        f = _finding(file_path=None, metadata={"affected_files": ["src/b.py"]})
        result = _affected(f)
        assert result == ["src/b.py"]

    def test_dedup(self):
        f = _finding(
            file_path="src/a.py",
            metadata={"affected_files": ["src/a.py", "src/b.py"]},
        )
        result = _affected(f)
        # src/a.py already present from file_path, should not be duplicated
        assert result == ["src/a.py", "src/b.py"]


# ---------------------------------------------------------------------------
# _scope_from_finding
# ---------------------------------------------------------------------------


class TestScopeFromFinding:
    def test_file_scope(self):
        from drift.models import NegativeContextScope

        f = _finding(file_path="src/a.py")
        assert _scope_from_finding(f) == NegativeContextScope.FILE

    def test_module_scope_no_file(self):
        from drift.models import NegativeContextScope

        f = _finding(file_path=None)
        assert _scope_from_finding(f) == NegativeContextScope.MODULE


# ---------------------------------------------------------------------------
# ECD generator
# ---------------------------------------------------------------------------


class TestEcdGenerator:
    def test_with_diverged_fns_and_comparison_ref(self):
        f = _finding(
            signal=SignalType.EXCEPTION_CONTRACT_DRIFT,
            metadata={
                "exception_types": ["ValueError", "TypeError"],
                "module": "drift.foo",
                "diverged_functions": ["fn_a", "fn_b"],
                "divergence_count": 2,
                "comparison_ref": "v1.0",
                "module_function_count": 10,
            },
        )
        results = findings_to_negative_context([f])
        assert len(results) >= 1
        ctx = results[0]
        assert "fn_a" in ctx.forbidden_pattern
        assert "v1.0" in ctx.description
        assert ctx.confidence == 0.85

    def test_without_diverged_fns(self):
        f = _finding(
            signal=SignalType.EXCEPTION_CONTRACT_DRIFT,
            metadata={
                "exception_types": ["RuntimeError"],
                "module": "drift.bar",
            },
        )
        results = findings_to_negative_context([f])
        assert len(results) >= 1
        ctx = results[0]
        assert "Introducing a new exception type" in ctx.forbidden_pattern
        assert ctx.confidence == 0.8


# ---------------------------------------------------------------------------
# AVS (BEM) generator
# ---------------------------------------------------------------------------


class TestAvsGenerator:
    def test_with_all_metadata(self):
        f = _finding(
            signal=SignalType.ARCHITECTURE_VIOLATION,
            metadata={
                "src_layer": "ui",
                "dst_layer": "infra",
                "rule": "no-ui-to-infra",
                "import": "infra.db",
                "blast_radius": 5,
                "instability": 0.8,
            },
        )
        results = findings_to_negative_context([f])
        assert len(results) >= 1
        ctx = results[0]
        assert "import infra.db" in ctx.forbidden_pattern
        assert "instability=0.80" in ctx.canonical_alternative
        assert ctx.confidence == 0.90

    def test_without_import_path(self):
        f = _finding(
            signal=SignalType.ARCHITECTURE_VIOLATION,
            metadata={
                "src_layer": "api",
                "dst_layer": "core",
            },
        )
        results = findings_to_negative_context([f])
        assert len(results) >= 1
        ctx = results[0]
        assert "from core import" in ctx.forbidden_pattern
        assert ctx.confidence == 0.85


# ---------------------------------------------------------------------------
# CCC generator
# ---------------------------------------------------------------------------


class TestCccGenerator:
    def test_with_co_change_weight_and_samples(self):
        f = _finding(
            signal=SignalType.CO_CHANGE_COUPLING,
            metadata={
                "file_a": "src/a.py",
                "file_b": "src/b.py",
                "co_change_weight": 3.5,
                "confidence": 0.9,
                "commit_samples": ["abc1234", "def5678", "ghi9012", "jkl3456"],
                "coupled_files": [],
            },
        )
        results = findings_to_negative_context([f])
        assert len(results) >= 1
        ctx = results[0]
        assert "3.5" in ctx.description
        assert "Evidence" in ctx.canonical_alternative
        assert ctx.metadata.get("co_change_weight") == 3.5

    def test_without_optional_fields(self):
        f = _finding(
            signal=SignalType.CO_CHANGE_COUPLING,
            file_path="src/a.py",
            metadata={},
        )
        results = findings_to_negative_context([f])
        assert len(results) >= 1
        ctx = results[0]
        assert "related files" in ctx.description


# ---------------------------------------------------------------------------
# HSC generator
# ---------------------------------------------------------------------------


class TestHscGenerator:
    def test_hardcoded_api_token(self):
        f = _finding(
            signal=SignalType.HARDCODED_SECRET,
            file_path="src/config.py",
            start_line=42,
            metadata={
                "variable": "API_KEY",
                "rule_id": "hardcoded_api_token",
                "cwe": "CWE-798",
            },
        )
        results = findings_to_negative_context([f])
        ctx = results[0]
        assert "API token" in ctx.forbidden_pattern
        assert "L42" in ctx.forbidden_pattern

    def test_placeholder_secret(self):
        f = _finding(
            signal=SignalType.HARDCODED_SECRET,
            metadata={
                "variable": "DB_PASS",
                "rule_id": "placeholder_secret",
            },
        )
        results = findings_to_negative_context([f])
        ctx = results[0]
        assert "changeme" in ctx.forbidden_pattern

    def test_default_rule_id(self):
        f = _finding(
            signal=SignalType.HARDCODED_SECRET,
            metadata={"variable": "TOKEN"},
        )
        results = findings_to_negative_context([f])
        ctx = results[0]
        assert "Hardcoded credentials" in ctx.forbidden_pattern

    def test_no_file_path_no_file_ref(self):
        f = _finding(
            signal=SignalType.HARDCODED_SECRET,
            file_path=None,
            metadata={"variable": "X", "rule_id": "hardcoded_api_token"},
        )
        results = findings_to_negative_context([f])
        ctx = results[0]
        # No file ref appended
        assert "L" not in ctx.forbidden_pattern or "NEVER" in ctx.forbidden_pattern
