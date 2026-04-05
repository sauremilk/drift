"""Tests for Missing Authorization signal (MAZ)."""

from __future__ import annotations

from pathlib import Path

from drift.config import DriftConfig
from drift.models import (
    ClassInfo,
    FunctionInfo,
    ImportInfo,
    ParseResult,
    PatternCategory,
    PatternInstance,
    Severity,
    SignalType,
)
from drift.signals.missing_authorization import MissingAuthorizationSignal


def _endpoint_pattern(
    fn_name: str,
    file_path: str,
    line: int,
    *,
    has_auth: bool = False,
    auth_mechanism: str | None = None,
) -> PatternInstance:
    return PatternInstance(
        category=PatternCategory.API_ENDPOINT,
        file_path=Path(file_path),
        function_name=fn_name,
        start_line=line,
        end_line=line + 10,
        fingerprint={
            "has_error_handling": False,
            "has_auth": has_auth,
            "auth_mechanism": auth_mechanism,
            "return_patterns": [],
            "is_async": False,
        },
    )


def _func(
    name: str,
    file_path: str,
    line: int,
    decorators: list[str] | None = None,
    has_docstring: bool = False,
) -> FunctionInfo:
    return FunctionInfo(
        name=name,
        file_path=Path(file_path),
        start_line=line,
        end_line=line + 10,
        language="python",
        decorators=decorators or [],
        has_docstring=has_docstring,
    )


def _imp(source: str, module: str, names: list[str] | None = None) -> ImportInfo:
    return ImportInfo(
        source_file=Path(source),
        imported_module=module,
        imported_names=names or [],
        line_number=1,
    )


# ---------------------------------------------------------------------------
# True positives: should detect missing auth
# ---------------------------------------------------------------------------


class TestMAZTruePositives:
    """Endpoints without auth should be flagged."""

    def test_fastapi_route_no_auth(self) -> None:
        pr = ParseResult(
            file_path=Path("api/routes.py"),
            language="python",
            functions=[_func("get_users", "api/routes.py", 10)],
            imports=[_imp("api/routes.py", "fastapi")],
            patterns=[_endpoint_pattern("get_users", "api/routes.py", 10)],
        )
        signal = MissingAuthorizationSignal()
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 1
        assert findings[0].rule_id == "missing_authz_route"
        assert findings[0].signal_type == SignalType.MISSING_AUTHORIZATION
        assert "get_users" in findings[0].title

    def test_django_route_no_auth(self) -> None:
        pr = ParseResult(
            file_path=Path("views.py"),
            language="python",
            functions=[_func("user_profile", "views.py", 5)],
            imports=[_imp("views.py", "django.http")],
            patterns=[_endpoint_pattern("user_profile", "views.py", 5)],
        )
        signal = MissingAuthorizationSignal()
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 1
        assert "django" in findings[0].metadata["framework"]

    def test_multiple_unauthed_endpoints(self) -> None:
        pr = ParseResult(
            file_path=Path("api.py"),
            language="python",
            functions=[
                _func("list_items", "api.py", 10),
                _func("create_item", "api.py", 20),
                _func("delete_item", "api.py", 30),
            ],
            imports=[_imp("api.py", "fastapi")],
            patterns=[
                _endpoint_pattern("list_items", "api.py", 10),
                _endpoint_pattern("create_item", "api.py", 20),
                _endpoint_pattern("delete_item", "api.py", 30),
            ],
        )
        signal = MissingAuthorizationSignal()
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 3

    def test_flask_route_no_auth(self) -> None:
        pr = ParseResult(
            file_path=Path("app.py"),
            language="python",
            functions=[_func("admin_panel", "app.py", 15)],
            imports=[_imp("app.py", "flask")],
            patterns=[_endpoint_pattern("admin_panel", "app.py", 15)],
        )
        signal = MissingAuthorizationSignal()
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 1
        assert "flask" in findings[0].metadata["framework"]

    def test_async_endpoint_no_auth(self) -> None:
        pr = ParseResult(
            file_path=Path("api/async_views.py"),
            language="python",
            functions=[_func("get_data", "api/async_views.py", 10)],
            imports=[_imp("api/async_views.py", "starlette")],
            patterns=[_endpoint_pattern("get_data", "api/async_views.py", 10)],
        )
        signal = MissingAuthorizationSignal()
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 1


