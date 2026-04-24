"""Signal: Missing Authorization (MAZ).

Detects API endpoint functions that lack any form of authorization check.
Routes without auth decorators, body-level auth checks, or class-level
auth mixins are flagged as potential security-by-default violations.

Targets the "vibe-coding" pattern where LLMs generate functional endpoints
but omit access control.  Maps to CWE-862 (Missing Authorization).

Deterministic, AST-only, LLM-free.
"""

from __future__ import annotations

import re

from drift.config import DriftConfig
from drift.ingestion.test_detection import classify_file_context
from drift.models import (
    FileHistory,
    Finding,
    FunctionInfo,
    ParseResult,
    PatternCategory,
    PatternInstance,
    Severity,
    SignalType,
)
from drift.signals.base import BaseSignal, register_signal

# Class-level auth mixins (Django CBV pattern).
_AUTH_MIXINS: frozenset[str] = frozenset({
    "loginrequiredmixin",
    "permissionrequiredmixin",
    "useraccessmixin",
    "accessmixin",
    "staffrequiredmixin",
    "superuserrequiredmixin",
    "isauthenticated",
})

# Public-safe endpoint intent markers. Keep this list conservative to avoid
# suppressing truly sensitive unauthenticated handlers.
_PUBLIC_SAFE_NAME_MARKERS: frozenset[str] = frozenset({
    "publishable",
    "publishablekey",
    "publickey",
    "clientkey",
})

# Local CLI serving tools are typically development utilities (localhost-only)
# and should not be treated as production-facing APIs for MAZ.
_CLI_LOCAL_SERVER_PATH_MARKERS: frozenset[str] = frozenset({"serving", "serve"})

# Conservative route-decorator markers used only as fallback when ingestion
# produced no API_ENDPOINT patterns for a file.
_ROUTE_DECORATOR_MARKERS: frozenset[str] = frozenset({
    "route",
    "api_view",
    "get",
    "post",
    "put",
    "patch",
    "delete",
    "options",
    "head",
})

_AUTH_DECORATOR_MARKERS: frozenset[str] = frozenset({
    "auth",
    "authorize",
    "authenticated",
    "permission",
    "login_required",
    "requires",
    "jwt_required",
    "token_required",
})

# Conservative fallback-only parameter markers that usually indicate injected
# auth context (for example current_user from dependency injection).
_AUTH_PARAM_MARKERS: frozenset[str] = frozenset({
    "currentuser",
    "authenticateduser",
    "authuser",
    "requestuser",
    "principal",
    "credentials",
    "token",
    "jwttoken",
    "jwtclaims",
    "userclaims",
})

_AUTH_PARAM_REGEXES: tuple[re.Pattern[str], ...] = (
    re.compile(r"^(?:current|authenticated|request|auth)user(?:context|info|obj|object)?$"),
    re.compile(r"^(?:jwt|access|id|bearer|auth)token(?:s|value|str|string)?$"),
    re.compile(r"^(?:auth|user|principal)claims?$"),
    re.compile(r"^credentials?$"),
    re.compile(r"^principal$"),
)

_SEVERITY_ORDER: dict[Severity, int] = {
    Severity.INFO: 0,
    Severity.LOW: 1,
    Severity.MEDIUM: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}


def _normalize_param_name(param: str) -> str:
    """Normalize parameter names across snake_case and camelCase variants."""
    with_boundaries = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", param)
    lower = with_boundaries.lower()
    return re.sub(r"[^a-z0-9]", "", lower)


_TS_INBOUND_HANDLER_PARAM_MARKERS: frozenset[str] = frozenset({
    "req",
    "request",
    "res",
    "response",
    "reply",
    "ctx",
    "context",
    "next",
})


def _has_ts_inbound_handler_signature(fn_info: FunctionInfo | None) -> bool:
    """Return True when TS/JS function params look like inbound HTTP handlers."""
    if fn_info is None:
        return False
    if fn_info.language not in {"typescript", "tsx", "javascript", "jsx"}:
        return True

    for param in fn_info.parameters:
        normalized = _normalize_param_name(param)
        if normalized in _TS_INBOUND_HANDLER_PARAM_MARKERS:
            return True
    return False


def _is_public_allowlisted(fn_name: str, allowlist: list[str]) -> bool:
    """Return True if the function name matches a known public endpoint."""
    lower = fn_name.lower().replace("_", "")
    return any(allowed.replace("_", "") in lower for allowed in allowlist)


