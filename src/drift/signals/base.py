"""Base interface for detection signals."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Literal, cast

from drift.config import DriftConfig
from drift.models import AnalyzerWarning, CommitInfo, FileHistory, Finding, ParseResult, SignalType

if TYPE_CHECKING:
    from drift.embeddings import EmbeddingService


@dataclass
class AnalysisContext:
    """Shared context passed to all signals during analysis.

    Provides standardised access to repo-level data so that signals
    don't need heterogeneous constructor arguments.
    """

    repo_path: Path
    config: DriftConfig
    parse_results: list[ParseResult] = field(default_factory=list)
    file_histories: dict[str, FileHistory] = field(default_factory=dict)
    embedding_service: EmbeddingService | None = None
    commits: list[CommitInfo] = field(default_factory=list)


@dataclass(slots=True)
class SignalCapabilities:
    """Explicit runtime capabilities provided by the analyzer to each signal."""

    repo_path: Path
    embedding_service: EmbeddingService | None
    commits: list[CommitInfo]

    @classmethod
    def from_analysis_context(cls, ctx: AnalysisContext) -> SignalCapabilities:
        """Build a capabilities payload from the full analysis context."""
        return cls(
            repo_path=ctx.repo_path,
            embedding_service=ctx.embedding_service,
            commits=ctx.commits,
        )


class BaseSignal(ABC):
    """Abstract base class for all detection signals.

    Each signal analyzes a specific dimension of architectural drift
    and produces findings with scores between 0.0 (no drift) and
    1.0 (severe drift).
    """

    incremental_scope: ClassVar[
        Literal["file_local", "cross_file", "git_dependent"]
    ] = "cross_file"
    cache_dependency_scope: ClassVar[
        Literal["file_local", "module_wide", "repo_wide", "git_dependent"]
    ] = "repo_wide"
    uses_embeddings: ClassVar[bool] = False

    _repo_path: Path | None
    _embedding_service: EmbeddingService | None
    _commits: list[CommitInfo]

    def __init__(
        self,
        *,
        repo_path: Path | None = None,
        embedding_service: EmbeddingService | None = None,
        commits: list[CommitInfo] | None = None,
    ) -> None:
        self._repo_path = repo_path
        self._embedding_service = embedding_service
        self._commits = commits if commits is not None else []
        self._warnings: list[AnalyzerWarning] = []

    def emit_warning(self, message: str, *, skipped: bool = True) -> None:
        """Record a non-finding diagnostic for this signal."""
        self._warnings.append(
            AnalyzerWarning(
                signal_type=str(self.signal_type),
                message=message,
                skipped=skipped,
            )
        )

    def bind_context(self, capabilities: SignalCapabilities) -> None:
        """Bind analyzer-provided runtime capabilities to this signal instance."""
        self._repo_path = capabilities.repo_path
        self._embedding_service = capabilities.embedding_service
        self._commits = capabilities.commits

    @property
    def repo_path(self) -> Path | None:
        """Repository root path if provided by the analyzer."""
        return self._repo_path

    @property
    def embedding_service(self) -> EmbeddingService | None:
        """Embedding service if enabled for the current analysis run."""
        return self._embedding_service

    @property
    def commits(self) -> list[CommitInfo]:
        """Commit history available for co-change style analysis."""
        return self._commits

    @property
    @abstractmethod
    def signal_type(self) -> SignalType: ...

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def analyze(
        self,
        parse_results: list[ParseResult],
        file_histories: dict[str, FileHistory],
        config: DriftConfig,
    ) -> list[Finding]:
        """Run this signal's detection logic and return findings."""
        ...


# ---------------------------------------------------------------------------
# Signal registry
# ---------------------------------------------------------------------------

_SIGNAL_REGISTRY: list[type[BaseSignal]] = []
_SIGNAL_TYPE_VALUE_CACHE: dict[type[BaseSignal], str] = {}


def register_signal(cls: type[BaseSignal]) -> type[BaseSignal]:
    """Class decorator that registers a signal for automatic discovery."""
    _SIGNAL_REGISTRY.append(cls)
    return cls


def _instantiate_signal(
    cls: type[BaseSignal],
    capabilities: SignalCapabilities,
) -> BaseSignal:
    """Instantiate a signal class with explicit contract and legacy fallback."""
    try:
        return cls()
    except TypeError:
        legacy_ctor = cast(Callable[..., BaseSignal], cls)
        try:
            return legacy_ctor(
                repo_path=capabilities.repo_path,
                embedding_service=capabilities.embedding_service,
            )
        except TypeError as legacy_error:
            raise TypeError(
                f"Signal '{cls.__name__}' could not be instantiated. "
                "Expected either a parameterless constructor or the legacy "
                "constructor signature (__init__(repo_path=..., embedding_service=...))."
            ) from legacy_error


def create_signals(
    ctx: AnalysisContext,
    *,
    active_signals: set[str] | None = None,
) -> list[BaseSignal]:
    """Instantiate registered signals with optional pre-filtering.

    Preferred contract:
    1. Parameterless constructor on the signal class
    2. Analyzer calls ``bind_context`` with explicit runtime capabilities

    Backward compatibility:
    Legacy signal constructors accepting ``repo_path`` and
    ``embedding_service`` keywords are still supported.
    """
    capabilities = SignalCapabilities.from_analysis_context(ctx)

    signals: list[BaseSignal] = []
    for cls in _SIGNAL_REGISTRY:
        if active_signals is not None:
            cached_type = _SIGNAL_TYPE_VALUE_CACHE.get(cls)
            if cached_type is None:
                probe = _instantiate_signal(cls, capabilities)
                cached_type = str(probe.signal_type)
                _SIGNAL_TYPE_VALUE_CACHE[cls] = cached_type
                if cached_type not in active_signals:
                    continue
                probe.bind_context(capabilities)
                signals.append(probe)
                continue
            if cached_type not in active_signals:
                continue
        inst = _instantiate_signal(cls, capabilities)
        inst.bind_context(capabilities)
        signals.append(inst)
    return signals


def registered_signals() -> list[type[BaseSignal]]:
    """Return a copy of the current signal registry (for testing)."""
    return list(_SIGNAL_REGISTRY)
