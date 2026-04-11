"""Build A2A v1.0 Agent Card for drift."""

from __future__ import annotations

import importlib.metadata
from typing import Any


def build_agent_card(base_url: str) -> dict[str, Any]:
    """Return a complete A2A v1.0 Agent Card dictionary.

    Args:
        base_url: The public base URL where the drift A2A server is reachable,
            e.g. ``http://localhost:8080``.  Used in ``supportedInterfaces``.
    """
    version = importlib.metadata.version("drift-analyzer")
    url = base_url.rstrip("/")

    return {
        "name": "drift",
        "description": (
            "Deterministic static analyzer that detects architectural erosion "
            "in Python codebases through cross-file coherence analysis."
        ),
        "version": version,
        "supportedInterfaces": [
            {
                "url": f"{url}/a2a/v1",
                "protocolBinding": "JSONRPC",
                "protocolVersion": "1.0",
            },
        ],
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
        },
        "defaultInputModes": ["application/json"],
        "defaultOutputModes": ["application/json"],
        "skills": _build_skills(),
        "provider": {
            "organization": "Mick Gottschalk",
            "url": "https://github.com/mick-gsk/drift",
        },
        "documentationUrl": "https://mick-gsk.github.io/drift/",
    }


def _build_skills() -> list[dict[str, Any]]:
    """Return the 8 core analysis skills."""
    return [
        {
            "id": "scan",
            "name": "Drift Scan",
            "description": (
                "Run a full architectural drift analysis on a repository "
                "and return scored findings."
            ),
            "tags": ["analysis", "architecture", "static-analysis"],
            "examples": [
                "Scan the repository at /path/to/repo for architectural drift.",
            ],
        },
        {
            "id": "diff",
            "name": "Drift Diff",
            "description": (
                "Compare the current drift state against a baseline and "
                "report new, resolved, and changed findings."
            ),
            "tags": ["analysis", "diff", "baseline"],
            "examples": [
                "Show what changed since the last baseline scan.",
            ],
        },
        {
            "id": "explain",
            "name": "Drift Explain",
            "description": (
                "Explain a specific finding or signal in human-readable detail."
            ),
            "tags": ["explanation", "finding"],
            "examples": [
                "Explain finding PFS-001 from the last scan.",
            ],
        },
        {
            "id": "fix_plan",
            "name": "Drift Fix Plan",
            "description": (
                "Generate an actionable repair plan with prioritized tasks "
                "for the most impactful findings."
            ),
            "tags": ["repair", "fix", "plan"],
            "examples": [
                "Create a fix plan for the top 5 findings.",
            ],
        },
        {
            "id": "validate",
            "name": "Drift Validate",
            "description": (
                "Validate that the drift configuration and environment are "
                "correctly set up for analysis."
            ),
            "tags": ["validation", "config"],
            "examples": [
                "Validate drift configuration for /path/to/repo.",
            ],
        },
        {
            "id": "nudge",
            "name": "Drift Nudge",
            "description": (
                "Get fast directional feedback on uncommitted changes "
                "between full scans."
            ),
            "tags": ["feedback", "incremental"],
            "examples": [
                "Check whether my uncommitted changes make drift better or worse.",
            ],
        },
        {
            "id": "brief",
            "name": "Drift Brief",
            "description": (
                "Get a structural briefing with scope-aware guardrails "
                "before implementing a task."
            ),
            "tags": ["briefing", "guardrails", "planning"],
            "examples": [
                "Brief me before I refactor the auth module.",
            ],
        },
        {
            "id": "negative_context",
            "name": "Drift Negative Context",
            "description": (
                "Export anti-patterns and negative constraints to avoid "
                "when writing new code."
            ),
            "tags": ["context", "anti-patterns", "constraints"],
            "examples": [
                "Show me which anti-patterns to avoid in this codebase.",
            ],
        },
    ]
