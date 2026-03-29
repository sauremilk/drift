"""Tests for Guard Clause Deficit signal (GCD)."""

from __future__ import annotations

import textwrap
from pathlib import Path

from drift.config import DriftConfig
from drift.models import FunctionInfo, ParseResult, SignalType
from drift.signals.guard_clause_deficit import GuardClauseDeficitSignal


def _fn(name: str, file_path: str, start: int, end: int, *, complexity: int = 8) -> FunctionInfo:
    return FunctionInfo(
        name=name,
        file_path=Path(file_path),
        start_line=start,
        end_line=end,
        language="python",
        complexity=complexity,
        loc=end - start + 1,
        parameters=["a", "b"],
    )


def test_gcd_deep_nesting_detection(tmp_path: Path) -> None:
    source = textwrap.dedent("""\
        def nested(a, b):
            if a:
                for i in range(3):
                    if i > 0:
                        while b:
                            if a > b:
                                return a - b
            return 0

        def plain(a, b):
            if not a:
                return 0
            return a + b

        def helper(a, b):
            if a < 0:
                return 0
            return b
    """)
    f = tmp_path / "app" / "service.py"
    f.parent.mkdir(parents=True)
    f.write_text(source)

    pr = ParseResult(
        file_path=Path("app/service.py"),
        language="python",
        functions=[
            _fn("nested", "app/service.py", 1, 8, complexity=10),
            _fn("plain", "app/service.py", 10, 13, complexity=6),
            _fn("helper", "app/service.py", 15, 18, complexity=6),
        ],
    )

    signal = GuardClauseDeficitSignal()
    signal._repo_path = tmp_path

    findings = signal.analyze([pr], {}, DriftConfig())

    assert any(
        f.rule_id == "deep_nesting" and f.signal_type == SignalType.GUARD_CLAUSE_DEFICIT
        for f in findings
    )
