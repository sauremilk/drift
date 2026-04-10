"""Unit tests for CoChangeCouplingSignal (CCC)."""

from __future__ import annotations

import datetime
from pathlib import Path

import pytest

from drift.config import DriftConfig
from drift.models import CommitInfo, ImportInfo, ParseResult, SignalType
from drift.precision import (
    ensure_signals_registered,
    has_matching_finding,
    run_fixture,
)
from drift.signals.base import SignalCapabilities
from drift.signals.co_change_coupling import CoChangeCouplingSignal
from tests.fixtures.ground_truth import FIXTURES_BY_SIGNAL, GroundTruthFixture


def _commit(
    idx: int,
    files: list[str],
    *,
    message: str = "feat: update modules",
    author: str = "dev",
    email: str | None = None,
    is_ai: bool = False,
) -> CommitInfo:
    ts = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC) + datetime.timedelta(days=idx)
    return CommitInfo(
        hash=f"c{idx:04d}",
        author=author,
        email=email or f"{author}@example.com",
        timestamp=ts,
        message=message,
        files_changed=files,
        is_ai_attributed=is_ai,
        ai_confidence=0.9 if is_ai else 0.0,
    )


def _pr(path: str, imports: list[ImportInfo] | None = None) -> ParseResult:
    return ParseResult(
        file_path=Path(path),
        language="python",
        functions=[],
        classes=[],
        imports=imports or [],
    )


def _run_signal(parse_results: list[ParseResult], commits: list[CommitInfo]):
    signal = CoChangeCouplingSignal()
    signal.bind_context(
        SignalCapabilities(
            repo_path=Path("."),
            embedding_service=None,
            commits=commits,
        )
    )
    return signal.analyze(parse_results, {}, DriftConfig())


class TestCoChangeCouplingSignal:
    def test_true_positive_hidden_coupling_without_import_edge(self) -> None:
        parse_results = [
            _pr("src/order_service.py"),
            _pr("src/payment_rules.py"),
            _pr("src/helpers.py"),
        ]

        commits = [
            _commit(1, ["src/order_service.py", "src/payment_rules.py"]),
            _commit(2, ["src/order_service.py", "src/payment_rules.py"]),
            _commit(3, ["src/order_service.py", "src/payment_rules.py"]),
            _commit(4, ["src/order_service.py", "src/payment_rules.py"]),
            _commit(5, ["src/helpers.py"]),
            _commit(
                6,
                ["src/order_service.py", "src/payment_rules.py"],
                message="Merge pull request #42 from feature/x",
            ),
            _commit(
                7,
                ["src/order_service.py", "src/payment_rules.py"],
                message="chore: automated cleanup",
                author="github-actions[bot]",
                email="github-actions[bot]@users.noreply.github.com",
            ),
            _commit(8, ["src/helpers.py", "src/order_service.py"]),
        ]

        findings = _run_signal(parse_results, commits)
        assert len(findings) >= 1

        first = findings[0]
        assert first.signal_type == SignalType.CO_CHANGE_COUPLING
        assert first.file_path == Path("src/order_service.py")
        assert Path("src/payment_rules.py") in first.related_files
        assert first.metadata["explicit_dependency"] is False
        assert first.metadata["co_change_commits"] >= 4
        assert first.score >= 0.2
        assert first.fix is not None
        assert "Analyze the implicit coupling" in first.fix
        assert "Analysiere" not in first.fix

    def test_true_negative_when_explicit_import_exists(self) -> None:
        parse_results = [
            _pr(
                "src/order_service.py",
                imports=[
                    ImportInfo(
                        source_file=Path("src/order_service.py"),
                        imported_module="src.payment_rules",
                        imported_names=[],
                        line_number=1,
                        is_relative=False,
                    )
                ],
            ),
            _pr("src/payment_rules.py"),
            _pr("src/helpers.py"),
        ]

        commits = [
            _commit(1, ["src/order_service.py", "src/payment_rules.py"]),
            _commit(2, ["src/order_service.py", "src/payment_rules.py"]),
            _commit(3, ["src/order_service.py", "src/payment_rules.py"]),
            _commit(4, ["src/order_service.py", "src/payment_rules.py"]),
            _commit(5, ["src/helpers.py", "src/order_service.py"]),
            _commit(6, ["src/helpers.py"]),
            _commit(7, ["src/order_service.py", "src/payment_rules.py"]),
            _commit(8, ["src/helpers.py", "src/payment_rules.py"]),
        ]

        findings = _run_signal(parse_results, commits)
        assert findings == []

    def test_graceful_degradation_with_insufficient_history(self) -> None:
        parse_results = [_pr("src/a.py"), _pr("src/b.py")]
        commits = [
            _commit(1, ["src/a.py", "src/b.py"]),
            _commit(2, ["src/a.py", "src/b.py"]),
        ]

        findings = _run_signal(parse_results, commits)
        assert findings == []


# ---------------------------------------------------------------------------
# Parametrized ground-truth fixture tests
# ---------------------------------------------------------------------------

ensure_signals_registered()

_CCC_FIXTURES = FIXTURES_BY_SIGNAL.get(SignalType.CO_CHANGE_COUPLING, [])


@pytest.mark.parametrize(
    "fixture",
    _CCC_FIXTURES,
    ids=[f.name for f in _CCC_FIXTURES],
)
def test_ccc_ground_truth(fixture: GroundTruthFixture, tmp_path: Path) -> None:
    """Verify CCC ground-truth fixtures produce expected findings."""
    findings, _warnings = run_fixture(
        fixture, tmp_path, signal_filter={SignalType.CO_CHANGE_COUPLING}
    )
    for exp in fixture.expected:
        if exp.signal_type != SignalType.CO_CHANGE_COUPLING:
            continue
        detected = has_matching_finding(findings, exp)
        if exp.should_detect:
            assert detected, (
                f"[FN] {fixture.name}: expected CCC at {exp.file_path} "
                f"but not found. Findings: {[(f.signal_type, f.file_path) for f in findings]}"
            )
        else:
            assert not detected, (
                f"[FP] {fixture.name}: did NOT expect CCC at {exp.file_path} "
                f"but found. Findings: {[(f.signal_type, f.file_path) for f in findings]}"
            )
