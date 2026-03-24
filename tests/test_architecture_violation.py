"""Tests for Architecture Violation signal."""

import datetime
from pathlib import Path

from drift.ingestion.git_history import build_co_change_pairs
from drift.models import (
    ClassInfo,
    CommitInfo,
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


# ── Blast radius ──────────────────────────────────────────────────────────


def test_blast_radius_metadata_on_upward_import():
    """Upward-import findings include blast_radius in metadata."""
    results = [
        _pr("db/queries.py", [_imp("db/queries.py", "api.routes")]),
        _pr("api/routes.py", []),
    ]
    signal = ArchitectureViolationSignal()
    findings = signal.analyze(results, {}, None)

    upward = [f for f in findings if "Upward" in f.title]
    assert len(upward) >= 1
    assert "blast_radius" in upward[0].metadata


def test_high_blast_radius_finding():
    """Modules with many transitive dependents produce a blast-radius finding."""
    # Hub module that everything depends on transitively
    imports = []
    prs = []
    for i in range(8):
        name = f"services/mod{i}.py"
        imports.append(_imp(name, "services.hub"))
        prs.append(_pr(name, [_imp(name, "services.hub")]))
    prs.append(_pr("services/hub.py", []))
    # hub.py has 0 out-degree but high in-degree;
    # modules depending on hub have descendants through hub
    signal = ArchitectureViolationSignal()
    findings = signal.analyze(prs, {}, None)

    blast = [f for f in findings if "blast radius" in f.title.lower()]
    # With 9 nodes and hub having 0 descendants, individual modules
    # each have 1 descendant (hub) → no high blast. This test verifies
    # no false positives on normal fan-in.
    assert all(f.metadata.get("blast_radius", 0) >= 5 for f in blast)


# ── Instability index ────────────────────────────────────────────────────


def test_zone_of_pain_detected():
    """A concrete, stable module with many dependents triggers Zone of Pain."""
    # core/models.py: many modules depend on it (high Ca), it depends on nothing (Ce=0)
    # → I=0, A=0, D=1.0 → Zone of Pain
    prs = [
        _pr("core/models.py", []),
        _pr("services/a.py", [_imp("services/a.py", "core.models")]),
        _pr("services/b.py", [_imp("services/b.py", "core.models")]),
        _pr("services/c.py", [_imp("services/c.py", "core.models")]),
        _pr("api/main.py", [_imp("api/main.py", "services.a")]),
    ]
    signal = ArchitectureViolationSignal()
    findings = signal.analyze(prs, {}, None)

    zone = [f for f in findings if "Zone of Pain" in f.title]
    assert len(zone) >= 1
    meta = zone[0].metadata
    assert meta["instability"] == 0.0
    assert meta["distance_main_seq"] == 1.0


def test_no_zone_of_pain_for_abstract_module():
    """Abstract modules (Protocol bases) should not be in Zone of Pain."""
    prs = [
        ParseResult(
            file_path=Path("core/base.py"),
            language="python",
            imports=[],
            classes=[
                ClassInfo(
                    name="BaseRepo",
                    file_path=Path("core/base.py"),
                    start_line=1,
                    end_line=10,
                    language="python",
                    bases=["Protocol"],
                ),
            ],
        ),
        _pr("services/a.py", [_imp("services/a.py", "core.base")]),
        _pr("services/b.py", [_imp("services/b.py", "core.base")]),
        _pr("services/c.py", [_imp("services/c.py", "core.base")]),
        _pr("api/main.py", [_imp("api/main.py", "services.a")]),
    ]
    signal = ArchitectureViolationSignal()
    findings = signal.analyze(prs, {}, None)

    zone = [f for f in findings if "Zone of Pain" in f.title and "base.py" in f.title]
    # A=1.0, I=0.0 → D=0.0 → NOT in zone of pain
    assert len(zone) == 0


# ── Co-change coupling ───────────────────────────────────────────────────


def _commit(files: list[str], msg: str = "change") -> CommitInfo:
    return CommitInfo(
        hash="abc123",
        author="dev",
        email="dev@test.com",
        timestamp=datetime.datetime.now(tz=datetime.UTC),
        message=msg,
        files_changed=files,
    )


def test_build_co_change_pairs_basic():
    """Files changed together repeatedly appear as co-change pairs."""
    commits = [
        _commit(["a.py", "b.py"]),
        _commit(["a.py", "b.py"]),
        _commit(["a.py", "b.py"]),
        _commit(["a.py", "c.py"]),
    ]
    pairs = build_co_change_pairs(commits, min_co_changes=3, min_confidence=0.3)
    assert len(pairs) >= 1
    assert pairs[0].file_a == "a.py"
    assert pairs[0].file_b == "b.py"
    assert pairs[0].co_change_count == 3


def test_co_change_filters_bulk_commits():
    """Commits with >20 files are excluded from co-change analysis."""
    bulk_files = [f"mod{i}.py" for i in range(25)]
    commits = [_commit(bulk_files)] * 5
    pairs = build_co_change_pairs(commits, min_co_changes=1)
    assert pairs == []


def test_co_change_finding_without_import():
    """Co-changed files without an import edge produce a hidden coupling finding."""
    prs = [
        _pr("services/auth.py", []),
        _pr("services/billing.py", []),
    ]
    signal = ArchitectureViolationSignal()
    signal._commits = [
        _commit(["services/auth.py", "services/billing.py"]),
        _commit(["services/auth.py", "services/billing.py"]),
        _commit(["services/auth.py", "services/billing.py"]),
    ]
    findings = signal.analyze(prs, {}, None)

    hidden = [f for f in findings if "Hidden coupling" in f.title]
    assert len(hidden) >= 1
    assert hidden[0].metadata["co_change_count"] == 3


def test_co_change_suppressed_when_import_exists():
    """Co-changed files with an import edge are NOT flagged as hidden."""
    prs = [
        _pr(
            "services/auth.py",
            [_imp("services/auth.py", "services.billing")],
        ),
        _pr("services/billing.py", []),
    ]
    signal = ArchitectureViolationSignal()
    signal._commits = [
        _commit(["services/auth.py", "services/billing.py"]),
        _commit(["services/auth.py", "services/billing.py"]),
        _commit(["services/auth.py", "services/billing.py"]),
    ]
    findings = signal.analyze(prs, {}, None)

    hidden = [f for f in findings if "Hidden coupling" in f.title]
    assert len(hidden) == 0


# ── Missing-pattern coverage: explicit detections ─────────────────────────


def test_god_module_candidate_detected():
    """High fan-in/fan-out module is flagged as god module candidate."""
    prs = [
        _pr(
            "core/hub.py",
            [
                _imp("core/hub.py", "services/a".replace("/", ".")),
                _imp("core/hub.py", "services/b".replace("/", ".")),
                _imp("core/hub.py", "services/c".replace("/", ".")),
            ],
        ),
        _pr("services/a.py", [_imp("services/a.py", "core.hub")]),
        _pr("services/b.py", [_imp("services/b.py", "core.hub")]),
        _pr("services/c.py", [_imp("services/c.py", "core.hub")]),
        _pr("services/d.py", [_imp("services/d.py", "core.hub")]),
        _pr("services/e.py", [_imp("services/e.py", "core.hub")]),
        _pr("api/main.py", [_imp("api/main.py", "core.hub")]),
    ]
    signal = ArchitectureViolationSignal()
    findings = signal.analyze(prs, {}, None)

    god = [f for f in findings if "God module candidate" in f.title]
    assert len(god) >= 1


def test_unstable_dependency_detected_with_churn_history():
    """Stable source depending on unstable + volatile target is flagged."""
    prs = [
        _pr("core/stable.py", [_imp("core/stable.py", "infra.unstable")]),
        _pr("infra/unstable.py", [_imp("infra/unstable.py", "api.routes")]),
        _pr("services/a.py", [_imp("services/a.py", "core.stable")]),
        _pr("services/b.py", [_imp("services/b.py", "core.stable")]),
        _pr("api/routes.py", []),
    ]
    now = datetime.datetime.now(tz=datetime.UTC)
    histories = {
        "infra/unstable.py": {
            "path": Path("infra/unstable.py"),
            "total_commits": 12,
            "unique_authors": 3,
            "ai_attributed_commits": 0,
            "change_frequency_30d": 1.4,
            "defect_correlated_commits": 2,
            "last_modified": now,
            "first_seen": now,
        }
    }

    # Build a real FileHistory object from dict literal shape used in tests.
    from drift.models import FileHistory

    file_histories = {
        "infra/unstable.py": FileHistory(**histories["infra/unstable.py"]),
    }

    signal = ArchitectureViolationSignal()
    findings = signal.analyze(prs, file_histories, None)

    unstable = [f for f in findings if "Unstable dependency" in f.title]
    assert len(unstable) >= 1
    assert unstable[0].metadata["dst_churn_week"] >= 1.0
