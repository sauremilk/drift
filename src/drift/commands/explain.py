"""drift explain — describe a signal in the terminal."""

from __future__ import annotations

import click

from drift.commands import console

# ---- Signal reference data ------------------------------------------------
# Each entry: (abbreviation, SignalType value, full name, short description,
#              what_it_detects, example, default_weight, tuning_hint)

_SIGNAL_INFO: dict[str, dict[str, str]] = {
    "PFS": {
        "signal_type": "pattern_fragmentation",
        "name": "Pattern Fragmentation Score",
        "weight": "0.16",
        "description": (
            "Detects when the same category of code pattern (e.g. error handling, "
            "validation, data access) has multiple incompatible implementation "
            "variants within a single module."
        ),
        "detects": (
            "Copy-paste-modify patterns typical of multi-session AI generation. "
            "For example, three different error-handling strategies in the same "
            "package: one using custom exceptions, one using return codes, one "
            "using bare try/except with logging."
        ),
        "example": (
            "  # Variant A — custom exception\n"
            "  raise ValidationError(msg)\n\n"
            "  # Variant B — return code\n"
            "  return None, error_msg\n\n"
            "  # Variant C — bare except\n"
            "  try: ... except: log(e)"
        ),
        "fix_hint": (
            "Consolidate to one canonical pattern per category per module. "
            "Choose the most explicit variant and refactor the others."
        ),
    },
    "AVS": {
        "signal_type": "architecture_violation",
        "name": "Architecture Violation Score",
        "weight": "0.16",
        "description": (
            "Detects imports that violate layer boundaries — e.g. a route handler "
            "importing directly from a database module instead of through a "
            "service layer. Also detects circular dependencies and high blast-radius hubs."
        ),
        "detects": (
            "Layer leaks, circular dependencies, and modules with excessive "
            "incoming dependencies (blast-radius hubs). Supports policy-based "
            "allowed_cross_layer exceptions and omnilayer recognition "
            "(config/utils/types are cross-cutting)."
        ),
        "example": (
            "  # routes/users.py imports directly from db layer:\n"
            "  from db.models import User  # AVS: layer violation\n\n"
            "  # Should go through service layer:\n"
            "  from services.users import get_user"
        ),
        "fix_hint": (
            "Introduce or enforce a service/mediator layer between the violating "
            "modules. For circular deps, extract shared types into a common module."
        ),
    },
    "MDS": {
        "signal_type": "mutant_duplicate",
        "name": "Mutant Duplicate Score",
        "weight": "0.13",
        "description": (
            "Detects near-duplicate functions within the same file — functions "
            "with ≥80% structural similarity (AST Jaccard) that differ only in "
            "minor details."
        ),
        "detects": (
            "Copy-paste-modify anti-pattern where a function was duplicated and "
            "slightly altered instead of being parameterized. Common when AI "
            "generates multiple similar handlers in one session."
        ),
        "example": (
            "  def create_user(data):\n"
            "      validate(data); db.insert('users', data); return 201\n\n"
            "  def create_order(data):  # 85% similar\n"
            "      validate(data); db.insert('orders', data); return 201"
        ),
        "fix_hint": (
            "Extract the common structure into a generic function and parameterize "
            "the differences (table name, validation logic)."
        ),
    },
    "EDS": {
        "signal_type": "explainability_deficit",
        "name": "Explainability Deficit Score",
        "weight": "0.09",
        "description": (
            "Detects high-complexity functions lacking documentation, type hints, "
            "or test coverage — especially when AI-attributed."
        ),
        "detects": (
            "Functions with cyclomatic complexity >10 and >10 LOC that have no "
            "docstring and incomplete type annotations. Signals 'accepted without "
            "understanding' code that is hard to maintain."
        ),
        "example": (
            "  def process_payment(order, user, config, retries=3):\n"
            "      # 45 lines, complexity 12, no docstring, no types\n"
            "      if order.status == ...:\n"
            "          ..."
        ),
        "fix_hint": (
            "Add a docstring explaining intent and edge cases. Add type hints "
            "for parameters and return value. Consider splitting if complexity >15."
        ),
    },
    "TVS": {
        "signal_type": "temporal_volatility",
        "name": "Temporal Volatility Score",
        "weight": "0.13",
        "description": (
            "Detects anomalous change frequency — files modified far more often "
            "than their peers, especially with many different authors."
        ),
        "detects": (
            "Hot spots with z-score volatility above threshold, high author count, "
            "and defect-correlated commits. Particularly signals AI-generated code "
            "that requires constant rework."
        ),
        "example": (
            "  # api/handlers.py: 47 commits in 30 days, 8 authors\n"
            "  # Module average: 6 commits, 2 authors\n"
            "  # → z-score: 3.2 (anomalous)"
        ),
        "fix_hint": (
            "Investigate why the file changes so often. Common causes: unclear "
            "ownership, missing abstractions, or unstable interfaces."
        ),
    },
    "SMS": {
        "signal_type": "system_misalignment",
        "name": "System Misalignment Score",
        "weight": "0.08",
        "description": (
            "Detects when recent commits introduce patterns, dependencies, or "
            "conventions not established in the target module."
        ),
        "detects": (
            "Locally correct but globally incoherent changes — e.g. a PR that "
            "introduces requests in a module that uses httpx, or adds callback-"
            "style error handling in a module using exceptions."
        ),
        "example": (
            "  # Module uses httpx everywhere:\n"
            "  import httpx\n\n"
            "  # New AI-generated code adds:\n"
            "  import requests  # SMS: novel dependency"
        ),
        "fix_hint": (
            "Align new code with existing module conventions. Adopt the same "
            "HTTP client, error strategy, and naming patterns as the surrounding code."
        ),
    },
    "DIA": {
        "signal_type": "doc_impl_drift",
        "name": "Doc-Implementation Drift",
        "weight": "0.04",
        "description": (
            "Detects divergence between architectural documentation (ADRs, README) "
            "and actual code structure."
        ),
        "detects": (
            "Claims in documentation that no longer match the implementation — "
            "e.g. README says 'uses SQLite' but code imports PostgreSQL. "
            "Parses markdown AST and compares against import graph."
        ),
        "example": (
            "  # README.md: 'Authentication uses JWT tokens'\n"
            "  # Actual code: session-based auth only, no JWT import"
        ),
        "fix_hint": (
            "Update documentation to match current implementation, or align "
            "implementation with documented architecture."
        ),
    },
    "BEM": {
        "signal_type": "broad_exception_monoculture",
        "name": "Broad Exception Monoculture",
        "weight": "0.04",
        "description": (
            "Detects modules where exception handling is uniformly broad — "
            "catching Exception, BaseException, or bare except without re-raise."
        ),
        "detects": (
            "Consistent wrongness: every handler catches everything and swallows "
            "the error (pass/log/print). Real error classes are silently discarded. "
            "Excludes intentional error boundaries (middleware, error_handler modules)."
        ),
        "example": (
            "  try:\n"
            "      result = do_work()\n"
            "  except Exception:\n"
            "      logger.error('failed')  # swallowed, no re-raise"
        ),
        "fix_hint": (
            "Catch specific exception types. Re-raise or convert to a domain "
            "exception instead of swallowing."
        ),
    },
    "TPD": {
        "signal_type": "test_polarity_deficit",
        "name": "Test Polarity Deficit",
        "weight": "0.04",
        "description": (
            "Detects test suites that only test the happy path — no negative "
            "tests, no boundary checks, no exception assertions."
        ),
        "detects": (
            "Test files with ≥5 test functions but zero uses of pytest.raises, "
            "assertRaises, or boundary-condition patterns. Signals false confidence "
            "from one-sided test coverage."
        ),
        "example": (
            "  def test_create_user():\n"
            "      assert create_user(valid_data).id > 0\n\n"
            "  # Missing:\n"
            "  # def test_create_user_invalid_email():\n"
            "  #     with pytest.raises(ValidationError): ..."
        ),
        "fix_hint": (
            "Add negative tests: invalid inputs, boundary values, expected "
            "exceptions. Aim for at least 20% negative-path coverage."
        ),
    },
    "GCD": {
        "signal_type": "guard_clause_deficit",
        "name": "Guard Clause Deficit",
        "weight": "0.03",
        "description": (
            "Detects public, non-trivial functions that uniformly lack input "
            "validation guard clauses."
        ),
        "detects": (
            "Modules where public functions have no isinstance checks, no "
            "assert statements, and no early-return validation. A structural "
            "vulnerability where one wrong assumption propagates everywhere."
        ),
        "example": (
            "  def transfer_funds(source, target, amount):\n"
            "      # No validation of amount > 0, accounts exist, etc.\n"
            "      source.balance -= amount\n"
            "      target.balance += amount"
        ),
        "fix_hint": (
            "Add guard clauses at function entry: validate types, ranges, "
            "and preconditions before proceeding with business logic."
        ),
    },
    "NBV": {
        "signal_type": "naming_contract_violation",
        "name": "Naming Contract Violation",
        "weight": "0.04",
        "description": (
            "Detects functions whose name implies a contract that the "
            "implementation doesn't fulfil."
        ),
        "detects": (
            "validate_* functions that never raise or return False. "
            "is_* / has_* functions that don't return bool. "
            "get_* functions that never return a value. "
            "Signals intention drift between name and behavior."
        ),
        "example": (
            "  def validate_email(email):\n"
            "      # Just logs, never raises or returns False\n"
            "      logger.info(f'checking {email}')\n"
            "      return email  # not a validation result"
        ),
        "fix_hint": (
            "Align implementation with naming contract: validate_* should "
            "raise on invalid input or return bool. Rename if behavior is intentional."
        ),
    },
    "BAT": {
        "signal_type": "bypass_accumulation",
        "name": "Bypass Accumulation",
        "weight": "0.03",
        "description": (
            "Detects quality-bypass markers accumulating beyond a density "
            "threshold (>0.05 markers per LOC)."
        ),
        "detects": (
            "# type: ignore, # noqa, # pragma: no cover, typing.Any, cast(), "
            "@pytest.mark.skip, TODO/FIXME/HACK/XXX comments. Each individually "
            "harmless, but accumulation signals process drift."
        ),
        "example": (
            "  result: Any = get_data()  # type: ignore[assignment]\n"
            "  value = cast(int, result)  # noqa: S101\n"
            "  # TODO: fix this properly  # HACK: temporary workaround"
        ),
        "fix_hint": (
            "Resolve bypass markers systematically. Replace Any with proper "
            "types. Remove outdated TODO/FIXME comments. Fix the underlying "
            "issues that noqa/type:ignore are suppressing."
        ),
    },
    "ECM": {
        "signal_type": "exception_contract_drift",
        "name": "Exception Contract Drift",
        "weight": "0.03",
        "description": (
            "Detects public functions whose exception profile changed across "
            "recent commits while the signature remained stable."
        ),
        "detects": (
            "Contract drift: a function starts raising new exceptions or stops "
            "raising documented ones without signature changes. Callers silently "
            "become incorrect. Uses git history comparison of AST exception profiles."
        ),
        "example": (
            "  # v1: raises ValueError on bad input\n"
            "  # v2: silently returns None on bad input\n"
            "  # → callers still expect ValueError"
        ),
        "fix_hint": (
            "Document exception changes in the signature (docstring, type hints). "
            "Update callers when exception behavior changes. Consider adding "
            "Protocol or abstract base class to formalize contracts."
        ),
    },
}

