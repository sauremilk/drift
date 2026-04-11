"""Ground-truth fixture definitions for precision/recall measurement.

Each fixture defines a minimal codebase with known TP, FP, and FN
expectations per signal type. Fixtures are deterministic — no git,
no embeddings, no external deps required.

Fixtures are classified by *kind* using :class:`FixtureKind`:
- ``positive``   – must be detected (TP expectation)
- ``negative``   – must *not* be detected (TN expectation)
- ``boundary``   – near threshold; tests sensitivity calibration
- ``confounder`` – looks similar to a real finding but is benign
"""

from __future__ import annotations

import datetime as _dt
import enum
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

from drift.models import CommitInfo, SignalType


class FixtureKind(enum.StrEnum):
    """Classification of a ground-truth fixture."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    BOUNDARY = "boundary"
    CONFOUNDER = "confounder"


@dataclass
class ExpectedFinding:
    """A single expected (or unexpected) finding."""

    signal_type: SignalType
    file_path: str  # relative to fixture root
    should_detect: bool  # True = TP, False = FP expectation (should NOT fire)
    description: str = ""


@dataclass
class FileHistoryOverride:
    """Partial overrides for FileHistory fields on a specific file."""

    total_commits: int | None = None
    unique_authors: int | None = None
    ai_attributed_commits: int | None = None
    change_frequency_30d: float | None = None
    defect_correlated_commits: int | None = None


@dataclass
class GroundTruthFixture:
    """A self-contained test fixture with known drift expectations."""

    name: str
    description: str
    files: dict[str, str]  # relative path -> content
    kind: FixtureKind | None = None
    expected: list[ExpectedFinding] = field(default_factory=list)
    file_history_overrides: dict[str, FileHistoryOverride] = field(default_factory=dict)
    commits: list[CommitInfo] = field(default_factory=list)
    # Prior file contents for git-backed signals.
    old_sources: dict[str, str] = field(default_factory=dict)

    def materialize(self, root: Path) -> Path:
        """Write all files to disk under *root* and return the fixture dir."""
        fixture_dir = root / self.name
        fixture_dir.mkdir(parents=True, exist_ok=True)
        for rel_path, content in self.files.items():
            full = fixture_dir / rel_path
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(textwrap.dedent(content), encoding="utf-8")
        return fixture_dir

    @property
    def tp_expectations(self) -> list[ExpectedFinding]:
        return [e for e in self.expected if e.should_detect]

    @property
    def fp_expectations(self) -> list[ExpectedFinding]:
        return [e for e in self.expected if not e.should_detect]

    @property
    def inferred_kind(self) -> FixtureKind:
        """Return explicit kind if set, otherwise infer from expectations."""
        if self.kind is not None:
            return self.kind
        if self.expected and all(not e.should_detect for e in self.expected):
            return FixtureKind.NEGATIVE
        return FixtureKind.POSITIVE


# ── Pattern Fragmentation (PFS) ──────────────────────────────────────────

PFS_TRUE_POSITIVE = GroundTruthFixture(
    name="pfs_tp",
    description="Multiple incompatible error-handling patterns in one module → should fire PFS",
    files={
        "services/__init__.py": "",
        "services/handler_a.py": """\
            def handle_a(data):
                try:
                    process(data)
                except ValueError as e:
                    raise AppError(str(e)) from e
        """,
        "services/handler_b.py": """\
            import logging
            logger = logging.getLogger(__name__)

            def handle_b(data):
                try:
                    process(data)
                except Exception as e:
                    logger.error("Failed: %s", e)
                    return None
        """,
        "services/handler_c.py": """\
            import sys

            def handle_c(data):
                try:
                    process(data)
                except Exception:
                    print("error", file=sys.stderr)
                    sys.exit(1)
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.PATTERN_FRAGMENTATION,
            file_path="services/",
            should_detect=True,
            description="3 different error-handling patterns in services/",
        ),
    ],
)

PFS_TRUE_NEGATIVE = GroundTruthFixture(
    name="pfs_tn",
    description="Consistent error-handling across module → should NOT fire PFS",
    files={
        "services/__init__.py": "",
        "services/handler_a.py": """\
            def handle_a(data):
                try:
                    process(data)
                except ValueError as e:
                    raise AppError(str(e)) from e
        """,
        "services/handler_b.py": """\
            def handle_b(data):
                try:
                    transform(data)
                except ValueError as e:
                    raise AppError(str(e)) from e
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.PATTERN_FRAGMENTATION,
            file_path="services/",
            should_detect=False,
            description="Consistent pattern — no fragmentation expected",
        ),
    ],
)

# ── Architecture Violation (AVS) ─────────────────────────────────────────

AVS_TRUE_POSITIVE = GroundTruthFixture(
    name="avs_tp",
    description="DB layer imports from API layer → should fire AVS",
    files={
        "api/__init__.py": "",
        "api/routes.py": """\
            def get_users():
                return []
        """,
        "db/__init__.py": "",
        "db/models.py": """\
            from api.routes import get_users

            class User:
                pass
        """,
        "services/__init__.py": "",
        "services/user_service.py": """\
            from db.models import User

            def create_user(name: str) -> User:
                return User()
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.ARCHITECTURE_VIOLATION,
            file_path="db/models.py",
            should_detect=True,
            description="DB layer importing from API layer (upward violation)",
        ),
    ],
)

AVS_TRUE_NEGATIVE = GroundTruthFixture(
    name="avs_tn",
    description="Clean layered architecture → should NOT fire AVS",
    files={
        "api/__init__.py": "",
        "api/routes.py": """\
            from services.user_service import create_user

            def post_user(name: str):
                return create_user(name)
        """,
        "services/__init__.py": "",
        "services/user_service.py": """\
            from db.models import User

            def create_user(name: str) -> User:
                return User()
        """,
        "db/__init__.py": "",
        "db/models.py": """\
            class User:
                pass
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.ARCHITECTURE_VIOLATION,
            file_path="api/routes.py",
            should_detect=False,
            description="Downward imports only — clean layering",
        ),
    ],
)

AVS_CIRCULAR_TP = GroundTruthFixture(
    name="avs_circular_tp",
    description="Circular dependency between two modules → should fire AVS",
    files={
        "module_a/__init__.py": "",
        "module_a/core.py": """\
            from module_b.helper import helper_func

            def a_func():
                return helper_func()
        """,
        "module_b/__init__.py": "",
        "module_b/helper.py": """\
            from module_a.core import a_func

            def helper_func():
                return a_func()
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.ARCHITECTURE_VIOLATION,
            file_path="module_a/core.py",
            should_detect=True,
            description="Circular dependency between module_a and module_b",
        ),
    ],
)


# ── Mutant Duplicates (MDS) ──────────────────────────────────────────────

MDS_TRUE_POSITIVE = GroundTruthFixture(
    name="mds_tp",
    description=("Near-duplicate functions (copy-paste with minor changes) → should fire MDS"),
    files={
        "utils/__init__.py": "",
        "utils/formatters.py": """\
            def format_currency(amount: float, currency: str = "EUR") -> str:
                \"\"\"Format a monetary amount with currency symbol.\"\"\"
                if amount < 0:
                    prefix = "-"
                    amount = abs(amount)
                else:
                    prefix = ""
                formatted = f"{amount:.2f}"
                parts = formatted.split(".")
                integer_part = parts[0]
                decimal_part = parts[1]
                return f"{prefix}{integer_part}.{decimal_part} {currency}"
        """,
        "utils/money.py": """\
            def format_money(amount: float, currency: str = "EUR") -> str:
                \"\"\"Format a monetary amount with currency symbol.\"\"\"
                if amount < 0:
                    prefix = "-"
                    amount = abs(amount)
                else:
                    prefix = ""
                formatted = f"{amount:.2f}"
                parts = formatted.split(".")
                integer_part = parts[0]
                decimal_part = parts[1]
                return f"{prefix}{integer_part}.{decimal_part} {currency}"
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.MUTANT_DUPLICATE,
            file_path="utils/",
            should_detect=True,
            description="Exact-duplicate functions across two files",
        ),
    ],
)

MDS_TRUE_NEGATIVE = GroundTruthFixture(
    name="mds_tn",
    description=(
        "Functions with similar structure but genuinely different logic → should NOT fire MDS"
    ),
    files={
        "math/__init__.py": "",
        "math/operations.py": """\
            import math

            def compute_area_circle(radius: float) -> float:
                \"\"\"Compute area of a circle.\"\"\"
                return math.pi * radius * radius

            def compute_area_rectangle(width: float, height: float) -> float:
                \"\"\"Compute area of a rectangle.\"\"\"
                return width * height

            def compute_area_triangle(base: float, height: float) -> float:
                \"\"\"Compute area of a triangle.\"\"\"
                return 0.5 * base * height
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.MUTANT_DUPLICATE,
            file_path="math/operations.py",
            should_detect=False,
            description="Different formulas — not duplicates",
        ),
    ],
)


# ── Explainability Deficit (EDS) ─────────────────────────────────────────

EDS_TRUE_POSITIVE = GroundTruthFixture(
    name="eds_tp",
    description="Complex function without docs or tests → should fire EDS",
    files={
        "core/__init__.py": "",
        "core/processor.py": """\
            def process_batch(items, config, retry_count=3, timeout=30):
                results = []
                for item in items:
                    if item.get("type") == "A":
                        if item.get("priority") > 5:
                            results.append(handle_high_priority(item))
                        elif item.get("status") == "pending":
                            results.append(handle_pending(item))
                        else:
                            results.append(handle_default(item))
                    elif item.get("type") == "B":
                        if config.get("fast_mode"):
                            results.append(fast_process(item))
                        else:
                            results.append(slow_process(item))
                    else:
                        if retry_count > 0:
                            results.append(
                                process_batch([item], config, retry_count - 1)
                            )
                        else:
                            results.append(None)
                return [r for r in results if r is not None]
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.EXPLAINABILITY_DEFICIT,
            file_path="core/processor.py",
            should_detect=True,
            description="High complexity (nested branches), no docstring, no tests",
        ),
    ],
)

EDS_TRUE_NEGATIVE = GroundTruthFixture(
    name="eds_tn",
    description="Well-documented complex function with tests → should NOT fire EDS",
    files={
        "core/__init__.py": "",
        "core/validator.py": """\
            def validate_input(data: dict, schema: dict) -> list[str]:
                \"\"\"Validate input data against a JSON schema.

                Args:
                    data: The input data to validate.
                    schema: The JSON schema definition.

                Returns:
                    List of validation error messages (empty if valid).
                \"\"\"
                errors = []
                for key, rules in schema.items():
                    if rules.get("required") and key not in data:
                        errors.append(f"Missing required field: {key}")
                    elif key in data:
                        value = data[key]
                        if rules.get("type") == "int" and not isinstance(value, int):
                            errors.append(f"Field {key} must be int")
                        elif rules.get("type") == "str" and not isinstance(value, str):
                            errors.append(f"Field {key} must be str")
                        if rules.get("min") and value < rules["min"]:
                            errors.append(f"Field {key} below minimum")
                        if rules.get("max") and value > rules["max"]:
                            errors.append(f"Field {key} above maximum")
                return errors
        """,
        "tests/__init__.py": "",
        "tests/test_validator.py": """\
            def test_validate_input():
                assert True

            def test_validate_input_missing_required():
                assert True
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.EXPLAINABILITY_DEFICIT,
            file_path="core/validator.py",
            should_detect=False,
            description="Has docstring + tests → well-explained",
        ),
    ],
)


# ── Temporal Volatility (TVS) ─────────────────────────────────────────────

TVS_TRUE_POSITIVE = GroundTruthFixture(
    name="tvs_tp",
    description="One file with extreme churn among stable files -> should fire TVS",
    files={
        "app/__init__.py": "",
        "app/stable_a.py": """\
            def stable_func_a():
                return 1
        """,
        "app/stable_b.py": """\
            def stable_func_b():
                return 2
        """,
        "app/stable_c.py": """\
            def stable_func_c():
                return 3
        """,
        "app/stable_d.py": """\
            def stable_func_d():
                return 4
        """,
        "app/volatile.py": """\
            def volatile_func(x):
                if x > 0:
                    return x * 2
                return -x
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.TEMPORAL_VOLATILITY,
            file_path="app/volatile.py",
            should_detect=True,
            description="Extreme churn outlier among stable files",
        ),
    ],
    file_history_overrides={
        "app/volatile.py": FileHistoryOverride(
            total_commits=80,
            unique_authors=8,
            change_frequency_30d=25.0,
            defect_correlated_commits=12,
            ai_attributed_commits=40,
        ),
    },
)

TVS_TRUE_NEGATIVE = GroundTruthFixture(
    name="tvs_tn",
    description="All files have similar low churn -> should NOT fire TVS",
    files={
        "lib/__init__.py": "",
        "lib/alpha.py": """\
            def alpha():
                return "a"
        """,
        "lib/beta.py": """\
            def beta():
                return "b"
        """,
        "lib/gamma.py": """\
            def gamma():
                return "c"
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.TEMPORAL_VOLATILITY,
            file_path="lib/",
            should_detect=False,
            description="Uniform churn across all files -- no outlier",
        ),
    ],
)


# ── System Misalignment (SMS) ────────────────────────────────────────────

SMS_TRUE_POSITIVE = GroundTruthFixture(
    name="sms_tp",
    description="New file introduces foreign dependencies not used by rest of module",
    files={
        "services/__init__.py": "",
        "services/core.py": """\
            import json
            import logging

            def process(data):
                logging.info("Processing")
                return json.dumps(data)
        """,
        "services/helper.py": """\
            import json

            def transform(data):
                return json.loads(data)
        """,
        "services/new_feature.py": """\
            import redis
            import boto3
            import kafka

            def push_event(event):
                client = redis.Redis()
                client.publish("events", str(event))
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.SYSTEM_MISALIGNMENT,
            file_path="services/",
            should_detect=True,
            description="redis, boto3, kafka are foreign to services/",
        ),
    ],
)

SMS_TRUE_NEGATIVE = GroundTruthFixture(
    name="sms_tn",
    description="New file uses only established module dependencies",
    files={
        "services/__init__.py": "",
        "services/core.py": """\
            import json
            import logging

            def process(data):
                logging.info("Processing")
                return json.dumps(data)
        """,
        "services/helper.py": """\
            import json
            import logging

            def transform(data):
                logging.debug("Transforming")
                return json.loads(data)
        """,
        "services/new_feature.py": """\
            import json
            import logging

            def new_func(data):
                logging.info("New feature")
                return json.dumps(data)
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.SYSTEM_MISALIGNMENT,
            file_path="services/new_feature.py",
            should_detect=False,
            description="Same imports as rest of module — no misalignment",
        ),
    ],
)


# ── Doc-Implementation Drift (DIA) ───────────────────────────────────────

DIA_TRUE_POSITIVE = GroundTruthFixture(
    name="dia_tp",
    description="README references dirs that don't exist → should fire DIA",
    files={
        "README.md": """\
            # Project

            The project has the following structure:

            - `src/` — main source code
            - `plugins/` — extension plugins
            - `workers/` — background workers
        """,
        "src/__init__.py": "",
        "src/main.py": """\
            def main():
                pass
        """,
        # plugins/ and workers/ do NOT exist
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.DOC_IMPL_DRIFT,
            file_path="README.md",
            should_detect=True,
            description="plugins/ and workers/ referenced but missing",
        ),
    ],
)

DIA_TRUE_NEGATIVE = GroundTruthFixture(
    name="dia_tn",
    description="README accurately describes existing dirs → should NOT fire DIA",
    files={
        "README.md": """\
            # Project

            The project has the following structure:

            - `src/` — main source code
            - `tests/` — test suite
        """,
        "src/__init__.py": "",
        "src/main.py": """\
            def main():
                pass
        """,
        "tests/__init__.py": "",
        "tests/test_main.py": """\
            def test_main():
                pass
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.DOC_IMPL_DRIFT,
            file_path="README.md",
            should_detect=False,
            description="All referenced dirs exist",
        ),
    ],
)


# ── Additional PFS fixtures ───────────────────────────────────────────────

PFS_VALIDATION_TP = GroundTruthFixture(
    name="pfs_validation_tp",
    description="Multiple validation patterns in one module → should fire PFS",
    files={
        "validators/__init__.py": "",
        "validators/input_validator.py": """\
            def validate_email(email: str) -> bool:
                try:
                    if "@" not in email:
                        raise ValueError("Invalid email")
                    return True
                except ValueError as e:
                    raise AppError(str(e)) from e
        """,
        "validators/form_validator.py": """\
            def validate_form(data: dict) -> dict:
                result = {"valid": True, "errors": []}
                if not data.get("name"):
                    result["valid"] = False
                    result["errors"].append("name required")
                return result
        """,
        "validators/api_validator.py": """\
            import logging
            logger = logging.getLogger(__name__)

            def validate_request(req):
                try:
                    assert req.get("method"), "method required"
                    assert req.get("path"), "path required"
                except AssertionError as e:
                    logger.warning("Validation failed: %s", e)
                    return None
        """,
        "validators/payload_validator.py": """\
            def validate_payload(payload: dict) -> dict:
                try:
                    if not isinstance(payload, dict):
                        raise TypeError("payload must be dict")
                    if "version" not in payload:
                        raise KeyError("missing version")
                    return payload
                except (TypeError, KeyError):
                    return {}
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.PATTERN_FRAGMENTATION,
            file_path="validators/",
            should_detect=True,
            description="3 different error-handling patterns in validators/",
        ),
    ],
)

PFS_LOGGING_TP = GroundTruthFixture(
    name="pfs_logging_tp",
    description="Multiple logging patterns in one module → should fire PFS",
    files={
        "workers/__init__.py": "",
        "workers/task_a.py": """\
            import logging
            logger = logging.getLogger(__name__)

            def run_task_a():
                try:
                    do_work()
                except Exception as e:
                    logger.exception("Task A failed")
                    raise
        """,
        "workers/task_b.py": """\
            def run_task_b():
                try:
                    do_work()
                except Exception as e:
                    print(f"Error in task B: {e}")
                    return None
        """,
        "workers/task_c.py": """\
            import sys

            def run_task_c():
                try:
                    do_work()
                except Exception:
                    sys.stderr.write("task_c error\\n")
                    sys.exit(1)
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.PATTERN_FRAGMENTATION,
            file_path="workers/",
            should_detect=True,
            description="3 different error-handling/logging patterns in workers/",
        ),
    ],
)

PFS_BOUNDARY_TP = GroundTruthFixture(
    name="pfs_boundary_tp",
    description="Two handling styles at threshold; fragmentation should be detected.",
    kind=FixtureKind.BOUNDARY,
    files={
        "workers/__init__.py": "",
        "workers/task_a.py": """\
            import logging
            logger = logging.getLogger(__name__)

            def run_task_a():
                try:
                    do_work()
                except Exception as e:
                    logger.error("Task A failed: %s", e)
                    raise
        """,
        "workers/task_b.py": """\
            def run_task_b():
                try:
                    do_work()
                except Exception:
                    return None
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.PATTERN_FRAGMENTATION,
            file_path="workers/",
            should_detect=True,
            description="Boundary case at detector threshold should be reported",
        ),
    ],
)

PFS_CONFOUNDER_TN = GroundTruthFixture(
    name="pfs_confounder_tn",
    description="Variation exists only in tests; production module remains consistent.",
    kind=FixtureKind.CONFOUNDER,
    files={
        "services/__init__.py": "",
        "services/handler.py": """\
            def handle(data):
                try:
                    process(data)
                except ValueError as e:
                    raise AppError(str(e)) from e
        """,
        "tests/__init__.py": "",
        "tests/test_handler.py": """\
            def test_handle_returns_none_on_error():
                try:
                    raise RuntimeError("boom")
                except RuntimeError:
                    assert True
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.PATTERN_FRAGMENTATION,
            file_path="services/",
            should_detect=False,
            description="Test-only variation should not produce PFS for service module",
        ),
    ],
)

PFS_DECORATOR_TN = GroundTruthFixture(
    name="pfs_decorator_tn",
    description="FastAPI-style decorated routes with consistent structure → should NOT fire PFS",
    kind=FixtureKind.CONFOUNDER,
    files={
        "routes/__init__.py": "",
        "routes/users.py": """\
            @app.get("/users")
            def list_users():
                return jsonify(users_service.get_all())

            @app.post("/users")
            def create_user():
                return jsonify(users_service.create(request.json))

            @app.get("/users/{user_id}")
            def get_user(user_id):
                return jsonify(users_service.get(user_id))

            @app.put("/users/{user_id}")
            def update_user(user_id):
                return jsonify(users_service.update(user_id, request.json))

            @app.delete("/users/{user_id}")
            def delete_user(user_id):
                return jsonify(users_service.delete(user_id))
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.PATTERN_FRAGMENTATION,
            file_path="routes/",
            should_detect=False,
            description=(
                "Consistent decorator pattern (framework routes) must not produce a PFS finding"
            ),
        ),
    ],
)

PFS_RETURN_PATTERN_TP = GroundTruthFixture(
    name="pfs_return_pattern_tp",
    description="Divergent return strategies in one module → should fire PFS",
    files={
        "models/__init__.py": "",
        "models/user.py": """\
def get_user(user_id: int):
    if user_id <= 0:
        return None
    return {"id": user_id, "name": "Alice"}

def get_user_or_raise(user_id: int) -> dict:
    if user_id <= 0:
        raise ValueError("Invalid user_id")
    return {"id": user_id, "name": "Alice"}

def get_user_result(user_id: int) -> tuple:
    if user_id <= 0:
        return None, "Invalid user_id"
    return {"id": user_id, "name": "Alice"}, None
""",
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.PATTERN_FRAGMENTATION,
            file_path="models/",
            should_detect=True,
            description="3 divergent return strategies in models/ module",
        ),
    ],
)


# ── Additional MDS fixtures ──────────────────────────────────────────────

MDS_NEAR_DUPLICATE_TP = GroundTruthFixture(
    name="mds_near_dup_tp",
    description="Near-duplicate functions with renamed variables → should fire MDS",
    files={
        "services/__init__.py": "",
        "services/user_service.py": """\
            def fetch_user_data(user_id: int, db_session) -> dict:
                \"\"\"Fetch user data from database.\"\"\"
                query = f"SELECT * FROM users WHERE id = {user_id}"
                result = db_session.execute(query)
                rows = result.fetchall()
                if not rows:
                    return {"error": "not found", "user_id": user_id}
                user = rows[0]
                return {
                    "id": user["id"],
                    "name": user["name"],
                    "email": user["email"],
                    "created_at": str(user["created_at"]),
                }
        """,
        "services/customer_service.py": """\
            def get_customer_info(customer_id: int, session) -> dict:
                \"\"\"Get customer info from database.\"\"\"
                sql = f"SELECT * FROM users WHERE id = {customer_id}"
                res = session.execute(sql)
                records = res.fetchall()
                if not records:
                    return {"error": "not found", "customer_id": customer_id}
                customer = records[0]
                return {
                    "id": customer["id"],
                    "name": customer["name"],
                    "email": customer["email"],
                    "created_at": str(customer["created_at"]),
                }
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.MUTANT_DUPLICATE,
            file_path="services/",
            should_detect=True,
            description="Near-duplicate with renamed variables across files",
        ),
    ],
)

MDS_EXACT_TRIPLE_TP = GroundTruthFixture(
    name="mds_exact_triple_tp",
    description="Three identical copies of the same function → should fire MDS",
    files={
        "lib/__init__.py": "",
        "lib/module_a.py": """\
            def compute_hash(data: str, algorithm: str = "sha256") -> str:
                \"\"\"Compute hash of data.\"\"\"
                import hashlib
                if algorithm == "sha256":
                    return hashlib.sha256(data.encode()).hexdigest()
                elif algorithm == "md5":
                    return hashlib.md5(data.encode()).hexdigest()
                else:
                    raise ValueError(f"Unknown algorithm: {algorithm}")
        """,
        "lib/module_b.py": """\
            def compute_hash(data: str, algorithm: str = "sha256") -> str:
                \"\"\"Compute hash of data.\"\"\"
                import hashlib
                if algorithm == "sha256":
                    return hashlib.sha256(data.encode()).hexdigest()
                elif algorithm == "md5":
                    return hashlib.md5(data.encode()).hexdigest()
                else:
                    raise ValueError(f"Unknown algorithm: {algorithm}")
        """,
        "lib/module_c.py": """\
            def compute_hash(data: str, algorithm: str = "sha256") -> str:
                \"\"\"Compute hash of data.\"\"\"
                import hashlib
                if algorithm == "sha256":
                    return hashlib.sha256(data.encode()).hexdigest()
                elif algorithm == "md5":
                    return hashlib.md5(data.encode()).hexdigest()
                else:
                    raise ValueError(f"Unknown algorithm: {algorithm}")
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.MUTANT_DUPLICATE,
            file_path="lib/",
            should_detect=True,
            description="Three exact copies of compute_hash across modules",
        ),
    ],
)


# ── Additional EDS fixtures ──────────────────────────────────────────────

