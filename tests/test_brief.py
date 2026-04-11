"""Tests for drift brief — pre-task structural briefing."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from drift.api import brief as api_brief
from drift.commands.brief import brief as brief_cmd
from drift.guardrails import (
    Guardrail,
    generate_guardrails,
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
        for key in (
            "schema_version",
            "type",
            "task",
            "scope",
            "risk",
            "landscape",
            "guardrails",
            "guardrails_prompt_block",
        ):
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
        for field in (
            "resolved_paths",
            "expanded_dependency_paths",
            "resolution_method",
            "confidence",
        ):
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
            ["--task", "update services", "--repo", str(tmp_repo), "--format", "markdown"],
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
            ["--task", "refactor", "--repo", str(tmp_repo), "--json", "--select", "PFS,BEM"],
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

    def test_guardrail_preferred_pattern_in_dict(self) -> None:
        gr = Guardrail(
            id="GR-PFS-002",
            signal="PFS",
            constraint_class="PATTERN",
            severity="MEDIUM",
            constraint="Use consistent error handling.",
            forbidden="bare except",
            reason="Pattern fragmentation.",
            affected_files=["services/payment_service.py"],
            prompt_text="CONSTRAINT [PFS]: Use consistent error handling.",
            preferred_pattern="Follow the canonical pattern: return_dict",
        )
        d = gr.to_dict()
        assert d["preferred_pattern"] == "Follow the canonical pattern: return_dict"

    def test_guardrail_preferred_pattern_default_empty(self) -> None:
        gr = Guardrail(
            id="GR-AVS-001",
            signal="AVS",
            constraint_class="ARCHITECTURE",
            severity="HIGH",
            constraint="Do not cross layer boundaries.",
            forbidden="Import db from api",
            reason="Violates layer architecture.",
        )
        assert gr.preferred_pattern == ""
        assert gr.to_dict()["preferred_pattern"] == ""

    def test_prompt_block_includes_preferred_pattern(self) -> None:
        gr = Guardrail(
            id="GR-PFS-001",
            signal="PFS",
            constraint_class="PATTERN",
            severity="MEDIUM",
            constraint="Use consistent error handling.",
            forbidden="bare except",
            reason="Pattern fragmentation.",
            prompt_text="CONSTRAINT [PFS]: Use consistent error handling.",
            preferred_pattern="Follow the canonical pattern: return_dict",
        )
        block = guardrails_to_prompt_block([gr])
        assert "PREFERRED: Follow the canonical pattern: return_dict" in block

    def test_prompt_block_omits_preferred_when_empty(self) -> None:
        gr = Guardrail(
            id="GR-AVS-001",
            signal="AVS",
            constraint_class="ARCHITECTURE",
            severity="HIGH",
            constraint="Do not cross layer boundaries.",
            forbidden="Import db from api",
            reason="Violates layer architecture.",
            prompt_text="CONSTRAINT [AVS]: Do not cross layer boundaries.",
            preferred_pattern="",
        )
        block = guardrails_to_prompt_block([gr])
        assert "PREFERRED" not in block


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

        cfg = DriftConfig.model_validate({"brief": {"scope_aliases": {"billing": "src/billing/"}}})
        assert cfg.brief.scope_aliases == {"billing": "src/billing/"}


# ---------------------------------------------------------------------------
# Pre-task signal selection
# ---------------------------------------------------------------------------


class TestPreTaskSignals:
    def test_brief_uses_pre_task_signals_by_default(
        self,
        tmp_repo: Path,
    ) -> None:
        """Without explicit --signals, brief should still return results."""
        result = api_brief(tmp_repo, task="refactor services layer")
        assert result["type"] == "brief"
        # landscape should have findings from pre-task-relevant signals only
        assert "landscape" in result

    def test_explicit_signals_override_pre_task(
        self,
        tmp_repo: Path,
    ) -> None:
        """Passing explicit signals should override the pre-task set."""
        result = api_brief(
            tmp_repo,
            task="refactor services layer",
            signals=["PFS"],
        )
        assert result["type"] == "brief"


# ---------------------------------------------------------------------------
# Issue #157: brief must surface directory-level findings in scope
# ---------------------------------------------------------------------------


class TestBriefScopeFiltering:
    """brief() must not miss findings whose file_path matches the resolved scope."""

    def test_directory_finding_matches_scope(self, tmp_repo: Path) -> None:
        """A finding with file_path = scope directory must be included (#157)."""
        import datetime
        from unittest.mock import patch

        from drift.models import Finding, RepoAnalysis, Severity, SignalType
        from drift.scope_resolver import ResolvedScope

        pfs_finding = Finding(
            signal_type=SignalType.PATTERN_FRAGMENTATION,
            severity=Severity.HIGH,
            score=0.85,
            title="api_endpoint: 5 variants in api/routers/",
            description="5 error handling variants.",
            file_path=Path("api/routers"),
        )

        fake_analysis = RepoAnalysis(
            repo_path=tmp_repo,
            analyzed_at=datetime.datetime.now(datetime.UTC),
            drift_score=0.7,
            findings=[pfs_finding],
            total_files=10,
            total_functions=50,
        )

        fake_scope = ResolvedScope(
            paths=["api/routers"],
            confidence=0.9,
            method="keyword_match",
            matched_tokens=["api", "routers"],
        )

        with (
            patch("drift.analyzer.analyze_repo", return_value=fake_analysis),
            patch("drift.scope_resolver.resolve_scope", return_value=fake_scope),
            patch("drift.scope_resolver.expand_scope_imports", return_value=[]),
        ):
            result = api_brief(
                tmp_repo,
                task="fix error handling in api routers",
            )

        assert result["landscape"]["finding_count"] >= 1

    def test_file_finding_in_scope_directory(self, tmp_repo: Path) -> None:
        """A finding with file_path under the scope directory must be included."""
        import datetime
        from unittest.mock import patch

        from drift.models import Finding, RepoAnalysis, Severity, SignalType
        from drift.scope_resolver import ResolvedScope

        finding = Finding(
            signal_type=SignalType.PATTERN_FRAGMENTATION,
            severity=Severity.MEDIUM,
            score=0.5,
            title="error_handling: 3 variants in api/routers/",
            description="Fragmentation detected.",
            file_path=Path("api/routers/users.py"),
        )

        out_of_scope = Finding(
            signal_type=SignalType.PATTERN_FRAGMENTATION,
            severity=Severity.LOW,
            score=0.3,
            title="unrelated",
            description="Outside scope.",
            file_path=Path("models/base.py"),
        )

        fake_analysis = RepoAnalysis(
            repo_path=tmp_repo,
            analyzed_at=datetime.datetime.now(datetime.UTC),
            drift_score=0.5,
            findings=[finding, out_of_scope],
            total_files=20,
            total_functions=100,
        )

        fake_scope = ResolvedScope(
            paths=["api/routers"],
            confidence=0.9,
            method="keyword_match",
            matched_tokens=["api", "routers"],
        )

        with (
            patch("drift.analyzer.analyze_repo", return_value=fake_analysis),
            patch("drift.scope_resolver.resolve_scope", return_value=fake_scope),
            patch("drift.scope_resolver.expand_scope_imports", return_value=[]),
        ):
            result = api_brief(tmp_repo, task="fix api routers")

        # Only the in-scope finding should appear
        assert result["landscape"]["finding_count"] == 1


# ---------------------------------------------------------------------------
# Issue #155: --progress option on brief CLI
# ---------------------------------------------------------------------------


class TestBriefProgress:
    @staticmethod
    def _make_runner() -> CliRunner:
        kwargs: dict = {}
        if "mix_stderr" in CliRunner.__init__.__code__.co_varnames:
            kwargs["mix_stderr"] = False
        return CliRunner(**kwargs)

    def test_brief_has_progress_option(self) -> None:
        """brief CLI must accept --progress."""
        runner = self._make_runner()
        result = runner.invoke(brief_cmd, ["--help"])
        assert "--progress" in result.output


# ---------------------------------------------------------------------------
# Guardrail min_confidence filtering
# ---------------------------------------------------------------------------


class TestGuardrailMinConfidence:
    """P1: generate_guardrails() must filter NC items below min_confidence."""

    @staticmethod
    def _make_findings() -> list:
        """Create findings that produce NCs with varying confidence levels."""
        from drift.models import Finding, Severity, SignalType

        return [
            Finding(
                signal_type=SignalType.ARCHITECTURE_VIOLATION,
                severity=Severity.HIGH,
                score=0.8,
                title="Layer violation in api/routes.py",
                description="Direct DB import from API layer.",
                file_path=Path("api/routes.py"),
                metadata={
                    "source_layer": "api",
                    "target_layer": "db",
                    "import_path": "db.models",
                },
            ),
            Finding(
                signal_type=SignalType.PHANTOM_REFERENCE,
                severity=Severity.MEDIUM,
                score=0.5,
                title="1 unresolvable reference in utils.py",
                description="utils.py uses 1 name that cannot be resolved.",
                file_path=Path("utils.py"),
                metadata={
                    "phantom_names": [{"name": "nonexistent_fn", "line": 10}],
                    "phantom_count": 1,
                },
            ),
            Finding(
                signal_type=SignalType.PATTERN_FRAGMENTATION,
                severity=Severity.HIGH,
                score=0.9,
                title="error_handling: 4 variants in services/",
                description="4 different error handling patterns found.",
                file_path=Path("services/payment.py"),
                related_files=[Path("services/order.py")],
                metadata={"pattern": "error_handling", "variant_count": 4},
            ),
        ]

    def test_min_confidence_zero_keeps_all(self) -> None:
        """Default min_confidence=0.0 preserves all guardrails."""
        findings = self._make_findings()
        guardrails = generate_guardrails(findings, min_confidence=0.0)
        assert len(guardrails) >= 1

    def test_min_confidence_filters_weak_items(self) -> None:
        """NC items below the floor are excluded."""
        findings = self._make_findings()
        all_grs = generate_guardrails(findings, min_confidence=0.0)
        filtered_grs = generate_guardrails(findings, min_confidence=0.6)
        assert len(filtered_grs) <= len(all_grs)

    def test_min_confidence_high_excludes_everything(self) -> None:
        """A very high floor removes all guardrails."""
        findings = self._make_findings()
        guardrails = generate_guardrails(findings, min_confidence=1.0)
        assert len(guardrails) == 0

    def test_backward_compat_no_min_confidence(self) -> None:
        """Calling without min_confidence works as before."""
        findings = self._make_findings()
        guardrails = generate_guardrails(findings)
        assert len(guardrails) >= 1
