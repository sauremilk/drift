"""Tests for Dead Code Accumulation signal (DCA)."""

from __future__ import annotations

from pathlib import Path

from drift.config import DriftConfig
from drift.models import ClassInfo, FunctionInfo, ImportInfo, ParseResult, Severity, SignalType
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


def _ts_exported_func(name: str, file_path: str, line: int) -> FunctionInfo:
    return FunctionInfo(
        name=name,
        file_path=Path(file_path),
        start_line=line,
        end_line=line + 3,
        language="typescript",
        complexity=1,
        loc=4,
        is_exported=True,
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

    def test_typescript_file_local_types_are_not_treated_as_exports(self) -> None:
        pr_translator = ParseResult(
            file_path=Path("src/acp/translator.ts"),
            language="typescript",
            classes=[
                ClassInfo(
                    name="DisconnectContext",
                    file_path=Path("src/acp/translator.ts"),
                    start_line=65,
                    end_line=68,
                    language="typescript",
                    is_interface=True,
                    is_exported=False,
                ),
                ClassInfo(
                    name="PendingPrompt",
                    file_path=Path("src/acp/translator.ts"),
                    start_line=70,
                    end_line=78,
                    language="typescript",
                    is_interface=True,
                    is_exported=False,
                ),
                ClassInfo(
                    name="AcpGatewayAgent",
                    file_path=Path("src/acp/translator.ts"),
                    start_line=411,
                    end_line=650,
                    language="typescript",
                    is_exported=True,
                ),
            ],
            imports=[],
        )

        pr_consumer = ParseResult(
            file_path=Path("src/acp/gateway.ts"),
            language="typescript",
            imports=[
                _imp(
                    "src/acp/gateway.ts",
                    "src/acp/translator",
                    ["AcpGatewayAgent"],
                )
            ],
        )

        findings = DeadCodeAccumulationSignal().analyze(
            [pr_translator, pr_consumer],
            {},
            DriftConfig(),
        )
        assert findings == []


class TestDCATestFileHandling:
    def test_test_file_is_reduced_not_excluded_by_default(self) -> None:
        pr_test = ParseResult(
            file_path=Path("tests/helpers.py"),
            language="python",
            functions=[
                _func("unused_a", "tests/helpers.py", 10),
                _func("unused_b", "tests/helpers.py", 20),
            ],
            imports=[],
        )

        findings = DeadCodeAccumulationSignal().analyze([pr_test], {}, DriftConfig())
        assert len(findings) == 1
        assert findings[0].severity == Severity.LOW
        assert findings[0].metadata.get("finding_context") == "test"

    def test_typescript_testkit_contract_file_is_reduced_to_low(self) -> None:
        pr_testkit = ParseResult(
            file_path=Path("src/acp/runtime/adapter-contract.testkit.ts"),
            language="typescript",
            functions=[
                _ts_exported_func(
                    "runAcpRuntimeAdapterContract",
                    "src/acp/runtime/adapter-contract.testkit.ts",
                    12,
                ),
                _ts_exported_func(
                    "buildAcpRuntimeAdapterContract",
                    "src/acp/runtime/adapter-contract.testkit.ts",
                    30,
                ),
            ],
            imports=[],
        )

        findings = DeadCodeAccumulationSignal().analyze([pr_testkit], {}, DriftConfig())

        assert len(findings) == 1
        assert findings[0].severity == Severity.LOW
        assert findings[0].score <= 0.39
        assert findings[0].metadata.get("testkit_contract_heuristic_applied") is True


class TestDCARuntimePluginConfigHeuristic:
    def test_extensions_config_file_is_dampened_to_medium(self) -> None:
        pr_cfg = ParseResult(
            file_path=Path("extensions/acpx/src/config.ts"),
            language="typescript",
            functions=[
                _ts_exported_func("resolveA", "extensions/acpx/src/config.ts", 10),
                _ts_exported_func("resolveB", "extensions/acpx/src/config.ts", 20),
                _ts_exported_func("resolveC", "extensions/acpx/src/config.ts", 30),
                _ts_exported_func("resolveD", "extensions/acpx/src/config.ts", 40),
            ],
            imports=[],
        )

        findings = DeadCodeAccumulationSignal().analyze([pr_cfg], {}, DriftConfig())
        assert len(findings) == 1
        assert findings[0].severity == Severity.MEDIUM
        assert findings[0].score <= 0.69
        assert findings[0].metadata.get("runtime_plugin_config_heuristic_applied") is True

    def test_extensions_non_config_file_is_dampened_to_low(self) -> None:
        pr_helpers = ParseResult(
            file_path=Path("extensions/acpx/src/helpers.ts"),
            language="typescript",
            functions=[
                _ts_exported_func("unusedA", "extensions/acpx/src/helpers.ts", 10),
                _ts_exported_func("unusedB", "extensions/acpx/src/helpers.ts", 20),
                _ts_exported_func("unusedC", "extensions/acpx/src/helpers.ts", 30),
                _ts_exported_func("unusedD", "extensions/acpx/src/helpers.ts", 40),
            ],
            imports=[],
        )

        findings = DeadCodeAccumulationSignal().analyze(
            [pr_helpers],
            {},
            DriftConfig(),
        )
        assert len(findings) == 1
        assert findings[0].severity == Severity.LOW
        assert findings[0].score <= 0.39
        assert findings[0].metadata.get("runtime_plugin_config_heuristic_applied") is False
        assert (
            findings[0].metadata.get("runtime_plugin_workspace_heuristic_applied")
            is True
        )

    def test_non_plugin_file_keeps_high_without_workspace_heuristic(self) -> None:
        pr_helpers = ParseResult(
            file_path=Path("packages/acpx/src/helpers.ts"),
            language="typescript",
            functions=[
                _ts_exported_func("unusedA", "packages/acpx/src/helpers.ts", 10),
                _ts_exported_func("unusedB", "packages/acpx/src/helpers.ts", 20),
                _ts_exported_func("unusedC", "packages/acpx/src/helpers.ts", 30),
                _ts_exported_func("unusedD", "packages/acpx/src/helpers.ts", 40),
            ],
            imports=[],
        )

        findings = DeadCodeAccumulationSignal().analyze([pr_helpers], {}, DriftConfig())
        assert len(findings) == 1
        assert findings[0].severity == Severity.HIGH
        assert (
            findings[0].metadata.get("runtime_plugin_workspace_heuristic_applied")
            is False
        )


class TestDCARuntimePluginEntrypointHeuristic:
    def test_extensions_components_entrypoint_is_dampened_to_medium(self) -> None:
        pr_components = ParseResult(
            file_path=Path("extensions/discord/src/components.ts"),
            language="typescript",
            functions=[
                _ts_exported_func("resolveA", "extensions/discord/src/components.ts", 10),
                _ts_exported_func("resolveB", "extensions/discord/src/components.ts", 20),
                _ts_exported_func("resolveC", "extensions/discord/src/components.ts", 30),
                _ts_exported_func("resolveD", "extensions/discord/src/components.ts", 40),
            ],
            imports=[],
        )

        findings = DeadCodeAccumulationSignal().analyze(
            [pr_components],
            {},
            DriftConfig(),
        )
        assert len(findings) == 1
        assert findings[0].severity == Severity.MEDIUM
        assert findings[0].score <= 0.69
        assert findings[0].metadata.get("runtime_plugin_config_heuristic_applied") is False
        assert (
            findings[0].metadata.get("runtime_plugin_entrypoint_heuristic_applied")
            is True
        )


class TestDCARuntimePluginWorkspaceHeuristic:
    def test_nested_dotpi_extensions_file_is_dampened_to_low(self) -> None:
        pr_nested = ParseResult(
            file_path=Path(".pi/extensions/files.ts"),
            language="typescript",
            functions=[
                _ts_exported_func("FileEntry", ".pi/extensions/files.ts", 10),
                _ts_exported_func("FileToolName", ".pi/extensions/files.ts", 20),
                _ts_exported_func("FileToolMeta", ".pi/extensions/files.ts", 30),
                _ts_exported_func("FileHandle", ".pi/extensions/files.ts", 40),
            ],
            imports=[],
        )

        findings = DeadCodeAccumulationSignal().analyze([pr_nested], {}, DriftConfig())
        assert len(findings) == 1
        assert findings[0].severity == Severity.LOW
        assert findings[0].score <= 0.39
        assert (
            findings[0].metadata.get("runtime_plugin_workspace_heuristic_applied")
            is True
        )
        assert findings[0].metadata.get("library_context_candidate") is True

    def test_extensions_plugin_sdk_entrypoint_is_dampened_to_medium(self) -> None:
        pr_sdk = ParseResult(
            file_path=Path("extensions/copilot-hub/src/plugin-sdk/core.ts"),
            language="typescript",
            functions=[
                _ts_exported_func(
                    "createClient",
                    "extensions/copilot-hub/src/plugin-sdk/core.ts",
                    10,
                ),
                _ts_exported_func(
                    "resolveSession",
                    "extensions/copilot-hub/src/plugin-sdk/core.ts",
                    20,
                ),
                _ts_exported_func(
                    "buildRuntime",
                    "extensions/copilot-hub/src/plugin-sdk/core.ts",
                    30,
                ),
                _ts_exported_func(
                    "registerCore",
                    "extensions/copilot-hub/src/plugin-sdk/core.ts",
                    40,
                ),
            ],
            imports=[],
        )

        findings = DeadCodeAccumulationSignal().analyze([pr_sdk], {}, DriftConfig())
        assert len(findings) == 1
        assert findings[0].severity == Severity.MEDIUM
        assert findings[0].score <= 0.69
        assert (
            findings[0].metadata.get("runtime_plugin_entrypoint_heuristic_applied")
            is True
        )