# Build a lookup by abbreviation (case-insensitive) and by signal_type value
_LOOKUP: dict[str, dict[str, str]] = {}
for _abbr, _info in _SIGNAL_INFO.items():
    _LOOKUP[_abbr.lower()] = _info
    _LOOKUP[_info["signal_type"]] = _info


def _all_abbreviations() -> list[str]:
    return sorted(_SIGNAL_INFO.keys())


@click.command()
@click.argument("signal", required=False, default=None)
@click.option("--list", "-l", "list_all", is_flag=True, help="List all signals.")
def explain(signal: str | None, list_all: bool) -> None:
    """Explain a drift signal: drift explain PFS"""
    if list_all or signal is None:
        _print_signal_list()
        return

    key = signal.strip()

    # Check for error code first (DRIFT-XXXX pattern)
    if key.upper().startswith("DRIFT-"):
        _print_error_code_detail(key.upper())
        return

    key_lower = key.lower()
    info = _LOOKUP.get(key_lower)
    if info is None:
        abbrs = ", ".join(_all_abbreviations())
        console.print(
            f"[red]Unknown signal:[/red] '{signal}'\n"
            f"[dim]Available signals: {abbrs}[/dim]\n"
            f"[dim]Run [bold]drift explain --list[/bold] for details.[/dim]"
        )
        raise SystemExit(1)

    _print_signal_detail(info)


