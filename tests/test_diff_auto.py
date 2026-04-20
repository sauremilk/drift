"""Tests for drift diff --auto — automated post-fix feedback loop."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------


def _minimal_scan_json(
    drift_score: float = 10.0,
    findings: list[dict] | None = None,
    analyzed_at: str = "2026-04-19T10:00:00+00:00",
) -> str:
    """Return a minimal drift analyze --format json snapshot string."""
    if findings is None:
        findings = []
    data = {
        "analyzed_at": analyzed_at,
        "drift_score": drift_score,
        "findings": findings,
    }
    return json.dumps(data, indent=2)


def _finding(
    fingerprint: str,
    signal: str = "PFS",
    severity: str = "high",
    title: str = "Pattern Fragmentation",
    file: str = "src/foo.py",
    start_line: int = 42,
) -> dict:
    return {
        "finding_id": fingerprint,
        "fingerprint": fingerprint,
        "signal": signal,
        "severity": severity,
        "title": title,
        "file": file,
        "start_line": start_line,
    }


# ---------------------------------------------------------------------------
# Tests: _last_scan helper module
# ---------------------------------------------------------------------------


class TestGetLastScanPath:
    def test_returns_path_inside_cache_dir(self, tmp_path: Path) -> None:
        from drift.commands._last_scan import get_last_scan_path

        result = get_last_scan_path(tmp_path, ".drift-cache")
        assert result == tmp_path / ".drift-cache" / "last_scan.json"

    def test_custom_cache_dir(self, tmp_path: Path) -> None:
        from drift.commands._last_scan import get_last_scan_path

        result = get_last_scan_path(tmp_path, ".my-cache")
        assert result == tmp_path / ".my-cache" / "last_scan.json"


class TestSaveLastScan:
    def test_creates_file_with_json(self, tmp_path: Path, monkeypatch) -> None:
        from drift.commands._last_scan import get_last_scan_path, save_last_scan

        # Build a minimal fake analysis object
        class _FakeAnalysis:
            pass

        fake = _FakeAnalysis()
        captured: list[object] = []

        def fake_analysis_to_json(analysis, **kwargs) -> str:
            captured.append(analysis)
            return _minimal_scan_json(drift_score=7.5)

        monkeypatch.setattr("drift.commands._last_scan.analysis_to_json", fake_analysis_to_json)

        save_last_scan(fake, tmp_path, ".drift-cache")

        dest = get_last_scan_path(tmp_path, ".drift-cache")
        assert dest.exists()
        data = json.loads(dest.read_text(encoding="utf-8"))
        assert data["drift_score"] == 7.5

    def test_creates_parent_dirs(self, tmp_path: Path, monkeypatch) -> None:
        from drift.commands._last_scan import save_last_scan

        monkeypatch.setattr(
            "drift.commands._last_scan.analysis_to_json",
            lambda *a, **kw: _minimal_scan_json(),
        )
        deep_cache = ".nested/cache/dir"
        save_last_scan(object(), tmp_path, deep_cache)
        assert (tmp_path / deep_cache / "last_scan.json").exists()

    def test_silently_ignores_write_error(self, tmp_path: Path, monkeypatch) -> None:
        """save_last_scan must not raise even if serialization fails."""
        from drift.commands._last_scan import save_last_scan

        def bad_serialize(*a, **kw):
            raise RuntimeError("disk full")

        monkeypatch.setattr("drift.commands._last_scan.analysis_to_json", bad_serialize)
        # Should not raise
        save_last_scan(object(), tmp_path, ".drift-cache")

    def test_overwrites_existing_file(self, tmp_path: Path, monkeypatch) -> None:
        from drift.commands._last_scan import get_last_scan_path, save_last_scan

        dest = get_last_scan_path(tmp_path, ".drift-cache")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(_minimal_scan_json(drift_score=5.0), encoding="utf-8")

        monkeypatch.setattr(
            "drift.commands._last_scan.analysis_to_json",
            lambda *a, **kw: _minimal_scan_json(drift_score=3.0),
        )
        save_last_scan(object(), tmp_path, ".drift-cache")
        data = json.loads(dest.read_text(encoding="utf-8"))
        assert data["drift_score"] == 3.0


# ---------------------------------------------------------------------------
# Tests: drift diff --auto CLI
# ---------------------------------------------------------------------------


class TestDiffAutoFlags:
    def test_auto_and_from_file_are_incompatible(self, tmp_path: Path) -> None:
        from drift.commands.diff_cmd import diff

        dummy = tmp_path / "snap.json"
        dummy.write_text(_minimal_scan_json(), encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(
            diff,
            [
                "--repo",
                str(tmp_path),
                "--auto",
                "--from-file",
                str(dummy),
                "--to-file",
                str(dummy),
            ],
        )
        assert result.exit_code != 0
        assert "auto" in result.output.lower() or "from-file" in result.output.lower()

    def test_auto_and_uncommitted_are_incompatible(self, tmp_path: Path) -> None:
        from drift.commands.diff_cmd import diff

        runner = CliRunner()
        result = runner.invoke(
            diff,
            ["--repo", str(tmp_path), "--auto", "--uncommitted"],
        )
        assert result.exit_code != 0

    def test_auto_without_last_scan_gives_clear_error(self, tmp_path: Path) -> None:
        from drift.commands.diff_cmd import diff

        runner = CliRunner()
        result = runner.invoke(diff, ["--repo", str(tmp_path), "--auto"])
        assert result.exit_code != 0
        output = result.output + (str(result.exception) if result.exception else "")
        # Should mention drift analyze or last_scan
        assert any(
            keyword in output.lower()
            for keyword in ["drift analyze", "last_scan", "kein", "no snapshot", "snapshot"]
        )


class TestDiffAutoSuccess:
    def test_auto_shows_score_delta(self, tmp_path: Path, monkeypatch) -> None:
        """--auto renders score before → after and finding changes."""
        from drift.commands.diff_cmd import diff

        # Write last_scan.json (before: 10.0, 2 findings)
        cache_dir = tmp_path / ".drift-cache"
        cache_dir.mkdir()
        last_scan = cache_dir / "last_scan.json"
        fp_resolved = "aabbccdd11223344"
        fp_shared = "deadbeef12345678"  # pragma: allowlist secret
        last_scan.write_text(
            _minimal_scan_json(
                drift_score=10.0,
                analyzed_at="2026-04-19T09:00:00+00:00",
                findings=[
                    _finding(fp_resolved, title="Old Finding"),
                    _finding(fp_shared, title="Shared Finding"),
                ],
            ),
            encoding="utf-8",
        )

        # Mock fresh analysis: 8.5, 2 findings (1 shared, 1 new LOW → no exit-1)
        fp_new = "11223344aabbccdd"
        fresh_json = _minimal_scan_json(
            drift_score=8.5,
            analyzed_at="2026-04-19T10:30:00+00:00",
            findings=[
                _finding(fp_shared, title="Shared Finding"),
                _finding(fp_new, title="New Finding", severity="low"),
            ],
        )

        monkeypatch.setattr(
            "drift.commands.diff_cmd._run_fresh_analysis_to_json",
            lambda path: fresh_json,
        )

        runner = CliRunner()
        result = runner.invoke(diff, ["--repo", str(tmp_path), "--auto"])

        assert result.exit_code == 0, result.output
        # Score values must appear
        assert "10" in result.output
        assert "8" in result.output

    def test_auto_shows_resolved_findings(self, tmp_path: Path, monkeypatch) -> None:
        from drift.commands.diff_cmd import diff

        cache_dir = tmp_path / ".drift-cache"
        cache_dir.mkdir()
        last_scan = cache_dir / "last_scan.json"
        fp_resolved = "rrrrrrrrrrrrrrrr"
        last_scan.write_text(
            _minimal_scan_json(
                drift_score=5.0,
                findings=[_finding(fp_resolved, title="Resolved Issue")],
            ),
            encoding="utf-8",
        )

        monkeypatch.setattr(
            "drift.commands.diff_cmd._run_fresh_analysis_to_json",
            lambda path: _minimal_scan_json(drift_score=3.0, findings=[]),
        )

        runner = CliRunner()
        result = runner.invoke(diff, ["--repo", str(tmp_path), "--auto"])
        assert result.exit_code == 0, result.output
        # Should mention resolved
        lower = result.output.lower()
        assert "resolved" in lower or "gelöst" in lower or "1" in lower

    def test_auto_shows_no_change_message(self, tmp_path: Path, monkeypatch) -> None:
        from drift.commands.diff_cmd import diff

        fp = "samesamesamesame"
        snap_json = _minimal_scan_json(
            drift_score=5.0,
            findings=[_finding(fp)],
        )

        cache_dir = tmp_path / ".drift-cache"
        cache_dir.mkdir()
        (cache_dir / "last_scan.json").write_text(snap_json, encoding="utf-8")

        monkeypatch.setattr(
            "drift.commands.diff_cmd._run_fresh_analysis_to_json",
            lambda path: snap_json,
        )

        runner = CliRunner()
        result = runner.invoke(diff, ["--repo", str(tmp_path), "--auto"])
        assert result.exit_code == 0, result.output
        lower = result.output.lower()
        assert any(word in lower for word in ["keine", "no change", "unchanged", "stable"])

    def test_auto_exit_code_1_on_new_high_critical(self, tmp_path: Path, monkeypatch) -> None:
        """Exit code 1 when new HIGH/CRITICAL findings appear (same as --from-file/--to-file)."""
        from drift.commands.diff_cmd import diff

        cache_dir = tmp_path / ".drift-cache"
        cache_dir.mkdir()
        (cache_dir / "last_scan.json").write_text(
            _minimal_scan_json(drift_score=5.0, findings=[]),
            encoding="utf-8",
        )

        monkeypatch.setattr(
            "drift.commands.diff_cmd._run_fresh_analysis_to_json",
            lambda path: _minimal_scan_json(
                drift_score=8.0,
                findings=[_finding("newcritical1234ab", severity="critical", title="Critical!")],
            ),
        )

        runner = CliRunner()
        result = runner.invoke(diff, ["--repo", str(tmp_path), "--auto"])
        assert result.exit_code == 1
