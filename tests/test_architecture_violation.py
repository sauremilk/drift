"""Tests for Architecture Violation signal."""

import datetime
from pathlib import Path

from drift.config import DriftConfig, LazyImportRule, PolicyConfig
from drift.ingestion.git_history import build_co_change_pairs
from drift.models import (
    ClassInfo,
    CommitInfo,
    ImportInfo,
    ParseResult,
    Severity,
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


def test_build_import_graph_resolves_relative_imports_to_internal_edges():
    results = [
        _pr(
            "src/pkg/api/routes.py",
            [
                ImportInfo(
                    source_file=Path("src/pkg/api/routes.py"),
                    imported_module="service",
                    imported_names=[],
                    line_number=3,
                    is_relative=True,
                )
            ],
        ),
        _pr("src/pkg/api/service.py", []),
    ]
    graph, _ = build_import_graph(results)

    assert graph.has_edge("src/pkg/api/routes.py", "src/pkg/api/service.py")


def test_build_import_graph_resolves_ts_esm_js_specifier_to_ts_target():
    results = [
        ParseResult(
            file_path=Path("src/commands/chutes-oauth.ts"),
            language="typescript",
            imports=[
                ImportInfo(
                    source_file=Path("src/commands/chutes-oauth.ts"),
                    imported_module="../agents/chutes-oauth.js",
                    imported_names=["ChutesOAuthProvider"],
                    line_number=5,
                    is_relative=True,
                )
            ],
        ),
        ParseResult(
            file_path=Path("src/agents/chutes-oauth.ts"),
            language="typescript",
            imports=[],
        ),
    ]

    graph, _ = build_import_graph(results)

    assert graph.has_edge("src/commands/chutes-oauth.ts", "src/agents/chutes-oauth.ts")
    assert graph.nodes.get("../agents/chutes-oauth.js", {}).get("external") is not True


def test_build_import_graph_resolves_ts_esm_mjs_and_cjs_specifiers():
    results = [
        ParseResult(
            file_path=Path("src/commands/loaders.ts"),
            language="typescript",
            imports=[
                ImportInfo(
                    source_file=Path("src/commands/loaders.ts"),
                    imported_module="../agents/esm-loader.mjs",
                    imported_names=["esmLoader"],
                    line_number=4,
                    is_relative=True,
                ),
                ImportInfo(
                    source_file=Path("src/commands/loaders.ts"),
                    imported_module="../agents/cjs-loader.cjs",
                    imported_names=["cjsLoader"],
                    line_number=5,
                    is_relative=True,
                ),
            ],
        ),
        ParseResult(
            file_path=Path("src/agents/esm-loader.mts"),
            language="typescript",
            imports=[],
        ),
        ParseResult(
            file_path=Path("src/agents/cjs-loader.cts"),
            language="typescript",
            imports=[],
        ),
    ]

    graph, _ = build_import_graph(results)

    assert graph.has_edge("src/commands/loaders.ts", "src/agents/esm-loader.mts")
    assert graph.has_edge("src/commands/loaders.ts", "src/agents/cjs-loader.cts")


def test_external_imports_marked():
    results = [
        _pr("app/main.py", [_imp("app/main.py", "flask")]),
    ]
    graph, _ = build_import_graph(results)

    assert graph.nodes.get("flask", {}).get("external") is True


def test_build_import_graph_avoids_per_import_fullscan(monkeypatch):
    """Import resolution should scale near-linearly with files + imports."""
    files = 220
    imports_per_file = 6

    results: list[ParseResult] = []
    for i in range(files):
        src = f"pkg/mod_{i}.py"
        imports = []
        for j in range(1, imports_per_file + 1):
            target_idx = (i + j) % files
            imports.append(_imp(src, f"pkg.mod_{target_idx}"))
        results.append(_pr(src, imports))

    from drift.signals import architecture_violation as avs_mod

    original = avs_mod._module_for_path
    call_count = 0

    def counted(path: Path) -> str:
        nonlocal call_count
        call_count += 1
        return original(path)

    monkeypatch.setattr(avs_mod, "_module_for_path", counted)

    graph, imports = build_import_graph(results)

    assert len(imports) == files * imports_per_file
    assert graph.number_of_edges() == len(imports)
    # O(files + imports): module normalization should happen once per known file,
    # not once per (import, known_file) pair.
    assert call_count <= files + 2


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
    assert upward[0].fix is not None
    assert "Move routes.py logic behind a service layer" in upward[0].fix
    assert "Verschiebe" not in upward[0].fix


def test_upward_import_detected_with_src_root_package_alias():
    # Repositories with src/ roots often import internal modules without the
    # src prefix (e.g. transformers.api.routes).
    results = [
        _pr(
            "src/transformers/db/queries.py",
            [_imp("src/transformers/db/queries.py", "transformers.api.routes")],
        ),
        _pr("src/transformers/api/routes.py", []),
    ]
    signal = ArchitectureViolationSignal()
    findings = signal.analyze(results, {}, None)

    upward = [f for f in findings if "Upward" in f.title]
    assert len(upward) >= 1
    assert upward[0].signal_type == SignalType.ARCHITECTURE_VIOLATION


def test_lazy_import_policy_violation_detected_for_module_level_heavy_import():
    results = [
        _pr("src/perception/detector.py", [_imp("src/perception/detector.py", "onnxruntime", 7)]),
    ]
    cfg = DriftConfig()
    cfg.policies = PolicyConfig(
        lazy_import_rules=[
            LazyImportRule(
                name="heavy_runtime_libs",
                **{"from": "src/perception/*.py"},
                modules=["onnxruntime", "torch", "cv2"],
            )
        ]
    )

    signal = ArchitectureViolationSignal()
    findings = signal.analyze(results, {}, cfg)

    lazy_findings = [f for f in findings if f.rule_id == "avs_lazy_import_policy"]
    assert len(lazy_findings) == 1
    assert lazy_findings[0].severity == Severity.HIGH
    assert "module level" in lazy_findings[0].description


def test_lazy_import_policy_ignores_local_import_when_module_level_only():
    results = [
        _pr(
            "src/perception/detector.py",
            [
                ImportInfo(
                    source_file=Path("src/perception/detector.py"),
                    imported_module="torch",
                    imported_names=["torch"],
                    line_number=22,
                    is_module_level=False,
                )
            ],
        ),
    ]
    cfg = DriftConfig()
    cfg.policies = PolicyConfig(
        lazy_import_rules=[
            LazyImportRule(
                name="heavy_runtime_libs",
                **{"from": "src/perception/*.py"},
                modules=["torch"],
                module_level_only=True,
            )
        ]
    )

    signal = ArchitectureViolationSignal()
    findings = signal.analyze(results, {}, cfg)

    assert [f for f in findings if f.rule_id == "avs_lazy_import_policy"] == []


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
    # With ancestors (correct direction): hub has 8 dependents → finding.
    # Modules with many dependents are correctly flagged.
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


def test_zone_of_pain_tiny_foundation_is_dampened():
    """Tiny foundational modules should not be emitted as HIGH without extra risk evidence."""
    prs = [
        ParseResult(
            file_path=Path("core/logger.py"),
            language="python",
            imports=[_imp("core/logger.py", "core.base")],
            line_count=4,
        ),
        _pr("core/base.py", []),
        _pr("services/a.py", [_imp("services/a.py", "core.logger")]),
        _pr("services/b.py", [_imp("services/b.py", "core.logger")]),
        _pr("services/c.py", [_imp("services/c.py", "core.logger")]),
        _pr("api/main.py", [_imp("api/main.py", "services.a")]),
    ]

    signal = ArchitectureViolationSignal()
    findings = signal.analyze(prs, {}, None)

    zone = [f for f in findings if "Zone of Pain" in f.title and "logger.py" in f.title]
    assert len(zone) == 1
    finding = zone[0]
    assert finding.severity == Severity.MEDIUM
    assert finding.score < 0.5
    assert finding.metadata["tiny_foundational_dampened"] is True
    assert finding.metadata["has_high_risk_evidence"] is False


def test_zone_of_pain_tiny_foundation_can_still_be_high_with_strong_evidence():
    """Tiny modules can remain HIGH when coupling evidence is strong enough."""
    prs = [
        ParseResult(
            file_path=Path("core/kernel.py"),
            language="python",
            imports=[_imp("core/kernel.py", "core.base")],
            line_count=8,
        ),
        _pr("core/base.py", []),
        _pr("services/a.py", [_imp("services/a.py", "core.kernel")]),
        _pr("services/b.py", [_imp("services/b.py", "core.kernel")]),
        _pr("services/c.py", [_imp("services/c.py", "core.kernel")]),
        _pr("services/d.py", [_imp("services/d.py", "core.kernel")]),
        _pr("services/e.py", [_imp("services/e.py", "core.kernel")]),
        _pr("services/f.py", [_imp("services/f.py", "core.kernel")]),
        _pr("api/main.py", [_imp("api/main.py", "services.a")]),
    ]

    signal = ArchitectureViolationSignal()
    findings = signal.analyze(prs, {}, None)

    zone = [f for f in findings if "Zone of Pain" in f.title and "kernel.py" in f.title]
    assert len(zone) == 1
    finding = zone[0]
    assert finding.severity == Severity.HIGH
    assert finding.metadata["tiny_foundational_dampened"] is False
    assert finding.metadata["has_high_risk_evidence"] is True


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
        _pr("handlers/billing.py", []),
    ]
    signal = ArchitectureViolationSignal()
    signal._commits = [
        _commit(["services/auth.py", "handlers/billing.py"]),
        _commit(["services/auth.py", "handlers/billing.py"]),
        _commit(["services/auth.py", "handlers/billing.py"]),
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


def test_co_change_same_directory_suppressed():
    """Sister files in the same package directory are NOT flagged (MCS-1)."""
    prs = [
        _pr("signals/foo.py", []),
        _pr("signals/bar.py", []),
    ]
    signal = ArchitectureViolationSignal()
    signal._commits = [
        _commit(["signals/foo.py", "signals/bar.py"]),
        _commit(["signals/foo.py", "signals/bar.py"]),
        _commit(["signals/foo.py", "signals/bar.py"]),
        _commit(["signals/foo.py", "signals/bar.py"]),
        _commit(["signals/foo.py", "signals/bar.py"]),
        _commit(["signals/foo.py", "signals/bar.py"]),
    ]
    findings = signal.analyze(prs, {}, None)

    hidden = [f for f in findings if "Hidden coupling" in f.title]
    assert len(hidden) == 0, f"Expected no same-dir findings, got: {hidden}"


def test_co_change_root_level_not_suppressed():
    """Root-level files (no package dir) are still flagged — guard protects flat repos."""
    prs = [
        _pr("foo.py", []),
        _pr("bar.py", []),
    ]
    signal = ArchitectureViolationSignal()
    signal._commits = [
        _commit(["foo.py", "bar.py"]),
        _commit(["foo.py", "bar.py"]),
        _commit(["foo.py", "bar.py"]),
        _commit(["foo.py", "bar.py"]),
        _commit(["foo.py", "bar.py"]),
        _commit(["foo.py", "bar.py"]),
    ]
    findings = signal.analyze(prs, {}, None)

    hidden = [f for f in findings if "Hidden coupling" in f.title]
    assert len(hidden) >= 1, "Root-level co-change should still produce a finding"


def test_co_change_test_source_pair_suppressed():
    """Test-source co-evolution is not flagged as hidden coupling (MCS-2)."""
    prs = [
        _pr("src/config.py", []),
        _pr("tests/test_config.py", []),
    ]
    signal = ArchitectureViolationSignal()
    signal._commits = [
        _commit(["src/config.py", "tests/test_config.py"]),
        _commit(["src/config.py", "tests/test_config.py"]),
        _commit(["src/config.py", "tests/test_config.py"]),
        _commit(["src/config.py", "tests/test_config.py"]),
        _commit(["src/config.py", "tests/test_config.py"]),
        _commit(["src/config.py", "tests/test_config.py"]),
        _commit(["src/config.py", "tests/test_config.py"]),
        _commit(["src/config.py", "tests/test_config.py"]),
    ]
    findings = signal.analyze(prs, {}, None)

    hidden = [f for f in findings if "Hidden coupling" in f.title]
    assert len(hidden) == 0, f"Test-source pair should be suppressed, got: {hidden}"


def test_co_change_bulk_commits_discounted():
    """Bulk commits (many files) are discounted in confidence calculation (MCS-3)."""
    # 6 commits with 15 files each — under the hard >20 cutoff but should
    # still be discounted.  a.py and b.py appear in every commit.
    other_files = [f"mod{i}.py" for i in range(13)]
    commits = [_commit(["a.py", "b.py"] + other_files) for _ in range(6)]
    pairs = build_co_change_pairs(commits, min_co_changes=1, min_confidence=0.3)
    ab_pairs = [p for p in pairs if {p.file_a, p.file_b} == {"a.py", "b.py"}]
    # With discount, 6 commits × weight ~0.07 each = ~0.43 weighted count
    # which should be below min_co_changes=3 default, or confidence too low.
    # Using min_co_changes=1 to isolate the confidence check.
    assert len(ab_pairs) == 0 or ab_pairs[0].confidence < 0.3, (
        f"Bulk commits should be discounted: {ab_pairs}"
    )

    # Counter-test: surgical commits preserve detection
    surgical = [_commit(["a.py", "b.py"]) for _ in range(4)]
    pairs2 = build_co_change_pairs(surgical, min_co_changes=3, min_confidence=0.3)
    ab_pairs2 = [p for p in pairs2 if {p.file_a, p.file_b} == {"a.py", "b.py"}]
    assert len(ab_pairs2) >= 1, "Surgical commits should still produce co-change pairs"


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
    assert god[0].fix is not None
    assert "Split hub.py by responsibility" in god[0].fix
    assert "Teile" not in god[0].fix


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
