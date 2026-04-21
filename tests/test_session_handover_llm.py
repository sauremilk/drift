"""Optional L4 LLM-review hook tests (ADR-079).

The L4 layer is opt-in via ``DRIFT_SESSION_END_LLM_REVIEW=1`` or the
``llm_review`` / ``llm_reviewer`` kwargs. These tests exercise only the hook
wiring; no real LLM is invoked.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from drift.session import DriftSession, SessionManager
from drift.session_handover import ChangeClass, validate


@pytest.fixture(autouse=True)
def _reset_sessions() -> Any:
    SessionManager.reset_instance()
    yield
    SessionManager.reset_instance()


def _session(tmp_path: Path) -> DriftSession:
    mgr = SessionManager.instance()
    sid = mgr.create(repo_path=str(tmp_path))
    s = mgr.get(sid)
    assert s is not None
    return s


def _valid_artifacts(tmp_path: Path, session: DriftSession) -> dict[str, str]:
    md = tmp_path / "work_artifacts" / f"session_{session.session_id[:8]}.md"
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(
        "---\n"
        f'session_id: "{session.session_id}"\n'
        "duration_seconds: 100\n"
        "tool_calls: 5\n"
        "tasks_completed: 1\n"
        'change_class: "docs"\n'
        "findings_delta: 0\n"
        "---\n\n"
        "## Scope\nDokumentation zum Gate wurde geschaerft.\n\n"
        "## Ergebnisse\nSkill-Datei erweitert.\n\n"
        "## Offene Enden\nKeine offenen Punkte.\n\n"
        "## Next-Agent-Einstieg\nMit drift_session_start beginnen.\n\n"
        "## Evidenz\nAudit unveraendert.\n",
        encoding="utf-8",
    )
    return {"session_md": str(md)}


class TestLlmReviewHook:
    def test_semantic_ok_absent_when_disabled(self, tmp_path: Path) -> None:
        session = _session(tmp_path)
        overrides = _valid_artifacts(tmp_path, session)

        result = validate(
            session,
            change_class=ChangeClass.DOCS,
            path_overrides=overrides,
        )
        assert result.ok is True
        assert result.semantic_ok is None
        assert "semantic_ok" not in result.to_dict()

    def test_semantic_ok_true_when_reviewer_accepts(self, tmp_path: Path) -> None:
        session = _session(tmp_path)
        overrides = _valid_artifacts(tmp_path, session)

        calls: list[dict[str, Any]] = []

        def reviewer(payload: dict[str, Any]) -> bool:
            calls.append(payload)
            return True

        result = validate(
            session,
            change_class=ChangeClass.DOCS,
            path_overrides=overrides,
            llm_review=True,
            llm_reviewer=reviewer,
        )
        assert result.ok is True
        assert result.semantic_ok is True
        assert calls, "reviewer must be invoked"
        assert calls[0]["change_class"] == "docs"

    def test_semantic_ok_false_blocks(self, tmp_path: Path) -> None:
        session = _session(tmp_path)
        overrides = _valid_artifacts(tmp_path, session)

        result = validate(
            session,
            change_class=ChangeClass.DOCS,
            path_overrides=overrides,
            llm_review=True,
            llm_reviewer=lambda _payload: False,
        )
        assert result.semantic_ok is False
        assert result.ok is False

    def test_reviewer_exception_fails_closed(self, tmp_path: Path) -> None:
        session = _session(tmp_path)
        overrides = _valid_artifacts(tmp_path, session)

        def reviewer(_payload: dict[str, Any]) -> bool:
            raise RuntimeError("reviewer crashed")

        result = validate(
            session,
            change_class=ChangeClass.DOCS,
            path_overrides=overrides,
            llm_review=True,
            llm_reviewer=reviewer,
        )
        assert result.semantic_ok is False

    def test_reviewer_skipped_when_earlier_layer_blocked(self, tmp_path: Path) -> None:
        session = _session(tmp_path)
        # No artifacts written -> L1 blocks, reviewer must not be called.

        invoked = {"count": 0}

        def reviewer(_payload: dict[str, Any]) -> bool:
            invoked["count"] += 1
            return True

        result = validate(
            session,
            change_class=ChangeClass.DOCS,
            llm_review=True,
            llm_reviewer=reviewer,
        )
        assert result.ok is False
        assert result.semantic_ok is None
        assert invoked["count"] == 0

    def test_env_flag_enables_reviewer(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        session = _session(tmp_path)
        overrides = _valid_artifacts(tmp_path, session)
        monkeypatch.setenv("DRIFT_SESSION_END_LLM_REVIEW", "1")

        # Default reviewer returns True, so ok stays True.
        result = validate(
            session,
            change_class=ChangeClass.DOCS,
            path_overrides=overrides,
        )
        assert result.semantic_ok is True
        # ensure JSON payload exposes semantic_ok when set
        assert json.dumps(result.to_dict())  # no serialization error
