"""Unit tests for drift ci command and CI environment detection."""

from __future__ import annotations

import pytest

from drift.ci_detect import detect_ci_environment


class TestCIDetection:
    def test_github_actions_pr(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        monkeypatch.setenv("GITHUB_BASE_REF", "main")
        monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")
        ctx = detect_ci_environment()
        assert ctx is not None
        assert ctx.provider == "github-actions"
        assert ctx.base_ref == "main"
        assert ctx.is_pr is True

    def test_github_actions_push(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        monkeypatch.setenv("GITHUB_EVENT_NAME", "push")
        monkeypatch.delenv("GITHUB_BASE_REF", raising=False)
        ctx = detect_ci_environment()
        assert ctx is not None
        assert ctx.provider == "github-actions"
        assert ctx.is_pr is False

    def test_gitlab_ci_mr(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
        monkeypatch.setenv("GITLAB_CI", "true")
        monkeypatch.setenv("CI_MERGE_REQUEST_TARGET_BRANCH_NAME", "develop")
        monkeypatch.setenv("CI_MERGE_REQUEST_IID", "42")
        ctx = detect_ci_environment()
        assert ctx is not None
        assert ctx.provider == "gitlab-ci"
        assert ctx.base_ref == "origin/develop"
        assert ctx.is_pr is True
        assert ctx.pr_number == 42

    def test_circleci(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
        monkeypatch.delenv("GITLAB_CI", raising=False)
        monkeypatch.setenv("CIRCLECI", "true")
        monkeypatch.setenv("CIRCLE_BRANCH", "feature-x")
        ctx = detect_ci_environment()
        assert ctx is not None
        assert ctx.provider == "circleci"
        assert ctx.base_ref == "origin/feature-x"

    def test_azure_pipelines(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
        monkeypatch.delenv("GITLAB_CI", raising=False)
        monkeypatch.delenv("CIRCLECI", raising=False)
        monkeypatch.setenv("BUILD_BUILDID", "1234")
        monkeypatch.setenv("SYSTEM_PULLREQUEST_TARGETBRANCH", "main")
        ctx = detect_ci_environment()
        assert ctx is not None
        assert ctx.provider == "azure-pipelines"
        assert ctx.is_pr is True
        assert ctx.base_ref == "origin/main"

    def test_generic_ci(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
        monkeypatch.delenv("GITLAB_CI", raising=False)
        monkeypatch.delenv("CIRCLECI", raising=False)
        monkeypatch.delenv("BUILD_BUILDID", raising=False)
        monkeypatch.delenv("AZURE_PIPELINES", raising=False)
        monkeypatch.setenv("CI", "true")
        ctx = detect_ci_environment()
        assert ctx is not None
        assert ctx.provider == "generic-ci"

    def test_no_ci(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for var in (
            "GITHUB_ACTIONS", "GITLAB_CI", "CIRCLECI",
            "BUILD_BUILDID", "AZURE_PIPELINES", "CI",
        ):
            monkeypatch.delenv(var, raising=False)
        ctx = detect_ci_environment()
        assert ctx is None
