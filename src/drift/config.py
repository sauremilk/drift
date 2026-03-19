"""Configuration loading and validation for Drift."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class LayerBoundary(BaseModel):
    """A single layer boundary rule."""

    name: str
    from_pattern: str = Field(alias="from")
    deny_import: list[str] = []

    model_config = {"populate_by_name": True}


class PolicyConfig(BaseModel):
    """Policy configuration for enforcement rules."""

    error_handling: dict[str, Any] = Field(default_factory=dict)
    layer_boundaries: list[LayerBoundary] = Field(default_factory=list)
    max_pattern_variants: dict[str, int] = Field(default_factory=dict)
    ai_attribution: dict[str, Any] = Field(default_factory=dict)


class ThresholdsConfig(BaseModel):
    """Tunable thresholds for detection signals."""

    high_complexity: int = 10
    medium_complexity: int = 5
    min_function_loc: int = 10
    similarity_threshold: float = 0.80
    recency_days: int = 14
    volatility_z_threshold: float = 1.5


class SignalWeights(BaseModel):
    """Weights for each detection signal in composite scoring.

    Weights are normalised internally — they don't need to sum to 1.0,
    but a warning is emitted if they deviate significantly.
    """

    pattern_fragmentation: float = 0.22
    architecture_violation: float = 0.22
    mutant_duplicate: float = 0.17
    explainability_deficit: float = 0.12
    doc_impl_drift: float = 0.00  # Phase 2 stub — zero weight until implemented
    temporal_volatility: float = 0.17
    system_misalignment: float = 0.10

    def as_dict(self) -> dict[str, float]:
        return self.model_dump()


class DriftConfig(BaseModel):
    """Main drift configuration, loaded from drift.yaml."""

    include: list[str] = Field(default_factory=lambda: ["**/*.py"])
    exclude: list[str] = Field(
        default_factory=lambda: [
            "**/node_modules/**",
            "**/__pycache__/**",
            "**/venv/**",
            "**/.venv/**",
            "**/.git/**",
            "**/dist/**",
            "**/build/**",
            "**/.tox/**",
            "**/*.egg-info/**",
        ]
    )
    policies: PolicyConfig = Field(default_factory=PolicyConfig)
    weights: SignalWeights = Field(default_factory=SignalWeights)
    thresholds: ThresholdsConfig = Field(default_factory=ThresholdsConfig)
    cache_dir: str = ".drift-cache"
    fail_on: str = "high"

    @staticmethod
    def _find_config_file(repo_path: Path) -> Path | None:
        for name in ("drift.yaml", "drift.yml", ".drift.yaml"):
            candidate = repo_path / name
            if candidate.exists():
                return candidate
        return None

    @classmethod
    def load(cls, repo_path: Path, config_path: Path | None = None) -> DriftConfig:
        if config_path is None:
            config_path = cls._find_config_file(repo_path)

        if config_path and config_path.exists():
            raw = config_path.read_text(encoding="utf-8")
            data = yaml.safe_load(raw) or {}
            return cls(**data)

        return cls()

    def severity_gate(self) -> str:
        return self.fail_on
