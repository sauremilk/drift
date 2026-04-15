"""Regression test for issue #367.

TypeSafetyBypassSignal must NOT emit a finding when every detected bypass
pattern is fully suppressed to an effective count of 0.0 by
``_effective_bypass_count()`` (e.g. SDK-guarded double casts).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from drift.ingestion.ts_parser import tree_sitter_available

needs_tree_sitter = pytest.mark.skipif(
    not tree_sitter_available(),
    reason="tree-sitter-typescript not installed",
)


@needs_tree_sitter
def test_issue_367_sdk_guarded_double_cast_emits_no_finding(tmp_path: Path) -> None:
    """A file with only SDK-guarded double casts must produce zero findings."""
    from drift.config import DriftConfig
    from drift.models import ParseResult
    from drift.signals.type_safety_bypass import TypeSafetyBypassSignal

    # Playwright-style import + guarded double cast (double_cast_sdk_guarded → weight 0.0)
    source = (
        'import { Page } from "@playwright/test";\n'
        "const page = context as unknown as Page;\n"
        "if (!page._client) { throw new Error('not a Page'); }\n"
    )

    file_path = tmp_path / "sdk.ts"
    file_path.write_text(source, encoding="utf-8")

    parse_result = ParseResult(
        file_path=file_path,
        language="typescript",
        functions=[],
        classes=[],
        imports=[],
        patterns=[],
        line_count=3,
    )

    signal = TypeSafetyBypassSignal()
    findings = signal.analyze([parse_result], {}, DriftConfig())

    assert findings == [], (
        f"Expected no findings for fully suppressed SDK-guarded double cast, "
        f"got: {findings}"
    )


@needs_tree_sitter
def test_issue_367_mixed_suppressed_and_real_bypasses_still_fires(tmp_path: Path) -> None:
    """If there is at least one non-zero-weight bypass, the signal must still fire."""
    from drift.config import DriftConfig
    from drift.models import ParseResult
    from drift.signals.type_safety_bypass import TypeSafetyBypassSignal

    # One SDK-guarded cast (weight 0.0) + one bare 'as any' (weight 1.0)
    source = (
        'import { Page } from "@playwright/test";\n'
        "const page = context as unknown as Page;\n"
        "if (!page._client) { throw new Error('not a Page'); }\n"
        "const x = someValue as any;\n"
    )

    file_path = tmp_path / "mixed.ts"
    file_path.write_text(source, encoding="utf-8")

    parse_result = ParseResult(
        file_path=file_path,
        language="typescript",
        functions=[],
        classes=[],
        imports=[],
        patterns=[],
        line_count=4,
    )

    signal = TypeSafetyBypassSignal()
    findings = signal.analyze([parse_result], {}, DriftConfig())

    assert len(findings) == 1, (
        f"Expected exactly one finding when 'as any' is present, got: {findings}"
    )
    assert findings[0].score > 0.0, "Score must be > 0.0 when real bypasses exist"
