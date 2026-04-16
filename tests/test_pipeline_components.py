"""Targeted unit tests for decomposed analyzer pipeline phases."""

from __future__ import annotations

import datetime
import importlib
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from drift.cache import ParseCache
from drift.config import DriftConfig
from drift.models import (
    ClassInfo,
    CommitInfo,
    FileHistory,
    FileInfo,
    Finding,
    FunctionInfo,
    ImportInfo,
    ParseResult,
    PatternCategory,
    PatternInstance,
    RepoAnalysis,
    Severity,
    SignalType,
)
from drift.pipeline import (
    AnalysisPipeline,
    DegradationInfo,
    IngestionPhase,
    ParsedInputs,
    ScoringPhase,
    SignalPhase,
)


def _config() -> DriftConfig:
    return DriftConfig(
        include=["**/*.py"],
        exclude=["**/.git/**", "**/.drift-cache/**", "**/__pycache__/**"],
        embeddings_enabled=False,
    )


def _file_info(path: str, size: int = 10) -> FileInfo:
    return FileInfo(path=Path(path), language="python", size_bytes=size, line_count=1)


def _finding(signal_type: SignalType = SignalType.PATTERN_FRAGMENTATION) -> Finding:
    return Finding(
        signal_type=signal_type,
        severity=Severity.LOW,
        score=0.2,
        title="sample",
        description="sample finding",
        file_path=Path("pkg/mod.py"),
    )


