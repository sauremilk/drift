"""Tests for inline suppression (``# drift:ignore``)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from drift.models import FileInfo, Finding, Severity, SignalType
from drift.suppression import (
    apply_inline_suppressions,
    filter_findings,
    insert_suppression_comment,
    scan_suppressions,
)

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

    def test_bare_ignore_marks_broad_security_suppression(self) -> None:
        finding = _make_finding(
            signal=SignalType.HARDCODED_SECRET,
            file_path="src/app.py",
            start_line=5,
        )

        active, suppressed = filter_findings([finding], {("src/app.py", 5): None})

        assert active == []
        assert len(suppressed) == 1
        assert suppressed[0].metadata["broad_security_suppression"] is True

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

    def test_expired_until_is_not_applied_and_is_reported(self, tmp_path: Path) -> None:
        src = tmp_path / "src" / "app.py"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text(
            "x = 1  # drift:ignore[AVS] until:2025-01-01 reason:temporary\n",
            encoding="utf-8",
        )
        files = [FileInfo(path=Path("src/app.py"), language="python", size_bytes=80)]

        finding = _make_finding(signal=SignalType.ARCHITECTURE_VIOLATION, start_line=1)
        result = apply_inline_suppressions([finding], files, tmp_path, today=date(2025, 3, 1))

        assert len(result.active) == 1
        assert len(result.suppressed) == 0
        assert len(result.expired_suppressions) == 1
        expired = result.expired_suppressions[0]
        assert expired.file_path == "src/app.py"
        assert expired.line_number == 1


# ---------------------------------------------------------------------------
# insert_suppression_comment
# ---------------------------------------------------------------------------


class TestInsertSuppressionComment:
    """Tests for insert_suppression_comment — writes drift:ignore into source files."""

    def test_python_bare_ignore(self, tmp_path: Path) -> None:
        src = tmp_path / "app.py"
        src.write_text("x = 1\n", encoding="utf-8")
        insert_suppression_comment(src, line_number=1, signals=None, language="python")
        assert src.read_text(encoding="utf-8") == "x = 1  # drift:ignore\n"

    def test_python_single_signal(self, tmp_path: Path) -> None:
        src = tmp_path / "app.py"
        src.write_text("x = 1\n", encoding="utf-8")
        insert_suppression_comment(
            src, line_number=1, signals={"architecture_violation"}, language="python"
        )
        assert src.read_text(encoding="utf-8") == "x = 1  # drift:ignore[AVS]\n"

    def test_python_multiple_signals_sorted(self, tmp_path: Path) -> None:
        src = tmp_path / "app.py"
        src.write_text("x = 1\n", encoding="utf-8")
        insert_suppression_comment(
            src,
            line_number=1,
            signals={"architecture_violation", "pattern_fragmentation"},
            language="python",
        )
        text = src.read_text(encoding="utf-8")
        # abbreviations must be sorted
        assert "drift:ignore[AVS,PFS]" in text or "drift:ignore[PFS,AVS]" in text
        # canonical sort is alphabetical by abbrev
        assert text == "x = 1  # drift:ignore[AVS,PFS]\n"

    def test_python_with_until(self, tmp_path: Path) -> None:
        src = tmp_path / "app.py"
        src.write_text("x = 1\n", encoding="utf-8")
        insert_suppression_comment(
            src,
            line_number=1,
            signals={"architecture_violation"},
            language="python",
            until=date(2026, 7, 19),
        )
        assert src.read_text(encoding="utf-8") == (
            "x = 1  # drift:ignore[AVS] until:2026-07-19\n"
        )

    def test_python_with_reason(self, tmp_path: Path) -> None:
        src = tmp_path / "app.py"
        src.write_text("x = 1\n", encoding="utf-8")
        insert_suppression_comment(
            src,
            line_number=1,
            signals=None,
            language="python",
            reason="intentional legacy coupling",
        )
        assert src.read_text(encoding="utf-8") == (
            "x = 1  # drift:ignore reason:intentional legacy coupling\n"
        )

    def test_python_with_until_and_reason(self, tmp_path: Path) -> None:
        src = tmp_path / "app.py"
        src.write_text("x = 1\n", encoding="utf-8")
        insert_suppression_comment(
            src,
            line_number=1,
            signals={"architecture_violation"},
            language="python",
            until=date(2026, 7, 19),
            reason="temporary",
        )
        assert src.read_text(encoding="utf-8") == (
            "x = 1  # drift:ignore[AVS] until:2026-07-19 reason:temporary\n"
        )

    def test_js_bare_ignore(self, tmp_path: Path) -> None:
        src = tmp_path / "app.ts"
        src.write_text("const x = 1;\n", encoding="utf-8")
        insert_suppression_comment(src, line_number=1, signals=None, language="typescript")
        assert src.read_text(encoding="utf-8") == "const x = 1;  // drift:ignore\n"

    def test_js_single_signal(self, tmp_path: Path) -> None:
        src = tmp_path / "app.ts"
        src.write_text("const x = 1;\n", encoding="utf-8")
        insert_suppression_comment(
            src, line_number=1, signals={"architecture_violation"}, language="javascript"
        )
        assert src.read_text(encoding="utf-8") == "const x = 1;  // drift:ignore[AVS]\n"

    def test_second_line_in_multiline_file(self, tmp_path: Path) -> None:
        src = tmp_path / "app.py"
        src.write_text("import os\nx = 1\n", encoding="utf-8")
        insert_suppression_comment(src, line_number=2, signals=None, language="python")
        lines = src.read_text(encoding="utf-8").splitlines()
        assert lines[0] == "import os"
        assert lines[1] == "x = 1  # drift:ignore"

    def test_utf8_content_preserved(self, tmp_path: Path) -> None:
        src = tmp_path / "app.py"
        src.write_text("x = '\u00e9l\u00e8ve'\n", encoding="utf-8")
        insert_suppression_comment(src, line_number=1, signals=None, language="python")
        assert src.read_text(encoding="utf-8") == "x = '\u00e9l\u00e8ve'  # drift:ignore\n"

    def test_trailing_newline_preserved(self, tmp_path: Path) -> None:
        src = tmp_path / "app.py"
        src.write_text("a = 1\nb = 2\n", encoding="utf-8")
        insert_suppression_comment(src, line_number=1, signals=None, language="python")
        text = src.read_text(encoding="utf-8")
        assert text.endswith("\n")
        assert text.count("\n") == 2

    def test_include_hash_embeds_tag(self, tmp_path: Path) -> None:
        src = tmp_path / "app.py"
        src.write_text("x = 1\n", encoding="utf-8")
        insert_suppression_comment(
            src, line_number=1, signals=None, language="python", include_hash=True
        )
        result = src.read_text(encoding="utf-8")
        assert "hash:" in result
        # hash must be exactly 8 hex chars
        import re
        assert re.search(r"hash:[0-9a-f]{8}", result)

    def test_include_hash_matches_collect(self, tmp_path: Path) -> None:
        """Stored hash written by insert_suppression_comment must equal current_hash
        as computed by collect_inline_suppressions on the same line."""
        from drift.models import FileInfo
        from drift.suppression import collect_inline_suppressions

        src = tmp_path / "app.py"
        src.write_text("password = os.environ['DB_PASS']\n", encoding="utf-8")
        insert_suppression_comment(
            src, line_number=1, signals=None, language="python", include_hash=True
        )
        files = [FileInfo(path=Path("app.py"), language="python", size_bytes=60)]
        entries = collect_inline_suppressions(files, tmp_path)
        assert len(entries) == 1
        entry = entries[0]
        assert entry.stored_hash is not None
        assert entry.current_hash == entry.stored_hash  # not stale yet


# ---------------------------------------------------------------------------
# Staleness detection
# ---------------------------------------------------------------------------


class TestStalenessDetection:
    """Tests for stale suppression detection via content hashes."""

    def _make_suppressed_file(
        self,
        tmp_path: Path,
        code_line: str,
        *,
        include_hash: bool = True,
        language: str = "python",
        suffix: str = ".py",
    ) -> Path:
        src = tmp_path / f"app{suffix}"
        src.write_text(f"{code_line}\n", encoding="utf-8")
        insert_suppression_comment(
            src, line_number=1, signals=None, language=language,
            include_hash=include_hash,
        )
        return src

    def test_unchanged_line_is_not_stale(self, tmp_path: Path) -> None:
        from drift.models import FileInfo
        from drift.suppression import collect_inline_suppressions

        self._make_suppressed_file(
            tmp_path, 'password = os.environ["DB_PASS"]'
        )
        files = [FileInfo(path=Path("app.py"), language="python", size_bytes=80)]
        entries = collect_inline_suppressions(files, tmp_path)
        assert entries[0].stored_hash == entries[0].current_hash

    def test_changed_line_is_stale(self, tmp_path: Path) -> None:
        """After the code is modified, current_hash should differ from stored_hash."""
        from drift.models import FileInfo
        from drift.suppression import collect_inline_suppressions

        # Write original line with hash
        src = tmp_path / "app.py"
        original_code = 'password = os.environ["DB_PASS"]'
        src.write_text(f"{original_code}\n", encoding="utf-8")
        insert_suppression_comment(
            src, line_number=1, signals=None, language="python", include_hash=True
        )
        # Now overwrite with a "refactored" — but dangerous — version,
        # keeping the old suppression comment intact
        suppressed_line = src.read_text(encoding="utf-8").splitlines()[0]
        new_code_part = 'password = "hardcoded_pwd_123"'  # pragma: allowlist secret
        # Replace only the code part before the drift:ignore comment
        import re as _re
        new_line = _re.sub(r"^.*?(?=  # drift:ignore)", new_code_part, suppressed_line)
        src.write_text(new_line + "\n", encoding="utf-8")

        files = [FileInfo(path=Path("app.py"), language="python", size_bytes=100)]
        entries = collect_inline_suppressions(files, tmp_path)
        assert len(entries) == 1
        entry = entries[0]
        assert entry.stored_hash is not None
        assert entry.current_hash != entry.stored_hash  # stale!

    def test_suppression_without_hash_has_none_stored_hash(self, tmp_path: Path) -> None:
        from drift.models import FileInfo
        from drift.suppression import collect_inline_suppressions

        src = tmp_path / "app.py"
        # Suppression added without --include-hash (legacy suppression)
        src.write_text(
            'password = os.environ["DB_PASS"]  # drift:ignore reason:env var\n',
            encoding="utf-8",
        )
        files = [FileInfo(path=Path("app.py"), language="python", size_bytes=80)]
        entries = collect_inline_suppressions(files, tmp_path)
        assert len(entries) == 1
        assert entries[0].stored_hash is None
        # current_hash is always computed
        assert entries[0].current_hash is not None

    def test_stale_security_signal_scenario(self, tmp_path: Path) -> None:
        """Reproduces the concrete scenario from issue #524 (HSC signal)."""
        from drift.models import FileInfo
        from drift.suppression import collect_inline_suppressions

        src = tmp_path / "app.py"
        # Original safe code
        original = 'password = os.environ["DB_PASS"]'
        src.write_text(f"{original}\n", encoding="utf-8")
        insert_suppression_comment(
            src, line_number=1, signals=None, language="python",
            include_hash=True, reason="env var, not a secret",
        )

        # Six months later: dangerous refactor, comment not updated
        suppressed_line = src.read_text(encoding="utf-8").splitlines()[0]
        dangerous = 'password = "hardcoded_pwd_123"'
        import re as _re
        new_line = _re.sub(r"^.*?(?=  # drift:ignore)", dangerous, suppressed_line)
        src.write_text(new_line + "\n", encoding="utf-8")

        files = [FileInfo(path=Path("app.py"), language="python", size_bytes=120)]
        entries = collect_inline_suppressions(files, tmp_path)
        stale = [e for e in entries if e.stored_hash and e.current_hash != e.stored_hash]
        assert len(stale) == 1, "Stale suppression hiding real security issue must be detectable"
