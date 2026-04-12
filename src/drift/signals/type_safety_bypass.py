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
from drift.ingestion.test_detection import classify_file_context
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
_SDK_IMPORT_RE = re.compile(
    r"from\s+[\"'](?:@?playwright(?:/test)?|playwright-core|discord\.js|@discordjs/[^\"']+)[\"']"
)
_EVENT_EMITTER_NON_NULL_RE = re.compile(
    r"\.(?:on|off|once|addlistener|removelistener)!\s*$",
    re.IGNORECASE,
)
_PLAYWRIGHT_LOCATOR_NON_NULL_RE = re.compile(
    r"\.locator\s*\(.*!\s*\)",
    re.IGNORECASE,
)
_DOUBLE_CAST_ASSIGN_RE = re.compile(
    r"\b(?:const|let|var)\s+(?P<var>[A-Za-z_$][\w$]*)\s*=\s*.+\bas\s+unknown\s+as\b",
    re.IGNORECASE,
)

_DEFAULT_THRESHOLD = 5


def _is_runtime_guarded_playwright_double_cast(
    source_lines: list[str],
    cast_line_no: int,
    has_sdk_import: bool,
) -> bool:
    """Return True if a double-cast assignment is guarded by an immediate runtime check.

    Bounded heuristic for Playwright duck-typing patterns where a value cast via
    ``as unknown as T`` is followed by ``if (!var._member) { throw ... }``.
    """
    if not has_sdk_import:
        return False
    if cast_line_no < 1 or cast_line_no > len(source_lines):
        return False

    assign_line = source_lines[cast_line_no - 1]
    assign_match = _DOUBLE_CAST_ASSIGN_RE.search(assign_line)
    if not assign_match:
        return False

    var_name = assign_match.group("var")
    guard_window = "\n".join(source_lines[cast_line_no : cast_line_no + 10])
    guard_re = re.compile(
        rf"if\s*\(\s*!\s*{re.escape(var_name)}\.(?:_[A-Za-z_$][\w$]*)\s*\)\s*\{{[\s\S]*?\bthrow\b",
        re.IGNORECASE,
    )
    return bool(guard_re.search(guard_window))


def _count_bypasses(source: str, language: str) -> list[dict[str, str | int]]:
    """Count type-safety bypass patterns in TS/TSX source.

    Returns a list of dicts with keys: kind, line, detail.
    """
    tree = ts_parse_source(source, language)
    if tree is None:
        return []

    root, source_bytes = tree
    source_lines = source.splitlines()
    bypasses: list[dict[str, str | int]] = []
    has_sdk_import = bool(_SDK_IMPORT_RE.search(source))

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
                    cast_line_no = node.parent.start_point[0] + 1
                    is_guarded_playwright_duck_cast = _is_runtime_guarded_playwright_double_cast(
                        source_lines,
                        cast_line_no,
                        has_sdk_import,
                    )
                    kind = "double_cast"
                    detail = "double cast (as unknown as T)"
                    if is_guarded_playwright_duck_cast:
                        kind = "double_cast_sdk_guarded"
                        detail = "double cast (as unknown as T), SDK duck-typing with runtime guard"
                    bypasses.append(
                        {
                            "kind": kind,
                            "line": cast_line_no,
                            "detail": detail,
                        }
                    )

        # Non-null assertion (postfix !)
        elif node.type == "non_null_expression":
            node_text = ts_node_text(node, source_bytes).strip()
            line_no = node.start_point[0] + 1
            line_text = source_lines[line_no - 1] if 0 <= line_no - 1 < len(source_lines) else ""
            is_sdk_event_emitter = bool(
                has_sdk_import and _EVENT_EMITTER_NON_NULL_RE.search(node_text)
            )
            is_sdk_locator_arg = bool(
                has_sdk_import and _PLAYWRIGHT_LOCATOR_NON_NULL_RE.search(line_text)
            )
            kind = "non_null_assertion"
            detail = "non-null assertion (!)"
            if is_sdk_event_emitter:
                kind = "non_null_assertion_sdk"
                detail = "non-null assertion (!), SDK event-emitter pattern"
            elif is_sdk_locator_arg:
                kind = "non_null_assertion_sdk"
                detail = "non-null assertion (!), SDK locator-argument pattern"
            bypasses.append(
                {
                    "kind": kind,
                    "line": line_no,
                    "detail": detail,
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


def _effective_bypass_count(bypasses: list[dict[str, str | int]]) -> float:
    """Return weighted bypass count for severity scoring.

    Some SDK-specific event-emitter patterns use non-null assertions as an
    idiomatic TypeScript interop pattern. These remain visible, but contribute
    less to severity than direct bypasses such as ``as any`` or directives.
    """

    weight_by_kind: dict[str, float] = {
        "double_cast_sdk_guarded": 0.0,
        "non_null_assertion_sdk": 0.0,
    }

    effective = 0.0
    for bypass in bypasses:
        kind = str(bypass.get("kind", ""))
        effective += weight_by_kind.get(kind, 1.0)
    return effective


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
        handling = config.test_file_handling or "exclude"
        findings: list[Finding] = []

        for pr in parse_results:
            if pr.language not in _TS_LANGUAGES:
                continue
            path_context = classify_file_context(pr.file_path)
            if path_context == "test" and handling == "exclude":
                continue

            source = _read_source(pr.file_path, self.repo_path)
            if source is None:
                continue

            bypasses = _count_bypasses(source, pr.language)
            if not bypasses:
                continue

            bypass_count = len(bypasses)
            effective_count = _effective_bypass_count(bypasses)
            score = round(min(1.0, effective_count / max(1, threshold)), 3)
            if path_context == "test" and handling == "reduce_severity":
                score = round(score * 0.4, 3)

            severity = (
                Severity.HIGH if score >= 0.7 else Severity.MEDIUM if score >= 0.3 else Severity.LOW
            )
            if path_context == "test" and handling == "reduce_severity":
                severity = Severity.LOW

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
                        "effective_bypass_count": round(effective_count, 3),
                        "bypasses": bypasses[:20],
                        "kind_distribution": kinds,
                        "finding_context": path_context,
                    },
                    finding_context=path_context,
                    rule_id="type_safety_bypass",
                )
            )

        return findings


def _read_source(file_path: Path, repo_path: Path | None = None) -> str | None:
    """Read source file, returning None on error."""
    target = repo_path / file_path if repo_path else file_path
    try:
        return target.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeDecodeError):
        return None
