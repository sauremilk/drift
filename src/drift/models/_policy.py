"""Data models for compiled task-specific policy packages."""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Any, Literal

PolicyCategory = Literal[
    "scope",
    "reuse",
    "prohibition",
    "invariant",
    "review_trigger",
    "stop_condition",
]

PolicyEnforcement = Literal["info", "warn", "block"]


@dataclass(slots=True)
class PolicyRule:
    """A single compiled policy rule for agent consumption.

    Attributes:
        id: Stable identifier (e.g. ``"prohibit-001"``).
        category: Kind of constraint this rule expresses.
        rule: Human-readable constraint text.
        enforcement: How strictly the rule must be followed.
        source: Optional reference to ADR, decision, or doc.
        confidence: How reliable the rule derivation is (0.0–1.0).
    """

    id: str
    category: PolicyCategory
    rule: str
    enforcement: PolicyEnforcement = "warn"
    source: str | None = None
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-safe dict."""
        return {
            "id": self.id,
            "category": self.category,
            "rule": self.rule,
            "enforcement": self.enforcement,
            "source": self.source,
            "confidence": self.confidence,
        }


@dataclass(slots=True)
class CompiledPolicy:
    """A task-specific policy package compiled from repo state.

    Contains scope boundaries, prioritised rules, reuse targets, and
    a pre-rendered Markdown instruction block for agent prompts.

    Attributes:
        task: The natural-language task description.
        compiled_at: ISO-8601 timestamp of compilation.
        scope: Scope metadata (allowed/forbidden paths, modules, layers).
        rules: Prioritised list of policy rules.
        reuse_targets: Abstractions the agent should prefer reusing.
        risk_context: Aggregated risk info from scoped findings.
        agent_instruction: Pre-rendered Markdown for prompt injection.
    """

    task: str
    compiled_at: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )
    scope: dict[str, Any] = field(default_factory=dict)
    rules: list[PolicyRule] = field(default_factory=list)
    reuse_targets: list[dict[str, Any]] = field(default_factory=list)
    risk_context: dict[str, Any] = field(default_factory=dict)
    agent_instruction: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-safe dict."""
        return {
            "task": self.task,
            "compiled_at": self.compiled_at,
            "scope": dict(self.scope),
            "rules": [r.to_dict() for r in self.rules],
            "reuse_targets": list(self.reuse_targets),
            "risk_context": dict(self.risk_context),
            "agent_instruction": self.agent_instruction,
        }
