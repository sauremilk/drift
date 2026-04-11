"""Tests for the ``drift badge`` command."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from drift.cli import main
from drift.commands.badge import _badge_color_for_score
from drift.models import Severity, severity_for_score


class TestBadgeCommand:
    """Test the ``drift badge`` command."""

    def test_badge_outputs_shields_url(self, tmp_repo: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["badge", "--repo", str(tmp_repo)])
        assert result.exit_code == 0
        assert "img.shields.io" in result.output

    def test_badge_outputs_markdown_snippet(self, tmp_repo: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["badge", "--repo", str(tmp_repo)])
        assert result.exit_code == 0
        assert "[![Drift Score]" in result.output

    def test_badge_write_to_file(self, tmp_repo: Path) -> None:
        out_file = tmp_repo / "badge.txt"
        runner = CliRunner()
        result = runner.invoke(main, ["badge", "--repo", str(tmp_repo), "--output", str(out_file)])
        assert result.exit_code == 0
        assert out_file.exists()
        url = out_file.read_text(encoding="utf-8")
        assert "img.shields.io" in url

    def test_badge_style_option(self, tmp_repo: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["badge", "--repo", str(tmp_repo), "--style", "for-the-badge"])
        assert result.exit_code == 0
        assert "for-the-badge" in result.output

    def test_badge_color_green_for_low_score(self, tmp_repo: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["badge", "--repo", str(tmp_repo)])
        assert result.exit_code == 0
        # An empty repo should have low drift → brightgreen
        assert "brightgreen" in result.output

    def test_badge_color_thresholds_follow_severity_mapping(self) -> None:
        severity_to_color = {
            Severity.CRITICAL: "critical",
            Severity.HIGH: "orange",
            Severity.MEDIUM: "yellow",
            Severity.LOW: "brightgreen",
            Severity.INFO: "brightgreen",
        }

        boundary_samples = [0.19, 0.2, 0.39, 0.4, 0.59, 0.6, 0.79, 0.8]
        for score in boundary_samples:
            expected_color = severity_to_color[severity_for_score(score)]
            assert _badge_color_for_score(score) == expected_color


class TestBadgeSvgFormat:
    """Test ``drift badge --format svg``."""

    def test_svg_output_to_stdout(self, tmp_repo: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["badge", "--repo", str(tmp_repo), "--format", "svg"])
        assert result.exit_code == 0
        assert "<svg" in result.output
        assert "drift score" in result.output

    def test_svg_output_to_file(self, tmp_repo: Path) -> None:
        out_file = tmp_repo / "badge.svg"
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["badge", "--repo", str(tmp_repo), "--format", "svg", "--output", str(out_file)],
        )
        assert result.exit_code == 0
        assert out_file.exists()
        svg = out_file.read_text(encoding="utf-8")
        assert "<svg" in svg
        assert "drift score" in svg


class TestBadgeSvgRenderer:
    """Unit tests for the SVG rendering module."""

    def test_render_produces_valid_svg(self) -> None:
        from drift.output.badge_svg import render_badge_svg

        svg = render_badge_svg("drift score", "0.42", "yellow")
        assert svg.startswith("<svg")
        assert "drift score" in svg
        assert "0.42" in svg
        assert 'aria-label="drift score: 0.42"' in svg

    def test_render_uses_hex_for_named_color(self) -> None:
        from drift.output.badge_svg import render_badge_svg

        svg = render_badge_svg("test", "1.00", "critical")
        assert "#e05d44" in svg

    def test_render_accepts_raw_hex_color(self) -> None:
        from drift.output.badge_svg import render_badge_svg

        svg = render_badge_svg("test", "0.10", "#abc")
        assert "#abc" in svg

    def test_render_brightgreen_for_low(self) -> None:
        from drift.output.badge_svg import render_badge_svg

        svg = render_badge_svg("drift score", "0.15", "brightgreen")
        assert "#4c1" in svg