EDS_STATE_MACHINE_TP = GroundTruthFixture(
    name="eds_state_machine_tp",
    description="Complex state machine without docs → should fire EDS",
    files={
        "engine/__init__.py": "",
        "engine/state_machine.py": """\
            def advance_state(current, event, context, rules, history):
                next_state = current
                for rule in rules:
                    if rule.get("from") == current and rule.get("event") == event:
                        guard = rule.get("guard")
                        if guard == "auth_required":
                            if not context.get("authenticated"):
                                continue
                        elif guard == "admin_only":
                            if context.get("role") != "admin":
                                continue
                        elif guard == "time_window":
                            if not context.get("in_window"):
                                continue
                        next_state = rule["to"]
                        action = rule.get("action")
                        if action == "log":
                            history.append({"from": current, "to": next_state})
                        elif action == "notify":
                            context["notifications"].append(next_state)
                        elif action == "escalate":
                            context["escalation_level"] = context.get("escalation_level", 0) + 1
                        break
                return next_state
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.EXPLAINABILITY_DEFICIT,
            file_path="engine/state_machine.py",
            should_detect=True,
            description="Complex state machine with nested branches, no docs",
        ),
    ],
)

EDS_NESTED_LOOPS_TP = GroundTruthFixture(
    name="eds_nested_loops_tp",
    description="Deep nested loops without documentation → should fire EDS",
    files={
        "analytics/__init__.py": "",
        "analytics/aggregator.py": """\
            def cross_correlate(datasets, filters, thresholds, output_mode):
                results = {}
                for ds_name, dataset in datasets.items():
                    for record in dataset:
                        for f_name, f_func in filters.items():
                            if not f_func(record):
                                continue
                            for threshold_name, threshold_val in thresholds.items():
                                val = record.get(threshold_name, 0)
                                if val >= threshold_val:
                                    key = f"{ds_name}:{f_name}:{threshold_name}"
                                    if key not in results:
                                        results[key] = []
                                    results[key].append(record)
                if output_mode == "count":
                    return {k: len(v) for k, v in results.items()}
                elif output_mode == "first":
                    return {k: v[0] for k, v in results.items() if v}
                return results
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.EXPLAINABILITY_DEFICIT,
            file_path="analytics/aggregator.py",
            should_detect=True,
            description="Deep nested loops, no docstring, no tests",
        ),
    ],
)

EDS_INIT_TN = GroundTruthFixture(
    name="eds_init_tn",
    description="Complex __init__ without docstring → should NOT fire EDS",
    files={
        "models/__init__.py": "",
        "models/pipeline.py": """\
            class Pipeline:
                def __init__(self, config, steps, hooks, timeout=30, retries=3):
                    self.config = config
                    self.steps = steps
                    self.hooks = hooks
                    self.timeout = timeout
                    self.retries = retries
                    if config.get("strict"):
                        for step in steps:
                            if not step.get("name"):
                                raise ValueError("Each step must have a name")
                            if step.get("timeout", 0) > timeout:
                                raise ValueError("Step timeout exceeds pipeline timeout")
                    for hook in hooks:
                        if hook.get("on") not in ("start", "end", "error"):
                            raise ValueError(f"Unknown hook event: {hook.get('on')}")
                    self._state = "ready"
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.EXPLAINABILITY_DEFICIT,
            file_path="models/pipeline.py",
            should_detect=False,
            description="Complex __init__ without docstring → EDS must not fire",
        ),
    ],
)


# ── Additional AVS fixtures ──────────────────────────────────────────────

AVS_SKIP_LAYER_TP = GroundTruthFixture(
    name="avs_skip_layer_tp",
    description="DB layer imports from API layer (upward) → should fire AVS",
    files={
        "api/__init__.py": "",
        "api/endpoints.py": """\
            def list_items():
                return []
        """,
        "services/__init__.py": "",
        "services/data_service.py": """\
            from db.queries import raw_query

            def get_processed_data():
                return raw_query("SELECT * FROM data")
        """,
        "db/__init__.py": "",
        "db/queries.py": """\
            from api.endpoints import list_items

            def raw_query(sql):
                return list_items()
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.ARCHITECTURE_VIOLATION,
            file_path="db/queries.py",
            should_detect=True,
            description="DB layer (layer 2) imports from API layer (layer 0) — upward violation",
        ),
    ],
)

AVS_BOUNDARY_TN = GroundTruthFixture(
    name="avs_boundary_tn",
    description="Indirect import via allowed service dependency should not be flagged.",
    kind=FixtureKind.BOUNDARY,
    files={
        "api/__init__.py": "",
        "api/routes.py": """\
            from services.user_service import get_user

            def get_user_route(user_id: int):
                return get_user(user_id)
        """,
        "services/__init__.py": "",
        "services/user_service.py": """\
            from db.models import User

            def get_user(user_id: int) -> User:
                return User()
        """,
        "db/__init__.py": "",
        "db/models.py": """\
            class User:
                pass
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.ARCHITECTURE_VIOLATION,
            file_path="services/user_service.py",
            should_detect=False,
            description="Transitive but allowed flow should remain non-violation",
        ),
    ],
)

AVS_CONFOUNDER_TN = GroundTruthFixture(
    name="avs_confounder_tn",
    description="Import in test file resembles upward dependency but must be ignored.",
    kind=FixtureKind.CONFOUNDER,
    files={
        "api/__init__.py": "",
        "api/routes.py": """\
            def list_users():
                return []
        """,
        "db/__init__.py": "",
        "db/models.py": """\
            class User:
                pass
        """,
        "tests/__init__.py": "",
        "tests/test_db_layer.py": """\
            from api.routes import list_users

            def test_fixture_import_for_mocks():
                assert list_users() == []
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.ARCHITECTURE_VIOLATION,
            file_path="db/models.py",
            should_detect=False,
            description="Test-only imports should not cause AVS violation",
        ),
    ],
)


# ── Additional DIA fixtures ──────────────────────────────────────────────

DIA_ADR_MISMATCH_TP = GroundTruthFixture(
    name="dia_adr_mismatch_tp",
    description="README references directories that don't exist → should fire DIA",
    files={
        "README.md": """\
            # My Project

            ## Architecture

            - `src/` — main source code
            - `workers/` — background job processors
            - `scheduler/` — task scheduling engine
        """,
        "src/__init__.py": "",
        "src/app.py": """\
            def main():
                pass
        """,
        # workers/ and scheduler/ do NOT exist
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.DOC_IMPL_DRIFT,
            file_path="README.md",
            should_detect=True,
            description="workers/ and scheduler/ referenced but missing",
        ),
    ],
)

DIA_ADR_FILE_TP = GroundTruthFixture(
    name="dia_adr_file_tp",
    description="ADR file references non-existent directories → should fire DIA",
    files={
        "README.md": """\
            # Project

            See `docs/adr/` for architectural decisions.
        """,
        "docs/adr/001-layers.md": """\
            # ADR 001: Layered Architecture

            The project uses:
            - `controllers/` — HTTP controllers
            - `repositories/` — Data access layer
        """,
        "src/__init__.py": "",
        "src/main.py": """\
            def main():
                pass
        """,
        # controllers/ and repositories/ do NOT exist
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.DOC_IMPL_DRIFT,
            file_path="docs/adr/001-layers.md",
            should_detect=True,
            description="ADR references controllers/ and repositories/ but they don't exist",
        ),
    ],
)


# ── Additional SMS fixtures ──────────────────────────────────────────────

SMS_ML_IN_WEB_TP = GroundTruthFixture(
    name="sms_ml_in_web_tp",
    description="ML dependencies in a web service module → should fire SMS",
    files={
        "api/__init__.py": "",
        "api/routes.py": """\
            import json

            def get_users():
                return json.dumps([])
        """,
        "api/helpers.py": """\
            import json
            import logging

            def log_request(req):
                logging.info(json.dumps(req))
        """,
        "api/new_feature.py": """\
            import tensorflow
            import pandas
            import scipy

            def predict(data):
                return tensorflow.constant(0)
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.SYSTEM_MISALIGNMENT,
            file_path="api/",
            should_detect=True,
            description="tensorflow, pandas, scipy are foreign to api/",
        ),
    ],
)


# ── Broad Exception Monoculture (BEM) ────────────────────────────────────

BEM_TRUE_POSITIVE = GroundTruthFixture(
    name="bem_tp",
    description="Module with uniformly broad exception handling → should fire BEM",
    files={
        "connectors/__init__.py": "",
        "connectors/db.py": """\
            import logging
            logger = logging.getLogger(__name__)

            def get_user(uid):
                try:
                    return {"id": uid}
                except Exception:
                    logger.error("db get failed")
        """,
        "connectors/cache.py": """\
            import logging
            logger = logging.getLogger(__name__)

            def invalidate(key):
                try:
                    return True
                except Exception:
                    logger.error("cache invalidate failed")
        """,
        "connectors/queue.py": """\
            import logging
            logger = logging.getLogger(__name__)

            def publish(topic, msg):
                try:
                    return True
                except Exception:
                    logger.error("queue publish failed")
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.BROAD_EXCEPTION_MONOCULTURE,
            file_path="connectors/",
            should_detect=True,
            description="3 handlers all catch Exception + log-only",
        ),
    ],
)

BEM_TRUE_NEGATIVE = GroundTruthFixture(
    name="bem_tn",
    description="Module with specific exception handling → should NOT fire BEM",
    files={
        "services/__init__.py": "",
        "services/mailer.py": """\
            def send_email(to, subject, body):
                try:
                    return True
                except ConnectionRefusedError:
                    raise RuntimeError("SMTP down") from None
        """,
        "services/storage.py": """\
            def upload(data):
                try:
                    return "/uploaded"
                except FileNotFoundError as e:
                    raise ValueError("bad path") from e
        """,
        "services/notifier.py": """\
            def notify(user_id, msg):
                try:
                    return True
                except TimeoutError:
                    raise IOError("notification timeout") from None
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.BROAD_EXCEPTION_MONOCULTURE,
            file_path="services/",
            should_detect=False,
            description="All handlers catch specific exceptions and re-raise",
        ),
    ],
)

BEM_MIXED_TP = GroundTruthFixture(
    name="bem_mixed_tp",
    description="Module with mostly broad handlers + swallowing → should fire BEM",
    files={
        "adapters/__init__.py": "",
        "adapters/http_client.py": """\
            import logging
            logger = logging.getLogger(__name__)

            def fetch_data(url):
                try:
                    return {"data": []}
                except Exception:
                    logger.error("HTTP fetch failed")

            def post_data(url, payload):
                try:
                    return True
                except Exception:
                    pass
        """,
        "adapters/ftp_client.py": """\
            import logging
            logger = logging.getLogger(__name__)

            def download(host, path):
                try:
                    return b""
                except Exception:
                    logger.error("FTP download failed")
        """,
        "adapters/smtp_client.py": """\
            def send(to, body):
                try:
                    return True
                except Exception:
                    pass
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.BROAD_EXCEPTION_MONOCULTURE,
            file_path="adapters/",
            should_detect=True,
            description="4 handlers catch Exception, all swallow (log/pass)",
        ),
    ],
)

BEM_BOUNDARY_TN = GroundTruthFixture(
    name="bem_boundary_tn",
    description="Error-boundary module with broad handlers → should NOT fire BEM",
    files={
        "middleware/__init__.py": "",
        "middleware/error_handler.py": """\
            import logging
            logger = logging.getLogger(__name__)

            def handle_request(req):
                try:
                    return process(req)
                except Exception:
                    logger.error("Request failed")
                    return {"error": "internal"}
        """,
        "middleware/error_middleware.py": """\
            import logging
            logger = logging.getLogger(__name__)

            def wrap_response(resp):
                try:
                    return resp
                except Exception:
                    logger.error("Response wrap failed")

            def log_error(exc):
                try:
                    return str(exc)
                except Exception:
                    logger.error("Error logging failed")
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.BROAD_EXCEPTION_MONOCULTURE,
            file_path="middleware/",
            should_detect=False,
            description="Error-boundary modules are excluded by design",
        ),
    ],
)


# ── Test Polarity Deficit (TPD) ──────────────────────────────────────────

TPD_TRUE_POSITIVE = GroundTruthFixture(
    name="tpd_tp",
    description="Test suite with only positive assertions → should fire TPD",
    files={
        "tests/__init__.py": "",
        "tests/test_math.py": """\
            def test_add():
                assert 1 + 1 == 2

            def test_sub():
                assert 5 - 3 == 2

            def test_mul():
                assert 2 * 3 == 6

            def test_div():
                assert 10 / 2 == 5.0

            def test_pow():
                assert 2 ** 3 == 8

            def test_mod():
                assert 10 % 3 == 1
                assert 15 % 5 == 0
                assert 7 % 2 == 1
                assert 9 % 4 == 1
                assert 100 % 10 == 0
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.TEST_POLARITY_DEFICIT,
            file_path="tests/",
            should_detect=True,
            description="6 test functions, 10 positive assertions, 0 negative",
        ),
    ],
)

TPD_TRUE_NEGATIVE = GroundTruthFixture(
    name="tpd_tn",
    description="Test suite with balanced positive/negative assertions → should NOT fire TPD",
    files={
        "tests/__init__.py": "",
        "tests/test_validation.py": """\
            import pytest

            def test_valid_input():
                assert validate("hello") is True
                assert validate("world") is True

            def test_invalid_raises():
                with pytest.raises(ValueError):
                    validate(None)
                with pytest.raises(ValueError):
                    validate("")

            def test_edge_case():
                assert validate("x") is True

            def test_type_error():
                with pytest.raises(TypeError):
                    validate(42)

            def test_boundary():
                assert validate("a" * 100) is True

            def test_overflow_raises():
                with pytest.raises(OverflowError):
                    validate("a" * 10000)
                assert True
                assert True
                assert True
                assert True
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.TEST_POLARITY_DEFICIT,
            file_path="tests/",
            should_detect=False,
            description="4 negative assertions out of ~11 → ratio > 10%",
        ),
    ],
)

TPD_LARGE_SUITE_TP = GroundTruthFixture(
    name="tpd_large_tp",
    description="Large test suite with no negative tests → should fire TPD",
    files={
        "tests/unit/__init__.py": "",
        "tests/__init__.py": "",
        "tests/unit/test_models.py": """\
            def test_create_user():
                user = {"name": "Alice"}
                assert user["name"] == "Alice"
                assert "name" in user

            def test_create_order():
                order = {"id": 1, "total": 99.0}
                assert order["id"] == 1
                assert order["total"] == 99.0

            def test_create_product():
                prod = {"sku": "A1", "price": 10}
                assert prod["sku"] == "A1"
                assert prod["price"] == 10

            def test_format_name():
                assert "Alice".upper() == "ALICE"

            def test_calculate_tax():
                assert round(100 * 0.19, 2) == 19.0
                assert round(200 * 0.19, 2) == 38.0

            def test_merge_dicts():
                a = {"x": 1}
                b = {"y": 2}
                merged = {**a, **b}
                assert merged == {"x": 1, "y": 2}
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.TEST_POLARITY_DEFICIT,
            file_path="tests/unit/",
            should_detect=True,
            description="6 test functions, 10 positive assertions, 0 negative",
        ),
    ],
)

TPD_FEW_TESTS_TN = GroundTruthFixture(
    name="tpd_few_tests_tn",
    description="Test suite with only 3 test functions → below threshold, should NOT fire TPD",
    files={
        "tests/__init__.py": "",
        "tests/test_tiny.py": """\
            def test_one():
                assert True

            def test_two():
                assert 1 == 1

            def test_three():
                assert "a" == "a"
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.TEST_POLARITY_DEFICIT,
            file_path="tests/",
            should_detect=False,
            description="Only 3 test functions — below min_test_functions=5 threshold",
        ),
    ],
)


# ── Guard Clause Deficit (GCD) ──────────────────────────────────────────

GCD_TRUE_POSITIVE = GroundTruthFixture(
    name="gcd_tp",
    description="Module with unguarded complex public functions → should fire GCD",
    files={
        "core/__init__.py": "",
        "core/processor.py": """\
            def transform(data, schema, options):
                result = []
                for item in data:
                    out = {}
                    for key, spec in schema.items():
                        val = item.get(key)
                        if spec == "upper":
                            out[key] = val.upper()
                        elif spec == "lower":
                            out[key] = val.lower()
                        elif spec == "strip":
                            out[key] = val.strip()
                        else:
                            out[key] = val
                    if options.get("filter_key"):
                        if out.get(options["filter_key"]):
                            result.append(out)
                    else:
                        result.append(out)
                return result

            def aggregate(records, dimensions, funcs):
                groups = {}
                for r in records:
                    key = tuple(r.get(d) for d in dimensions)
                    if key not in groups:
                        groups[key] = []
                    groups[key].append(r)
                out = []
                for key, rows in groups.items():
                    entry = dict(zip(dimensions, key))
                    for fn in funcs:
                        vals = [r.get(fn, 0) for r in rows]
                        if vals:
                            entry[fn] = sum(vals) / len(vals)
                    out.append(entry)
                return out

            def export_report(data, columns, fmt):
                lines = []
                header = [str(c) for c in columns]
                lines.append(",".join(header))
                for row in data:
                    cells = []
                    for col in columns:
                        val = row.get(col, "")
                        if fmt == "quoted":
                            cells.append(f'"{val}"')
                        elif fmt == "raw":
                            cells.append(str(val))
                        else:
                            cells.append(str(val).strip())
                    lines.append(",".join(cells))
                return "\\n".join(lines)
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.GUARD_CLAUSE_DEFICIT,
            file_path="core/",
            should_detect=True,
            description="3 public functions with >=2 params, CC>=5, no guards",
        ),
    ],
)

GCD_TRUE_NEGATIVE = GroundTruthFixture(
    name="gcd_tn",
    description="Module with guarded public functions → should NOT fire GCD",
    files={
        "core/__init__.py": "",
        "core/safe_processor.py": """\
            def transform(data, schema, options):
                if not isinstance(data, list):
                    raise TypeError("data must be a list")
                if not isinstance(schema, dict):
                    raise TypeError("schema must be a dict")
                result = []
                for item in data:
                    out = {}
                    for key, spec in schema.items():
                        val = item.get(key)
                        if spec == "upper":
                            out[key] = val.upper()
                        elif spec == "lower":
                            out[key] = val.lower()
                        elif spec == "strip":
                            out[key] = val.strip()
                        else:
                            out[key] = val
                    result.append(out)
                return result

            def aggregate(records, dimensions, funcs):
                if not records:
                    return []
                assert isinstance(dimensions, (list, tuple))
                groups = {}
                for r in records:
                    key = tuple(r.get(d) for d in dimensions)
                    if key not in groups:
                        groups[key] = []
                    groups[key].append(r)
                out = []
                for key, rows in groups.items():
                    entry = dict(zip(dimensions, key))
                    for fn in funcs:
                        vals = [r.get(fn, 0) for r in rows]
                        if vals:
                            entry[fn] = sum(vals) / len(vals)
                    out.append(entry)
                return out

            def export_report(data, columns, fmt):
                if data is None:
                    raise ValueError("data cannot be None")
                if not columns:
                    return ""
                lines = []
                header = [str(c) for c in columns]
                lines.append(",".join(header))
                for row in data:
                    cells = []
                    for col in columns:
                        val = row.get(col, "")
                        if fmt == "quoted":
                            cells.append(f'"{val}"')
                        elif fmt == "raw":
                            cells.append(str(val))
                        else:
                            cells.append(str(val).strip())
                    lines.append(",".join(cells))
                return "\\n".join(lines)
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.GUARD_CLAUSE_DEFICIT,
            file_path="core/",
            should_detect=False,
            description="All 3 functions have guard clauses in first 30% of body",
        ),
    ],
)

GCD_COMPLEX_TP = GroundTruthFixture(
    name="gcd_complex_tp",
    description="Multiple unguarded high-complexity public functions → should fire GCD",
    files={
        "engine/__init__.py": "",
        "engine/pipeline.py": """\
            def run_pipeline(stages, context, config):
                for stage in stages:
                    if stage["type"] == "filter":
                        context = [c for c in context if stage["fn"](c)]
                    elif stage["type"] == "map":
                        context = [stage["fn"](c) for c in context]
                    elif stage["type"] == "reduce":
                        val = context[0]
                        for c in context[1:]:
                            val = stage["fn"](val, c)
                        context = [val]
                    elif stage["type"] == "sort":
                        context = sorted(context, key=stage.get("key"))
                    else:
                        context = list(context)
                return context

            def validate_schema(data, rules, strict):
                errors = []
                for key, rule in rules.items():
                    val = data.get(key)
                    if rule == "required" and val is None:
                        errors.append(f"{key} is required")
                    elif rule == "int" and not isinstance(val, int):
                        errors.append(f"{key} must be int")
                    elif rule == "str" and not isinstance(val, str):
                        errors.append(f"{key} must be str")
                    elif rule == "positive" and (not isinstance(val, (int, float)) or val <= 0):
                        errors.append(f"{key} must be positive")
                    else:
                        pass
                if strict and errors:
                    raise ValueError(errors)
                return errors

            def build_response(result, headers, status):
                body = {}
                for key in result:
                    if isinstance(result[key], list):
                        body[key] = len(result[key])
                    elif isinstance(result[key], dict):
                        body[key] = list(result[key].keys())
                    elif isinstance(result[key], str):
                        body[key] = result[key][:100]
                    else:
                        body[key] = result[key]
                for h_key, h_val in headers.items():
                    if h_key.startswith("X-"):
                        body[f"header_{h_key}"] = h_val
                return {"status": status, "body": body}
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.GUARD_CLAUSE_DEFICIT,
            file_path="engine/",
            should_detect=True,
            description="3 public functions, all unguarded, high complexity",
        ),
    ],
)

GCD_SIMPLE_TN = GroundTruthFixture(
    name="gcd_simple_tn",
    description="Public functions with low complexity → below CC threshold, should NOT fire GCD",
    files={
        "utils/__init__.py": "",
        "utils/helpers.py": """\
            def add(a, b):
                return a + b

            def multiply(a, b):
                return a * b

            def format_name(first, last):
                return f"{first} {last}"
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.GUARD_CLAUSE_DEFICIT,
            file_path="utils/",
            should_detect=False,
            description="All functions have complexity < 5",
        ),
    ],
)


# ── New fixtures: edge cases for signal improvements ─────────────────────

DIA_URL_FRAGMENT_TN = GroundTruthFixture(
    name="dia_url_fragment_tn",
    description="README with URL-like refs (auth/, db/) → should NOT fire DIA",
    files={
        "README.md": """\
            # API Service

            ## Authentication

            The `auth/` endpoint handles OAuth tokens.
            Use `db/` prefix for database admin routes.

            ```bash
            curl http://localhost:8000/auth/login
            curl http://localhost:8000/db/status
            ```
        """,
        "src/__init__.py": "",
        "src/main.py": """\
            def main():
                pass
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.DOC_IMPL_DRIFT,
            file_path="README.md",
            should_detect=False,
            description="auth/ and db/ are API path fragments, not project dirs",
        ),
    ],
)

BEM_DECORATOR_BOUNDARY_TN = GroundTruthFixture(
    name="bem_decorator_boundary_tn",
    description="Module with @app.errorhandler decorated broad handlers → should NOT fire BEM",
    files={
        "handlers/__init__.py": "",
        "handlers/errors.py": """\
            import logging
            logger = logging.getLogger(__name__)

            def app_errorhandler(func):
                return func

            @app_errorhandler
            def handle_404(error):
                try:
                    return {"error": "not found"}
                except Exception:
                    logger.error("404 handler failed")

            @app_errorhandler
            def handle_500(error):
                try:
                    return {"error": "internal"}
                except Exception:
                    logger.error("500 handler failed")

            @app_errorhandler
            def handle_403(error):
                try:
                    return {"error": "forbidden"}
                except Exception:
                    logger.error("403 handler failed")
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.BROAD_EXCEPTION_MONOCULTURE,
            file_path="handlers/",
            should_detect=False,
            description="Error-handler decorated functions are boundary by design",
        ),
    ],
)

GCD_DECORATOR_GUARD_TN = GroundTruthFixture(
    name="gcd_decorator_guard_tn",
    description="Module with @validate decorated functions → should NOT fire GCD",
    files={
        "api/__init__.py": "",
        "api/endpoints.py": """\
            def validate(func):
                return func

            @validate
            def create_item(data, schema, options):
                result = []
                for item in data:
                    out = {}
                    for key, spec in schema.items():
                        val = item.get(key)
                        if spec == "upper":
                            out[key] = val.upper()
                        elif spec == "lower":
                            out[key] = val.lower()
                        elif spec == "strip":
                            out[key] = val.strip()
                        else:
                            out[key] = val
                    if options.get("filter_key"):
                        if out.get(options["filter_key"]):
                            result.append(out)
                    else:
                        result.append(out)
                return result

            @validate
            def update_item(records, dimensions, funcs):
                groups = {}
                for r in records:
                    key = tuple(r.get(d) for d in dimensions)
                    if key not in groups:
                        groups[key] = []
                    groups[key].append(r)
                out = []
                for key, rows in groups.items():
                    entry = dict(zip(dimensions, key))
                    for fn in funcs:
                        vals = [r.get(fn, 0) for r in rows]
                        if vals:
                            entry[fn] = sum(vals) / len(vals)
                    out.append(entry)
                return out

            @validate
            def delete_item(data, columns, fmt):
                lines = []
                header = [str(c) for c in columns]
                lines.append(",".join(header))
                for row in data:
                    cells = []
                    for col in columns:
                        val = row.get(col, "")
                        if fmt == "quoted":
                            cells.append(f'"' + str(val) + '"')
                        elif fmt == "raw":
                            cells.append(str(val))
                        else:
                            cells.append(str(val).strip())
                    lines.append(",".join(cells))
                return "\\n".join(lines)
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.GUARD_CLAUSE_DEFICIT,
            file_path="api/",
            should_detect=False,
            description="All functions use @validate decorator → guarded externally",
        ),
    ],
)


