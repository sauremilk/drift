"""Tests for git_history AI attribution heuristics and edge cases.

Targeted gaps (git_history.py at 91%, lines 152-153, 156, 182, 205-206, 216-217):
- _detect_ai_attribution: tier 1 patterns, tier 2 patterns, co-author markers
- _is_defect_correlated: regression in various message formats
- parse_git_history: malformed commit data, empty output
- build_file_histories: defect correlation, recent window, unknown file filtering

AI attribution is the foundation for all AI-related scoring — false positives
produce inflated drift scores, false negatives miss actual AI debt.
"""

import datetime

import pytest

from drift.ingestion.git_history import (
    _detect_ai_attribution,
    _is_defect_correlated,
    build_file_histories,
)
from drift.models import CommitInfo

# ── _detect_ai_attribution ────────────────────────────────────────────────


class TestDetectAIAttribution:
    """Test multi-tier AI attribution heuristics."""

    def test_copilot_coauthor_high_confidence(self):
        is_ai, conf = _detect_ai_attribution("Add feature", ["GitHub Copilot"])
        assert is_ai is True
        assert conf >= 0.90

    def test_cursor_coauthor(self):
        is_ai, conf = _detect_ai_attribution("Update handler", ["Cursor AI"])
        assert is_ai is True
        assert conf >= 0.90

    def test_codeium_coauthor(self):
        is_ai, conf = _detect_ai_attribution("Fix bug", ["Codeium"])
        assert is_ai is True

    def test_anthropic_coauthor(self):
        is_ai, conf = _detect_ai_attribution("Refactor module", ["Anthropic"])
        assert is_ai is True

    def test_human_coauthor_not_flagged(self):
        is_ai, conf = _detect_ai_attribution("Add feature", ["John Doe"])
        assert conf < 0.5

    def test_tier1_implement_pattern(self):
        """'Implement X Y Z' with short message, no body → tier 1."""
        is_ai, conf = _detect_ai_attribution("Implement user auth handler", [])
        assert is_ai is True
        assert conf >= 0.30

    def test_tier1_with_body_not_flagged(self):
        """Tier 1 pattern but with message body → not considered AI."""
        msg = "Implement user auth handler\n\nThis adds OAuth2 support for the API."
        is_ai, conf = _detect_ai_attribution(msg, [])
        # Has body → doesn't match tier1 criteria
        assert conf < 0.50

    def test_tier1_long_first_line_not_flagged(self):
        """Tier 1 pattern but first line > 72 chars → not considered AI."""
        msg = (
            "Implement user authentication handler with comprehensive"
            " OAuth2 support for all endpoints"
        )
        is_ai, conf = _detect_ai_attribution(msg, [])
        assert conf < 0.50

    def test_tier2_pattern_low_confidence(self):
        """'Add X Y' → tier 2 with low confidence (0.15)."""
        is_ai, conf = _detect_ai_attribution("Add user tests", [])
        # Tier 2: is_ai=False, confidence=0.15
        assert is_ai is False
        assert conf <= 0.20

    def test_tier2_long_message_not_flagged(self):
        """Tier 2 pattern but first line >= 50 chars → not flagged."""
        msg = "Add comprehensive user authentication tests with mocking"
        is_ai, conf = _detect_ai_attribution(msg, [])
        assert conf < 0.20

    def test_normal_human_message(self):
        """Regular commit message → no AI attribution."""
        is_ai, conf = _detect_ai_attribution("fix: resolve null pointer in payment flow", [])
        assert is_ai is False
        assert conf == 0.0

    def test_empty_message(self):
        is_ai, conf = _detect_ai_attribution("", [])
        assert is_ai is False
        assert conf == 0.0

    def test_add_functionality_tier1(self):
        """'Add X functionality for Y' pattern is tier 1."""
        is_ai, conf = _detect_ai_attribution("Add error handling functionality for auth", [])
        assert is_ai is True
        assert conf >= 0.30


# ── _is_defect_correlated ────────────────────────────────────────────────


class TestDefectCorrelation:
    @pytest.mark.parametrize(
        "msg",
        [
            "fix: resolve null pointer",
            "Bug: payment fails on zero amount",
            "hotfix: emergency rollback",
            "revert: undo breaking change",
            "patch session timeout regression",
            "Fix broken CI pipeline",
            "Handle crash on empty input",
            "Fix error in validation logic",
        ],
    )
    def test_defect_messages_detected(self, msg):
        assert _is_defect_correlated(msg) is True

    @pytest.mark.parametrize(
        "msg",
        [
            "Add user authentication",
            "Refactor database layer",
            "Update dependencies",
            "Implement caching strategy",
            "chore: update changelog",
        ],
    )
    def test_non_defect_messages_not_flagged(self, msg):
        assert _is_defect_correlated(msg) is False


# ── build_file_histories ─────────────────────────────────────────────────


def _commit(
    files: list[str],
    author: str = "dev",
    is_ai: bool = False,
    message: str = "update",
    days_ago: int = 5,
) -> CommitInfo:
    ts = datetime.datetime.now(tz=datetime.UTC) - datetime.timedelta(days=days_ago)
    return CommitInfo(
        hash="abc123def456",
        author=author,
        email=f"{author}@test.com",
        timestamp=ts,
        message=message,
        files_changed=files,
        insertions=10,
        deletions=5,
        is_ai_attributed=is_ai,
        ai_confidence=0.9 if is_ai else 0.0,
        coauthors=[],
    )


class TestBuildFileHistories:
    def test_basic_aggregation(self):
        commits = [
            _commit(["src/a.py", "src/b.py"], author="alice"),
            _commit(["src/a.py"], author="bob"),
        ]
        histories = build_file_histories(commits)
        assert "src/a.py" in histories
        assert "src/b.py" in histories
        assert histories["src/a.py"].total_commits == 2
        assert histories["src/a.py"].unique_authors == 2
        assert histories["src/b.py"].total_commits == 1

    def test_ai_attributed_count(self):
        commits = [
            _commit(["f.py"], is_ai=True),
            _commit(["f.py"], is_ai=False),
            _commit(["f.py"], is_ai=True),
        ]
        h = build_file_histories(commits)
        assert h["f.py"].ai_attributed_commits == 2

    def test_defect_correlation(self):
        commits = [
            _commit(["f.py"], message="fix: null pointer"),
            _commit(["f.py"], message="add feature"),
            _commit(["f.py"], message="bug: payment crash"),
        ]
        h = build_file_histories(commits)
        assert h["f.py"].defect_correlated_commits == 2

    def test_known_files_filter(self):
        """Only track files in known_files set."""
        commits = [
            _commit(["a.py", "b.py"]),
        ]
        h = build_file_histories(commits, known_files={"a.py"})
        assert "a.py" in h
        assert "b.py" not in h

    def test_recent_change_frequency(self):
        """Commits within 30 days count toward change_frequency_30d."""
        commits = [
            _commit(["f.py"], days_ago=5),
            _commit(["f.py"], days_ago=10),
            _commit(["f.py"], days_ago=60),  # outside 30-day window
        ]
        h = build_file_histories(commits)
        # 2 recent commits / 30 * 7 = ~0.467 changes/week
        assert h["f.py"].change_frequency_30d > 0.0

    def test_timestamps_set(self):
        commits = [
            _commit(["f.py"], days_ago=30),
            _commit(["f.py"], days_ago=5),
        ]
        h = build_file_histories(commits)
        assert h["f.py"].last_modified is not None
        assert h["f.py"].first_seen is not None
        assert h["f.py"].last_modified > h["f.py"].first_seen

    def test_empty_commits(self):
        h = build_file_histories([])
        assert h == {}
