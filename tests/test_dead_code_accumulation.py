"""Tests for Dead Code Accumulation signal (DCA)."""

from __future__ import annotations

from pathlib import Path

from drift.config import DriftConfig
from drift.models import ClassInfo, FunctionInfo, ImportInfo, ParseResult, SignalType
from drift.signals.dead_code_accumulation import DeadCodeAccumulationSignal


def _func(
    name: str,
    file_path: str,
    line: int,
    decorators: list[str] | None = None,
) -> FunctionInfo:
    return FunctionInfo(
        name=name,
        file_path=Path(file_path),
        start_line=line,
        end_line=line + 5,
        language="python",
        complexity=2,
        loc=6,
        decorators=decorators or [],
    )


def _cls(
    name: str,
    file_path: str,
    line: int,
    bases: list[str] | None = None,
) -> ClassInfo:
    return ClassInfo(
        name=name,
        file_path=Path(file_path),
        start_line=line,
        end_line=line + 10,
        language="python",
        bases=bases or [],
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

    def test_library_layout_marks_context_candidate(self) -> None:
        pr_lib = ParseResult(
            file_path=Path("src/mylib/contracts.py"),
            language="python",
            functions=[
                _func("validate_schema", "src/mylib/contracts.py", 10),
                _func("ensure_types", "src/mylib/contracts.py", 20),
            ],
            imports=[],
        )
        pr_other = ParseResult(
            file_path=Path("src/mylib/utils.py"),
            language="python",
            functions=[_func("helper", "src/mylib/utils.py", 5)],
            imports=[],
        )

        signal = DeadCodeAccumulationSignal()
        findings = signal.analyze([pr_lib, pr_other], {}, DriftConfig())

        assert len(findings) == 1
        assert findings[0].metadata.get("library_context_candidate") is True

    def test_internal_module_in_package_layout_is_still_reported(self) -> None:
        pr_pkg_init = ParseResult(
            file_path=Path("fastapi/__init__.py"),
            language="python",
            imports=[],
        )
        pr_internal = ParseResult(
            file_path=Path("fastapi/internal/lifecycle.py"),
            language="python",
            functions=[
                _func("build_state", "fastapi/internal/lifecycle.py", 10),
                _func("flush_state", "fastapi/internal/lifecycle.py", 20),
            ],
            imports=[],
        )

        signal = DeadCodeAccumulationSignal()
        findings = signal.analyze([pr_pkg_init, pr_internal], {}, DriftConfig())

        assert len(findings) == 1
        assert findings[0].metadata.get("dead_count") == 2


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

    def test_route_handlers_and_schema_classes_are_not_reported(self) -> None:
        """Framework route entry points should not be suggested for removal."""
        pr_router = ParseResult(
            file_path=Path("backend/api/routers/analytics.py"),
            language="python",
            functions=[
                _func(
                    "get_dashboard_data",
                    "backend/api/routers/analytics.py",
                    20,
                    decorators=["get"],
                ),
                _func(
                    "submit_telemetry",
                    "backend/api/routers/analytics.py",
                    40,
                    decorators=["post"],
                ),
            ],
            classes=[
                _cls(
                    "TelemetryBatch",
                    "backend/api/routers/analytics.py",
                    5,
                    bases=["BaseModel"],
                ),
                _cls(
                    "TelemetryEventSchema",
                    "backend/api/routers/analytics.py",
                    12,
                    bases=["BaseModel"],
                ),
            ],
            imports=[],
        )

        signal = DeadCodeAccumulationSignal()
        findings = signal.analyze([pr_router], {}, DriftConfig())

        assert len(findings) == 0

    def test_public_api_exports_in_package_layout_are_not_reported(self) -> None:
        pr_pkg_init = ParseResult(
            file_path=Path("fastapi/__init__.py"),
            language="python",
            imports=[],
        )
        pr_public = ParseResult(
            file_path=Path("fastapi/applications.py"),
            language="python",
            functions=[
                _func("build_openapi", "fastapi/applications.py", 12),
                _func("build_swagger_ui", "fastapi/applications.py", 26),
            ],
            imports=[],
        )

        signal = DeadCodeAccumulationSignal()
        findings = signal.analyze([pr_pkg_init, pr_public], {}, DriftConfig())

        assert len(findings) == 0

    def test_script_context_exports_are_not_reported(self) -> None:
        """Executable script paths should not be treated as import-style exports."""
        pr_script = ParseResult(
            file_path=Path(".github/workflows/python-check-coverage.py"),
            language="python",
            functions=[
                _func("collect_modules", ".github/workflows/python-check-coverage.py", 10),
                _func("calculate_coverage", ".github/workflows/python-check-coverage.py", 25),
                _func("main", ".github/workflows/python-check-coverage.py", 40),
            ],
            imports=[],
        )

        signal = DeadCodeAccumulationSignal()
        findings = signal.analyze([pr_script], {}, DriftConfig())

        assert len(findings) == 0
