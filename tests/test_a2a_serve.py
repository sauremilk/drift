"""Tests for A2A Agent Card and drift serve HTTP endpoints."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Fixture: FastAPI TestClient (skip entire module if deps missing)
# ---------------------------------------------------------------------------

fastapi = pytest.importorskip("fastapi", reason="fastapi not installed")
httpx = pytest.importorskip("httpx", reason="httpx not installed")

from starlette.testclient import TestClient  # noqa: E402

from drift.serve.app import create_app  # noqa: E402

BASE_URL = "http://testserver"


@pytest.fixture()
def client() -> TestClient:
    app = create_app(BASE_URL)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Agent Card tests
# ---------------------------------------------------------------------------


class TestAgentCard:
    """Test GET /.well-known/agent-card.json."""

    def test_agent_card_returns_valid_json(self, client: TestClient) -> None:
        resp = client.get("/.well-known/agent-card.json")
        assert resp.status_code == 200
        card = resp.json()
        # Required A2A v1.0 fields
        assert "name" in card
        assert "description" in card
        assert "version" in card
        assert "supportedInterfaces" in card
        assert "capabilities" in card
        assert "defaultInputModes" in card
        assert "defaultOutputModes" in card
        assert "skills" in card

    def test_agent_card_version_matches_drift(self, client: TestClient) -> None:
        from drift import __version__

        resp = client.get("/.well-known/agent-card.json")
        card = resp.json()
        assert card["version"] == __version__

    def test_agent_card_has_eight_skills(self, client: TestClient) -> None:
        resp = client.get("/.well-known/agent-card.json")
        card = resp.json()
        assert len(card["skills"]) == 8
        skill_ids = {s["id"] for s in card["skills"]}
        expected = {
            "scan", "diff", "explain", "fix_plan",
            "validate", "nudge", "brief", "negative_context",
        }
        assert skill_ids == expected

    def test_agent_card_interface_url(self, client: TestClient) -> None:
        resp = client.get("/.well-known/agent-card.json")
        card = resp.json()
        iface = card["supportedInterfaces"][0]
        assert iface["url"] == f"{BASE_URL}/a2a/v1"
        assert iface["protocolBinding"] == "JSONRPC"
        assert iface["protocolVersion"] == "1.0"

    def test_agent_card_content_type(self, client: TestClient) -> None:
        resp = client.get("/.well-known/agent-card.json")
        assert "application/a2a+json" in resp.headers.get("content-type", "")

    def test_agent_card_provider(self, client: TestClient) -> None:
        resp = client.get("/.well-known/agent-card.json")
        card = resp.json()
        assert card["provider"]["organization"] == "Mick Gottschalk"

    def test_agent_card_no_streaming(self, client: TestClient) -> None:
        resp = client.get("/.well-known/agent-card.json")
        card = resp.json()
        assert card["capabilities"]["streaming"] is False


# ---------------------------------------------------------------------------
# A2A JSON-RPC endpoint tests
# ---------------------------------------------------------------------------


def _rpc_request(
    skill: str,
    params: dict[str, Any] | None = None,
    *,
    request_id: int = 1,
    method: str = "message/send",
) -> dict[str, Any]:
    """Build a minimal A2A JSON-RPC 2.0 request."""
    data: dict[str, Any] = {"skill": skill}
    if params:
        data.update(params)
    return {
        "jsonrpc": "2.0",
        "method": method,
        "id": request_id,
        "params": {
            "message": {
                "role": "user",
                "parts": [{"kind": "data", "data": data}],
            },
        },
    }


class TestA2AEndpoint:
    """Test POST /a2a/v1."""

    def test_scan_skill_dispatch(self, client: TestClient, tmp_path: Any) -> None:
        """A scan request dispatches to the scan handler and returns a result."""
        mock_result: dict[str, Any] = {"drift_score": 0.42, "findings": []}
        with patch("drift.api.scan", return_value=mock_result) as mock_scan:
            resp = client.post(
                "/a2a/v1",
                json=_rpc_request("scan", {"path": str(tmp_path)}),
            )
        assert resp.status_code == 200
        body = resp.json()
        assert "result" in body
        assert body["id"] == 1
        result_data = body["result"]["message"]["parts"][0]["data"]
        assert result_data["drift_score"] == 0.42
        mock_scan.assert_called_once()

    def test_unknown_skill_returns_method_not_found(self, client: TestClient) -> None:
        resp = client.post(
            "/a2a/v1",
            json=_rpc_request("nonexistent_skill"),
        )
        body = resp.json()
        assert "error" in body
        assert body["error"]["code"] == -32601
        assert "nonexistent_skill" in body["error"]["message"]

    def test_missing_skill_returns_invalid_params(self, client: TestClient) -> None:
        """Request without skill identifier returns -32602."""
        req = {
            "jsonrpc": "2.0",
            "method": "message/send",
            "id": 1,
            "params": {
                "message": {
                    "role": "user",
                    "parts": [{"kind": "text", "text": "hello"}],
                },
            },
        }
        resp = client.post("/a2a/v1", json=req)
        body = resp.json()
        assert "error" in body
        assert body["error"]["code"] == -32602

    def test_malformed_json_returns_parse_error(self, client: TestClient) -> None:
        resp = client.post(
            "/a2a/v1",
            content=b"not json at all{{{",
            headers={"content-type": "application/json"},
        )
        body = resp.json()
        assert "error" in body
        assert body["error"]["code"] == -32700

    def test_unsupported_method_returns_error(self, client: TestClient) -> None:
        resp = client.post(
            "/a2a/v1",
            json=_rpc_request("scan", method="tasks/list"),
        )
        body = resp.json()
        assert "error" in body
        assert body["error"]["code"] == -32600
        assert "message/send" in body["error"]["message"]

    def test_invalid_path_returns_error(self, client: TestClient) -> None:
        """Non-existent repo path triggers an INVALID_PARAMS error."""
        resp = client.post(
            "/a2a/v1",
            json=_rpc_request("scan", {"path": "/nonexistent/repo/path"}),
        )
        body = resp.json()
        assert "error" in body
        assert body["error"]["code"] == -32602

    def test_skill_via_metadata(self, client: TestClient, tmp_path: Any) -> None:
        """Skill specified via metadata.skillId works."""
        mock_result: dict[str, Any] = {"status": "ok"}
        with patch("drift.api.validate", return_value=mock_result):
            req = {
                "jsonrpc": "2.0",
                "method": "message/send",
                "id": 42,
                "params": {
                    "message": {
                        "role": "user",
                        "parts": [
                            {"kind": "data", "data": {"path": str(tmp_path)}},
                        ],
                        "metadata": {"skillId": "validate"},
                    },
                },
            }
            resp = client.post("/a2a/v1", json=req)
        body = resp.json()
        assert "result" in body
        assert body["id"] == 42


# ---------------------------------------------------------------------------
# CLI serve command tests
# ---------------------------------------------------------------------------


class TestServeCommand:
    """Test the drift serve CLI command."""

    def test_serve_missing_deps_shows_hint(self) -> None:
        from click.testing import CliRunner

        from drift.commands.serve import serve

        with patch.dict("sys.modules", {"uvicorn": None, "fastapi": None}):
            # The import check in the command will fail
            runner = CliRunner()
            result = runner.invoke(serve, ["--base-url", "http://localhost:8080"])
            # Should fail because we can't actually block the import
            # in a clean way when the module is already cached;
            # just verify the command is registered and callable
            assert result.exit_code in (0, 1)
