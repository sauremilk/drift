"""Tests for adr_scanner — scans decisions/ for active ADRs relevant to a task scope."""

from __future__ import annotations

from pathlib import Path

from drift.adr_scanner import scan_active_adrs

# ---------------------------------------------------------------------------
# Fixtures helpers
# ---------------------------------------------------------------------------


def _write_adr(decisions_dir: Path, filename: str, content: str) -> Path:
    """Write an ADR file and return its path."""
    path = decisions_dir / filename
    path.write_text(content, encoding="utf-8")
    return path


_ADR_ACCEPTED = """\
---
id: ADR-001
status: accepted
date: 2026-01-01
---
# ADR-001: Use signals layer for pattern detection

## Kontext
signals layer handles pattern detection.
"""

_ADR_PROPOSED = """\
---
id: ADR-002
status: proposed
date: 2026-01-02
---
# ADR-002: Introduce session management

## Kontext
session management for mcp layer.
"""

_ADR_REJECTED = """\
---
id: ADR-003
status: rejected
date: 2026-01-03
---
# ADR-003: Remove all caching

## Kontext
caching removal was considered.
"""

_ADR_OBSOLETE = """\
---
id: ADR-004
status: obsolete
date: 2026-01-04
---
# ADR-004: Old approach

## Kontext
this is obsolete.
"""

_ADR_SIGNALS_SCOPE = """\
---
id: ADR-005
status: accepted
date: 2026-01-05
---
# ADR-005: signals layer boundary rules

## Kontext
src/drift/signals must not import from output or commands.
"""


# ---------------------------------------------------------------------------
# Status filtering
# ---------------------------------------------------------------------------


class TestStatusFiltering:
    def test_accepted_adr_is_returned(self, tmp_path: Path) -> None:
        decisions = tmp_path / "decisions"
        decisions.mkdir()
        _write_adr(decisions, "ADR-001.md", _ADR_ACCEPTED)

        result = scan_active_adrs(tmp_path, scope_paths=[], task="")
        assert len(result) == 1
        assert result[0]["id"] == "ADR-001"

    def test_proposed_adr_is_returned(self, tmp_path: Path) -> None:
        decisions = tmp_path / "decisions"
        decisions.mkdir()
        _write_adr(decisions, "ADR-002.md", _ADR_PROPOSED)

        result = scan_active_adrs(tmp_path, scope_paths=[], task="")
        assert len(result) == 1
        assert result[0]["id"] == "ADR-002"

    def test_rejected_adr_is_filtered(self, tmp_path: Path) -> None:
        decisions = tmp_path / "decisions"
        decisions.mkdir()
        _write_adr(decisions, "ADR-003.md", _ADR_REJECTED)

        result = scan_active_adrs(tmp_path, scope_paths=[], task="")
        assert result == []

    def test_obsolete_adr_is_filtered(self, tmp_path: Path) -> None:
        decisions = tmp_path / "decisions"
        decisions.mkdir()
        _write_adr(decisions, "ADR-004.md", _ADR_OBSOLETE)

        result = scan_active_adrs(tmp_path, scope_paths=[], task="")
        assert result == []

    def test_mixed_statuses_returns_only_active(self, tmp_path: Path) -> None:
        decisions = tmp_path / "decisions"
        decisions.mkdir()
        _write_adr(decisions, "ADR-001.md", _ADR_ACCEPTED)
        _write_adr(decisions, "ADR-002.md", _ADR_PROPOSED)
        _write_adr(decisions, "ADR-003.md", _ADR_REJECTED)
        _write_adr(decisions, "ADR-004.md", _ADR_OBSOLETE)

        result = scan_active_adrs(tmp_path, scope_paths=[], task="")
        ids = {r["id"] for r in result}
        assert ids == {"ADR-001", "ADR-002"}


# ---------------------------------------------------------------------------
# Scope filtering
# ---------------------------------------------------------------------------


