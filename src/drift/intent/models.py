"""Intent data models — contracts, requirements, constraints, categories."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal


class IntentCategory(StrEnum):
    """Core application archetypes for intent classification."""

    DATA_PERSISTENCE = "data_persistence"
    CRUD = "crud"
    AUTH = "auth"
    REALTIME = "realtime"
    API = "api"
    AUTOMATION = "automation"
    OFFLINE = "offline"
    MULTI_USER = "multi_user"
    GENERAL = "general"


# Accepted priority values
_VALID_PRIORITIES = frozenset({"must", "should", "nice"})


@dataclass
class Requirement:
    """A single formalized requirement extracted from user intent."""

    id: str
    description_plain: str
    description_technical: str
    priority: Literal["must", "should", "nice"]
    validation_signal: str | None = None

    def __post_init__(self) -> None:
        if self.priority not in _VALID_PRIORITIES:
            raise ValueError(
                f"Invalid priority {self.priority!r}, must be one of {sorted(_VALID_PRIORITIES)}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description_plain": self.description_plain,
            "description_technical": self.description_technical,
            "priority": self.priority,
            "validation_signal": self.validation_signal,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Requirement:
        return cls(
            id=data["id"],
            description_plain=data["description_plain"],
            description_technical=data["description_technical"],
            priority=data["priority"],
            validation_signal=data.get("validation_signal"),
        )


@dataclass
class Constraint:
    """A non-functional constraint on the intent."""

    id: str
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "description": self.description}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Constraint:
        return cls(id=data["id"], description=data["description"])


@dataclass
class IntentContract:
    """Full formalized intent contract."""

    description: str
    category: IntentCategory
    requirements: list[Requirement]
    language: str = "en"
    constraints: list[Constraint] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "category": self.category.value,
            "requirements": [r.to_dict() for r in self.requirements],
            "constraints": [c.to_dict() for c in self.constraints],
            "language": self.language,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IntentContract:
        return cls(
            id=data["id"],
            description=data["description"],
            category=IntentCategory(data["category"]),
            requirements=[Requirement.from_dict(r) for r in data.get("requirements", [])],
            constraints=[Constraint.from_dict(c) for c in data.get("constraints", [])],
            language=data.get("language", "en"),
            created_at=datetime.fromisoformat(data["created_at"]),
        )


@dataclass
class ClarifyingQuestion:
    """A question to ask the user to fill gaps in an intent contract."""

    question_text: str
    options: list[str]
    affects_requirement: str


# ---------------------------------------------------------------------------
# Phase-based contract models (5-phase intent loop)
# ---------------------------------------------------------------------------

# Valid categories for the intent baselines / contract loop
INTENT_CATEGORIES = frozenset(
    {"persistence", "security", "error_handling", "communication", "automation", "utility"}
)

# Mapping from IntentCategory to baseline category
_CATEGORY_TO_BASELINE: dict[str, str] = {
    "data_persistence": "persistence",
    "crud": "persistence",
    "auth": "security",
    "realtime": "communication",
    "api": "communication",
    "automation": "automation",
    "offline": "utility",
    "multi_user": "persistence",
    "general": "utility",
}


@dataclass
class Contract:
    """A single verifiable contract from the intent loop.

    Used across all five phases.
    """

    id: str
    description_technical: str
    description_human: str
    category: str
    severity: Literal["critical", "high", "medium"]
    auto_repair_eligible: bool
    source: Literal["baseline", "extracted", "clarification"] = "baseline"
    verification_signal: str | None = None

    def __post_init__(self) -> None:
        if self.category not in INTENT_CATEGORIES:
            raise ValueError(
                f"Invalid category {self.category!r}, must be one of {sorted(INTENT_CATEGORIES)}"
            )

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": self.id,
            "description_technical": self.description_technical,
            "description_human": self.description_human,
            "category": self.category,
            "severity": self.severity,
            "auto_repair_eligible": self.auto_repair_eligible,
            "source": self.source,
        }
        if self.verification_signal is not None:
            d["verification_signal"] = self.verification_signal
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Contract:
        return cls(
            id=data["id"],
            description_technical=data["description_technical"],
            description_human=data["description_human"],
            category=data["category"],
            severity=data["severity"],
            auto_repair_eligible=data["auto_repair_eligible"],
            source=data.get("source", "baseline"),
            verification_signal=data.get("verification_signal"),
        )


class ContractStatus(StrEnum):
    """Status of a contract after validation."""

    FULFILLED = "fulfilled"
    VIOLATED = "violated"
    UNVERIFIABLE = "unverifiable"


@dataclass
class ContractResult:
    """Validation result for a single contract."""

    contract: Contract
    status: ContractStatus
    finding_id: str | None = None
    finding_title: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "contract_id": self.contract.id,
            "status": self.status.value,
            "description_human": self.contract.description_human,
        }
        if self.finding_id:
            d["finding_id"] = self.finding_id
            d["finding_title"] = self.finding_title
        return d
