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


def _is_public_allowlisted(fn_name: str, allowlist: list[str]) -> bool:
    """Return True if the function name matches a known public endpoint."""
    lower = fn_name.lower().replace("_", "")
    return any(allowed.replace("_", "") in lower for allowed in allowlist)


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

        for pr in parse_results:
            if pr.language != "python":
                continue
            if is_test_file(pr.file_path):
                continue

            framework = _detect_framework(pr)

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

                score = 0.7
                severity = Severity.HIGH

                findings.append(
                    Finding(
                        signal_type=self.signal_type,
                        severity=severity,
                        score=score,
                        title=f"Endpoint '{fn_name}' has no authorization check",
                        description=(
                            f"The route handler '{fn_name}' in {pr.file_path} "
                            f"is missing an authorization check. Without auth, "
                            f"any caller can access this endpoint. "
                            f"Detected framework: {framework}."
                        ),
                        file_path=pr.file_path,
                        start_line=pat.start_line,
                        end_line=pat.end_line,
                        symbol=fn_name,
                        fix=_fix_suggestion(framework),
                        metadata={
                            "framework": framework,
                            "cwe": "CWE-862",
                            "endpoint_name": fn_name,
                            "auth_mechanism": "none",
                        },
                        rule_id="missing_authz_route",
                    )
                )

        return findings
