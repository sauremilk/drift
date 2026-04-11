"""Signal: Type Safety Bypass (TSB).

Detects patterns that circumvent TypeScript's type system:
- ``as any`` casts
- Double casts (``as unknown as T``)
- Non-null assertions (``!``)
- ``@ts-ignore`` directives
- ``@ts-expect-error`` directives

Only fires on TypeScript/TSX files. Deterministic, AST-only, LLM-free.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import ClassVar, Literal

from drift.config import DriftConfig
from drift.models import (
    FileHistory,
    Finding,
    ParseResult,
    Severity,
    SignalType,
)
from drift.signals._utils import _TS_LANGUAGES, ts_node_text, ts_parse_source, ts_walk
from drift.signals.base import BaseSignal, register_signal

_TS_DIRECTIVE_RE = re.compile(r"@ts-(ignore|expect-error)")

_DEFAULT_THRESHOLD = 5


def _count_bypasses(source: str, language: str) -> list[dict[str, str | int]]:
    """Count type-safety bypass patterns in TS/TSX source.

    Returns a list of dicts with keys: kind, line, detail.
    """
    tree = ts_parse_source(source, language)
    if tree is None:
        return []

    root, source_bytes = tree
    bypasses: list[dict[str, str | int]] = []

    for node in ts_walk(root):
        # as any
        if node.type == "as_expression":
            # Check if target type is 'any'
            type_node = None
            for child in node.children:
                if child.type in (
                    "type_identifier",
                    "predefined_type",
                    "generic_type",
                ):
                    type_node = child
            if type_node:
                type_text = ts_node_text(type_node, source_bytes)
                if type_text == "any":
                    bypasses.append(
                        {
                            "kind": "as_any",
                            "line": node.start_point[0] + 1,
                            "detail": "as any cast",
                        }
                    )
                elif type_text == "unknown" and node.parent and node.parent.type == "as_expression":
                    bypasses.append(
                        {
                            "kind": "double_cast",
                            "line": node.parent.start_point[0] + 1,
                            "detail": "double cast (as unknown as T)",
                        }
                    )

        # Non-null assertion (postfix !)
        elif node.type == "non_null_expression":
            bypasses.append(
                {
                    "kind": "non_null_assertion",
                    "line": node.start_point[0] + 1,
                    "detail": "non-null assertion (!)",
                }
            )

        # @ts-ignore / @ts-expect-error in comments
        elif node.type == "comment":
            text = ts_node_text(node, source_bytes)
            match = _TS_DIRECTIVE_RE.search(text)
            if match:
                directive = match.group(1)
                bypasses.append(
                    {
                        "kind": f"ts_{directive.replace('-', '_')}",
                        "line": node.start_point[0] + 1,
                        "detail": f"@ts-{directive} directive",
                    }
                )

    return bypasses


@register_signal
class TypeSafetyBypassSignal(BaseSignal):
    """Detect type safety bypass patterns in TypeScript files."""

    incremental_scope: ClassVar[Literal["file_local", "cross_file", "git_dependent"]] = "file_local"

    @property
    def signal_type(self) -> SignalType:
        return SignalType.TYPE_SAFETY_BYPASS

    @property
    def name(self) -> str:
        return "Type Safety Bypass"

    def analyze(
        self,
        parse_results: list[ParseResult],
        file_histories: dict[str, FileHistory],
        config: DriftConfig,
    ) -> list[Finding]:
        threshold = getattr(config.thresholds, "tsb_bypass_threshold", _DEFAULT_THRESHOLD)
        findings: list[Finding] = []

        for pr in parse_results:
            if pr.language not in _TS_LANGUAGES:
                continue

            source = _read_source(pr.file_path)
            if source is None:
                continue

            bypasses = _count_bypasses(source, pr.language)
            if not bypasses:
                continue

            bypass_count = len(bypasses)
            score = round(min(1.0, bypass_count / max(1, threshold)), 3)

            severity = (
                Severity.HIGH if score >= 0.7 else Severity.MEDIUM if score >= 0.3 else Severity.LOW
            )

            kinds: dict[str, int] = {}
            for b in bypasses:
                kind = str(b["kind"])
                kinds[kind] = kinds.get(kind, 0) + 1

            kind_summary = ", ".join(f"{count}× {kind}" for kind, count in sorted(kinds.items()))

            findings.append(
                Finding(
                    signal_type=self.signal_type,
                    severity=severity,
                    score=score,
                    title=(
                        f"{bypass_count} type safety bypass"
                        f"{'es' if bypass_count != 1 else ''} "
                        f"in {pr.file_path.name}"
                    ),
                    description=(
                        f"{pr.file_path} contains {bypass_count} type safety "
                        f"bypass pattern(s): {kind_summary}. "
                        f"These weaken TypeScript's type guarantees and "
                        f"can mask bugs at compile time."
                    ),
                    file_path=pr.file_path,
                    start_line=int(bypasses[0]["line"]),
                    fix=(
                        f"Replace type safety bypasses with proper type guards, "
                        f"narrowing, or explicit type definitions. "
                        f"Found: {kind_summary}."
                    ),
                    metadata={
                        "bypass_count": bypass_count,
                        "bypasses": bypasses[:20],
                        "kind_distribution": kinds,
                    },
                    rule_id="type_safety_bypass",
                )
            )

        return findings


def _read_source(file_path: Path) -> str | None:
    """Read source file, returning None on error."""
    try:
        return file_path.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeDecodeError):
        return None
