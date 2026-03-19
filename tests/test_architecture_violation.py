"""Tests for Architecture Violation signal."""

from pathlib import Path

from drift.models import (
    ImportInfo,
    ParseResult,
    SignalType,
)
from drift.signals.architecture_violation import (
    ArchitectureViolationSignal,
    build_import_graph,
)


def _pr(path: str, imports: list[ImportInfo]) -> ParseResult:
    return ParseResult(
        file_path=Path(path),
        language="python",
        imports=imports,
    )


def _imp(source: str, module: str, line: int = 1) -> ImportInfo:
    return ImportInfo(
        source_file=Path(source),
        imported_module=module,
        imported_names=[],
        line_number=line,
    )


# ── Import graph ──────────────────────────────────────────────────────────


def test_build_import_graph_basic():
    results = [
        _pr("api/routes.py", [_imp("api/routes.py", "services.payment")]),
        _pr("services/payment.py", []),
    ]
    graph, imports = build_import_graph(results)

    assert "api/routes.py" in graph.nodes
    assert "services/payment.py" in graph.nodes
    assert len(imports) == 1


def test_external_imports_marked():
    results = [
        _pr("app/main.py", [_imp("app/main.py", "flask")]),
    ]
    graph, _ = build_import_graph(results)

    assert graph.nodes.get("flask", {}).get("external") is True


# ── Layer violations ──────────────────────────────────────────────────────


def test_no_violations_in_correct_direction():
    # Presentation (api) imports Service (services) → OK
    results = [
        _pr("api/routes.py", [_imp("api/routes.py", "services.payment")]),
        _pr("services/payment.py", []),
    ]
    signal = ArchitectureViolationSignal()
    findings = signal.analyze(results, {}, None)

    # No inferred-layer violations (api=0 → services=1, lower → higher = OK)
    layer_findings = [f for f in findings if "Upward" in f.title]
    assert layer_findings == []


def test_upward_import_detected():
    # DB layer (db, layer=2) importing from API layer (api, layer=0) → violation
    results = [
        _pr("db/queries.py", [_imp("db/queries.py", "api.routes")]),
        _pr("api/routes.py", []),
    ]
    signal = ArchitectureViolationSignal()
    findings = signal.analyze(results, {}, None)

    upward = [f for f in findings if "Upward" in f.title]
    assert len(upward) >= 1
    assert upward[0].signal_type == SignalType.ARCHITECTURE_VIOLATION


def test_circular_dependency_detected():
    results = [
        _pr("services/a.py", [_imp("services/a.py", "services.b")]),
        _pr("services/b.py", [_imp("services/b.py", "services.a")]),
    ]
    signal = ArchitectureViolationSignal()
    findings = signal.analyze(results, {}, None)

    circular = [f for f in findings if "Circular" in f.title]
    assert len(circular) >= 1


def test_score_zero_when_clean():
    results = [
        _pr("api/routes.py", [_imp("api/routes.py", "services.payment")]),
        _pr("services/payment.py", [_imp("services/payment.py", "db.models")]),
        _pr("db/models.py", []),
    ]
    signal = ArchitectureViolationSignal()
    findings = signal.analyze(results, {}, None)

    # Clean layered architecture → no violations
    assert findings == []
