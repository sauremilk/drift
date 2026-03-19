"""Tests for the enhanced AVS (Omnilayer + Hub-dampening + allowed_cross_layer)."""

from __future__ import annotations

from pathlib import Path

from drift.config import DriftConfig, PolicyConfig
from drift.models import ImportInfo, ParseResult
from drift.signals.architecture_violation import (
    _OMNILAYER,
    ArchitectureViolationSignal,
    _infer_layer,
)


def _pr(path: str, imports: list[ImportInfo]) -> ParseResult:
    return ParseResult(file_path=Path(path), language="python", imports=imports)


def _imp(source: str, module: str, line: int = 1) -> ImportInfo:
    return ImportInfo(
        source_file=Path(source),
        imported_module=module,
        imported_names=[],
        line_number=line,
    )


# ── Omnilayer inference ──────────────────────────────────────────────────


class TestOmnilayer:
    def test_config_dir_is_omnilayer(self):
        assert _infer_layer(Path("config/settings.py")) == _OMNILAYER

    def test_utils_dir_is_omnilayer(self):
        assert _infer_layer(Path("utils/helpers.py")) == _OMNILAYER

    def test_schemas_dir_is_omnilayer(self):
        assert _infer_layer(Path("schemas/user.py")) == _OMNILAYER

    def test_exceptions_dir_is_omnilayer(self):
        assert _infer_layer(Path("exceptions/custom.py")) == _OMNILAYER

    def test_api_dir_is_layer_zero(self):
        assert _infer_layer(Path("api/routes.py")) == 0

    def test_services_dir_is_layer_one(self):
        assert _infer_layer(Path("services/payment.py")) == 1

    def test_db_dir_is_layer_two(self):
        assert _infer_layer(Path("db/models.py")) == 2

    def test_unknown_dir_returns_none(self):
        assert _infer_layer(Path("foobar/baz.py")) is None

    def test_omnilayer_import_generates_no_violation(self):
        """Importing from config/ should NOT trigger a violation."""
        results = [
            _pr("db/queries.py", [_imp("db/queries.py", "config.settings")]),
            _pr("config/settings.py", []),
        ]
        signal = ArchitectureViolationSignal()
        findings = signal.analyze(results, {}, DriftConfig())
        upward = [f for f in findings if "Upward" in f.title]
        assert upward == []

    def test_import_from_utils_generates_no_violation(self):
        results = [
            _pr("db/queries.py", [_imp("db/queries.py", "utils.helpers")]),
            _pr("utils/helpers.py", []),
        ]
        signal = ArchitectureViolationSignal()
        findings = signal.analyze(results, {}, DriftConfig())
        upward = [f for f in findings if "Upward" in f.title]
        assert upward == []


# ── Allowed cross-layer patterns ──────────────────────────────────────────


class TestAllowedCrossLayer:
    def test_allowed_pattern_suppresses_finding(self):
        """A pattern in allowed_cross_layer should suppress the violation."""
        results = [
            _pr("db/queries.py", [_imp("db/queries.py", "api.routes")]),
            _pr("api/routes.py", []),
        ]
        cfg = DriftConfig()
        cfg.policies = PolicyConfig(allowed_cross_layer=["db/*"])

        signal = ArchitectureViolationSignal()
        findings = signal.analyze(results, {}, cfg)
        upward = [f for f in findings if "Upward" in f.title]
        assert upward == []

    def test_non_matching_pattern_still_reports(self):
        results = [
            _pr("db/queries.py", [_imp("db/queries.py", "api.routes")]),
            _pr("api/routes.py", []),
        ]
        cfg = DriftConfig()
        cfg.policies = PolicyConfig(allowed_cross_layer=["services/*"])

        signal = ArchitectureViolationSignal()
        findings = signal.analyze(results, {}, cfg)
        upward = [f for f in findings if "Upward" in f.title]
        assert len(upward) >= 1


# ── Hub-dampening ─────────────────────────────────────────────────────────


class TestHubDampening:
    def test_hub_module_gets_reduced_score(self):
        """A frequently-imported target should have its score dampened."""
        # api/routes.py is imported by many db modules → becomes hub
        imports = []
        results = []
        for i in range(10):
            imp = _imp(f"db/q{i}.py", "api.routes")
            imports.append(imp)
            results.append(_pr(f"db/q{i}.py", [imp]))
        results.append(_pr("api/routes.py", []))

        signal = ArchitectureViolationSignal()
        findings = signal.analyze(results, {}, DriftConfig())
        upward = [f for f in findings if "Upward" in f.title]

        # All findings targeting the hub should be dampened
        for f in upward:
            assert f.score <= 0.3, f"Expected dampened score, got {f.score}"
            assert f.metadata.get("hub_dampened") is True
