"""Tests for ADR-070: drift verify — post-edit coherence verification."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

from drift.api.verify import (
    _direction_from_delta,
    _verify_agent_instruction,
    verify,
)

# ---------------------------------------------------------------------------
# Helper: direction from delta
# ---------------------------------------------------------------------------


class TestDirectionFromDelta:
    def test_improving(self) -> None:
        assert _direction_from_delta(-0.05) == "improving"

    def test_degrading(self) -> None:
        assert _direction_from_delta(0.05) == "degrading"

    def test_stable_zero(self) -> None:
        assert _direction_from_delta(0.0) == "stable"

    def test_stable_near_zero(self) -> None:
        assert _direction_from_delta(0.0005) == "stable"
        assert _direction_from_delta(-0.0005) == "stable"


# ---------------------------------------------------------------------------
# Agent instruction
# ---------------------------------------------------------------------------


class TestVerifyAgentInstruction:
    def test_pass_instruction(self) -> None:
        instr = _verify_agent_instruction(passed=True, blocking_reasons=[])
        assert "PASSED" in instr
        assert "safe to commit" in instr

    def test_fail_instruction(self) -> None:
        reasons = [{"reason": "Score degraded"}, {"reason": "HIGH finding"}]
        instr = _verify_agent_instruction(passed=False, blocking_reasons=reasons)
        assert "FAILED" in instr
        assert "2 blocking" in instr


# ---------------------------------------------------------------------------
# verify() API — mocked shadow_verify
# ---------------------------------------------------------------------------


class TestVerifyApi:
    """verify() wraps shadow_verify with pass/fail envelope."""

    def _shadow_result(
        self,
        *,
        shadow_clean: bool = True,
        delta: float = 0.0,
        new_findings: list[dict[str, Any]] | None = None,
        resolved_findings: list[dict[str, Any]] | None = None,
        score_after: float = 0.3,
    ) -> dict[str, Any]:
        return {
            "schema_version": "2.2",
            "shadow_clean": shadow_clean,
            "delta": delta,
            "score_after": score_after,
            "new_findings_in_scope": new_findings or [],
            "resolved_findings_in_scope": resolved_findings or [],
            "new_finding_count": len(new_findings or []),
            "resolved_finding_count": len(resolved_findings or []),
            "scope_files": [],
            "scope_file_count": 0,
            "safe_to_merge": shadow_clean and delta <= 0,
            "agent_instruction": "shadow ok",
            "next_tool_call": None,
            "fallback_tool_call": None,
            "done_when": "safe_to_commit == true",
        }

    def _diff_result(
        self,
        *,
        delta: float = 0.0,
        new_findings: list[dict[str, Any]] | None = None,
        resolved_findings: list[dict[str, Any]] | None = None,
        score_before: float = 0.3,
        score_after: float = 0.3,
    ) -> dict[str, Any]:
        return {
            "schema_version": "2.2",
            "type": "diff",
            "delta": delta,
            "score_before": score_before,
            "score_after": score_after,
            "new_findings": new_findings or [],
            "resolved_findings": resolved_findings or [],
            "new_finding_count": len(new_findings or []),
            "resolved_count": len(resolved_findings or []),
        }

    @patch("drift.api.verify._emit_api_telemetry")
    @patch("drift.api.verify.shadow_verify")
    def test_pass_when_clean_and_no_degradation(
        self, mock_sv: Any, mock_telem: Any,
    ) -> None:
        mock_sv.return_value = self._shadow_result(shadow_clean=True, delta=0.0)
        result = verify(path=".")
        assert result["pass"] is True
        assert result["type"] == "verify"
        assert result["blocking_reasons"] == []
        assert result["direction"] == "stable"
        assert result.get("error_code") is None

    @patch("drift.api.verify._emit_api_telemetry")
    @patch("drift.api.verify.shadow_verify")
    def test_fail_on_score_degradation(
        self, mock_sv: Any, mock_telem: Any,
    ) -> None:
        mock_sv.return_value = self._shadow_result(
            shadow_clean=True, delta=0.05, score_after=0.35,
        )
        result = verify(path=".")
        assert result["pass"] is False
        assert any(r["type"] == "score_degradation" for r in result["blocking_reasons"])
        assert result["direction"] == "degrading"

    @patch("drift.api.verify._emit_api_telemetry")
    @patch("drift.api.verify.shadow_verify")
    def test_fail_on_new_high_finding(
        self, mock_sv: Any, mock_telem: Any,
    ) -> None:
        new_finding = {
            "signal": "PFS",
            "severity": "high",
            "title": "Pattern fragmentation detected",
            "file": "src/foo.py",
        }
        mock_sv.return_value = self._shadow_result(
            shadow_clean=False, delta=0.0, new_findings=[new_finding],
        )
        result = verify(path=".", fail_on="high")
        assert result["pass"] is False
        assert len(result["blocking_reasons"]) >= 1
        assert any(
            r["type"] == "finding_above_threshold"
            for r in result["blocking_reasons"]
        )

    @patch("drift.api.verify._emit_api_telemetry")
    @patch("drift.api.verify.shadow_verify")
    def test_pass_when_finding_below_threshold(
        self, mock_sv: Any, mock_telem: Any,
    ) -> None:
        low_finding = {
            "signal": "DIA",
            "severity": "low",
            "title": "Minor issue",
            "file": "src/bar.py",
        }
        mock_sv.return_value = self._shadow_result(
            shadow_clean=False, delta=0.0, new_findings=[low_finding],
        )
        result = verify(path=".", fail_on="high")
        # Low is below high threshold → pass
        assert result["pass"] is True

    @patch("drift.api.verify._emit_api_telemetry")
    @patch("drift.api.verify.shadow_verify")
    def test_fail_on_none_never_blocks(
        self, mock_sv: Any, mock_telem: Any,
    ) -> None:
        critical_finding = {
            "signal": "AVS",
            "severity": "critical",
            "title": "Architecture violation",
            "file": "src/core.py",
        }
        mock_sv.return_value = self._shadow_result(
            shadow_clean=False, delta=0.05, new_findings=[critical_finding],
            score_after=0.5,
        )
        result = verify(path=".", fail_on="none")
        # fail_on=none → only score degradation blocks, findings don't
        # but delta > 0 still blocks
        assert any(
            r["type"] == "score_degradation" for r in result["blocking_reasons"]
        )
        assert result["pass"] is False

    @patch("drift.api.verify._emit_api_telemetry")
    @patch("drift.api.verify.shadow_verify")
    def test_pass_with_improving_score(
        self, mock_sv: Any, mock_telem: Any,
    ) -> None:
        mock_sv.return_value = self._shadow_result(
            shadow_clean=True, delta=-0.02, score_after=0.28,
        )
        result = verify(path=".")
        assert result["pass"] is True
        assert result["direction"] == "improving"
        assert result["score_delta"] == -0.02
        assert result.get("error_code") is None

    @patch("drift.api.verify._emit_api_telemetry")
    @patch("drift.api.verify.shadow_verify")
    def test_next_tool_on_pass(
        self, mock_sv: Any, mock_telem: Any,
    ) -> None:
        mock_sv.return_value = self._shadow_result(shadow_clean=True, delta=0.0)
        result = verify(path=".")
        assert result["next_tool_call"] is None
        assert "safe_to_commit" in result["done_when"]

    @patch("drift.api.verify._emit_api_telemetry")
    @patch("drift.api.verify.shadow_verify")
    def test_next_tool_on_fail(
        self, mock_sv: Any, mock_telem: Any,
    ) -> None:
        mock_sv.return_value = self._shadow_result(
            shadow_clean=True, delta=0.05, score_after=0.35,
        )
        result = verify(path=".")
        assert result["next_tool_call"]["tool"] == "drift_fix_plan"

    @patch("drift.api.verify._emit_api_telemetry")
    @patch("drift.api.verify.shadow_verify")
    def test_error_propagation(
        self, mock_sv: Any, mock_telem: Any,
    ) -> None:
        mock_sv.return_value = {
            "type": "error",
            "error_code": "DRIFT-5001",
            "message": "analysis failed",
        }
        result = verify(path=".")
        assert result["type"] == "error"
        assert result.get("pass") is None

    @patch("drift.api.verify._emit_api_telemetry")
    @patch("drift.api.verify.shadow_verify")
    def test_scope_files_passed_through(
        self, mock_sv: Any, mock_telem: Any,
    ) -> None:
        mock_sv.return_value = self._shadow_result(shadow_clean=True, delta=0.0)
        verify(path=".", scope_files=["src/a.py", "src/b.py"])
        _, kwargs = mock_sv.call_args
        assert kwargs["scope_files"] == ["src/a.py", "src/b.py"]

    @patch("drift.api.verify._emit_api_telemetry")
    @patch("drift.api.verify.diff_api")
    @patch("drift.api.verify.shadow_verify")
    def test_ref_mode_uses_diff_api(
        self, mock_sv: Any, mock_diff: Any, mock_telem: Any,
    ) -> None:
        mock_diff.return_value = self._diff_result(delta=0.0)
        result = verify(path=".", ref="main", uncommitted=False)
        assert result["pass"] is True
        _, kwargs = mock_diff.call_args
        assert kwargs["diff_ref"] == "main"
        assert kwargs["uncommitted"] is False
        assert kwargs["staged_only"] is False
        mock_sv.assert_not_called()

    @patch("drift.api.verify._emit_api_telemetry")
    @patch("drift.api.verify.diff_api")
    @patch("drift.api.verify.shadow_verify")
    def test_baseline_mode_uses_diff_api(
        self, mock_sv: Any, mock_diff: Any, mock_telem: Any,
    ) -> None:
        mock_diff.return_value = self._diff_result(delta=0.0)
        result = verify(path=".", baseline=".drift-baseline.json", uncommitted=False)
        assert result["pass"] is True
        _, kwargs = mock_diff.call_args
        assert kwargs["baseline_file"] == ".drift-baseline.json"
        mock_sv.assert_not_called()

    @patch("drift.api.verify._emit_api_telemetry")
    @patch("drift.api.verify.diff_api")
    @patch("drift.api.verify.shadow_verify")
    def test_staged_only_mode_uses_diff_api(
        self, mock_sv: Any, mock_diff: Any, mock_telem: Any,
    ) -> None:
        mock_diff.return_value = self._diff_result(delta=0.0)
        result = verify(path=".", staged_only=True, uncommitted=False)
        assert result["pass"] is True
        _, kwargs = mock_diff.call_args
        assert kwargs["staged_only"] is True
        assert kwargs["uncommitted"] is False
        mock_sv.assert_not_called()

    @patch("drift.api.verify._emit_api_telemetry")
    def test_invalid_uncommitted_with_staged_only_returns_error(self, mock_telem: Any) -> None:
        result = verify(path=".", staged_only=True, uncommitted=True)
        assert result["type"] == "error"
        assert result["error_code"] == "DRIFT-1012"
        assert result.get("pass") is None

    @patch("drift.api.verify._emit_api_telemetry")
    def test_invalid_ref_with_uncommitted_returns_error(self, mock_telem: Any) -> None:
        result = verify(path=".", ref="main", uncommitted=True)
        assert result["type"] == "error"
        assert result["error_code"] == "DRIFT-1012"
        assert result.get("pass") is None

    @patch("drift.api.verify._emit_api_telemetry")
    def test_invalid_ref_with_baseline_returns_error(self, mock_telem: Any) -> None:
        result = verify(path=".", ref="main", baseline=".drift-baseline.json", uncommitted=False)
        assert result["type"] == "error"
        assert result["error_code"] == "DRIFT-1012"
        assert result.get("pass") is None

    @patch("drift.api.verify._emit_api_telemetry")
    @patch("drift.api.verify.shadow_verify")
    def test_exception_returns_error_response(
        self, mock_sv: Any, mock_telem: Any,
    ) -> None:
        mock_sv.side_effect = RuntimeError("boom")
        result = verify(path=".")
        assert result["type"] == "error"
        assert result.get("pass") is None
        assert "boom" in result["message"]


# ---------------------------------------------------------------------------
# CLI command
# ---------------------------------------------------------------------------


class TestVerifyCommand:
    """drift verify CLI exits correctly."""

    @patch("drift.api.verify.verify")
    def test_cli_pass_exits_zero(self, mock_verify: Any) -> None:
        from click.testing import CliRunner

        from drift.commands.verify import verify as verify_cmd

        mock_verify.return_value = {
            "type": "verify",
            "pass": True,
            "blocking_reasons": [],
            "findings_introduced": [],
            "findings_resolved": [],
            "findings_introduced_count": 0,
            "findings_resolved_count": 0,
            "score_before": 0.3,
            "score_after": 0.3,
            "score_delta": 0.0,
            "direction": "stable",
            "ref": "HEAD",
            "scope_files": [],
            "agent_instruction": "verify PASSED",
        }
        runner = CliRunner()
        result = runner.invoke(verify_cmd, ["--format", "json"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["pass"] is True

    @patch("drift.api.verify.verify")
    def test_cli_fail_exits_one(self, mock_verify: Any) -> None:
        from click.testing import CliRunner

        from drift.commands.verify import verify as verify_cmd

        mock_verify.return_value = {
            "type": "verify",
            "pass": False,
            "blocking_reasons": [{"type": "score_degradation", "reason": "degraded"}],
            "findings_introduced": [],
            "findings_resolved": [],
            "findings_introduced_count": 0,
            "findings_resolved_count": 0,
            "score_before": 0.3,
            "score_after": 0.35,
            "score_delta": 0.05,
            "direction": "degrading",
            "ref": "HEAD",
            "scope_files": [],
            "agent_instruction": "verify FAILED",
        }
        runner = CliRunner()
        result = runner.invoke(verify_cmd, ["--format", "json"])
        assert result.exit_code != 0

    @patch("drift.api.verify.verify")
    def test_cli_exit_zero_flag(self, mock_verify: Any) -> None:
        from click.testing import CliRunner

        from drift.commands.verify import verify as verify_cmd

        mock_verify.return_value = {
            "type": "verify",
            "pass": False,
            "blocking_reasons": [{"type": "score_degradation", "reason": "degraded"}],
            "findings_introduced": [],
            "findings_resolved": [],
            "findings_introduced_count": 0,
            "findings_resolved_count": 0,
            "score_before": 0.3,
            "score_after": 0.35,
            "score_delta": 0.05,
            "direction": "degrading",
            "ref": "HEAD",
            "scope_files": [],
            "agent_instruction": "verify FAILED",
        }
        runner = CliRunner()
        result = runner.invoke(verify_cmd, ["--format", "json", "--exit-zero"])
        assert result.exit_code == 0

