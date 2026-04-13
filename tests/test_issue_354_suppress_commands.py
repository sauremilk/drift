from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from drift.cli import main


def _write_sample_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_suppress_list_shows_inline_suppressions_with_metadata(tmp_path: Path) -> None:
    _write_sample_file(
        tmp_path / "src" / "mod.py",
        """
def alpha() -> None:
    pass  # drift:ignore[AVS] until:2026-12-31 reason:legacy transition


def beta() -> None:
    pass  # drift:ignore
""".strip(),
    )

    runner = CliRunner()
    result = runner.invoke(main, ["suppress", "list", "--repo", str(tmp_path)])

    assert result.exit_code == 0
    assert "src/mod.py" in result.output
    assert "AVS" in result.output
    assert "ALL" in result.output
    assert "2026-12-31" in result.output
    assert "legacy transition" in result.output


def test_suppress_audit_exits_non_zero_for_expired_entries(tmp_path: Path) -> None:
    _write_sample_file(
        tmp_path / "src" / "mod.py",
        """
def alpha() -> None:
    pass  # drift:ignore[AVS] until:2025-01-01 reason:cleanup pending
""".strip(),
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "suppress",
            "audit",
            "--repo",
            str(tmp_path),
            "--today",
            "2026-04-13",
        ],
    )

    assert result.exit_code == 1
    assert "Expired suppressions" in result.output
    assert "Found 1 expired inline suppression" in result.output


def test_suppress_audit_passes_when_no_suppressions_are_expired(tmp_path: Path) -> None:
    _write_sample_file(
        tmp_path / "src" / "mod.py",
        """
def alpha() -> None:
    pass  # drift:ignore[AVS] until:2099-01-01 reason:future cleanup
""".strip(),
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "suppress",
            "audit",
            "--repo",
            str(tmp_path),
            "--today",
            "2026-04-13",
        ],
    )

    assert result.exit_code == 0
    assert "No expired suppressions." in result.output
