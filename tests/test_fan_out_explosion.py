"""Tests for Fan-Out Explosion signal (FOE)."""

from __future__ import annotations

from pathlib import Path

from drift.config import DriftConfig
from drift.models import ImportInfo, ParseResult, SignalType
from drift.signals.fan_out_explosion import FanOutExplosionSignal


def _imp(source: str, module: str, line: int = 1) -> ImportInfo:
    return ImportInfo(
        source_file=Path(source),
        imported_module=module,
        imported_names=[module.split(".")[-1]],
        line_number=line,
    )


def _pr(
    file_path: str,
    imports: list[ImportInfo],
    *,
    language: str = "python",
) -> ParseResult:
    return ParseResult(
        file_path=Path(file_path),
        language=language,
        imports=imports,
    )


class TestFOETruePositive:
    """File with excessive imports should trigger a finding."""

    def test_many_imports_detected(self) -> None:
        path = "services/monolith.py"
        imports = [
            _imp(path, f"package_{i}.module_{i}")
            for i in range(25)
        ]
        pr = _pr(path, imports)

        signal = FanOutExplosionSignal()
        findings = signal.analyze([pr], {}, DriftConfig())

        assert len(findings) == 1
        f = findings[0]
        assert f.signal_type == SignalType.FAN_OUT_EXPLOSION
        assert f.metadata["unique_import_count"] >= 20
        assert f.score > 0.3

    def test_score_increases_with_more_imports(self) -> None:
        path = "services/hub.py"
        imports_20 = [_imp(path, f"mod_{i}") for i in range(20)]
        imports_40 = [_imp(path, f"mod_{i}") for i in range(40)]

        signal = FanOutExplosionSignal()
        findings_20 = signal.analyze([_pr(path, imports_20)], {}, DriftConfig())
        findings_40 = signal.analyze([_pr(path, imports_40)], {}, DriftConfig())

        assert findings_20[0].score < findings_40[0].score


class TestFOETrueNegative:
    """File with few imports should not trigger."""

    def test_few_imports_not_detected(self) -> None:
        path = "services/clean.py"
        imports = [
            _imp(path, "os"),
            _imp(path, "sys"),
            _imp(path, "pathlib"),
        ]
        pr = _pr(path, imports)

        signal = FanOutExplosionSignal()
        findings = signal.analyze([pr], {}, DriftConfig())

        assert len(findings) == 0

    def test_init_file_excluded(self) -> None:
        """__init__.py files are barrel files — high fan-out is expected."""
        path = "services/__init__.py"
        imports = [_imp(path, f"mod_{i}") for i in range(30)]
        pr = _pr(path, imports)

        signal = FanOutExplosionSignal()
        findings = signal.analyze([pr], {}, DriftConfig())

        assert len(findings) == 0

    def test_test_files_excluded(self) -> None:
        path = "tests/test_integration.py"
        imports = [_imp(path, f"mod_{i}") for i in range(30)]
        pr = _pr(path, imports)

        signal = FanOutExplosionSignal()
        findings = signal.analyze([pr], {}, DriftConfig())

        assert len(findings) == 0
