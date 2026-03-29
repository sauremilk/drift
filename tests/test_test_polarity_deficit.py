"""Tests for Test Polarity Deficit signal (TPD)."""

from __future__ import annotations

import textwrap
from pathlib import Path

from drift.config import DriftConfig
from drift.models import ParseResult, SignalType
from drift.signals.test_polarity_deficit import TestPolarityDeficitSignal


def test_tpd_zero_assertion_density(tmp_path: Path) -> None:
    source = textwrap.dedent("""\
        def test_a():
            x = 1
            y = 2

        def test_b():
            value = "x"

        def test_c():
            assert 1 == 1

        def test_d():
            foo = {"a": 1}

        def test_e():
            assert True

        def test_f():
            z = [1, 2, 3]
    """)
    f = tmp_path / "tests" / "test_sample.py"
    f.parent.mkdir(parents=True)
    f.write_text(source)

    pr = ParseResult(
        file_path=Path("tests/test_sample.py"),
        language="python",
    )

    signal = TestPolarityDeficitSignal()
    signal._repo_path = tmp_path

    findings = signal.analyze([pr], {}, DriftConfig())

    assert any(
        f.rule_id == "assertion_density_deficit"
        and f.signal_type == SignalType.TEST_POLARITY_DEFICIT
        for f in findings
    )
