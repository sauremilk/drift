"""Utility helpers for the drift API package."""

from __future__ import annotations

import json
from typing import Any


def to_json(result: dict[str, Any], *, indent: int = 2) -> str:
    """Serialize an API result dict to JSON string."""
    return json.dumps(result, indent=indent, default=str, sort_keys=True)
