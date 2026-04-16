"""Error code registry and structured error metadata.

Error code ranges:
  DRIFT-1xxx  User errors (config, CLI usage, invalid input)
  DRIFT-2xxx  System errors (I/O, git, permissions, dependencies)
  DRIFT-3xxx  Analysis errors (AST parse failures, signal errors)

Each error follows the format:
  [DRIFT-XXXX] <what happened> → <why> → <what to do>

Exit codes:
  0  — Success (no blocking findings)
  1  — Findings exceed severity threshold (--fail-on gate)
  2  — Configuration or user input error
  3  — Analysis pipeline error (partial results may exist)
  4  — System error (I/O, git, permissions)
  130 — Interrupted (Ctrl+C)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# Exit code constants — use these instead of magic numbers
# ---------------------------------------------------------------------------

EXIT_OK = 0
EXIT_FINDINGS_ABOVE_THRESHOLD = 1
EXIT_CONFIG_ERROR = 2
EXIT_ANALYSIS_ERROR = 3
EXIT_SYSTEM_ERROR = 4
EXIT_INTERRUPTED = 130


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
        summary="Configuration file is not valid",
        why="Parse error: {reason}",
        action="Check syntax near line {line} in the config file",
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
    "DRIFT-1012": ErrorInfo(
        code="DRIFT-1012",
        summary="Invalid CLI usage",
        why="{reason}",
        action=(
            "Run 'drift start' for the guided path or "
            "'drift --help' / 'drift <command> --help' for usage"
        ),
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
        action="Check that the --output path is writable and its parent directory exists",
        category="system",
    ),
    "DRIFT-2010": ErrorInfo(
        code="DRIFT-2010",
        summary="Optional dependency missing: {package}",
        why="This feature requires the '{extra}' extra",
        action="Install with: pip install drift-analyzer[{extra}]",
        category="system",
    ),
    "DRIFT-2011": ErrorInfo(
        code="DRIFT-2011",
        summary="Drift installation incomplete: internal module not importable: {module}",
        why="One or more core Drift submodules failed to import after package installation",
        action="Reinstall with: pip install --upgrade 'drift-analyzer[mcp]'",
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


# Example interpolation values used by `drift explain DRIFT-XXXX`.
# They document a concrete remediation path without requiring runtime context.
ERROR_EXPLAIN_DEFAULTS: dict[str, dict[str, str]] = {
    "DRIFT-2010": {"package": "mcp", "extra": "mcp"},
}


def _format_template_with_defaults(template: str, defaults: dict[str, str]) -> str:
    """Best-effort interpolation for explain docs with graceful fallback."""
    if not defaults:
        return template
    try:
        return template.format(**defaults)
    except KeyError:
        return template


def format_error_info_for_explain(code: str, info: ErrorInfo) -> tuple[str, str, str]:
    """Return explain-ready summary/why/action fields for an error code."""
    defaults = ERROR_EXPLAIN_DEFAULTS.get(code, {})
    return (
        _format_template_with_defaults(info.summary, defaults),
        _format_template_with_defaults(info.why, defaults),
        _format_template_with_defaults(info.action, defaults),
    )
