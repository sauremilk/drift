# ADR-004: Subprocess Git Parsing over GitPython

**Status:** Accepted
**Date:** 2025-12-15
**Decision Makers:** @mick-gsk

## Context

Drift needs to extract git history for two purposes:
1. **Temporal Volatility Signal (TVS):** Commit frequency and file-level churn rates.
2. **AI Attribution:** Heuristic classification of commits as likely AI-generated.

GitPython is the de-facto Python library for git operations. However, it wraps git commands in Python objects with significant overhead — particularly when iterating large commit histories.

## Decision

Use `subprocess.run()` to call `git log` directly with structured output parsing. Specifically:

```python
git log --pretty=format:'<RECORD_SEP>%H|%an|%ae|%aI|%s' --numstat
```

### Key Design Choices

**1. Record separator strategy.**
Git log output with `--numstat` interleaves commit metadata and per-file stats. We use a custom `<RECORD_SEP>` marker (not a standard ASCII control character) to delimit commit records, then split on that marker for parsing. This avoids fragile blank-line splitting that breaks when commit messages contain empty lines.

**2. `--numstat` over `--stat`.**
`--stat` produces human-readable output with column alignment and abbreviation (`... | 42 +++---`). `--numstat` produces machine-readable tab-separated `additions\tdeletions\tfilename`. Parsing `--numstat` is trivial and robust; parsing `--stat` requires regex that breaks on filenames with special characters.

**3. ISO 8601 timestamps (`%aI`).**
Author date in ISO 8601 format (`2024-01-15T10:30:00+01:00`) is unambiguous and parseable with `datetime.fromisoformat()`. The alternative `%ai` (similar but with space-separated timezone) requires manual parsing.

**4. Single git invocation.**
One `git log` call retrieves all needed data (hashes, authors, dates, messages, per-file stats). This avoids N+1 patterns where each commit requires a second call for diff stats.

## Performance Measurements

Benchmarked against a repository with ~4,200 commits:

| Approach | Wall Time | Peak Memory |
|----------|-----------|-------------|
| GitPython `iter_commits()` + per-commit `.stats` | 18.4s | ~380 MB |
| GitPython `iter_commits()` (metadata only) | 3.2s | ~120 MB |
| subprocess `git log --numstat` (single call) | 0.9s | ~25 MB |

The subprocess approach is **~20x faster** than full GitPython iteration and uses **~15x less memory**, because:
- No Python object instantiation per commit.
- No lazy `.stats` property triggering a second git call per commit.
- String parsing of a single stdout buffer is cheaper than constructing `Commit` objects with full parent/tree references.

## Trade-offs

| Gain | Lose |
|------|------|
| 20x faster git history ingestion | Requires `git` binary on PATH (not embedded) |
| ~15x less memory usage | No access to GitPython's higher-level APIs (diff objects, tree traversal) |
| Single process, no leaked file handles | Must handle subprocess errors manually |
| Trivial output format to parse | Tied to `git log` output format (unlikely to change) |

## Alternatives Considered

### Alternative 1: Pure GitPython

Use GitPython for all git operations.

**Rejected because:** The `Commit.stats` property triggers a subprocess call per commit, creating an N+1 problem. For 4,000 commits, this means 4,001 git invocations instead of 1. GitPython's object model also holds references to parent commits, creating memory pressure on large histories.

### Alternative 2: pygit2 (libgit2 bindings)

Use pygit2 for in-process git access via libgit2.

**Rejected because:** pygit2 requires libgit2 as a C dependency, which complicates installation on Windows and in CI environments. The performance gain over subprocess is marginal (~20-30% faster) but the packaging burden is significant. We already have `git` as a runtime dependency.

### Alternative 3: Dulwich (pure Python git)

Use Dulwich for zero-dependency git access.

**Rejected because:** Dulwich is slower than subprocess for log-style queries. It's designed for low-level pack file access, not high-level history traversal. It would require reimplementing `git log` equivalent logic.

## Error Handling

- If `git` is not on PATH, `subprocess.run` raises `FileNotFoundError` — caught and re-raised as a descriptive error.
- If the working directory is not a git repository, `git log` exits with code 128 — detected via `returncode` check.
- Malformed output lines (missing fields, unexpected separators) are skipped with a warning logged, rather than crashing the entire analysis.

## Consequences

- `git` must be available in the runtime environment. This is documented in README prerequisites.
- GitPython remains as a declared dependency (used for `git.Repo` repository validation and remote URL extraction in `git_history.py`), but is not used for history iteration.
- Future signals that need git data (e.g., blame-based ownership) should extend the subprocess approach rather than introducing GitPython iteration.
