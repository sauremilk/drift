"""Tests for AI tool indicator detection, indicator boost, and enhanced
commit attribution heuristics.

Covers:
- detect_ai_tool_indicators: file-based AI tool detection
- indicator_boost_for_tools: boost value mapping
- _detect_ai_attribution with indicator_boost: boosted confidence tiers
- manual_ratio override via PolicyConfig.ai_attribution
- Integration: mock repo with AI tool files + conventional commits
"""

from __future__ import annotations

import datetime
from pathlib import Path

import pytest

from drift.ingestion.git_history import (
    _detect_ai_attribution,
    detect_ai_tool_indicators,
    indicator_boost_for_tools,
)
from drift.models import CommitInfo

# ── detect_ai_tool_indicators ─────────────────────────────────────────────


class TestDetectAIToolIndicators:
    """Test file-based AI tool indicator scanning."""

    def test_empty_repo(self, tmp_path: Path) -> None:
        assert detect_ai_tool_indicators(tmp_path) == []

    def test_claude_directory(self, tmp_path: Path) -> None:
        (tmp_path / ".claude").mkdir()
        assert detect_ai_tool_indicators(tmp_path) == ["claude"]

    def test_claude_md(self, tmp_path: Path) -> None:
        (tmp_path / "CLAUDE.md").write_text("# Claude config")
        assert detect_ai_tool_indicators(tmp_path) == ["claude"]

    def test_agents_md(self, tmp_path: Path) -> None:
        (tmp_path / "AGENTS.md").write_text("# Agent config")
        assert detect_ai_tool_indicators(tmp_path) == ["agents"]

    def test_claudeignore(self, tmp_path: Path) -> None:
        (tmp_path / ".claudeignore").write_text("")
        assert detect_ai_tool_indicators(tmp_path) == ["claude"]

    def test_copilot_indicators(self, tmp_path: Path) -> None:
        (tmp_path / ".copilotignore").write_text("")
        assert detect_ai_tool_indicators(tmp_path) == ["copilot"]

    def test_copilot_instructions(self, tmp_path: Path) -> None:
        gh_dir = tmp_path / ".github"
        gh_dir.mkdir()
        (gh_dir / "copilot-instructions.md").write_text("# Copilot")
        assert detect_ai_tool_indicators(tmp_path) == ["copilot"]

    def test_cursor_directory(self, tmp_path: Path) -> None:
        (tmp_path / ".cursor").mkdir()
        assert detect_ai_tool_indicators(tmp_path) == ["cursor"]

    def test_cursorrules(self, tmp_path: Path) -> None:
        (tmp_path / ".cursorrules").write_text("")
        assert detect_ai_tool_indicators(tmp_path) == ["cursor"]

    def test_aider_directory(self, tmp_path: Path) -> None:
        (tmp_path / ".aider").mkdir()
        assert detect_ai_tool_indicators(tmp_path) == ["aider"]

    def test_aider_config(self, tmp_path: Path) -> None:
        (tmp_path / ".aider.conf.yml").write_text("")
        assert detect_ai_tool_indicators(tmp_path) == ["aider"]

    def test_cline_directory(self, tmp_path: Path) -> None:
        (tmp_path / ".cline").mkdir()
        assert detect_ai_tool_indicators(tmp_path) == ["cline"]

    def test_cline_docs(self, tmp_path: Path) -> None:
        (tmp_path / "cline_docs").mkdir()
        assert detect_ai_tool_indicators(tmp_path) == ["cline"]

    def test_windsurf(self, tmp_path: Path) -> None:
        (tmp_path / ".windsurf").mkdir()
        assert detect_ai_tool_indicators(tmp_path) == ["windsurf"]

    def test_codeium(self, tmp_path: Path) -> None:
        (tmp_path / ".codeium").mkdir()
        assert detect_ai_tool_indicators(tmp_path) == ["codeium"]

    def test_amazon_q(self, tmp_path: Path) -> None:
        (tmp_path / ".amazon-q").mkdir()
        assert detect_ai_tool_indicators(tmp_path) == ["amazon-q"]

    def test_continue_dir(self, tmp_path: Path) -> None:
        (tmp_path / ".continue").mkdir()
        assert detect_ai_tool_indicators(tmp_path) == ["continue"]

    def test_multiple_tools_sorted(self, tmp_path: Path) -> None:
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".copilotignore").write_text("")
        result = detect_ai_tool_indicators(tmp_path)
        assert result == ["claude", "copilot"]

    def test_three_tools(self, tmp_path: Path) -> None:
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".copilotignore").write_text("")
        (tmp_path / ".cursor").mkdir()
        result = detect_ai_tool_indicators(tmp_path)
        assert result == ["claude", "copilot", "cursor"]

    def test_deduplication(self, tmp_path: Path) -> None:
        """Multiple indicators for same tool → single entry."""
        (tmp_path / ".claude").mkdir()
        (tmp_path / "CLAUDE.md").write_text("# Claude")
        (tmp_path / ".claudeignore").write_text("")
        result = detect_ai_tool_indicators(tmp_path)
        assert result == ["claude"]

    def test_four_tools(self, tmp_path: Path) -> None:
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".copilotignore").write_text("")
        (tmp_path / ".cursor").mkdir()
        (tmp_path / ".aider").mkdir()
        result = detect_ai_tool_indicators(tmp_path)
        assert len(result) == 4


