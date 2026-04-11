"""Tests for context-tagging feature (ADR-006)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from drift.context_tags import apply_context_tags, scan_context_tags
from drift.models import FileInfo, Finding, Severity, SignalType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_finding(
    file_path: str = "services/payment.py",
    start_line: int = 10,
    end_line: int = 20,
    score: float = 0.8,
    signal_type: SignalType = SignalType.PATTERN_FRAGMENTATION,
) -> Finding:
    return Finding(
        signal_type=signal_type,
        severity=Severity.HIGH,
        score=score,
        title="Test finding",
        description="Test description",
        file_path=Path(file_path),
        start_line=start_line,
        end_line=end_line,
    )


def _write_python_file(tmp_path: Path, rel_path: str, content: str) -> FileInfo:
    full = tmp_path / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")
    return FileInfo(
        path=Path(rel_path),
        language="python",
        size_bytes=len(content),
        line_count=content.count("\n") + 1,
    )


def _write_ts_file(tmp_path: Path, rel_path: str, content: str) -> FileInfo:
    full = tmp_path / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")
    return FileInfo(
        path=Path(rel_path),
        language="typescript",
        size_bytes=len(content),
        line_count=content.count("\n") + 1,
    )


# ---------------------------------------------------------------------------
# scan_context_tags
# ---------------------------------------------------------------------------

class TestScanContextTags:
    def test_python_single_tag(self, tmp_path: Path) -> None:
        fi = _write_python_file(tmp_path, "svc/handler.py", (
            "import os\n"
            "# drift:context migration\n"
            "class OldHandler:\n"
            "    pass\n"
        ))
        tags = scan_context_tags([fi], tmp_path)
        assert tags[("svc/handler.py", 2)] == {"migration"}

    def test_python_multiple_tags(self, tmp_path: Path) -> None:
        fi = _write_python_file(tmp_path, "svc/handler.py", (
            "# drift:context migration, legacy\n"
            "def old_func(): pass\n"
        ))
        tags = scan_context_tags([fi], tmp_path)
        assert tags[("svc/handler.py", 1)] == {"migration", "legacy"}

    def test_typescript_tag(self, tmp_path: Path) -> None:
        fi = _write_ts_file(tmp_path, "svc/handler.ts", (
            "// drift:context refactoring\n"
            "export function legacyHandler() {}\n"
        ))
        tags = scan_context_tags([fi], tmp_path)
        assert tags[("svc/handler.ts", 1)] == {"refactoring"}

    def test_no_context_tags(self, tmp_path: Path) -> None:
        fi = _write_python_file(tmp_path, "svc/clean.py", (
            "def clean(): pass\n"
        ))
        tags = scan_context_tags([fi], tmp_path)
        assert len(tags) == 0

    def test_ignores_drift_ignore(self, tmp_path: Path) -> None:
        fi = _write_python_file(tmp_path, "svc/ignored.py", (
            "# drift:ignore\n"
            "def old(): pass\n"
        ))
        tags = scan_context_tags([fi], tmp_path)
        assert len(tags) == 0

    def test_multiple_files(self, tmp_path: Path) -> None:
        f1 = _write_python_file(tmp_path, "a.py", "# drift:context migration\nx = 1\n")
        f2 = _write_python_file(tmp_path, "b.py", "# drift:context deliberate\ny = 2\n")
        tags = scan_context_tags([f1, f2], tmp_path)
        assert ("a.py", 1) in tags
        assert ("b.py", 1) in tags

    def test_tag_with_hyphens_and_underscores(self, tmp_path: Path) -> None:
        fi = _write_python_file(tmp_path, "x.py", (
            "# drift:context strategy-pattern, tech_debt\n"
            "class X: pass\n"
        ))
        tags = scan_context_tags([fi], tmp_path)
        assert tags[("x.py", 1)] == {"strategy-pattern", "tech_debt"}

    def test_unsupported_language_ignored(self, tmp_path: Path) -> None:
        fi = FileInfo(path=Path("data.json"), language="json", size_bytes=10)
        tags = scan_context_tags([fi], tmp_path)
        assert len(tags) == 0

    def test_missing_file_skipped(self, tmp_path: Path) -> None:
        fi = FileInfo(path=Path("nonexistent.py"), language="python", size_bytes=0)
        tags = scan_context_tags([fi], tmp_path)
        assert len(tags) == 0


# ---------------------------------------------------------------------------
# apply_context_tags
# ---------------------------------------------------------------------------

class TestApplyContextTags:
    def test_tags_applied_to_overlapping_finding(self) -> None:
        tags = {("services/payment.py", 15): {"migration"}}
        findings = [_make_finding(start_line=10, end_line=20, score=0.8)]
        result, count = apply_context_tags(findings, tags, dampening=0.5)
        assert count == 1
        assert result[0].metadata["context_tags"] == ["migration"]
        assert result[0].score == pytest.approx(0.4)

    def test_no_overlap_no_dampening(self) -> None:
        tags = {("services/payment.py", 50): {"migration"}}
        findings = [_make_finding(start_line=10, end_line=20, score=0.8)]
        result, count = apply_context_tags(findings, tags, dampening=0.5)
        assert count == 0
        assert "context_tags" not in result[0].metadata
        assert result[0].score == pytest.approx(0.8)

    def test_dampening_factor_1_no_score_change(self) -> None:
        tags = {("services/payment.py", 15): {"deliberate"}}
        findings = [_make_finding(start_line=10, end_line=20, score=0.8)]
        result, count = apply_context_tags(findings, tags, dampening=1.0)
        assert count == 1
        assert result[0].metadata["context_tags"] == ["deliberate"]
        assert result[0].score == pytest.approx(0.8)

    def test_dampening_factor_0_zeros_score(self) -> None:
        tags = {("services/payment.py", 15): {"legacy"}}
        findings = [_make_finding(start_line=10, end_line=20, score=0.8)]
        result, count = apply_context_tags(findings, tags, dampening=0.0)
        assert count == 1
        assert result[0].score == pytest.approx(0.0)

    def test_multiple_tags_merged(self) -> None:
        tags = {
            ("services/payment.py", 12): {"migration"},
            ("services/payment.py", 18): {"legacy"},
        }
        findings = [_make_finding(start_line=10, end_line=20)]
        result, count = apply_context_tags(findings, tags, dampening=0.5)
        assert count == 1
        assert set(result[0].metadata["context_tags"]) == {"migration", "legacy"}

    def test_finding_without_file_path_untouched(self) -> None:
        tags = {("services/payment.py", 15): {"migration"}}
        f = Finding(
            signal_type=SignalType.PATTERN_FRAGMENTATION,
            severity=Severity.HIGH,
            score=0.8,
            title="No location",
            description="Test",
        )
        result, count = apply_context_tags([f], tags, dampening=0.5)
        assert count == 0
        assert result[0].score == pytest.approx(0.8)

    def test_empty_tags_dict(self) -> None:
        findings = [_make_finding()]
        result, count = apply_context_tags(findings, {}, dampening=0.5)
        assert count == 0
        assert result[0].score == pytest.approx(0.8)

    def test_dampening_clamped_above_1(self) -> None:
        tags = {("services/payment.py", 15): {"test"}}
        findings = [_make_finding(score=0.8)]
        result, count = apply_context_tags(findings, tags, dampening=1.5)
        assert count == 1
        # Should be clamped to 1.0
        assert result[0].score == pytest.approx(0.8)

    def test_dampening_clamped_below_0(self) -> None:
        tags = {("services/payment.py", 15): {"test"}}
        findings = [_make_finding(score=0.8)]
        result, count = apply_context_tags(findings, tags, dampening=-0.5)
        assert count == 1
        # Should be clamped to 0.0
        assert result[0].score == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Config integration
# ---------------------------------------------------------------------------

class TestContextDampeningConfig:
    def test_default_dampening(self) -> None:
        from drift.config import DriftConfig
        cfg = DriftConfig()
        assert cfg.context_dampening == 0.5

    def test_custom_dampening(self) -> None:
        from drift.config import DriftConfig
        cfg = DriftConfig(context_dampening=0.3)
        assert cfg.context_dampening == 0.3


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------

class TestJsonContextOutput:
    def test_context_tagged_count_in_json(self) -> None:
        import datetime

        from drift.models import RepoAnalysis
        from drift.output.json_output import analysis_to_json

        analysis = RepoAnalysis(
            repo_path=Path("/test"),
            analyzed_at=datetime.datetime.now(tz=datetime.UTC),
            drift_score=0.5,
            context_tagged_count=3,
        )
        data = json.loads(analysis_to_json(analysis))
        assert data["context_tagged_count"] == 3

    def test_context_tags_in_finding_metadata(self) -> None:
        import datetime

        from drift.models import RepoAnalysis
        from drift.output.json_output import analysis_to_json

        f = _make_finding(score=0.4)
        f.metadata["context_tags"] = ["migration", "legacy"]
        analysis = RepoAnalysis(
            repo_path=Path("/test"),
            analyzed_at=datetime.datetime.now(tz=datetime.UTC),
            drift_score=0.5,
            findings=[f],
            context_tagged_count=1,
        )
        data = json.loads(analysis_to_json(analysis))
        assert data["findings"][0]["metadata"]["context_tags"] == ["migration", "legacy"]


# ---------------------------------------------------------------------------
# SARIF output
# ---------------------------------------------------------------------------

class TestSarifContextTags:
    def test_context_tags_in_sarif_result_properties(self) -> None:
        import datetime

        from drift.models import RepoAnalysis
        from drift.output.json_output import findings_to_sarif

        f = _make_finding(score=0.4)
        f.metadata["context_tags"] = ["refactoring"]
        analysis = RepoAnalysis(
            repo_path=Path("/test"),
            analyzed_at=datetime.datetime.now(tz=datetime.UTC),
            drift_score=0.5,
            findings=[f],
            context_tagged_count=1,
        )
        sarif = json.loads(findings_to_sarif(analysis))
        result = sarif["runs"][0]["results"][0]
        assert result["properties"]["drift:context"] == ["refactoring"]

    def test_no_context_tags_no_properties(self) -> None:
        import datetime

        from drift.models import RepoAnalysis
        from drift.output.json_output import findings_to_sarif

        f = _make_finding(score=0.4)
        analysis = RepoAnalysis(
            repo_path=Path("/test"),
            analyzed_at=datetime.datetime.now(tz=datetime.UTC),
            drift_score=0.5,
            findings=[f],
        )
        sarif = json.loads(findings_to_sarif(analysis))
        result = sarif["runs"][0]["results"][0]
        # drift:findingId is always present; only context tags should be absent
        assert "drift:context" not in result.get("properties", {})


# ---------------------------------------------------------------------------
# End-to-end: scan + apply
# ---------------------------------------------------------------------------

class TestContextTagEndToEnd:
    def test_scan_and_apply(self, tmp_path: Path) -> None:
        fi = _write_python_file(tmp_path, "svc/handler.py", (
            "import os\n"                         # line 1
            "# drift:context migration\n"         # line 2
            "class OldHandler:\n"                 # line 3
            "    def process(self):\n"            # line 4
            "        pass\n"                      # line 5
        ))
        tags = scan_context_tags([fi], tmp_path)
        finding = _make_finding(
            file_path="svc/handler.py",
            start_line=2,
            end_line=5,
            score=0.6,
        )
        result, count = apply_context_tags([finding], tags, dampening=0.5)
        assert count == 1
        assert result[0].score == pytest.approx(0.3)
        assert result[0].metadata["context_tags"] == ["migration"]

    def test_untagged_finding_untouched(self, tmp_path: Path) -> None:
        fi = _write_python_file(tmp_path, "svc/handler.py", (
            "# drift:context migration\n"         # line 1
            "class OldHandler:\n"                 # line 2
            "    pass\n"                          # line 3
            "\n"                                  # line 4
            "class NewHandler:\n"                 # line 5
            "    pass\n"                          # line 6
        ))
        tags = scan_context_tags([fi], tmp_path)
        tagged_finding = _make_finding(
            file_path="svc/handler.py",
            start_line=1,
            end_line=3,
            score=0.8,
        )
        clean_finding = _make_finding(
            file_path="svc/handler.py",
            start_line=5,
            end_line=6,
            score=0.8,
        )
        result, count = apply_context_tags(
            [tagged_finding, clean_finding], tags, dampening=0.5,
        )
        assert count == 1
        assert result[0].score == pytest.approx(0.4)  # dampened
        assert result[1].score == pytest.approx(0.8)  # untouched
