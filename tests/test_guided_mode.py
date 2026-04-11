"""Tests for drift Guided Mode — guided_output, prompt_generator, status command."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

import pytest

from drift.output.guided_output import (
    SCORING_ACTIVE_SIGNALS,
    TrafficLight,
    can_continue,
    determine_status,
    emoji_for_status,
    headline_for_status,
    is_calibrated,
    plain_text_for_signal,
    severity_label,
)
from drift.output.prompt_generator import (
    _PROMPT_TEMPLATES,
    file_role_description,
    generate_agent_prompt,
)

# ---------------------------------------------------------------------------
# Minimal stubs
# ---------------------------------------------------------------------------


@dataclass
class _FakeSeverity:
    value: str


@dataclass
class _FakeLogicalLocation:
    kind: str = ""
    name: str = ""
    class_name: str | None = None


@dataclass
class _FakeFinding:
    signal_type: str = "pattern_fragmentation"
    severity: _FakeSeverity = field(default_factory=lambda: _FakeSeverity("medium"))
    score: float = 0.5
    impact: float = 0.5
    file_path: Path | PurePosixPath | None = None
    start_line: int | None = None
    end_line: int | None = None
    title: str = "Test finding"
    description: str = "Test description"
    fix: str | None = "Shared first step"
    logical_location: _FakeLogicalLocation | None = None
    symbol: str | None = None
    related_files: list[PurePosixPath] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    rule_id: str = "PFS"


@dataclass
class _FakeAnalysis:
    drift_score: float = 0.3
    findings: list[Any] = field(default_factory=list)


# ===========================================================================
# TrafficLight / determine_status
# ===========================================================================


class TestTrafficLight:
    def test_green_low_score_no_findings(self) -> None:
        a = _FakeAnalysis(drift_score=0.1, findings=[])
        assert determine_status(a) == TrafficLight.GREEN

    def test_yellow_medium_score(self) -> None:
        a = _FakeAnalysis(drift_score=0.4, findings=[])
        assert determine_status(a) == TrafficLight.YELLOW

    def test_red_high_score(self) -> None:
        a = _FakeAnalysis(drift_score=0.7, findings=[])
        assert determine_status(a) == TrafficLight.RED

    def test_red_on_critical_finding(self) -> None:
        """CRITICAL finding forces RED regardless of score (PRD F-02)."""
        f = _FakeFinding(severity=_FakeSeverity("critical"))
        a = _FakeAnalysis(drift_score=0.1, findings=[f])
        assert determine_status(a) == TrafficLight.RED

    def test_yellow_on_high_finding(self) -> None:
        """HIGH finding forces at least YELLOW."""
        f = _FakeFinding(severity=_FakeSeverity("high"))
        a = _FakeAnalysis(drift_score=0.1, findings=[f])
        assert determine_status(a) == TrafficLight.YELLOW

    def test_custom_thresholds(self) -> None:
        a = _FakeAnalysis(drift_score=0.5, findings=[])
        th = {"green_max": 0.6, "yellow_max": 0.8}
        assert determine_status(a, th) == TrafficLight.GREEN

    def test_empty_thresholds_use_defaults(self) -> None:
        a = _FakeAnalysis(drift_score=0.4, findings=[])
        assert determine_status(a, {}) == TrafficLight.YELLOW


class TestCanContinue:
    def test_green_can_continue(self) -> None:
        assert can_continue(TrafficLight.GREEN) is True

    def test_yellow_cannot_continue(self) -> None:
        assert can_continue(TrafficLight.YELLOW) is False

    def test_red_cannot_continue(self) -> None:
        assert can_continue(TrafficLight.RED) is False


# ===========================================================================
# Headlines / Emojis / Labels
# ===========================================================================


class TestHeadlines:
    @pytest.mark.parametrize("status", list(TrafficLight))
    def test_headline_exists_for_every_status(self, status: TrafficLight) -> None:
        h = headline_for_status(status)
        assert isinstance(h, str)
        assert len(h) > 10

    @pytest.mark.parametrize("status", list(TrafficLight))
    def test_emoji_exists_for_every_status(self, status: TrafficLight) -> None:
        e = emoji_for_status(status)
        assert len(e) >= 1


class TestSeverityLabels:
    @pytest.mark.parametrize(
        "sev,expected",
        [
            ("critical", "Kritisch"),
            ("high", "Wichtig"),
            ("medium", "Auffällig"),
            ("low", "Hinweis"),
            ("info", "Info"),
        ],
    )
    def test_known_severities(self, sev: str, expected: str) -> None:
        assert severity_label(sev) == expected

    def test_unknown_severity_returns_raw(self) -> None:
        assert severity_label("exotic") == "exotic"


# ===========================================================================
# Signal plain text
# ===========================================================================


class TestSignalPlainText:
    def test_all_scoring_signals_have_plain_text(self) -> None:
        """Every scoring-active signal MUST have a plain-text description."""
        for sig in SCORING_ACTIVE_SIGNALS:
            text = plain_text_for_signal(sig)
            assert text != sig, f"Signal {sig} has no plain text"
            assert len(text) > 10

    def test_unknown_signal_returns_type_name(self) -> None:
        assert plain_text_for_signal("nonexistent_signal") == "nonexistent_signal"

    def test_all_signal_types_covered(self) -> None:
        """All 25 SignalType enum values should have plain text."""
        from drift.models import SignalType

        for st in SignalType:
            text = plain_text_for_signal(st.value)
            assert text != st.value, f"SignalType {st.value} missing plain text"


# ===========================================================================
# Prompt generation
# ===========================================================================


class TestPromptTemplates:
    def test_all_scoring_signals_have_templates(self) -> None:
        """Every scoring-active signal MUST have a prompt template."""
        for sig in SCORING_ACTIVE_SIGNALS:
            assert sig in _PROMPT_TEMPLATES, f"Missing template for {sig}"

    def test_templates_contain_file_role_placeholder(self) -> None:
        for sig, tmpl in _PROMPT_TEMPLATES.items():
            assert "{file_role}" in tmpl, f"Template for {sig} missing {{file_role}}"

    def test_templates_contain_expected_outcome(self) -> None:
        """PRD F-07: each prompt ends with an expected-outcome sentence."""
        for sig, tmpl in _PROMPT_TEMPLATES.items():
            assert "Danach sollte" in tmpl, (
                f"Template for {sig} missing expected-outcome ('Danach sollte')"
            )


class TestFileRoleDescription:
    def test_logical_location_function(self) -> None:
        f = _FakeFinding(logical_location=_FakeLogicalLocation(kind="function", name="do_stuff"))
        assert "do_stuff" in file_role_description(f)

    def test_logical_location_method(self) -> None:
        f = _FakeFinding(
            logical_location=_FakeLogicalLocation(kind="method", name="save", class_name="User")
        )
        desc = file_role_description(f)
        assert "save" in desc
        assert "User" in desc

    def test_directory_heuristic(self) -> None:
        f = _FakeFinding(
            file_path=PurePosixPath("src/api/routes.py"),
            logical_location=None,
        )
        desc = file_role_description(f)
        assert "API" in desc or "api" in desc.lower()

    def test_fallback_no_info(self) -> None:
        f = _FakeFinding(file_path=None, logical_location=None, symbol=None)
        desc = file_role_description(f)
        assert "Bereich" in desc or "Projekt" in desc


class TestGenerateAgentPrompt:
    def test_returns_string(self) -> None:
        f = _FakeFinding(signal_type="pattern_fragmentation")
        prompt = generate_agent_prompt(f)
        assert isinstance(prompt, str)
        assert len(prompt) > 20

    def test_unknown_signal_fallback(self) -> None:
        f = _FakeFinding(signal_type="totally_unknown")
        prompt = generate_agent_prompt(f)
        assert "Problem" in prompt or "Projekt" in prompt

    def test_no_raw_file_path_in_prompt(self) -> None:
        """PRD F-06: prompts must not contain raw file paths."""
        f = _FakeFinding(
            signal_type="mutant_duplicate",
            file_path=PurePosixPath("src/utils/helpers.py"),
            logical_location=None,
        )
        prompt = generate_agent_prompt(f)
        assert "src/utils/helpers.py" not in prompt
        assert ".py" not in prompt


# ===========================================================================
# Calibration hint
# ===========================================================================


class TestCalibration:
    def test_calibrated_when_thresholds_present(self) -> None:
        assert is_calibrated({"green_max": 0.35}) is True

    def test_not_calibrated_for_empty(self) -> None:
        assert is_calibrated({}) is False

    def test_not_calibrated_for_none(self) -> None:
        assert is_calibrated(None) is False


# ===========================================================================
# _finding_guided (finding_rendering integration)
# ===========================================================================


class TestFindingGuided:
    def test_returns_expected_keys(self) -> None:
        from drift.finding_rendering import _finding_guided

        f = _FakeFinding(
            signal_type="pattern_fragmentation",
            file_path=PurePosixPath("src/utils/foo.py"),
            start_line=10,
        )
        result = _finding_guided(f, rank=1)
        assert "signal" in result
        assert "plain_text" in result
        assert "agent_prompt" in result
        assert "severity_label" in result
        assert "file_role" in result
        assert result["rank"] == 1

    def test_no_rank_when_omitted(self) -> None:
        from drift.finding_rendering import _finding_guided

        f = _FakeFinding()
        result = _finding_guided(f)
        assert "rank" not in result


class TestFirstRunSummary:
    def test_select_priority_findings_prefers_architecture_boundary(self) -> None:
        from drift.finding_rendering import select_priority_findings

        architecture = _FakeFinding(
            signal_type="architecture_violation",
            severity=_FakeSeverity("medium"),
            title="Layer violation",
            impact=0.4,
        )
        style = _FakeFinding(
            signal_type="naming_contract_violation",
            severity=_FakeSeverity("high"),
            title="Naming issue",
            impact=0.8,
        )
        analysis = _FakeAnalysis(drift_score=0.5, findings=[style, architecture])

        result = select_priority_findings(analysis, max_items=1)

        assert len(result) == 1
        assert result[0].signal_type == "architecture_violation"

    def test_build_first_run_summary_returns_guidance(self) -> None:
        from drift.finding_rendering import build_first_run_summary

        finding = _FakeFinding(
            signal_type="pattern_fragmentation",
            file_path=Path("src/app/service.py"),
            start_line=10,
        )
        analysis = _FakeAnalysis(drift_score=0.4, findings=[finding])

        summary = build_first_run_summary(analysis, max_items=1, language="de")

        assert "headline" in summary
        assert "why_this_matters" in summary
        assert "next_step" in summary
        assert len(summary["top_findings"]) == 1
        assert summary["top_findings"][0]["signal_type"] == "pattern_fragmentation"

    def test_build_first_run_summary_empty_uses_default_next_step(self) -> None:
        from drift.finding_rendering import build_first_run_summary

        summary = build_first_run_summary(_FakeAnalysis(), language="en")

        assert summary["top_findings"] == []
        assert "drift check --fail-on none" in summary["next_step"]


# ===========================================================================
# Status command (Click CliRunner)
# ===========================================================================


class TestStatusCommand:
    def test_status_help(self) -> None:
        from click.testing import CliRunner

        from drift.commands.status import status

        runner = CliRunner()
        result = runner.invoke(status, ["--help"])
        assert result.exit_code == 0
        assert "Ampel" in result.output or "status" in result.output.lower()

    def test_status_always_exit_zero(self, tmp_path: Any) -> None:
        """PRD NF-08: exit code is always 0."""
        from click.testing import CliRunner

        from drift.commands.status import status

        # Create minimal repo structure
        (tmp_path / "example.py").write_text("x = 1\n", encoding="utf-8")
        runner = CliRunner()
        result = runner.invoke(status, ["--repo", str(tmp_path), "--top", "1"])
        assert result.exit_code == 0

    def test_status_json_payload_contains_guidance_fields(self) -> None:
        from drift.commands.status import _build_json_payload

        finding = _FakeFinding(file_path=Path("src/app.py"), start_line=7)
        payload = _build_json_payload(
            TrafficLight.YELLOW,
            "Es gibt Stellen, die Aufmerksamkeit brauchen.",
            False,
            [finding],
            _FakeAnalysis(findings=[finding]),
            {"green_max": 0.35, "yellow_max": 0.65},
            {
                "why_this_matters": "Ein einzelner Fix ist der beste erste Schritt.",
                "next_step": "Shared first step",
            },
        )

        assert payload["why_this_matters"] == "Ein einzelner Fix ist der beste erste Schritt."
        assert payload["next_step"] == "Shared first step"


# ===========================================================================
# Setup command (Click CliRunner)
# ===========================================================================


class TestSetupCommand:
    def test_setup_help(self) -> None:
        from click.testing import CliRunner

        from drift.commands.setup import setup

        runner = CliRunner()
        result = runner.invoke(setup, ["--help"])
        assert result.exit_code == 0
        assert "setup" in result.output.lower() or "Erstnutzer" in result.output

    def test_setup_non_interactive(self, tmp_path: Any) -> None:
        from click.testing import CliRunner

        from drift.commands.setup import setup

        runner = CliRunner()
        result = runner.invoke(setup, ["--repo", str(tmp_path), "--non-interactive"])
        assert result.exit_code == 0
        config_file = tmp_path / "drift.yaml"
        assert config_file.exists()
        content = config_file.read_text(encoding="utf-8")
        assert "vibe-coding" in content

    def test_setup_json_output(self, tmp_path: Any) -> None:
        import json

        from click.testing import CliRunner

        from drift.commands.setup import setup

        runner = CliRunner()
        result = runner.invoke(setup, ["--repo", str(tmp_path), "--non-interactive", "--json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["profile"] == "vibe-coding"
        assert "config" in payload


# ===========================================================================
# Profile fields
# ===========================================================================


class TestProfileGuidedFields:
    def test_vibe_coding_has_guided_thresholds(self) -> None:
        from drift.profiles import get_profile

        prof = get_profile("vibe-coding")
        assert prof.guided_thresholds
        assert "green_max" in prof.guided_thresholds
        assert "yellow_max" in prof.guided_thresholds

    def test_default_profile_empty_thresholds(self) -> None:
        from drift.profiles import get_profile

        prof = get_profile("default")
        assert prof.guided_thresholds == {}

    def test_output_language_field(self) -> None:
        from drift.profiles import get_profile

        prof = get_profile("vibe-coding")
        assert prof.output_language == "de"


# ===========================================================================
# First-run render mode
# ===========================================================================


class TestFirstRunRenderMode:
    def test_first_run_skips_module_table_and_shows_next_steps(self) -> None:
        from io import StringIO

        from rich.console import Console

        from drift.models import Severity
        from drift.output.rich_output import render_full_report

        finding = _FakeFinding(
            signal_type="pattern_fragmentation",
            file_path=Path("src/app/service.py"),
            start_line=10,
        )
        analysis = _FakeAnalysis(drift_score=0.4, findings=[finding])
        # Add minimal attributes expected by render_summary
        analysis.severity = Severity.MEDIUM  # type: ignore[attr-defined]
        analysis.grade = ("C", "medium")  # type: ignore[attr-defined]
        analysis.trend = None  # type: ignore[attr-defined]
        analysis.total_files = 10  # type: ignore[attr-defined]
        analysis.total_functions = 50  # type: ignore[attr-defined]
        analysis.ai_attributed_ratio = 0.0  # type: ignore[attr-defined]
        analysis.ai_tools_detected = []  # type: ignore[attr-defined]
        analysis.suppressed_count = 0  # type: ignore[attr-defined]
        analysis.context_tagged_count = 0  # type: ignore[attr-defined]
        analysis.analysis_duration_seconds = 1.0  # type: ignore[attr-defined]
        analysis.phase_timings = {}  # type: ignore[attr-defined]
        analysis.is_degraded = False  # type: ignore[attr-defined]
        analysis.degradation_causes = []  # type: ignore[attr-defined]
        analysis.degradation_components = []  # type: ignore[attr-defined]
        analysis.repo_path = Path(".")  # type: ignore[attr-defined]
        analysis.module_scores = []  # type: ignore[attr-defined]
        analysis.skipped_languages = {}  # type: ignore[attr-defined]

        buf = StringIO()
        console = Console(file=buf, force_terminal=True, width=120)

        render_full_report(analysis, console, first_run=True, language="en")
        output = buf.getvalue()

        # Next-Steps panel must be present
        assert "Next Steps" in output or "drift setup" in output
        # Module table must NOT be present
        assert "Module Drift Ranking" not in output