# ── indicator_boost_for_tools ─────────────────────────────────────────────


class TestIndicatorBoost:
    def test_zero_tools(self) -> None:
        assert indicator_boost_for_tools([]) == 0.0

    def test_one_tool(self) -> None:
        assert indicator_boost_for_tools(["copilot"]) == 0.10

    def test_two_tools(self) -> None:
        assert indicator_boost_for_tools(["copilot", "claude"]) == 0.15

    def test_three_tools(self) -> None:
        assert indicator_boost_for_tools(["copilot", "claude", "cursor"]) == 0.20

    def test_four_tools(self) -> None:
        assert indicator_boost_for_tools(["copilot", "claude", "cursor", "aider"]) == 0.20


# ── _detect_ai_attribution with indicator_boost ───────────────────────────


class TestDetectAIAttributionWithBoost:
    """Test enhanced _detect_ai_attribution with indicator_boost parameter."""

    # Co-author signal: boost has NO effect (co-author is always 0.95)
    def test_coauthor_unaffected_by_boost(self) -> None:
        is_ai, conf = _detect_ai_attribution(
            "Add feature",
            ["GitHub Copilot"],
            indicator_boost=0.20,
        )
        assert is_ai is True
        assert conf == pytest.approx(0.95)

    # Tier 1 without boost: unchanged behavior (0.40)
    def test_tier1_no_boost(self) -> None:
        is_ai, conf = _detect_ai_attribution(
            "Implement user auth handler",
            [],
            indicator_boost=0.0,
        )
        assert is_ai is True
        assert conf == pytest.approx(0.40)

    # Tier 1 with boost: 0.40 + 0.20 = 0.60
    def test_tier1_with_boost(self) -> None:
        is_ai, conf = _detect_ai_attribution(
            "Implement user auth handler",
            [],
            indicator_boost=0.20,
        )
        assert is_ai is True
        assert conf == pytest.approx(0.60)

    # Tier 1 with boost: 0.40 + 0.10 = 0.50
    def test_tier1_with_single_tool_boost(self) -> None:
        is_ai, conf = _detect_ai_attribution(
            "Implement user auth handler",
            [],
            indicator_boost=0.10,
        )
        assert is_ai is True
        assert conf == pytest.approx(0.50)

    # Conventional commit without boost: no effect (skipped entirely)
    def test_conventional_commit_no_boost(self) -> None:
        is_ai, conf = _detect_ai_attribution(
            "feat(ui): add dark mode toggle",
            [],
            indicator_boost=0.0,
        )
        assert is_ai is False
        assert conf == 0.0

    # Conventional commit with 1 tool boost: 0.40 + 0.10 = 0.50
    def test_conventional_commit_one_tool(self) -> None:
        is_ai, conf = _detect_ai_attribution(
            "feat(ui): add dark mode toggle",
            [],
            indicator_boost=0.10,
        )
        assert is_ai is True
        assert conf == pytest.approx(0.50)

    # Conventional commit with 3+ tools boost: 0.40 + 0.20 = 0.60
    def test_conventional_commit_three_tools(self) -> None:
        is_ai, conf = _detect_ai_attribution(
            "feat(ui): add dark mode toggle",
            [],
            indicator_boost=0.20,
        )
        assert is_ai is True
        assert conf == pytest.approx(0.60)

    # Conventional fix: pattern
    def test_conventional_fix(self) -> None:
        is_ai, conf = _detect_ai_attribution(
            "fix(backend): resolve null pointer",
            [],
            indicator_boost=0.15,
        )
        assert is_ai is True
        assert conf == pytest.approx(0.55)

    # Conventional refactor:
    def test_conventional_refactor(self) -> None:
        is_ai, conf = _detect_ai_attribution(
            "refactor: extract validation logic",
            [],
            indicator_boost=0.20,
        )
        assert is_ai is True
        assert conf == pytest.approx(0.60)

    # Conventional commit with body → NOT matched (body disqualifies)
    def test_conventional_with_body_not_matched(self) -> None:
        msg = "feat(ui): add dark mode toggle\n\nAdded toggle for dark mode."
        is_ai, conf = _detect_ai_attribution(msg, [], indicator_boost=0.20)
        assert is_ai is False
        assert conf == 0.0

    # Tier 2 with boost: 0.15 + 0.20 = 0.35
    def test_tier2_with_boost(self) -> None:
        is_ai, conf = _detect_ai_attribution(
            "Add user tests",
            [],
            indicator_boost=0.20,
        )
        # Tier 2 never sets is_ai=True (always False from base logic)
        assert is_ai is False
        assert conf == pytest.approx(0.35)

    # Tier 2 without boost: unchanged (0.15)
    def test_tier2_no_boost(self) -> None:
        is_ai, conf = _detect_ai_attribution(
            "Add user tests",
            [],
            indicator_boost=0.0,
        )
        assert is_ai is False
        assert conf == pytest.approx(0.15)

    # Boost cap: confidence should never exceed 0.95
    def test_boost_cap_at_095(self) -> None:
        # Tier 1 (0.40) + extreme boost (0.80) → capped at 0.95
        _is_ai, conf = _detect_ai_attribution(
            "Implement user auth handler",
            [],
            indicator_boost=0.80,
        )
        assert conf == pytest.approx(0.95)
        assert conf <= 0.95

    # No pattern + boost: still 0.0 (bare messages don't get boosted)
    def test_no_pattern_no_signal(self) -> None:
        is_ai, conf = _detect_ai_attribution(
            "did some stuff",
            [],
            indicator_boost=0.20,
        )
        assert is_ai is False
        assert conf == 0.0

    # WIP message: no match
    def test_wip_message_no_match(self) -> None:
        is_ai, conf = _detect_ai_attribution(
            "wip: auto-save 2026-02-27 00:01",
            [],
            indicator_boost=0.20,
        )
        assert is_ai is False
        assert conf == 0.0