def _print_signal_list() -> None:
    """Print a compact table of all signals."""
    from rich.table import Table

    table = Table(title="Drift Signals", show_lines=False)
    table.add_column("Abbr", style="bold cyan", min_width=5)
    table.add_column("Signal", min_width=28)
    table.add_column("Weight", justify="right", min_width=6)
    table.add_column("Description", min_width=40)

    for abbr in _all_abbreviations():
        info = _SIGNAL_INFO[abbr]
        table.add_row(
            abbr,
            info["name"],
            info["weight"],
            info["description"][:80] + ("…" if len(info["description"]) > 80 else ""),
        )

    console.print(table)
    console.print("\n[dim]Run [bold]drift explain <SIGNAL>[/bold] for full details.[/dim]")


def _print_signal_detail(info: dict[str, str]) -> None:
    """Print detailed explanation of a single signal."""
    from rich.panel import Panel
    from rich.text import Text

    # Find abbreviation for this signal
    abbr = next(
        (a for a, i in _SIGNAL_INFO.items() if i is info),
        "?",
    )

    body = Text()
    body.append(f"{info['name']}", style="bold")
    body.append(f"  ({abbr})\n", style="dim")
    body.append(f"Default weight: {info['weight']}\n\n", style="dim")

    body.append("What it detects\n", style="bold underline")
    body.append(f"{info['detects']}\n\n")

    body.append("Example\n", style="bold underline")
    body.append(f"{info['example']}\n\n", style="dim")

    body.append("How to fix\n", style="bold underline")
    body.append(f"{info['fix_hint']}\n", style="green")

    console.print(Panel(body, border_style="cyan", title=f"[bold]Signal: {abbr}[/bold]"))


def _print_error_code_detail(code: str) -> None:
    """Print detailed explanation of a Drift error code (DRIFT-XXXX)."""
    from rich.panel import Panel
    from rich.text import Text

    from drift.errors import ERROR_REGISTRY

    info = ERROR_REGISTRY.get(code)
    if info is None:
        codes = ", ".join(sorted(ERROR_REGISTRY.keys()))
        console.print(
            f"[red]Unknown error code:[/red] '{code}'\n"
            f"[dim]Known codes: {codes}[/dim]"
        )
        raise SystemExit(1)

    category_label = {
        "user": "User Error (exit code 1)",
        "system": "System Error (exit code 2)",
        "analysis": "Analysis Error (exit code 3)",
    }

    body = Text()
    body.append(f"{code}\n", style="bold")
    body.append(f"Category: {category_label.get(info.category, info.category)}\n\n", style="dim")

    body.append("What happens\n", style="bold underline")
    body.append(f"  {info.summary}\n\n")

    body.append("Why\n", style="bold underline")
    body.append(f"  {info.why}\n\n")

    body.append("What to do\n", style="bold underline")
    body.append(f"  {info.action}\n", style="green")

    console.print(Panel(body, border_style="yellow", title=f"[bold]Error: {code}[/bold]"))