def test_ingestion_phase_uses_cache_and_preserves_order(tmp_path: Path) -> None:
    cfg = _config()
    (tmp_path / "a.py").write_text("def a():\n    return 1\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("def b():\n    return 2\n", encoding="utf-8")

    files = [_file_info("a.py"), _file_info("b.py")]

    cache = ParseCache(tmp_path / cfg.cache_dir)
    cached_hash = ParseCache.file_hash(tmp_path / "a.py")
    cache.put(cached_hash, ParseResult(file_path=Path("a.py"), language="python"))

    parsed_paths: list[Path] = []

    def _fake_parse(path: Path, _repo_path: Path, language: str) -> ParseResult:
        parsed_paths.append(path)
        return ParseResult(file_path=path, language=language)

    phase = IngestionPhase(parse_file_fn=_fake_parse, is_git_repo_fn=lambda _p: False)
    out = phase.run(
        tmp_path,
        files,
        cfg,
        since_days=30,
        workers=1,
        degradation=DegradationInfo(causes=set(), components=set(), events=[]),
    )

    assert parsed_paths == [Path("b.py")]
    assert [r.file_path for r in out.parse_results] == [Path("a.py"), Path("b.py")]
    assert out.commits == []
    assert out.file_histories == {}


def test_ingestion_phase_remaps_all_cached_file_references(tmp_path: Path) -> None:
    cfg = _config()
    old_file = tmp_path / "old.py"
    new_file = tmp_path / "new.py"
    content = "def same():\n    return 1\n"
    old_file.write_text(content, encoding="utf-8")
    new_file.write_text(content, encoding="utf-8")

    files = [_file_info("new.py")]

    cache = ParseCache(tmp_path / cfg.cache_dir)
    cached_hash = ParseCache.file_hash(new_file)
    cached = ParseResult(
        file_path=Path("old.py"),
        language="python",
        functions=[
            FunctionInfo(
                name="same",
                file_path=Path("old.py"),
                start_line=1,
                end_line=2,
                language="python",
            )
        ],
        classes=[
            ClassInfo(
                name="Old",
                file_path=Path("old.py"),
                start_line=1,
                end_line=2,
                language="python",
                methods=[
                    FunctionInfo(
                        name="m",
                        file_path=Path("old.py"),
                        start_line=1,
                        end_line=2,
                        language="python",
                    )
                ],
            )
        ],
        imports=[
            ImportInfo(
                source_file=Path("old.py"),
                imported_module="typing",
                imported_names=["Any"],
                line_number=1,
            )
        ],
        patterns=[
            PatternInstance(
                category=PatternCategory.ERROR_HANDLING,
                file_path=Path("old.py"),
                function_name="same",
                start_line=1,
                end_line=2,
            )
        ],
    )
    cache.put(cached_hash, cached)

    phase = IngestionPhase(is_git_repo_fn=lambda _p: False)
    out = phase.run(
        tmp_path,
        files,
        cfg,
        since_days=30,
        workers=1,
        degradation=DegradationInfo(causes=set(), components=set(), events=[]),
    )

    pr = out.parse_results[0]
    assert pr.file_path == Path("new.py")
    assert all(func.file_path == Path("new.py") for func in pr.functions)
    assert all(cls.file_path == Path("new.py") for cls in pr.classes)
    assert all(method.file_path == Path("new.py") for cls in pr.classes for method in cls.methods)
    assert all(imp.source_file == Path("new.py") for imp in pr.imports)
    assert all(pattern.file_path == Path("new.py") for pattern in pr.patterns)


def test_fetch_git_history_uses_cache_for_same_head(monkeypatch) -> None:
    import drift.pipeline as pipeline

    pipeline._GIT_HISTORY_CACHE.clear()

    calls = {"parse": 0, "build": 0}
    now = datetime.datetime.now(datetime.UTC)
    fake_commits = [
        CommitInfo(
            hash="abc123",
            author="bot",
            email="bot@example.com",
            timestamp=now,
            message="test",
            files_changed=["a.py"],
        )
    ]

    def _fake_parse(*_args, **_kwargs):
        calls["parse"] += 1
        return list(fake_commits)

    def _fake_build(commits, *, known_files):
        calls["build"] += 1
        return {k: FileHistory(path=Path(k), total_commits=len(commits)) for k in known_files}

    monkeypatch.setattr(pipeline, "parse_git_history", _fake_parse)
    monkeypatch.setattr(pipeline, "build_file_histories", _fake_build)
    monkeypatch.setattr(pipeline, "_current_git_head", lambda _p: "HEAD1")

    known = {"a.py", "b.py"}
    commits_1, histories_1 = pipeline.fetch_git_history(Path("."), 30, known)
    commits_2, histories_2 = pipeline.fetch_git_history(Path("."), 30, known)

    assert calls["parse"] == 1
    assert calls["build"] == 1
    assert commits_1 == commits_2
    assert histories_1 == histories_2


def test_fetch_git_history_cache_invalidates_on_head_change(monkeypatch) -> None:
    import drift.pipeline as pipeline

    pipeline._GIT_HISTORY_CACHE.clear()

    calls = {"parse": 0}
    now = datetime.datetime.now(datetime.UTC)

    def _fake_parse(*_args, **_kwargs):
        calls["parse"] += 1
        return [
            CommitInfo(
                hash=f"h{calls['parse']}",
                author="bot",
                email="bot@example.com",
                timestamp=now,
                message="test",
                files_changed=["a.py"],
            )
        ]

    def _fake_build(commits, *, known_files):
        return {k: FileHistory(path=Path(k), total_commits=len(commits)) for k in known_files}

    heads = iter(["HEAD1", "HEAD2"])

    monkeypatch.setattr(pipeline, "parse_git_history", _fake_parse)
    monkeypatch.setattr(pipeline, "build_file_histories", _fake_build)
    monkeypatch.setattr(pipeline, "_current_git_head", lambda _p: next(heads))

    known = {"a.py"}
    commits_1, _ = pipeline.fetch_git_history(Path("."), 30, known)
    commits_2, _ = pipeline.fetch_git_history(Path("."), 30, known)

    assert calls["parse"] == 2
    assert commits_1[0].hash != commits_2[0].hash


def test_fetch_git_history_uses_persistent_index_when_enabled(monkeypatch) -> None:
    import drift.pipeline as pipeline

    pipeline._GIT_HISTORY_CACHE.clear()

    cfg = _config()
    cfg.git_history_index_enabled = True

    now = datetime.datetime.now(datetime.UTC)

    def _fake_index(*_args, **_kwargs):
        return [
            CommitInfo(
                hash="idx1",
                author="bot",
                email="bot@example.com",
                timestamp=now,
                message="test",
                files_changed=["a.py"],
            )
        ]

    monkeypatch.setattr(pipeline, "load_or_update_git_history_index", _fake_index)
    monkeypatch.setattr(
        pipeline,
        "parse_git_history",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("legacy parse path used")),
    )
    monkeypatch.setattr(pipeline, "_current_git_head", lambda _p: "HEAD1")

    commits, histories = pipeline.fetch_git_history(Path("."), 30, {"a.py"}, config=cfg)

    assert [c.hash for c in commits] == ["idx1"]
    assert "a.py" in histories


