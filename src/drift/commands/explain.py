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
    "COD": {
        "signal_type": "cohesion_deficit",
        "name": "Cohesion Deficit",
        "weight": "0.01",
        "description": (
            "Detects modules or classes with low internal cohesion — members "
            "that don't share data or call each other, indicating the unit "
            "bundles unrelated responsibilities."
        ),
        "detects": (
            "Classes where methods operate on disjoint subsets of attributes, "
            "or modules where top-level functions share no imports or calls. "
            "Signals 'kitchen-sink' modules that grew by accretion."
        ),
        "example": (
            "  class UserService:\n"
            "      def create_user(self, data): ...   # uses self.db\n"
            "      def send_email(self, msg): ...     # uses self.smtp\n"
            "      def generate_report(self, q): ...  # uses self.analytics"
        ),
        "fix_hint": (
            "Split the module or class along cohesion boundaries. Group "
            "functions that share the same data and dependencies."
        ),
    },
    "CCC": {
        "signal_type": "co_change_coupling",
        "name": "Co-Change Coupling",
        "weight": "0.005",
        "description": (
            "Detects file pairs that are almost always changed together in "
            "commits, indicating hidden coupling not visible in the import graph."
        ),
        "detects": (
            "Files with co-change frequency above threshold (e.g. >80% of "
            "commits touching file A also touch file B). Signals implicit "
            "contracts, shared assumptions, or missing abstractions."
        ),
        "example": (
            "  # 9 out of 10 commits that touch models/user.py also\n"
            "  # touch serializers/user.py and tests/test_user.py\n"
            "  # → hidden coupling between model and serializer"
        ),
        "fix_hint": (
            "Investigate whether coupled files share an implicit contract. "
            "Consider extracting shared types or introducing an interface "
            "to make the dependency explicit."
        ),
    },
    "TSA": {
        "signal_type": "ts_architecture",
        "name": "TypeScript Architecture",
        "weight": "0.0 (report-only)",
        "description": (
            "Detects architecture violations in TypeScript/JavaScript code "
            "(layer leaks, circular module cycles, cross-package violations, "
            "and UI-to-infra imports)."
        ),
        "detects": (
            "TS/JS-specific structural violations from the tsjs rule suite. "
            "Only active when .ts/.tsx/.js/.jsx files are present in the repository."
        ),
        "example": (
            "  # web/ui/page.ts directly imports infra adapter:\n"
            "  import { SqlUserRepo } from '../infra/sql/user_repo'  # TSA"
        ),
        "fix_hint": (
            "Keep frontend/application/infrastructure boundaries explicit. "
            "Route cross-layer access through interfaces or service boundaries."
        ),
    },
    "CXS": {
        "signal_type": "cognitive_complexity",
        "name": "Cognitive Complexity",
        "weight": "0.0 (report-only)",
        "description": (
            "Detects functions with excessive cognitive complexity — deeply "
            "nested control flow, many branches, and interleaved logic that "
            "is hard to follow mentally."
        ),
        "detects": (
            "Functions exceeding a cognitive complexity threshold (default: 15). "
            "Unlike cyclomatic complexity, cognitive complexity penalises "
            "nesting depth and break-of-flow structures more heavily."
        ),
        "example": (
            "  def process_order(order, user, config):\n"
            "      if order.status == 'new':          # +1\n"
            "          for item in order.items:        # +2 (nesting)\n"
            "              if item.stock > 0:          # +3 (nesting)\n"
            "                  if user.is_premium:     # +4 (nesting)\n"
            "                      ...                 # CC already 10+"
        ),
        "fix_hint": (
            "Extract nested blocks into well-named helper functions. "
            "Use early returns and guard clauses to reduce nesting depth. "
            "Split functions exceeding 2× the threshold."
        ),
    },
    "FOE": {
        "signal_type": "fan_out_explosion",
        "name": "Fan-Out Explosion",
        "weight": "0.0 (report-only)",
        "description": (
            "Detects modules or functions that import or depend on an "
            "excessive number of other modules — high fan-out indicating "
            "a 'God module' or orchestration bottleneck."
        ),
        "detects": (
            "Modules whose import count or function-call fan-out exceeds "
            "a threshold relative to the repository median. Signals tight "
            "coupling and high blast radius for changes."
        ),
        "example": (
            "  # app/main.py imports 35 modules directly\n"
            "  # Repository median: 8 imports per module\n"
            "  # → fan-out z-score: 3.1 (anomalous)"
        ),
        "fix_hint": (
            "Introduce a facade or mediator pattern to reduce direct "
            "dependencies. Split orchestration logic into smaller, focused "
            "modules with explicit contracts."
        ),
    },
    "CIR": {
        "signal_type": "circular_import",
        "name": "Circular Import",
        "weight": "0.0 (report-only)",
        "description": (
            "Detects circular import chains — module A imports B which "
            "imports C which imports A. A structural anti-pattern that "
            "causes runtime errors and prevents clean layering."
        ),
        "detects": (
            "Import cycles of any length in the module dependency graph. "
            "Reports the shortest cycle path and all participating modules."
        ),
        "example": (
            "  # models/user.py → services/auth.py → models/user.py\n"
            "  # Cycle length: 2"
        ),
        "fix_hint": (
            "Break the cycle by extracting shared types into a common module, "
            "using dependency injection, or deferring imports with "
            "TYPE_CHECKING guards."
        ),
    },
    "DCA": {
        "signal_type": "dead_code_accumulation",
        "name": "Dead Code Accumulation",
        "weight": "0.0 (report-only)",
        "description": (
            "Detects functions, classes, or module-level symbols that are "
            "defined but never referenced elsewhere in the codebase."
        ),
        "detects": (
            "Unreferenced exports that accumulate over time as code evolves. "
            "Excludes framework entry-points (decorated handlers, CLI commands), "
            "test functions, and __dunder__ methods."
        ),
        "example": (
            "  def legacy_migrate_v2(db):  # defined but never called\n"
            "      ...                     # 85 lines of dead code"
        ),
        "fix_hint": (
            "Remove confirmed dead code. For uncertain cases, add a "
            "deprecation marker and monitor usage before deletion. "
            "Verify framework entry-points are not false positives."
        ),
    },
    "MAZ": {
        "signal_type": "missing_authorization",
        "name": "Missing Authorization",
        "weight": "0.0 (report-only)",
        "description": (
            "Detects HTTP/API endpoints that lack any form of "
            "authentication or authorization check (CWE-862)."
        ),
        "detects": (
            "Route handler functions with @app.route / @router.get / etc. "
            "decorators that have no auth decorator, no body-level auth "
            "dependency, and are not on the public endpoint allowlist."
        ),
        "example": (
            '  @app.get("/users/{user_id}")\n'
            "  async def get_user(user_id: int):  # no auth check\n"
            "      return db.get(user_id)"
        ),
        "fix_hint": (
            "Add an authentication dependency (e.g. Depends(get_current_user) "
            "for FastAPI, @login_required for Django) or add the endpoint to "
            "maz_public_endpoint_allowlist in drift.yaml if intentionally public."
        ),
    },
    "ISD": {
        "signal_type": "insecure_default",
        "name": "Insecure Default",
        "weight": "0.0 (report-only)",
        "description": (
            "Detects insecure configuration defaults that are commonly "
            "copy-pasted from tutorials or scaffolding (CWE-1188)."
        ),
        "detects": (
            "DEBUG=True, ALLOWED_HOSTS=['*'], CORS_ALLOW_ALL_ORIGINS=True, "
            "insecure cookie settings, SECURE_SSL_REDIRECT=False, and "
            "requests.get(..., verify=False) patterns in non-test code."
        ),
        "example": (
            "  DEBUG = True\n"
            "  ALLOWED_HOSTS = ['*']\n"
            "  SESSION_COOKIE_SECURE = False"
        ),
        "fix_hint": (
            "Set DEBUG=False, restrict ALLOWED_HOSTS, enable CORS origin "
            "validation, set cookie Secure flags to True, and use "
            "verify=True for HTTP requests. Add # drift:ignore-security "
            "for intentional local-dev overrides."
        ),
    },
    "HSC": {
        "signal_type": "hardcoded_secret",
        "name": "Hardcoded Secret",
        "weight": "0.0 (report-only)",
        "description": (
            "Detects hardcoded secrets, API tokens, and credentials "
            "in Python source code (CWE-798)."
        ),
        "detects": (
            "String literals assigned to variables with secret-related names "
            "(SECRET_KEY, API_TOKEN, PASSWORD, etc.), known token prefixes "
            "(ghp_, sk-, AKIA, xoxb-), and high-entropy strings that are "
            "not loaded from environment or config."
        ),
        "example": (
            '  SECRET_KEY = "django-insecure-abc123..."\n'
            '  GITHUB_TOKEN = "ghp_xxxxxxxxxxxxxxxxxxxx"'
        ),
        "fix_hint": (
            "Move secrets to environment variables (os.environ['SECRET_KEY']) "
            "or a secrets manager. Never commit real credentials. Use "
            "placeholder values only in example/template files."
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
