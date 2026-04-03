"""Tests for Insecure Default signal (ISD)."""

from __future__ import annotations

import textwrap
from pathlib import Path

from drift.config import DriftConfig
from drift.models import ParseResult, SignalType
from drift.signals.insecure_default import InsecureDefaultSignal


def _make_pr(file_path: str = "settings.py") -> ParseResult:
    return ParseResult(
        file_path=Path(file_path),
        language="python",
    )


def _write_source(tmp_path: Path, rel_path: str, code: str) -> None:
    full = tmp_path / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(textwrap.dedent(code), encoding="utf-8")


# ---------------------------------------------------------------------------
# True positives: should detect insecure defaults
# ---------------------------------------------------------------------------


class TestISDTruePositives:
    def test_debug_true(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "settings.py",
            """\
            DEBUG = True
            """,
        )
        signal = InsecureDefaultSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) == 1
        assert findings[0].rule_id == "insecure_debug_mode"
        assert findings[0].signal_type == SignalType.INSECURE_DEFAULT

    def test_allowed_hosts_star(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "settings.py",
            """\
            ALLOWED_HOSTS = ["*"]
            """,
        )
        signal = InsecureDefaultSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) == 1
        assert findings[0].rule_id == "insecure_allowed_hosts"

    def test_allowed_hosts_empty(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "settings.py",
            """\
            ALLOWED_HOSTS = []
            """,
        )
        signal = InsecureDefaultSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) == 1
        assert findings[0].rule_id == "insecure_allowed_hosts"

    def test_cors_allow_all(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "settings.py",
            """\
            CORS_ALLOW_ALL_ORIGINS = True
            """,
        )
        signal = InsecureDefaultSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) == 1
        assert findings[0].rule_id == "insecure_cors"

    def test_cors_origin_allow_all(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "settings.py",
            """\
            CORS_ORIGIN_ALLOW_ALL = True
            """,
        )
        signal = InsecureDefaultSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) == 1
        assert findings[0].rule_id == "insecure_cors"

    def test_session_cookie_insecure(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "settings.py",
            """\
            SESSION_COOKIE_SECURE = False
            """,
        )
        signal = InsecureDefaultSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) == 1
        assert findings[0].rule_id == "insecure_cookie"

    def test_csrf_cookie_insecure(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "settings.py",
            """\
            CSRF_COOKIE_SECURE = False
            """,
        )
        signal = InsecureDefaultSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) == 1
        assert findings[0].rule_id == "insecure_cookie"

    def test_ssl_redirect_disabled(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "settings.py",
            """\
            SECURE_SSL_REDIRECT = False
            """,
        )
        signal = InsecureDefaultSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) == 1
        assert findings[0].rule_id == "insecure_ssl_redirect"

    def test_verify_false(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "client.py",
            """\
            import requests
            response = requests.get("https://api.example.com", verify=False)
            """,
        )
        signal = InsecureDefaultSignal(repo_path=tmp_path)
        pr = _make_pr("client.py")
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 1
        assert findings[0].rule_id == "insecure_ssl_verify"

    def test_multiple_insecure_defaults(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "settings.py",
            """\
            DEBUG = True
            ALLOWED_HOSTS = ["*"]
            CORS_ALLOW_ALL_ORIGINS = True
            SESSION_COOKIE_SECURE = False
            """,
        )
        signal = InsecureDefaultSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) == 4


# ---------------------------------------------------------------------------
# True negatives: should NOT flag these
# ---------------------------------------------------------------------------