def _is_public_route_allowlisted(route: str, allowlist: list[str]) -> bool:
    """Return True if the route path matches known intentionally public endpoints."""
    normalized_route = route.lower().replace("_", "").replace("-", "")
    normalized_route = normalized_route.replace("/", "")
    return any(allowed.replace("_", "") in normalized_route for allowed in allowlist)


def _looks_like_http_route_path(route: str) -> bool:
    """Return True when route resembles an HTTP path (not a cache/store key)."""
    candidate = route.strip().strip("'\"")
    if not candidate:
        return False
    if candidate == "*":
        return True
    return candidate.startswith("/")


def _route_specificity(route: str) -> tuple[int, int]:
    """Rank route specificity; non-empty concrete paths win over empty routes."""
    candidate = route.strip().strip("'\"")
    if not candidate:
        return (0, 0)
    if candidate == "*":
        return (1, 1)
    if candidate.startswith("/"):
        return (2, len(candidate))
    return (1, len(candidate))


def _prefer_route_metadata(current: Finding, candidate: Finding) -> Finding:
    """Keep one finding and prefer richer route metadata for the same endpoint."""
    current_route = str(current.metadata.get("route", ""))
    candidate_route = str(candidate.metadata.get("route", ""))

    current_rank = _route_specificity(current_route)
    candidate_rank = _route_specificity(candidate_route)
    if candidate_rank > current_rank:
        return candidate

    if _SEVERITY_ORDER[candidate.severity] > _SEVERITY_ORDER[current.severity]:
        return candidate
    if candidate.score > current.score:
        return candidate

    return current


def _has_strong_unknown_ts_route_evidence(pr: ParseResult, pat: PatternInstance) -> bool:
    """Require stronger endpoint evidence for TS/JS when framework detection failed."""
    if pr.language not in {"typescript", "tsx", "javascript", "jsx"}:
        return True
    route = str(pat.fingerprint.get("route", ""))
    return _looks_like_http_route_path(route)


def _is_dev_tool_path(file_path: str, dev_paths: list[str]) -> bool:
    """Return True if the file lives under a known dev/internal tool directory."""
    parts = file_path.lower().replace("\\", "/").split("/")
    return any(part in dev_paths for part in parts)


def _is_cli_local_serving_path(file_path: str) -> bool:
    """Return True for CLI-local serving modules (e.g. cli/serving/server.py)."""
    parts = file_path.lower().replace("\\", "/").split("/")
    if "cli" not in parts:
        return False
    return any(marker in parts for marker in _CLI_LOCAL_SERVER_PATH_MARKERS)


def _is_documented_public_safe_endpoint(
    fn_name: str,
    fn_info: FunctionInfo | None,
) -> bool:
    """Return True when endpoint looks intentionally public-safe and documented."""
    if fn_info is None or not fn_info.has_docstring:
        return False
    normalized = fn_name.split(".")[-1].lower().replace("_", "")
    return any(marker in normalized for marker in _PUBLIC_SAFE_NAME_MARKERS)


def _decorator_name(decorator: str) -> str:
    """Normalize decorator name while preserving dotted suffix semantics."""
    base = decorator.strip().split("(", 1)[0]
    return base.split(".")[-1].lower()


def _looks_like_route_decorator(decorator: str) -> bool:
    """Return True for common route decorator names."""
    name = _decorator_name(decorator)
    return name in _ROUTE_DECORATOR_MARKERS


def _looks_like_auth_decorator(decorator: str) -> bool:
    """Return True for common auth-related decorators."""
    normalized = _decorator_name(decorator).replace("_", "")
    return any(marker.replace("_", "") in normalized for marker in _AUTH_DECORATOR_MARKERS)


def _has_auth_like_parameter(fn_info: FunctionInfo) -> bool:
    """Return True if function parameters indicate injected auth context."""
    for param in fn_info.parameters:
        normalized = _normalize_param_name(param)
        if normalized in _AUTH_PARAM_MARKERS:
            return True
        if any(regex.match(normalized) for regex in _AUTH_PARAM_REGEXES):
            return True
    return False


def _fallback_endpoint_functions(pr: ParseResult) -> list[FunctionInfo]:
    """Infer API endpoints from decorators when pattern ingestion misses them."""
    endpoints: list[FunctionInfo] = []
    for fn in pr.functions:
        if not fn.decorators:
            continue
        if any(_looks_like_route_decorator(deco) for deco in fn.decorators):
            endpoints.append(fn)
    return endpoints


