"""Tests for scripts/verify_gate_not_bypassed.py (Paket 2B / ADR-089)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Make scripts/ importable even though it has no package marker.
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from verify_gate_not_bypassed import (  # noqa: E402
    ArtifactResult,
    FindingGateRecord,
    _parse_artifact,
    main,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_artifact(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / "work_artifacts" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# _parse_artifact — clean cases
# ---------------------------------------------------------------------------


class TestParseArtifactClean:
    def test_global_safe_to_commit_true(self, tmp_path: Path) -> None:
        art = _write_artifact(
            tmp_path,
            "agent_run_clean.md",
            "# Agent Run\n\nsafe_to_commit: true\n",
        )
        result = _parse_artifact(art)
        assert result.passage_evidence_global is True
        assert result.is_clean

    def test_global_approved_true(self, tmp_path: Path) -> None:
        art = _write_artifact(
            tmp_path,
            "agent_run_clean.md",
            "# Agent Run\n\napproved: true\n",
        )
        result = _parse_artifact(art)
        assert result.passage_evidence_global is True
        assert result.is_clean

    def test_embedded_json_nudge_safe_to_commit(self, tmp_path: Path) -> None:
        nudge_json = json.dumps({"safe_to_commit": True, "direction": "stable"})
        content = f"# Agent Run\n\n```json\n{nudge_json}\n```\n"
        art = _write_artifact(tmp_path, "agent_run_json.md", content)
        result = _parse_artifact(art)
        assert result.passage_evidence_global is True
        assert result.is_clean

    def test_gate_table_auto_row_clean(self, tmp_path: Path) -> None:
        table = (
            "| finding_id | severity | gate | safe_to_commit | status |\n"
            "|---|---|---|---|---|\n"
            "| PFS-001 | low | AUTO | true | APPLIED |\n"
        )
        art = _write_artifact(tmp_path, "agent_run_auto.md", f"# Agent Run\n\n{table}")
        result = _parse_artifact(art)
        assert result.is_clean
        assert len(result.records) == 1
        assert result.records[0].gate == "AUTO"

    def test_review_pending_not_actioned_is_clean(self, tmp_path: Path) -> None:
        table = (
            "| finding_id | severity | gate | safe_to_commit | status |\n"
            "|---|---|---|---|---|\n"
            "| AVS-001 | medium | REVIEW | false | PENDING |\n"
        )
        art = _write_artifact(tmp_path, "agent_run_pending.md", f"# Agent Run\n\n{table}")
        result = _parse_artifact(art)
        assert result.is_clean  # PENDING = not actioned → no bypass

    def test_review_actioned_with_safe_to_commit_is_clean(self, tmp_path: Path) -> None:
        table = (
            "| finding_id | severity | gate | safe_to_commit | status |\n"
            "|---|---|---|---|---|\n"
            "| MDS-001 | medium | REVIEW | true | APPLIED |\n"
        )
        art = _write_artifact(tmp_path, "agent_run_review_approved.md", f"# Agent Run\n\n{table}")
        result = _parse_artifact(art)
        assert result.is_clean


# ---------------------------------------------------------------------------
# _parse_artifact — bypass cases
# ---------------------------------------------------------------------------


class TestParseArtifactBypass:
    def test_review_actioned_without_approval_is_bypass(self, tmp_path: Path) -> None:
        table = (
            "| finding_id | severity | gate | safe_to_commit | status |\n"
            "|---|---|---|---|---|\n"
            "| AVS-001 | medium | REVIEW | false | APPLIED |\n"
        )
        art = _write_artifact(tmp_path, "agent_run_bypass.md", f"# Agent Run\n\n{table}")
        result = _parse_artifact(art)
        assert not result.is_clean
        assert len(result.bypassed_records) == 1
        assert result.bypassed_records[0].finding_id == "AVS-001"

    def test_block_actioned_without_approval_is_bypass(self, tmp_path: Path) -> None:
        table = (
            "| finding_id | severity | gate | safe_to_commit | status |\n"
            "|---|---|---|---|---|\n"
            "| EDS-001 | critical | BLOCK | false | APPLIED |\n"
        )
        art = _write_artifact(tmp_path, "agent_run_block_bypass.md", f"# Agent Run\n\n{table}")
        result = _parse_artifact(art)
        assert not result.is_clean
        assert result.bypassed_records[0].gate == "BLOCK"

    def test_global_safe_to_commit_overrides_bypass(self, tmp_path: Path) -> None:
        """Global passage evidence supersedes per-row safe_to_commit=false."""
        table = (
            "| finding_id | severity | gate | safe_to_commit | status |\n"
            "|---|---|---|---|---|\n"
            "| MDS-001 | medium | REVIEW | false | APPLIED |\n"
        )
        content = f"safe_to_commit: true\n\n{table}"
        art = _write_artifact(tmp_path, "agent_run_global_pass.md", content)
        result = _parse_artifact(art)
        assert result.is_clean, "global passage evidence should clear bypass"

    def test_mixed_auto_review_bypass(self, tmp_path: Path) -> None:
        """One AUTO row (clean) + one REVIEW-actioned-without-approval (bypass)."""
        table = (
            "| finding_id | severity | gate | safe_to_commit | status |\n"
            "|---|---|---|---|---|\n"
            "| PFS-001 | low | AUTO | true | APPLIED |\n"
            "| AVS-002 | medium | REVIEW | false | APPLIED |\n"
        )
        art = _write_artifact(tmp_path, "agent_run_mixed.md", f"# Agent Run\n\n{table}")
        result = _parse_artifact(art)
        assert not result.is_clean
        assert len(result.bypassed_records) == 1
        assert result.bypassed_records[0].finding_id == "AVS-002"


# ---------------------------------------------------------------------------
# _parse_artifact — edge cases
# ---------------------------------------------------------------------------


class TestParseArtifactEdgeCases:
    def test_empty_artifact_returns_warning(self, tmp_path: Path) -> None:
        art = _write_artifact(tmp_path, "agent_run_empty.md", "")
        result = _parse_artifact(art)
        assert result.parse_warnings  # should warn about missing structure
        assert result.is_clean  # empty = nothing actioned = clean

    def test_no_gate_table_with_prose_is_clean(self, tmp_path: Path) -> None:
        art = _write_artifact(
            tmp_path,
            "agent_run_prose.md",
            "# Agent Run\n\nThis run only analyzed findings and filed a PR comment.\n",
        )
        result = _parse_artifact(art)
        assert result.is_clean  # prose-only = nothing actioned

    def test_artifact_parse_error_on_missing_file(self, tmp_path: Path) -> None:
        missing = tmp_path / "work_artifacts" / "nonexistent.md"
        result = _parse_artifact(missing)
        assert result.parse_warnings


# ---------------------------------------------------------------------------
# main() integration
# ---------------------------------------------------------------------------


class TestMainCLI:
    def test_no_artifacts_exits_2(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import verify_gate_not_bypassed as vg
        monkeypatch.setattr(vg, "ARTIFACTS_DIR", tmp_path / "empty_work_artifacts")
        assert main([]) == 2

    def test_clean_artifact_exits_0(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import verify_gate_not_bypassed as vg
        artifacts_dir = tmp_path / "work_artifacts"
        artifacts_dir.mkdir()
        (artifacts_dir / "agent_run_20260422.md").write_text(
            "safe_to_commit: true\n", encoding="utf-8"
        )
        monkeypatch.setattr(vg, "ARTIFACTS_DIR", artifacts_dir)
        assert main([]) == 0

    def test_bypass_artifact_exits_1(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import verify_gate_not_bypassed as vg
        artifacts_dir = tmp_path / "work_artifacts"
        artifacts_dir.mkdir()
        table = (
            "| finding_id | severity | gate | safe_to_commit | status |\n"
            "|---|---|---|---|---|\n"
            "| AVS-001 | medium | REVIEW | false | APPLIED |\n"
        )
        (artifacts_dir / "agent_run_20260422.md").write_text(table, encoding="utf-8")
        monkeypatch.setattr(vg, "ARTIFACTS_DIR", artifacts_dir)
        assert main([]) == 1

    def test_json_output_clean(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        import verify_gate_not_bypassed as vg
        artifacts_dir = tmp_path / "work_artifacts"
        artifacts_dir.mkdir()
        (artifacts_dir / "agent_run_20260422.md").write_text(
            "safe_to_commit: true\n", encoding="utf-8"
        )
        monkeypatch.setattr(vg, "ARTIFACTS_DIR", artifacts_dir)
        rc = main(["--json"])
        assert rc == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["clean"] is True
        assert data["bypass_count"] == 0

    def test_specific_artifact_missing_exits_2(self, tmp_path: Path) -> None:
        missing = tmp_path / "work_artifacts" / "nonexistent.md"
        with pytest.raises(SystemExit) as exc_info:
            main(["--artifact", str(missing)])
        assert exc_info.value.code == 2
