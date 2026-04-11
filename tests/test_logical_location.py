"""Tests for logical_location enrichment (ADR-039)."""

from __future__ import annotations

from pathlib import Path

from drift.logical_location import (
    _build_location_index,
    _file_path_to_namespace,
    enrich_logical_locations,
)
from drift.models import (
    ClassInfo,
    Finding,
    FunctionInfo,
    LogicalLocation,
    ParseResult,
    Severity,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fn(
    name: str,
    file_path: str,
    start: int,
    end: int,
    *,
    language: str = "python",
) -> FunctionInfo:
    return FunctionInfo(
        name=name,
        file_path=Path(file_path),
        start_line=start,
        end_line=end,
        language=language,
    )


def _cls(
    name: str,
    file_path: str,
    start: int,
    end: int,
    methods: list[FunctionInfo] | None = None,
    *,
    language: str = "python",
) -> ClassInfo:
    return ClassInfo(
        name=name,
        file_path=Path(file_path),
        start_line=start,
        end_line=end,
        language=language,
        methods=methods or [],
    )


def _finding(
    file_path: str,
    start_line: int,
    *,
    symbol: str | None = None,
) -> Finding:
    return Finding(
        signal_type="test_signal",
        severity=Severity.MEDIUM,
        score=0.5,
        title="Test finding",
        description="A test finding",
        file_path=Path(file_path),
        start_line=start_line,
        symbol=symbol,
    )


def _pr(
    file_path: str,
    functions: list[FunctionInfo] | None = None,
    classes: list[ClassInfo] | None = None,
) -> ParseResult:
    return ParseResult(
        file_path=Path(file_path),
        language="python",
        functions=functions or [],
        classes=classes or [],
    )


# ---------------------------------------------------------------------------
# _file_path_to_namespace
# ---------------------------------------------------------------------------


class TestFilePathToNamespace:
    def test_simple_module(self) -> None:
        assert _file_path_to_namespace(Path("src/api/auth.py")) == "src.api.auth"

    def test_init_file(self) -> None:
        assert _file_path_to_namespace(Path("src/api/__init__.py")) == "src.api"

    def test_pyi_suffix(self) -> None:
        assert _file_path_to_namespace(Path("src/api/auth.pyi")) == "src.api.auth"

    def test_single_file(self) -> None:
        assert _file_path_to_namespace(Path("main.py")) == "main"


# ---------------------------------------------------------------------------
# _build_location_index
# ---------------------------------------------------------------------------


class TestBuildLocationIndex:
    def test_empty_parse_results(self) -> None:
        index = _build_location_index([])
        assert index == {}

    def test_functions_indexed(self) -> None:
        pr = _pr("src/app.py", functions=[_fn("do_work", "src/app.py", 10, 20)])
        index = _build_location_index([pr])
        assert "src/app.py" in index
        assert len(index["src/app.py"]) == 1

    def test_class_and_methods_indexed(self) -> None:
        method = _fn("MyClass.do_work", "src/app.py", 15, 20)
        cls = _cls("MyClass", "src/app.py", 10, 25, methods=[method])
        pr = _pr("src/app.py", classes=[cls])
        index = _build_location_index([pr])
        entries = index["src/app.py"]
        # Should have class + method entries
        assert len(entries) == 2

    def test_sorted_by_span_ascending(self) -> None:
        method = _fn("MyClass.do_work", "src/app.py", 15, 18)
        cls = _cls("MyClass", "src/app.py", 10, 25, methods=[method])
        pr = _pr("src/app.py", classes=[cls])
        index = _build_location_index([pr])
        entries = index["src/app.py"]
        # Method span (3) < class span (15) → method first
        assert entries[0][3] == "method"
        assert entries[1][3] == "class"

    def test_class_qualified_functions_skipped_in_toplevel(self) -> None:
        """Functions with '.' in name (class-qualified) added via class only."""
        method = _fn("MyClass.do_work", "src/app.py", 15, 20)
        standalone = _fn("standalone", "src/app.py", 30, 40)
        pr = _pr("src/app.py", functions=[method, standalone])
        index = _build_location_index([pr])
        entries = index["src/app.py"]
        # Only standalone should be added; class-qualified is skipped
        assert len(entries) == 1
        assert entries[0][3] == "function"


# ---------------------------------------------------------------------------
# enrich_logical_locations — method in class
# ---------------------------------------------------------------------------


class TestEnrichMethod:
    def test_method_in_class(self) -> None:
        method = _fn("AuthService.login", "src/api/auth.py", 15, 30)
        cls = _cls("AuthService", "src/api/auth.py", 10, 50, methods=[method])
        pr = _pr("src/api/auth.py", classes=[cls])

        f = _finding("src/api/auth.py", 20)
        enrich_logical_locations([f], [pr])

        assert f.logical_location is not None
        assert f.logical_location.kind == "method"
        assert f.logical_location.name == "login"
        assert f.logical_location.class_name == "AuthService"
        assert f.logical_location.namespace == "src.api.auth"
        assert f.logical_location.fully_qualified_name == "src.api.auth.AuthService.login"

    def test_symbol_backfill(self) -> None:
        method = _fn("AuthService.login", "src/api/auth.py", 15, 30)
        cls = _cls("AuthService", "src/api/auth.py", 10, 50, methods=[method])
        pr = _pr("src/api/auth.py", classes=[cls])

        f = _finding("src/api/auth.py", 20, symbol=None)
        enrich_logical_locations([f], [pr])

        assert f.symbol == "login"

    def test_existing_symbol_preserved(self) -> None:
        method = _fn("AuthService.login", "src/api/auth.py", 15, 30)
        cls = _cls("AuthService", "src/api/auth.py", 10, 50, methods=[method])
        pr = _pr("src/api/auth.py", classes=[cls])

        f = _finding("src/api/auth.py", 20, symbol="custom_symbol")
        enrich_logical_locations([f], [pr])

        assert f.symbol == "custom_symbol"


# ---------------------------------------------------------------------------
# enrich_logical_locations — standalone function
# ---------------------------------------------------------------------------


class TestEnrichStandaloneFunction:
    def test_standalone_function(self) -> None:
        fn = _fn("validate_input", "src/utils.py", 10, 25)
        pr = _pr("src/utils.py", functions=[fn])

        f = _finding("src/utils.py", 15)
        enrich_logical_locations([f], [pr])

        assert f.logical_location is not None
        assert f.logical_location.kind == "function"
        assert f.logical_location.name == "validate_input"
        assert f.logical_location.class_name is None
        assert f.logical_location.namespace == "src.utils"
        assert f.logical_location.fully_qualified_name == "src.utils.validate_input"


# ---------------------------------------------------------------------------
# enrich_logical_locations — class-level finding
# ---------------------------------------------------------------------------


class TestEnrichClassLevel:
    def test_finding_on_class_declaration(self) -> None:
        cls = _cls("AuthService", "src/api/auth.py", 10, 50)
        pr = _pr("src/api/auth.py", classes=[cls])

        f = _finding("src/api/auth.py", 10)
        enrich_logical_locations([f], [pr])

        assert f.logical_location is not None
        assert f.logical_location.kind == "class"
        assert f.logical_location.name == "AuthService"
        assert f.logical_location.class_name == "AuthService"


# ---------------------------------------------------------------------------
# enrich_logical_locations — no match (module fallback)
# ---------------------------------------------------------------------------


class TestEnrichModuleFallback:
    def test_no_ast_match(self) -> None:
        pr = _pr("src/utils.py")  # no functions or classes

        f = _finding("src/utils.py", 5)
        enrich_logical_locations([f], [pr])

        assert f.logical_location is not None
        assert f.logical_location.kind == "module"
        assert f.logical_location.name == "utils"
        assert f.logical_location.namespace == "src.utils"

    def test_finding_outside_any_node(self) -> None:
        fn = _fn("validate_input", "src/utils.py", 10, 25)
        pr = _pr("src/utils.py", functions=[fn])

        f = _finding("src/utils.py", 50)  # line 50 is outside any function
        enrich_logical_locations([f], [pr])

        assert f.logical_location is not None
        assert f.logical_location.kind == "module"

    def test_no_file_path_skipped(self) -> None:
        f = Finding(
            signal_type="test",
            severity=Severity.MEDIUM,
            score=0.5,
            title="No file",
            description="No file",
        )
        enrich_logical_locations([f], [_pr("src/x.py")])
        assert f.logical_location is None


# ---------------------------------------------------------------------------
# enrich_logical_locations — narrowest match
# ---------------------------------------------------------------------------


class TestNarrowestMatch:
    def test_method_preferred_over_class(self) -> None:
        """When a finding line is inside a method, method wins over class."""
        method = _fn("Outer.inner_method", "src/app.py", 20, 30)
        cls = _cls("Outer", "src/app.py", 10, 50, methods=[method])
        pr = _pr("src/app.py", classes=[cls])

        f = _finding("src/app.py", 25)
        enrich_logical_locations([f], [pr])

        assert f.logical_location is not None
        assert f.logical_location.kind == "method"
        assert f.logical_location.name == "inner_method"
        assert f.logical_location.class_name == "Outer"


# ---------------------------------------------------------------------------
# enrich_logical_locations — empty parse results
# ---------------------------------------------------------------------------


class TestEnrichEmpty:
    def test_empty_parse_results_noop(self) -> None:
        f = _finding("src/app.py", 10)
        enrich_logical_locations([f], [])
        assert f.logical_location is None

    def test_empty_findings_noop(self) -> None:
        pr = _pr("src/app.py", functions=[_fn("foo", "src/app.py", 1, 10)])
        enrich_logical_locations([], [pr])  # Should not raise


# ---------------------------------------------------------------------------
# LogicalLocation serialization (round-trip check)
# ---------------------------------------------------------------------------


class TestLogicalLocationDataclass:
    def test_fields(self) -> None:
        loc = LogicalLocation(
            fully_qualified_name="src.api.auth.AuthService.login",
            name="login",
            kind="method",
            class_name="AuthService",
            namespace="src.api.auth",
        )
        assert loc.fully_qualified_name == "src.api.auth.AuthService.login"
        assert loc.kind == "method"
        assert loc.class_name == "AuthService"
        assert loc.namespace == "src.api.auth"

    def test_module_level_defaults(self) -> None:
        loc = LogicalLocation(
            fully_qualified_name="src.utils",
            name="utils",
            kind="module",
        )
        assert loc.class_name is None
        assert loc.namespace is None
