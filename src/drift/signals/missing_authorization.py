"""Signal: Missing Authorization (MAZ).

Detects API endpoint functions that lack any form of authorization check.
Routes without auth decorators, body-level auth checks, or class-level
auth mixins are flagged as potential security-by-default violations.

Targets the "vibe-coding" pattern where LLMs generate functional endpoints
but omit access control.  Maps to CWE-862 (Missing Authorization).

Deterministic, AST-only, LLM-free.
"""

from __future__ import annotations

from drift.config import DriftConfig
from drift.models import (
    FileHistory,
    Finding,
    FunctionInfo,
    ParseResult,
    PatternCategory,
    Severity,
    SignalType,
)
from drift.signals._utils import is_test_file
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


def _is_public_allowlisted(fn_name: str, allowlist: list[str]) -> bool:
    """Return True if the function name matches a known public endpoint."""
    lower = fn_name.lower().replace("_", "")
    return any(allowed.replace("_", "") in lower for allowed in allowlist)


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
    }
    return suggestions.get(
        framework,
        "Add an authorization check (decorator, dependency injection, or body check).",
    )


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

        for pr in parse_results:
            if pr.language != "python":
                continue
            if is_test_file(pr.file_path):
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
            for pat in pr.patterns:
                if pat.category != PatternCategory.API_ENDPOINT:
                    continue
                fp = pat.fingerprint
                if fp.get("has_auth", False):
                    continue

                fn_name = pat.function_name
                if _is_public_allowlisted(fn_name, allowlist):
                    continue

                # Check if function belongs to an authed class.
                if "." in fn_name:
                    class_name = fn_name.split(".")[0]
                    if class_name in authed_classes:
                        continue

                fn_info = functions_by_name.get(fn_name)
                is_documented_public_safe = _is_documented_public_safe_endpoint(
                    fn_name,
                    fn_info,
                )

                score = 0.35 if is_documented_public_safe else 0.7
                severity = Severity.LOW if is_documented_public_safe else Severity.HIGH

                description = (
                    f"The route handler '{fn_name}' in {pr.file_path} "
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

                findings.append(
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
                        },
                        rule_id="missing_authz_route",
                    )
                )

        return findings