# ── manual_ratio config ──────────────────────────────────────────────────


class TestManualRatioConfig:
    def test_manual_ratio_in_policy(self) -> None:
        from drift.config import PolicyConfig

        policy = PolicyConfig(ai_attribution={"manual_ratio": 0.9})
        assert policy.ai_attribution["manual_ratio"] == 0.9

    def test_manual_ratio_absent_by_default(self) -> None:
        from drift.config import PolicyConfig

        policy = PolicyConfig()
        assert policy.ai_attribution.get("manual_ratio") is None

    def test_manual_ratio_in_full_config(self) -> None:
        import yaml

        from drift.config import DriftConfig

        raw = yaml.safe_load("""
policies:
  ai_attribution:
    manual_ratio: 0.85
""")
        config = DriftConfig.model_validate(raw)
        assert config.policies.ai_attribution["manual_ratio"] == 0.85


# ── Integration: RepoAnalysis with ai_tools_detected ─────────────────────


class TestRepoAnalysisAITools:
    def test_ai_tools_detected_default_empty(self) -> None:
        from drift.models import RepoAnalysis

        analysis = RepoAnalysis(
            repo_path=Path("/tmp/test"),
            analyzed_at=datetime.datetime.now(tz=datetime.UTC),
            drift_score=0.0,
        )
        assert analysis.ai_tools_detected == []

    def test_ai_tools_detected_set(self) -> None:
        from drift.models import RepoAnalysis

        analysis = RepoAnalysis(
            repo_path=Path("/tmp/test"),
            analyzed_at=datetime.datetime.now(tz=datetime.UTC),
            drift_score=0.0,
            ai_tools_detected=["claude", "copilot"],
        )
        assert analysis.ai_tools_detected == ["claude", "copilot"]


# ── Integration: ResultAssemblyPhase with manual_ratio ────────────────────


