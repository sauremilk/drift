"""Tests for ExceptionContractDriftSignal (ECM)."""

from __future__ import annotations

from pathlib import Path

import pytest

from drift.config import DriftConfig
from drift.ingestion.ast_parser import PythonFileParser
from drift.models import FileHistory, ParseResult, SignalType
from drift.signals import exception_contract_drift as ecm_mod
from drift.signals.exception_contract_drift import ExceptionContractDriftSignal


def _write_and_parse(tmp_path: Path, rel: str, source: str) -> ParseResult:
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    parser = PythonFileParser(source, path)
    return parser.parse()


def _history_for(parse_result: ParseResult, commits: int = 3) -> dict[str, FileHistory]:
    return {
        parse_result.file_path.as_posix(): FileHistory(
            path=parse_result.file_path,
            total_commits=commits,
        )
    }


def _run(
    tmp_path: Path,
    parse_results: list[ParseResult],
    old_sources: dict[str, str],
    histories: dict[str, FileHistory],
    monkeypatch: pytest.MonkeyPatch,
):
    signal = ExceptionContractDriftSignal(repo_path=tmp_path)

    def _fake_git_show(_repo_path: Path, _ref: str, file_posix: str) -> str | None:
        return old_sources.get(file_posix)

    def _fake_git_show_batch(
        _repo_path: Path,
        _ref: str,
        file_posix_list: list[str],
    ) -> dict[str, str | None]:
        return {fp: old_sources.get(fp) for fp in file_posix_list}

    monkeypatch.setattr(ecm_mod, "_git_show_file", _fake_git_show)
    monkeypatch.setattr(ecm_mod, "_git_show_files_batch", _fake_git_show_batch)
    return signal.analyze(parse_results, histories, DriftConfig())


class TestExceptionContractDrift:
    def test_effective_candidate_limit_scales_for_large_repositories(self) -> None:
        assert ecm_mod._effective_candidate_limit(40, 50) == 40
        assert ecm_mod._effective_candidate_limit(500, 50) == 50
        assert ecm_mod._effective_candidate_limit(10_000, 50) == 300

    def test_true_positive_on_exception_profile_change(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        current = _write_and_parse(
            tmp_path,
            "src/service/core.py",
            """\
def fetch_user(user_id: str) -> dict:
    if not user_id:
        raise RuntimeError("missing id")
    return {"id": user_id}
""",
        )

        old_sources = {
            current.file_path.as_posix(): """\
def fetch_user(user_id: str) -> dict:
    if not user_id:
        raise ValueError("missing id")
    return {"id": user_id}
"""
        }

        findings = _run(
            tmp_path,
            [current],
            old_sources,
            _history_for(current),
            monkeypatch,
        )

        assert len(findings) == 1
        finding = findings[0]
        assert finding.signal_type == SignalType.EXCEPTION_CONTRACT_DRIFT
        assert "fetch_user" in finding.metadata["diverged_functions"]

    def test_true_negative_when_profile_is_unchanged(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        current = _write_and_parse(
            tmp_path,
            "src/service/core.py",
            """\
def fetch_user(user_id: str) -> dict:
    if not user_id:
        raise ValueError("missing id")
    return {"id": user_id}
""",
        )

        old_sources = {
            current.file_path.as_posix(): """\
def fetch_user(user_id: str) -> dict:
    if not user_id:
        raise ValueError("missing id")
    return {"id": user_id}
"""
        }

        findings = _run(
            tmp_path,
            [current],
            old_sources,
            _history_for(current),
            monkeypatch,
        )

        assert findings == []

    def test_edge_case_signature_change_is_ignored(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        current = _write_and_parse(
            tmp_path,
            "src/service/core.py",
            """\
def fetch_user(user_id: str, tenant_id: str) -> dict:
    if not user_id:
        raise RuntimeError("missing id")
    return {"id": user_id, "tenant": tenant_id}
""",
        )

        old_sources = {
            current.file_path.as_posix(): """\
def fetch_user(user_id: str) -> dict:
    if not user_id:
        raise ValueError("missing id")
    return {"id": user_id}
"""
        }

        findings = _run(
            tmp_path,
            [current],
            old_sources,
            _history_for(current),
            monkeypatch,
        )

        assert findings == []

    def test_edge_case_file_without_history_is_skipped(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        current = _write_and_parse(
            tmp_path,
            "src/service/core.py",
            """\
def fetch_user(user_id: str) -> dict:
    if not user_id:
        raise RuntimeError("missing id")
    return {"id": user_id}
""",
        )

        old_sources = {
            current.file_path.as_posix(): """\
def fetch_user(user_id: str) -> dict:
    if not user_id:
        raise ValueError("missing id")
    return {"id": user_id}
"""
        }

        findings = _run(
            tmp_path,
            [current],
            old_sources,
            _history_for(current, commits=1),
            monkeypatch,
        )

        assert findings == []

    def test_edge_case_private_functions_do_not_trigger(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        current = _write_and_parse(
            tmp_path,
            "src/service/core.py",
            """\
def _fetch_user(user_id: str) -> dict:
    if not user_id:
        raise RuntimeError("missing id")
    return {"id": user_id}
""",
        )

        old_sources = {
            current.file_path.as_posix(): """\
def _fetch_user(user_id: str) -> dict:
    if not user_id:
        raise ValueError("missing id")
    return {"id": user_id}
"""
        }

        findings = _run(
            tmp_path,
            [current],
            old_sources,
            _history_for(current),
            monkeypatch,
        )

        assert findings == []
