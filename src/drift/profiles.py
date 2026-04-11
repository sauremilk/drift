"""Built-in configuration profiles for common use-cases.

Each profile provides pre-tuned signal weights, thresholds, and policies
that can be scaffolded via ``drift init --profile <name>``.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Profile:
    """A named configuration profile with description and config overrides."""

    name: str
    description: str
    weights: dict[str, float]
    thresholds: dict[str, object]
    policies: dict[str, object] = field(default_factory=dict)
    fail_on: str = "none"
    auto_calibrate: bool = True
    guided_thresholds: dict[str, float] = field(default_factory=dict)
    output_language: str = "de"


# ---------------------------------------------------------------------------
# Profile registry
# ---------------------------------------------------------------------------

PROFILES: dict[str, Profile] = {}


def _register(p: Profile) -> Profile:
    PROFILES[p.name] = p
    return p


# ---------------------------------------------------------------------------
# Default profile — mirrors DriftConfig() defaults
# ---------------------------------------------------------------------------
_register(
    Profile(
        name="default",
        description="Balanced defaults suitable for most Python/TS projects.",
        weights={
            "pattern_fragmentation": 0.16,
            "architecture_violation": 0.16,
            "mutant_duplicate": 0.13,
            "temporal_volatility": 0.0,
            "explainability_deficit": 0.09,
            "system_misalignment": 0.08,
            "doc_impl_drift": 0.04,
            "broad_exception_monoculture": 0.04,
            "test_polarity_deficit": 0.04,
            "guard_clause_deficit": 0.03,
            "naming_contract_violation": 0.04,
            "bypass_accumulation": 0.03,
            "exception_contract_drift": 0.03,
            "cohesion_deficit": 0.01,
            "co_change_coupling": 0.005,
        },
        thresholds={
            "similarity_threshold": 0.80,
            "min_function_loc": 10,
            "min_complexity": 5,
            "recency_days": 14,
            "volatility_z_threshold": 1.5,
            "max_discovery_files": 10000,
        },
        fail_on="none",
    )
)

# ---------------------------------------------------------------------------
# Vibe-Coding profile — optimised for AI-accelerated codebases
# ---------------------------------------------------------------------------
_register(
    Profile(
        name="vibe-coding",
        description=(
            "Optimised for AI-accelerated codebases (Copilot, Cursor, Claude). "
            "Upweights copy-paste detection, bypass accumulation, and test "
            "polarity deficit — the dominant debt vectors in vibe-coded repos."
        ),
        weights={
            # ↑ Copy-paste and fragmentation (primary vibe-coding debt vector)
            "mutant_duplicate": 0.20,
            "pattern_fragmentation": 0.18,
            # Architecture erosion
            "architecture_violation": 0.14,
            "temporal_volatility": 0.0,
            "system_misalignment": 0.08,
            # ↑ Explainability + quality bypass (AI-specific deficit patterns)
            "explainability_deficit": 0.10,
            "bypass_accumulation": 0.06,
            "test_polarity_deficit": 0.06,
            # Remaining signals
            "naming_contract_violation": 0.04,
            "broad_exception_monoculture": 0.04,
            "guard_clause_deficit": 0.03,
            "doc_impl_drift": 0.02,
            "exception_contract_drift": 0.02,
            "cohesion_deficit": 0.01,
            "co_change_coupling": 0.005,
        },
        thresholds={
            "similarity_threshold": 0.75,
            "min_function_loc": 8,
            "min_complexity": 4,
            "recency_days": 14,
            "volatility_z_threshold": 1.5,
            "max_discovery_files": 10000,
        },
        policies={
            "layer_boundaries": [
                {
                    "name": "No DB imports in API layer",
                    "from": "api/**",
                    "deny_import": ["db.*", "models.*", "repositories.*"],
                },
                {
                    "name": "No API imports in DB layer",
                    "from": "db/**",
                    "deny_import": ["api.*", "routes.*", "views.*"],
                },
            ],
            "max_pattern_variants": {
                "error_handling": 2,
                "data_access": 2,
                "api_endpoint": 3,
            },
        },
        fail_on="none",
        guided_thresholds={"green_max": 0.35, "yellow_max": 0.65},
        output_language="de",
    )
)

# ---------------------------------------------------------------------------
# Strict profile — maximum enforcement for mature projects
# ---------------------------------------------------------------------------
_register(
    Profile(
        name="strict",
        description=(
            "Maximum enforcement for mature projects that want zero tolerance "
            "on architectural drift. All signals weighted, fail-on medium."
        ),
        weights={
            "pattern_fragmentation": 0.16,
            "architecture_violation": 0.16,
            "mutant_duplicate": 0.13,
            "temporal_volatility": 0.0,
            "explainability_deficit": 0.09,
            "system_misalignment": 0.08,
            "doc_impl_drift": 0.04,
            "broad_exception_monoculture": 0.04,
            "test_polarity_deficit": 0.04,
            "guard_clause_deficit": 0.03,
            "naming_contract_violation": 0.04,
            "bypass_accumulation": 0.03,
            "exception_contract_drift": 0.03,
            "cohesion_deficit": 0.01,
            "co_change_coupling": 0.005,
        },
        thresholds={
            "similarity_threshold": 0.80,
            "min_function_loc": 10,
            "min_complexity": 5,
            "recency_days": 14,
            "volatility_z_threshold": 1.5,
            "max_discovery_files": 10000,
        },
        fail_on="medium",
    )
)


# ---------------------------------------------------------------------------
# FastAPI profile — tuned for web API projects
# ---------------------------------------------------------------------------
_register(
    Profile(
        name="fastapi",
        description=(
            "Tuned for FastAPI / web-API projects. Upweights architecture "
            "violations and enforces strict layer boundaries between "
            "routes, services, and data layers."
        ),
        weights={
            "pattern_fragmentation": 0.14,
            "architecture_violation": 0.20,
            "mutant_duplicate": 0.13,
            "temporal_volatility": 0.0,
            "explainability_deficit": 0.08,
            "system_misalignment": 0.08,
            "doc_impl_drift": 0.04,
            "broad_exception_monoculture": 0.05,
            "test_polarity_deficit": 0.04,
            "guard_clause_deficit": 0.03,
            "naming_contract_violation": 0.04,
            "bypass_accumulation": 0.03,
            "exception_contract_drift": 0.03,
            "cohesion_deficit": 0.01,
            "co_change_coupling": 0.005,
        },
        thresholds={
            "similarity_threshold": 0.80,
            "min_function_loc": 10,
            "min_complexity": 5,
            "recency_days": 14,
            "volatility_z_threshold": 1.5,
            "max_discovery_files": 10000,
        },
        policies={
            "layer_boundaries": [
                {
                    "name": "No DB imports in routers",
                    "from": "routers/**",
                    "deny_import": ["db.*", "models.*", "repositories.*"],
                },
                {
                    "name": "No HTTP imports in services",
                    "from": "services/**",
                    "deny_import": ["fastapi.*", "starlette.*"],
                },
            ],
        },
        fail_on="none",
    )
)

# ---------------------------------------------------------------------------
# Library profile — tuned for reusable packages
# ---------------------------------------------------------------------------
_register(
    Profile(
        name="library",
        description=(
            "Tuned for reusable Python libraries. Upweights API surface "
            "quality signals (explainability, naming, doc-impl drift) "
            "to keep the public interface clean."
        ),
        weights={
            "pattern_fragmentation": 0.14,
            "architecture_violation": 0.12,
            "mutant_duplicate": 0.10,
            "temporal_volatility": 0.0,
            "explainability_deficit": 0.12,
            "system_misalignment": 0.06,
            "doc_impl_drift": 0.08,
            "broad_exception_monoculture": 0.04,
            "test_polarity_deficit": 0.04,
            "guard_clause_deficit": 0.03,
            "naming_contract_violation": 0.08,
            "bypass_accumulation": 0.03,
            "exception_contract_drift": 0.03,
            "cohesion_deficit": 0.01,
            "co_change_coupling": 0.005,
        },
        thresholds={
            "similarity_threshold": 0.80,
            "min_function_loc": 8,
            "min_complexity": 5,
            "recency_days": 14,
            "volatility_z_threshold": 1.5,
            "max_discovery_files": 10000,
        },
        fail_on="none",
    )
)

# ---------------------------------------------------------------------------
# Monorepo profile — tuned for large multi-package repositories
# ---------------------------------------------------------------------------
_register(
    Profile(
        name="monorepo",
        description=(
            "Tuned for large monorepos with multiple packages. Upweights "
            "architecture violations and co-change coupling; raises file "
            "discovery limits for broad coverage."
        ),
        weights={
            "pattern_fragmentation": 0.14,
            "architecture_violation": 0.18,
            "mutant_duplicate": 0.13,
            "temporal_volatility": 0.0,
            "explainability_deficit": 0.08,
            "system_misalignment": 0.08,
            "doc_impl_drift": 0.04,
            "broad_exception_monoculture": 0.04,
            "test_polarity_deficit": 0.04,
            "guard_clause_deficit": 0.03,
            "naming_contract_violation": 0.04,
            "bypass_accumulation": 0.03,
            "exception_contract_drift": 0.02,
            "cohesion_deficit": 0.01,
            "co_change_coupling": 0.02,
        },
        thresholds={
            "similarity_threshold": 0.80,
            "min_function_loc": 10,
            "min_complexity": 5,
            "recency_days": 14,
            "volatility_z_threshold": 1.5,
            "max_discovery_files": 20000,
        },
        fail_on="none",
    )
)


def get_profile(name: str) -> Profile:
    """Look up a profile by name. Raises ``KeyError`` if unknown."""
    if name not in PROFILES:
        available = ", ".join(sorted(PROFILES))
        raise KeyError(f"Unknown profile '{name}'. Available: {available}")
    return PROFILES[name]


def list_profiles() -> list[Profile]:
    """Return all registered profiles in registration order."""
    return list(PROFILES.values())