class TestResultAssemblyManualRatio:
    def test_manual_ratio_overrides_computed(self) -> None:
        """When manual_ratio is configured, it replaces the commit-based ratio."""
        import time

        from drift.config import DriftConfig
        from drift.pipeline import (
            DegradationInfo,
            ParsedInputs,
            PipelineArtifacts,
            ResultAssemblyPhase,
            ScoredFindings,
            SignalOutput,
        )

        config = DriftConfig.model_validate(
            {
                "policies": {"ai_attribution": {"manual_ratio": 0.95}},
            }
        )

        # Create minimal artifacts with 0 ai commits
        parsed = ParsedInputs(
            parse_results=[],
            commits=[],
            file_histories={},
            ai_tools_detected=["claude", "copilot"],
        )
        scored = ScoredFindings(
            findings=[],
            repo_score=0.0,
            module_scores=[],
            suppressed_count=0,
            context_tagged_count=0,
        )
        artifacts = PipelineArtifacts(
            parsed=parsed,
            signaled=SignalOutput(findings=[]),
            scored=scored,
            degradation=DegradationInfo(causes=set(), components=set(), events=[]),
        )

        assembly = ResultAssemblyPhase()
        result = assembly.run(
            Path("/tmp/test"),
            [],
            artifacts,
            started_at=time.monotonic(),
            config=config,
        )

        assert result.ai_attributed_ratio == 0.95
        assert result.ai_tools_detected == ["claude", "copilot"]

    def test_no_manual_ratio_uses_computed(self) -> None:
        """Without manual_ratio, the commit-based ratio is used."""
        import time

        from drift.config import DriftConfig
        from drift.pipeline import (
            DegradationInfo,
            ParsedInputs,
            PipelineArtifacts,
            ResultAssemblyPhase,
            ScoredFindings,
            SignalOutput,
        )

        config = DriftConfig()

        commit_ai = CommitInfo(
            hash="abc123",
            author="dev",
            email="dev@test.com",
            timestamp=datetime.datetime.now(tz=datetime.UTC),
            message="feat: add feature",
            files_changed=["f.py"],
            is_ai_attributed=True,
            ai_confidence=0.60,
        )
        commit_human = CommitInfo(
            hash="def456",
            author="dev",
            email="dev@test.com",
            timestamp=datetime.datetime.now(tz=datetime.UTC),
            message="update readme",
            files_changed=["README.md"],
            is_ai_attributed=False,
            ai_confidence=0.0,
        )

        parsed = ParsedInputs(
            parse_results=[],
            commits=[commit_ai, commit_human],
            file_histories={},
            ai_tools_detected=["copilot"],
        )
        scored = ScoredFindings(
            findings=[],
            repo_score=0.0,
            module_scores=[],
            suppressed_count=0,
            context_tagged_count=0,
        )
        artifacts = PipelineArtifacts(
            parsed=parsed,
            signaled=SignalOutput(findings=[]),
            scored=scored,
            degradation=DegradationInfo(causes=set(), components=set(), events=[]),
        )

        assembly = ResultAssemblyPhase()
        result = assembly.run(
            Path("/tmp/test"),
            [],
            artifacts,
            started_at=time.monotonic(),
            config=config,
        )

        # 1 of 2 commits is AI → 0.5
        assert result.ai_attributed_ratio == 0.5
        assert result.ai_tools_detected == ["copilot"]


# ── JSON output includes ai_tools_detected ────────────────────────────────


class TestJSONOutputAITools:
    def test_json_contains_ai_tools(self) -> None:
        import json

        from drift.models import RepoAnalysis
        from drift.output.json_output import analysis_to_json

        analysis = RepoAnalysis(
            repo_path=Path("/tmp/test"),
            analyzed_at=datetime.datetime.now(tz=datetime.UTC),
            drift_score=0.25,
            ai_tools_detected=["claude", "copilot"],
        )
        raw = analysis_to_json(analysis)
        data = json.loads(raw)
        assert data["summary"]["ai_tools_detected"] == ["claude", "copilot"]

    def test_json_empty_ai_tools(self) -> None:
        import json

        from drift.models import RepoAnalysis
        from drift.output.json_output import analysis_to_json

        analysis = RepoAnalysis(
            repo_path=Path("/tmp/test"),
            analyzed_at=datetime.datetime.now(tz=datetime.UTC),
            drift_score=0.25,
        )
        raw = analysis_to_json(analysis)
        data = json.loads(raw)
        assert data["summary"]["ai_tools_detected"] == []