# ── Cohesion Deficit (COD) ──────────────────────────────────────────────

COD_TRUE_POSITIVE = GroundTruthFixture(
    name="cod_tp",
    description="Single file with unrelated responsibilities → should fire COD",
    files={
        "utils/__init__.py": "",
        "utils/misc.py": """\
            def parse_invoice_xml(raw: str) -> dict:
                return {"invoice": raw.strip()}

            def send_slack_alert(message: str) -> None:
                print(f"alert: {message}")

            def resize_profile_image(image: bytes, width: int) -> bytes:
                return image[:width]

            def compile_tax_report(rows: list[dict]) -> list[dict]:
                return sorted(rows, key=lambda r: r.get("year", 0))

            def decrypt_api_secret(token: str) -> str:
                return token[::-1]

            class ExperimentScheduler:
                def enqueue_trial(self, payload: dict) -> dict:
                    return {"queued": True, "payload": payload}
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.COHESION_DEFICIT,
            file_path="utils/misc.py",
            should_detect=True,
            description="Mixed domains in one file indicate low cohesion",
        ),
    ],
)

COD_TRUE_NEGATIVE = GroundTruthFixture(
    name="cod_tn",
    description="Single cohesive tax module → should NOT fire COD",
    files={
        "finance/__init__.py": "",
        "finance/tax.py": """\
            def calculate_tax_base(amount: float, discount: float) -> float:
                return max(0.0, amount - discount)

            def calculate_tax_rate(region: str) -> float:
                if region == "EU":
                    return 0.19
                return 0.07

            def validate_tax_input(amount: float, discount: float) -> bool:
                return amount >= 0 and discount >= 0

            def round_tax_amount(amount: float) -> float:
                return round(amount, 2)

            def format_tax_summary(amount: float, region: str) -> str:
                return f"tax for {region}: {round_tax_amount(amount)}"
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.COHESION_DEFICIT,
            file_path="finance/tax.py",
            should_detect=False,
            description="Domain vocabulary is cohesive across all units",
        ),
    ],
)


# ── Registry of all fixtures ─────────────────────────────────────────────

ALL_FIXTURES: list[GroundTruthFixture] = [
    PFS_TRUE_POSITIVE,
    PFS_TRUE_NEGATIVE,
    PFS_VALIDATION_TP,
    PFS_LOGGING_TP,
    PFS_BOUNDARY_TP,
    PFS_CONFOUNDER_TN,
    PFS_DECORATOR_TN,
    PFS_RETURN_PATTERN_TP,
    AVS_TRUE_POSITIVE,
    AVS_TRUE_NEGATIVE,
    AVS_CIRCULAR_TP,
    AVS_SKIP_LAYER_TP,
    AVS_BOUNDARY_TN,
    AVS_CONFOUNDER_TN,
    MDS_TRUE_POSITIVE,
    MDS_TRUE_NEGATIVE,
    MDS_NEAR_DUPLICATE_TP,
    MDS_EXACT_TRIPLE_TP,
    EDS_TRUE_POSITIVE,
    EDS_TRUE_NEGATIVE,
    EDS_STATE_MACHINE_TP,
    EDS_NESTED_LOOPS_TP,
    EDS_INIT_TN,
    TVS_TRUE_POSITIVE,
    TVS_TRUE_NEGATIVE,
    SMS_TRUE_POSITIVE,
    SMS_TRUE_NEGATIVE,
    SMS_ML_IN_WEB_TP,
    DIA_TRUE_POSITIVE,
    DIA_TRUE_NEGATIVE,
    DIA_ADR_MISMATCH_TP,
    DIA_ADR_FILE_TP,
    DIA_URL_FRAGMENT_TN,
    BEM_TRUE_POSITIVE,
    BEM_TRUE_NEGATIVE,
    BEM_MIXED_TP,
    BEM_BOUNDARY_TN,
    BEM_DECORATOR_BOUNDARY_TN,
    TPD_TRUE_POSITIVE,
    TPD_TRUE_NEGATIVE,
    TPD_LARGE_SUITE_TP,
    TPD_FEW_TESTS_TN,
    GCD_TRUE_POSITIVE,
    GCD_TRUE_NEGATIVE,
    GCD_COMPLEX_TP,
    GCD_SIMPLE_TN,
    GCD_DECORATOR_GUARD_TN,
    COD_TRUE_POSITIVE,
    COD_TRUE_NEGATIVE,
    # ── NBV / BAT fixtures below ──
]


# ── Naming Contract Violation (NBV) ─────────────────────────────────────

NBV_VALIDATE_TP = GroundTruthFixture(
    name="nbv_validate_tp",
    description="validate_email() without raise or return False → should fire NBV",
    files={
        "core/__init__.py": "",
        "core/validators.py": """\
            def validate_email(email: str) -> str:
                parts = email.split("@")
                domain = parts[-1] if len(parts) > 1 else ""
                local = parts[0] if parts else ""
                cleaned = local.strip().lower()
                return f"{cleaned}@{domain}"
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.NAMING_CONTRACT_VIOLATION,
            file_path="core/validators.py",
            should_detect=True,
            description="validate_email has no raise and never returns False/None",
        ),
    ],
)

NBV_ENSURE_TP = GroundTruthFixture(
    name="nbv_ensure_tp",
    description="ensure_connection() without raise → should fire NBV",
    files={
        "infra/__init__.py": "",
        "infra/db.py": """\
            def ensure_connection(host: str, port: int) -> dict:
                config = {"host": host, "port": port}
                config["timeout"] = 30
                config["retries"] = 3
                return config
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.NAMING_CONTRACT_VIOLATION,
            file_path="infra/db.py",
            should_detect=True,
            description="ensure_connection has no raise statement",
        ),
    ],
)

NBV_IS_HAS_TP = GroundTruthFixture(
    name="nbv_is_has_tp",
    description="is_valid() without bool return → should fire NBV",
    files={
        "utils/__init__.py": "",
        "utils/checks.py": """\
            def is_valid(data: dict) -> str:
                keys = list(data.keys())
                values = list(data.values())
                summary = f"{len(keys)} keys, {len(values)} values"
                return summary
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.NAMING_CONTRACT_VIOLATION,
            file_path="utils/checks.py",
            should_detect=True,
            description="is_valid returns str, not bool",
        ),
    ],
)

NBV_GET_OR_CREATE_TP = GroundTruthFixture(
    name="nbv_get_or_create_tp",
    description="get_or_create_user() without creation path → should fire NBV",
    files={
        "services/__init__.py": "",
        "services/users.py": """\
            USERS = {"alice": {"id": 1}, "bob": {"id": 2}}

            def get_or_create_user(name: str) -> dict:
                user = USERS.get(name)
                result = user if user else {}
                return result
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.NAMING_CONTRACT_VIOLATION,
            file_path="services/users.py",
            should_detect=True,
            description="get_or_create_user has no creation path after conditional",
        ),
    ],
)

NBV_TRY_TP = GroundTruthFixture(
    name="nbv_try_tp",
    description="try_connect() without try/except → should fire NBV",
    files={
        "network/__init__.py": "",
        "network/client.py": """\
            def try_connect(host: str, port: int) -> dict:
                addr = f"{host}:{port}"
                config = {"address": addr, "connected": False}
                config["connected"] = True
                return config
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.NAMING_CONTRACT_VIOLATION,
            file_path="network/client.py",
            should_detect=True,
            description="try_connect has no try/except block",
        ),
    ],
)

NBV_TRUE_NEGATIVE = GroundTruthFixture(
    name="nbv_tn",
    description="All naming contracts correctly fulfilled → should NOT fire NBV",
    files={
        "lib/__init__.py": "",
        "lib/contracts.py": """\
            def validate_input(data: dict) -> bool:
                if not data:
                    raise ValueError("data is empty")
                if "id" not in data:
                    return False
                return True

            def ensure_ready(service: str) -> None:
                if not service:
                    raise RuntimeError("service not configured")
                if len(service) < 2:
                    raise ValueError("invalid service name")

            def is_active(status: str) -> bool:
                return status == "active"

            def try_parse(raw: str) -> dict:
                try:
                    parts = raw.split(",")
                    return {"parts": parts}
                except Exception:
                    return {}
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.NAMING_CONTRACT_VIOLATION,
            file_path="lib/contracts.py",
            should_detect=False,
            description="All naming contracts are satisfied",
        ),
    ],
)

NBV_STUB_TN = GroundTruthFixture(
    name="nbv_stub_tn",
    description="Functions under nbv_min_function_loc → should NOT fire NBV",
    files={
        "stubs/__init__.py": "",
        "stubs/tiny.py": """\
            def validate_id(x):
                return x

            def is_ok(v):
                return v
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.NAMING_CONTRACT_VIOLATION,
            file_path="stubs/tiny.py",
            should_detect=False,
            description="Functions too small (< 3 LOC) — below threshold",
        ),
    ],
)

NBV_TS_ASYNC_BOOL_TN = GroundTruthFixture(
    name="nbv_ts_async_bool_tn",
    description=(
        "TypeScript is_*/has_* with PromiseLike/Observable<boolean> wrappers "
        "should NOT fire NBV"
    ),
    files={
        "src/checks.ts": """\
            export async function isSessionActive(): Promise<boolean> {
                return false;
            }

            export function hasPermission(): PromiseLike<boolean> {
                return Promise.resolve(true);
            }

            export function isObservableReady(): Observable<boolean> {
                return streamReady;
            }
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.NAMING_CONTRACT_VIOLATION,
            file_path="src/checks.ts",
            should_detect=False,
            description="Async boolean wrappers satisfy is_*/has_* bool contract",
        ),
    ],
)

NBV_TS_ENSURE_UPSERT_TN = GroundTruthFixture(
    name="nbv_ts_ensure_upsert_tn",
    description=(
        "TypeScript ensure_* upsert/get-or-create pattern with return value "
        "should NOT fire NBV"
    ),
    files={
        "src/config.ts": """\
            export type JsonRecord = Record<string, unknown>;

            export function ensureRecord(root: JsonRecord, key: string): JsonRecord {
                let next = root[key];
                if (next == null || typeof next !== "object" || Array.isArray(next)) {
                    next = {};
                    root[key] = next;
                }
                return next as JsonRecord;
            }
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.NAMING_CONTRACT_VIOLATION,
            file_path="src/config.ts",
            should_detect=False,
            description="TS ensure_* upsert with value return satisfies language-specific contract",
        ),
    ],
)


# ── Bypass Accumulation (BAT) ───────────────────────────────────────────

BAT_TRUE_POSITIVE = GroundTruthFixture(
    name="bat_tp",
    description="File >50 LOC with >5% bypass marker density → should fire BAT",
    files={
        "legacy/__init__.py": "",
        "legacy/compat.py": (
            "# Legacy compatibility layer\n"
            + "\n".join(
                [
                    f"def func_{i}(x):  # type: ignore"
                    if i % 3 == 0
                    else (
                        f"def func_{i}(x):  # noqa"
                        if i % 3 == 1
                        else f"def func_{i}(x):  # pragma: no cover"
                    )
                    for i in range(20)
                ]
            )
            + "\n"
            + "\n".join([f"    return x + {i}" for i in range(20)])
            + "\n# TODO fix all the above\n"
            + "# FIXME legacy code\n"
            + "# HACK workaround\n"
            + "\n".join([f"CONST_{i} = {i}" for i in range(20)])
        ),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.BYPASS_ACCUMULATION,
            file_path="legacy/compat.py",
            should_detect=True,
            description="High bypass marker density (type: ignore, noqa, pragma, TODO/FIXME/HACK)",
        ),
    ],
)

BAT_HIGH_DENSITY_TP = GroundTruthFixture(
    name="bat_high_density_tp",
    description="File with very high bypass density (>10%) → should fire BAT with HIGH severity",
    files={
        "hacks/__init__.py": "",
        "hacks/workaround.py": "\n".join(
            [f"x_{i} = None  # type: ignore" for i in range(60)]
            + [f"# TODO fix item {i}" for i in range(10)]
        ),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.BYPASS_ACCUMULATION,
            file_path="hacks/workaround.py",
            should_detect=True,
            description="Very high bypass marker density -> HIGH severity",
        ),
    ],
)

BAT_TRUE_NEGATIVE = GroundTruthFixture(
    name="bat_tn",
    description="File >50 LOC with <5% bypass density → should NOT fire BAT",
    files={
        "clean/__init__.py": "",
        "clean/module.py": "\n".join(
            [f"def clean_func_{i}(x):" for i in range(25)]
            + [f"    return x + {i}" for i in range(25)]
            + ["# one TODO is fine", "CONST = 42"]
        ),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.BYPASS_ACCUMULATION,
            file_path="clean/module.py",
            should_detect=False,
            description="Low bypass density — below threshold",
        ),
    ],
)

BAT_TINY_FILE_TN = GroundTruthFixture(
    name="bat_tiny_file_tn",
    description="File <50 LOC even with high marker density → should NOT fire BAT",
    files={
        "small/__init__.py": "",
        "small/tiny.py": "\n".join([f"x = {i}  # type: ignore" for i in range(10)]),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.BYPASS_ACCUMULATION,
            file_path="small/tiny.py",
            should_detect=False,
            description="File too small (<50 LOC) — below bat_min_loc threshold",
        ),
    ],
)

BAT_TEST_FILE_TN = GroundTruthFixture(
    name="bat_test_file_tn",
    description="Test file with high bypass density → excluded, should NOT fire BAT",
    files={
        "tests/__init__.py": "",
        "tests/test_legacy.py": "\n".join(
            [f"def test_item_{i}():  # type: ignore" for i in range(30)]
            + ["    assert True  # noqa" for _ in range(30)]
        ),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.BYPASS_ACCUMULATION,
            file_path="tests/test_legacy.py",
            should_detect=False,
            description="Test files are excluded from BAT analysis",
        ),
    ],
)


# ── Boundary & Confounder fixtures ────────────────────────────────────────
# Boundary: near detection threshold (±1 of config default).
# Confounder: structurally similar to a real finding but benign.


# -- MDS boundary (similarity_threshold = 0.80) --

MDS_BOUNDARY_TP = GroundTruthFixture(
    name="mds_boundary_tp",
    description="Near-duplicate pair just above similarity threshold → should fire MDS",
    kind=FixtureKind.BOUNDARY,
    files={
        "services/__init__.py": "",
        "services/export_csv.py": """\
            def export_records(records: list, output_path: str) -> int:
                \"\"\"Export records to CSV file.\"\"\"
                count = 0
                with open(output_path, "w") as fh:
                    for record in records:
                        line_parts = []
                        for key in sorted(record.keys()):
                            value = str(record[key])
                            line_parts.append(value)
                        fh.write(",".join(line_parts) + "\\n")
                        count += 1
                return count
        """,
        "services/export_tsv.py": """\
            def dump_records(records: list, target_path: str) -> int:
                \"\"\"Dump records to TSV file.\"\"\"
                total = 0
                with open(target_path, "w") as fh:
                    for record in records:
                        line_parts = []
                        for key in sorted(record.keys()):
                            value = str(record[key])
                            line_parts.append(value)
                        fh.write("\\t".join(line_parts) + "\\n")
                        total += 1
                return total
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.MUTANT_DUPLICATE,
            file_path="services/",
            should_detect=True,
            description="Structural clone differing only in separator and var names",
        ),
    ],
)

MDS_CONFOUNDER_TN = GroundTruthFixture(
    name="mds_confounder_tn",
    description="Async/sync pair with same logic — intentional variant, not a duplicate",
    kind=FixtureKind.CONFOUNDER,
    files={
        "transport/__init__.py": "",
        "transport/sync_client.py": """\
            def send_request(url: str, payload: dict) -> dict:
                \"\"\"Send HTTP request synchronously.\"\"\"
                import urllib.request
                import json
                data = json.dumps(payload).encode()
                req = urllib.request.Request(url, data=data)
                req.add_header("Content-Type", "application/json")
                with urllib.request.urlopen(req) as resp:
                    body = resp.read().decode()
                return json.loads(body)
        """,
        "transport/async_client.py": """\
            async def send_request(url: str, payload: dict) -> dict:
                \"\"\"Send HTTP request asynchronously.\"\"\"
                import aiohttp
                import json
                data = json.dumps(payload)
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, data=data) as resp:
                        body = await resp.text()
                return json.loads(body)
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.MUTANT_DUPLICATE,
            file_path="transport/",
            should_detect=False,
            description="Async/sync variants are intentional — not copy-paste",
        ),
    ],
)


# -- EDS boundary (high_complexity = 10, min_function_loc = 10) --

EDS_BOUNDARY_TP = GroundTruthFixture(
    name="eds_boundary_tp",
    description="Function at CC=10 (exactly at threshold) without docstring → should fire EDS",
    kind=FixtureKind.BOUNDARY,
    files={
        "core/__init__.py": "",
        "core/threshold.py": """\
            def classify_event(event, rules, context, fallback):
                result = fallback
                for rule in rules:
                    if rule["type"] == "match":
                        if event.get("source") == rule["value"]:
                            result = rule["action"]
                    elif rule["type"] == "range":
                        if rule["low"] <= event.get("score", 0) <= rule["high"]:
                            result = rule["action"]
                    elif rule["type"] == "context":
                        if context.get(rule["key"]):
                            result = rule["action"]
                    else:
                        if event.get("priority", 0) > 5:
                            result = "escalate"
                return result
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.EXPLAINABILITY_DEFICIT,
            file_path="core/threshold.py",
            should_detect=True,
            description="CC at threshold (10), no docstring, meets min_function_loc",
        ),
    ],
)

EDS_BOUNDARY_TN = GroundTruthFixture(
    name="eds_boundary_tn",
    description="Function just below CC threshold with no docstring → should NOT fire EDS",
    kind=FixtureKind.BOUNDARY,
    files={
        "core/__init__.py": "",
        "core/below_threshold.py": """\
            def route_event(event, handler_map):
                kind = event.get("kind", "default")
                handler = handler_map.get(kind)
                if handler:
                    return handler(event)
                return None
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.EXPLAINABILITY_DEFICIT,
            file_path="core/below_threshold.py",
            should_detect=False,
            description="CC below threshold — no EDS expected",
        ),
    ],
)

EDS_CONFOUNDER_TN = GroundTruthFixture(
    name="eds_confounder_tn",
    description="High-complexity function in test file → should NOT fire EDS",
    kind=FixtureKind.CONFOUNDER,
    files={
        "tests/__init__.py": "",
        "tests/test_complex.py": """\
            def test_all_branches():
                for case in range(20):
                    if case % 2 == 0:
                        if case > 10:
                            assert case < 20
                        else:
                            assert case >= 0
                    elif case % 3 == 0:
                        assert case > 0
                    elif case % 5 == 0:
                        assert case > 0
                    else:
                        assert True
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.EXPLAINABILITY_DEFICIT,
            file_path="tests/test_complex.py",
            should_detect=False,
            description="High CC in test file — should be excluded",
        ),
    ],
)


# -- TVS boundary (volatility_z_threshold = 1.5) --

TVS_BOUNDARY_TP = GroundTruthFixture(
    name="tvs_boundary_tp",
    description="File with churn just above z-score threshold among stable peers",
    kind=FixtureKind.BOUNDARY,
    files={
        "app/__init__.py": "",
        "app/module_a.py": """\
            def func_a():
                return 1
        """,
        "app/module_b.py": """\
            def func_b():
                return 2
        """,
        "app/module_c.py": """\
            def func_c():
                return 3
        """,
        "app/module_d.py": """\
            def func_d():
                return 4
        """,
        "app/borderline.py": """\
            def borderline_func(x):
                return x * 2
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.TEMPORAL_VOLATILITY,
            file_path="app/borderline.py",
            should_detect=True,
            description="Churn just above z-score threshold among stable peers",
        ),
    ],
    file_history_overrides={
        # Stable peers: ~1 commit, 0.5 change freq
        "app/module_a.py": FileHistoryOverride(total_commits=2, change_frequency_30d=0.5),
        "app/module_b.py": FileHistoryOverride(total_commits=2, change_frequency_30d=0.5),
        "app/module_c.py": FileHistoryOverride(total_commits=2, change_frequency_30d=0.5),
        "app/module_d.py": FileHistoryOverride(total_commits=2, change_frequency_30d=0.5),
        # Borderline: enough churn to be >1.5σ above mean of ~0.5
        "app/borderline.py": FileHistoryOverride(
            total_commits=30,
            unique_authors=4,
            change_frequency_30d=12.0,
            defect_correlated_commits=5,
        ),
    },
)

TVS_CONFOUNDER_TN = GroundTruthFixture(
    name="tvs_confounder_tn",
    description="All files have uniformly high churn — no outlier → should NOT fire TVS",
    kind=FixtureKind.CONFOUNDER,
    files={
        "app/__init__.py": "",
        "app/hot_a.py": """\
            def hot_a():
                return "a"
        """,
        "app/hot_b.py": """\
            def hot_b():
                return "b"
        """,
        "app/hot_c.py": """\
            def hot_c():
                return "c"
        """,
        "app/hot_d.py": """\
            def hot_d():
                return "d"
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.TEMPORAL_VOLATILITY,
            file_path="app/",
            should_detect=False,
            description="Uniform high churn — no z-score outlier",
        ),
    ],
    file_history_overrides={
        "app/hot_a.py": FileHistoryOverride(
            total_commits=40,
            unique_authors=5,
            change_frequency_30d=15.0,
        ),
        "app/hot_b.py": FileHistoryOverride(
            total_commits=38,
            unique_authors=5,
            change_frequency_30d=14.0,
        ),
        "app/hot_c.py": FileHistoryOverride(
            total_commits=42,
            unique_authors=6,
            change_frequency_30d=16.0,
        ),
        "app/hot_d.py": FileHistoryOverride(
            total_commits=39,
            unique_authors=5,
            change_frequency_30d=15.0,
        ),
    },
)


# -- SMS boundary/confounder --

SMS_BOUNDARY_TP = GroundTruthFixture(
    name="sms_boundary_tp",
    description="File introduces exactly one novel third-party import → should fire SMS",
    kind=FixtureKind.BOUNDARY,
    files={
        "services/__init__.py": "",
        "services/core.py": """\
            import json
            import logging

            def process(data):
                logging.info("Processing")
                return json.dumps(data)
        """,
        "services/helper.py": """\
            import json

            def transform(data):
                return json.loads(data)
        """,
        "services/new_feature.py": """\
            import json
            import celery

            def enqueue(data):
                return celery.current_app.send_task("run", args=[json.dumps(data)])
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.SYSTEM_MISALIGNMENT,
            file_path="services/",
            should_detect=True,
            description="celery is novel third-party in services/ — misalignment",
        ),
    ],
)

SMS_CONFOUNDER_TN = GroundTruthFixture(
    name="sms_confounder_tn",
    description="stdlib import used by one file but common in Python → should NOT fire SMS",
    kind=FixtureKind.CONFOUNDER,
    files={
        "utils/__init__.py": "",
        "utils/text.py": """\
            import re
            import string

            def clean(text):
                return re.sub(r"\\s+", " ", text).strip()
        """,
        "utils/numbers.py": """\
            import math

            def round_up(x):
                return math.ceil(x)
        """,
        "utils/dates.py": """\
            import datetime

            def today():
                return datetime.date.today()
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.SYSTEM_MISALIGNMENT,
            file_path="utils/",
            should_detect=False,
            description="Each file uses different stdlib modules — all common, not misaligned",
        ),
    ],
)


# -- DIA boundary --

DIA_BOUNDARY_TP = GroundTruthFixture(
    name="dia_boundary_tp",
    description="README references one existing and one non-existing directory",
    kind=FixtureKind.BOUNDARY,
    files={
        "README.md": """\
            # Project

            Structure:
            - `src/` — source code
            - `migrations/` — database migrations
        """,
        "src/__init__.py": "",
        "src/app.py": """\
            def run():
                pass
        """,
        # migrations/ does NOT exist
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.DOC_IMPL_DRIFT,
            file_path="README.md",
            should_detect=True,
            description="migrations/ referenced but missing — single phantom dir",
        ),
    ],
)


