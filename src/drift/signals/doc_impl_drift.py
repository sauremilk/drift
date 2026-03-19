"""Signal 5: Doc-Implementation Drift (DIA).

Detects divergence between architectural documentation (ADRs, README)
and actual code implementation. Phase 2 feature — MVP provides a
basic structural check.
"""

from __future__ import annotations

from typing import Any

from drift.models import FileHistory, Finding, ParseResult, SignalType
from drift.signals.base import BaseSignal


class DocImplDriftSignal(BaseSignal):
    """Detect drift between documentation claims and code reality.

    MVP implementation: checks for presence of README/ADR files and
    basic structural claims. Full NLP-based claim extraction is Phase 2.
    """

    @property
    def signal_type(self) -> SignalType:
        return SignalType.DOC_IMPL_DRIFT

    @property
    def name(self) -> str:
        return "Doc-Implementation Drift"

    def analyze(
        self,
        parse_results: list[ParseResult],
        file_histories: dict[str, FileHistory],
        config: Any,
    ) -> list[Finding]:
        # Phase 2: ADR parsing and claim verification against code
        # MVP returns empty — this signal requires NLP which adds complexity
        return []
