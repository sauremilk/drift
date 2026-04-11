from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

import drift.signals.base as signal_base
from drift.config import DriftConfig
from drift.models import CommitInfo, FileHistory, Finding, ParseResult, SignalType
from drift.signals.base import AnalysisContext, BaseSignal, create_signals


class _NoArgSignal(BaseSignal):
    @property
    def signal_type(self) -> SignalType:
        return SignalType.PATTERN_FRAGMENTATION

    @property
    def name(self) -> str:
        return "No Arg"

    def analyze(
        self,
        parse_results: list[ParseResult],
        file_histories: dict[str, FileHistory],
        config: DriftConfig,
    ) -> list[Finding]:
        return []


class _LegacyCtorSignal(BaseSignal):
    def __init__(
        self,
        repo_path: Path,
        embedding_service: object | None = None,
    ) -> None:
        super().__init__()
        self.legacy_repo_path = repo_path
        self.legacy_embedding_service = embedding_service

    @property
    def signal_type(self) -> SignalType:
        return SignalType.MUTANT_DUPLICATE

    @property
    def name(self) -> str:
        return "Legacy"

    def analyze(
        self,
        parse_results: list[ParseResult],
        file_histories: dict[str, FileHistory],
        config: DriftConfig,
    ) -> list[Finding]:
        return []


class _InvalidCtorSignal(BaseSignal):
    def __init__(self, required: int) -> None:
        super().__init__()
        self.required = required

    @property
    def signal_type(self) -> SignalType:
        return SignalType.DOC_IMPL_DRIFT

    @property
    def name(self) -> str:
        return "Invalid"

    def analyze(
        self,
        parse_results: list[ParseResult],
        file_histories: dict[str, FileHistory],
        config: DriftConfig,
    ) -> list[Finding]:
        return []


def _ctx(repo_path: Path, embedding_service: object | None = None) -> AnalysisContext:
    commits = [
        CommitInfo(
            hash="abc123",
            author="tester",
            email="test@example.com",
            timestamp=datetime.datetime.now(tz=datetime.UTC),
            message="test",
        )
    ]
    return AnalysisContext(
        repo_path=repo_path,
        config=DriftConfig(),
        embedding_service=(
            embedding_service if embedding_service is None else cast_to_embedding(embedding_service)
        ),
        commits=commits,
    )


def cast_to_embedding(value: object) -> Any:
    """Provide a typed embedding marker for contract tests without real model deps."""
    return value


def test_create_signals_binds_context_for_parameterless_signal(
    tmp_path: Path,
    monkeypatch,
) -> None:
    marker = object()
    monkeypatch.setattr(signal_base, "_SIGNAL_REGISTRY", [_NoArgSignal])

    signals = create_signals(_ctx(tmp_path, embedding_service=marker))

    assert len(signals) == 1
    signal = signals[0]
    assert isinstance(signal, _NoArgSignal)
    assert signal.repo_path == tmp_path
    assert signal.embedding_service is marker
    assert len(signal.commits) == 1


def test_create_signals_supports_legacy_constructor_contract(
    tmp_path: Path,
    monkeypatch,
) -> None:
    marker = object()
    monkeypatch.setattr(signal_base, "_SIGNAL_REGISTRY", [_LegacyCtorSignal])

    signals = create_signals(_ctx(tmp_path, embedding_service=marker))

    assert len(signals) == 1
    signal = signals[0]
    assert isinstance(signal, _LegacyCtorSignal)
    assert signal.legacy_repo_path == tmp_path
    assert signal.legacy_embedding_service is marker
    assert signal.repo_path == tmp_path
    assert signal.embedding_service is marker
    assert len(signal.commits) == 1


def test_create_signals_raises_clear_error_for_incompatible_constructor(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(signal_base, "_SIGNAL_REGISTRY", [_InvalidCtorSignal])

    try:
        create_signals(_ctx(tmp_path))
    except TypeError as exc:
        assert "could not be instantiated" in str(exc)
        assert "_InvalidCtorSignal" in str(exc)
    else:
        raise AssertionError("Expected TypeError for unsupported signal constructor")