class TestISDTrueNegatives:
    def test_debug_false(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "settings.py",
            """\
            DEBUG = False
            """,
        )
        signal = InsecureDefaultSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) == 0

    def test_allowed_hosts_specific(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "settings.py",
            """\
            ALLOWED_HOSTS = ["example.com", "api.example.com"]
            """,
        )
        signal = InsecureDefaultSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) == 0

    def test_cors_false(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "settings.py",
            """\
            CORS_ALLOW_ALL_ORIGINS = False
            """,
        )
        signal = InsecureDefaultSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) == 0

    def test_cookie_secure_true(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "settings.py",
            """\
            SESSION_COOKIE_SECURE = True
            """,
        )
        signal = InsecureDefaultSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) == 0

    def test_verify_true(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "client.py",
            """\
            import requests
            response = requests.get("https://api.example.com", verify=True)
            """,
        )
        signal = InsecureDefaultSignal(repo_path=tmp_path)
        pr = _make_pr("client.py")
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 0

    def test_test_file_skipped(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "tests/test_settings.py",
            """\
            DEBUG = True
            ALLOWED_HOSTS = ["*"]
            """,
        )
        signal = InsecureDefaultSignal(repo_path=tmp_path)
        pr = _make_pr("tests/test_settings.py")
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 0

    def test_conftest_skipped(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "conftest.py",
            """\
            DEBUG = True
            """,
        )
        signal = InsecureDefaultSignal(repo_path=tmp_path)
        pr = _make_pr("conftest.py")
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 0

    def test_non_python_skipped(self, tmp_path: Path) -> None:
        pr = ParseResult(
            file_path=Path("settings.ts"),
            language="typescript",
        )
        signal = InsecureDefaultSignal(repo_path=tmp_path)
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 0

    def test_unrelated_variable(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "settings.py",
            """\
            APP_DEBUG = True
            SOME_HOSTS = ["*"]
            """,
        )
        signal = InsecureDefaultSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) == 0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestISDEdgeCases:
    def test_metadata_includes_cwe(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "settings.py",
            """\
            DEBUG = True
            """,
        )
        signal = InsecureDefaultSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) == 1
        assert findings[0].metadata["cwe"] == "CWE-1188"

    def test_fix_suggestion_present(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "settings.py",
            """\
            DEBUG = True
            """,
        )
        signal = InsecureDefaultSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) == 1
        assert findings[0].fix is not None
        assert len(findings[0].fix) > 0

    def test_empty_parse_results(self, tmp_path: Path) -> None:
        signal = InsecureDefaultSignal(repo_path=tmp_path)
        findings = signal.analyze([], {}, DriftConfig())
        assert len(findings) == 0

    def test_syntax_error_file_skipped(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "broken.py",
            """\
            DEBUG = True def broken
            """,
        )
        signal = InsecureDefaultSignal(repo_path=tmp_path)
        pr = _make_pr("broken.py")
        findings = signal.analyze([pr], {}, DriftConfig())
        assert isinstance(findings, list)

    def test_severity_mapping(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "settings.py",
            """\
            DEBUG = True
            """,
        )
        signal = InsecureDefaultSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) == 1
        # DEBUG = True has score 0.8, so severity should be HIGH
        assert findings[0].score == 0.8


# ---------------------------------------------------------------------------
# Framework-specific fixtures (Issue #26)
# ---------------------------------------------------------------------------


