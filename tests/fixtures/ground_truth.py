"""Ground-truth fixture definitions for precision/recall measurement.

Each fixture defines a minimal codebase with known TP, FP, and FN
expectations per signal type. Fixtures are deterministic — no git,
no embeddings, no external deps required.
"""

from __future__ import annotations

import textwrap
from dataclasses import dataclass, field
from pathlib import Path

from drift.models import SignalType


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


# ── Registry of all fixtures ─────────────────────────────────────────────

ALL_FIXTURES: list[GroundTruthFixture] = [
    PFS_TRUE_POSITIVE,
    PFS_TRUE_NEGATIVE,
    AVS_TRUE_POSITIVE,
    AVS_TRUE_NEGATIVE,
    AVS_CIRCULAR_TP,
    MDS_TRUE_POSITIVE,
    MDS_TRUE_NEGATIVE,
    EDS_TRUE_POSITIVE,
    EDS_TRUE_NEGATIVE,
    TVS_TRUE_POSITIVE,
    TVS_TRUE_NEGATIVE,
    SMS_TRUE_POSITIVE,
    SMS_TRUE_NEGATIVE,
    DIA_TRUE_POSITIVE,
    DIA_TRUE_NEGATIVE,
]

FIXTURES_BY_SIGNAL: dict[SignalType, list[GroundTruthFixture]] = {}
for _fixture in ALL_FIXTURES:
    for _exp in _fixture.expected:
        FIXTURES_BY_SIGNAL.setdefault(_exp.signal_type, []).append(_fixture)
