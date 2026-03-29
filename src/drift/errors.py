"""Structured error codes and exception hierarchy for Drift.

Error code ranges:
  DRIFT-1xxx  User errors (config, CLI usage, invalid input)
  DRIFT-2xxx  System errors (I/O, git, permissions, dependencies)
  DRIFT-3xxx  Analysis errors (AST parse failures, signal errors)

Each error follows the format:
  [DRIFT-XXXX] <what happened> → <why> → <what to do>
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ErrorInfo:
    """Reference data for a single error code."""

    code: str
    summary: str
    why: str
    action: str
    category: str  # "user" | "system" | "analysis"

    def format(self, **kwargs: Any) -> str:
        """Render the structured error message with optional interpolation."""
        what = self.summary.format(**kwargs) if kwargs else self.summary
        why = self.why.format(**kwargs) if kwargs else self.why
        action = self.action.format(**kwargs) if kwargs else self.action
        return f"[{self.code}] {what} → {why} → {action}"


# ---------------------------------------------------------------------------
# Error code registry
# ---------------------------------------------------------------------------

ERROR_REGISTRY: dict[str, ErrorInfo] = {
    # ── User errors (1xxx) ────────────────────────────────────────────────
    "DRIFT-1001": ErrorInfo(
        code="DRIFT-1001",
        summary="Invalid config value in {config_path}",
        why="Field '{field}' {reason}",
        action="Fix the value at line {line} or run 'drift config show' to see defaults",
        category="user",
    ),
    "DRIFT-1002": ErrorInfo(
        code="DRIFT-1002",
        summary="Configuration file is not valid YAML",
        why="YAML parse error: {reason}",
        action="Check syntax near line {line} — common causes: wrong indentation, missing colon",
        category="user",
    ),
    "DRIFT-1003": ErrorInfo(
        code="DRIFT-1003",
        summary="Unknown signal '{signal}'",
        why="'{signal}' is not a recognized signal abbreviation or type name",
        action="Run 'drift explain --list' to see available signals",
        category="user",
    ),
    "DRIFT-1010": ErrorInfo(
        code="DRIFT-1010",
        summary="Unknown option '{option}'",
        why="This flag is not recognized by the '{command}' command",
        action="Did you mean '{suggestion}'? Run 'drift {command} --help' for options",
        category="user",
    ),
    "DRIFT-1011": ErrorInfo(
        code="DRIFT-1011",
        summary="Missing required argument '{argument}'",
        why="The '{command}' command requires this argument",
        action="Run 'drift {command} --help' for usage",
        category="user",
    ),
    "DRIFT-1020": ErrorInfo(
        code="DRIFT-1020",
        summary="Baseline file not found at {path}",
        why="No baseline has been saved yet for this repository",
        action="Run 'drift baseline save' first",
        category="user",
    ),
    # ── System errors (2xxx) ──────────────────────────────────────────────
    "DRIFT-2001": ErrorInfo(
        code="DRIFT-2001",
        summary="Repository path not found: {path}",
        why="The path does not exist or is not a directory",
        action="Check the --repo argument and ensure the directory exists",
        category="system",
    ),
    "DRIFT-2002": ErrorInfo(
        code="DRIFT-2002",
        summary="Git operation failed",
        why="{reason}",
        action="Ensure git is installed and the path is a git repository",
        category="system",
    ),
    "DRIFT-2003": ErrorInfo(
        code="DRIFT-2003",
        summary="File I/O error: {path}",
        why="{reason}",
        action="Check file permissions and disk space",
        category="system",
    ),
    "DRIFT-2010": ErrorInfo(
        code="DRIFT-2010",
        summary="Optional dependency missing: {package}",
        why="This feature requires the '{extra}' extra",
        action="Install with: pip install drift-analyzer[{extra}]",
        category="system",
    ),
    # ── Analysis errors (3xxx) ────────────────────────────────────────────
    "DRIFT-3001": ErrorInfo(
        code="DRIFT-3001",
        summary="AST parse error in {path}",
        why="Python syntax error at line {line}: {reason}",
        action="Fix the syntax error or exclude the file via 'exclude' in drift.yaml",
        category="analysis",
    ),
    "DRIFT-3002": ErrorInfo(
        code="DRIFT-3002",
        summary="Signal '{signal}' raised an unexpected error",
        why="{reason}",
        action="Run with -v for the full traceback and report the issue",
        category="analysis",
    ),
}


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


class DriftError(Exception):
    """Base exception for all structured Drift errors."""

    exit_code: int = 2  # default

    def __init__(
        self,
        code: str,
        message: str | None = None,
        *,
        context: str | None = None,
        **kwargs: Any,
    ) -> None:
        self.code = code
        self._kwargs = kwargs
        self._context = context

        info = ERROR_REGISTRY.get(code)
        if info and not message:
            self._formatted = info.format(**kwargs)
        elif message:
            self._formatted = f"[{code}] {message}"
        else:
            self._formatted = f"[{code}] Unknown error"

        super().__init__(self._formatted)

    @property
    def hint(self) -> str | None:
        """Return an explain hint for this error code."""
        if self.code in ERROR_REGISTRY:
            return f"Run 'drift explain {self.code}' for details."
        return None

    @property
    def detail(self) -> str:
        """Full formatted message including optional YAML/code context."""
        parts = [self._formatted]
        if self._context:
            parts.append("")
            parts.append(self._context)
        if self.hint:
            parts.append("")
            parts.append(self.hint)
        return "\n".join(parts)


class DriftConfigError(DriftError):
    """User-caused configuration error.  Exit code 1."""

    exit_code = 1


class DriftSystemError(DriftError):
    """System/environment error.  Exit code 2."""

    exit_code = 2


class DriftAnalysisError(DriftError):
    """Analysis pipeline error.  Exit code 3."""

    exit_code = 3


# ---------------------------------------------------------------------------
# YAML context helper
# ---------------------------------------------------------------------------


def yaml_context_snippet(raw_yaml: str, target_line: int, context: int = 2) -> str:
    """Return a few lines of YAML surrounding *target_line* (1-indexed).

    Format matches rustc-style diagnostics::

        10 │ weights:
        11 │   avs: 0.16
      → 12 │   pfs: "not_a_number"
        13 │   mds: 0.13
    """
    lines = raw_yaml.splitlines()
    first = max(0, target_line - 1 - context)
    last = min(len(lines), target_line + context)
    gutter_w = len(str(last))

    out: list[str] = []
    for idx in range(first, last):
        lineno = idx + 1
        marker = "→" if lineno == target_line else " "
        out.append(f"  {marker} {lineno:>{gutter_w}} │ {lines[idx]}")
    return "\n".join(out)


def _find_yaml_line(raw_yaml: str, field_path: tuple[str | int, ...]) -> int | None:
    """Best-effort: find the 1-indexed line of a dotted field path in raw YAML.

    Walks the path segments in order and looks for the key in the text.
    Returns *None* if it cannot be located.
    """
    lines = raw_yaml.splitlines()
    # Walk from the top, matching each segment
    start = 0
    for segment in field_path:
        if isinstance(segment, int):
            continue  # list indices — skip, stay at current block
        key = str(segment)
        for i in range(start, len(lines)):
            stripped = lines[i].lstrip()
            if stripped.startswith(f"{key}:") or stripped.startswith(f"{key} :"):
                start = i + 1
                target = i + 1  # 1-indexed
                break
        else:
            return None
    return target  # type: ignore[possibly-undefined]  # noqa: F821