# ---------------------------------------------------------------------------
# True negatives: should NOT flag these
# ---------------------------------------------------------------------------


class TestMAZTrueNegatives:
    """Properly secured endpoints should not be flagged."""

    def test_endpoint_with_auth_decorator(self) -> None:
        pr = ParseResult(
            file_path=Path("api.py"),
            language="python",
            functions=[_func("get_users", "api.py", 10, decorators=["login_required"])],
            imports=[_imp("api.py", "django.http")],
            patterns=[
                _endpoint_pattern(
                    "get_users", "api.py", 10,
                    has_auth=True, auth_mechanism="decorator",
                )
            ],
        )
        signal = MissingAuthorizationSignal()
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 0

    def test_endpoint_with_body_auth(self) -> None:
        pr = ParseResult(
            file_path=Path("api.py"),
            language="python",
            functions=[_func("get_users", "api.py", 10)],
            imports=[_imp("api.py", "fastapi")],
            patterns=[
                _endpoint_pattern(
                    "get_users", "api.py", 10,
                    has_auth=True, auth_mechanism="body_name",
                )
            ],
        )
        signal = MissingAuthorizationSignal()
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 0

    def test_health_check_endpoint(self) -> None:
        pr = ParseResult(
            file_path=Path("api.py"),
            language="python",
            functions=[_func("health_check", "api.py", 10)],
            imports=[_imp("api.py", "fastapi")],
            patterns=[_endpoint_pattern("health_check", "api.py", 10)],
        )
        signal = MissingAuthorizationSignal()
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 0

    def test_ping_endpoint(self) -> None:
        pr = ParseResult(
            file_path=Path("api.py"),
            language="python",
            functions=[_func("ping", "api.py", 10)],
            imports=[_imp("api.py", "fastapi")],
            patterns=[_endpoint_pattern("ping", "api.py", 10)],
        )
        signal = MissingAuthorizationSignal()
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 0

    def test_metrics_endpoint(self) -> None:
        pr = ParseResult(
            file_path=Path("api.py"),
            language="python",
            functions=[_func("metrics", "api.py", 10)],
            imports=[_imp("api.py", "fastapi")],
            patterns=[_endpoint_pattern("metrics", "api.py", 10)],
        )
        signal = MissingAuthorizationSignal()
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 0

    def test_openapi_docs_endpoint(self) -> None:
        pr = ParseResult(
            file_path=Path("api.py"),
            language="python",
            functions=[_func("openapi_schema", "api.py", 10)],
            imports=[_imp("api.py", "fastapi")],
            patterns=[_endpoint_pattern("openapi_schema", "api.py", 10)],
        )
        signal = MissingAuthorizationSignal()
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 0

    def test_test_file_skipped(self) -> None:
        pr = ParseResult(
            file_path=Path("tests/test_api.py"),
            language="python",
            functions=[_func("get_users", "tests/test_api.py", 10)],
            imports=[_imp("tests/test_api.py", "fastapi")],
            patterns=[_endpoint_pattern("get_users", "tests/test_api.py", 10)],
        )
        signal = MissingAuthorizationSignal()
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 0

    def test_non_python_skipped(self) -> None:
        pr = ParseResult(
            file_path=Path("api.ts"),
            language="typescript",
            functions=[],
            imports=[],
            patterns=[_endpoint_pattern("getUsers", "api.ts", 10)],
        )
        signal = MissingAuthorizationSignal()
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 0

    def test_class_view_with_auth_mixin(self) -> None:
        pr = ParseResult(
            file_path=Path("views.py"),
            language="python",
            functions=[_func("UserView.get", "views.py", 10)],
            classes=[
                ClassInfo(
                    name="UserView",
                    file_path=Path("views.py"),
                    start_line=5,
                    end_line=30,
                    language="python",
                    bases=["LoginRequiredMixin", "View"],
                )
            ],
            imports=[_imp("views.py", "django.views")],
            patterns=[_endpoint_pattern("UserView.get", "views.py", 10)],
        )
        signal = MissingAuthorizationSignal()
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 0

    def test_documented_publishable_key_endpoint_is_downgraded(self) -> None:
        pr = ParseResult(
            file_path=Path("backend/ee/onyx/server/billing/api.py"),
            language="python",
            functions=[
                _func(
                    "get_stripe_publishable_key",
                    "backend/ee/onyx/server/billing/api.py",
                    10,
                    has_docstring=True,
                )
            ],
            imports=[_imp("backend/ee/onyx/server/billing/api.py", "fastapi")],
            patterns=[
                _endpoint_pattern(
                    "get_stripe_publishable_key",
                    "backend/ee/onyx/server/billing/api.py",
                    10,
                )
            ],
        )
        signal = MissingAuthorizationSignal()
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 1
        assert findings[0].severity == Severity.LOW
        assert findings[0].metadata["public_safe_documented"] is True

    def test_publishable_key_without_docstring_stays_high(self) -> None:
        pr = ParseResult(
            file_path=Path("backend/ee/onyx/server/billing/api.py"),
            language="python",
            functions=[
                _func(
                    "get_stripe_publishable_key",
                    "backend/ee/onyx/server/billing/api.py",
                    10,
                    has_docstring=False,
                )
            ],
            imports=[_imp("backend/ee/onyx/server/billing/api.py", "fastapi")],
            patterns=[
                _endpoint_pattern(
                    "get_stripe_publishable_key",
                    "backend/ee/onyx/server/billing/api.py",
                    10,
                )
            ],
        )
        signal = MissingAuthorizationSignal()
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 1
        assert findings[0].severity == Severity.HIGH
        assert findings[0].metadata["public_safe_documented"] is False


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestMAZEdgeCases:
    """Edge cases and framework detection."""

    def test_metadata_includes_cwe(self) -> None:
        pr = ParseResult(
            file_path=Path("api.py"),
            language="python",
            functions=[_func("delete_user", "api.py", 10)],
            imports=[_imp("api.py", "fastapi")],
            patterns=[_endpoint_pattern("delete_user", "api.py", 10)],
        )
        signal = MissingAuthorizationSignal()
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 1
        assert findings[0].metadata["cwe"] == "CWE-862"

    def test_fix_suggestion_framework_specific(self) -> None:
        pr = ParseResult(
            file_path=Path("api.py"),
            language="python",
            functions=[_func("get_item", "api.py", 10)],
            imports=[_imp("api.py", "fastapi")],
            patterns=[_endpoint_pattern("get_item", "api.py", 10)],
        )
        signal = MissingAuthorizationSignal()
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 1
        assert findings[0].fix is not None
        assert "Depends" in findings[0].fix

    def test_empty_parse_results(self) -> None:
        signal = MissingAuthorizationSignal()
        findings = signal.analyze([], {}, DriftConfig())
        assert len(findings) == 0

    def test_no_endpoints(self) -> None:
        pr = ParseResult(
            file_path=Path("utils.py"),
            language="python",
            functions=[_func("helper", "utils.py", 10)],
            imports=[],
            patterns=[],
        )
        signal = MissingAuthorizationSignal()
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 0

    def test_custom_allowlist(self) -> None:
        config = DriftConfig()
        config.thresholds.maz_public_endpoint_allowlist.append("public_api")
        pr = ParseResult(
            file_path=Path("api.py"),
            language="python",
            functions=[_func("public_api_list", "api.py", 10)],
            imports=[_imp("api.py", "fastapi")],
            patterns=[_endpoint_pattern("public_api_list", "api.py", 10)],
        )
        signal = MissingAuthorizationSignal()
        findings = signal.analyze([pr], {}, config)
        assert len(findings) == 0
