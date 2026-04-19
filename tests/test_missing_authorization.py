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
    route: str = "",
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
            "route": route,
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
    parameters: list[str] | None = None,
) -> FunctionInfo:
    return FunctionInfo(
        name=name,
        file_path=Path(file_path),
        start_line=line,
        end_line=line + 10,
        language="python",
        parameters=parameters or [],
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
                    "get_users",
                    "api.py",
                    10,
                    has_auth=True,
                    auth_mechanism="decorator",
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
                    "get_users",
                    "api.py",
                    10,
                    has_auth=True,
                    auth_mechanism="body_name",
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

    def test_test_file_can_be_included_with_reduced_severity(self) -> None:
        pr = ParseResult(
            file_path=Path("tests/test_api.py"),
            language="python",
            functions=[_func("get_users", "tests/test_api.py", 10)],
            imports=[_imp("tests/test_api.py", "fastapi")],
            patterns=[_endpoint_pattern("get_users", "tests/test_api.py", 10)],
        )
        signal = MissingAuthorizationSignal()
        findings = signal.analyze([pr], {}, DriftConfig(test_file_handling="reduce_severity"))
        assert len(findings) == 1
        assert findings[0].severity == Severity.LOW
        assert findings[0].metadata.get("finding_context") == "test"

    def test_non_python_skipped(self) -> None:
        pr = ParseResult(
            file_path=Path("api.rs"),
            language="rust",
            functions=[],
            imports=[],
            patterns=[_endpoint_pattern("getUsers", "api.rs", 10)],
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
        assert findings[0].severity == Severity.CRITICAL
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

    def test_deduplicates_same_endpoint_and_prefers_specific_route(self) -> None:
        """MAZ should emit one finding per endpoint symbol and keep the best route metadata."""
        pr = ParseResult(
            file_path=Path("extensions/msteams/src/monitor.ts"),
            language="typescript",
            functions=[
                FunctionInfo(
                    name="monitorMSTeamsProvider",
                    file_path=Path("extensions/msteams/src/monitor.ts"),
                    start_line=80,
                    end_line=140,
                    language="typescript",
                    parameters=["req", "res"],
                )
            ],
            imports=[_imp("extensions/msteams/src/monitor.ts", "express")],
            patterns=[
                _endpoint_pattern(
                    "monitorMSTeamsProvider",
                    "extensions/msteams/src/monitor.ts",
                    90,
                    route="",
                ),
                _endpoint_pattern(
                    "monitorMSTeamsProvider",
                    "extensions/msteams/src/monitor.ts",
                    120,
                    route="/api/messages",
                ),
            ],
        )

        signal = MissingAuthorizationSignal()
        findings = signal.analyze([pr], {}, DriftConfig())

        assert len(findings) == 1
        assert findings[0].symbol == "monitorMSTeamsProvider"
        assert findings[0].metadata["route"] == "/api/messages"

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

    def test_public_endpoint_allowlisted_by_default(self) -> None:
        """Endpoints with 'public' or 'anon' in name should be allowlisted (#148)."""
        names = ["get_public_prices", "create_anon_session", "anon_coach", "security_txt"]
        for name in names:
            pr = ParseResult(
                file_path=Path("api.py"),
                language="python",
                functions=[_func(name, "api.py", 10)],
                imports=[_imp("api.py", "fastapi")],
                patterns=[_endpoint_pattern(name, "api.py", 10)],
            )
            signal = MissingAuthorizationSignal()
            findings = signal.analyze([pr], {}, DriftConfig())
            assert len(findings) == 0, f"'{name}' should be allowlisted by default"

    def test_dev_tool_path_skipped(self) -> None:
        """Endpoints in dev/internal tool directories should be skipped (#148)."""
        pr = ParseResult(
            file_path=Path("internal/tools/api.py"),
            language="python",
            functions=[_func("run_pipeline", "internal/tools/api.py", 10)],
            imports=[_imp("internal/tools/api.py", "fastapi")],
            patterns=[_endpoint_pattern("run_pipeline", "internal/tools/api.py", 10)],
        )
        signal = MissingAuthorizationSignal()
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 0

    def test_cli_serving_path_skipped(self) -> None:
        """Local CLI serving modules should be skipped for MAZ (#167)."""
        file_path = "src/transformers/cli/serving/server.py"
        endpoint_names = [
            "chat_completions",
            "responses",
            "load_model",
            "list_models",
            "generate",
        ]
        pr = ParseResult(
            file_path=Path(file_path),
            language="python",
            functions=[
                _func(name, file_path, idx * 10) for idx, name in enumerate(endpoint_names, start=1)
            ],
            imports=[_imp(file_path, "fastapi")],
            patterns=[
                _endpoint_pattern(name, file_path, idx * 10)
                for idx, name in enumerate(endpoint_names, start=1)
            ],
        )
        signal = MissingAuthorizationSignal()
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 0

    def test_non_dev_path_still_flagged(self) -> None:
        """Endpoints in production paths should still be flagged."""
        pr = ParseResult(
            file_path=Path("src/api/routes.py"),
            language="python",
            functions=[_func("delete_user", "src/api/routes.py", 10)],
            imports=[_imp("src/api/routes.py", "fastapi")],
            patterns=[_endpoint_pattern("delete_user", "src/api/routes.py", 10)],
        )
        signal = MissingAuthorizationSignal()
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 1

    def test_typescript_loopback_only_endpoint_is_suppressed(self) -> None:
        """Loopback-only bound TS endpoints should not be flagged as missing auth."""
        pr = ParseResult(
            file_path=Path("src/media/server.ts"),
            language="typescript",
            functions=[
                FunctionInfo(
                    name="attachMediaRoutes",
                    file_path=Path("src/media/server.ts"),
                    start_line=10,
                    end_line=120,
                    language="typescript",
                    parameters=["app"],
                )
            ],
            imports=[_imp("src/media/server.ts", "express")],
            patterns=[
                PatternInstance(
                    category=PatternCategory.API_ENDPOINT,
                    file_path=Path("src/media/server.ts"),
                    function_name="attachMediaRoutes",
                    start_line=40,
                    end_line=100,
                    fingerprint={
                        "method": "GET",
                        "route": "/media/:id",
                        "framework": "express",
                        "has_auth": False,
                        "loopback_only": True,
                    },
                )
            ],
        )

        signal = MissingAuthorizationSignal()
        findings = signal.analyze([pr], {}, DriftConfig())
        assert findings == []

    def test_serving_path_without_cli_still_flagged(self) -> None:
        """Serving modules outside CLI context should still be flagged."""
        pr = ParseResult(
            file_path=Path("src/transformers/serving/server.py"),
            language="python",
            functions=[_func("chat_completions", "src/transformers/serving/server.py", 10)],
            imports=[_imp("src/transformers/serving/server.py", "fastapi")],
            patterns=[
                _endpoint_pattern(
                    "chat_completions",
                    "src/transformers/serving/server.py",
                    10,
                )
            ],
        )
        signal = MissingAuthorizationSignal()
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 1

    def test_decorator_fallback_detects_endpoint_without_pattern(self) -> None:
        """Decorator fallback should recover endpoints when ingestion misses patterns."""
        pr = ParseResult(
            file_path=Path("api/routes.py"),
            language="python",
            functions=[
                _func(
                    "get_orders",
                    "api/routes.py",
                    12,
                    decorators=["router.get('/orders')"],
                )
            ],
            imports=[_imp("api/routes.py", "fastapi")],
            patterns=[],
        )
        signal = MissingAuthorizationSignal()
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 1
        assert findings[0].metadata["detection_source"] == "decorator_fallback"

    def test_decorator_fallback_skips_auth_decorator(self) -> None:
        """Decorator fallback should not flag routes with explicit auth decorators."""
        pr = ParseResult(
            file_path=Path("api/routes.py"),
            language="python",
            functions=[
                _func(
                    "get_orders",
                    "api/routes.py",
                    12,
                    decorators=[
                        "router.get('/orders')",
                        "login_required",
                    ],
                )
            ],
            imports=[_imp("api/routes.py", "fastapi")],
            patterns=[],
        )
        signal = MissingAuthorizationSignal()
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 0

    def test_decorator_fallback_skips_auth_like_parameter(self) -> None:
        """Fallback should not flag routes with injected auth-like parameters."""
        pr = ParseResult(
            file_path=Path("api/routes.py"),
            language="python",
            functions=[
                _func(
                    "get_orders",
                    "api/routes.py",
                    12,
                    decorators=["router.get('/orders')"],
                    parameters=["current_user"],
                )
            ],
            imports=[_imp("api/routes.py", "fastapi")],
            patterns=[],
        )
        signal = MissingAuthorizationSignal()
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 0

    def test_decorator_fallback_skips_camel_case_auth_parameter(self) -> None:
        """Fallback should normalize camelCase auth-context parameters."""
        pr = ParseResult(
            file_path=Path("api/routes.py"),
            language="python",
            functions=[
                _func(
                    "get_orders",
                    "api/routes.py",
                    12,
                    decorators=["router.get('/orders')"],
                    parameters=["currentUserContext"],
                )
            ],
            imports=[_imp("api/routes.py", "fastapi")],
            patterns=[],
        )
        signal = MissingAuthorizationSignal()
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 0

    def test_decorator_fallback_skips_access_token_parameter(self) -> None:
        """Fallback should treat access-token style params as auth context."""
        pr = ParseResult(
            file_path=Path("api/routes.py"),
            language="python",
            functions=[
                _func(
                    "get_orders",
                    "api/routes.py",
                    12,
                    decorators=["router.get('/orders')"],
                    parameters=["access_token"],
                )
            ],
            imports=[_imp("api/routes.py", "fastapi")],
            patterns=[],
        )
        signal = MissingAuthorizationSignal()
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 0

    def test_decorator_fallback_keeps_user_id_path_param_flagged(self) -> None:
        """Path params like user_id must not be mistaken for auth context."""
        pr = ParseResult(
            file_path=Path("api/routes.py"),
            language="python",
            functions=[
                _func(
                    "get_user",
                    "api/routes.py",
                    12,
                    decorators=["router.get('/users/{user_id}')"],
                    parameters=["user_id"],
                )
            ],
            imports=[_imp("api/routes.py", "fastapi")],
            patterns=[],
        )
        signal = MissingAuthorizationSignal()
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 1
        assert findings[0].metadata["detection_source"] == "decorator_fallback"

    def test_decorator_fallback_keeps_user_id_token_param_flagged(self) -> None:
        """Composite path-style params must not be auto-suppressed as auth context."""
        pr = ParseResult(
            file_path=Path("api/routes.py"),
            language="python",
            functions=[
                _func(
                    "get_user",
                    "api/routes.py",
                    12,
                    decorators=["router.get('/users/{user_id_token}')"],
                    parameters=["user_id_token"],
                )
            ],
            imports=[_imp("api/routes.py", "fastapi")],
            patterns=[],
        )
        signal = MissingAuthorizationSignal()
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 1
        assert findings[0].metadata["detection_source"] == "decorator_fallback"

    def test_typescript_unknown_framework_suppresses_non_route_like_pattern(self) -> None:
        """Unknown TS framework must not flag generic method calls as endpoints."""
        pr = ParseResult(
            file_path=Path("extensions/active-memory/index.ts"),
            language="typescript",
            functions=[
                FunctionInfo(
                    name="getCachedResult",
                    file_path=Path("extensions/active-memory/index.ts"),
                    start_line=20,
                    end_line=40,
                    language="typescript",
                )
            ],
            imports=[],
            patterns=[
                PatternInstance(
                    category=PatternCategory.API_ENDPOINT,
                    file_path=Path("extensions/active-memory/index.ts"),
                    function_name="getCachedResult",
                    start_line=24,
                    end_line=24,
                    fingerprint={
                        "method": "GET",
                        "route": "cache_key",
                        "framework": "express",
                        "has_auth": False,
                    },
                )
            ],
        )

        signal = MissingAuthorizationSignal()
        findings = signal.analyze([pr], {}, DriftConfig())
        assert findings == []

    def test_typescript_unknown_framework_keeps_route_like_path(self) -> None:
        """Unknown TS framework should still flag clear HTTP route paths."""
        pr = ParseResult(
            file_path=Path("src/api/routes.ts"),
            language="typescript",
            functions=[
                FunctionInfo(
                    name="listUsers",
                    file_path=Path("src/api/routes.ts"),
                    start_line=10,
                    end_line=30,
                    language="typescript",
                    parameters=["req", "res"],
                )
            ],
            imports=[],
            patterns=[
                PatternInstance(
                    category=PatternCategory.API_ENDPOINT,
                    file_path=Path("src/api/routes.ts"),
                    function_name="listUsers",
                    start_line=14,
                    end_line=14,
                    fingerprint={
                        "method": "GET",
                        "route": "/users",
                        "framework": "express",
                        "has_auth": False,
                    },
                )
            ],
        )

        signal = MissingAuthorizationSignal()
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 1
        assert findings[0].metadata["framework"] == "unknown"

    def test_typescript_unknown_framework_skips_outbound_api_client_signature(self) -> None:
        """Unknown TS route-like paths in outbound client helpers should be suppressed."""
        pr = ParseResult(
            file_path=Path("extensions/discord/src/send.channels.ts"),
            language="typescript",
            functions=[
                FunctionInfo(
                    name="setChannelPermissionDiscord",
                    file_path=Path("extensions/discord/src/send.channels.ts"),
                    start_line=10,
                    end_line=45,
                    language="typescript",
                    parameters=["rest", "payload"],
                )
            ],
            imports=[],
            patterns=[
                PatternInstance(
                    category=PatternCategory.API_ENDPOINT,
                    file_path=Path("extensions/discord/src/send.channels.ts"),
                    function_name="setChannelPermissionDiscord",
                    start_line=14,
                    end_line=14,
                    fingerprint={
                        "method": "PUT",
                        "route": "/channels/${payload.channelId}/permissions/${payload.targetId}",
                        "framework": "express",
                        "has_auth": False,
                    },
                )
            ],
        )

        signal = MissingAuthorizationSignal()
        findings = signal.analyze([pr], {}, DriftConfig())
        assert findings == []

    def test_a2a_protocol_endpoints_allowlisted_by_default(self) -> None:
        """A2A-protocol endpoints are always intentionally public and must not be flagged (#391)."""
        cases = [
            # Function-name match: agent_card -> agentcard
            ("agent_card", "src/drift/serve/app.py", 41, "/.well-known/agent-card.json"),
            # Function-name match: a2a_endpoint -> a2aendpoint
            ("a2a_endpoint", "src/drift/serve/app.py", 46, "/a2a/v1"),
        ]
        for fn_name, file_path, line, route in cases:
            pr = ParseResult(
                file_path=Path(file_path),
                language="python",
                functions=[_func(fn_name, file_path, line)],
                imports=[_imp(file_path, "fastapi")],
                patterns=[_endpoint_pattern(fn_name, file_path, line, route=route)],
            )
            signal = MissingAuthorizationSignal()
            findings = signal.analyze([pr], {}, DriftConfig())
            assert findings == [], (
                f"A2A endpoint '{fn_name}' (route '{route}') should be allowlisted by default"
            )

    def test_route_allowlist_skips_login_path_even_without_name_hint(self) -> None:
        """Public route allowlist should also work on route path metadata."""
        pr = ParseResult(
            file_path=Path("src/api/routes.ts"),
            language="typescript",
            functions=[
                FunctionInfo(
                    name="handleAuthRequest",
                    file_path=Path("src/api/routes.ts"),
                    start_line=10,
                    end_line=30,
                    language="typescript",
                )
            ],
            imports=[],
            patterns=[
                PatternInstance(
                    category=PatternCategory.API_ENDPOINT,
                    file_path=Path("src/api/routes.ts"),
                    function_name="handleAuthRequest",
                    start_line=14,
                    end_line=14,
                    fingerprint={
                        "method": "POST",
                        "route": "/oauth/callback",
                        "framework": "express",
                        "has_auth": False,
                    },
                )
            ],
        )

        signal = MissingAuthorizationSignal()
        findings = signal.analyze([pr], {}, DriftConfig())
        assert findings == []


# ---------------------------------------------------------------------------
# Negative property checks
# ---------------------------------------------------------------------------


class TestMAZNegativeProperties:
    """Verify that MAZ signal outputs never contain None or invalid states."""

    def test_unauthed_findings_not_none(self) -> None:
        pr = ParseResult(
            file_path=Path("api/routes.py"),
            language="python",
            functions=[_func("get_users", "api/routes.py", 10)],
            imports=[_imp("api/routes.py", "fastapi")],
            patterns=[_endpoint_pattern("get_users", "api/routes.py", 10)],
        )
        signal = MissingAuthorizationSignal()
        findings = signal.analyze([pr], {}, DriftConfig())
        assert not any(f is None for f in findings)
        assert not any(f.rule_id is None for f in findings)

    def test_authed_endpoint_no_findings(self) -> None:
        pr = ParseResult(
            file_path=Path("api/safe.py"),
            language="python",
            functions=[_func("get_users", "api/safe.py", 10)],
            imports=[_imp("api/safe.py", "fastapi")],
            patterns=[_endpoint_pattern(  # noqa: E501
                "get_users", "api/safe.py", 10, has_auth=True, auth_mechanism="bearer")],
        )
        signal = MissingAuthorizationSignal()
        findings = signal.analyze([pr], {}, DriftConfig())
        assert not findings
        assert not any(f is None for f in findings)

    def test_empty_pr_no_findings(self) -> None:
        pr = ParseResult(file_path=Path("empty.py"), language="python")
        signal = MissingAuthorizationSignal()
        findings = signal.analyze([pr], {}, DriftConfig())
        assert not findings
        assert not any(f is None for f in findings)

    def test_findings_severity_not_none(self) -> None:
        pr = ParseResult(
            file_path=Path("api.py"),
            language="python",
            functions=[_func("delete_user", "api.py", 5)],
            imports=[_imp("api.py", "fastapi")],
            patterns=[_endpoint_pattern("delete_user", "api.py", 5)],
        )
        signal = MissingAuthorizationSignal()
        findings = signal.analyze([pr], {}, DriftConfig())
        assert not any(f.severity is None for f in findings)
        assert not any(f.signal_type is None for f in findings)

    def test_findings_title_not_none(self) -> None:
        pr = ParseResult(
            file_path=Path("api.py"),
            language="python",
            functions=[_func("list_items", "api.py", 1)],
            imports=[_imp("api.py", "fastapi")],
            patterns=[_endpoint_pattern("list_items", "api.py", 1)],
        )
        signal = MissingAuthorizationSignal()
        findings = signal.analyze([pr], {}, DriftConfig())
        assert not any(f is None for f in findings)
        assert not any(f.title is None for f in findings)

    def test_no_findings_for_non_endpoint(self) -> None:
        pr = ParseResult(
            file_path=Path("utils.py"),
            language="python",
            functions=[_func("helper_func", "utils.py", 1)],
        )
        signal = MissingAuthorizationSignal()
        findings = signal.analyze([pr], {}, DriftConfig())
        assert not findings
        assert not any(f is None for f in findings)

    def test_findings_file_path_not_none(self) -> None:
        pr = ParseResult(
            file_path=Path("views.py"),
            language="python",
            functions=[_func("user_profile", "views.py", 5)],
            imports=[_imp("views.py", "django.http")],
            patterns=[_endpoint_pattern("user_profile", "views.py", 5)],
        )
        signal = MissingAuthorizationSignal()
        findings = signal.analyze([pr], {}, DriftConfig())
        assert not any(f is None for f in findings)
        assert not any(f.file_path is None for f in findings)

    def test_findings_score_not_none(self) -> None:
        pr = ParseResult(
            file_path=Path("api.py"),
            language="python",
            functions=[_func("create_item", "api.py", 10)],
            imports=[_imp("api.py", "fastapi")],
            patterns=[_endpoint_pattern("create_item", "api.py", 10)],
        )
        signal = MissingAuthorizationSignal()
        findings = signal.analyze([pr], {}, DriftConfig())
        assert not any(f is None for f in findings)
        assert not any(f.score is None for f in findings)

    def test_findings_metadata_not_none(self) -> None:
        pr = ParseResult(
            file_path=Path("api.py"),
            language="python",
            functions=[_func("update_user", "api.py", 15)],
            imports=[_imp("api.py", "fastapi")],
            patterns=[_endpoint_pattern("update_user", "api.py", 15)],
        )
        signal = MissingAuthorizationSignal()
        findings = signal.analyze([pr], {}, DriftConfig())
        assert not any(f is None for f in findings)
        assert not any(f.metadata is None for f in findings)

    def test_empty_signal_list_no_findings(self) -> None:
        signal = MissingAuthorizationSignal()
        findings = signal.analyze([], {}, DriftConfig())
        assert not findings
        assert not any(f is None for f in findings)
