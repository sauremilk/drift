"""AVS mutation tests — inject targeted layer violations and verify detection.

Phase 2.3 of the drift optimization plan: validate that the Architecture
Violation Signal correctly detects specific violation patterns and that
omnilayer / hub-dampening behave as intended.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from drift.config import DriftConfig, PolicyConfig
from drift.models import ImportInfo, ParseResult, Severity
from drift.signals.architecture_violation import ArchitectureViolationSignal

# ── Helpers ───────────────────────────────────────────────────────────────


def _pr(path: str, imports: list[ImportInfo]) -> ParseResult:
    return ParseResult(file_path=Path(path), language="python", imports=imports)


def _imp(source: str, module: str, line: int = 1) -> ImportInfo:
    return ImportInfo(
        source_file=Path(source),
        imported_module=module,
        imported_names=[],
        line_number=line,
    )


# ── Mutation 1: DB → API (clear upward violation) ────────────────────────


class TestMutationDbImportsApi:
    """Database layer (layer 2) importing from API layer (layer 0)."""

    def test_storage_imports_routes(self):
        results = [
            _pr("storage/repo.py", [_imp("storage/repo.py", "routes.api_handler")]),
            _pr("routes/api_handler.py", []),
        ]
        signal = ArchitectureViolationSignal()
        findings = signal.analyze(results, {}, DriftConfig())
        upward = [f for f in findings if "Upward" in f.title]
        assert len(upward) >= 1
        assert upward[0].fix is not None

    def test_repositories_imports_views(self):
        results = [
            _pr(
                "repositories/user_repo.py",
                [_imp("repositories/user_repo.py", "views.dashboard")],
            ),
            _pr("views/dashboard.py", []),
        ]
        signal = ArchitectureViolationSignal()
        findings = signal.analyze(results, {}, DriftConfig())
        upward = [f for f in findings if "Upward" in f.title]
        assert len(upward) >= 1

    def test_infrastructure_imports_controllers(self):
        results = [
            _pr("infrastructure/cache.py", [_imp("infrastructure/cache.py", "controllers.main")]),
            _pr("controllers/main.py", []),
        ]
        signal = ArchitectureViolationSignal()
        findings = signal.analyze(results, {}, DriftConfig())
        upward = [f for f in findings if "Upward" in f.title]
        assert len(upward) >= 1


# ── Mutation 2: DB → Services (upward violation, 1 layer gap) ────────────


class TestMutationDbImportsServices:
    """Database layer (layer 2) importing from service layer (layer 1)."""

    def test_models_imports_services(self):
        # models/ is now Omnilayer (ADR-036), so no upward-import violation
        results = [
            _pr("models/user.py", [_imp("models/user.py", "services.auth")]),
            _pr("services/auth.py", []),
        ]
        signal = ArchitectureViolationSignal()
        findings = signal.analyze(results, {}, DriftConfig())
        upward = [f for f in findings if "Upward" in f.title]
        assert len(upward) == 0

    def test_db_imports_domain(self):
        results = [
            _pr("db/queries.py", [_imp("db/queries.py", "domain.entities")]),
            _pr("domain/entities.py", []),
        ]
        signal = ArchitectureViolationSignal()
        findings = signal.analyze(results, {}, DriftConfig())
        upward = [f for f in findings if "Upward" in f.title]
        assert len(upward) >= 1


# ── Mutation 3: Valid directions (should NOT trigger) ─────────────────────


class TestValidDirections:
    """Correct layering directions — no violations expected."""

    def test_api_imports_services(self):
        results = [
            _pr("api/routes.py", [_imp("api/routes.py", "services.payment")]),
            _pr("services/payment.py", []),
        ]
        signal = ArchitectureViolationSignal()
        findings = signal.analyze(results, {}, DriftConfig())
        upward = [f for f in findings if "Upward" in f.title]
        assert upward == []

    def test_services_imports_db(self):
        results = [
            _pr("services/user.py", [_imp("services/user.py", "db.models")]),
            _pr("db/models.py", []),
        ]
        signal = ArchitectureViolationSignal()
        findings = signal.analyze(results, {}, DriftConfig())
        upward = [f for f in findings if "Upward" in f.title]
        assert upward == []

    def test_api_imports_db(self):
        """Skipping a layer is allowed — only upward matters."""
        results = [
            _pr("api/routes.py", [_imp("api/routes.py", "db.models")]),
            _pr("db/models.py", []),
        ]
        signal = ArchitectureViolationSignal()
        findings = signal.analyze(results, {}, DriftConfig())
        upward = [f for f in findings if "Upward" in f.title]
        assert upward == []

    def test_same_layer_no_violation(self):
        results = [
            _pr("services/a.py", [_imp("services/a.py", "services.b")]),
            _pr("services/b.py", []),
        ]
        signal = ArchitectureViolationSignal()
        findings = signal.analyze(results, {}, DriftConfig())
        upward = [f for f in findings if "Upward" in f.title]
        assert upward == []


# ── Mutation 4: Omnilayer NEVER triggers violations ──────────────────────


class TestOmnilayerMutations:
    """Cross-cutting modules can be imported from any layer without violations."""

    @pytest.mark.parametrize(
        "omni_dir",
        [
            "config",
            "utils",
            "helpers",
            "constants",
            "types",
            "common",
            "shared",
            "base",
            "exceptions",
            "errors",
            "enums",
            "schemas",
        ],
    )
    def test_db_importing_omnilayer_no_violation(self, omni_dir: str):
        results = [
            _pr("db/queries.py", [_imp("db/queries.py", f"{omni_dir}.settings")]),
            _pr(f"{omni_dir}/settings.py", []),
        ]
        signal = ArchitectureViolationSignal()
        findings = signal.analyze(results, {}, DriftConfig())
        upward = [f for f in findings if "Upward" in f.title]
        assert upward == [], f"Omnilayer dir '{omni_dir}' should not cause violations"

    @pytest.mark.parametrize(
        "omni_dir",
        [
            "config",
            "utils",
            "helpers",
            "constants",
            "types",
            "common",
            "shared",
            "base",
            "exceptions",
            "errors",
            "enums",
            "schemas",
        ],
    )
    def test_omnilayer_importing_anything_no_upward(self, omni_dir: str):
        """Omnilayer source importing from API should not trigger (both sides omnilayer check)."""
        results = [
            _pr(f"{omni_dir}/helper.py", [_imp(f"{omni_dir}/helper.py", "api.routes")]),
            _pr("api/routes.py", []),
        ]
        signal = ArchitectureViolationSignal()
        findings = signal.analyze(results, {}, DriftConfig())
        upward = [f for f in findings if "Upward" in f.title]
        assert upward == [], f"Omnilayer source '{omni_dir}' should not trigger upward violations"


# ── Mutation 5: Circular dependencies ────────────────────────────────────


class TestCircularMutations:
    """Circular dependency detection with fix text."""

    def test_simple_cycle_detected(self):
        results = [
            _pr("services/a.py", [_imp("services/a.py", "services.b")]),
            _pr("services/b.py", [_imp("services/b.py", "services.a")]),
        ]
        signal = ArchitectureViolationSignal()
        findings = signal.analyze(results, {}, DriftConfig())
        circular = [f for f in findings if "Circular" in f.title]
        assert len(circular) >= 1
        assert circular[0].fix is not None
        assert "Circular dependency" in circular[0].fix or "cycle" in circular[0].fix.lower()

    def test_three_module_cycle(self):
        results = [
            _pr("services/a.py", [_imp("services/a.py", "services.b")]),
            _pr("services/b.py", [_imp("services/b.py", "services.c")]),
            _pr("services/c.py", [_imp("services/c.py", "services.a")]),
        ]
        signal = ArchitectureViolationSignal()
        findings = signal.analyze(results, {}, DriftConfig())
        circular = [f for f in findings if "Circular" in f.title]
        assert len(circular) >= 1
        assert circular[0].metadata.get("cycle") is not None
        assert len(circular[0].related_files) >= 1

    def test_no_cycle_in_dag(self):
        results = [
            _pr("services/a.py", [_imp("services/a.py", "services.b")]),
            _pr("services/b.py", [_imp("services/b.py", "services.c")]),
            _pr("services/c.py", []),
        ]
        signal = ArchitectureViolationSignal()
        findings = signal.analyze(results, {}, DriftConfig())
        circular = [f for f in findings if "Circular" in f.title]
        assert circular == []


# ── Mutation 6: Hub-dampening calibration ────────────────────────────────


class TestHubDampeningCalibration:
    """Verify hub-dampening reduces scores proportionally."""

    def test_non_hub_gets_full_score(self):
        """A target imported only once should NOT be dampened."""
        results = [
            _pr("db/queries.py", [_imp("db/queries.py", "api.routes")]),
            _pr("api/routes.py", []),
        ]
        signal = ArchitectureViolationSignal()
        findings = signal.analyze(results, {}, DriftConfig())
        upward = [f for f in findings if "Upward" in f.title]
        assert len(upward) >= 1
        # Non-hub → full base score (0.5)
        assert upward[0].score == 0.5
        assert upward[0].metadata.get("hub_dampened") is False

    def test_hub_score_is_half_of_base(self):
        """Hub targets should get exactly 0.5× the base score."""
        # Make api/routes.py a hub by having many importers
        results = []
        for i in range(15):
            results.append(_pr(f"db/q{i}.py", [_imp(f"db/q{i}.py", "api.routes")]))
        results.append(_pr("api/routes.py", []))

        signal = ArchitectureViolationSignal()
        findings = signal.analyze(results, {}, DriftConfig())
        upward = [f for f in findings if "Upward" in f.title]
        assert len(upward) >= 1
        for f in upward:
            assert f.score == 0.25, f"Expected 0.5 × 0.5 = 0.25, got {f.score}"
            assert f.metadata.get("hub_dampened") is True


# ── Mutation 7: Policy violations ────────────────────────────────────────


class TestPolicyViolationMutations:
    """Policy-based boundary rules with fix text."""

    def test_policy_violation_has_fix(self):
        from drift.config import LayerBoundary

        cfg = DriftConfig()
        cfg.policies = PolicyConfig(
            layer_boundaries=[
                LayerBoundary(
                    name="no-db-in-api",
                    **{"from": "api/*"},
                    deny_import=["db.*", "models.*"],
                )
            ]
        )
        results = [
            _pr("api/routes.py", [_imp("api/routes.py", "db.queries", line=42)]),
            _pr("db/queries.py", []),
        ]
        signal = ArchitectureViolationSignal()
        findings = signal.analyze(results, {}, cfg)
        policy = [f for f in findings if "Policy" in f.title]
        assert len(policy) >= 1
        assert policy[0].fix is not None
        assert "Remove import" in policy[0].fix
        assert policy[0].severity == Severity.HIGH


class TestCrossPassDeduplication:
    """Ensure policy + inferred-layer checks do not emit duplicate AVS findings."""

    def test_policy_and_inferred_same_edge_are_deduplicated(self):
        from drift.config import LayerBoundary

        cfg = DriftConfig()
        cfg.policies = PolicyConfig(
            layer_boundaries=[
                LayerBoundary(
                    name="no-api-import-in-db",
                    **{"from": "db/*"},
                    deny_import=["api.*"],
                )
            ]
        )

        results = [
            _pr("db/queries.py", [_imp("db/queries.py", "api.routes", line=42)]),
            _pr("api/routes.py", []),
        ]

        signal = ArchitectureViolationSignal()
        findings = signal.analyze(results, {}, cfg)

        assert len(findings) == 1
        assert findings[0].file_path == Path("db/queries.py")
        assert findings[0].start_line == 42


# ── Mutation 8: Fix text format validation ───────────────────────────────


class TestFixTextFormat:
    """All AVS finding types must include actionable fix text."""

    def test_upward_fix_mentions_service_layer(self):
        results = [
            _pr("db/queries.py", [_imp("db/queries.py", "api.routes")]),
            _pr("api/routes.py", []),
        ]
        signal = ArchitectureViolationSignal()
        findings = signal.analyze(results, {}, DriftConfig())
        upward = [f for f in findings if "Upward" in f.title]
        assert len(upward) >= 1
        fix = (upward[0].fix or "").lower()
        assert "service layer" in fix or "interface" in fix

    def test_circular_fix_mentions_dependency_inversion(self):
        results = [
            _pr("services/a.py", [_imp("services/a.py", "services.b")]),
            _pr("services/b.py", [_imp("services/b.py", "services.a")]),
        ]
        signal = ArchitectureViolationSignal()
        findings = signal.analyze(results, {}, DriftConfig())
        circular = [f for f in findings if "Circular" in f.title]
        assert len(circular) >= 1
        fix = (circular[0].fix or "").lower()
        assert "interface" in fix or "dependency inversion" in fix