class TestFrameworkSpecificDefaults:
    """Validate ISD against realistic Django, FastAPI, and Flask patterns."""

    # -- Django true positives ------------------------------------------------

    def test_django_settings_debug_true(self, tmp_path: Path) -> None:
        """Django settings.py with DEBUG = True at module level."""
        _write_source(
            tmp_path, "myproject/settings.py",
            """\
            import os
            from pathlib import Path

            BASE_DIR = Path(__file__).resolve().parent.parent
            SECRET_KEY = "insecure-dev-key"
            DEBUG = True
            ALLOWED_HOSTS = ["localhost"]
            """,
        )
        signal = InsecureDefaultSignal(repo_path=tmp_path)
        pr = _make_pr("myproject/settings.py")
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 1
        assert findings[0].rule_id == "insecure_debug_mode"

    def test_django_settings_allowed_hosts_star(self, tmp_path: Path) -> None:
        """Django ALLOWED_HOSTS = ['*'] is a common insecure default."""
        _write_source(
            tmp_path, "myproject/settings.py",
            """\
            DEBUG = False
            ALLOWED_HOSTS = ["*"]
            INSTALLED_APPS = [
                "django.contrib.admin",
                "django.contrib.auth",
            ]
            """,
        )
        signal = InsecureDefaultSignal(repo_path=tmp_path)
        pr = _make_pr("myproject/settings.py")
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 1
        assert findings[0].rule_id == "insecure_allowed_hosts"

    def test_django_multiple_insecure_defaults(self, tmp_path: Path) -> None:
        """Full Django settings with several insecure defaults at once."""
        _write_source(
            tmp_path, "config/settings.py",
            """\
            import os
            from pathlib import Path

            BASE_DIR = Path(__file__).resolve().parent.parent
            SECRET_KEY = "dev-only"
            DEBUG = True
            ALLOWED_HOSTS = ["*"]
            CORS_ALLOW_ALL_ORIGINS = True
            SESSION_COOKIE_SECURE = False
            CSRF_COOKIE_SECURE = False
            SECURE_SSL_REDIRECT = False
            """,
        )
        signal = InsecureDefaultSignal(repo_path=tmp_path)
        pr = _make_pr("config/settings.py")
        findings = signal.analyze([pr], {}, DriftConfig())
        rule_ids = {f.rule_id for f in findings}
        assert "insecure_debug_mode" in rule_ids
        assert "insecure_allowed_hosts" in rule_ids
        assert "insecure_cors" in rule_ids
        assert "insecure_cookie" in rule_ids
        assert "insecure_ssl_redirect" in rule_ids
        assert len(findings) >= 6  # 2× cookie (session + csrf)

    def test_django_verify_false_in_view(self, tmp_path: Path) -> None:
        """Django view calling external API with verify=False."""
        _write_source(
            tmp_path, "myapp/views.py",
            """\
            import requests
            from django.http import JsonResponse

            def proxy_api(request):
                resp = requests.get("https://internal-api.local/data", verify=False)
                return JsonResponse(resp.json())
            """,
        )
        signal = InsecureDefaultSignal(repo_path=tmp_path)
        pr = _make_pr("myapp/views.py")
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 1
        assert findings[0].rule_id == "insecure_ssl_verify"

    # -- Django true negatives ------------------------------------------------

    def test_django_debug_from_env(self, tmp_path: Path) -> None:
        """DEBUG loaded from environment — should not flag."""
        _write_source(
            tmp_path, "myproject/settings.py",
            """\
            import os
            DEBUG = os.environ.get("DEBUG", "False").lower() == "true"
            ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "").split(",")
            """,
        )
        signal = InsecureDefaultSignal(repo_path=tmp_path)
        pr = _make_pr("myproject/settings.py")
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 0

    # -- FastAPI true negatives (keyword args not at module level) ------------

    def test_fastapi_debug_keyword_not_detected(self, tmp_path: Path) -> None:
        """FastAPI(debug=True) is a keyword arg, not a module-level assignment.

        The current ISD signal detects module-level ``DEBUG = True``
        assignments and ``verify=False`` keyword args. Constructor keyword
        ``debug=True`` is not in scope.
        """
        _write_source(
            tmp_path, "app/main.py",
            """\
            from fastapi import FastAPI

            app = FastAPI(debug=True)

            @app.get("/")
            def root():
                return {"status": "ok"}
            """,
        )
        signal = InsecureDefaultSignal(repo_path=tmp_path)
        pr = _make_pr("app/main.py")
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 0

    def test_fastapi_config_driven_debug(self, tmp_path: Path) -> None:
        """FastAPI(debug=settings.DEBUG) — config-driven, should not flag."""
        _write_source(
            tmp_path, "app/main.py",
            """\
            from fastapi import FastAPI
            from app.config import settings

            app = FastAPI(debug=settings.DEBUG)
            """,
        )
        signal = InsecureDefaultSignal(repo_path=tmp_path)
        pr = _make_pr("app/main.py")
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 0

    def test_fastapi_verify_false_in_endpoint(self, tmp_path: Path) -> None:
        """FastAPI endpoint calling httpx with verify=False → should flag."""
        _write_source(
            tmp_path, "app/routes.py",
            """\
            import httpx
            from fastapi import APIRouter

            router = APIRouter()

            @router.get("/proxy")
            async def proxy():
                async with httpx.AsyncClient(verify=False) as client:
                    resp = await client.get("https://api.internal/data")
                return resp.json()
            """,
        )
        signal = InsecureDefaultSignal(repo_path=tmp_path)
        pr = _make_pr("app/routes.py")
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 1
        assert findings[0].rule_id == "insecure_ssl_verify"

    # -- Flask true negatives (keyword args not at module level) --------------

    def test_flask_run_debug_keyword_not_detected(self, tmp_path: Path) -> None:
        """app.run(debug=True) is a keyword arg — not in ISD scope.

        ISD detects module-level assignments and verify=False only.
        """
        _write_source(
            tmp_path, "app.py",
            """\
            from flask import Flask

            app = Flask(__name__)

            @app.route("/")
            def index():
                return "Hello"

            if __name__ == "__main__":
                app.run(debug=True)
            """,
        )
        signal = InsecureDefaultSignal(repo_path=tmp_path)
        pr = _make_pr("app.py")
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 0

    def test_flask_debug_module_level(self, tmp_path: Path) -> None:
        """Flask project with DEBUG = True at module level → detected."""
        _write_source(
            tmp_path, "config.py",
            """\
            DEBUG = True
            SECRET_KEY = "dev-secret"
            SQLALCHEMY_DATABASE_URI = "sqlite:///app.db"
            """,
        )
        signal = InsecureDefaultSignal(repo_path=tmp_path)
        pr = _make_pr("config.py")
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 1
        assert findings[0].rule_id == "insecure_debug_mode"
