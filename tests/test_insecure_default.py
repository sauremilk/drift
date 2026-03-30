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
