"""Gate integration tests for run_session_end (ADR-079).

Covers the MCP router layer — block path, unblock path, force path, retry
counter. For pure validator-layer tests see ``test_session_handover.py``.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from drift.session import DriftSession, SessionManager


@pytest.fixture(autouse=True)
def _reset_sessions() -> Any:
    SessionManager.reset_instance()
    yield
    SessionManager.reset_instance()


def _run(coro: Any) -> dict[str, Any]:
    return json.loads(asyncio.run(coro))


def _prepare_signal_session(tmp_path: Path) -> DriftSession:
    """Create a session with non-empty state so the gate is active."""
    mgr = SessionManager.instance()
    sid = mgr.create(repo_path=str(tmp_path))
    s = mgr.get(sid)
    assert s is not None
    # Mark the session as having done work so the empty-session carve-out
    # does not apply.
    s.completed_task_ids = ["t-1"]
    s.tool_calls = 10
    s.record_trace(
        tool="drift_scan",
        advisory="fake",
        metadata={"touched_files": ["src/drift/signals/pfs.py"]},
    )
    return s


def _good_frontmatter(session: DriftSession, change_class: str) -> str:
    return (
        "---\n"
        f'session_id: "{session.session_id}"\n'
        'started_at: "2026-04-21T09:15:30Z"\n'
        'ended_at: "2026-04-21T09:47:12Z"\n'
        "duration_seconds: 1902\n"
        "tool_calls: 42\n"
        "tasks_completed: 1\n"
        "tasks_remaining: 0\n"
        "findings_delta: -1\n"
        f'change_class: "{change_class}"\n'
        f'repo_path: "{session.repo_path}"\n'
        'git_head_at_plan: "a1b2c3d4"\n'
        'git_head_at_end: "e5f6a7b8"\n'
        "adr_refs: []\n"
        "evidence_files: []\n"
        "audit_artifacts_updated: []\n"
        "---\n"
    )


def _good_sections() -> str:
    return (
        "\n## Scope\n\n"
        "Session fuegte einen neuen Signal-Detektor hinzu und aktualisierte "
        "die Audit-Matrix. Nicht beruehrt: Ingestion-Parser.\n\n"
        "## Ergebnisse\n\n"
        "Neues Signal implementiert, 42 Tests gruen, Precision 0.9.\n\n"
        "## Offene Enden\n\n"
        "Keine offenen Enden; alle Audit-Artefakte aktualisiert.\n\n"
        "## Next-Agent-Einstieg\n\n"
        "1. Release vorbereiten.\n"
        "2. Signal in README dokumentieren.\n"
        "3. Abnahme: make check gruen.\n\n"
        "## Evidenz\n\n"
        "- Evidence: benchmark_results/v2.25.0_session_handover_gate_feature_evidence.json\n"
        "- ADR: decisions/ADR-079-session-handover-artifact-gate.md\n"
        "- Audit: audit_results/risk_register.md\n"
    )


def _write_session_md(
    repo: Path, session: DriftSession, change_class: str = "signal"
) -> Path:
    path = repo / "work_artifacts" / f"session_{session.session_id[:8]}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        _good_frontmatter(session, change_class) + _good_sections(),
        encoding="utf-8",
    )
    return path


def _write_evidence(repo: Path) -> Path:
    evidence = repo / "benchmark_results" / "v2.25.0_gate_feature_evidence.json"
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text(
        json.dumps(
            {
                "version": "2.25.0",
                "feature": "session_handover_gate",
                "description": "ADR-079 gate enforces handover artifacts.",
                "tests": {"unit": 25, "integration": 3},
                "audit_artifacts_updated": [
                    "audit_results/fmea_matrix.md",
                    "audit_results/risk_register.md",
                ],
            }
        ),
        encoding="utf-8",
    )
    return evidence


def _write_adr(repo: Path) -> Path:
    adr = repo / "decisions" / "ADR-999-test-adr.md"
    adr.parent.mkdir(parents=True, exist_ok=True)
    adr.write_text(
        "---\n"
        "id: ADR-999\n"
        "status: proposed\n"
        "---\n\n"
        "# ADR-999\n\n"
        "## Kontext\n\n"
        "Die Session-Handover-Gate entsteht, weil Agenten Pflichten "
        "umgehen koennen. Ohne Evidenz bleiben Architekturaenderungen "
        "nachtraeglich nicht nachvollziehbar. Ziel ist ein harter Gate.\n\n"
        "## Alternativen\n\n"
        "1. Alternative A: reine Dokumentation ohne Pruefung.\n"
        "2. Alternative B: weicher Reminder statt Gate.\n\n"
        "## Entscheidung\n\n"
        "Wir fuehren einen harten Gate ein mit L1 Existenz, L2 Schema, "
        "L3 Placeholder-Denylist und optionalem L4 LLM-Review.\n\n"
        "## Konsequenzen\n\n"
        "Sessions ohne Artefakte werden blockiert; force=true bleibt als "
        "auditierter Notausgang.\n",
        encoding="utf-8",
    )
    return adr


class TestSessionEndGate:
    """drift_session_end should enforce ADR-079 handover artifacts."""

    def test_blocks_when_artifacts_missing(self, tmp_path: Path) -> None:
        import drift.mcp_server as mcp_server

        session = _prepare_signal_session(tmp_path)

        resp = _run(mcp_server.drift_session_end(session_id=session.session_id))
        assert resp["status"] == "blocked"
        assert resp["error_code"] == "DRIFT-6100"
        kinds = {m["kind"] for m in resp["missing_artifacts"]}
        assert "session_md" in kinds
        # Session is still alive for retry.
        assert SessionManager.instance().get(session.session_id) is not None

    def test_unblocks_when_all_artifacts_valid(self, tmp_path: Path) -> None:
        import drift.mcp_server as mcp_server

        session = _prepare_signal_session(tmp_path)
        md = _write_session_md(tmp_path, session, change_class="signal")
        evidence = _write_evidence(tmp_path)
        adr = _write_adr(tmp_path)

        resp = _run(
            mcp_server.drift_session_end(
                session_id=session.session_id,
                session_md_path=str(md),
                evidence_path=str(evidence),
                adr_path=str(adr),
            )
        )
        assert resp["status"] == "ok"
        assert resp.get("handover_gate", {}).get("ok") is True
        assert SessionManager.instance().get(session.session_id) is None

    def test_force_requires_valid_bypass_reason(self, tmp_path: Path) -> None:
        import drift.mcp_server as mcp_server

        session = _prepare_signal_session(tmp_path)

        resp = _run(
            mcp_server.drift_session_end(
                session_id=session.session_id,
                force=True,
                bypass_reason="short",
            )
        )
        assert resp["status"] == "blocked"
        assert resp["error_code"] == "DRIFT-6101"
        # Session not destroyed.
        assert SessionManager.instance().get(session.session_id) is not None

    def test_force_with_placeholder_reason_blocks(self, tmp_path: Path) -> None:
        import drift.mcp_server as mcp_server

        session = _prepare_signal_session(tmp_path)

        resp = _run(
            mcp_server.drift_session_end(
                session_id=session.session_id,
                force=True,
                bypass_reason=(
                    "TODO wird spaeter ergaenzt weil Zeitdruck in Pipeline "
                    "besteht und dokumentation fehlt"
                ),
            )
        )
        assert resp["status"] == "blocked"
        assert resp["error_code"] == "DRIFT-6101"

    def test_force_with_valid_reason_unblocks(self, tmp_path: Path) -> None:
        import drift.mcp_server as mcp_server

        session = _prepare_signal_session(tmp_path)
        reason = (
            "Kritische Hotfix-Session fuer Release-Blocker; Artefakte werden "
            "im Follow-up-Task bis Ende der Woche nachgereicht."
        )

        resp = _run(
            mcp_server.drift_session_end(
                session_id=session.session_id,
                force=True,
                bypass_reason=reason,
            )
        )
        assert resp["status"] == "ok"
        assert resp["handover_bypass"]["forced"] is True
        assert resp["handover_bypass"]["reason"] == reason
        assert SessionManager.instance().get(session.session_id) is None

    def test_retry_counter_increments_on_each_block(self, tmp_path: Path) -> None:
        import drift.mcp_server as mcp_server

        session = _prepare_signal_session(tmp_path)

        for expected_retry in (1, 2, 3):
            resp = _run(
                mcp_server.drift_session_end(session_id=session.session_id)
            )
            assert resp["status"] == "blocked"
            live = SessionManager.instance().get(session.session_id)
            assert live is not None
            assert live.handover_retries == expected_retry

    def test_empty_session_without_work_is_exempt(self, tmp_path: Path) -> None:
        import drift.mcp_server as mcp_server

        mgr = SessionManager.instance()
        sid = mgr.create(repo_path=str(tmp_path))

        resp = _run(mcp_server.drift_session_end(session_id=sid))
        assert resp["status"] == "ok"
        assert mgr.get(sid) is None
