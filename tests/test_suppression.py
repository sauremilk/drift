"""Tests for inline suppression (``# drift:ignore``)."""

from __future__ import annotations

from pathlib import Path

from drift.models import FileInfo, Finding, Severity, SignalType
from drift.suppression import filter_findings, scan_suppressions

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_finding(
    signal: SignalType = SignalType.ARCHITECTURE_VIOLATION,
    file_path: str = "src/app.py",
    start_line: int = 5,
) -> Finding:
    return Finding(
        signal_type=signal,
        severity=Severity.HIGH,
        score=0.8,
        title="test finding",
        description="desc",
        file_path=Path(file_path),
        start_line=start_line,
    )


# ---------------------------------------------------------------------------
# scan_suppressions
# ---------------------------------------------------------------------------

class TestScanSuppressions:
    """Test the comment scanner."""

    def test_ignore_all_python(self, tmp_path: Path) -> None:
        src = tmp_path / "app.py"
        src.write_text("import foo  # drift:ignore\n", encoding="utf-8")
        files = [FileInfo(path=Path("app.py"), language="python", size_bytes=30)]

        result = scan_suppressions(files, tmp_path)
        assert ("app.py", 1) in result
        assert result[("app.py", 1)] is None  # all signals

    def test_ignore_single_signal(self, tmp_path: Path) -> None:
        src = tmp_path / "app.py"
        src.write_text("import foo  # drift:ignore[AVS]\n", encoding="utf-8")
        files = [FileInfo(path=Path("app.py"), language="python", size_bytes=30)]

        result = scan_suppressions(files, tmp_path)
        assert result[("app.py", 1)] == {"architecture_violation"}

    def test_ignore_multiple_signals(self, tmp_path: Path) -> None:
        src = tmp_path / "app.py"
        src.write_text("import foo  # drift:ignore[AVS,PFS]\n", encoding="utf-8")
        files = [FileInfo(path=Path("app.py"), language="python", size_bytes=30)]

        result = scan_suppressions(files, tmp_path)
        assert result[("app.py", 1)] == {
            "architecture_violation",
            "pattern_fragmentation",
        }

    def test_js_comment_syntax(self, tmp_path: Path) -> None:
        src = tmp_path / "app.ts"
        src.write_text("import foo  // drift:ignore[AVS]\n", encoding="utf-8")
        files = [FileInfo(path=Path("app.ts"), language="typescript", size_bytes=30)]

        result = scan_suppressions(files, tmp_path)
        assert result[("app.ts", 1)] == {"architecture_violation"}

    def test_unsupported_language_skipped(self, tmp_path: Path) -> None:
        src = tmp_path / "app.rb"
        src.write_text("# drift:ignore\n", encoding="utf-8")
        files = [FileInfo(path=Path("app.rb"), language="ruby", size_bytes=15)]

        result = scan_suppressions(files, tmp_path)
        assert not result

    def test_missing_file_skipped(self, tmp_path: Path) -> None:
        files = [FileInfo(path=Path("gone.py"), language="python", size_bytes=10)]
        result = scan_suppressions(files, tmp_path)
        assert not result

    def test_multiple_lines(self, tmp_path: Path) -> None:
        src = tmp_path / "app.py"
        src.write_text(
            "line1\nimport foo  # drift:ignore\nline3\nbar  # drift:ignore[PFS]\n",
            encoding="utf-8",
        )
        files = [FileInfo(path=Path("app.py"), language="python", size_bytes=60)]

        result = scan_suppressions(files, tmp_path)
        assert len(result) == 2
        assert result[("app.py", 2)] is None
        assert result[("app.py", 4)] == {"pattern_fragmentation"}


# ---------------------------------------------------------------------------
# filter_findings
# ---------------------------------------------------------------------------

class TestFilterFindings:
    """Test the finding filter."""

    def test_empty_suppressions_passes_all(self) -> None:
        findings = [_make_finding()]
        active, suppressed = filter_findings(findings, {})
        assert len(active) == 1
        assert len(suppressed) == 0

    def test_suppress_all_signals_on_line(self) -> None:
        findings = [_make_finding(file_path="src/app.py", start_line=5)]
        suppressions = {("src/app.py", 5): None}

        active, suppressed = filter_findings(findings, suppressions)
        assert len(active) == 0
        assert len(suppressed) == 1

    def test_suppress_matching_signal(self) -> None:
        findings = [
            _make_finding(signal=SignalType.ARCHITECTURE_VIOLATION, start_line=5),
        ]
        suppressions = {("src/app.py", 5): {"architecture_violation"}}

        active, suppressed = filter_findings(findings, suppressions)
        assert len(active) == 0
        assert len(suppressed) == 1
        assert suppressed[0].status.value == "suppressed"
        assert suppressed[0].status_set_by == "inline_comment"
        assert suppressed[0].status_reason is not None

    def test_non_matching_signal_passes(self) -> None:
        findings = [
            _make_finding(signal=SignalType.PATTERN_FRAGMENTATION, start_line=5),
        ]
        suppressions = {("src/app.py", 5): {"architecture_violation"}}

        active, suppressed = filter_findings(findings, suppressions)
        assert len(active) == 1
        assert len(suppressed) == 0
        assert active[0].status.value == "active"

    def test_finding_without_file_passes(self) -> None:
        f = _make_finding()
        f.file_path = None
        active, suppressed = filter_findings([f], {("src/app.py", 5): None})
        assert len(active) == 1
        assert len(suppressed) == 0

    def test_finding_without_start_line_passes(self) -> None:
        f = _make_finding()
        f.start_line = None
        active, suppressed = filter_findings([f], {("src/app.py", 5): None})
        assert len(active) == 1
        assert len(suppressed) == 0

    def test_multiple_findings_mixed(self) -> None:
        f1 = _make_finding(signal=SignalType.ARCHITECTURE_VIOLATION, start_line=5)
        f2 = _make_finding(signal=SignalType.PATTERN_FRAGMENTATION, start_line=5)
        f3 = _make_finding(signal=SignalType.MUTANT_DUPLICATE, start_line=10)

        suppressions = {("src/app.py", 5): {"architecture_violation"}}  # only AVS on line 5

        active, suppressed = filter_findings([f1, f2, f3], suppressions)
        assert len(suppressed) == 1
        assert suppressed[0].signal_type == SignalType.ARCHITECTURE_VIOLATION
        assert len(active) == 2

    def test_suppresses_when_ignore_matches_end_line(self) -> None:
        f = _make_finding(start_line=5)
        f.end_line = 8

        active, suppressed = filter_findings([f], {("src/app.py", 8): None})
        assert len(active) == 0
        assert len(suppressed) == 1

    def test_abbrev_comment_suppresses_matching_finding(self, tmp_path: Path) -> None:
        src = tmp_path / "src" / "app.py"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text("x = 1  # drift:ignore[AVS]\n", encoding="utf-8")
        files = [FileInfo(path=Path("src/app.py"), language="python", size_bytes=32)]

        suppressions = scan_suppressions(files, tmp_path)
        finding = _make_finding(signal=SignalType.ARCHITECTURE_VIOLATION, start_line=1)
        active, suppressed = filter_findings([finding], suppressions)

        assert len(active) == 0
        assert len(suppressed) == 1
