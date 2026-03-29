"""Tests for Dead Code Accumulation signal (DCA)."""

from __future__ import annotations

from pathlib import Path

from drift.config import DriftConfig
from drift.models import ClassInfo, FunctionInfo, ImportInfo, ParseResult, SignalType
from drift.signals.dead_code_accumulation import DeadCodeAccumulationSignal


def _func(name: str, file_path: str, line: int) -> FunctionInfo:
    return FunctionInfo(
        name=name,
        file_path=Path(file_path),
        start_line=line,
        end_line=line + 5,
        language="python",
        complexity=2,
        loc=6,
    )


def _cls(name: str, file_path: str, line: int) -> ClassInfo:
    return ClassInfo(
        name=name,
        file_path=Path(file_path),
        start_line=line,
        end_line=line + 10,
        language="python",
    )


def _imp(source: str, module: str, names: list[str], line: int = 1) -> ImportInfo:
    return ImportInfo(
        source_file=Path(source),
        imported_module=module,
        imported_names=names,
        line_number=line,
    )


class TestDCATruePositive:
    """Multiple unused public symbols should trigger DCA."""

    def test_unused_exports_detected(self) -> None:
        pr_dead = ParseResult(
            file_path=Path("services/legacy.py"),
            language="python",
            functions=[
                _func("unused_a", "services/legacy.py", 10),
                _func("unused_b", "services/legacy.py", 20),
                _func("used_c", "services/legacy.py", 30),
            ],
            classes=[
                _cls("UnusedClass", "services/legacy.py", 40),
            ],
            imports=[],
        )

        pr_consumer = ParseResult(
            file_path=Path("services/consumer.py"),
            language="python",
            functions=[_func("run", "services/consumer.py", 1)],
            imports=[_imp("services/consumer.py", "services.legacy", ["used_c"])],
        )

        signal = DeadCodeAccumulationSignal()
        findings = signal.analyze([pr_dead, pr_consumer], {}, DriftConfig())

        assert len(findings) == 1
        f = findings[0]
        assert f.signal_type == SignalType.DEAD_CODE_ACCUMULATION
        assert f.metadata["dead_count"] >= 2
        assert "unused_a" in str(f.metadata["dead_symbols"])


class TestDCATrueNegative:
    """Used exports should not trigger DCA."""

    def test_all_exports_used(self) -> None:
        pr_api = ParseResult(
            file_path=Path("api/public.py"),
            language="python",
            functions=[
                _func("create_user", "api/public.py", 10),
                _func("delete_user", "api/public.py", 20),
            ],
            classes=[
                _cls("UserDTO", "api/public.py", 30),
            ],
            imports=[],
        )

        pr_service = ParseResult(
            file_path=Path("services/user_service.py"),
            language="python",
            functions=[_func("process", "services/user_service.py", 1)],
            imports=[
                _imp(
                    "services/user_service.py",
                    "api.public",
                    ["create_user", "delete_user", "UserDTO"],
                ),
            ],
        )

        signal = DeadCodeAccumulationSignal()
        findings = signal.analyze([pr_api, pr_service], {}, DriftConfig())

        assert len(findings) == 0

    def test_dunder_init_excluded(self) -> None:
        """__init__.py re-exports are ignored by default."""
        pr_init = ParseResult(
            file_path=Path("pkg/__init__.py"),
            language="python",
            functions=[
                _func("exported_a", "pkg/__init__.py", 1),
                _func("exported_b", "pkg/__init__.py", 2),
            ],
            imports=[],
        )

        signal = DeadCodeAccumulationSignal()
        findings = signal.analyze([pr_init], {}, DriftConfig())

        assert len(findings) == 0