def _detect_framework(parse_result: ParseResult) -> str:
    """Best-effort framework detection from imports."""
    for imp in parse_result.imports:
        mod = imp.imported_module.lower()
        if "fastapi" in mod:
            return "fastapi"
        if "django" in mod or "rest_framework" in mod:
            return "django"
        if "flask" in mod:
            return "flask"
        if "starlette" in mod:
            return "starlette"
        if "sanic" in mod:
            return "sanic"
        # TypeScript / JavaScript frameworks
        if "express" in mod:
            return "express"
        if "fastify" in mod:
            return "fastify"
        if "@nestjs" in mod:
            return "nestjs"
        if "koa" in mod:
            return "koa"
        if "hono" in mod:
            return "hono"
    return "unknown"


def _fix_suggestion(framework: str) -> str:
    """Return a framework-specific fix suggestion."""
    suggestions = {
        "fastapi": (
            "Add an auth dependency: "
            "async def endpoint(user: User = Depends(get_current_user))"
        ),
        "django": "Add @login_required or @permission_required decorator.",
        "flask": "Add @login_required from flask_login or check current_user.",
        "starlette": "Add requires() decorator or auth middleware.",
        "sanic": "Add @authorized() decorator or check request.ctx.user.",
        "express": (
            "Add auth middleware: "
            "router.get('/path', authMiddleware, handler)"
        ),
        "fastify": (
            "Add onRequest hook: "
            "{ onRequest: [fastify.authenticate] }"
        ),
        "nestjs": "Add @UseGuards(AuthGuard) decorator.",
        "koa": "Add auth middleware before the route handler.",
        "hono": "Add auth middleware via app.use().",
    }
    base = suggestions.get(
        framework,
        "Add an authorization check (decorator, dependency injection, or body check).",
    )
    return base + " (Exempt if endpoint is intentionally public, e.g. A2A agent card.)"


