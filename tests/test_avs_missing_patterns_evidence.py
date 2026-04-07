"""Empirical evidence suite for newly added AVS patterns.

This suite provides deterministic, reproducible evidence for:
- God Module detection
- Unstable Dependency detection
- Hidden logical coupling (co-change without import edge)

The tests use controlled synthetic fixtures and compute per-pattern
precision/recall style metrics to enforce a minimum evidence bar for
new AVS capabilities.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from pathlib import Path

import pytest

from drift.config import DriftConfig
from drift.models import CommitInfo, FileHistory, ImportInfo, ParseResult
from drift.signals.architecture_violation import ArchitectureViolationSignal

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pr(path: str, imports: list[ImportInfo]) -> ParseResult:
    return ParseResult(file_path=Path(path), language="python", imports=imports)


def _imp(source: str, module: str, line: int = 1) -> ImportInfo:
    return ImportInfo(
        source_file=Path(source),
        imported_module=module,
        imported_names=[],
        line_number=line,
    )


def _commit(files: list[str], msg: str = "change") -> CommitInfo:
    return CommitInfo(
        hash="emp123",
        author="qa",
        email="qa@drift.dev",
        timestamp=datetime.datetime.now(tz=datetime.UTC),
        message=msg,
        files_changed=files,
    )


@dataclass
class Scenario:
    name: str
    target: str
    expected_detect: bool
    parse_results: list[ParseResult]
    file_histories: dict[str, FileHistory]
    commits: list[CommitInfo]


def _detected(findings: list, marker: str) -> bool:
    return any(marker in f.title for f in findings)


# ---------------------------------------------------------------------------
# Scenario corpus
# ---------------------------------------------------------------------------


def _build_scenarios() -> list[Scenario]:
    now = datetime.datetime.now(tz=datetime.UTC)

    god_positive = Scenario(
        name="god_positive",
        target="god",
        expected_detect=True,
        parse_results=[
            _pr("core/hub.py", [
                _imp("core/hub.py", "services.a"),
                _imp("core/hub.py", "services.b"),
                _imp("core/hub.py", "services.c"),
                _imp("core/hub.py", "services.d"),
            ]),
            _pr("services/a.py", [_imp("services/a.py", "core.hub")]),
            _pr("services/b.py", [_imp("services/b.py", "core.hub")]),
            _pr("services/c.py", [_imp("services/c.py", "core.hub")]),
            _pr("services/d.py", [_imp("services/d.py", "core.hub")]),
            _pr("services/e.py", [_imp("services/e.py", "core.hub")]),
            _pr("api/routes.py", [_imp("api/routes.py", "core.hub")]),
        ],
        file_histories={},
        commits=[],
    )

    god_negative = Scenario(
        name="god_negative",
        target="god",
        expected_detect=False,
        parse_results=[
            _pr("api/routes.py", [_imp("api/routes.py", "services.auth")]),
            _pr("services/auth.py", [_imp("services/auth.py", "db.models")]),
            _pr("services/payments.py", [_imp("services/payments.py", "db.models")]),
            _pr("db/models.py", []),
            _pr("utils/helpers.py", []),
            _pr("config/settings.py", []),
        ],
        file_histories={},
        commits=[],
    )

    unstable_positive = Scenario(
        name="unstable_positive",
        target="unstable",
        expected_detect=True,
        parse_results=[
            _pr("core/stable.py", [_imp("core/stable.py", "infra.unstable")]),
            _pr("infra/unstable.py", [_imp("infra/unstable.py", "api.routes")]),
            _pr("services/a.py", [_imp("services/a.py", "core.stable")]),
            _pr("services/b.py", [_imp("services/b.py", "core.stable")]),
            _pr("api/routes.py", []),
        ],
        file_histories={
            "infra/unstable.py": FileHistory(
                path=Path("infra/unstable.py"),
                total_commits=16,
                unique_authors=4,
                ai_attributed_commits=0,
                change_frequency_30d=1.6,
                defect_correlated_commits=3,
                last_modified=now,
                first_seen=now - datetime.timedelta(days=120),
            )
        },
        commits=[],
    )

    unstable_negative = Scenario(
        name="unstable_negative",
        target="unstable",
        expected_detect=False,
        parse_results=[
            _pr("core/stable.py", [_imp("core/stable.py", "infra.stable")]),
            _pr("infra/stable.py", [_imp("infra/stable.py", "db.models")]),
            _pr("services/a.py", [_imp("services/a.py", "core.stable")]),
            _pr("services/b.py", [_imp("services/b.py", "core.stable")]),
            _pr("db/models.py", []),
        ],
        file_histories={
            "infra/stable.py": FileHistory(
                path=Path("infra/stable.py"),
                total_commits=10,
                unique_authors=2,
                ai_attributed_commits=0,
                change_frequency_30d=0.2,
                defect_correlated_commits=0,
                last_modified=now,
                first_seen=now - datetime.timedelta(days=120),
            )
        },
        commits=[],
    )

    hidden_positive = Scenario(
        name="hidden_positive",
        target="hidden",
        expected_detect=True,
        parse_results=[
            _pr("services/auth.py", []),
            _pr("handlers/billing.py", []),
            _pr("services/notifications.py", []),
        ],
        file_histories={},
        commits=[
            _commit(["services/auth.py", "handlers/billing.py"]),
            _commit(["services/auth.py", "handlers/billing.py"]),
            _commit(["services/auth.py", "handlers/billing.py"]),
        ],
    )

    hidden_negative = Scenario(
        name="hidden_negative",
        target="hidden",
        expected_detect=False,
        parse_results=[
            _pr("services/auth.py", [_imp("services/auth.py", "handlers.billing")]),
            _pr("handlers/billing.py", []),
        ],
        file_histories={},
        commits=[
            _commit(["services/auth.py", "handlers/billing.py"]),
            _commit(["services/auth.py", "handlers/billing.py"]),
            _commit(["services/auth.py", "handlers/billing.py"]),
        ],
    )

    return [
        god_positive,
        god_negative,
        unstable_positive,
        unstable_negative,
        hidden_positive,
        hidden_negative,
    ]


MARKERS = {
    "god": "God module candidate",
    "unstable": "Unstable dependency",
    "hidden": "Hidden coupling",
}


@pytest.mark.parametrize("scenario", _build_scenarios(), ids=lambda s: s.name)
def test_avs_missing_patterns_scenarios(scenario: Scenario) -> None:
    """Per-scenario expectation check for new AVS pattern coverage."""
    signal = ArchitectureViolationSignal()
    signal._commits = scenario.commits  # type: ignore[attr-defined]
    findings = signal.analyze(scenario.parse_results, scenario.file_histories, DriftConfig())

    detected = _detected(findings, MARKERS[scenario.target])
    assert detected == scenario.expected_detect, (
        f"Scenario {scenario.name} expected_detect={scenario.expected_detect} "
        f"but got detected={detected}. "
        f"Titles: {[f.title for f in findings]}"
    )


def test_avs_missing_patterns_empirical_metrics() -> None:
    """Empirical mini-benchmark with minimum evidence thresholds.

    Thresholds are conservative and deterministic for this synthetic corpus.
    """
    scenarios = _build_scenarios()
    signal = ArchitectureViolationSignal()

    counts: dict[str, dict[str, int]] = {
        "god": {"tp": 0, "fp": 0, "fn": 0, "tn": 0},
        "unstable": {"tp": 0, "fp": 0, "fn": 0, "tn": 0},
        "hidden": {"tp": 0, "fp": 0, "fn": 0, "tn": 0},
    }

    for sc in scenarios:
        signal._commits = sc.commits  # type: ignore[attr-defined]
        findings = signal.analyze(sc.parse_results, sc.file_histories, DriftConfig())
        detected = _detected(findings, MARKERS[sc.target])

        if sc.expected_detect and detected:
            counts[sc.target]["tp"] += 1
        elif sc.expected_detect and not detected:
            counts[sc.target]["fn"] += 1
        elif (not sc.expected_detect) and detected:
            counts[sc.target]["fp"] += 1
        else:
            counts[sc.target]["tn"] += 1

    def _precision(d: dict[str, int]) -> float:
        tp = d["tp"]
        fp = d["fp"]
        return tp / (tp + fp) if (tp + fp) else 1.0

    def _recall(d: dict[str, int]) -> float:
        tp = d["tp"]
        fn = d["fn"]
        return tp / (tp + fn) if (tp + fn) else 1.0

    for target, d in counts.items():
        p = _precision(d)
        r = _recall(d)
        assert p >= 1.0, f"{target} precision too low: {p:.2f}, counts={d}"
        assert r >= 1.0, f"{target} recall too low: {r:.2f}, counts={d}"
