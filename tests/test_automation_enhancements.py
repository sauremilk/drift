"""Tests for automation enhancements layered on top of Pakete 2A/2B/2C.

Scope:
- ``drift baseline status`` tests live in tests/test_baseline_status.py.
- This module verifies the workflow and dedup-script hardening that
  keep CI fast (pip cache), portable (workflow_call) and flood-safe
  (``--max-issues`` + multi-label dedup).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

yaml = pytest.importorskip("yaml")

REPO = Path(__file__).resolve().parent.parent
WORKFLOW = REPO / ".github" / "workflows" / "drift-agent-gate.yml"
DEDUP = REPO / "scripts" / "gh_issue_dedup.py"

# Make scripts/ importable just like tests/test_gh_issue_dedup.py does.
sys.path.insert(0, str(REPO / "scripts"))


def _load_workflow() -> dict:
    raw = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    # Workflow uses ``on:`` which PyYAML 1.1 coerces to True — accept either.
    assert isinstance(raw, dict)
    raw["_triggers"] = raw.get("on") if raw.get("on") is not None else raw.get(True)
    return raw


class TestWorkflowPipCache:
    """Automation boost 2B: pip cache avoids redundant installs per PR."""

    def test_setup_python_enables_pip_cache(self) -> None:
        wf = _load_workflow()
        jobs = wf["jobs"]
        job = next(iter(jobs.values()))
        steps = job.get("steps", [])

        setup_python = next(
            (s for s in steps if str(s.get("uses", "")).startswith("actions/setup-python")),
            None,
        )
        assert setup_python is not None, "setup-python step missing"
        wth = setup_python.get("with") or {}
        assert wth.get("cache") == "pip", f"pip cache not enabled: {wth}"


class TestWorkflowReusable:
    """Automation boost 2B: downstream repos can reuse the gate via workflow_call."""

    def test_workflow_call_trigger_declared(self) -> None:
        wf = _load_workflow()
        triggers = wf["_triggers"]
        assert isinstance(triggers, dict)
        assert "workflow_call" in triggers, f"workflow_call missing: {triggers}"
        inputs = (triggers["workflow_call"] or {}).get("inputs") or {}
        assert "approval-label" in inputs


class TestWorkflowStepSummary:
    """Productivity boost 2B: gate reports into GITHUB_STEP_SUMMARY.

    Posting a PR comment is forbidden by repo policy; the step-summary
    surface is a maintainer-facing artifact that does NOT notify anyone.
    """

    def test_step_summary_write_present(self) -> None:
        raw = WORKFLOW.read_text(encoding="utf-8")
        assert "GITHUB_STEP_SUMMARY" in raw, "step summary integration missing"


# ---------------------------------------------------------------------------
# 2C automation hardening: --max-issues cap + multi-label dedup
# ---------------------------------------------------------------------------


def _run_dedup(args: list[str], *, input_report: dict, cwd: Path) -> subprocess.CompletedProcess:
    report_path = cwd / "report.json"
    report_path.write_text(json.dumps(input_report), encoding="utf-8")
    cmd = [
        sys.executable,
        str(DEDUP),
        "--repo",
        "x/y",
        "--report",
        str(report_path),
        "--dry-run",
        *args,
    ]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )


class TestMaxIssuesCap:
    """Flood guard: ``--max-issues N`` skips findings beyond the cap."""

    def test_default_cap_is_ten(self, tmp_path: Path) -> None:
        # 12 BLOCK findings, default cap 10 -> 2 capped.
        findings = [
            {
                "id": f"f{i}",
                "severity": "high",
                "title": f"t{i}",
                "signal_type": "sig",
                "file_path": f"src/f{i}.py",
                "start_line": i,
            }
            for i in range(12)
        ]
        proc = _run_dedup([], input_report={"findings": findings}, cwd=tmp_path)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert "flood guard" in proc.stdout + proc.stderr
        assert "capped=2" in proc.stdout

    def test_explicit_cap_overrides_default(self, tmp_path: Path) -> None:
        findings = [
            {"id": f"f{i}", "severity": "critical", "title": "t", "signal_type": "s",
             "file_path": "a.py", "start_line": i}
            for i in range(5)
        ]
        proc = _run_dedup(["--max-issues", "2"], input_report={"findings": findings}, cwd=tmp_path)
        assert proc.returncode == 0
        assert "capped=3" in proc.stdout
        assert "filed=2" in proc.stdout


class TestMultiLabelDedup:
    """Dedup must query every configured label, not only the first one."""

    def test_existing_open_issues_queries_each_label(self) -> None:
        import gh_issue_dedup

        calls: list[list[str]] = []

        def fake_run(args: list[str]) -> tuple[int, str]:
            calls.append(list(args))
            issue = {"number": len(calls), "title": "t", "body": "no-marker"}
            return 0, json.dumps([issue])

        with patch.object(gh_issue_dedup, "_run_gh", side_effect=fake_run):
            issues = gh_issue_dedup._existing_open_issues("x/y", "drift,agent-block,critical")

        # Three labels -> three gh invocations.
        label_args = [c[c.index("--label") + 1] for c in calls if "--label" in c]
        assert label_args == ["drift", "agent-block", "critical"]
        # Three unique issue numbers (1,2,3).
        assert {i["number"] for i in issues} == {1, 2, 3}

    def test_multi_label_dedup_skips_duplicates_across_labels(self) -> None:
        import gh_issue_dedup

        # Same issue number returned by two label lookups -> counted once.
        def fake_run(args: list[str]) -> tuple[int, str]:
            return 0, json.dumps([{"number": 42, "title": "t", "body": "b"}])

        with patch.object(gh_issue_dedup, "_run_gh", side_effect=fake_run):
            issues = gh_issue_dedup._existing_open_issues("x/y", "a,b")

        assert len(issues) == 1
        assert issues[0]["number"] == 42