# -- TPD boundary (tpd_min_test_functions = 5) --

TPD_BOUNDARY_TP = GroundTruthFixture(
    name="tpd_boundary_tp",
    description="5 test functions, 10 positive asserts, 0 negative → should fire TPD",
    kind=FixtureKind.BOUNDARY,
    files={
        "tests/__init__.py": "",
        "tests/test_boundary.py": """\
            def test_one():
                assert 1 + 1 == 2
                assert 2 + 2 == 4

            def test_two():
                assert "hello".upper() == "HELLO"
                assert "world".lower() == "world"

            def test_three():
                assert [1, 2, 3] == [1, 2, 3]
                assert len([1, 2]) == 2

            def test_four():
                assert len("abc") == 3
                assert len("ab") == 2

            def test_five():
                assert True
                assert 3 > 1
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.TEST_POLARITY_DEFICIT,
            file_path="tests/",
            should_detect=True,
            description="5 tests, 10 positive asserts, 0 negative → deficit",
        ),
    ],
)

TPD_CONFOUNDER_TN = GroundTruthFixture(
    name="tpd_confounder_tn",
    description="Large test suite with negative tests via manual exception checks",
    kind=FixtureKind.CONFOUNDER,
    files={
        "tests/__init__.py": "",
        "tests/test_robust.py": """\
            import pytest

            def test_create():
                assert True

            def test_read():
                assert True

            def test_update():
                assert True

            def test_delete():
                assert True

            def test_invalid_create():
                with pytest.raises(ValueError):
                    raise ValueError("bad input")

            def test_invalid_read():
                with pytest.raises(KeyError):
                    raise KeyError("not found")

            def test_overflow():
                with pytest.raises(OverflowError):
                    raise OverflowError("too big")
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.TEST_POLARITY_DEFICIT,
            file_path="tests/",
            should_detect=False,
            description="3 negative tests out of 7 → ratio > 10%, balanced",
        ),
    ],
)


# -- GCD boundary (gcd_min_public_functions = 3) --

GCD_BOUNDARY_TP = GroundTruthFixture(
    name="gcd_boundary_tp",
    description="Exactly 3 public functions (at threshold) with no guards → should fire GCD",
    kind=FixtureKind.BOUNDARY,
    files={
        "core/__init__.py": "",
        "core/unguarded.py": """\
            def process(items, config, mode):
                results = []
                for item in items:
                    if mode == "fast":
                        results.append(item)
                    elif mode == "slow":
                        for sub in item:
                            results.append(sub)
                    else:
                        results.append(str(item))
                return results

            def merge(left, right, strategy):
                output = {}
                for k in left:
                    if strategy == "left":
                        output[k] = left[k]
                    elif strategy == "right":
                        output[k] = right.get(k, left[k])
                    else:
                        output[k] = left[k]
                for k in right:
                    if k not in output:
                        output[k] = right[k]
                return output

            def render(template, data, fmt):
                lines = []
                for key, value in data.items():
                    if fmt == "json":
                        lines.append(f'"{key}": "{value}"')
                    elif fmt == "xml":
                        lines.append(f"<{key}>{value}</{key}>")
                    elif fmt == "yaml":
                        lines.append(f"{key}: {value}")
                    elif fmt == "toml":
                        lines.append(f"{key} = {value}")
                    else:
                        lines.append(f"{key}={value}")
                return "\\n".join(lines)
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.GUARD_CLAUSE_DEFICIT,
            file_path="core/",
            should_detect=True,
            description="Exactly 3 public functions (min threshold), all unguarded",
        ),
    ],
)


# -- COD boundary/confounder --

COD_BOUNDARY_TP = GroundTruthFixture(
    name="cod_boundary_tp",
    description="File with 6 semantically unrelated functions → low cohesion",
    kind=FixtureKind.BOUNDARY,
    files={
        "app/__init__.py": "",
        "app/mixed.py": """\
            def send_email_notification(recipient, subject):
                print(f"Sending email to {recipient}: {subject}")
                return True

            def parse_csv_upload(raw_data):
                lines = raw_data.decode().strip().split("\\n")
                return [line.split(",") for line in lines]

            def generate_pdf_invoice(order_id, items):
                header = f"Invoice #{order_id}\\n"
                body = "\\n".join(str(i) for i in items)
                return (header + body).encode()

            def calculate_tax_rate(income, region):
                return income * 0.19 if region == "DE" else income * 0.21

            def compress_image_thumbnail(path, quality):
                return f"compressed:{path}:{quality}"

            def decrypt_auth_token(cipher, secret):
                return cipher[::-1]
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.COHESION_DEFICIT,
            file_path="app/mixed.py",
            should_detect=True,
            description="Six unrelated domains in one file → cohesion deficit",
        ),
    ],
)

COD_CONFOUNDER_TN = GroundTruthFixture(
    name="cod_confounder_tn",
    description="Functions sharing 'text' token → cohesive by naming, should NOT fire COD",
    kind=FixtureKind.CONFOUNDER,
    files={
        "utils/__init__.py": "",
        "utils/helpers.py": """\
            def format_text(raw):
                return raw.strip()

            def clean_text(raw):
                import re
                return re.sub(r"\\s+", " ", raw)

            def validate_text(raw):
                return len(raw) > 0

            def normalize_text(raw):
                return raw.lower()

            def split_text(raw):
                return raw.split()
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.COHESION_DEFICIT,
            file_path="utils/helpers.py",
            should_detect=False,
            description="All share 'text' token → cohesive naming, no deficit",
        ),
    ],
)


# -- NBV boundary (nbv_min_function_loc = 3) --

NBV_BOUNDARY_TP = GroundTruthFixture(
    name="nbv_boundary_tp",
    description="validate_ function with exactly 3 LOC (at threshold) without raise → should fire",
    kind=FixtureKind.BOUNDARY,
    files={
        "core/__init__.py": "",
        "core/check.py": """\
            def validate_token(token: str) -> str:
                parts = token.split(".")
                cleaned = parts[0].strip()
                return cleaned
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.NAMING_CONTRACT_VIOLATION,
            file_path="core/check.py",
            should_detect=True,
            description="validate_token at exactly nbv_min_function_loc=3, no raise",
        ),
    ],
)

NBV_CONFOUNDER_TN = GroundTruthFixture(
    name="nbv_confounder_tn",
    description="validate_ function that delegates to a raising helper → should NOT fire NBV",
    kind=FixtureKind.CONFOUNDER,
    files={
        "core/__init__.py": "",
        "core/validation.py": """\
            def _check_format(value: str) -> None:
                if not value:
                    raise ValueError("empty value")

            def validate_email(email: str) -> bool:
                _check_format(email)
                if "@" not in email:
                    raise ValueError("missing @")
                return True
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.NAMING_CONTRACT_VIOLATION,
            file_path="core/validation.py",
            should_detect=False,
            description="validate_email raises ValueError — contract satisfied",
        ),
    ],
)


# -- BEM confounders --

BEM_CONFOUNDER_FLASK_TN = GroundTruthFixture(
    name="bem_confounder_flask_tn",
    description="Flask-style error handlers with broad except — framework-idiomatic",
    kind=FixtureKind.CONFOUNDER,
    files={
        "app/__init__.py": "",
        "app/errors.py": """\
            import logging
            logger = logging.getLogger(__name__)

            def errorhandler(code):
                def decorator(func):
                    return func
                return decorator

            @errorhandler(404)
            def not_found(error):
                try:
                    return {"error": "not found", "code": 404}
                except Exception:
                    logger.error("404 handler failed")
                    return {"error": "internal"}, 500

            @errorhandler(500)
            def internal_error(error):
                try:
                    return {"error": "server error", "code": 500}
                except Exception:
                    logger.error("500 handler failed")
                    return {"error": "internal"}, 500

            @errorhandler(403)
            def forbidden(error):
                try:
                    return {"error": "forbidden", "code": 403}
                except Exception:
                    logger.error("403 handler failed")
                    return {"error": "internal"}, 500
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.BROAD_EXCEPTION_MONOCULTURE,
            file_path="app/",
            should_detect=False,
            description="Flask @errorhandler decorated → boundary by design",
        ),
    ],
)

BEM_CONFOUNDER_CELERY_TN = GroundTruthFixture(
    name="bem_confounder_celery_tn",
    description="Celery tasks with self.retry() inside broad except — idiomatic retry pattern",
    kind=FixtureKind.CONFOUNDER,
    files={
        "tasks/__init__.py": "",
        "tasks/worker.py": """\
            import logging
            logger = logging.getLogger(__name__)

            class TaskBase:
                def retry(self, exc=None, countdown=10):
                    raise exc

            def shared_task(bind=False):
                def decorator(func):
                    return func
                return decorator

            @shared_task(bind=True)
            def fetch_data(self, url):
                try:
                    return {"data": "ok"}
                except Exception as exc:
                    logger.warning("fetch failed, retrying")
                    self.retry(exc=exc, countdown=30)

            @shared_task(bind=True)
            def send_notification(self, user_id, msg):
                try:
                    return True
                except Exception as exc:
                    logger.warning("notification failed, retrying")
                    self.retry(exc=exc, countdown=60)

            @shared_task(bind=True)
            def sync_records(self, batch_id):
                try:
                    return {"synced": batch_id}
                except Exception as exc:
                    logger.warning("sync failed, retrying")
                    self.retry(exc=exc, countdown=120)
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.BROAD_EXCEPTION_MONOCULTURE,
            file_path="tasks/",
            should_detect=False,
            description="Celery @shared_task with retry — boundary by design",
        ),
    ],
)

BEM_CONFOUNDER_LOGGING_TN = GroundTruthFixture(
    name="bem_confounder_logging_tn",
    description="Stdlib logging.exception() in except BaseException — accepted pattern",
    kind=FixtureKind.CONFOUNDER,
    files={
        "reporting/__init__.py": "",
        "reporting/error_handler.py": """\
            import logging
            logger = logging.getLogger(__name__)

            def report_api_error(endpoint, params):
                try:
                    return call_api(endpoint, params)
                except BaseException:
                    logging.exception("API call to %s failed", endpoint)
                    return None

            def report_db_error(query, args):
                try:
                    return execute(query, args)
                except BaseException:
                    logging.exception("DB query failed: %s", query)
                    return None

            def report_cache_error(key):
                try:
                    return cache_get(key)
                except BaseException:
                    logging.exception("Cache lookup failed for %s", key)
                    return None
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.BROAD_EXCEPTION_MONOCULTURE,
            file_path="reporting/",
            should_detect=False,
            description="Error-handler module with logging.exception — boundary by name",
        ),
    ],
)

BEM_CONFOUNDER_STRING_TN = GroundTruthFixture(
    name="bem_confounder_string_tn",
    description="Module with 'except Exception' only in docstrings/comments — should NOT fire BEM",
    kind=FixtureKind.CONFOUNDER,
    files={
        "docs_helpers/__init__.py": "",
        "docs_helpers/examples.py": """\
            \"\"\"Example module demonstrating exception handling.

            Bad pattern:
                try:
                    result = do_something()
                except Exception:
                    pass  # swallowed!

            Good pattern:
                try:
                    result = do_something()
                except ValueError as e:
                    logger.error("Specific: %s", e)
                    raise
            \"\"\"

            def safe_parse(text: str) -> dict:
                # This does NOT use broad except — only references it in comments
                # See: "except Exception:" is an anti-pattern
                try:
                    import json
                    return json.loads(text)
                except (ValueError, TypeError) as exc:
                    raise RuntimeError("parse failed") from exc

            def safe_convert(value: str) -> int:
                # "except BaseException" should never be used here
                try:
                    return int(value)
                except (ValueError, OverflowError):
                    raise

            def safe_lookup(mapping: dict, key: str) -> str:
                # These comments mention "except Exception" but code doesn't use it
                try:
                    return mapping[key]
                except KeyError:
                    raise
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.BROAD_EXCEPTION_MONOCULTURE,
            file_path="docs_helpers/",
            should_detect=False,
            description="'except Exception' only in strings/comments, not real handlers",
        ),
    ],
)


# -- DIA confounders --

DIA_CONFOUNDER_BADGE_TN = GroundTruthFixture(
    name="dia_confounder_badge_tn",
    description="README with badge URLs containing path-like segments → should NOT fire DIA",
    kind=FixtureKind.CONFOUNDER,
    files={
        "README.md": """\
            # MyProject

            [![Build](https://github.com/org/repo/actions/workflows/ci.yml/badge.svg)](https://github.com/org/repo/actions)
            [![Coverage](https://codecov.io/gh/org/repo/branch/main/graph/badge.svg)](https://codecov.io/gh/org/repo)
            [![PyPI](https://img.shields.io/pypi/v/myproject.svg)](https://pypi.org/project/myproject/)

            ## Installation

            ```bash
            pip install myproject
            ```
        """,
        "src/__init__.py": "",
        "src/main.py": """\
            def main():
                pass
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.DOC_IMPL_DRIFT,
            file_path="README.md",
            should_detect=False,
            description="Badge/shield URLs are not project directory references",
        ),
    ],
)

DIA_CONFOUNDER_HEADING_TN = GroundTruthFixture(
    name="dia_confounder_heading_tn",
    description="README with directory-like headings (TypeScript/, Frontend/) → not DIA",
    kind=FixtureKind.CONFOUNDER,
    files={
        "README.md": """\
            # Multi-Language Guide

            This project supports multiple ecosystems:

            ## TypeScript/

            TypeScript support is planned but not yet implemented.

            ## Frontend/

            The frontend code will live in a separate repository.

            ## Getting Started

            Run `pip install mypackage` to get started.
        """,
        "src/__init__.py": "",
        "src/core.py": """\
            def process():
                return True
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.DOC_IMPL_DRIFT,
            file_path="README.md",
            should_detect=False,
            description="TypeScript/ and Frontend/ are section headings, not dir refs",
        ),
    ],
)

DIA_CONFOUNDER_API_PATH_TN = GroundTruthFixture(
    name="dia_confounder_api_path_tn",
    description="README with API endpoint paths in code blocks → should NOT fire DIA",
    kind=FixtureKind.CONFOUNDER,
    files={
        "README.md": """\
            # API Documentation

            ## Endpoints

            All endpoints are prefixed with `/api/v1/`:

            ```
            GET  /api/v1/users/
            POST /api/v1/auth/login
            DELETE /api/v1/sessions/
            ```

            ## Configuration

            Set `DATABASE_URL` in your environment.
        """,
        "src/__init__.py": "",
        "src/app.py": """\
            def create_app():
                return {"name": "api"}
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.DOC_IMPL_DRIFT,
            file_path="README.md",
            should_detect=False,
            description="API endpoint paths in code blocks are not project directory references",
        ),
    ],
)


# -- GCD confounders --

GCD_CONFOUNDER_DISPATCH_TN = GroundTruthFixture(
    name="gcd_confounder_dispatch_tn",
    description="Module with @validate + isinstance guards — guard clauses handled externally",
    kind=FixtureKind.CONFOUNDER,
    files={
        "views/__init__.py": "",
        "views/handlers.py": """\
            def validate(func):
                return func

            @validate
            def dispatch_request(request, action, context):
                assert isinstance(request, dict)
                if action == "create":
                    name = context.get("name", "")
                    category = context.get("category", "default")
                    tags = context.get("tags", [])
                    return {"status": "created", "name": name,
                            "category": category, "tags": tags}
                elif action == "update":
                    item_id = context.get("id")
                    fields = context.get("fields", {})
                    merged = {**fields, "updated": True}
                    return {"status": "updated", "id": item_id, "data": merged}
                elif action == "delete":
                    item_id = context.get("id")
                    return {"status": "deleted", "id": item_id}
                return {"status": "unknown"}

            @validate
            def dispatch_event(event, payload, options):
                assert isinstance(event, str)
                if event == "user.created":
                    email = payload.get("email", "")
                    name = payload.get("name", "")
                    if options.get("notify"):
                        return {"sent_to": email, "name": name}
                    return {"queued": email}
                elif event == "user.deleted":
                    user_id = payload.get("id")
                    reason = payload.get("reason", "none")
                    return {"removed": user_id, "reason": reason}
                return {"ignored": event}

            @validate
            def dispatch_notification(channel, recipient, message):
                assert isinstance(channel, str)
                if channel == "email":
                    subject = message.get("subject", "")
                    body = message.get("body", "")
                    return {"type": "email", "to": recipient, "subject": subject}
                elif channel == "sms":
                    text = message.get("text", "")[:160]
                    return {"type": "sms", "to": recipient, "text": text}
                elif channel == "push":
                    title = message.get("title", "")
                    return {"type": "push", "to": recipient, "title": title}
                return {"type": "unknown", "channel": channel}
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.GUARD_CLAUSE_DEFICIT,
            file_path="views/",
            should_detect=False,
            description="@validate decorator + assert guards — external + inline guarding",
        ),
    ],
)

GCD_CONFOUNDER_FUNCTIONAL_TN = GroundTruthFixture(
    name="gcd_confounder_functional_tn",
    description="Module using comprehensions/map instead of guard clauses — functional style",
    kind=FixtureKind.CONFOUNDER,
    files={
        "transforms/__init__.py": "",
        "transforms/pipeline.py": """\
            def transform_records(records, columns, filters):
                filtered = [r for r in records if all(
                    r.get(k) == v for k, v in filters.items()
                )]
                projected = [
                    {c: r.get(c) for c in columns}
                    for r in filtered
                ]
                return projected

            def aggregate_data(rows, group_key, value_key):
                groups = {}
                for row in rows:
                    key = row.get(group_key, "unknown")
                    val = row.get(value_key, 0)
                    if key not in groups:
                        groups[key] = []
                    groups[key].append(val)
                return {k: sum(v) / len(v) for k, v in groups.items() if v}

            def enrich_entries(entries, lookup, join_field):
                result = []
                for entry in entries:
                    join_val = entry.get(join_field)
                    extra = lookup.get(join_val, {})
                    merged = {**entry, **extra}
                    if merged.get("active"):
                        result.append(merged)
                return result
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.GUARD_CLAUSE_DEFICIT,
            file_path="transforms/",
            should_detect=False,
            description="Functional-style code — comprehensions/map replace guard clauses",
        ),
    ],
)

GCD_CONFOUNDER_SHORT_TN = GroundTruthFixture(
    name="gcd_confounder_short_tn",
    description="Module with short functions (< 5 LOC) — guard clauses unnecessary",
    kind=FixtureKind.CONFOUNDER,
    files={
        "helpers/__init__.py": "",
        "helpers/converters.py": """\
            def to_upper(text, encoding, locale):
                return text.upper()

            def to_lower(text, encoding, locale):
                return text.lower()

            def to_title(text, encoding, locale):
                return text.title()

            def strip_ws(text, encoding, locale):
                return text.strip()
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.GUARD_CLAUSE_DEFICIT,
            file_path="helpers/",
            should_detect=False,
            description="Functions too short/simple — complexity below threshold",
        ),
    ],
)


# -- BAT confounders --

BAT_CONFOUNDER_FEATURE_TOGGLE_TN = GroundTruthFixture(
    name="bat_confounder_feature_toggle_tn",
    description="Production file with feature toggles and inline comments — not BAT",
    kind=FixtureKind.CONFOUNDER,
    files={
        "config/__init__.py": "",
        "config/features.py": (
            "# Feature toggle configuration\n"
            "# This module manages runtime feature flags\n"
            "\n"
            "FEATURE_NEW_UI = True  # Enable new UI components\n"
            "FEATURE_DARK_MODE = False  # Dark mode is experimental\n"
            "FEATURE_BETA_API = True  # Beta API for early adopters\n"
            "\n"
            + "\n".join([f"SETTING_{i} = {i}  # Configuration value {i}" for i in range(45)])
            + "\n"
        ),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.BYPASS_ACCUMULATION,
            file_path="config/features.py",
            should_detect=False,
            description="Regular comments (# Enable...) are not bypass markers",
        ),
    ],
)

BAT_CONFOUNDER_TYPE_STUB_TN = GroundTruthFixture(
    name="bat_confounder_type_stub_tn",
    description="Type stub file (.pyi) with type: ignore — acceptable in stub files",
    kind=FixtureKind.CONFOUNDER,
    files={
        "stubs/__init__.py": "",
        "stubs/config.py": (
            "# Configuration module\n"
            + "\n".join(
                [
                    f"def get_setting_{i}(key: str) -> str:\n    return str(key) + '_{i}'"
                    for i in range(30)
                ]
            )
            + "\n"
        ),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.BYPASS_ACCUMULATION,
            file_path="stubs/config.py",
            should_detect=False,
            description="Clean module with no bypass markers — below density threshold",
        ),
    ],
)

BAT_CONFOUNDER_NOQA_CONFIG_TN = GroundTruthFixture(
    name="bat_confounder_noqa_config_tn",
    description="Build/config file with noqa comments below threshold — NOT bypass accumulation",
    kind=FixtureKind.CONFOUNDER,
    files={
        "project/__init__.py": "",
        "project/setup_config.py": (
            "# Project setup configuration\n"
            + "\n".join([f"OPTION_{i} = {i}" for i in range(50)])
            + "\nLONG_LINE = 'this is a very long configuration string'  # noqa: E501\n"
        ),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.BYPASS_ACCUMULATION,
            file_path="project/setup_config.py",
            should_detect=False,
            description="Single noqa in 50+ LOC file — density well below 5% threshold",
        ),
    ],
)


# -- BAT boundary (bat_density_threshold = 0.05, bat_min_loc = 50) --

BAT_BOUNDARY_TP = GroundTruthFixture(
    name="bat_boundary_tp",
    description="File with exactly 50 LOC and ~5% bypass density → at threshold, should fire BAT",
    kind=FixtureKind.BOUNDARY,
    files={
        "legacy/__init__.py": "",
        "legacy/edge.py": (
            "# Legacy edge-case module\n"
            + "\n".join([f"val_{i} = {i}" for i in range(45)])
            + "\n"
            + "x = 1  # type: ignore\n"
            + "y = 2  # noqa\n"
            + "z = 3  # type: ignore\n"
        ),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.BYPASS_ACCUMULATION,
            file_path="legacy/edge.py",
            should_detect=True,
            description="50 LOC with ~5% bypass density — at threshold",
        ),
    ],
)


# ── MDS: PEP 562 lazy __getattr__ false-positive mitigation (RISK-SIG-2026-04-05-144) ──

MDS_TN_PACKAGE_LAZY_GETATTR = GroundTruthFixture(
    name="mds_tn_package_lazy_getattr",
    description=(
        "Identical __getattr__ in two __init__.py files (PEP 562 lazy loading) "
        "→ should NOT fire MDS"
    ),
    kind=FixtureKind.CONFOUNDER,
    files={
        "pkg_a/__init__.py": """\
            def __getattr__(name):
                import importlib
                mod = importlib.import_module(f".{name}", __name__)
                globals()[name] = mod
                return mod
        """,
        "pkg_b/__init__.py": """\
            def __getattr__(name):
                import importlib
                mod = importlib.import_module(f".{name}", __name__)
                globals()[name] = mod
                return mod
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.MUTANT_DUPLICATE,
            file_path="pkg_a/__init__.py",
            should_detect=False,
            description=(
                "PEP 562 lazy __getattr__ in __init__.py must not be flagged as duplicate"
            ),
        ),
    ],
)


# ── TPD: Inline negative assertions false-negative mitigation (RISK-SIG-2026-04-05-143) ──

TPD_TN_NEGATIVE_ASSERT_INLINE = GroundTruthFixture(
    name="tpd_tn_negative_assert_inline",
    description=(
        "Test suite with 'assert not', 'assert ... is None', 'assert ... is False' "
        "→ should NOT fire TPD (inline negative assertions counted)"
    ),
    kind=FixtureKind.CONFOUNDER,
    files={
        "tests/__init__.py": "",
        "tests/test_service.py": """\
            def test_empty_result_is_none():
                result = lookup_user(999)
                assert result is None

            def test_disabled_flag_is_false():
                flag = get_feature_flag("beta")
                assert flag is False

            def test_empty_list_not_truthy():
                items = get_items_for_unknown_user()
                assert not items

            def test_valid_happy_path():
                result = lookup_user(1)
                assert result is not None

            def test_another_happy_path():
                result = lookup_user(2)
                assert result["id"] == 2

            def test_disabled_returns_empty():
                result = get_items_for_disabled_account()
                assert not result
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.TEST_POLARITY_DEFICIT,
            file_path="tests/",
            should_detect=False,
            description=(
                "assert is None / is False / not ... count as negative assertions "
                "→ balanced polarity, no TPD expected"
            ),
        ),
    ],
)


# ── MAZ: CLI-serving path TN (RISK-SIG-2026-04-05-167) ──────────────────────────────────

MAZ_TN_CLI_SERVING_PATH = GroundTruthFixture(
    name="maz_tn_cli_serving_path",
    description=(
        "CLI-serving path handlers for localhost development tooling "
        "→ should NOT fire MISSING_AUTHORIZATION"
    ),
    kind=FixtureKind.CONFOUNDER,
    files={
        "cli/__init__.py": "",
        "cli/serving/__init__.py": "",
        "cli/serving/server.py": """\
            from http.server import BaseHTTPRequestHandler

            class LocalServingHandler(BaseHTTPRequestHandler):
                def do_GET(self):
                    if self.path == "/load_model":
                        self._send_json({"status": "ok"})
                    elif self.path == "/list_models":
                        self._send_json({"models": []})
                    elif self.path == "/generate":
                        self._send_json({"output": ""})
                    elif self.path == "/chat_completions":
                        self._send_json({"choices": []})
                    else:
                        self.send_response(404)

                def _send_json(self, data):
                    self.send_response(200)
                    self.end_headers()
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.MISSING_AUTHORIZATION,
            file_path="cli/serving/server.py",
            should_detect=False,
            description=(
                "CLI-local serving handlers are localhost-only dev tooling "
                "→ missing auth is intentional, not a production gap"
            ),
        ),
    ],
)


# ── HSC: ML tokenizer constants TN (RISK-SIG-2026-04-05-166) ────────────────────────────

HSC_TN_ML_TOKENIZER_CONSTANTS = GroundTruthFixture(
    name="hsc_tn_ml_tokenizer_constants",
    description=(
        "NLP tokenizer configuration constants (pad_token, cls_token, etc.) "
        "→ should NOT fire HARDCODED_SECRET"
    ),
    kind=FixtureKind.CONFOUNDER,
    files={
        "tokenization/__init__.py": "",
        "tokenization/tokenizer_config.py": """\
            PAD_TOKEN = "[PAD]"
            CLS_TOKEN = "[CLS]"
            SEP_TOKEN = "[SEP]"
            MASK_TOKEN = "[MASK]"
            UNK_TOKEN = "[UNK]"

            pad_token_id: int = 0
            cls_token_id: int = 101
            sep_token_id: int = 102
            mask_token_id: int = 103

            tokenizer_class_name: str = "BertTokenizer"
            chat_template: str = (
                "{% for message in messages %}{{ message['content'] }}{% endfor %}"
            )
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.HARDCODED_SECRET,
            file_path="tokenization/tokenizer_config.py",
            should_detect=False,
            description=(
                "NLP tokenizer constants ([PAD], [CLS] etc.) are NLP metadata, "
                "not credentials → HSC must not fire"
            ),
        ),
    ],
)


# ── NBV: try_* comparison-semantics TN (RISK-SIG-2026-04-05-165) ────────────────────────

NBV_TN_TRY_COMPARISON_HELPER = GroundTruthFixture(
    name="nbv_tn_try_comparison_helper",
    description=(
        "try_* helper functions with comparison/check semantics "
        "→ should NOT fire NBV (attempt-semantics suppression)"
    ),
    kind=FixtureKind.CONFOUNDER,
    files={
        "utils/__init__.py": "",
        "utils/comparison_helpers.py": """\
            def try_neq_default(val, default):
                return val is not None and val != default

            def try_eq_empty(container):
                return len(container) == 0 if container is not None else True

            def try_gt_zero(value):
                return isinstance(value, (int, float)) and value > 0

            def try_is_valid_key(key, mapping):
                return key is not None and key in mapping
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.NAMING_CONTRACT_VIOLATION,
            file_path="utils/comparison_helpers.py",
            should_detect=False,
            description=(
                "try_* functions with comparison body (is None, ==, isinstance) "
                "use attempt-semantics → NBV suppression must apply"
            ),
        ),
    ],
)