def test_signal_phase_records_degradation_on_signal_failure(tmp_path: Path) -> None:
    class _FailingSignal:
        name = "failing"

        def analyze(self, *_args: object, **_kwargs: object) -> list[Finding]:
            raise RuntimeError("boom")

    class _WorkingSignal:
        name = "working"

        def analyze(self, *_args: object, **_kwargs: object) -> list[Finding]:
            return [_finding()]

    cfg = _config()
    parsed = IngestionPhase(is_git_repo_fn=lambda _p: False).run(
        tmp_path,
        [],
        cfg,
        since_days=30,
        workers=1,
        degradation=DegradationInfo(causes=set(), components=set(), events=[]),
    )

    degradation = DegradationInfo(causes=set(), components=set(), events=[])
    phase = SignalPhase(
        embedding_factory=lambda **_kwargs: None,
        signal_factory=lambda _ctx: [_FailingSignal(), _WorkingSignal()],
    )
    out = phase.run(tmp_path, cfg, parsed, degradation=degradation)

    assert len(out.findings) == 1
    assert "signal_failure" in degradation.causes
    assert "signal:failing" in degradation.components
    assert len(degradation.events) == 1
    event = degradation.events[0]
    assert event["cause"] == "signal_failure"
    assert event["component"] == "signal:failing"
    assert event["details"]["signal"] == "failing"
    assert event["details"]["error_type"] == "RuntimeError"
    assert event["details"]["error_message"] == "boom"


