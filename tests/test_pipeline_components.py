"""Targeted unit tests for decomposed analyzer pipeline phases."""

from __future__ import annotations

import importlib
from pathlib import Path

from drift.cache import ParseCache
from drift.config import DriftConfig
from drift.models import (
    ClassInfo,
    FileInfo,
    Finding,
    FunctionInfo,
    ImportInfo,
    ParseResult,
    PatternCategory,
    PatternInstance,
    Severity,
    SignalType,
)
from drift.pipeline import DegradationInfo, IngestionPhase, ScoringPhase, SignalPhase


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

    def _impact_assigner(_findings: list[Finding], weights: dict) -> None:
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
