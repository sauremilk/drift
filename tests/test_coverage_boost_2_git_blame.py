"""Coverage-Boost: ingestion/git_blame.py — Fehlerpfade und parallele Blame-Logik."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from drift.ingestion.git_blame import (
    BlameCache,
    _content_hash,
    _parse_porcelain,
    blame_files_parallel,
    blame_lines,
    extract_branch_hint,
)

# ---------------------------------------------------------------------------
# _parse_porcelain
# ---------------------------------------------------------------------------


def test_parse_porcelain_empty_string() -> None:
    assert _parse_porcelain("") == []


def test_parse_porcelain_valid_block() -> None:
    raw = (
        "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0 1 1 1\n"
        "author Jane Doe\n"
        "author-mail <jane@example.com>\n"
        "author-time 1700000000\n"
        "summary Initial commit\n"
        "\tdef foo(): pass\n"
    )
    lines = _parse_porcelain(raw)
    assert len(lines) == 1
    assert lines[0].author == "Jane Doe"
    assert lines[0].email == "jane@example.com"
    assert lines[0].content == "def foo(): pass"
    assert lines[0].line_no == 1


def test_parse_porcelain_invalid_author_time_ignored() -> None:
    """Invalid author-time should not raise — date defaults."""
    raw = (
        "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0 1 1 1\n"
        "author Bob\n"
        "author-mail <bob@x.com>\n"
        "author-time not_a_number\n"
        "\tcode line\n"
    )
    lines = _parse_porcelain(raw)
    assert len(lines) == 1
    assert lines[0].author == "Bob"


def test_parse_porcelain_large_timestamp() -> None:
    """Out-of-range unix timestamp should not raise (OSError path)."""
    raw = (
        "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0 1 1 1\n"
        "author Bob\n"
        "author-mail <bob@x.com>\n"
        "author-time 99999999999999\n"
        "\tcode line\n"
    )
    lines = _parse_porcelain(raw)
    assert len(lines) == 1  # Should not raise


# ---------------------------------------------------------------------------
# blame_lines — subprocess error paths
# ---------------------------------------------------------------------------


def test_blame_lines_file_not_found(tmp_path: Path) -> None:
    """FileNotFoundError (git not installed) should return []."""
    with patch("subprocess.run", side_effect=FileNotFoundError("git not found")):
        result = blame_lines(tmp_path, "some/file.py")
    assert result == []


def test_blame_lines_timeout(tmp_path: Path) -> None:
    """TimeoutExpired should return []."""
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(["git"], 3.0)):
        result = blame_lines(tmp_path, "some/file.py")
    assert result == []


def test_blame_lines_oserror(tmp_path: Path) -> None:
    """Generic OSError should return []."""
    with patch("subprocess.run", side_effect=OSError("IO error")):
        result = blame_lines(tmp_path, "some/file.py")
    assert result == []


def test_blame_lines_nonzero_returncode(tmp_path: Path) -> None:
    """Non-zero returncode should return []."""
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    with patch("subprocess.run", return_value=mock_result):
        result = blame_lines(tmp_path, "nonexistent.py")
    assert result == []


def test_blame_lines_with_line_range(tmp_path: Path) -> None:
    """blame_lines with start_line and no end_line should use start as end."""
    porcelain = (
        "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0 5 5 1\n"
        "author Alice\n"
        "author-mail <alice@x.com>\n"
        "author-time 1700000000\n"
        "\tline content\n"
    )
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = porcelain
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        result = blame_lines(tmp_path, "file.py", start_line=5)
    assert len(result) == 1
    # Verify -L flag was passed
    call_args = mock_run.call_args[0][0]
    assert any("-L" in arg for arg in call_args)


def test_blame_lines_success(tmp_path: Path) -> None:
    """Successful blame returns parsed BlameLine objects."""
    porcelain = (
        "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0 1 1 1\n"
        "author Dev\n"
        "author-mail <dev@example.com>\n"
        "author-time 1700000000\n"
        "\tsome code\n"
    )
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = porcelain
    with patch("subprocess.run", return_value=mock_result):
        lines = blame_lines(tmp_path, "src/foo.py", start_line=1, end_line=1)
    assert len(lines) == 1
    assert lines[0].content == "some code"


# ---------------------------------------------------------------------------
# BlameCache
# ---------------------------------------------------------------------------


def test_blame_cache_eviction() -> None:
    """Cache should evict oldest entry when full."""
    cache = BlameCache(max_size=2)
    cache.put("k1", [])
    cache.put("k2", [])
    cache.put("k3", [])  # should evict "k1"
    assert cache.get("k1") is None
    assert cache.get("k2") is not None
    assert cache.get("k3") is not None


def test_blame_cache_miss() -> None:
    cache = BlameCache()
    assert cache.get("nonexistent") is None


# ---------------------------------------------------------------------------
# _content_hash
# ---------------------------------------------------------------------------


def test_content_hash_returns_string(tmp_path: Path) -> None:
    f = tmp_path / "test.py"
    f.write_bytes(b"hello world")
    result = _content_hash(tmp_path, "test.py")
    assert result is not None
    assert len(result) == 16


def test_content_hash_missing_file_returns_none(tmp_path: Path) -> None:
    result = _content_hash(tmp_path, "nonexistent.py")
    assert result is None


# ---------------------------------------------------------------------------
# blame_files_parallel
# ---------------------------------------------------------------------------


def test_blame_files_parallel_empty_requests(tmp_path: Path) -> None:
    result = blame_files_parallel(tmp_path, [])
    assert result == {}


def test_blame_files_parallel_with_cache_hit(tmp_path: Path) -> None:
    """Files with cached blame data should not trigger subprocess calls."""
    f = tmp_path / "cached.py"
    f.write_bytes(b"def foo(): pass")
    chash = _content_hash(tmp_path, "cached.py")

    cache = BlameCache()
    import datetime

    from drift.models import BlameLine

    fake_blame = [
        BlameLine(
            line_no=1,
            commit_hash="abc123" * 7 + "ab",
            author="Dev",
            email="d@x.com",
            date=datetime.date.today(),
            content="def foo(): pass",
        )
    ]
    if chash:
        cache.put(chash, fake_blame)

    with patch("drift.ingestion.git_blame.blame_lines") as mock_blame:
        result = blame_files_parallel(tmp_path, [("cached.py", None, None)], cache=cache)

    # blame_lines should NOT have been called (cache hit)
    mock_blame.assert_not_called()
    assert "cached.py" in result


def test_blame_files_parallel_worker_exception(tmp_path: Path) -> None:
    """Exception in blame worker should result in empty list for that file."""
    with patch(
        "drift.ingestion.git_blame.blame_lines",
        side_effect=RuntimeError("unexpected failure"),
    ):
        result = blame_files_parallel(tmp_path, [("file.py", None, None)], cache=BlameCache())
    assert result.get("file.py") == []


def test_blame_files_parallel_deduplicates_ranges(tmp_path: Path) -> None:
    """Multiple requests for same file should be deduplicated."""
    calls = []

    def mock_blame(repo, fpath, start, end, timeout=3.0):
        calls.append(fpath)
        return []

    with patch("drift.ingestion.git_blame.blame_lines", side_effect=mock_blame):
        blame_files_parallel(
            tmp_path,
            [("same.py", 1, 5), ("same.py", 3, 10), ("other.py", None, None)],
        )

    # same.py should appear exactly once
    assert calls.count("same.py") == 1
    assert calls.count("other.py") == 1


def test_blame_files_parallel_widens_range_when_none(tmp_path: Path) -> None:
    """When one request has no range, full file blame should be used."""
    calls: list[tuple] = []

    def mock_blame(repo, fpath, start, end, timeout=3.0):
        calls.append((fpath, start, end))
        return []

    with patch("drift.ingestion.git_blame.blame_lines", side_effect=mock_blame):
        blame_files_parallel(
            tmp_path,
            [("f.py", 1, 5), ("f.py", None, None)],
        )

    for fpath, start, _end in calls:
        if fpath == "f.py":
            assert start is None  # widened to full file


# ---------------------------------------------------------------------------
# extract_branch_hint
# ---------------------------------------------------------------------------


def test_extract_branch_hint_file_not_found(tmp_path: Path) -> None:
    with patch("subprocess.run", side_effect=FileNotFoundError()):
        result = extract_branch_hint(tmp_path, "abc123" * 7)
    assert result is None


def test_extract_branch_hint_timeout(tmp_path: Path) -> None:
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(["git"], 3.0)):
        result = extract_branch_hint(tmp_path, "abc123")
    assert result is None


def test_extract_branch_hint_nonzero_returncode(tmp_path: Path) -> None:
    mock_result = MagicMock()
    mock_result.returncode = 128
    mock_result.stdout = ""
    with patch("subprocess.run", return_value=mock_result):
        result = extract_branch_hint(tmp_path, "abc123")
    assert result is None


def test_extract_branch_hint_merge_branch_pattern(tmp_path: Path) -> None:
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "Merge branch 'feature/my-feature' into main\n"
    with patch("subprocess.run", return_value=mock_result):
        result = extract_branch_hint(tmp_path, "abc123")
    assert result == "feature/my-feature"


def test_extract_branch_hint_merge_pr_pattern(tmp_path: Path) -> None:
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "Merge pull request #42 from org/feat/add-payment\n"
    with patch("subprocess.run", return_value=mock_result):
        result = extract_branch_hint(tmp_path, "abc123")
    assert result == "feat/add-payment"


def test_extract_branch_hint_no_match_returns_none(tmp_path: Path) -> None:
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "Regular commit message\n"
    with patch("subprocess.run", return_value=mock_result):
        result = extract_branch_hint(tmp_path, "abc123")
    assert result is None
