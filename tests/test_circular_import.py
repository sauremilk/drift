"""Tests for Circular Import signal (CID)."""

from __future__ import annotations

from pathlib import Path

from drift.config import DriftConfig
from drift.models import ImportInfo, ParseResult, SignalType
from drift.signals.circular_import import CircularImportSignal


def _imp(source: str, module: str, line: int = 1) -> ImportInfo:
    return ImportInfo(
        source_file=Path(source),
        imported_module=module,
        imported_names=[module.split(".")[-1]],
        line_number=line,
    )


def _pr(path: str, imports: list[ImportInfo]) -> ParseResult:
    return ParseResult(
        file_path=Path(path),
        language="python",
        imports=imports,
    )


class TestCIDTruePositive:
    """Circular import chain should be detected."""

    def test_simple_two_module_cycle(self) -> None:
        # a -> b -> a
        a = _pr("pkg/a.py", [_imp("pkg/a.py", "pkg.b")])
        b = _pr("pkg/b.py", [_imp("pkg/b.py", "pkg.a")])

        signal = CircularImportSignal()
        findings = signal.analyze([a, b], {}, DriftConfig())

        assert len(findings) == 1
        f = findings[0]
        assert f.signal_type == SignalType.CIRCULAR_IMPORT
        assert f.metadata["cycle_length"] == 2
        assert set(f.metadata["cycle_modules"]) == {"pkg.a", "pkg.b"}

    def test_three_module_cycle(self) -> None:
        # a -> b -> c -> a
        a = _pr("pkg/a.py", [_imp("pkg/a.py", "pkg.b")])
        b = _pr("pkg/b.py", [_imp("pkg/b.py", "pkg.c")])
        c = _pr("pkg/c.py", [_imp("pkg/c.py", "pkg.a")])

        signal = CircularImportSignal()
        findings = signal.analyze([a, b, c], {}, DriftConfig())

        assert len(findings) == 1
        f = findings[0]
        assert f.metadata["cycle_length"] == 3


class TestCIDTrueNegative:
    """Acyclic imports should not be flagged."""

    def test_acyclic_graph_not_detected(self) -> None:
        # a -> b -> c (no cycle)
        a = _pr("pkg/a.py", [_imp("pkg/a.py", "pkg.b")])
        b = _pr("pkg/b.py", [_imp("pkg/b.py", "pkg.c")])
        c = _pr("pkg/c.py", [])

        signal = CircularImportSignal()
        findings = signal.analyze([a, b, c], {}, DriftConfig())

        assert len(findings) == 0

    def test_external_imports_ignored(self) -> None:
        a = _pr("pkg/a.py", [_imp("pkg/a.py", "numpy")])
        b = _pr("pkg/b.py", [_imp("pkg/b.py", "requests")])

        signal = CircularImportSignal()
        findings = signal.analyze([a, b], {}, DriftConfig())

        assert len(findings) == 0
