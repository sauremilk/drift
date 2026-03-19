"""Base interface for detection signals."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from drift.models import FileHistory, Finding, ParseResult, SignalType


class BaseSignal(ABC):
    """Abstract base class for all detection signals.

    Each signal analyzes a specific dimension of architectural drift
    and produces findings with scores between 0.0 (no drift) and
    1.0 (severe drift).
    """

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
        config: Any,
    ) -> list[Finding]:
        """Run this signal's detection logic and return findings."""
        ...
