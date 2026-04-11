"""FastAPI application for the drift A2A server."""

from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from drift.serve.agent_card import build_agent_card
from drift.serve.models import (
    INVALID_REQUEST,
    PARSE_ERROR,
    A2AErrorDetail,
    A2AErrorResponse,
    A2ARequest,
)

# Custom media type registered by the A2A spec
_A2A_MEDIA_TYPE = "application/a2a+json"


def create_app(base_url: str) -> FastAPI:
    """Create and return the drift A2A FastAPI application.

    Args:
        base_url: Public base URL for the agent card, e.g.
            ``http://localhost:8080``.
    """
    app = FastAPI(
        title="drift A2A Server",
        description="A2A-compatible HTTP server for drift architectural analysis.",
        docs_url="/docs",
    )

    # Cache the agent card dict
    card = build_agent_card(base_url)

    @app.get("/.well-known/agent-card.json")
    async def agent_card() -> JSONResponse:
        """Return the A2A Agent Card."""
        return JSONResponse(content=card, media_type=_A2A_MEDIA_TYPE)

    @app.post("/a2a/v1")
    async def a2a_endpoint(request: Request) -> JSONResponse:
        """A2A JSON-RPC 2.0 entry point."""
        from drift.serve.a2a_router import dispatch

        # Parse raw body
        try:
            body: dict[str, Any] = await request.json()
        except (json.JSONDecodeError, ValueError):
            err = A2AErrorResponse(
                id=None,
                error=A2AErrorDetail(
                    code=PARSE_ERROR,
                    message="Invalid JSON in request body.",
                ),
            )
            return JSONResponse(
                content=err.model_dump(), status_code=200
            )

        # Validate JSON-RPC envelope
        try:
            rpc_request = A2ARequest.model_validate(body)
        except Exception:
            err = A2AErrorResponse(
                id=body.get("id"),
                error=A2AErrorDetail(
                    code=INVALID_REQUEST,
                    message="Invalid A2A JSON-RPC request.",
                ),
            )
            return JSONResponse(
                content=err.model_dump(), status_code=200
            )

        # Only handle message/send
        if rpc_request.method != "message/send":
            err = A2AErrorResponse(
                id=rpc_request.id,
                error=A2AErrorDetail(
                    code=INVALID_REQUEST,
                    message=f"Unsupported method: {rpc_request.method!r}. Use 'message/send'.",
                ),
            )
            return JSONResponse(
                content=err.model_dump(), status_code=200
            )

        if rpc_request.params is None:
            err = A2AErrorResponse(
                id=rpc_request.id,
                error=A2AErrorDetail(
                    code=INVALID_REQUEST,
                    message="Missing 'params' in request.",
                ),
            )
            return JSONResponse(
                content=err.model_dump(), status_code=200
            )

        # Dispatch to skill handler
        result = dispatch(rpc_request.params, rpc_request.id)
        return JSONResponse(content=result.model_dump(), status_code=200)

    return app
