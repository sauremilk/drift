from __future__ import annotations

import json
import urllib.error
from pathlib import Path
from types import SimpleNamespace

import pytest

from drift.calibration.history import FindingSnapshot, ScanSnapshot
from drift.models import (
    NegativeContext,
    NegativeContextCategory,
    NegativeContextScope,
    Severity,
    SignalType,
)


def test_correlate_github_issues_tp_and_fn() -> None:
    from drift.calibration.github_correlator import correlate_github_issues

    snapshots = [
        ScanSnapshot(
            findings=[FindingSnapshot(signal_type="pattern_fragmentation", file_path="src/a.py")]
        )
    ]
    issues = [
        {"number": 42, "title": "Fix bug", "labels": [{"name": "bug"}]},
        {"number": 77, "title": "No match", "labels": ["defect"]},
        {"number": "bad", "title": "ignored", "labels": [{"name": "bug"}]},
    ]

    events = correlate_github_issues(
        snapshots,
        issues,
        pr_files_map={1: ["src/a.py"], 2: ["src/other.py"]},
    )

    verdicts = {(e.signal_type, e.file_path, e.verdict) for e in events}
    assert ("pattern_fragmentation", "src/a.py", "tp") in verdicts
    assert ("_unattributed", "src/other.py", "fn") in verdicts


def test_correlate_github_issues_filters_invalid_shapes() -> None:
    from drift.calibration.github_correlator import correlate_github_issues

    events = correlate_github_issues(
        snapshots=[],
        issues=[
            123,
            {"number": 1, "labels": "not-list"},
            {"number": 2, "labels": [{"name": "feature"}]},
        ],
        pr_files_map={},
    )
    assert events == []


class _FakeResp:
    def __init__(self, payload: object, headers: dict[str, str] | None = None) -> None:
        self._payload = payload
        self.headers = headers or {}

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self) -> _FakeResp:
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def test_github_client_request_and_headers(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from drift.ingestion.github_api import GitHubClient, _float_header, _int_header

    client = GitHubClient(token="tok", cache_dir=tmp_path / "cache")
    assert client.is_authenticated is True

    def fake_open(_req, timeout=30):
        assert timeout == 30
        return _FakeResp(
            [{"id": 1}],
            headers={"X-RateLimit-Remaining": "20", "X-RateLimit-Reset": "123.5"},
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_open)

    out = client._request("/repos/o/r/issues", params={"state": "closed"})
    assert isinstance(out, list)
    assert client._rate_remaining == 20
    assert client._rate_reset == 123.5

    assert _int_header(SimpleNamespace(headers={"X": "7"}), "X") == 7
    assert _int_header(SimpleNamespace(headers={"X": "bad"}), "X") is None
    assert _float_header(SimpleNamespace(headers={"X": "1.5"}), "X") == 1.5
    assert _float_header(SimpleNamespace(headers={"X": "bad"}), "X") is None


def test_github_client_rate_limit_and_error_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    from drift.ingestion.github_api import GitHubClient

    client = GitHubClient(token=None)
    assert client.is_authenticated is False

    monkeypatch.setattr("time.time", lambda: 100.0)
    slept: list[float] = []
    monkeypatch.setattr("time.sleep", lambda s: slept.append(s))

    client._rate_remaining = 1
    client._rate_reset = 120.0

    def fake_open_http(_req, timeout=30):
        raise urllib.error.HTTPError("u", 403, "forbidden", hdrs=None, fp=None)

    monkeypatch.setattr("urllib.request.urlopen", fake_open_http)
    with pytest.raises(urllib.error.HTTPError):
        client._request("/repos/o/r/issues")
    assert slept  # waited due to low quota

    def fake_open_url(_req, timeout=30):
        raise urllib.error.URLError("down")

    monkeypatch.setattr("urllib.request.urlopen", fake_open_url)
    with pytest.raises(urllib.error.URLError):
        client._request("/repos/o/r/issues")


def test_github_client_issue_pr_file_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    from drift.ingestion.github_api import GitHubClient

    client = GitHubClient(token="tok")

    monkeypatch.setattr(
        client,
        "_request",
        lambda endpoint, **kwargs: [{"number": 1}] if endpoint.endswith("/issues") else [],
    )
    issues = client.get_issues("o", "r", labels=["bug"], state="closed", per_page=10)
    assert issues == [{"number": 1}]

    timeline = [
        {
            "event": "cross-referenced",
            "source": {"issue": {"pull_request": {"url": "x"}, "number": 5}},
        },
        {"event": "opened"},
    ]
    monkeypatch.setattr(client, "_request", lambda endpoint, **kwargs: timeline)
    prs = client.get_pull_requests_for_issue("o", "r", 1)
    assert prs == [{"pull_request": {"url": "x"}, "number": 5}]

    monkeypatch.setattr(
        client, "_request", lambda endpoint, **kwargs: [{"filename": "a.py"}, {"x": 1}]
    )
    files = client.get_pr_files("o", "r", 10)
    assert files == ["a.py", ""]

    monkeypatch.setattr(
        client,
        "_request",
        lambda endpoint, **kwargs: (_ for _ in ()).throw(
            urllib.error.HTTPError("u", 404, "n", hdrs=None, fp=None)
        ),
    )
    assert client.get_pull_requests_for_issue("o", "r", 1) == []
    assert client.get_pr_files("o", "r", 1) == []


def _nc(**kwargs: object) -> NegativeContext:
    defaults = dict(
        anti_pattern_id="neg-1",
        category=NegativeContextCategory.SECURITY,
        source_signal=SignalType.MISSING_AUTHORIZATION,
        severity=Severity.HIGH,
        scope=NegativeContextScope.FILE,
        description="desc",
        forbidden_pattern="forbidden",
        canonical_alternative="canonical",
        affected_files=["src/a.py"],
        confidence=0.9,
        rationale="r",
    )
    defaults.update(kwargs)
    return NegativeContext(**defaults)


def test_negative_context_export_module_formats() -> None:
    from drift.negative_context.export import (
        MARKER_BEGIN,
        MARKER_END,
        _deduplicate_items,
        _render_body,
        _render_empty,
        _render_prompt_rule,
        render_negative_context_markdown,
    )

    items = [
        _nc(anti_pattern_id="neg-1", affected_files=["src/a.py"], forbidden_pattern="f1"),
        _nc(anti_pattern_id="neg-2", affected_files=["src/b.py"], forbidden_pattern="f2"),
    ]

    deduped = _deduplicate_items(items)
    assert len(deduped) == 1
    assert deduped[0].occurrences == 2
    assert "(x2)" in _render_prompt_rule(deduped[0])

    instructions = render_negative_context_markdown(
        items, fmt="instructions", drift_score=0.5, severity=Severity.MEDIUM
    )
    assert MARKER_BEGIN in instructions and MARKER_END in instructions
    assert "INSTEAD" in instructions

    prompt = render_negative_context_markdown(
        items, fmt="prompt", drift_score=0.5, severity=Severity.MEDIUM
    )
    assert "DO_NOT -> INSTEAD" in prompt

    raw = render_negative_context_markdown(
        items, fmt="raw", drift_score=0.5, severity=Severity.MEDIUM
    )
    payload = json.loads(raw)
    assert payload["format"] == "drift-negative-context-v1"
    assert payload["total_items"] == 1

    body = _render_body(items, 0.2, Severity.LOW, "2026-04-10")
    assert "Anti-Patterns" in body

    empty_prompt = _render_empty("prompt", 0.1, Severity.INFO)
    assert "No significant anti-patterns detected" in empty_prompt
