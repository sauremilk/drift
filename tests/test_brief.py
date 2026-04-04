"""Tests for drift brief — pre-task structural briefing."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from drift.api import brief as api_brief
from drift.commands.brief import brief as brief_cmd
from drift.guardrails import (
    Guardrail,
    guardrails_to_prompt_block,
)


def _make_runner() -> CliRunner:
    """Create a CliRunner compatible with older/newer Click versions."""
    try:
        return CliRunner(mix_stderr=False)
    except TypeError:
        return CliRunner()


def _parse_json_from_output(output: str) -> dict:
    """Parse JSON payload even when noisy prelude text is present."""
    start = output.find("{")
    end = output.rfind("}")
    assert start != -1 and end != -1 and end >= start, output
    return json.loads(output[start : end + 1])

# ---------------------------------------------------------------------------
# API-layer tests
# ---------------------------------------------------------------------------


class TestApiBrief:
    def test_returns_dict_with_required_keys(self, tmp_repo: Path) -> None:
        result = api_brief(tmp_repo, task="refactor the services layer")
        assert isinstance(result, dict)
        for key in ("schema_version", "type", "task", "scope", "risk",
                     "landscape", "guardrails", "guardrails_prompt_block"):
            assert key in result, f"Missing key: {key}"

    def test_type_is_brief(self, tmp_repo: Path) -> None:
        result = api_brief(tmp_repo, task="anything")
        assert result["type"] == "brief"

    def test_task_echoed_back(self, tmp_repo: Path) -> None:
        result = api_brief(tmp_repo, task="add caching to api")
        assert result["task"] == "add caching to api"

    def test_scope_has_resolution_fields(self, tmp_repo: Path) -> None:
        result = api_brief(tmp_repo, task="update services layer")
        scope = result["scope"]
        for field in ("resolved_paths", "expanded_dependency_paths",
                       "resolution_method", "confidence"):
            assert field in scope, f"Missing scope field: {field}"

    def test_risk_has_level(self, tmp_repo: Path) -> None:
        result = api_brief(tmp_repo, task="update api routes")
        risk = result["risk"]
        assert "level" in risk
        assert risk["level"] in ("LOW", "MEDIUM", "HIGH", "BLOCK")

    def test_guardrails_is_list(self, tmp_repo: Path) -> None:
        result = api_brief(tmp_repo, task="update services")
        assert isinstance(result["guardrails"], list)

    def test_scope_override(self, tmp_repo: Path) -> None:
        result = api_brief(
            tmp_repo,
            task="anything",
            scope_override="services/",
        )
        scope = result["scope"]
        assert scope["resolution_method"] == "manual_override"
        assert scope["confidence"] == 0.95

    def test_max_guardrails_limits_output(self, tmp_repo: Path) -> None:
        result = api_brief(tmp_repo, task="refactor services", max_guardrails=2)
        assert len(result["guardrails"]) <= 2


# ---------------------------------------------------------------------------
# CLI-layer tests
# ---------------------------------------------------------------------------


class TestBriefCli:

    @staticmethod
    def _make_runner() -> CliRunner:
        """Create a CliRunner compatible with both Click 8.1 and 8.2+."""
        kwargs: dict = {}
        if "mix_stderr" in CliRunner.__init__.__code__.co_varnames:
            kwargs["mix_stderr"] = False
        return CliRunner(**kwargs)

    @staticmethod
    def _extract_json(output: str) -> dict:
        """Extract the JSON object from CLI output that may contain stderr."""
        # When mix_stderr is unavailable (Click 8.2+), stderr may precede
        # or follow the JSON payload.  Find the outermost { ... }.
        start = output.find("{")
        end = output.rfind("}")
        if start == -1 or end == -1:
            raise ValueError(f"No JSON object in output: {output!r}")
        return json.loads(output[start : end + 1])

    def test_json_output_is_valid(self, tmp_repo: Path) -> None:
        runner = self._make_runner()
        result = runner.invoke(
            brief_cmd,
            ["--task", "refactor api", "--repo", str(tmp_repo), "--json"],
        )
        # Exit code 0 or 1 (BLOCK) is acceptable
        assert result.exit_code in (0, 1), result.output
        parsed = self._extract_json(result.output)
        assert parsed["type"] == "brief"

    def test_markdown_output(self, tmp_repo: Path) -> None:
        runner = self._make_runner()
        result = runner.invoke(
            brief_cmd,
            ["--task", "update services", "--repo", str(tmp_repo),
             "--format", "markdown"],
        )
        assert result.exit_code in (0, 1), result.output
        assert "# Drift Brief" in result.output or "## " in result.output

    def test_rich_output(self, tmp_repo: Path) -> None:
        runner = self._make_runner()
        result = runner.invoke(
            brief_cmd,
            ["--task", "fix db layer", "--repo", str(tmp_repo)],
        )
        assert result.exit_code in (0, 1), result.output

    def test_task_option_required(self) -> None:
        runner = self._make_runner()
        result = runner.invoke(brief_cmd, ["--repo", "."])
        assert result.exit_code != 0
        combined = result.output + (getattr(result, "stderr", None) or "")
        assert "Missing option" in combined or "required" in combined.lower()

    def test_quiet_flag(self, tmp_repo: Path) -> None:
        """--quiet should suppress the header but still print guardrails."""
        runner = self._make_runner()
        result = runner.invoke(
            brief_cmd,
            ["--task", "update api", "--repo", str(tmp_repo), "--quiet"],
        )
        assert result.exit_code in (0, 1)

    def test_select_signals(self, tmp_repo: Path) -> None:
        runner = self._make_runner()
        result = runner.invoke(
            brief_cmd,
            ["--task", "refactor", "--repo", str(tmp_repo),
             "--json", "--select", "PFS,BEM"],
        )
        assert result.exit_code in (0, 1), result.output
        parsed = self._extract_json(result.output)
        assert "landscape" in parsed


# ---------------------------------------------------------------------------
# Guardrail generation tests
# ---------------------------------------------------------------------------


class TestGuardrails:
    def test_guardrails_to_prompt_block_empty(self) -> None:
        assert guardrails_to_prompt_block([]) == ""

    def test_guardrails_to_prompt_block_contains_constraints(self) -> None:
        gr = Guardrail(
            id="GR-AVS-001",
            signal="AVS",
            constraint_class="ARCHITECTURE",
            severity="HIGH",
            constraint="Do not cross layer boundaries.",
            forbidden="Import db from api",
            reason="Violates layer architecture.",
            affected_files=["api/routes.py"],
            prompt_text="CONSTRAINT [AVS]: Do not cross layer boundaries.",
        )
        block = guardrails_to_prompt_block([gr])
        assert "Structural Constraints" in block
        assert "CONSTRAINT [AVS]" in block

    def test_guardrail_to_dict(self) -> None:
        gr = Guardrail(
            id="GR-PFS-001",
            signal="PFS",
            constraint_class="PATTERN",
            severity="MEDIUM",
            constraint="Use consistent error handling.",
            forbidden="bare except",
            reason="Pattern fragmentation.",
            affected_files=["services/payment_service.py"],
            prompt_text="CONSTRAINT [PFS]: Use consistent error handling.",
        )
        d = gr.to_dict()
        assert d["id"] == "GR-PFS-001"
        assert d["signal"] == "PFS"
        assert isinstance(d["affected_files"], list)


# ---------------------------------------------------------------------------
# Config: BriefConfig
# ---------------------------------------------------------------------------


class TestBriefConfig:
    def test_default_brief_config(self) -> None:
        from drift.config import DriftConfig

        cfg = DriftConfig()
        assert hasattr(cfg, "brief")
        assert cfg.brief.scope_aliases == {}

    def test_brief_config_from_dict(self) -> None:
        from drift.config import DriftConfig

        cfg = DriftConfig.model_validate({
            "brief": {"scope_aliases": {"billing": "src/billing/"}}
        })
        assert cfg.brief.scope_aliases == {"billing": "src/billing/"}


# ---------------------------------------------------------------------------
# Pre-task signal selection
# ---------------------------------------------------------------------------


class TestPreTaskSignals:
    def test_brief_uses_pre_task_signals_by_default(
        self, tmp_repo: Path,
    ) -> None:
        """Without explicit --signals, brief should still return results."""
        result = api_brief(tmp_repo, task="refactor services layer")
        assert result["type"] == "brief"
        # landscape should have findings from pre-task-relevant signals only
        assert "landscape" in result

    def test_explicit_signals_override_pre_task(
        self, tmp_repo: Path,
    ) -> None:
        """Passing explicit signals should override the pre-task set."""
        result = api_brief(
            tmp_repo,
            task="refactor services layer",
            signals=["PFS"],
        )
        assert result["type"] == "brief"