class TestScopeFiltering:
    def test_scope_path_token_matches_adr_content(self, tmp_path: Path) -> None:
        decisions = tmp_path / "decisions"
        decisions.mkdir()
        _write_adr(decisions, "ADR-005.md", _ADR_SIGNALS_SCOPE)

        result = scan_active_adrs(
            tmp_path,
            scope_paths=["src/drift/signals"],
            task="",
        )
        assert len(result) == 1
        assert result[0]["id"] == "ADR-005"

    def test_scope_path_non_match_returns_empty(self, tmp_path: Path) -> None:
        decisions = tmp_path / "decisions"
        decisions.mkdir()
        _write_adr(decisions, "ADR-005.md", _ADR_SIGNALS_SCOPE)

        result = scan_active_adrs(
            tmp_path,
            scope_paths=["src/drift/output"],
            task="",
        )
        assert result == []

    def test_task_keyword_matches_adr_content(self, tmp_path: Path) -> None:
        decisions = tmp_path / "decisions"
        decisions.mkdir()
        _write_adr(decisions, "ADR-002.md", _ADR_PROPOSED)

        result = scan_active_adrs(
            tmp_path,
            scope_paths=[],
            task="implement session management for agent",
        )
        assert len(result) == 1
        assert result[0]["id"] == "ADR-002"

    def test_empty_scope_and_task_returns_all_active(self, tmp_path: Path) -> None:
        """When neither scope nor task provided, return all active ADRs."""
        decisions = tmp_path / "decisions"
        decisions.mkdir()
        _write_adr(decisions, "ADR-001.md", _ADR_ACCEPTED)
        _write_adr(decisions, "ADR-002.md", _ADR_PROPOSED)
        _write_adr(decisions, "ADR-003.md", _ADR_REJECTED)

        result = scan_active_adrs(tmp_path, scope_paths=[], task="")
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Result structure
# ---------------------------------------------------------------------------


class TestResultStructure:
    def test_result_has_required_fields(self, tmp_path: Path) -> None:
        decisions = tmp_path / "decisions"
        decisions.mkdir()
        _write_adr(decisions, "ADR-001.md", _ADR_ACCEPTED)

        result = scan_active_adrs(tmp_path, scope_paths=[], task="")
        assert len(result) == 1
        item = result[0]
        assert "id" in item
        assert "title" in item
        assert "status" in item
        assert "scope_match_reason" in item

    def test_title_extracted_from_heading(self, tmp_path: Path) -> None:
        decisions = tmp_path / "decisions"
        decisions.mkdir()
        _write_adr(decisions, "ADR-001.md", _ADR_ACCEPTED)

        result = scan_active_adrs(tmp_path, scope_paths=[], task="")
        assert "signals" in result[0]["title"].lower()

    def test_status_preserved(self, tmp_path: Path) -> None:
        decisions = tmp_path / "decisions"
        decisions.mkdir()
        _write_adr(decisions, "ADR-002.md", _ADR_PROPOSED)

        result = scan_active_adrs(tmp_path, scope_paths=[], task="")
        assert result[0]["status"] == "proposed"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_missing_decisions_dir_returns_empty(self, tmp_path: Path) -> None:
        """No decisions/ directory → empty list, no exception."""
        result = scan_active_adrs(tmp_path, scope_paths=[], task="")
        assert result == []

    def test_empty_decisions_dir_returns_empty(self, tmp_path: Path) -> None:
        decisions = tmp_path / "decisions"
        decisions.mkdir()
        result = scan_active_adrs(tmp_path, scope_paths=[], task="")
        assert result == []

    def test_non_md_files_ignored(self, tmp_path: Path) -> None:
        decisions = tmp_path / "decisions"
        decisions.mkdir()
        (decisions / "README.txt").write_text("not an ADR", encoding="utf-8")
        result = scan_active_adrs(tmp_path, scope_paths=[], task="")
        assert result == []

    def test_max_results_limit(self, tmp_path: Path) -> None:
        decisions = tmp_path / "decisions"
        decisions.mkdir()
        for i in range(10):
            content = (
                f"---\nid: ADR-{i:03d}\nstatus: accepted\ndate: 2026-01-01\n---\n"
                f"# ADR-{i:03d}: Rule {i}\n\n## Kontext\nsome content {i}.\n"
            )
            _write_adr(decisions, f"ADR-{i:03d}.md", content)

        result = scan_active_adrs(tmp_path, scope_paths=[], task="", max_results=3)
        assert len(result) <= 3

    def test_malformed_frontmatter_does_not_raise(self, tmp_path: Path) -> None:
        decisions = tmp_path / "decisions"
        decisions.mkdir()
        _write_adr(decisions, "ADR-bad.md", "no frontmatter here\njust some text\n")
        # Should not raise
        result = scan_active_adrs(tmp_path, scope_paths=[], task="")
        assert isinstance(result, list)
