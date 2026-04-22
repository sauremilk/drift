"""Tests for drift explain <fingerprint> — finding-level context (ADR-042)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from click.testing import CliRunner

from drift.api.explain import (
    _FINGERPRINT_RE,
    _explain_finding_from_analysis_file,
    _extract_code_context,
)
from drift.commands.explain import _print_finding_detail, explain

# ---------------------------------------------------------------------------
# _FINGERPRINT_RE
# ---------------------------------------------------------------------------


class TestFingerprintRegex:
    def test_accepts_16_char_hex(self) -> None:
        assert _FINGERPRINT_RE.match("abcd1234abcd1234")  # pragma: allowlist secret

    def test_accepts_8_char_hex(self) -> None:
        assert _FINGERPRINT_RE.match("abcd1234")

    def test_rejects_signal_abbr(self) -> None:
        assert not _FINGERPRINT_RE.match("PFS")

    def test_rejects_uppercase_hex(self) -> None:
        # regex is lowercase-only per spec
        assert not _FINGERPRINT_RE.match("ABCD1234ABCD1234")

    def test_rejects_17_chars(self) -> None:
        assert not _FINGERPRINT_RE.match("abcd1234abcd12345")  # pragma: allowlist secret


# ---------------------------------------------------------------------------
# _extract_code_context
# ---------------------------------------------------------------------------


class TestExtractCodeContext:
    def test_returns_empty_for_none_path(self) -> None:
        result = _extract_code_context(None, 3, None, None)
        assert result == []

    def test_returns_empty_for_none_line(self) -> None:
        result = _extract_code_context(Path("some_file.py"), None, None, None)
        assert result == []

    def test_returns_empty_for_missing_file(self, tmp_path: Path) -> None:
        result = _extract_code_context(tmp_path / "nonexistent.py", 1, None, None)
        assert result == []

    def test_basic_snippet(self, tmp_path: Path) -> None:
        src = tmp_path / "src.py"
        src.write_text(
            "line1\nline2\nline3\nline4\nline5\nline6\nline7\nline8\nline9\nline10\n",
            encoding="utf-8",
        )
        result = _extract_code_context(src, 5, None, None, context=2)
        line_nos = [e["line_no"] for e in result]
        # context=2 → lines 3..7 (start 5 - 2 = 3, end 5 + 2 = 7)
        assert 3 in line_nos
        assert 7 in line_nos

    def test_target_lines_marked(self, tmp_path: Path) -> None:
        src = tmp_path / "src.py"
        src.write_text("\n".join(f"line{i}" for i in range(1, 20)) + "\n", encoding="utf-8")
        result = _extract_code_context(src, 5, 7, None, context=1)
        targets = [e for e in result if e["is_target"]]
        non_targets = [e for e in result if not e["is_target"]]
        assert all(5 <= e["line_no"] <= 7 for e in targets)
        assert all(e["line_no"] < 5 or e["line_no"] > 7 for e in non_targets)

    def test_resolves_relative_path_via_repo_root(self, tmp_path: Path) -> None:
        src = tmp_path / "module" / "file.py"
        src.parent.mkdir()
        src.write_text("a\nb\nc\n", encoding="utf-8")
        result = _extract_code_context(Path("module/file.py"), 2, None, tmp_path, context=0)
        assert len(result) == 1
        assert result[0]["line_no"] == 2
        assert result[0]["content"] == "b"
        assert result[0]["is_target"] is True

    def test_content_strips_newlines(self, tmp_path: Path) -> None:
        src = tmp_path / "file.py"
        src.write_text("hello world\n", encoding="utf-8")
        result = _extract_code_context(src, 1, None, None, context=0)
        assert result[0]["content"] == "hello world"


# ---------------------------------------------------------------------------
# _explain_finding_from_analysis_file
# ---------------------------------------------------------------------------


class TestExplainFindingFromFile:
    def _make_analysis_json(self, tmp_path: Path, findings: list[dict[str, Any]]) -> Path:
        data = {
            "schema_version": "2.2",
            "drift_score": 0.5,
            "findings": findings,
        }
        p = tmp_path / "analysis.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        return p

    def test_returns_none_for_missing_file(self, tmp_path: Path) -> None:
        result = _explain_finding_from_analysis_file(
            "abcd1234abcd1234", tmp_path / "nope.json", None
        )
        assert result is None

    def test_returns_none_for_missing_fingerprint(self, tmp_path: Path) -> None:
        path = self._make_analysis_json(tmp_path, [])
        result = _explain_finding_from_analysis_file("abcd1234abcd1234", path, None)
        assert result is None

    def test_finds_by_exact_finding_id(self, tmp_path: Path) -> None:
        finding = {
            "finding_id": "abcd1234abcd1234",
            "signal_type": "pattern_fragmentation",
            "signal_abbrev": "PFS",
            "title": "Test finding",
            "description": "Multiple variants detected.",
            "fix": "Consolidate patterns.",
            "file": "src/module.py",
            "start_line": 10,
            "end_line": 15,
            "severity": "high",
            "score": 0.75,
        }
        path = self._make_analysis_json(tmp_path, [finding])
        result = _explain_finding_from_analysis_file("abcd1234abcd1234", path, None)
        assert result is not None
        assert result["type"] == "finding"
        assert result["finding_id"] == "abcd1234abcd1234"
        assert result["signal"] == "PFS"

    def test_prefix_match(self, tmp_path: Path) -> None:
        finding = {
            "finding_id": "abcd1234abcd1234",
            "signal_type": "pattern_fragmentation",
            "signal_abbrev": "PFS",
            "title": "Test",
            "description": "desc",
            "file": None,
            "start_line": None,
            "end_line": None,
            "severity": "medium",
            "score": 0.4,
        }
        path = self._make_analysis_json(tmp_path, [finding])
        result = _explain_finding_from_analysis_file("abcd1234", path, None)
        assert result is not None
        assert result["finding_id"] == "abcd1234abcd1234"

    def test_code_context_included(self, tmp_path: Path) -> None:
        src = tmp_path / "src" / "module.py"
        src.parent.mkdir()
        src.write_text("\n".join(f"line{i}" for i in range(1, 30)) + "\n", encoding="utf-8")
        finding = {
            "finding_id": "aaaa1111aaaa1111",
            "signal_type": "pattern_fragmentation",
            "signal_abbrev": "PFS",
            "title": "Test",
            "description": "desc",
            "fix": "fix text",
            "file": "src/module.py",
            "start_line": 5,
            "end_line": 7,
            "severity": "high",
            "score": 0.8,
        }
        path = self._make_analysis_json(tmp_path, [finding])
        result = _explain_finding_from_analysis_file("aaaa1111aaaa1111", path, tmp_path)
        assert result is not None
        ctx = result.get("code_context", [])
        assert isinstance(ctx, list)
        assert len(ctx) > 0
        targets = [e for e in ctx if e["is_target"]]
        assert len(targets) == 3  # lines 5, 6, 7


# ---------------------------------------------------------------------------
# CLI routing: drift explain <fingerprint>
# ---------------------------------------------------------------------------


class TestExplainCLIFingerprint:
    def test_help_includes_from_file(self) -> None:
        runner = CliRunner()
        result = runner.invoke(explain, ["--help"])
        assert result.exit_code == 0
        assert "--from-file" in result.output or "-f" in result.output

    def test_signal_abbr_still_works(self) -> None:
        runner = CliRunner()
        result = runner.invoke(explain, ["PFS"])
        assert result.exit_code == 0
        assert "PFS" in result.output or "Pattern" in result.output

    def test_fingerprint_not_found_exits_1(self, tmp_path: Path) -> None:
        """An unresolvable fingerprint should exit with code 1."""
        # Use --from-file with an empty findings list to avoid a slow re-scan.
        analysis_file = tmp_path / "empty.json"
        analysis_file.write_text(
            json.dumps({"schema_version": "2.2", "drift_score": 0.0, "findings": []}),
            encoding="utf-8",
        )
        runner = CliRunner()
        result = runner.invoke(
            explain,
            ["abcd1234abcd1234", "--from-file", str(analysis_file), "--repo", str(tmp_path)],
        )
        assert result.exit_code == 1
        assert "not found" in result.output.lower() or "fingerprint" in result.output.lower()

    def test_from_file_resolves_finding(self, tmp_path: Path) -> None:
        src = tmp_path / "auth.py"
        src.write_text("def handle():\n    pass\n", encoding="utf-8")

        analysis_file = tmp_path / "analysis.json"
        finding = {
            "finding_id": "beef0123beef0123",
            "signal_type": "pattern_fragmentation",
            "signal_abbrev": "PFS",
            "title": "Pattern fragmentation in auth module",
            "description": "Three incompatible patterns found.",
            "fix": "Consolidate to one canonical pattern.",
            "file": "auth.py",
            "start_line": 1,
            "end_line": 2,
            "severity": "high",
            "score": 0.72,
        }
        analysis_file.write_text(
            json.dumps({"schema_version": "2.2", "drift_score": 0.4, "findings": [finding]}),
            encoding="utf-8",
        )
        runner = CliRunner()
        result = runner.invoke(
            explain,
            [
                "beef0123beef0123",
                "--from-file",
                str(analysis_file),
                "--repo",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 0
        assert "beef0123beef0123" in result.output or "Pattern" in result.output

    def test_from_file_json_output(self, tmp_path: Path) -> None:
        analysis_file = tmp_path / "analysis.json"
        finding = {
            "finding_id": "cafe4321cafe4321",
            "signal_type": "pattern_fragmentation",
            "signal_abbrev": "PFS",
            "title": "Test",
            "description": "desc",
            "fix": "fix",
            "file": None,
            "start_line": None,
            "end_line": None,
            "severity": "medium",
            "score": 0.5,
        }
        analysis_file.write_text(
            json.dumps({"schema_version": "2.2", "drift_score": 0.3, "findings": [finding]}),
            encoding="utf-8",
        )
        out_file = tmp_path / "out.json"
        runner = CliRunner()
        result = runner.invoke(
            explain,
            [
                "cafe4321cafe4321",
                "--from-file",
                str(analysis_file),
                "--repo",
                str(tmp_path),
                "--output",
                str(out_file),
            ],
        )
        assert result.exit_code == 0
        assert out_file.exists()
        data = json.loads(out_file.read_text(encoding="utf-8"))
        assert data.get("type") == "finding"
        assert data.get("finding_id") == "cafe4321cafe4321"


# ---------------------------------------------------------------------------
# _print_finding_detail smoke test
# ---------------------------------------------------------------------------


class TestPrintFindingDetailSmoke:
    def test_renders_without_exception(self, tmp_path: Path) -> None:
        result: dict[str, Any] = {
            "type": "finding",
            "finding_id": "deadbeef12345678",
            "signal": "PFS",
            "signal_name": "Pattern Fragmentation Score",
            "signal_description": "Detects incompatible patterns.",
            "detection_logic": "AST-based variant detection.",
            "remediation_approach": "Consolidate to one pattern.",
            "related_signals": ["MDS"],
            "code_context": [
                {"line_no": 3, "content": "def func():", "is_target": False},
                {"line_no": 4, "content": "    raise ValueError('oops')", "is_target": True},
                {"line_no": 5, "content": "    return None", "is_target": False},
            ],
            "finding": {
                "title": "Multiple error-handling variants",
                "severity": "high",
                "score": 0.8,
                "description": "Found 3 incompatible error-handling patterns.",
                "fix": "Consolidate error handling to a single strategy.",
                "next_step": "Refactor auth/handler.py to use custom exceptions.",
                "file": "auth/handler.py",
                "start_line": 4,
                "end_line": 4,
                "symbol": "func",
            },
        }
        # Must not raise
        _print_finding_detail(result, tmp_path)

    def test_renders_minimal_result(self, tmp_path: Path) -> None:
        result: dict[str, Any] = {
            "type": "finding",
            "finding_id": "0000000000000000",
            "signal": "AVS",
            "finding": {},
        }
        # Must not raise even with empty finding dict
        _print_finding_detail(result, tmp_path)

