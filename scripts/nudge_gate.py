"""Pre-commit gate: block commits when the last drift_nudge demanded a REVERT.

Reads ``.drift-cache/last_nudge.json`` (written by ``drift.api.nudge``) and
refuses to let a commit proceed when all of the following hold:

  1. The last nudge recorded ``revert_recommended == true``.
  2. Every file listed in ``changed_files`` is still staged or modified in
     the working tree.
  3. The current contents of those files hash to the same value as when the
     nudge ran (i.e. the agent did **not** actually revert).

Configuration in ``drift.yaml``::

    nudge_gate:
      on_missing: warn   # or "block" (default: warn)

Override via environment:

    DRIFT_SKIP_NUDGE_GATE=1   — skip the gate entirely (escape hatch)

Exit codes:
  0  — gate passed (nothing to enforce, or REVERT was honoured).
  1  — gate failed (commit should be aborted).
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

_ENV_SKIP = "DRIFT_SKIP_NUDGE_GATE"
_STATE_FILE = "last_nudge.json"
_DEFAULT_CACHE_DIR = ".drift-cache"
_DEFAULT_ON_MISSING = "warn"  # or "block"


def _log(msg: str, *, err: bool = False) -> None:
    stream = sys.stderr if err else sys.stdout
    print(f"[drift-nudge-gate] {msg}", file=stream)


def _read_state(repo_root: Path, cache_dir: str) -> dict[str, Any] | None:
    path = repo_root / cache_dir / _STATE_FILE
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _staged_files(repo_root: Path) -> set[str]:
    """Return files staged for commit (posix-relative to repo root)."""
    try:
        proc = subprocess.run(  # noqa: S603
            ["git", "diff", "--name-only", "--cached", "--relative"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=repo_root,
            check=True,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return set()
    return {line.strip() for line in proc.stdout.splitlines() if line.strip()}


def _file_hash(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    except OSError:
        return None


def _load_on_missing_policy(repo_root: Path) -> str:
    """Read ``nudge_gate.on_missing`` from drift.yaml, default ``warn``."""
    cfg = repo_root / "drift.yaml"
    if not cfg.is_file():
        return _DEFAULT_ON_MISSING
    try:
        text = cfg.read_text(encoding="utf-8")
    except OSError:
        return _DEFAULT_ON_MISSING
    # Minimal, dependency-free parse — we only look for the specific key.
    in_section = False
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if line.startswith("nudge_gate:"):
            in_section = True
            continue
        if in_section:
            stripped = line.lstrip()
            if line == stripped:  # section ended
                in_section = False
                continue
            if stripped.startswith("on_missing:"):
                value = stripped.split(":", 1)[1].strip().strip('"').strip("'")
                if value in ("warn", "block"):
                    return value
    return _DEFAULT_ON_MISSING


def _staged_src_or_tests(staged: set[str]) -> bool:
    return any(
        fp.endswith(".py") and (fp.startswith("src/") or fp.startswith("tests/"))
        for fp in staged
    )


def run(repo_root: Path) -> int:
    if os.environ.get(_ENV_SKIP, "").strip() not in ("", "0"):
        _log("skipped via DRIFT_SKIP_NUDGE_GATE")
        return 0

    cache_dir = _DEFAULT_CACHE_DIR
    state = _read_state(repo_root, cache_dir)
    staged = _staged_files(repo_root)

    if state is None:
        policy = _load_on_missing_policy(repo_root)
        if _staged_src_or_tests(staged) and policy == "block":
            _log(
                "no recent drift_nudge state found — commit blocked "
                "(set nudge_gate.on_missing: warn in drift.yaml to soften)",
                err=True,
            )
            return 1
        if _staged_src_or_tests(staged):
            _log(
                "no recent drift_nudge state found — consider running "
                "drift_nudge before committing (warn-only)",
            )
        return 0

    if not state.get("revert_recommended"):
        return 0

    changed = [fp for fp in state.get("changed_files", []) if isinstance(fp, str)]
    if not changed:
        return 0

    # Only enforce when the flagged files are actually part of this commit.
    overlap = [fp for fp in changed if fp in staged]
    if not overlap:
        # The agent may already have reverted or staged a different set of files.
        return 0

    # Verify hashes — if the files changed since the nudge recorded them,
    # the agent has taken action, so don't block.
    stored_hashes: dict[str, str] = state.get("file_hashes") or {}
    unchanged: list[str] = []
    for fp in overlap:
        stored = stored_hashes.get(fp)
        current = _file_hash(repo_root / fp)
        if stored and current and stored == current:
            unchanged.append(fp)

    if not unchanged:
        return 0

    _log(
        "last drift_nudge recommended REVERT but the following files are "
        "still unchanged in this commit:",
        err=True,
    )
    for fp in unchanged:
        _log(f"  - {fp}", err=True)
    _log(
        "Revert the edits, run drift_nudge again, or bypass with "
        f"{_ENV_SKIP}=1 if intentional.",
        err=True,
    )
    return 1


def main() -> int:
    # Pre-commit runs from the repo root.  Fall back to cwd.
    return run(Path.cwd())


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