@register_signal
class MissingAuthorizationSignal(BaseSignal):
    """Detect API endpoints missing authorization checks."""

    incremental_scope = "file_local"

    @property
    def signal_type(self) -> SignalType:
        return SignalType.MISSING_AUTHORIZATION

    @property
    def name(self) -> str:
        return "Missing Authorization"

    def analyze(
        self,
        parse_results: list[ParseResult],
        file_histories: dict[str, FileHistory],
        config: DriftConfig,
    ) -> list[Finding]:
        findings: list[Finding] = []
        allowlist = config.thresholds.maz_public_endpoint_allowlist
        dev_paths = config.thresholds.maz_dev_tool_paths
        handling = config.test_file_handling or "exclude"

        supported_langs = {"python", "typescript", "tsx", "javascript", "jsx"}
        for pr in parse_results:
            endpoint_findings_by_symbol: dict[tuple[str, str | None], Finding] = {}

            def _collect_endpoint_finding(
                finding: Finding,
                _findings_map: dict[tuple[str, str | None], Finding] = endpoint_findings_by_symbol,
            ) -> None:
                dedupe_key = (str(finding.file_path), finding.symbol)
                existing = _findings_map.get(dedupe_key)
                if existing is None:
                    _findings_map[dedupe_key] = finding
                    return
                _findings_map[dedupe_key] = _prefer_route_metadata(
                    existing,
                    finding,
                )

            if pr.language not in supported_langs:
                continue
            path_context = classify_file_context(pr.file_path)
            if path_context == "test" and handling == "exclude":
                continue
            if _is_dev_tool_path(pr.file_path.as_posix(), dev_paths):
                continue
            if _is_cli_local_serving_path(pr.file_path.as_posix()):
                continue

            framework = _detect_framework(pr)
            functions_by_name = {fn.name: fn for fn in pr.functions}

            # Build set of class names with auth mixins for CBV detection.
            authed_classes: set[str] = set()
            for cls in pr.classes:
                for base in cls.bases:
                    if base.lower().replace("_", "") in _AUTH_MIXINS:
                        authed_classes.add(cls.name)
                        break

            # Check endpoint patterns from ingestion.
            saw_api_pattern = False
            for pat in pr.patterns:
                if pat.category != PatternCategory.API_ENDPOINT:
                    continue
                saw_api_pattern = True
                fp = pat.fingerprint
                if bool(fp.get("loopback_only", False)):
                    continue
                if fp.get("has_auth", False):
                    continue

                if framework == "unknown" and not _has_strong_unknown_ts_route_evidence(pr, pat):
                    continue

                fn_name = pat.function_name
                if _is_public_allowlisted(fn_name, allowlist):
                    continue
                route = str(fp.get("route", ""))
                if route and _is_public_route_allowlisted(route, allowlist):
                    continue

                # Check if function belongs to an authed class.
                if "." in fn_name:
                    class_name = fn_name.split(".")[0]
                    if class_name in authed_classes:
                        continue

                fn_info = functions_by_name.get(fn_name)
                if framework == "unknown" and not _has_ts_inbound_handler_signature(fn_info):
                    continue
                is_documented_public_safe = _is_documented_public_safe_endpoint(
                    fn_name,
                    fn_info,
                )

                score = 0.35 if is_documented_public_safe else 0.85
                severity = Severity.LOW if is_documented_public_safe else Severity.CRITICAL
                if path_context == "test" and handling == "reduce_severity":
                    score = min(score, 0.25)
                    severity = Severity.LOW

                description = (
                    f"The route handler '{fn_name}' in {pr.file_path.as_posix()} "
                    f"is missing an authorization check. Without auth, "
                    f"any caller can access this endpoint. "
                    f"Detected framework: {framework}."
                )
                fix = _fix_suggestion(framework)
                if is_documented_public_safe:
                    description += (
                        " This endpoint appears intentionally public-safe "
                        "(documented publishable/public key semantics), "
                        "so severity was downgraded for triage."
                    )
                    fix = (
                        "If this endpoint is intentionally public, keep explicit "
                        "documentation and ensure only non-sensitive publishable "
                        "key material is returned; otherwise add authorization."
                    )

                _collect_endpoint_finding(
                    Finding(
                        signal_type=self.signal_type,
                        severity=severity,
                        score=score,
                        title=f"Endpoint '{fn_name}' has no authorization check",
                        description=description,
                        file_path=pr.file_path,
                        start_line=pat.start_line,
                        end_line=pat.end_line,
                        symbol=fn_name,
                        fix=fix,
                        metadata={
                            "framework": framework,
                            "cwe": "CWE-862",
                            "endpoint_name": fn_name,
                            "auth_mechanism": "none",
                            "public_safe_documented": is_documented_public_safe,
                            "route": route,
                            "finding_context": path_context,
                        },
                        finding_context=path_context,
                        rule_id="missing_authz_route",
                    )
                )

            # Conservative fallback: if ingestion found no endpoint patterns,
            # infer obvious route handlers from decorators to recover recall.
            if saw_api_pattern:
                findings.extend(endpoint_findings_by_symbol.values())
                continue

            for fn_info in _fallback_endpoint_functions(pr):
                fn_name = fn_info.name
                if any(_looks_like_auth_decorator(deco) for deco in fn_info.decorators):
                    continue
                if _has_auth_like_parameter(fn_info):
                    continue
                if _is_public_allowlisted(fn_name, allowlist):
                    continue

                if "." in fn_name:
                    class_name = fn_name.split(".")[0]
                    if class_name in authed_classes:
                        continue

                is_documented_public_safe = _is_documented_public_safe_endpoint(
                    fn_name,
                    fn_info,
                )

                score = 0.35 if is_documented_public_safe else 0.85
                severity = Severity.LOW if is_documented_public_safe else Severity.CRITICAL
                if path_context == "test" and handling == "reduce_severity":
                    score = min(score, 0.25)
                    severity = Severity.LOW

                description = (
                    f"The route handler '{fn_name}' in {pr.file_path.as_posix()} "
                    f"is missing an authorization check. Without auth, "
                    f"any caller can access this endpoint. "
                    f"Detected framework: {framework}."
                )
                fix = _fix_suggestion(framework)
                if is_documented_public_safe:
                    description += (
                        " This endpoint appears intentionally public-safe "
                        "(documented publishable/public key semantics), "
                        "so severity was downgraded for triage."
                    )
                    fix = (
                        "If this endpoint is intentionally public, keep explicit "
                        "documentation and ensure only non-sensitive publishable "
                        "key material is returned; otherwise add authorization."
                    )

                _collect_endpoint_finding(
                    Finding(
                        signal_type=self.signal_type,
                        severity=severity,
                        score=score,
                        title=f"Endpoint '{fn_name}' has no authorization check",
                        description=description,
                        file_path=pr.file_path,
                        start_line=fn_info.start_line,
                        end_line=fn_info.end_line,
                        symbol=fn_name,
                        fix=fix,
                        metadata={
                            "framework": framework,
                            "cwe": "CWE-862",
                            "endpoint_name": fn_name,
                            "auth_mechanism": "none",
                            "public_safe_documented": is_documented_public_safe,
                            "detection_source": "decorator_fallback",
                            "finding_context": path_context,
                        },
                        finding_context=path_context,
                        rule_id="missing_authz_route",
                    )
                )

            findings.extend(endpoint_findings_by_symbol.values())

        return findings
