"""Tests for Hardcoded Secret signal (HSC)."""

from __future__ import annotations

import textwrap
from pathlib import Path

from drift.config import DriftConfig
from drift.models import (
    ParseResult,
    SignalType,
)
from drift.signals.hardcoded_secret import (
    HardcodedSecretSignal,
    _shannon_entropy,
)


def _make_pr(file_path: str = "config.py") -> ParseResult:
    return ParseResult(
        file_path=Path(file_path),
        language="python",
    )


def _write_source(tmp_path: Path, rel_path: str, code: str) -> None:
    full = tmp_path / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(textwrap.dedent(code), encoding="utf-8")


# ---------------------------------------------------------------------------
# Unit: entropy calculation
# ---------------------------------------------------------------------------


class TestShannonEntropy:
    def test_empty_string(self) -> None:
        assert _shannon_entropy("") == 0.0

    def test_single_char(self) -> None:
        assert _shannon_entropy("aaaa") == 0.0

    def test_high_entropy(self) -> None:
        # Random-looking string should have high entropy
        val = "aB3$xZ9!kL2@mN5#"
        assert _shannon_entropy(val) > 3.5

    def test_low_entropy(self) -> None:
        assert _shannon_entropy("aaabbbccc") < 2.0


# ---------------------------------------------------------------------------
# True positives: should detect hardcoded secrets
# ---------------------------------------------------------------------------


class TestHSCTruePositives:
    def test_secret_key_hardcoded(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "settings.py",
            '''\
            SECRET_KEY = "s3cr3t-k3y-th4t-1s-v3ry-l0ng-4nd-r4nd0m"
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        pr = _make_pr("settings.py")
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) >= 1
        assert findings[0].signal_type == SignalType.HARDCODED_SECRET
        assert "SECRET_KEY" in findings[0].title

    def test_github_token(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "config.py",
            '''\
            GITHUB_TOKEN = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefgh"
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) == 1
        assert findings[0].rule_id == "hardcoded_api_token"

    def test_aws_access_key(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "config.py",
            '''\
            access_key = "AKIAIOSFODNN7EXAMPLE"
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) == 1
        assert findings[0].rule_id == "hardcoded_api_token"

    def test_openai_key(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "config.py",
            '''\
            api_key = "sk-abcdefghijklmnopqrstuvwxyz123456"
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) == 1
        assert findings[0].rule_id == "hardcoded_api_token"

    def test_password_literal(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "config.py",
            '''\
            db_password = "SuperSecretPassword123!"
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) >= 1
        assert "db_password" in findings[0].title

    def test_placeholder_secret(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "config.py",
            '''\
            SECRET_KEY = "your-secret-here"
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) >= 1

    def test_annotated_assignment(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "config.py",
            '''\
            api_token: str = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456"
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) >= 1


# ---------------------------------------------------------------------------
# True negatives: should NOT flag these
# ---------------------------------------------------------------------------


class TestHSCTrueNegatives:
    def test_env_variable(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "config.py",
            '''\
            import os
            SECRET_KEY = os.environ["SECRET_KEY"]
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) == 0

    def test_getenv(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "config.py",
            '''\
            import os
            SECRET_KEY = os.getenv("SECRET_KEY", "fallback")
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) == 0

    def test_config_get(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "config.py",
            '''\
            SECRET_KEY = config.get("secret_key")
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) == 0

    def test_short_string(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "config.py",
            '''\
            secret = "short"
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) == 0

    def test_test_file_skipped(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "tests/test_auth.py",
            '''\
            SECRET_KEY = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefgh"
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        pr = _make_pr("tests/test_auth.py")
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 0

    def test_non_python_skipped(self, tmp_path: Path) -> None:
        pr = ParseResult(file_path=Path("config.ts"), language="typescript")
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 0

    def test_non_secret_variable(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "config.py",
            '''\
            APP_NAME = "my-really-great-production-application"
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) == 0

    def test_fstring_value(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "config.py",
            '''\
            env = "prod"
            secret_key = f"prefix-{env}-suffix-dynamic"
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) == 0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestHSCEdgeCases:
    def test_metadata_includes_cwe(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "config.py",
            '''\
            token = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefgh"
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) == 1
        assert findings[0].metadata["cwe"] == "CWE-798"

    def test_fix_suggestion_present(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "config.py",
            '''\
            SECRET_KEY = "s3cr3t-v3ry-l0ng-k3y-f0r-pr0d"
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) >= 1
        assert findings[0].fix is not None
        assert "os.environ" in findings[0].fix

    def test_empty_parse_results(self, tmp_path: Path) -> None:
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([], {}, DriftConfig())
        assert len(findings) == 0

    def test_syntax_error_file_skipped(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "broken.py",
            '''\
            SECRET_KEY = "ghp_test" def broken
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        pr = _make_pr("broken.py")
        findings = signal.analyze([pr], {}, DriftConfig())
        # Should not crash, may or may not find the secret depending on parse
        assert isinstance(findings, list)

    def test_class_attribute_secret(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "config.py",
            '''\
            class Config:
                secret_key = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefgh"
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) >= 1