# ── New confounders + boundary/negative fixtures (drift precision infrastructure) ─────


NBV_REPOSITORY_PATTERN_TN = GroundTruthFixture(
    name="nbv_repository_pattern_tn",
    description="get_user() → Optional[User] in Repository class — naming OK, should NOT fire NBV",
    kind=FixtureKind.CONFOUNDER,
    files={
        "repos/__init__.py": "",
        "repos/user_repo.py": """\
            from typing import Optional

            class UserRepository:
                def get_user(self, user_id: int) -> Optional[dict]:
                    \"\"\"Fetch a user by ID, return None if not found.\"\"\"
                    if user_id <= 0:
                        return None
                    return {"id": user_id, "name": "Alice"}

                def get_user_by_email(self, email: str) -> Optional[dict]:
                    if "@" not in email:
                        return None
                    return {"email": email, "name": "Bob"}
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.NAMING_CONTRACT_VIOLATION,
            file_path="repos/user_repo.py",
            should_detect=False,
            description=("get_user returns Optional — repository pattern, not a naming violation"),
        ),
    ],
)


TVS_NEW_FILE_TN = GroundTruthFixture(
    name="tvs_new_file_tn",
    description="Brand-new file with zero commit history among stable peers → NOT an outlier",
    kind=FixtureKind.CONFOUNDER,
    files={
        "app/__init__.py": "",
        "app/stable_a.py": """\
            def func_a():
                return 1
        """,
        "app/stable_b.py": """\
            def func_b():
                return 2
        """,
        "app/stable_c.py": """\
            def func_c():
                return 3
        """,
        "app/stable_d.py": """\
            def func_d():
                return 4
        """,
        "app/brand_new.py": """\
            def new_func():
                return "hello"
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.TEMPORAL_VOLATILITY,
            file_path="app/brand_new.py",
            should_detect=False,
            description="Brand-new file with 0 commits — not a churn outlier",
        ),
    ],
    file_history_overrides={
        "app/brand_new.py": FileHistoryOverride(
            total_commits=0,
            unique_authors=0,
            change_frequency_30d=0.0,
            defect_correlated_commits=0,
        ),
    },
)


EDS_PROPERTY_TN = GroundTruthFixture(
    name="eds_property_tn",
    description="@property without docstring in a class that has a class docstring → NOT EDS",
    kind=FixtureKind.CONFOUNDER,
    files={
        "domain/__init__.py": "",
        "domain/account.py": """\
            class Account:
                \"\"\"Represents a user account with balance tracking.\"\"\"

                def __init__(self, owner: str, balance: float = 0.0):
                    self._owner = owner
                    self._balance = balance
                    self._transactions: list = []

                @property
                def owner(self):
                    return self._owner

                @property
                def balance(self):
                    return self._balance

                @property
                def transaction_count(self):
                    return len(self._transactions)

                def deposit(self, amount: float) -> None:
                    \"\"\"Add funds to the account.\"\"\"
                    if amount <= 0:
                        raise ValueError("Deposit must be positive")
                    self._balance += amount
                    self._transactions.append(("deposit", amount))
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.EXPLAINABILITY_DEFICIT,
            file_path="domain/account.py",
            should_detect=False,
            description="@property methods without docstrings — class docstring suffices",
        ),
    ],
)


DIA_INLINE_CODE_TN = GroundTruthFixture(
    name="dia_inline_code_tn",
    description="README with directory-like paths only inside fenced code blocks → NOT DIA",
    kind=FixtureKind.CONFOUNDER,
    files={
        "README.md": """\
            # MyProject

            ## Usage

            ```bash
            curl http://localhost:8000/api/users/
            curl http://localhost:8000/api/orders/
            ls migrations/
            ```

            ## Installation

            Run `pip install myproject` to get started.
        """,
        "src/__init__.py": "",
        "src/app.py": """\
            def create_app():
                return {"name": "myproject"}
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.DOC_IMPL_DRIFT,
            file_path="README.md",
            should_detect=False,
            description="Directory-like paths inside code blocks — not real dir references",
        ),
    ],
)


AVS_TEST_MOCK_TN = GroundTruthFixture(
    name="avs_test_mock_tn",
    description="Test file imports from higher layer for mocking → should NOT fire AVS",
    kind=FixtureKind.CONFOUNDER,
    files={
        "api/__init__.py": "",
        "api/views.py": """\
            from services.user_service import get_user

            def user_detail(user_id):
                return get_user(user_id)
        """,
        "services/__init__.py": "",
        "services/user_service.py": """\
            def get_user(user_id):
                return {"id": user_id}
        """,
        "tests/__init__.py": "",
        "tests/test_views.py": """\
            from api.views import user_detail
            from services.user_service import get_user

            def test_user_detail():
                result = user_detail(1)
                assert result["id"] == 1
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.ARCHITECTURE_VIOLATION,
            file_path="tests/test_views.py",
            should_detect=False,
            description="Test files importing across layers for mocking — not a violation",
        ),
    ],
)


MDS_BOUNDARY_TN = GroundTruthFixture(
    name="mds_boundary_tn",
    description="Same control-flow skeleton but different semantics → NOT a duplicate",
    kind=FixtureKind.BOUNDARY,
    files={
        "utils/__init__.py": "",
        "utils/validator.py": """\
            def validate_email(value: str) -> bool:
                if not value:
                    return False
                if "@" not in value:
                    return False
                parts = value.split("@")
                if len(parts) != 2:
                    return False
                return len(parts[1]) > 2

            def validate_phone(value: str) -> bool:
                if not value:
                    return False
                if not value.startswith("+"):
                    return False
                digits = value[1:]
                if len(digits) < 7:
                    return False
                return digits.isdigit()
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.MUTANT_DUPLICATE,
            file_path="utils/validator.py",
            should_detect=False,
            description=(
                "Same if-return-if-return skeleton but email vs phone — "
                "different semantics, not a mutant duplicate"
            ),
        ),
    ],
)


NBV_BOUNDARY_TN = GroundTruthFixture(
    name="nbv_boundary_tn",
    description="validate_* returning False for invalid input — contract met via return",
    kind=FixtureKind.BOUNDARY,
    files={
        "core/__init__.py": "",
        "core/checks.py": """\
            def validate_age(age: int) -> bool:
                \"\"\"Return False if age is out of range.\"\"\"
                if age < 0:
                    return False
                if age > 150:
                    return False
                return True

            def validate_name(name: str) -> bool:
                \"\"\"Return False if name is empty or too long.\"\"\"
                if not name or not name.strip():
                    return False
                if len(name) > 200:
                    return False
                return True
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.NAMING_CONTRACT_VIOLATION,
            file_path="core/checks.py",
            should_detect=False,
            description="validate_* with return False on invalid input — contract satisfied",
        ),
    ],
)


EDS_INIT_MEDIUM_TN = GroundTruthFixture(
    name="eds_init_medium_tn",
    description="__init__ with 3-4 params, CC≈4, no docstring → NOT EDS (__init__ suppressed)",
    kind=FixtureKind.NEGATIVE,
    files={
        "services/__init__.py": "",
        "services/connection.py": """\
            class ConnectionPool:
                def __init__(self, host, port, max_connections=10, timeout=30):
                    self.host = host
                    self.port = port
                    self.max_connections = max_connections
                    self.timeout = timeout
                    self._pool = []
                    if max_connections <= 0:
                        raise ValueError("max_connections must be positive")
                    if timeout <= 0:
                        raise ValueError("timeout must be positive")
                    for _ in range(min(3, max_connections)):
                        self._pool.append(self._create_conn())

                def _create_conn(self):
                    return {"host": self.host, "port": self.port}
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.EXPLAINABILITY_DEFICIT,
            file_path="services/connection.py",
            should_detect=False,
            description="__init__ with moderate complexity but no docstring — EDS suppressed",
        ),
    ],
)


# ── Cohesion Deficit (COD) boundary TN — threshold edge ──

