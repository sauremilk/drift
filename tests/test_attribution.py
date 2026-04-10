"""Tests for causal attribution (ADR-034).

Covers:
- git blame porcelain parsing
- blame subprocess invocation (mocked)
- parallel blame with caching
- finding enrichment pipeline
- attribution in JSON / SARIF output
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from unittest.mock import patch

from drift.config import AttributionConfig
from drift.ingestion.git_blame import (
    BlameCache,
    _parse_porcelain,
    blame_files_parallel,
    blame_lines,
    extract_branch_hint,
)
from drift.models import (
    Attribution,
    BlameLine,
    CommitInfo,
    Finding,
    RepoAnalysis,
    Severity,
)

# ---------------------------------------------------------------------------
# Porcelain Parsing
# ---------------------------------------------------------------------------

PORCELAIN_SAMPLE = """\
abc1234567890123456789012345678901234567 10 42 1
author Jane Doe
author-mail <jane@example.com>
author-time 1712620800
author-tz +0000
committer Jane Doe
committer-mail <jane@example.com>
committer-time 1712620800
committer-tz +0000
summary feat: add guard clause
filename src/module.py
\tdef process(data):
abc1234567890123456789012345678901234567 11 43
\t    if not data:
def5678901234567890123456789012345678901 12 44 1
author Bob Smith
author-mail <bob@example.com>
author-time 1712534400
author-tz +0000
committer Bob Smith
committer-mail <bob@example.com>
committer-time 1712534400
committer-tz +0000
summary fix: handle edge case
filename src/module.py
\t        return None
"""


class TestParsePorcelain:
    def test_parses_basic_porcelain(self) -> None:
        lines = _parse_porcelain(PORCELAIN_SAMPLE)
        assert len(lines) == 3

    def test_first_line_fields(self) -> None:
        lines = _parse_porcelain(PORCELAIN_SAMPLE)
        first = lines[0]
        assert first.line_no == 42
        assert (
            first.commit_hash == "abc1234567890123456789012345678901234567"
        )  # pragma: allowlist secret
        assert first.author == "Jane Doe"
        assert first.email == "jane@example.com"
        assert first.content == "def process(data):"

    def test_second_commit_fields(self) -> None:
        lines = _parse_porcelain(PORCELAIN_SAMPLE)
        last = lines[2]
        assert (
            last.commit_hash == "def5678901234567890123456789012345678901"
        )  # pragma: allowlist secret
        assert last.author == "Bob Smith"
        assert last.email == "bob@example.com"

    def test_empty_input(self) -> None:
        assert _parse_porcelain("") == []
        assert _parse_porcelain("   \n  ") == []

    def test_date_parsing(self) -> None:
        lines = _parse_porcelain(PORCELAIN_SAMPLE)
        # 1712620800 = 2024-04-09 (UTC)
        assert lines[0].date == datetime.date(2024, 4, 9)


# ---------------------------------------------------------------------------
# Blame Execution (mocked subprocess)
# ---------------------------------------------------------------------------


class TestBlameLines:
    @patch("drift.ingestion.git_blame.subprocess.run")
    def test_blame_returns_parsed_lines(self, mock_run: object) -> None:
        mock_run.return_value = type("Result", (), {"returncode": 0, "stdout": PORCELAIN_SAMPLE})()
        result = blame_lines(Path("/repo"), "src/module.py", 42, 44)
        assert len(result) == 3
        assert result[0].author == "Jane Doe"

    @patch("drift.ingestion.git_blame.subprocess.run")
    def test_blame_with_line_range_passes_l_flag(self, mock_run: object) -> None:
        mock_run.return_value = type("Result", (), {"returncode": 0, "stdout": ""})()
        blame_lines(Path("/repo"), "src/file.py", 10, 20)
        cmd = mock_run.call_args[0][0]
        assert "-L10,20" in cmd

    @patch("drift.ingestion.git_blame.subprocess.run")
    def test_blame_without_range_no_l_flag(self, mock_run: object) -> None:
        mock_run.return_value = type("Result", (), {"returncode": 0, "stdout": ""})()
        blame_lines(Path("/repo"), "src/file.py")
        cmd = mock_run.call_args[0][0]
        assert not any(c.startswith("-L") for c in cmd)

    @patch("drift.ingestion.git_blame.subprocess.run", side_effect=FileNotFoundError)
    def test_blame_git_not_found_returns_empty(self, _mock: object) -> None:
        result = blame_lines(Path("/repo"), "src/file.py")
        assert result == []

    @patch("drift.ingestion.git_blame.subprocess.run")
    def test_blame_nonzero_return_code(self, mock_run: object) -> None:
        mock_run.return_value = type(
            "Result", (), {"returncode": 128, "stdout": "", "stderr": ""}
        )()
        result = blame_lines(Path("/repo"), "src/file.py")
        assert result == []


# ---------------------------------------------------------------------------
# Blame Cache
# ---------------------------------------------------------------------------


class TestBlameCache:
    def test_put_and_get(self) -> None:
        cache = BlameCache(max_size=10)
        bl = [BlameLine(1, "abc", "Author", "a@b.com", datetime.date.today())]
        cache.put("key1", bl)
        assert cache.get("key1") == bl

    def test_miss_returns_none(self) -> None:
        cache = BlameCache()
        assert cache.get("nonexistent") is None

    def test_eviction_on_overflow(self) -> None:
        cache = BlameCache(max_size=2)
        cache.put("k1", [])
        cache.put("k2", [])
        cache.put("k3", [])  # should evict k1
        assert cache.get("k1") is None
        assert cache.get("k2") == []
        assert cache.get("k3") == []


# ---------------------------------------------------------------------------
# Parallel Blame
# ---------------------------------------------------------------------------


class TestBlameFilesParallel:
    @patch("drift.ingestion.git_blame.blame_lines")
    @patch("drift.ingestion.git_blame._content_hash", return_value=None)
    def test_deduplicates_by_file(self, _hash: object, mock_blame: object) -> None:
        bl = [BlameLine(1, "abc", "Author", "a@b.com", datetime.date.today())]
        mock_blame.return_value = bl

        requests = [
            ("src/a.py", 10, 20),
            ("src/a.py", 15, 25),  # same file, should be merged
            ("src/b.py", 1, 5),
        ]
        results = blame_files_parallel(Path("/repo"), requests, max_workers=2)
        # Should have called blame for 2 files (a.py merged, b.py)
        assert "src/a.py" in results
        assert "src/b.py" in results


# ---------------------------------------------------------------------------
# Branch Hint Extraction
# ---------------------------------------------------------------------------


class TestBranchHint:
    @patch("drift.ingestion.git_blame.subprocess.run")
    def test_extracts_branch_from_merge_message(self, mock_run: object) -> None:
        mock_run.return_value = type(
            "Result",
            (),
            {
                "returncode": 0,
                "stdout": "Merge branch 'feature/llm-refactor' into main\n",
            },
        )()
        hint = extract_branch_hint(Path("/repo"), "abc123")
        assert hint == "feature/llm-refactor"

    @patch("drift.ingestion.git_blame.subprocess.run")
    def test_extracts_branch_from_pr_message(self, mock_run: object) -> None:
        mock_run.return_value = type(
            "Result",
            (),
            {
                "returncode": 0,
                "stdout": "Merge pull request #42 from org/feature-auth\n",
            },
        )()
        hint = extract_branch_hint(Path("/repo"), "abc123")
        assert hint == "feature-auth"

    @patch("drift.ingestion.git_blame.subprocess.run")
    def test_returns_none_on_no_merge(self, mock_run: object) -> None:
        mock_run.return_value = type(
            "Result", (), {"returncode": 0, "stdout": "feat: add thing\n"}
        )()
        hint = extract_branch_hint(Path("/repo"), "abc123")
        assert hint is None


# ---------------------------------------------------------------------------
# Finding Enrichment
# ---------------------------------------------------------------------------


class TestEnrichFindings:
    def _make_finding(
        self,
        file_path: str = "src/module.py",
        start_line: int = 42,
        end_line: int | None = 44,
    ) -> Finding:
        return Finding(
            signal_type="guard_clause_deficit",
            severity=Severity.MEDIUM,
            score=0.5,
            title="Missing guard clause",
            description="Function lacks early return",
            file_path=Path(file_path),
            start_line=start_line,
            end_line=end_line,
        )

    def _make_commits(self) -> list[CommitInfo]:
        return [
            CommitInfo(
                hash="abc1234567890123456789012345678901234567",  # pragma: allowlist secret
                author="Jane Doe",
                email="jane@example.com",
                timestamp=datetime.datetime(2024, 4, 9, tzinfo=datetime.UTC),
                message="feat: add guard clause",
                is_ai_attributed=True,
                ai_confidence=0.85,
            ),
        ]

    @patch("drift.attribution.blame_files_parallel")
    def test_enriches_finding_with_attribution(self, mock_blame: object) -> None:
        from drift.attribution import enrich_findings

        bl = [
            BlameLine(
                42,
                "abc1234567890123456789012345678901234567",  # pragma: allowlist secret
                "Jane Doe",
                "jane@example.com",
                datetime.date(2024, 4, 9),
            ),
            BlameLine(
                43,
                "abc1234567890123456789012345678901234567",  # pragma: allowlist secret
                "Jane Doe",
                "jane@example.com",
                datetime.date(2024, 4, 9),
            ),
        ]
        mock_blame.return_value = {"src/module.py": bl}

        findings = [self._make_finding()]
        config = AttributionConfig(enabled=True, include_branch_hint=False)
        result = enrich_findings(findings, Path("/repo"), config, self._make_commits())

        assert result[0].attribution is not None
        assert result[0].attribution.author == "Jane Doe"
        assert (
            result[0].attribution.commit_hash == "abc1234567890123456789012345678901234567"
        )  # pragma: allowlist secret
        assert result[0].attribution.ai_attributed is True
        assert result[0].attribution.ai_confidence == 0.85

    @patch("drift.attribution.blame_files_parallel")
    def test_skips_finding_without_file_path(self, mock_blame: object) -> None:
        from drift.attribution import enrich_findings

        mock_blame.return_value = {}
        finding = Finding(
            signal_type="test",
            severity=Severity.LOW,
            score=0.1,
            title="No file",
            description="desc",
        )
        config = AttributionConfig(enabled=True, include_branch_hint=False)
        result = enrich_findings([finding], Path("/repo"), config)
        assert result[0].attribution is None

    @patch("drift.attribution.blame_files_parallel")
    def test_fallback_on_empty_blame(self, mock_blame: object) -> None:
        from drift.attribution import enrich_findings

        mock_blame.return_value = {"src/module.py": []}
        findings = [self._make_finding()]
        config = AttributionConfig(enabled=True, include_branch_hint=False)
        result = enrich_findings(findings, Path("/repo"), config)
        assert result[0].attribution is None

    def test_disabled_config_skips_enrichment(self) -> None:
        from drift.attribution import enrich_findings

        findings = [self._make_finding()]
        config = AttributionConfig(enabled=False)
        result = enrich_findings(findings, Path("/repo"), config)
        assert result[0].attribution is None


# ---------------------------------------------------------------------------
# JSON Output — Attribution Serialization
# ---------------------------------------------------------------------------


class TestJsonAttribution:
    def test_finding_with_attribution_serialized(self) -> None:
        from drift.output.json_output import _finding_to_dict

        f = Finding(
            signal_type="guard_clause_deficit",
            severity=Severity.MEDIUM,
            score=0.5,
            title="Missing guard clause",
            description="desc",
            file_path=Path("src/module.py"),
            start_line=42,
            attribution=Attribution(
                commit_hash="abc1234",
                author="Jane Doe",
                email="jane@example.com",
                date=datetime.date(2024, 4, 9),
                branch_hint="feature/llm-refactor",
                ai_attributed=True,
                ai_confidence=0.85,
                commit_message_summary="feat: add guard clause",
            ),
        )
        d = _finding_to_dict(f)
        assert d["attribution"] is not None
        assert d["attribution"]["commit_hash"] == "abc1234"
        assert d["attribution"]["author"] == "Jane Doe"
        assert d["attribution"]["ai_attributed"] is True
        assert d["attribution"]["date"] == "2024-04-09"

    def test_finding_without_attribution_has_null(self) -> None:
        from drift.output.json_output import _finding_to_dict

        f = Finding(
            signal_type="test",
            severity=Severity.LOW,
            score=0.1,
            title="Test",
            description="desc",
        )
        d = _finding_to_dict(f)
        assert d["attribution"] is None


# ---------------------------------------------------------------------------
# SARIF Output — Attribution Properties
# ---------------------------------------------------------------------------


class TestSarifAttribution:
    def test_sarif_includes_attribution_properties(self) -> None:
        from drift.output.json_output import findings_to_sarif

        analysis = RepoAnalysis(
            repo_path=Path("/repo"),
            analyzed_at=datetime.datetime.now(tz=datetime.UTC),
            drift_score=0.5,
            findings=[
                Finding(
                    signal_type="guard_clause_deficit",
                    severity=Severity.MEDIUM,
                    score=0.5,
                    title="Missing guard clause",
                    description="desc",
                    file_path=Path("src/module.py"),
                    start_line=42,
                    attribution=Attribution(
                        commit_hash="abc1234",
                        author="Jane Doe",
                        email="jane@example.com",
                        date=datetime.date(2024, 4, 9),
                        ai_attributed=True,
                        ai_confidence=0.85,
                    ),
                ),
            ],
        )
        sarif_str = findings_to_sarif(analysis)
        sarif = json.loads(sarif_str)
        result = sarif["runs"][0]["results"][0]
        assert "drift:attribution" in result.get("properties", {})
        attr = result["properties"]["drift:attribution"]
        assert attr["commitHash"] == "abc1234"
        assert attr["author"] == "Jane Doe"
        assert attr["aiAttributed"] is True


# ---------------------------------------------------------------------------
# Rich Output — Attribution Display
# ---------------------------------------------------------------------------


class TestRichAttribution:
    def test_finding_detail_includes_attribution_line(self) -> None:
        from drift.output.rich_output import _format_finding_detail

        f = Finding(
            signal_type="guard_clause_deficit",
            severity=Severity.MEDIUM,
            score=0.5,
            title="Missing guard clause",
            description="desc",
            file_path=Path("src/module.py"),
            start_line=42,
            attribution=Attribution(
                commit_hash="abc1234567890",  # pragma: allowlist secret
                author="Jane Doe",
                email="jane@example.com",
                date=datetime.date(2024, 4, 9),
                branch_hint="feature/llm-refactor",
                ai_attributed=True,
                ai_confidence=0.85,
            ),
        )
        text = _format_finding_detail(f, show_code=False)
        plain = text.plain
        assert "abc1234" in plain
        assert "Jane Doe" in plain
        assert "2024-04-09" in plain
        assert "feature/llm-refactor" in plain
        assert "[AI]" in plain

    def test_finding_detail_without_attribution(self) -> None:
        from drift.output.rich_output import _format_finding_detail

        f = Finding(
            signal_type="test",
            severity=Severity.LOW,
            score=0.1,
            title="Test",
            description="desc",
        )
        text = _format_finding_detail(f, show_code=False)
        assert "╰─" not in text.plain


# ---------------------------------------------------------------------------
# Attribution Model
# ---------------------------------------------------------------------------


class TestAttributionModel:
    def test_attribution_defaults(self) -> None:
        a = Attribution(
            commit_hash="abc",
            author="Test",
            email="t@t.com",
            date=datetime.date.today(),
        )
        assert a.branch_hint is None
        assert a.ai_attributed is False
        assert a.ai_confidence == 0.0
        assert a.commit_message_summary == ""

    def test_finding_attribution_field_default_none(self) -> None:
        f = Finding(
            signal_type="test",
            severity=Severity.LOW,
            score=0.1,
            title="Test",
            description="desc",
        )
        assert f.attribution is None
