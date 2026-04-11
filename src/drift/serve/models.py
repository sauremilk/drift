"""Pydantic models for A2A JSON-RPC 2.0 messages."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class A2AMessagePart(BaseModel):
    """A single part inside an A2A message."""

    kind: Literal["text", "data"] = "text"
    text: str | None = None
    data: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class A2AMessage(BaseModel):
    """An A2A protocol message with role and parts."""

    role: Literal["user", "agent"] = "user"
    parts: list[A2AMessagePart] = Field(default_factory=list)
    metadata: dict[str, Any] | None = None


class A2AMessageSendParams(BaseModel):
    """Parameters for the ``message/send`` JSON-RPC method."""

    message: A2AMessage


class A2ARequest(BaseModel):
    """A2A JSON-RPC 2.0 request envelope."""

    jsonrpc: Literal["2.0"] = "2.0"
    method: str
    id: str | int
    params: A2AMessageSendParams | None = None


class A2AResult(BaseModel):
    """Successful result wrapper for a JSON-RPC response."""

    message: A2AMessage


class A2AResponse(BaseModel):
    """A2A JSON-RPC 2.0 success response."""

    jsonrpc: Literal["2.0"] = "2.0"
    id: str | int
    result: A2AResult


class A2AErrorDetail(BaseModel):
    """JSON-RPC error object."""

    code: int
    message: str
    data: dict[str, Any] | None = None


class A2AErrorResponse(BaseModel):
    """A2A JSON-RPC 2.0 error response."""

    jsonrpc: Literal["2.0"] = "2.0"
    id: str | int | None = None
    error: A2AErrorDetail


# Standard JSON-RPC 2.0 error codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
