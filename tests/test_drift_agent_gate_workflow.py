"""Tests for .github/workflows/drift-agent-gate.yml (Paket 2B / ADR-094).

We cannot exercise the GitHub Actions runner from pytest, so we verify:

1. The workflow YAML parses and declares the required trigger/permission
   contract (pull_request + contents:read + pull-requests:read).
2. The workflow references the drift/approved label and invokes
   ``verify_gate_not_bypassed.py`` as the tamper-check step.
3. CODEOWNERS covers the agent-critical paths introduced by ADR-094.
4. ADR-094 exists and is marked as proposed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

REPO = Path(__file__).resolve().parent.parent
WORKFLOW = REPO / ".github" / "workflows" / "drift-agent-gate.yml"
CODEOWNERS = REPO / ".github" / "CODEOWNERS"
ADR = REPO / "decisions" / "ADR-094-human-approval-gate.md"


def _load_workflow() -> dict:
    assert WORKFLOW.exists(), f"missing {WORKFLOW}"
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


class TestWorkflowContract:
    def test_trigger_is_pull_request_on_main(self) -> None:
        wf = _load_workflow()
        # PyYAML turns the top-level ``on`` key into Python True
        # because YAML 1.1 treats it as a boolean; accept either form.
        on = wf.get("on") or wf.get(True)
        assert on is not None, "workflow missing 'on' trigger"
        assert "pull_request" in on
        assert on["pull_request"]["branches"] == ["main"]

    def test_permissions_are_read_only(self) -> None:
        wf = _load_workflow()
        perms = wf["permissions"]
        assert perms["contents"] == "read"
        assert perms["pull-requests"] == "read"

    def test_has_approval_gate_job(self) -> None:
        wf = _load_workflow()
        assert "approval-gate" in wf["jobs"]

    def test_references_approved_label_and_tamper_check(self) -> None:
        raw = WORKFLOW.read_text(encoding="utf-8")
        assert "drift/approved" in raw
        assert "verify_gate_not_bypassed.py" in raw
        # Core gate assertion: BLOCK-triggered exit 1 when unapproved.
        assert "sys.exit(1)" in raw


class TestCodeownersCoverage:
    @pytest.mark.parametrize(
        "path",
        [
            "drift.agent.prompt.md",
            "drift.output.schema.json",
            "drift.schema.json",
            "src/drift/signal_registry.py",
            "src/drift/intent/handoff.py",
            ".github/workflows/drift-agent-gate.yml",
            "scripts/verify_gate_not_bypassed.py",
            "decisions/",
        ],
    )
    def test_agent_critical_path_has_owner(self, path: str) -> None:
        content = CODEOWNERS.read_text(encoding="utf-8")
        assert path in content, f"CODEOWNERS missing agent-critical path: {path}"


class TestAdr094:
    def test_exists_and_marked_proposed(self) -> None:
        assert ADR.exists()
        text = ADR.read_text(encoding="utf-8")
        assert "ADR-094" in text
        assert "proposed" in text.lower()
        assert "drift/approved" in text