COD_BOUNDARY_TN = GroundTruthFixture(
    name="cod_boundary_tn",
    description="File with exactly 4 functions all sharing 'config' domain → cohesive, no fire",
    kind=FixtureKind.BOUNDARY,
    files={
        "settings/__init__.py": "",
        "settings/config_loader.py": """\
            def load_config(path: str) -> dict:
                with open(path) as f:
                    return eval(f.read())

            def validate_config(config: dict) -> bool:
                required = {"host", "port", "debug"}
                return required.issubset(config.keys())

            def merge_config(base: dict, override: dict) -> dict:
                merged = dict(base)
                merged.update(override)
                return merged

            def serialize_config(config: dict) -> str:
                return str(config)
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.COHESION_DEFICIT,
            file_path="settings/config_loader.py",
            should_detect=False,
            description="4 func at min_units threshold, all config-related — cohesive",
        ),
    ],
)


# ── Co-Change Coupling (CCC) ─────────────────────────────────────────────

CCC_TRUE_POSITIVE = GroundTruthFixture(
    name="ccc_tp",
    description="Two unrelated files that co-change repeatedly without imports → should fire CCC",
    files={
        "billing/__init__.py": "",
        "billing/invoice.py": """\
            def create_invoice(customer_id: int, amount: float) -> dict:
                return {"customer": customer_id, "amount": amount}

            def format_invoice(invoice: dict) -> str:
                return f"Invoice: ${invoice['amount']}"
        """,
        "notifications/__init__.py": "",
        "notifications/email.py": """\
            def send_email(recipient: str, subject: str, body: str) -> bool:
                print(f"To: {recipient}, Subject: {subject}")
                return True

            def format_email_body(template: str, data: dict) -> str:
                return template.format(**data)
        """,
    },
    commits=[
        CommitInfo(
            hash=f"abc{i:04d}",
            author="dev",
            email="dev@example.com",
            timestamp=_dt.datetime(2026, 1, 1 + i, tzinfo=_dt.UTC),
            message=f"feat: update billing and notifications #{i}",
            files_changed=["billing/invoice.py", "notifications/email.py"],
        )
        for i in range(12)
    ],
    expected=[
        ExpectedFinding(
            signal_type=SignalType.CO_CHANGE_COUPLING,
            file_path="billing/invoice.py",
            should_detect=True,
            description="Hidden co-change coupling between billing and notifications",
        ),
    ],
)

CCC_TRUE_NEGATIVE = GroundTruthFixture(
    name="ccc_tn",
    description="Two files that co-change but have explicit imports → should NOT fire CCC",
    files={
        "core/__init__.py": "",
        "core/models.py": """\
            class User:
                def __init__(self, name: str, email: str):
                    self.name = name
                    self.email = email
        """,
        "core/serializers.py": """\
            from core.models import User

            def serialize_user(user) -> dict:
                return {"name": user.name, "email": user.email}
        """,
    },
    commits=[
        CommitInfo(
            hash=f"def{i:04d}",
            author="dev",
            email="dev@example.com",
            timestamp=_dt.datetime(2026, 2, 1 + i, tzinfo=_dt.UTC),
            message=f"fix: update models and serializers #{i}",
            files_changed=["core/models.py", "core/serializers.py"],
        )
        for i in range(12)
    ],
    expected=[
        ExpectedFinding(
            signal_type=SignalType.CO_CHANGE_COUPLING,
            file_path="core/models.py",
            should_detect=False,
            description="Co-change pair has explicit import dependency — not hidden coupling",
        ),
    ],
)

CCC_CONFOUNDER_TN = GroundTruthFixture(
    name="ccc_confounder_few_commits_tn",
    description="Two unrelated files but too few commits → should NOT fire CCC",
    kind=FixtureKind.CONFOUNDER,
    files={
        "a/__init__.py": "",
        "a/foo.py": """\
            def foo():
                return 1
        """,
        "b/__init__.py": "",
        "b/bar.py": """\
            def bar():
                return 2
        """,
    },
    commits=[
        CommitInfo(
            hash=f"few{i:04d}",
            author="dev",
            email="dev@example.com",
            timestamp=_dt.datetime(2026, 3, 1 + i, tzinfo=_dt.UTC),
            message=f"chore: minor tweak #{i}",
            files_changed=["a/foo.py", "b/bar.py"],
        )
        for i in range(3)
    ],
    expected=[
        ExpectedFinding(
            signal_type=SignalType.CO_CHANGE_COUPLING,
            file_path="a/foo.py",
            should_detect=False,
            description="Below minimum history threshold — too few commits to identify coupling",
        ),
    ],
)

CCC_BOUNDARY_TP = GroundTruthFixture(
    name="ccc_boundary_min_commits_tp",
    description="Co-change pair with exactly 8 commits (minimum threshold) → should fire CCC",
    kind=FixtureKind.BOUNDARY,
    files={
        "inventory/__init__.py": "",
        "inventory/stock.py": """\
            def update_stock(item_id: int, delta: int) -> dict:
                return {"item": item_id, "change": delta}

            def get_stock_level(item_id: int) -> int:
                return 100
        """,
        "shipping/__init__.py": "",
        "shipping/dispatch.py": """\
            def schedule_delivery(order_id: int, address: str) -> dict:
                return {"order": order_id, "address": address}

            def cancel_delivery(order_id: int) -> bool:
                return True
        """,
    },
    commits=[
        CommitInfo(
            hash=f"bnd{i:04d}",
            author="dev",
            email="dev@example.com",
            timestamp=_dt.datetime(2026, 4, 1 + i, tzinfo=_dt.UTC),
            message=f"feat: sync stock and shipping #{i}",
            files_changed=["inventory/stock.py", "shipping/dispatch.py"],
        )
        for i in range(8)
    ],
    expected=[
        ExpectedFinding(
            signal_type=SignalType.CO_CHANGE_COUPLING,
            file_path="inventory/stock.py",
            should_detect=True,
            description=(
                "At minimum 8-commit threshold — hidden coupling between inventory and shipping"
            ),
        ),
    ],
)

CCC_LARGE_COMMIT_TN = GroundTruthFixture(
    name="ccc_large_commit_tn",
    description="Files co-change in bulk commits (>20 files each) → should NOT fire CCC",
    kind=FixtureKind.CONFOUNDER,
    files={
        "pkg/__init__.py": "",
        "pkg/alpha.py": """\
            def alpha():
                return "a"
        """,
        "pkg/beta.py": """\
            def beta():
                return "b"
        """,
        **{f"pkg/mod_{j}.py": f"VAL = {j}\n" for j in range(25)},
    },
    commits=[
        CommitInfo(
            hash=f"bulk{i:04d}",
            author="dev",
            email="dev@example.com",
            timestamp=_dt.datetime(2026, 5, 1 + i, tzinfo=_dt.UTC),
            message=f"chore: bulk refactor #{i}",
            files_changed=["pkg/alpha.py", "pkg/beta.py"] + [f"pkg/mod_{j}.py" for j in range(25)],
        )
        for i in range(12)
    ],
    expected=[
        ExpectedFinding(
            signal_type=SignalType.CO_CHANGE_COUPLING,
            file_path="pkg/alpha.py",
            should_detect=False,
            description="Large commits (>20 known files) are filtered out — no coupling signal",
        ),
    ],
)


# ── Exception Contract Drift (ECM) ────────────────────────────────────────
# ECM requires actual git history (git show HEAD~N). Fixtures with
# old_sources create a 2-commit git repo so HEAD~1 provides the prior
# exception profile.

ECM_TRUE_NEGATIVE = GroundTruthFixture(
    name="ecm_tn_stable_contract",
    description="Stable function with documented exceptions → should NOT fire ECM (no git)",
    kind=FixtureKind.NEGATIVE,
    files={
        "services/__init__.py": "",
        "services/payment.py": """\
            class PaymentError(Exception):
                pass

            class InsufficientFundsError(PaymentError):
                pass

            def process_payment(amount: float, card_token: str) -> dict:
                \"\"\"Process a payment.

                Raises:
                    InsufficientFundsError: If the balance is too low.
                    PaymentError: For other payment failures.
                \"\"\"
                if amount <= 0:
                    raise PaymentError("Amount must be positive")
                if not card_token:
                    raise PaymentError("Card token required")
                return {"status": "ok", "amount": amount}
        """,
    },
    file_history_overrides={
        "services/payment.py": FileHistoryOverride(total_commits=20),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.EXCEPTION_CONTRACT_DRIFT,
            file_path="services/payment.py",
            should_detect=False,
            description="Stable exception contract with documented raises — no git diff available",
        ),
    ],
)

ECM_TRUE_POSITIVE = GroundTruthFixture(
    name="ecm_tp_contract_changed",
    description="Function whose exception contract changed between commits → should fire ECM",
    kind=FixtureKind.POSITIVE,
    files={
        "orders/__init__.py": "",
        "orders/processing.py": """\
            def process_order(order_id: int, items: list) -> dict:
                \"\"\"Process an order.\"\"\"
                result = {"id": order_id, "items": items}
                if order_id <= 0:
                    result["error"] = "invalid"
                    return result
                result["status"] = "processed"
                return result
        """,
    },
    old_sources={
        "orders/__init__.py": "",
        "orders/processing.py": """\
            def process_order(order_id: int, items: list) -> dict:
                \"\"\"Process an order.

                Raises:
                    ValueError: If order_id is invalid.
                    RuntimeError: If processing fails.
                \"\"\"
                if order_id <= 0:
                    raise ValueError("Invalid order ID")
                if not items:
                    raise RuntimeError("Empty order")
                return {"id": order_id, "items": items, "status": "processed"}
        """,
    },
    file_history_overrides={
        "orders/processing.py": FileHistoryOverride(total_commits=15),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.EXCEPTION_CONTRACT_DRIFT,
            file_path="orders/processing.py",
            should_detect=True,
            description="Raises removed between commits — exception contract silently changed",
        ),
    ],
)

ECM_CONFOUNDER_TN = GroundTruthFixture(
    name="ecm_confounder_refactored_body_tn",
    description="Function body refactored but exception profile unchanged → should NOT fire ECM",
    kind=FixtureKind.CONFOUNDER,
    files={
        "auth/__init__.py": "",
        "auth/login.py": """\
            class AuthError(Exception):
                pass

            def authenticate(username: str, password: str) -> dict:
                \"\"\"Authenticate a user.\"\"\"
                credentials = {"user": username, "pass": password}
                if not credentials["user"]:
                    raise AuthError("Username required")
                if not credentials["pass"]:
                    raise AuthError("Password required")
                # Refactored: uses dict-based credential check
                return {"user": credentials["user"], "status": "ok"}
        """,
    },
    old_sources={
        "auth/__init__.py": "",
        "auth/login.py": """\
            class AuthError(Exception):
                pass

            def authenticate(username: str, password: str) -> dict:
                \"\"\"Authenticate a user.\"\"\"
                if not username:
                    raise AuthError("Username required")
                if not password:
                    raise AuthError("Password required")
                return {"user": username, "status": "ok"}
        """,
    },
    file_history_overrides={
        "auth/login.py": FileHistoryOverride(total_commits=12),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.EXCEPTION_CONTRACT_DRIFT,
            file_path="auth/login.py",
            should_detect=False,
            description=(
                "Same raises (AuthError) in both versions — body change, contract unchanged"
            ),
        ),
    ],
)


# ── Phantom Reference (PHR) ──────────────────────────────────────────────

PHR_TRUE_POSITIVE = GroundTruthFixture(
    name="phr_tp",
    description="Function calls hallucinated helper that does not exist anywhere → should fire PHR",
    files={
        "services/__init__.py": "",
        "services/auth.py": textwrap.dedent("""\
            from services.utils import hash_password

            def authenticate(username: str, password: str) -> bool:
                hashed = hash_password(password)
                token = sanitize_input(username)
                validated = validate_token(token)
                return validated is not None
        """),
        "services/utils.py": textwrap.dedent("""\
            import hashlib

            def hash_password(password: str) -> str:
                return hashlib.sha256(password.encode()).hexdigest()
        """),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.PHANTOM_REFERENCE,
            file_path="services/auth.py",
            should_detect=True,
            description=(
                "sanitize_input and validate_token are called but never defined or imported"
            ),
        ),
    ],
)

PHR_TRUE_NEGATIVE = GroundTruthFixture(
    name="phr_tn",
    description="All references properly imported/defined → should NOT fire PHR",
    files={
        "core/__init__.py": "",
        "core/helpers.py": textwrap.dedent("""\
            def clean_input(value: str) -> str:
                return value.strip().lower()

            def format_output(data: dict) -> str:
                return str(data)
        """),
        "core/main.py": textwrap.dedent("""\
            from core.helpers import clean_input, format_output

            def process(raw: str) -> str:
                cleaned = clean_input(raw)
                result = {"value": cleaned}
                return format_output(result)
        """),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.PHANTOM_REFERENCE,
            file_path="core/main.py",
            should_detect=False,
            description="All names resolve — no phantoms expected",
        ),
    ],
)

PHR_STAR_IMPORT_TN = GroundTruthFixture(
    name="phr_star_import_tn",
    kind=FixtureKind.CONFOUNDER,
    description=(
        "Star import means we cannot verify names → should NOT fire PHR (conservative skip)"
    ),
    files={
        "lib/__init__.py": textwrap.dedent("""\
            def secret_helper():
                pass
        """),
        "lib/consumer.py": textwrap.dedent("""\
            from lib import *

            def run():
                result = secret_helper()
                return result
        """),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.PHANTOM_REFERENCE,
            file_path="lib/consumer.py",
            should_detect=False,
            description="Star import → conservatively skip file",
        ),
    ],
)

PHR_BUILTIN_TN = GroundTruthFixture(
    name="phr_builtin_tn",
    description="Only builtins used → should NOT fire PHR",
    files={
        "utils/__init__.py": "",
        "utils/basics.py": textwrap.dedent("""\
            def summarize(items):
                count = len(items)
                total = sum(items)
                types = set(type(i).__name__ for i in items)
                output = dict(count=count, total=total, types=sorted(types))
                return str(output)
        """),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.PHANTOM_REFERENCE,
            file_path="utils/basics.py",
            should_detect=False,
            description="All names are builtins — no phantoms",
        ),
    ],
)

PHR_CROSS_FILE_TP = GroundTruthFixture(
    name="phr_cross_file_tp",
    kind=FixtureKind.POSITIVE,
    description="Imports module but calls function that does not exist in it → should fire PHR",
    files={
        "app/__init__.py": "",
        "app/models.py": textwrap.dedent("""\
            class User:
                def __init__(self, name: str):
                    self.name = name
        """),
        "app/views.py": textwrap.dedent("""\
            from app.models import User

            def get_dashboard(user_id: int):
                user = User("test")
                perms = check_permissions(user, "admin")
                data = build_dashboard_data(user, perms)
                return data
        """),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.PHANTOM_REFERENCE,
            file_path="app/views.py",
            should_detect=True,
            description="check_permissions and build_dashboard_data are never defined or imported",
        ),
    ],
)

PHR_DYNAMIC_GETATTR_TN = GroundTruthFixture(
    name="phr_dynamic_tn",
    kind=FixtureKind.CONFOUNDER,
    description="Module has __getattr__ → dynamic namespace, skip → should NOT fire PHR",
    files={
        "plugins/__init__.py": "",
        "plugins/loader.py": textwrap.dedent("""\
            _registry = {}

            def __getattr__(name):
                if name in _registry:
                    return _registry[name]
                raise AttributeError(name)

            def load_all():
                result = process_plugins()
                return result
        """),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.PHANTOM_REFERENCE,
            file_path="plugins/loader.py",
            should_detect=False,
            description="Module __getattr__ → dynamic namespace, conservatively skip",
        ),
    ],
)

PHR_COMPREHENSION_TN = GroundTruthFixture(
    name="phr_comprehension_tn",
    kind=FixtureKind.CONFOUNDER,
    description="Comprehension/genexpr iteration variables must not be flagged as phantom",
    files={
        "app/__init__.py": "",
        "app/transform.py": textwrap.dedent("""\
            def process(items):
                upper = [item.strip().upper() for item in items if item.strip()]
                mapping = {k: v.lower() for k, v in zip(items, items)}
                total = sum(x.count("a") for x in items)
                return upper, mapping, total
        """),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.PHANTOM_REFERENCE,
            file_path="app/transform.py",
            should_detect=False,
            description="item/k/v/x are comprehension iteration vars, not phantom refs",
        ),
    ],
)

PHR_LAMBDA_PARAM_TN = GroundTruthFixture(
    name="phr_lambda_param_tn",
    kind=FixtureKind.CONFOUNDER,
    description="Lambda parameter names must not be flagged as phantom",
    files={
        "app/__init__.py": "",
        "app/sort.py": textwrap.dedent("""\
            data = [{"path": "a.txt"}, {"path": "b.txt"}]

            def sorted_data():
                return sorted(data, key=lambda item: str(item["path"]))
        """),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.PHANTOM_REFERENCE,
            file_path="app/sort.py",
            should_detect=False,
            description="item is a lambda parameter, not a phantom reference",
        ),
    ],
)

PHR_IMPORT_FROM_TP = GroundTruthFixture(
    name="phr_import_from_tp",
    kind=FixtureKind.POSITIVE,
    description="Importing a non-existent name from a project module → phantom import",
    files={
        "pkg/__init__.py": "",
        "pkg/helpers.py": textwrap.dedent("""\
            def actual_func():
                return 42
        """),
        "pkg/main.py": textwrap.dedent("""\
            from pkg.helpers import hallucinated_helper

            def run():
                return hallucinated_helper()
        """),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.PHANTOM_REFERENCE,
            file_path="pkg/main.py",
            should_detect=True,
            description="hallucinated_helper does not exist in pkg.helpers → phantom import",
        ),
    ],
)

PHR_DECORATOR_PHANTOM_TP = GroundTruthFixture(
    name="phr_decorator_tp",
    kind=FixtureKind.POSITIVE,
    description="Decorator referencing undefined name → should fire PHR",
    files={
        "webapp/__init__.py": "",
        "webapp/routes.py": textwrap.dedent("""\
            from webapp.models import User

            @require_auth
            @rate_limit(max_calls=100)
            def get_users():
                return User.query.all()
        """),
        "webapp/models.py": textwrap.dedent("""\
            class User:
                pass
        """),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.PHANTOM_REFERENCE,
            file_path="webapp/routes.py",
            should_detect=True,
            description=(
                "require_auth and rate_limit are never defined/imported - phantom decorators"
            ),
        ),
    ],
)

PHR_MULTI_PHANTOM_TP = GroundTruthFixture(
    name="phr_multi_phantom_tp",
    kind=FixtureKind.POSITIVE,
    description="File with many phantom calls → high score expected",
    files={
        "pipeline/__init__.py": "",
        "pipeline/process.py": textwrap.dedent("""\
            def run_pipeline(data):
                validated = validate_schema(data)
                normalized = normalize_encoding(validated)
                deduplicated = deduplicate_records(normalized)
                enriched = enrich_metadata(deduplicated)
                scored = calculate_risk_score(enriched)
                return scored
        """),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.PHANTOM_REFERENCE,
            file_path="pipeline/process.py",
            should_detect=True,
            description=(
                "5 hallucinated names: validate_schema, normalize_encoding, "
                "deduplicate_records, enrich_metadata, calculate_risk_score"
            ),
        ),
    ],
)

PHR_TYPE_CHECKING_TN = GroundTruthFixture(
    name="phr_type_checking_tn",
    kind=FixtureKind.CONFOUNDER,
    description="Names inside TYPE_CHECKING block should not fire PHR",
    files={
        "lib/__init__.py": "",
        "lib/service.py": textwrap.dedent("""\
            from __future__ import annotations
            import typing

            if typing.TYPE_CHECKING:
                from lib.models import DetailedReport, AuditTrail

            def get_summary() -> str:
                return "summary"
        """),
        "lib/models.py": textwrap.dedent("""\
            class DetailedReport:
                pass
        """),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.PHANTOM_REFERENCE,
            file_path="lib/service.py",
            should_detect=False,
            description="TYPE_CHECKING imports are excluded from phantom detection",
        ),
    ],
)

PHR_PRIVATE_NAME_BOUNDARY = GroundTruthFixture(
    name="phr_private_boundary",
    kind=FixtureKind.BOUNDARY,
    description="Private _names are skipped by design → boundary: should NOT fire",
    files={
        "core/__init__.py": "",
        "core/engine.py": textwrap.dedent("""\
            def run():
                result = _internal_helper("data")
                config = _load_defaults()
                return _format_result(result, config)
        """),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.PHANTOM_REFERENCE,
            file_path="core/engine.py",
            should_detect=False,
            description="_-prefixed names are intentionally excluded (low hallucination risk)",
        ),
    ],
)

PHR_SINGLE_CHAR_BOUNDARY = GroundTruthFixture(
    name="phr_single_char_boundary",
    kind=FixtureKind.BOUNDARY,
    description="Single-character names are skipped by design → boundary: should NOT fire",
    files={
        "math_utils/__init__.py": "",
        "math_utils/calc.py": textwrap.dedent("""\
            def compute(x, y, z):
                a = x + y
                b = y * z
                c = a + b
                return c
        """),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.PHANTOM_REFERENCE,
            file_path="math_utils/calc.py",
            should_detect=False,
            description=(
                "Single-char names (a, b, c) are skipped - too common for meaningful detection"
            ),
        ),
    ],
)

PHR_PARENT_REEXPORT_TN = GroundTruthFixture(
    name="phr_parent_reexport_tn",
    kind=FixtureKind.CONFOUNDER,
    description="Name re-exported by parent __init__.py → import-from should NOT fire",
    files={
        "mylib/__init__.py": textwrap.dedent("""\
            from mylib.core import Engine
        """),
        "mylib/core.py": textwrap.dedent("""\
            class Engine:
                def run(self):
                    return True
        """),
        "mylib/cli.py": textwrap.dedent("""\
            from mylib import Engine

            def main():
                engine = Engine()
                engine.run()
        """),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.PHANTOM_REFERENCE,
            file_path="mylib/cli.py",
            should_detect=False,
            description="Engine is re-exported by mylib/__init__.py — valid import",
        ),
    ],
)


# ---------------------------------------------------------------------------
# PHR third-party import resolver fixtures (ADR-040)
# ---------------------------------------------------------------------------

PHR_MISSING_PACKAGE_TP = GroundTruthFixture(
    name="phr_missing_package_tp",
    kind=FixtureKind.POSITIVE,
    description="Import of a nonexistent third-party package → should fire PHR",
    files={
        "app/__init__.py": "",
        "app/pipeline.py": textwrap.dedent("""\
            import nonexistent_ai_helper
            from nonexistent_ai_helper import transform_data

            def run(data):
                return nonexistent_ai_helper.process(transform_data(data))
        """),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.PHANTOM_REFERENCE,
            file_path="app/pipeline.py",
            should_detect=True,
            description=("nonexistent_ai_helper is not installed → phantom third-party import"),
        ),
    ],
)

PHR_OPTIONAL_DEP_TN = GroundTruthFixture(
    name="phr_optional_dep_tn",
    kind=FixtureKind.CONFOUNDER,
    description="try/except ImportError guarded import → should NOT fire PHR",
    files={
        "lib/__init__.py": "",
        "lib/compat.py": textwrap.dedent("""\
            try:
                import some_optional_accelerator
                HAS_ACCEL = True
            except ImportError:
                some_optional_accelerator = None
                HAS_ACCEL = False

            def process(data):
                if HAS_ACCEL:
                    return some_optional_accelerator.fast_process(data)
                return data
        """),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.PHANTOM_REFERENCE,
            file_path="lib/compat.py",
            should_detect=False,
            description="Import is guarded by try/except ImportError → conditional",
        ),
    ],
)

PHR_STDLIB_IMPORT_TN = GroundTruthFixture(
    name="phr_stdlib_import_tn",
    kind=FixtureKind.CONFOUNDER,
    description="Only stdlib imports → should NOT fire PHR",
    files={
        "tools/__init__.py": "",
        "tools/utils.py": textwrap.dedent("""\
            import json
            import os
            import sys
            from pathlib import Path
            from collections import defaultdict

            def get_config():
                config_path = Path(os.environ.get("CONFIG", "config.json"))
                with open(config_path) as fh:
                    data = json.load(fh)
                return defaultdict(str, data)
        """),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.PHANTOM_REFERENCE,
            file_path="tools/utils.py",
            should_detect=False,
            description="All imports are stdlib — no phantom references",
        ),
    ],
)

PHR_TYPE_CHECKING_THIRD_PARTY_TN = GroundTruthFixture(
    name="phr_type_checking_third_party_tn",
    kind=FixtureKind.BOUNDARY,
    description="Third-party import inside TYPE_CHECKING → should NOT fire PHR",
    files={
        "svc/__init__.py": "",
        "svc/handler.py": textwrap.dedent("""\
            from __future__ import annotations
            import typing

            if typing.TYPE_CHECKING:
                import nonexistent_type_stubs

            def handle(data: str) -> str:
                return data.upper()
        """),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.PHANTOM_REFERENCE,
            file_path="svc/handler.py",
            should_detect=False,
            description="TYPE_CHECKING imports excluded from third-party check",
        ),
    ],
)

PHR_MODULE_NOT_FOUND_ERROR_TN = GroundTruthFixture(
    name="phr_module_not_found_error_tn",
    kind=FixtureKind.CONFOUNDER,
    description="try/except ModuleNotFoundError guarded import → should NOT fire PHR",
    files={
        "ext/__init__.py": "",
        "ext/loader.py": textwrap.dedent("""\
            try:
                import ujson as json_impl
            except ModuleNotFoundError:
                import json as json_impl

            def parse(text):
                return json_impl.loads(text)
        """),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.PHANTOM_REFERENCE,
            file_path="ext/loader.py",
            should_detect=False,
            description="Import guarded by ModuleNotFoundError → conditional",
        ),
    ],
)


# ---------------------------------------------------------------------------
# PHR runtime attribute validation fixtures (ADR-041)
# ---------------------------------------------------------------------------

PHR_RUNTIME_MISSING_ATTR_TP = GroundTruthFixture(
    name="phr_runtime_missing_attr_tp",
    kind=FixtureKind.POSITIVE,
    description="from os import nonexistent_func → module exists, attribute doesn't → PHR",
    files={
        "svc/__init__.py": "",
        "svc/handler.py": textwrap.dedent("""\
            from os import nonexistent_func

            def run():
                return nonexistent_func()
        """),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.PHANTOM_REFERENCE,
            file_path="svc/handler.py",
            should_detect=True,
            description="os.nonexistent_func does not exist at runtime",
        ),
    ],
)

PHR_RUNTIME_VALID_ATTR_TN = GroundTruthFixture(
    name="phr_runtime_valid_attr_tn",
    kind=FixtureKind.CONFOUNDER,
    description="from os.path import join → exists at runtime → should NOT fire PHR",
    files={
        "svc/__init__.py": "",
        "svc/paths.py": textwrap.dedent("""\
            from os.path import join, exists

            def full_path(base, name):
                return join(base, name) if exists(base) else name
        """),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.PHANTOM_REFERENCE,
            file_path="svc/paths.py",
            should_detect=False,
            description="os.path.join and os.path.exists are real attributes",
        ),
    ],
)

PHR_RUNTIME_GUARDED_TN = GroundTruthFixture(
    name="phr_runtime_guarded_tn",
    kind=FixtureKind.CONFOUNDER,
    description="try: from os import nonexistent except ImportError → guarded → no PHR",
    files={
        "svc/__init__.py": "",
        "svc/compat.py": textwrap.dedent("""\
            try:
                from os import nonexistent_func
            except ImportError:
                def nonexistent_func():
                    return None

            def run():
                return nonexistent_func()
        """),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.PHANTOM_REFERENCE,
            file_path="svc/compat.py",
            should_detect=False,
            description="Import guarded by try/except ImportError → conditional",
        ),
    ],
)


# ---------------------------------------------------------------------------
# HSC scoring-promotion fixtures (ADR-040)
# ---------------------------------------------------------------------------

HSC_GITHUB_TOKEN_TP = GroundTruthFixture(
    name="hsc_github_token_tp",
    description="Hardcoded GitHub PAT token → should fire HSC",
    files={
        "deploy/__init__.py": "",
        "deploy/config.py": textwrap.dedent("""\
            GITHUB_TOKEN = "ghp_ABCDEFghijklmnopqrstuvwxyz0123456789"
            API_URL = "https://api.github.com"
        """),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.HARDCODED_SECRET,
            file_path="deploy/config.py",
            should_detect=True,
            description="ghp_ prefix is a high-confidence GitHub PAT token",
        ),
    ],
)

HSC_HIGH_ENTROPY_TP = GroundTruthFixture(
    name="hsc_high_entropy_tp",
    description="High-entropy string in secret-named variable → should fire HSC",
    files={
        "settings/__init__.py": "",
        "settings/secrets.py": textwrap.dedent("""\
            DB_PASSWORD = "xK9#mP2$vL5nQ8wR3jT6yU0iO4eA7sD1fG"
            APP_NAME = "myapp"
        """),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.HARDCODED_SECRET,
            file_path="settings/secrets.py",
            should_detect=True,
            description="Variable name matches secret pattern and value has high entropy",
        ),
    ],
)

HSC_ENV_READ_TN = GroundTruthFixture(
    name="hsc_env_read_tn",
    description="Secrets read from environment → should NOT fire HSC",
    kind=FixtureKind.CONFOUNDER,
    files={
        "config/__init__.py": "",
        "config/settings.py": textwrap.dedent("""\
            import os
            SECRET_KEY = os.environ["SECRET_KEY"]
            DB_PASSWORD = os.getenv("DB_PASSWORD", "")
            API_TOKEN = os.environ.get("API_TOKEN", None)
        """),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.HARDCODED_SECRET,
            file_path="config/settings.py",
            should_detect=False,
            description="All secrets sourced from os.environ/os.getenv → safe",
        ),
    ],
)

HSC_PLACEHOLDER_TN = GroundTruthFixture(
    name="hsc_placeholder_tn",
    description=(
        "Non-secret config values in file with secret-like variable names → should NOT fire HSC"
    ),
    kind=FixtureKind.CONFOUNDER,
    files={
        "config/__init__.py": "",
        "config/defaults.py": textwrap.dedent("""\
            DB_HOST = "localhost"
            DB_PORT = "5432"
            API_TIMEOUT = "30"
            LOG_LEVEL = "DEBUG"
            APP_NAME = "myservice"
        """),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.HARDCODED_SECRET,
            file_path="config/defaults.py",
            should_detect=False,
            description=(
                "Non-secret config values (host, port, timeout) do not match secret heuristics"
            ),
        ),
    ],
)


# ---------------------------------------------------------------------------
# FOE scoring-promotion fixtures (ADR-040)
# ---------------------------------------------------------------------------

FOE_HIGH_IMPORT_TP = GroundTruthFixture(
    name="foe_high_import_tp",
    description="File with 22 unique imports → should fire FOE (threshold 15)",
    files={
        "app/__init__.py": "",
        "app/god_module.py": textwrap.dedent("""\
            import os
            import sys
            import json
            import logging
            import pathlib
            import hashlib
            import datetime
            import collections
            import functools
            import itertools
            import typing
            import dataclasses
            import re
            import math
            import sqlite3
            import urllib
            import http
            import email
            import csv
            import io
            import abc
            import contextlib

            def do_everything():
                pass
        """),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.FAN_OUT_EXPLOSION,
            file_path="app/god_module.py",
            should_detect=True,
            description="22 unique imports exceeds threshold of 15",
        ),
    ],
)

FOE_NORMAL_IMPORT_TN = GroundTruthFixture(
    name="foe_normal_import_tn",
    description="File with 8 imports → should NOT fire FOE",
    files={
        "utils/__init__.py": "",
        "utils/helpers.py": textwrap.dedent("""\
            import os
            import sys
            import json
            import logging
            import pathlib
            import hashlib
            import typing
            import dataclasses

            def helper():
                pass
        """),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.FAN_OUT_EXPLOSION,
            file_path="utils/helpers.py",
            should_detect=False,
            description="8 imports is well below threshold of 15",
        ),
    ],
)

FOE_BARREL_FILE_TN = GroundTruthFixture(
    name="foe_barrel_file_tn",
    description="__init__.py barrel file with many re-exports → excluded from FOE",
    kind=FixtureKind.CONFOUNDER,
    files={
        "mypackage/__init__.py": textwrap.dedent("""\
            from mypackage.core import Engine
            from mypackage.config import Settings
            from mypackage.utils import helper
            from mypackage.models import User, Order, Product
            from mypackage.db import connect, disconnect
            from mypackage.api import create_app, register_routes
            from mypackage.auth import login, logout, verify_token
            from mypackage.cache import get_cache, set_cache
            from mypackage.logging import setup_logging
            from mypackage.errors import AppError, ValidationError
        """),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.FAN_OUT_EXPLOSION,
            file_path="mypackage/__init__.py",
            should_detect=False,
            description="__init__.py barrel files are excluded from FOE detection",
        ),
    ],
)


# ---------------------------------------------------------------------------
# PHR additional fixtures (ADR-040: scoring-promotion coverage)
# ---------------------------------------------------------------------------

PHR_CONDITIONAL_IMPORT_TN = GroundTruthFixture(
    name="phr_conditional_import_tn",
    description="try/except ImportError guard → should NOT fire PHR",
    kind=FixtureKind.CONFOUNDER,
    files={
        "compat/__init__.py": "",
        "compat/shims.py": textwrap.dedent("""\
            try:
                from rapidjson import loads as json_loads
            except ImportError:
                from json import loads as json_loads

            def parse(data: str):
                return json_loads(data)
        """),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.PHANTOM_REFERENCE,
            file_path="compat/shims.py",
            should_detect=False,
            description="try/except ImportError is a valid conditional import guard",
        ),
    ],
)

PHR_FRAMEWORK_DECORATOR_TN = GroundTruthFixture(
    name="phr_framework_decorator_tn",
    description="Flask/pytest decorators → should NOT fire PHR",
    kind=FixtureKind.CONFOUNDER,
    files={
        "web/__init__.py": "",
        "flask/__init__.py": textwrap.dedent("""\
            class Flask:
                def __init__(self, name):
                    self.name = name
                def route(self, path):
                    def decorator(fn):
                        return fn
                    return decorator
        """),
        "web/routes.py": textwrap.dedent("""\
            from flask import Flask

            app = Flask(__name__)

            @app.route("/health")
            def health():
                return {"status": "ok"}
        """),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.PHANTOM_REFERENCE,
            file_path="web/routes.py",
            should_detect=False,
            description="Flask app.route decorator is a framework-injected name",
        ),
    ],
)


# ---------------------------------------------------------------------------
# FP-Reduction fixtures (ADR-036, ADR-037, ADR-038)
# ---------------------------------------------------------------------------

# AVS: models/ is now Omnilayer — cross-layer import should not fire
AVS_MODELS_OMNILAYER_TN = GroundTruthFixture(
    name="avs_models_omnilayer_tn",
    description=(
        "models.py imported from api layer — models is now Omnilayer, "
        "should NOT fire AVS upward-import"
    ),
    files={
        "api/__init__.py": "",
        "api/routes.py": textwrap.dedent("""\
            from models.user import User
            def get_user() -> User:
                return User(name="test")
        """),
        "models/__init__.py": "",
        "models/user.py": textwrap.dedent("""\
            class User:
                def __init__(self, name: str):
                    self.name = name
        """),
        "services/__init__.py": "",
        "services/user_service.py": textwrap.dedent("""\
            from models.user import User
            def create_user(name: str) -> User:
                return User(name=name)
        """),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.ARCHITECTURE_VIOLATION,
            file_path="api/routes.py",
            should_detect=False,
            description="models is Omnilayer — no upward-import violation",
        ),
    ],
)

# AVS: DTO models used across layers — should not fire
AVS_CONFOUNDER_DTO_TN = GroundTruthFixture(
    name="avs_confounder_dto_tn",
    description=("DTO models used across all layers — Omnilayer behavior expected"),
    kind=FixtureKind.CONFOUNDER,
    files={
        "models/__init__.py": "",
        "models/dto.py": textwrap.dedent("""\
            from dataclasses import dataclass
            @dataclass
            class UserDTO:
                name: str
                email: str
        """),
        "api/__init__.py": "",
        "api/views.py": textwrap.dedent("""\
            from models.dto import UserDTO
            def render_user(user: UserDTO) -> dict:
                return {"name": user.name}
        """),
        "db/__init__.py": "",
        "db/repository.py": textwrap.dedent("""\
            from models.dto import UserDTO
            def save_user(user: UserDTO) -> None:
                pass
        """),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.ARCHITECTURE_VIOLATION,
            file_path="api/views.py",
            should_detect=False,
            description="models/dto is Omnilayer — no violation",
        ),
    ],
)

# DIA: Default auxiliary dir (scripts/) — should not report as undocumented
DIA_CUSTOM_AUXILIARY_TN = GroundTruthFixture(
    name="dia_custom_auxiliary_tn",
    description=("scripts/ is a default auxiliary dir — should NOT fire DIA undocumented-dir"),
    files={
        "README.md": textwrap.dedent("""\
            # My Project
            The main code lives in `src/`.
        """),
        "src/__init__.py": "",
        "src/core.py": textwrap.dedent("""\
            def main():
                pass
        """),
        "scripts/__init__.py": "",
        "scripts/deploy.py": textwrap.dedent("""\
            def deploy():
                pass
        """),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.DOC_IMPL_DRIFT,
            file_path="scripts/",
            should_detect=False,
            description=("scripts/ is a default auxiliary dir — not expected in README"),
        ),
    ],
)

# MDS: Protocol methods in different classes — should not fire
MDS_CONFOUNDER_PROTOCOL_METHODS_TN = GroundTruthFixture(
    name="mds_confounder_protocol_methods_tn",
    description=(
        "Two classes implementing the same protocol method with similar "
        "structure — should NOT fire MDS"
    ),
    kind=FixtureKind.CONFOUNDER,
    files={
        "serializers/__init__.py": "",
        "serializers/json_serializer.py": textwrap.dedent("""\
            class JsonSerializer:
                def serialize(self, data: dict) -> str:
                    import json
                    result = json.dumps(data)
                    return result

                def deserialize(self, text: str) -> dict:
                    import json
                    result = json.loads(text)
                    return result
        """),
        "serializers/yaml_serializer.py": textwrap.dedent("""\
            class YamlSerializer:
                def serialize(self, data: dict) -> str:
                    import yaml
                    result = yaml.dump(data)
                    return result

                def deserialize(self, text: str) -> dict:
                    import yaml
                    result = yaml.safe_load(text)
                    return result
        """),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.MUTANT_DUPLICATE,
            file_path="serializers/json_serializer.py",
            should_detect=False,
            description=(
                "Protocol methods (serialize/deserialize) in different "
                "classes — intentional polymorphism"
            ),
        ),
    ],
)

# MDS: Thin wrapper delegating to another function — should not fire
MDS_CONFOUNDER_THIN_WRAPPER_TN = GroundTruthFixture(
    name="mds_confounder_thin_wrapper_tn",
    description=("Thin wrapper function delegating to implementation — should NOT fire MDS"),
    kind=FixtureKind.CONFOUNDER,
    files={
        "utils/__init__.py": "",
        "utils/core.py": textwrap.dedent("""\
            def _do_process(items: list, config: dict) -> list:
                result = []
                for item in items:
                    if config.get("filter"):
                        if item.get("active"):
                            result.append(item)
                    else:
                        result.append(item)
                return result

            def process_items(items: list, config: dict) -> list:
                return _do_process(items, config)
        """),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.MUTANT_DUPLICATE,
            file_path="utils/core.py",
            should_detect=False,
            description=(
                "process_items is a thin wrapper for _do_process — intentional delegation"
            ),
        ),
    ],
)

# MDS: Similar body but very different names — should not fire
MDS_CONFOUNDER_NAME_DIVERSE_TN = GroundTruthFixture(
    name="mds_confounder_name_diverse_tn",
    description=(
        "Functions with similar structure but semantically different "
        "names — name distance should reduce similarity below threshold"
    ),
    kind=FixtureKind.CONFOUNDER,
    files={
        "validators/__init__.py": "",
        "validators/checks.py": textwrap.dedent("""\
            def validate_email_format(value: str) -> bool:
                if not value:
                    return False
                if "@" not in value:
                    return False
                parts = value.split("@")
                if len(parts) != 2:
                    return False
                return bool(parts[0] and parts[1])

            def sanitize_phone_number(value: str) -> bool:
                if not value:
                    return False
                if "+" not in value:
                    return False
                parts = value.split("+")
                if len(parts) != 2:
                    return False
                return bool(parts[0] or parts[1])
        """),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.MUTANT_DUPLICATE,
            file_path="validators/checks.py",
            should_detect=False,
            description=(
                "validate_email_format and sanitize_phone_number have "
                "different names — name distance should help"
            ),
        ),
    ],
)


# ── Cognitive Complexity (CXS) ────────────────────────────────────────────

CXS_TP_DEEP_NESTING = GroundTruthFixture(
    name="cxs_tp_deep_nesting",
    description="Function with 4+ nested if/for/while levels → CC >> 15, should fire CXS",
    kind=FixtureKind.POSITIVE,
    files={
        "services/__init__.py": "",
        "services/processor.py": """\
            def process_batch(orders, users, config, database):
                results = []
                for order in orders:
                    if order.status == "pending":
                        for item in order.items:
                            if item.quantity > 0:
                                if item.price > config.min_price:
                                    while not database.is_ready():
                                        if config.retry:
                                            try:
                                                database.reconnect()
                                            except Exception:
                                                if config.fallback:
                                                    results.append(None)
                                                else:
                                                    raise
                                        else:
                                            break
                                    results.append(item)
                return results
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.COGNITIVE_COMPLEXITY,
            file_path="services/processor.py",
            should_detect=True,
            description="Deep nesting (4+ levels) produces CC well above threshold 15",
        ),
    ],
)

