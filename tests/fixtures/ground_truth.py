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

import enum
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

from drift.models import SignalType


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
                "Consistent decorator pattern (framework routes) "
                "must not produce a PFS finding"
            ),
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
        "small/tiny.py": "\n".join(
            [f"x = {i}  # type: ignore" for i in range(10)]
        ),
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


# Append NBV + BAT fixtures to ALL_FIXTURES
ALL_FIXTURES.extend([
    NBV_VALIDATE_TP,
    NBV_ENSURE_TP,
    NBV_IS_HAS_TP,
    NBV_GET_OR_CREATE_TP,
    NBV_TRY_TP,
    NBV_TRUE_NEGATIVE,
    NBV_STUB_TN,
    BAT_TRUE_POSITIVE,
    BAT_HIGH_DENSITY_TP,
    BAT_TRUE_NEGATIVE,
    BAT_TINY_FILE_TN,
    BAT_TEST_FILE_TN,
])


FIXTURES_BY_SIGNAL: dict[SignalType, list[GroundTruthFixture]] = {}
for _fixture in ALL_FIXTURES:
    for _exp in _fixture.expected:
        FIXTURES_BY_SIGNAL.setdefault(_exp.signal_type, []).append(_fixture)


FIXTURES_BY_KIND: dict[FixtureKind, list[GroundTruthFixture]] = {
    kind: [] for kind in FixtureKind
}
for _fixture in ALL_FIXTURES:
    FIXTURES_BY_KIND[_fixture.inferred_kind].append(_fixture)