def test_signal_phase_warning_always_includes_exc_info(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Regression test for issue #411: exc_info must be True unconditionally."""

    class _FailingSignal:
        name = "failing411"

        def analyze(self, *_args: object, **_kwargs: object) -> list[Finding]:
            raise ValueError("issue411")

    cfg = _config()
    parsed = IngestionPhase(is_git_repo_fn=lambda _p: False).run(
        tmp_path,
        [],
        cfg,
        since_days=30,
        workers=1,
        degradation=DegradationInfo(causes=set(), components=set(), events=[]),
    )

    phase = SignalPhase(
        embedding_factory=lambda **_kwargs: None,
        signal_factory=lambda _ctx: [_FailingSignal()],
    )

    # Set WARNING level (not DEBUG) — stack trace must still be captured
    with caplog.at_level(logging.WARNING, logger="drift"):
        phase.run(
            tmp_path, cfg, parsed,
            degradation=DegradationInfo(causes=set(), components=set(), events=[]),
        )

    warning_records = [r for r in caplog.records if "failing411" in r.getMessage()]
    assert warning_records, "Expected a warning log for the failing signal"
    assert warning_records[0].exc_info is not None, (
        "Stack trace must be attached unconditionally (exc_info=True), not only at DEBUG"
    )


def test_signal_phase_filters_active_signals(tmp_path: Path) -> None:
    class _PfsSignal:
        name = "pfs"
        signal_type = SignalType.PATTERN_FRAGMENTATION

        def analyze(self, *_args: object, **_kwargs: object) -> list[Finding]:
            return [_finding(SignalType.PATTERN_FRAGMENTATION)]

    class _AvsSignal:
        name = "avs"
        signal_type = SignalType.ARCHITECTURE_VIOLATION

        def analyze(self, *_args: object, **_kwargs: object) -> list[Finding]:
            return [_finding(SignalType.ARCHITECTURE_VIOLATION)]

    cfg = _config()
    parsed = IngestionPhase(is_git_repo_fn=lambda _p: False).run(
        tmp_path,
        [],
        cfg,
        since_days=30,
        workers=1,
        degradation=DegradationInfo(causes=set(), components=set(), events=[]),
    )

    phase = SignalPhase(
        embedding_factory=lambda **_kwargs: None,
        signal_factory=lambda _ctx: [_PfsSignal(), _AvsSignal()],
    )
    out = phase.run(
        tmp_path,
        cfg,
        parsed,
        degradation=DegradationInfo(causes=set(), components=set(), events=[]),
        active_signals={"pattern_fragmentation"},
    )

    assert len(out.findings) == 1
    assert out.findings[0].signal_type is SignalType.PATTERN_FRAGMENTATION


def test_signal_phase_skips_embedding_init_when_not_needed(tmp_path: Path) -> None:
    class _NoEmbeddingSignal:
        name = "no-embedding"
        signal_type = SignalType.PATTERN_FRAGMENTATION
        uses_embeddings = False

        def analyze(self, *_args: object, **_kwargs: object) -> list[Finding]:
            return [_finding(SignalType.PATTERN_FRAGMENTATION)]

    cfg = DriftConfig(
        include=["**/*.py"],
        exclude=["**/.git/**", "**/.drift-cache/**", "**/__pycache__/**"],
        embeddings_enabled=True,
    )
    parsed = IngestionPhase(is_git_repo_fn=lambda _p: False).run(
        tmp_path,
        [],
        cfg,
        since_days=30,
        workers=1,
        degradation=DegradationInfo(causes=set(), components=set(), events=[]),
    )

    calls = {"count": 0}

    def _embedding_factory(**_kwargs: object) -> object:
        calls["count"] += 1
        return object()

    phase = SignalPhase(
        embedding_factory=_embedding_factory,
        signal_factory=lambda _ctx: [_NoEmbeddingSignal()],
    )
    phase.run(
        tmp_path,
        cfg,
        parsed,
        degradation=DegradationInfo(causes=set(), components=set(), events=[]),
    )

    assert calls["count"] == 0


def test_signal_phase_initializes_embeddings_when_needed(tmp_path: Path) -> None:
    class _NeedsEmbeddingSignal:
        name = "needs-embedding"
        signal_type = SignalType.PATTERN_FRAGMENTATION
        uses_embeddings = True

        def __init__(self) -> None:
            self.received_embedding = None

        def bind_context(self, capabilities) -> None:
            self.received_embedding = capabilities.embedding_service

        def analyze(self, *_args: object, **_kwargs: object) -> list[Finding]:
            return [_finding(SignalType.PATTERN_FRAGMENTATION)]

    cfg = DriftConfig(
        include=["**/*.py"],
        exclude=["**/.git/**", "**/.drift-cache/**", "**/__pycache__/**"],
        embeddings_enabled=True,
    )
    parsed = IngestionPhase(is_git_repo_fn=lambda _p: False).run(
        tmp_path,
        [],
        cfg,
        since_days=30,
        workers=1,
        degradation=DegradationInfo(causes=set(), components=set(), events=[]),
    )

    calls = {"count": 0}
    marker = object()

    def _embedding_factory(**_kwargs: object) -> object:
        calls["count"] += 1
        return marker

    signal = _NeedsEmbeddingSignal()
    phase = SignalPhase(
        embedding_factory=_embedding_factory,
        signal_factory=lambda _ctx: [signal],
    )
    phase.run(
        tmp_path,
        cfg,
        parsed,
        degradation=DegradationInfo(causes=set(), components=set(), events=[]),
    )

    assert calls["count"] == 1
    assert signal.received_embedding is marker


def test_scoring_phase_applies_small_repo_kwargs_and_post_processing() -> None:
    cfg = _config()
    files = [_file_info("pkg/mod.py")]
    findings = [_finding()]

    impact_calls: list[dict] = []
    score_kwargs: list[dict[str, int]] = []

    def _impact_assigner(_findings: list[Finding], weights: dict, **_kw: object) -> None:
        impact_calls.append(weights)

    def _suppression_filter(
        items: list[Finding],
        _suppressions: dict,
    ) -> tuple[list[Finding], list[Finding]]:
        return items, [_finding()]

    def _context_apply(
        items: list[Finding],
        _tags: dict,
        **_kwargs: object,
    ) -> tuple[list[Finding], int]:
        return items, 1

    def _signal_scores(_findings: list[Finding], **kwargs: int) -> dict:
        score_kwargs.append(kwargs)
        return {}

    phase = ScoringPhase(
        impact_assigner=_impact_assigner,
        suppression_scanner=lambda _files, _repo: {},
        suppression_filter=_suppression_filter,
        context_scanner=lambda _files, _repo: {},
        context_applicator=_context_apply,
        calibrator=lambda _findings, weights: weights,
        signal_score_fn=_signal_scores,
        repo_score_fn=lambda _scores, _weights: 0.0,
        module_score_fn=lambda _findings, _weights: [],
    )

    out = phase.run(Path("."), files, cfg, findings)

    assert out.suppressed_count == 1
    assert out.context_tagged_count == 1
    assert len(impact_calls) == 3
    assert score_kwargs[-1]["dampening_k"] == 20
    assert score_kwargs[-1]["min_findings"] == cfg.thresholds.small_repo_min_findings


def test_default_workers_uses_env_override(monkeypatch) -> None:
    monkeypatch.setenv("DRIFT_WORKERS", "3")
    pipeline = importlib.import_module("drift.pipeline")
    pipeline = importlib.reload(pipeline)

    assert pipeline.DEFAULT_WORKERS == 3


def test_default_workers_ignores_invalid_env(monkeypatch) -> None:
    monkeypatch.setenv("DRIFT_WORKERS", "abc")
    pipeline = importlib.import_module("drift.pipeline")
    pipeline = importlib.reload(pipeline)

    assert 2 <= pipeline.DEFAULT_WORKERS <= 16


def test_signal_phase_file_local_dependency_cache_reruns_only_changed_file(tmp_path: Path) -> None:
    class _FileLocalSignal:
        name = "file-local"
        signal_type = SignalType.PATTERN_FRAGMENTATION
        incremental_scope = "file_local"
        cache_dependency_scope = "file_local"

        def __init__(self) -> None:
            self.calls: list[list[str]] = []

        def analyze(self, parse_results, *_args, **_kwargs):
            self.calls.append([pr.file_path.as_posix() for pr in parse_results])
            out: list[Finding] = []
            for pr in parse_results:
                out.append(
                    Finding(
                        signal_type=SignalType.PATTERN_FRAGMENTATION,
                        severity=Severity.LOW,
                        score=0.1,
                        title=f"f:{pr.file_path.as_posix()}",
                        description="local",
                        file_path=pr.file_path,
                    ),
                )
            return out

    cfg = DriftConfig(
        include=["**/*.py"],
        exclude=["**/.git/**", "**/.drift-cache/**", "**/__pycache__/**"],
        embeddings_enabled=False,
        signal_cache_dependency_scopes_enabled=True,
    )

    a_path = tmp_path / "a.py"
    b_path = tmp_path / "b.py"
    a_path.write_text("def a():\n    return 1\n", encoding="utf-8")
    b_path.write_text("def b():\n    return 2\n", encoding="utf-8")

    def _parsed_inputs() -> ParsedInputs:
        return ParsedInputs(
            parse_results=[
                ParseResult(file_path=Path("a.py"), language="python"),
                ParseResult(file_path=Path("b.py"), language="python"),
            ],
            commits=[],
            file_histories={},
            file_hashes={
                "a.py": ParseCache.file_hash(a_path),
                "b.py": ParseCache.file_hash(b_path),
            },
        )

    signal = _FileLocalSignal()
    phase = SignalPhase(
        embedding_factory=lambda **_kwargs: None,
        signal_factory=lambda _ctx: [signal],
    )

    phase.run(
        tmp_path,
        cfg,
        _parsed_inputs(),
        degradation=DegradationInfo(causes=set(), components=set(), events=[]),
    )
    assert signal.calls == [["a.py"], ["b.py"]]

    phase.run(
        tmp_path,
        cfg,
        _parsed_inputs(),
        degradation=DegradationInfo(causes=set(), components=set(), events=[]),
    )
    assert signal.calls == [["a.py"], ["b.py"]]

    a_path.write_text("def a():\n    return 3\n", encoding="utf-8")

    phase.run(
        tmp_path,
        cfg,
        _parsed_inputs(),
        degradation=DegradationInfo(causes=set(), components=set(), events=[]),
    )
    assert signal.calls == [["a.py"], ["b.py"], ["a.py"]]


def test_signal_phase_file_local_cache_reuses_results_across_scope_switch(
    tmp_path: Path,
) -> None:
    class _FileLocalSignal:
        name = "file-local-scope"
        signal_type = SignalType.PATTERN_FRAGMENTATION
        incremental_scope = "file_local"
        cache_dependency_scope = "file_local"

        def __init__(self) -> None:
            self.calls: list[list[str]] = []

        def analyze(self, parse_results, *_args, **_kwargs):
            self.calls.append([pr.file_path.as_posix() for pr in parse_results])
            return [
                Finding(
                    signal_type=SignalType.PATTERN_FRAGMENTATION,
                    severity=Severity.LOW,
                    score=0.1,
                    title=f"f:{pr.file_path.as_posix()}",
                    description="local",
                    file_path=pr.file_path,
                )
                for pr in parse_results
            ]

    cfg = DriftConfig(
        include=["**/*.py"],
        exclude=["**/.git/**", "**/.drift-cache/**", "**/__pycache__/**"],
        embeddings_enabled=False,
        signal_cache_dependency_scopes_enabled=True,
    )

    a_path = tmp_path / "a.py"
    b_path = tmp_path / "b.py"
    a_path.write_text("def a():\n    return 1\n", encoding="utf-8")
    b_path.write_text("def b():\n    return 2\n", encoding="utf-8")

    signal = _FileLocalSignal()
    phase = SignalPhase(
        embedding_factory=lambda **_kwargs: None,
        signal_factory=lambda _ctx: [signal],
    )

    full_inputs = ParsedInputs(
        parse_results=[
            ParseResult(file_path=Path("a.py"), language="python"),
            ParseResult(file_path=Path("b.py"), language="python"),
        ],
        commits=[],
        file_histories={},
        file_hashes={
            "a.py": ParseCache.file_hash(a_path),
            "b.py": ParseCache.file_hash(b_path),
        },
    )

    scoped_inputs = ParsedInputs(
        parse_results=[
            ParseResult(file_path=Path("a.py"), language="python"),
        ],
        commits=[],
        file_histories={},
        file_hashes={
            "a.py": ParseCache.file_hash(a_path),
        },
    )

    phase.run(
        tmp_path,
        cfg,
        full_inputs,
        degradation=DegradationInfo(causes=set(), components=set(), events=[]),
    )
    assert signal.calls == [["a.py"], ["b.py"]]

    # Scope switch from repo-wide to a narrower subset should hit file-local cache.
    phase.run(
        tmp_path,
        cfg,
        scoped_inputs,
        degradation=DegradationInfo(causes=set(), components=set(), events=[]),
    )
    assert signal.calls == [["a.py"], ["b.py"]]


def test_analysis_pipeline_exposes_phase_timings() -> None:
    cfg = _config()

    class _Ingestion:
        def run(self, *_args, **_kwargs):
            return ParsedInputs(
                parse_results=[],
                commits=[],
                file_histories={},
                phase_timings={"parse_seconds": 0.2, "git_seconds": 0.1},
            )

    class _Signals:
        def run(self, *_args, **_kwargs):
            return SimpleNamespace(findings=[], phase_timings={"signals_seconds": 0.3})

    class _Scoring:
        def run(self, *_args, **_kwargs):
            return SimpleNamespace(
                findings=[],
                repo_score=0.0,
                module_scores=[],
                suppressed_count=0,
                context_tagged_count=0,
                suppressed_findings=[],
            )

    class _Assembly:
        def run(
            self, repo_path, _files, _artifacts, *, started_at, phase_timings=None, config=None
        ):
            _ = (started_at, config)
            return RepoAnalysis(
                repo_path=repo_path,
                analyzed_at=datetime.datetime.now(tz=datetime.UTC),
                drift_score=0.0,
                analysis_duration_seconds=0.6,
                phase_timings=dict(phase_timings or {}),
            )

    pipeline = AnalysisPipeline(
        ingestion_phase=_Ingestion(),
        signal_phase=_Signals(),
        scoring_phase=_Scoring(),
        result_assembly_phase=_Assembly(),
    )

    analysis = pipeline.run(
        Path("."),
        [],
        cfg,
        discover_duration_seconds=0.15,
    )

    assert analysis.phase_timings["discover_seconds"] == 0.15
    assert analysis.phase_timings["parse_seconds"] == 0.2
    assert analysis.phase_timings["git_seconds"] == 0.1
    assert analysis.phase_timings["signals_seconds"] == 0.3
    assert analysis.phase_timings["output_seconds"] >= 0.0
    assert analysis.phase_timings["total_seconds"] == 0.75


def test_ingestion_phase_continues_in_degraded_mode_on_parser_exception(
    tmp_path: Path,
) -> None:
    """Single parser failure must not abort the ingestion phase (#374)."""
    cfg = _config()
    (tmp_path / "good.py").write_text("def ok():\n    pass\n", encoding="utf-8")
    (tmp_path / "bad.py").write_text("def bad():\n    syntax error\n", encoding="utf-8")

    files = [_file_info("good.py"), _file_info("bad.py")]

    def _parse(path: Path, _repo_path: Path, language: str) -> ParseResult:
        if path == Path("bad.py"):
            raise RuntimeError("synthetic parser crash")
        return ParseResult(file_path=path, language=language)

    degradation = DegradationInfo(causes=set(), components=set(), events=[])
    phase = IngestionPhase(parse_file_fn=_parse, is_git_repo_fn=lambda _p: False)
    out = phase.run(
        tmp_path,
        files,
        cfg,
        since_days=30,
        workers=1,
        degradation=degradation,
    )

    # Analysis must complete and return results for both slots
    assert len(out.parse_results) == 2
    # Good file parsed normally
    good = out.parse_results[0]
    assert good.file_path == Path("good.py")
    assert good.parse_errors == []
    # Failed file present as empty stub with error recorded
    bad = out.parse_results[1]
    assert bad.file_path == Path("bad.py")
    assert bad.parse_errors != []
    assert "synthetic parser crash" in bad.parse_errors[0]
    # Degradation metadata recorded
    assert "parser_failure" in degradation.causes
    assert "parser" in degradation.components
    assert any(e["cause"] == "parser_failure" for e in degradation.events)
