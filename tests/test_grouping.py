"""Tests for drift.output.grouping."""

from __future__ import annotations

from pathlib import Path

import pytest

from drift.models import Finding, Severity
from drift.output.grouping import group_findings


def _make_finding(
    signal: str = "PFS",
    severity: Severity = Severity.MEDIUM,
    file_path: str | None = "src/drift/foo.py",
) -> Finding:
    return Finding(
        signal_type=signal,
        severity=severity,
        score=0.5,
        title="test",
        description="test finding",
        file_path=Path(file_path) if file_path else None,
    )


class TestGroupBySignal:
    def test_groups_by_signal_type(self) -> None:
        findings = [
            _make_finding(signal="PFS"),
            _make_finding(signal="AVS"),
            _make_finding(signal="PFS"),
        ]
        groups = group_findings(findings, "signal")
        assert set(groups.keys()) == {"AVS", "PFS"}
        assert len(groups["PFS"]) == 2
        assert len(groups["AVS"]) == 1

    def test_sorted_group_keys(self) -> None:
        findings = [
            _make_finding(signal="MDS"),
            _make_finding(signal="AVS"),
        ]
        groups = group_findings(findings, "signal")
        assert list(groups.keys()) == ["AVS", "MDS"]


class TestGroupBySeverity:
    def test_groups_by_severity(self) -> None:
        findings = [
            _make_finding(severity=Severity.HIGH),
            _make_finding(severity=Severity.LOW),
            _make_finding(severity=Severity.HIGH),
        ]
        groups = group_findings(findings, "severity")
        assert "high" in groups
        assert "low" in groups
        assert len(groups["high"]) == 2


class TestGroupByDirectory:
    def test_groups_by_parent_dir(self) -> None:
        findings = [
            _make_finding(file_path="src/drift/signals/pfs.py"),
            _make_finding(file_path="src/drift/signals/avs.py"),
            _make_finding(file_path="src/drift/output/json.py"),
        ]
        groups = group_findings(findings, "directory")
        assert "src/drift/signals" in groups
        assert "src/drift/output" in groups
        assert len(groups["src/drift/signals"]) == 2

    def test_no_file_path(self) -> None:
        findings = [_make_finding(file_path=None)]
        groups = group_findings(findings, "directory")
        assert "(no file)" in groups


class TestGroupByModule:
    def test_groups_by_first_segment(self) -> None:
        findings = [
            _make_finding(file_path="src/drift/foo.py"),
            _make_finding(file_path="tests/test_foo.py"),
            _make_finding(file_path="src/drift/bar.py"),
        ]
        groups = group_findings(findings, "module")
        assert set(groups.keys()) == {"src", "tests"}
        assert len(groups["src"]) == 2

    def test_no_file_path(self) -> None:
        findings = [_make_finding(file_path=None)]
        groups = group_findings(findings, "module")
        assert "(no file)" in groups


class TestEdgeCases:
    def test_empty_findings(self) -> None:
        groups = group_findings([], "signal")
        assert groups == {}

    def test_single_finding(self) -> None:
        groups = group_findings([_make_finding()], "signal")
        assert len(groups) == 1

    @pytest.mark.parametrize("mode", ["signal", "severity", "directory", "module"])
    def test_all_modes_accept_findings(self, mode: str) -> None:
        findings = [_make_finding(), _make_finding(signal="AVS")]
        groups = group_findings(findings, mode)
        total = sum(len(v) for v in groups.values())
        assert total == 2