CXS_TN_FLAT_CODE = GroundTruthFixture(
    name="cxs_tn_flat_code",
    description="Linear function with no control structures → CC = 0, should NOT fire CXS",
    kind=FixtureKind.NEGATIVE,
    files={
        "utils/__init__.py": "",
        "utils/format.py": """\
            def format_report(title, body, footer, author, date):
                header = f"Report: {title}"
                separator = "=" * len(header)
                content = f"{header}\\n{separator}\\n{body}"
                attribution = f"By {author} on {date}"
                result = f"{content}\\n{footer}\\n{attribution}"
                return result
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.COGNITIVE_COMPLEXITY,
            file_path="utils/format.py",
            should_detect=False,
            description="Purely linear code, CC = 0",
        ),
    ],
)

CXS_TP_MANY_ELIF = GroundTruthFixture(
    name="cxs_tp_many_elif",
    description="Function with long elif chain → CC > 15 from many branches, should fire CXS",
    kind=FixtureKind.POSITIVE,
    files={
        "handlers/__init__.py": "",
        "handlers/dispatch.py": """\
            def dispatch_event(event_type, payload, context, logger, config):
                if event_type == "create":
                    logger.info("create")
                elif event_type == "update":
                    logger.info("update")
                elif event_type == "delete":
                    logger.info("delete")
                elif event_type == "archive":
                    logger.info("archive")
                elif event_type == "restore":
                    logger.info("restore")
                elif event_type == "publish":
                    logger.info("publish")
                elif event_type == "unpublish":
                    logger.info("unpublish")
                elif event_type == "merge":
                    logger.info("merge")
                elif event_type == "split":
                    logger.info("split")
                elif event_type == "clone":
                    logger.info("clone")
                elif event_type == "transfer":
                    logger.info("transfer")
                elif event_type == "import":
                    logger.info("import")
                elif event_type == "export":
                    logger.info("export")
                elif event_type == "validate":
                    logger.info("validate")
                elif event_type == "notify":
                    logger.info("notify")
                elif event_type == "escalate":
                    logger.info("escalate")
                else:
                    logger.warning("unknown event")
                return True
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.COGNITIVE_COMPLEXITY,
            file_path="handlers/dispatch.py",
            should_detect=True,
            description="16 elif branches → CC = 17 (1 if + 16 elif), above threshold 15",
        ),
    ],
)

CXS_BOUNDARY_THRESHOLD = GroundTruthFixture(
    name="cxs_boundary_threshold",
    description="Function with CC=16 (just above threshold 15) — boundary detection case",
    kind=FixtureKind.BOUNDARY,
    files={
        "core/__init__.py": "",
        "core/validation.py": """\
def validate_order(order, catalog, user, config, logger):
    if not order.items:
        return False
    for item in order.items:
        if item.id not in catalog:
            if config.strict:
                return False
            else:
                logger.warning("Unknown item", item.id)
        if item.quantity <= 0:
            return False
        if item.price < 0:
            return False
    if not user.is_active and not user.is_guest:
        if config.block_inactive:
            return False
    if config.warn_inactive:
        logger.warning("Inactive user", user.id)
    return True
""",
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.COGNITIVE_COMPLEXITY,
            file_path="core/validation.py",
            should_detect=True,
            description="CC=16 — just above threshold 15, boundary detection case",
        ),
    ],
)

CXS_CONFOUNDER_ASYNC_LOOPS = GroundTruthFixture(
    name="cxs_confounder_async_loops",
    description="Async for + if with moderate nesting → CC below threshold, should NOT fire CXS",
    kind=FixtureKind.CONFOUNDER,
    files={
        "workers/__init__.py": "",
        "workers/fetcher.py": """\
            async def fetch_pages(urls, session, max_retries):
                results = []
                async for url in urls:
                    if url.startswith("https"):
                        try:
                            resp = await session.get(url)
                            results.append(resp)
                        except Exception:
                            if max_retries > 0:
                                results.append(None)
                return results
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.COGNITIVE_COMPLEXITY,
            file_path="workers/fetcher.py",
            should_detect=False,
            description="CC ~9 despite async for/if/try/except nesting — below threshold 15",
        ),
    ],
)

CXS_CONFOUNDER_DECORATORS = GroundTruthFixture(
    name="cxs_confounder_decorators",
    description="Many decorators but trivial body → CC = 0, should NOT fire CXS",
    kind=FixtureKind.CONFOUNDER,
    files={
        "api/__init__.py": "",
        "api/endpoints.py": """\
            def require_auth(f):
                return f
            def rate_limit(f):
                return f
            def cache_response(f):
                return f
            def log_request(f):
                return f
            def validate_input(f):
                return f
            def track_metrics(f):
                return f

            @require_auth
            @rate_limit
            @cache_response
            @log_request
            @validate_input
            @track_metrics
            def get_user_profile(user_id, session, config, logger, cache):
                return session.query(user_id)
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.COGNITIVE_COMPLEXITY,
            file_path="api/endpoints.py",
            should_detect=False,
            description="Decorators don't affect CC — function body is trivial, CC = 0",
        ),
    ],
)


# ── Additional Co-Change Coupling (CCC) fixtures ─────────────────────────

CCC_TP_CROSS_LAYER = GroundTruthFixture(
    name="ccc_tp_cross_layer",
    description="API views + DB queries co-change 10 times without imports → should fire CCC",
    kind=FixtureKind.POSITIVE,
    files={
        "api/__init__.py": "",
        "api/views.py": """\
            def list_users(request):
                return {"users": []}
            def get_user(request, user_id):
                return {"user": user_id}
        """,
        "db/__init__.py": "",
        "db/queries.py": """\
            def fetch_users(connection):
                return connection.execute("SELECT * FROM users")
            def fetch_user_by_id(connection, user_id):
                return connection.execute("SELECT * FROM users WHERE id=?", user_id)
        """,
    },
    commits=[
        CommitInfo(
            hash=f"cross{i:04d}",
            author="dev",
            email="dev@example.com",
            timestamp=_dt.datetime(2026, 6, 1 + i, tzinfo=_dt.UTC),
            message=f"feat: update api and db layer #{i}",
            files_changed=["api/views.py", "db/queries.py"],
        )
        for i in range(10)
    ],
    expected=[
        ExpectedFinding(
            signal_type=SignalType.CO_CHANGE_COUPLING,
            file_path="api/views.py",
            should_detect=True,
            description="Cross-layer co-change without import edge → hidden coupling",
        ),
    ],
)

CCC_CONFOUNDER_BURST_TN = GroundTruthFixture(
    name="ccc_confounder_burst_tn",
    description=(
        "9 co-changes in burst + 24 solo commits — CCC has no burst filtering, "
        "so this still fires (should_detect=True despite burst pattern)"
    ),
    kind=FixtureKind.CONFOUNDER,
    files={
        "svc/__init__.py": "",
        "svc/auth.py": """\
            def authenticate(username, password):
                return username == "admin"
        """,
        "svc/logging.py": """\
            def log_event(event_type, payload):
                print(f"{event_type}: {payload}")
        """,
    },
    commits=[
        # Burst: 9 co-changes in 2 days
        *[
            CommitInfo(
                hash=f"burst{i:04d}",
                author="dev",
                email="dev@example.com",
                timestamp=_dt.datetime(2026, 1, 1, tzinfo=_dt.UTC) + _dt.timedelta(hours=i * 2),
                message=f"fix: burst commit #{i}",
                files_changed=["svc/auth.py", "svc/logging.py"],
            )
            for i in range(9)
        ],
        # Solo commits to give enough history
        *[
            CommitInfo(
                hash=f"solo{i:04d}",
                author="dev",
                email="dev@example.com",
                timestamp=_dt.datetime(2026, 2, 1 + i, tzinfo=_dt.UTC),
                message=f"chore: solo work #{i}",
                files_changed=["svc/auth.py"],
            )
            for i in range(24)
        ],
    ],
    expected=[
        ExpectedFinding(
            signal_type=SignalType.CO_CHANGE_COUPLING,
            file_path="svc/auth.py",
            should_detect=True,
            description=(
                "CCC has no temporal/burst filtering — 9 co-changes satisfy "
                "all thresholds even though concentrated in a burst"
            ),
        ),
    ],
)


# ── Additional Cohesion Deficit (COD) fixtures ────────────────────────────

COD_CONFOUNDER_SINGLE_METHOD_TN = GroundTruthFixture(
    name="cod_confounder_single_method_tn",
    description="File with only 1 function — below min_units=4, should NOT fire COD",
    kind=FixtureKind.CONFOUNDER,
    files={
        "helpers/__init__.py": "",
        "helpers/single.py": """\
            def compute_total(items):
                return sum(item.price * item.quantity for item in items)
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.COHESION_DEFICIT,
            file_path="helpers/single.py",
            should_detect=False,
            description="Only 1 function — below min_units=4 threshold",
        ),
    ],
)

COD_CONFOUNDER_PROPERTY_ONLY_TN = GroundTruthFixture(
    name="cod_confounder_property_only_tn",
    description=(
        "Class with 5 @property methods sharing domain vocabulary → cohesive, should NOT fire COD"
    ),
    kind=FixtureKind.CONFOUNDER,
    files={
        "domain/__init__.py": "",
        "domain/order.py": """\
            class Order:
                def __init__(self, items, customer, discount):
                    self._items = items
                    self._customer = customer
                    self._discount = discount

                @property
                def order_total(self):
                    return sum(i.price for i in self._items)

                @property
                def order_discount(self):
                    return self._discount

                @property
                def order_final_price(self):
                    return self.order_total - self.order_discount

                @property
                def order_item_count(self):
                    return len(self._items)

                @property
                def order_customer_name(self):
                    return self._customer.name
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.COHESION_DEFICIT,
            file_path="domain/order.py",
            should_detect=False,
            description="All properties share 'order' vocabulary — cohesive domain object",
        ),
    ],
)

COD_BOUNDARY_PARTIAL_COHESION = GroundTruthFixture(
    name="cod_boundary_partial_cohesion",
    description="4 payment-cohesive + 4 unrelated functions → mixed cohesion, should fire COD",
    kind=FixtureKind.BOUNDARY,
    files={
        "services/__init__.py": "",
        "services/mixed.py": """\
            def calculate_payment_amount(order):
                return order.total

            def validate_payment_method(method):
                return method in ("card", "bank")

            def process_payment_refund(payment_id):
                return {"refunded": payment_id}

            def format_payment_receipt(payment):
                return f"Receipt: {payment}"

            def send_email_notification(recipient, subject, body):
                print(f"To: {recipient}")

            def resize_image_thumbnail(image, width, height):
                return image[:width * height]

            def parse_xml_config(raw):
                return {"config": raw}

            def generate_pdf_report(data, template):
                return f"PDF: {template}"
        """,
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.COHESION_DEFICIT,
            file_path="services/mixed.py",
            should_detect=True,
            description="4 payment functions + 4 unrelated → low aggregate Jaccard similarity",
        ),
    ],
)


# ---------------------------------------------------------------------------
# ISD scoring-promotion fixtures (ADR-039)
# ---------------------------------------------------------------------------

ISD_DJANGO_INSECURE_TP = GroundTruthFixture(
    name="isd_django_insecure_tp",
    description="Django settings with DEBUG=True and ALLOWED_HOSTS=['*'] → should fire ISD",
    files={
        "myproject/__init__.py": "",
        "myproject/settings.py": textwrap.dedent("""\
            import os

            DEBUG = True
            ALLOWED_HOSTS = ["*"]
            CORS_ALLOW_ALL_ORIGINS = True
            SECRET_KEY = os.environ["SECRET_KEY"]
        """),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.INSECURE_DEFAULT,
            file_path="myproject/settings.py",
            should_detect=True,
            description=(
                "DEBUG=True + ALLOWED_HOSTS=['*'] + CORS all origins → multiple ISD findings"
            ),
        ),
    ],
)

ISD_VERIFY_FALSE_TP = GroundTruthFixture(
    name="isd_verify_false_tp",
    description="requests.get with verify=False to external URL → should fire ISD",
    files={
        "client/__init__.py": "",
        "client/api.py": textwrap.dedent("""\
            import requests

            def fetch_data():
                resp = requests.get("https://api.example.com/data", verify=False)
                return resp.json()
        """),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.INSECURE_DEFAULT,
            file_path="client/api.py",
            should_detect=True,
            description="verify=False on external HTTPS endpoint disables TLS validation",
        ),
    ],
)

ISD_SECURE_DJANGO_TN = GroundTruthFixture(
    name="isd_secure_django_tn",
    description="Properly secured Django settings → should NOT fire ISD",
    kind=FixtureKind.CONFOUNDER,
    files={
        "myproject/__init__.py": "",
        "myproject/settings.py": textwrap.dedent("""\
            import os

            DEBUG = False
            ALLOWED_HOSTS = ["myapp.example.com"]
            SESSION_COOKIE_SECURE = True
            CSRF_COOKIE_SECURE = True
            SECURE_SSL_REDIRECT = True
            SECRET_KEY = os.environ["SECRET_KEY"]
        """),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.INSECURE_DEFAULT,
            file_path="myproject/settings.py",
            should_detect=False,
            description="All settings are production-safe → no ISD findings",
        ),
    ],
)

ISD_VERIFY_FALSE_LOCALHOST_TN = GroundTruthFixture(
    name="isd_verify_false_localhost_tn",
    description=(
        "verify=False targeting localhost → reduced severity, still detected but loopback-scoped"
    ),
    kind=FixtureKind.BOUNDARY,
    files={
        "dev/__init__.py": "",
        "dev/local_client.py": textwrap.dedent("""\
            import requests

            def ping_local():
                return requests.get("http://localhost:8000/health", verify=False)
        """),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.INSECURE_DEFAULT,
            file_path="dev/local_client.py",
            should_detect=True,
            description="verify=False on localhost is still detected but with reduced score (0.45)",
        ),
    ],
)

ISD_IGNORE_DIRECTIVE_TN = GroundTruthFixture(
    name="isd_ignore_directive_tn",
    description="File with # drift:ignore-security → should NOT fire ISD despite insecure settings",
    kind=FixtureKind.CONFOUNDER,
    files={
        "legacy/__init__.py": "",
        "legacy/settings.py": textwrap.dedent("""\
            # drift:ignore-security
            # Legacy settings kept for backwards compatibility testing

            DEBUG = True
            ALLOWED_HOSTS = ["*"]
        """),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.INSECURE_DEFAULT,
            file_path="legacy/settings.py",
            should_detect=False,
            description="drift:ignore-security directive suppresses all ISD findings in this file",
        ),
    ],
)


# ── TypeScript Ground-Truth Fixtures (Phase 1 — TS Parity) ──────────────

# TYPE_SAFETY_BYPASS — TS-specific signal for @ts-ignore, as any, non-null assertions

TSB_TS_TRUE_POSITIVE = GroundTruthFixture(
    name="tsb_ts_tp",
    description="TypeScript file with multiple type safety bypasses → should fire TSB",
    files={
        "src/legacy.ts": (
            "// Legacy TypeScript module with accumulated bypasses\n"
            "interface User { id: string; name: string; role: string; }\n"
            "\n"
            "// @ts-ignore\n"
            "const config = JSON.parse(rawData) as any;\n"
            "\n"
            "// @ts-ignore\n"
            "const settings = loadSettings() as any;\n"
            "\n"
            "// @ts-expect-error\n"
            "const broken: number = 'not a number';\n"
            "\n"
            "function getUser(id: string): User {\n"
            "  const el = document.getElementById(id)!;\n"
            "  const parent = el.parentElement!;\n"
            "  return { id, name: el.textContent as any, role: parent.dataset.role as any };\n"
            "}\n"
            "\n"
            "function processData(data: unknown): void {\n"
            "  const items = data as any;\n"
            "  items.forEach((item: any) => console.log(item));\n"
            "}\n"
        ),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.TYPE_SAFETY_BYPASS,
            file_path="src/legacy.ts",
            should_detect=True,
            description="Multiple @ts-ignore, as any, and non-null assertion bypasses",
        ),
    ],
)

TSB_TS_TRUE_NEGATIVE = GroundTruthFixture(
    name="tsb_ts_tn",
    description="Clean TypeScript file without bypasses → should NOT fire TSB",
    files={
        "src/clean.ts": (
            "// Well-typed TypeScript module\n"
            "interface User {\n"
            "  id: string;\n"
            "  name: string;\n"
            "  email: string;\n"
            "}\n"
            "\n"
            "interface Config {\n"
            "  host: string;\n"
            "  port: number;\n"
            "  debug: boolean;\n"
            "}\n"
            "\n"
            "function createUser(name: string, email: string): User {\n"
            "  return { id: crypto.randomUUID(), name, email };\n"
            "}\n"
            "\n"
            "function validateConfig(config: Config): boolean {\n"
            "  if (!config.host) return false;\n"
            "  if (config.port < 1 || config.port > 65535) return false;\n"
            "  return true;\n"
            "}\n"
            "\n"
            "function formatUser(user: User): string {\n"
            "  return `${user.name} <${user.email}>`;\n"
            "}\n"
            "\n"
            "export { createUser, validateConfig, formatUser };\n"
        ),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.TYPE_SAFETY_BYPASS,
            file_path="src/clean.ts",
            should_detect=False,
            description="No bypasses in well-typed code",
        ),
    ],
)

# NAMING_CONTRACT_VIOLATION — TS-specific: camelCase naming + tree-sitter checkers

NBV_TS_VALIDATE_TP = GroundTruthFixture(
    name="nbv_ts_validate_tp",
    description="TS validateEmail() without throw or return false → should fire NBV",
    files={
        "src/validators.ts": (
            "// Validator module\n"
            "\n"
            "export function validateEmail(email: string): string {\n"
            "  const parts = email.split('@');\n"
            "  const domain = parts.length > 1 ? parts[1] : '';\n"
            "  const local = parts[0] || '';\n"
            "  const cleaned = local.trim().toLowerCase();\n"
            "  return `${cleaned}@${domain}`;\n"
            "}\n"
        ),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.NAMING_CONTRACT_VIOLATION,
            file_path="src/validators.ts",
            should_detect=True,
            description="validateEmail has no throw and never returns false/null",
        ),
    ],
)

NBV_TS_TRUE_NEGATIVE = GroundTruthFixture(
    name="nbv_ts_tn",
    description="TS validateEmail() with proper throw → should NOT fire NBV",
    files={
        "src/validators_clean.ts": (
            "// Validator module with proper contracts\n"
            "\n"
            "export function validateEmail(email: string): boolean {\n"
            "  if (!email.includes('@')) {\n"
            "    throw new Error('Invalid email format');\n"
            "  }\n"
            "  return true;\n"
            "}\n"
            "\n"
            "export function isAdmin(user: { role: string }): boolean {\n"
            "  return user.role === 'admin';\n"
            "}\n"
            "\n"
            "export function hasPermission(user: { perms: string[] }, perm: string): boolean {\n"
            "  return user.perms.includes(perm);\n"
            "}\n"
        ),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.NAMING_CONTRACT_VIOLATION,
            file_path="src/validators_clean.ts",
            should_detect=False,
            description="validateEmail has throw, isAdmin/hasPermission return boolean",
        ),
    ],
)

# GUARD_CLAUSE_DEFICIT — TS functions with no guards

GCD_TS_TRUE_POSITIVE = GroundTruthFixture(
    name="gcd_ts_tp",
    description="TS module with 3+ unguarded complex public functions → should fire GCD",
    files={
        "src/processor.ts": (
            "// Data processing module — no input validation guards\n"
            "\n"
            "export function transformData(data: unknown[], schema: Record<string, string>,\n"
            "                              options: Record<string, unknown>): "
            "Record<string, unknown>[] {\n"
            "  const result: Record<string, unknown>[] = [];\n"
            "  for (const item of data as Record<string, unknown>[]) {\n"
            "    const out: Record<string, unknown> = {};\n"
            "    for (const [key, spec] of Object.entries(schema)) {\n"
            "      const val = (item as Record<string, string>)[key];\n"
            "      if (spec === 'upper') {\n"
            "        out[key] = val.toUpperCase();\n"
            "      } else if (spec === 'lower') {\n"
            "        out[key] = val.toLowerCase();\n"
            "      } else if (spec === 'strip') {\n"
            "        out[key] = val.trim();\n"
            "      } else {\n"
            "        out[key] = val;\n"
            "      }\n"
            "    }\n"
            "    if (options.filterKey) {\n"
            "      if (out[options.filterKey as string]) {\n"
            "        result.push(out);\n"
            "      }\n"
            "    } else {\n"
            "      result.push(out);\n"
            "    }\n"
            "  }\n"
            "  return result;\n"
            "}\n"
            "\n"
            "export function aggregateRecords(records: Record<string, unknown>[],\n"
            "                                 dimensions: string[],\n"
            "                                 funcs: string[]): Record<string, unknown>[] {\n"
            "  const groups = new Map<string, Record<string, unknown>[]>();\n"
            "  for (const r of records) {\n"
            "    const key = dimensions.map(d => String(r[d])).join('|');\n"
            "    if (!groups.has(key)) groups.set(key, []);\n"
            "    groups.get(key)!.push(r);\n"
            "  }\n"
            "  const out: Record<string, unknown>[] = [];\n"
            "  for (const [key, rows] of groups.entries()) {\n"
            "    const parts = key.split('|');\n"
            "    const entry: Record<string, unknown> = {};\n"
            "    dimensions.forEach((d, i) => entry[d] = parts[i]);\n"
            "    for (const fn of funcs) {\n"
            "      const vals = rows.map(r => Number(r[fn]) || 0);\n"
            "      if (vals.length > 0) {\n"
            "        entry[fn] = vals.reduce((a, b) => a + b, 0) / vals.length;\n"
            "      }\n"
            "    }\n"
            "    out.push(entry);\n"
            "  }\n"
            "  return out;\n"
            "}\n"
            "\n"
            "export function exportReport(data: Record<string, unknown>[],\n"
            "                             columns: string[],\n"
            "                             fmt: string): string {\n"
            "  const lines: string[] = [];\n"
            "  const header = columns.map(c => String(c));\n"
            "  lines.push(header.join(','));\n"
            "  for (const row of data) {\n"
            "    const cells: string[] = [];\n"
            "    for (const col of columns) {\n"
            "      const val = row[col] ?? '';\n"
            "      if (fmt === 'quoted') {\n"
            "        cells.push(`\"${val}\"`);\n"
            "      } else if (fmt === 'raw') {\n"
            "        cells.push(String(val));\n"
            "      } else {\n"
            "        cells.push(String(val).trim());\n"
            "      }\n"
            "    }\n"
            "    lines.push(cells.join(','));\n"
            "  }\n"
            "  return lines.join('\\n');\n"
            "}\n"
        ),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.GUARD_CLAUSE_DEFICIT,
            file_path="src/",
            should_detect=True,
            description="3 public TS functions with >=2 params, no guards",
        ),
    ],
)

GCD_TS_TRUE_NEGATIVE = GroundTruthFixture(
    name="gcd_ts_tn",
    description="TS module with properly guarded functions → should NOT fire GCD",
    files={
        "src/guarded.ts": (
            "// Well-guarded TypeScript module\n"
            "\n"
            "export function processUser(user: unknown, id: string): string {\n"
            "  if (!user) throw new Error('User is required');\n"
            "  if (!id) return '';\n"
            "  return String(user) + id;\n"
            "}\n"
            "\n"
            "export function formatDate(date: Date, locale: string): string {\n"
            "  if (!date) throw new Error('Date is required');\n"
            "  if (!locale) return date.toISOString();\n"
            "  return date.toLocaleDateString(locale);\n"
            "}\n"
            "\n"
            "export function mergeConfigs(base: Record<string, unknown>,\n"
            "                             override: Record<string, unknown>): "
            "Record<string, unknown> {\n"
            "  if (!base) throw new Error('Base config required');\n"
            "  if (!override) return { ...base };\n"
            "  return { ...base, ...override };\n"
            "}\n"
        ),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.GUARD_CLAUSE_DEFICIT,
            file_path="src/",
            should_detect=False,
            description="All functions have early-return/throw guards",
        ),
    ],
)

# TS_ARCHITECTURE — circular import cycle

TSA_CIRCULAR_TP = GroundTruthFixture(
    name="tsa_circular_tp",
    description="Circular TS import cycle (A → B → C → A) → should fire TSA",
    files={
        "src/a.ts": (
            "import { helperB } from './b';\n"
            "\n"
            "export function serviceA(): string {\n"
            "  return 'A:' + helperB();\n"
            "}\n"
        ),
        "src/b.ts": (
            "import { helperC } from './c';\n"
            "\n"
            "export function helperB(): string {\n"
            "  return 'B:' + helperC();\n"
            "}\n"
        ),
        "src/c.ts": (
            "import { serviceA } from './a';\n"
            "\n"
            "export function helperC(): string {\n"
            "  return 'C:' + serviceA();\n"
            "}\n"
        ),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.TS_ARCHITECTURE,
            file_path="src/a.ts",
            should_detect=True,
            description="Circular import cycle: a → b → c → a",
        ),
    ],
)

TSA_CLEAN_TN = GroundTruthFixture(
    name="tsa_clean_tn",
    description="TS files with acyclic imports → should NOT fire TSA",
    files={
        "src/types.ts": (
            "export interface Config {\n"
            "  host: string;\n"
            "  port: number;\n"
            "}\n"
        ),
        "src/utils.ts": (
            "import { Config } from './types';\n"
            "\n"
            "export function formatConfig(cfg: Config): string {\n"
            "  return `${cfg.host}:${cfg.port}`;\n"
            "}\n"
        ),
        "src/main.ts": (
            "import { Config } from './types';\n"
            "import { formatConfig } from './utils';\n"
            "\n"
            "const config: Config = { host: 'localhost', port: 8080 };\n"
            "console.log(formatConfig(config));\n"
        ),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.TS_ARCHITECTURE,
            file_path="src/",
            should_detect=False,
            description="Acyclic import structure — no circular dependencies",
        ),
    ],
)


# ── Phase 2 — TS ground-truth fixtures: BEM, EDS, MDS, PFS ──────────────

BEM_TS_TRUE_POSITIVE = GroundTruthFixture(
    name="bem_ts_tp",
    description="TS module with broad catch + swallowing in every handler → should fire BEM",
    files={
        "connectors/db.ts": (
            "import { logger } from './logger';\n"
            "\n"
            "export function getUser(uid: string): object | undefined {\n"
            "  try {\n"
            "    return { id: uid };\n"
            "  } catch (e) {\n"
            "    logger.error('db get failed');\n"
            "  }\n"
            "}\n"
        ),
        "connectors/cache.ts": (
            "import { logger } from './logger';\n"
            "\n"
            "export function invalidate(key: string): boolean | undefined {\n"
            "  try {\n"
            "    return true;\n"
            "  } catch (e) {\n"
            "    logger.error('cache invalidate failed');\n"
            "  }\n"
            "}\n"
        ),
        "connectors/queue.ts": (
            "import { logger } from './logger';\n"
            "\n"
            "export function publish(topic: string, msg: string): boolean | undefined {\n"
            "  try {\n"
            "    return true;\n"
            "  } catch (e) {\n"
            "    logger.error('queue publish failed');\n"
            "  }\n"
            "}\n"
        ),
        "connectors/logger.ts": (
            "export const logger = {\n"
            "  error: (msg: string) => console.error(msg),\n"
            "};\n"
        ),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.BROAD_EXCEPTION_MONOCULTURE,
            file_path="connectors/",
            should_detect=True,
            description="3 handlers all catch bare exception + log-only swallowing",
        ),
    ],
)

BEM_TS_TRUE_NEGATIVE = GroundTruthFixture(
    name="bem_ts_tn",
    description="TS module with specific catches and re-throws → should NOT fire BEM",
    files={
        "services/user.ts": (
            "export class UserNotFoundError extends Error {\n"
            "  constructor(id: string) { super(`User ${id} not found`); }\n"
            "}\n"
            "\n"
            "export function getUser(uid: string): object {\n"
            "  try {\n"
            "    return { id: uid };\n"
            "  } catch (e: unknown) {\n"
            "    if (e instanceof UserNotFoundError) {\n"
            "      throw e;\n"
            "    }\n"
            "    throw new Error(`Unexpected error: ${e}`);\n"
            "  }\n"
            "}\n"
        ),
        "services/order.ts": (
            "export class OrderError extends Error {}\n"
            "\n"
            "export function createOrder(data: object): object {\n"
            "  try {\n"
            "    return { ...data, id: 1 };\n"
            "  } catch (e: unknown) {\n"
            "    if (e instanceof OrderError) {\n"
            "      throw e;\n"
            "    }\n"
            "    throw new Error(`Order creation failed: ${e}`);\n"
            "  }\n"
            "}\n"
        ),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.BROAD_EXCEPTION_MONOCULTURE,
            file_path="services/",
            should_detect=False,
            description="Typed catches with re-throw — not a broad exception monoculture",
        ),
    ],
)

EDS_TS_TRUE_POSITIVE = GroundTruthFixture(
    name="eds_ts_tp",
    description="Complex TS function without docs or tests → should fire EDS",
    files={
        "core/processor.ts": (
            "export function processBatch(\n"
            "  items: any[],\n"
            "  config: Record<string, any>,\n"
            "  retryCount: number = 3,\n"
            "  timeout: number = 30\n"
            "): any[] {\n"
            "  const results: any[] = [];\n"
            "  for (const item of items) {\n"
            "    if (item.type === 'A') {\n"
            "      if (item.priority > 5) {\n"
            "        results.push(handleHighPriority(item));\n"
            "      } else if (item.status === 'pending') {\n"
            "        results.push(handlePending(item));\n"
            "      } else {\n"
            "        results.push(handleDefault(item));\n"
            "      }\n"
            "    } else if (item.type === 'B') {\n"
            "      if (config.fastMode) {\n"
            "        results.push(fastProcess(item));\n"
            "      } else {\n"
            "        results.push(slowProcess(item));\n"
            "      }\n"
            "    } else {\n"
            "      if (retryCount > 0) {\n"
            "        results.push(...processBatch([item], config, retryCount - 1));\n"
            "      } else {\n"
            "        results.push(null);\n"
            "      }\n"
            "    }\n"
            "  }\n"
            "  return results.filter(r => r !== null);\n"
            "}\n"
            "\n"
            "function handleHighPriority(item: any): any { return item; }\n"
            "function handlePending(item: any): any { return item; }\n"
            "function handleDefault(item: any): any { return item; }\n"
            "function fastProcess(item: any): any { return item; }\n"
            "function slowProcess(item: any): any { return item; }\n"
        ),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.EXPLAINABILITY_DEFICIT,
            file_path="core/processor.ts",
            should_detect=True,
            description="High complexity (nested branches), no JSDoc, no test file",
        ),
    ],
)

EDS_TS_TRUE_NEGATIVE = GroundTruthFixture(
    name="eds_ts_tn",
    description="Well-documented simple TS function → should NOT fire EDS",
    files={
        "lib/format.ts": (
            "/**\n"
            " * Format a currency amount.\n"
            " * @param amount - The numeric amount\n"
            " * @param currency - ISO 4217 currency code\n"
            " * @returns Formatted string like '12.50 EUR'\n"
            " */\n"
            "export function formatCurrency(amount: number, currency: string = 'EUR'): string {\n"
            "  return `${amount.toFixed(2)} ${currency}`;\n"
            "}\n"
        ),
        "lib/format.spec.ts": (
            "import { formatCurrency } from './format';\n"
            "\n"
            "describe('formatCurrency', () => {\n"
            "  it('formats positive amounts', () => {\n"
            "    expect(formatCurrency(12.5)).toBe('12.50 EUR');\n"
            "  });\n"
            "  it('formats with custom currency', () => {\n"
            "    expect(formatCurrency(100, 'USD')).toBe('100.00 USD');\n"
            "  });\n"
            "});\n"
        ),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.EXPLAINABILITY_DEFICIT,
            file_path="lib/format.ts",
            should_detect=False,
            description="Simple function with JSDoc + test file — well explained",
        ),
    ],
)

MDS_TS_TRUE_POSITIVE = GroundTruthFixture(
    name="mds_ts_tp",
    description="Near-duplicate TS functions (copy-paste with minor changes) → should fire MDS",
    files={
        "utils/formatters.ts": (
            "export function formatCurrency(amount: number, currency: string = 'EUR'): string {\n"
            "  let prefix = '';\n"
            "  let absAmount = amount;\n"
            "  if (amount < 0) {\n"
            "    prefix = '-';\n"
            "    absAmount = Math.abs(amount);\n"
            "  }\n"
            "  const formatted = absAmount.toFixed(2);\n"
            "  const parts = formatted.split('.');\n"
            "  const integerPart = parts[0];\n"
            "  const decimalPart = parts[1];\n"
            "  return `${prefix}${integerPart}.${decimalPart} ${currency}`;\n"
            "}\n"
        ),
        "utils/money.ts": (
            "export function formatMoney(amount: number, currency: string = 'EUR'): string {\n"
            "  let prefix = '';\n"
            "  let absAmount = amount;\n"
            "  if (amount < 0) {\n"
            "    prefix = '-';\n"
            "    absAmount = Math.abs(amount);\n"
            "  }\n"
            "  const formatted = absAmount.toFixed(2);\n"
            "  const parts = formatted.split('.');\n"
            "  const integerPart = parts[0];\n"
            "  const decimalPart = parts[1];\n"
            "  return `${prefix}${integerPart}.${decimalPart} ${currency}`;\n"
            "}\n"
        ),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.MUTANT_DUPLICATE,
            file_path="utils/",
            should_detect=True,
            description="Near-identical functions across two TS files — copy-paste mutation",
        ),
    ],
)

MDS_TS_TRUE_NEGATIVE = GroundTruthFixture(
    name="mds_ts_tn",
    description="Distinct TS functions with different logic → should NOT fire MDS",
    files={
        "utils/validators.ts": (
            "export function validateEmail(email: string): boolean {\n"
            "  const regex = /^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/;\n"
            "  return regex.test(email);\n"
            "}\n"
        ),
        "utils/parsers.ts": (
            "export function parseDate(input: string): Date | null {\n"
            "  const timestamp = Date.parse(input);\n"
            "  if (isNaN(timestamp)) {\n"
            "    return null;\n"
            "  }\n"
            "  return new Date(timestamp);\n"
            "}\n"
        ),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.MUTANT_DUPLICATE,
            file_path="utils/",
            should_detect=False,
            description="Completely different functions — no duplication",
        ),
    ],
)

PFS_TS_TRUE_POSITIVE = GroundTruthFixture(
    name="pfs_ts_tp",
    description="Multiple incompatible error-handling patterns in one TS module → should fire PFS",
    files={
        "services/handler_a.ts": (
            "export function handleA(data: unknown): void {\n"
            "  try {\n"
            "    process(data);\n"
            "  } catch (e: unknown) {\n"
            "    if (e instanceof Error) {\n"
            "      throw new AppError(e.message);\n"
            "    }\n"
            "    throw e;\n"
            "  }\n"
            "}\n"
            "function process(data: unknown): void {}\n"
            "class AppError extends Error {}\n"
        ),
        "services/handler_b.ts": (
            "export function handleB(data: unknown): null | void {\n"
            "  try {\n"
            "    process(data);\n"
            "  } catch (e) {\n"
            "    console.error('Failed:', e);\n"
            "    return null;\n"
            "  }\n"
            "}\n"
            "function process(data: unknown): void {}\n"
        ),
        "services/handler_c.ts": (
            "export function handleC(data: unknown): void {\n"
            "  try {\n"
            "    process(data);\n"
            "  } catch (e) {\n"
            "    console.error('error', e);\n"
            "    process.exit(1);\n"
            "  }\n"
            "}\n"
            "function process(data: unknown): void {}\n"
        ),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.PATTERN_FRAGMENTATION,
            file_path="services/",
            should_detect=True,
            description="3 different error-handling patterns in TS services/",
        ),
    ],
)

PFS_TS_TRUE_NEGATIVE = GroundTruthFixture(
    name="pfs_ts_tn",
    description="Consistent error-handling pattern across TS module → should NOT fire PFS",
    files={
        "handlers/create.ts": (
            "import { AppError } from './errors';\n"
            "\n"
            "export function create(data: unknown): object {\n"
            "  try {\n"
            "    return { data };\n"
            "  } catch (e: unknown) {\n"
            "    if (e instanceof Error) {\n"
            "      throw new AppError(e.message);\n"
            "    }\n"
            "    throw e;\n"
            "  }\n"
            "}\n"
        ),
        "handlers/update.ts": (
            "import { AppError } from './errors';\n"
            "\n"
            "export function update(id: string, data: unknown): object {\n"
            "  try {\n"
            "    return { id, data };\n"
            "  } catch (e: unknown) {\n"
            "    if (e instanceof Error) {\n"
            "      throw new AppError(e.message);\n"
            "    }\n"
            "    throw e;\n"
            "  }\n"
            "}\n"
        ),
        "handlers/delete.ts": (
            "import { AppError } from './errors';\n"
            "\n"
            "export function remove(id: string): boolean {\n"
            "  try {\n"
            "    return true;\n"
            "  } catch (e: unknown) {\n"
            "    if (e instanceof Error) {\n"
            "      throw new AppError(e.message);\n"
            "    }\n"
            "    throw e;\n"
            "  }\n"
            "}\n"
        ),
        "handlers/errors.ts": (
            "export class AppError extends Error {\n"
            "  constructor(message: string) {\n"
            "    super(message);\n"
            "    this.name = 'AppError';\n"
            "  }\n"
            "}\n"
        ),
    },
    expected=[
        ExpectedFinding(
            signal_type=SignalType.PATTERN_FRAGMENTATION,
            file_path="handlers/",
            should_detect=False,
            description="Consistent re-throw via AppError across all handlers",
        ),
    ],
)


# Append NBV + BAT + PHR fixtures to ALL_FIXTURES
ALL_FIXTURES.extend(
    [
        NBV_VALIDATE_TP,
        NBV_ENSURE_TP,
        NBV_IS_HAS_TP,
        NBV_GET_OR_CREATE_TP,
        NBV_TRY_TP,
        NBV_TRUE_NEGATIVE,
        NBV_STUB_TN,
        NBV_TS_ASYNC_BOOL_TN,
        NBV_TS_ENSURE_UPSERT_TN,
        BAT_TRUE_POSITIVE,
        BAT_HIGH_DENSITY_TP,
        BAT_TRUE_NEGATIVE,
        BAT_TINY_FILE_TN,
        BAT_TEST_FILE_TN,
        # ── Boundary & Confounder fixtures ──
        MDS_BOUNDARY_TP,
        MDS_CONFOUNDER_TN,
        EDS_BOUNDARY_TP,
        EDS_BOUNDARY_TN,
        EDS_CONFOUNDER_TN,
        TVS_BOUNDARY_TP,
        TVS_CONFOUNDER_TN,
        SMS_BOUNDARY_TP,
        SMS_CONFOUNDER_TN,
        DIA_BOUNDARY_TP,
        TPD_BOUNDARY_TP,
        TPD_CONFOUNDER_TN,
        GCD_BOUNDARY_TP,
        COD_BOUNDARY_TP,
        COD_CONFOUNDER_TN,
        NBV_BOUNDARY_TP,
        NBV_CONFOUNDER_TN,
        BAT_BOUNDARY_TP,
        # ── New CONFOUNDER fixtures (FP-Strategie) ──
        BEM_CONFOUNDER_FLASK_TN,
        BEM_CONFOUNDER_CELERY_TN,
        BEM_CONFOUNDER_LOGGING_TN,
        BEM_CONFOUNDER_STRING_TN,
        DIA_CONFOUNDER_BADGE_TN,
        DIA_CONFOUNDER_HEADING_TN,
        DIA_CONFOUNDER_API_PATH_TN,
        GCD_CONFOUNDER_DISPATCH_TN,
        GCD_CONFOUNDER_FUNCTIONAL_TN,
        GCD_CONFOUNDER_SHORT_TN,
        BAT_CONFOUNDER_FEATURE_TOGGLE_TN,
        BAT_CONFOUNDER_TYPE_STUB_TN,
        BAT_CONFOUNDER_NOQA_CONFIG_TN,
        # ── Risk-Register FP mitigation fixtures (TN) ──
        MDS_TN_PACKAGE_LAZY_GETATTR,
        TPD_TN_NEGATIVE_ASSERT_INLINE,
        MAZ_TN_CLI_SERVING_PATH,
        HSC_TN_ML_TOKENIZER_CONSTANTS,
        NBV_TN_TRY_COMPARISON_HELPER,
        # ── New confounders + boundary/negative fixtures (drift precision) ──
        NBV_REPOSITORY_PATTERN_TN,
        TVS_NEW_FILE_TN,
        EDS_PROPERTY_TN,
        DIA_INLINE_CODE_TN,
        AVS_TEST_MOCK_TN,
        MDS_BOUNDARY_TN,
        NBV_BOUNDARY_TN,
        EDS_INIT_MEDIUM_TN,
        # ── CCC/COD/ECM coverage fixtures (v2.7 baseline) ──
        COD_BOUNDARY_TN,
        CCC_TRUE_POSITIVE,
        CCC_TRUE_NEGATIVE,
        CCC_CONFOUNDER_TN,
        CCC_BOUNDARY_TP,
        CCC_LARGE_COMMIT_TN,
        ECM_TRUE_NEGATIVE,
        ECM_TRUE_POSITIVE,
        ECM_CONFOUNDER_TN,
        # ── Phantom Reference (PHR) fixtures ──
        PHR_TRUE_POSITIVE,
        PHR_TRUE_NEGATIVE,
        PHR_STAR_IMPORT_TN,
        PHR_BUILTIN_TN,
        PHR_CROSS_FILE_TP,
        PHR_DYNAMIC_GETATTR_TN,
        PHR_COMPREHENSION_TN,
        PHR_LAMBDA_PARAM_TN,
        PHR_IMPORT_FROM_TP,
        PHR_DECORATOR_PHANTOM_TP,
        PHR_MULTI_PHANTOM_TP,
        PHR_TYPE_CHECKING_TN,
        PHR_PRIVATE_NAME_BOUNDARY,
        PHR_SINGLE_CHAR_BOUNDARY,
        PHR_PARENT_REEXPORT_TN,
        # ── PHR third-party import resolver fixtures (ADR-040) ──
        PHR_MISSING_PACKAGE_TP,
        PHR_OPTIONAL_DEP_TN,
        PHR_STDLIB_IMPORT_TN,
        PHR_TYPE_CHECKING_THIRD_PARTY_TN,
        PHR_MODULE_NOT_FOUND_ERROR_TN,
        # ── PHR runtime attribute validation fixtures (ADR-041) ──
        PHR_RUNTIME_MISSING_ATTR_TP,
        PHR_RUNTIME_VALID_ATTR_TN,
        PHR_RUNTIME_GUARDED_TN,
        # ── HSC scoring-promotion fixtures (ADR-040) ──
        HSC_GITHUB_TOKEN_TP,
        HSC_HIGH_ENTROPY_TP,
        HSC_ENV_READ_TN,
        HSC_PLACEHOLDER_TN,
        # ── FOE scoring-promotion fixtures (ADR-040) ──
        FOE_HIGH_IMPORT_TP,
        FOE_NORMAL_IMPORT_TN,
        FOE_BARREL_FILE_TN,
        # ── PHR additional fixtures (ADR-040) ──
        PHR_CONDITIONAL_IMPORT_TN,
        PHR_FRAMEWORK_DECORATOR_TN,
        # ── FP-Reduction fixtures (ADR-036/037/038) ──
        AVS_MODELS_OMNILAYER_TN,
        AVS_CONFOUNDER_DTO_TN,
        DIA_CUSTOM_AUXILIARY_TN,
        MDS_CONFOUNDER_PROTOCOL_METHODS_TN,
        MDS_CONFOUNDER_THIN_WRAPPER_TN,
        MDS_CONFOUNDER_NAME_DIVERSE_TN,
        # ── CXS / CCC / COD extended coverage ──
        CXS_TP_DEEP_NESTING,
        CXS_TN_FLAT_CODE,
        CXS_TP_MANY_ELIF,
        CXS_BOUNDARY_THRESHOLD,
        CXS_CONFOUNDER_ASYNC_LOOPS,
        CXS_CONFOUNDER_DECORATORS,
        CCC_TP_CROSS_LAYER,
        CCC_CONFOUNDER_BURST_TN,
        COD_CONFOUNDER_SINGLE_METHOD_TN,
        COD_CONFOUNDER_PROPERTY_ONLY_TN,
        COD_BOUNDARY_PARTIAL_COHESION,
        # ── ISD scoring-promotion fixtures (ADR-039) ──
        ISD_DJANGO_INSECURE_TP,
        ISD_VERIFY_FALSE_TP,
        ISD_SECURE_DJANGO_TN,
        ISD_VERIFY_FALSE_LOCALHOST_TN,
        ISD_IGNORE_DIRECTIVE_TN,
        # ── TypeScript ground-truth fixtures (Phase 1 — TS Parity) ──
        TSB_TS_TRUE_POSITIVE,
        TSB_TS_TRUE_NEGATIVE,
        NBV_TS_VALIDATE_TP,
        NBV_TS_TRUE_NEGATIVE,
        GCD_TS_TRUE_POSITIVE,
        GCD_TS_TRUE_NEGATIVE,
        TSA_CIRCULAR_TP,
        TSA_CLEAN_TN,
        # ── TypeScript ground-truth fixtures (Phase 2 — BEM/EDS/MDS/PFS) ──
        BEM_TS_TRUE_POSITIVE,
        BEM_TS_TRUE_NEGATIVE,
        EDS_TS_TRUE_POSITIVE,
        EDS_TS_TRUE_NEGATIVE,
        MDS_TS_TRUE_POSITIVE,
        MDS_TS_TRUE_NEGATIVE,
        PFS_TS_TRUE_POSITIVE,
        PFS_TS_TRUE_NEGATIVE,
    ]
)


FIXTURES_BY_SIGNAL: dict[SignalType, list[GroundTruthFixture]] = {}
for _fixture in ALL_FIXTURES:
    for _exp in _fixture.expected:
        FIXTURES_BY_SIGNAL.setdefault(_exp.signal_type, []).append(_fixture)


FIXTURES_BY_KIND: dict[FixtureKind, list[GroundTruthFixture]] = {kind: [] for kind in FixtureKind}
for _fixture in ALL_FIXTURES:
    FIXTURES_BY_KIND[_fixture.inferred_kind].append(_fixture)
