#!/usr/bin/env python3
"""Controlled Mutation Benchmark for drift.

Creates a synthetic Python project with intentionally injected drift
patterns (one per signal), runs drift on it, and measures detection
recall per signal.

Each "mutation" is a known-bad pattern that drift SHOULD detect.
Detection Recall = (detected mutations) / (total injected mutations).
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class MutationEntity:
    """Single benchmark mutation with explicit metadata."""

    id: str
    signal: str
    description: str
    klass: str = "injected_positive"
    severity_expectation: str = "medium"
    must_detect: bool = True
    min_findings: int = 1
    rationale: str = ""


def _entity_id(signal: str, idx: int) -> str:
    abbrev = {
        "architecture_violation": "avs",
        "pattern_fragmentation": "pfs",
        "mutant_duplicate": "mds",
        "explainability_deficit": "eds",
        "temporal_volatility": "tvs",
        "system_misalignment": "sms",
        "doc_impl_drift": "dia",
        "broad_exception_monoculture": "bem",
        "test_polarity_deficit": "tpd",
        "guard_clause_deficit": "gcd",
        "naming_contract_violation": "nbv",
        "bypass_accumulation": "bat",
        "exception_contract_drift": "ecd",
    }.get(signal, signal)
    return f"{abbrev}_{idx:03d}"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _create_synthetic_repo(repo_dir: Path) -> dict[str, list[str]]:
    """Create a synthetic repo with known drift patterns.

    Returns a dict mapping signal_type -> list of injected mutation descriptions.
    """
    mutations: dict[str, list[str]] = {}

    src = repo_dir / "src" / "myapp"
    handlers = src / "handlers"
    models = src / "models"
    utils = src / "utils"
    tests = repo_dir / "tests"

    for d in [src, handlers, models, utils, tests]:
        d.mkdir(parents=True, exist_ok=True)
        _write(d / "__init__.py", "")

    # =========================================================
    # MDS: Mutant Duplicates - copy-paste functions
    # =========================================================
    mds_mutations = []

    dup_code = (
        "def process_order(order_id: int, user_id: int) -> dict:\n"
        '    """Process an order for a user."""\n'
        "    if order_id <= 0:\n"
        '        raise ValueError("Invalid order ID")\n'
        '    result = {"order_id": order_id, "user_id": user_id, "status": "processed"}\n'
        "    return result\n"
        "\n\n"
        "def validate_input(data: dict) -> bool:\n"
        '    """Validate incoming data."""\n'
        '    required = ["name", "email", "age"]\n'
        "    for field in required:\n"
        "        if field not in data:\n"
        "            return False\n"
        '    if not isinstance(data["age"], int) or data["age"] < 0:\n'
        "        return False\n"
        "    return True\n"
    )
    _write(src / "service_a.py", dup_code)
    _write(src / "service_b.py", dup_code)
    mds_mutations.append("Exact duplicate: process_order in service_a.py and service_b.py")
    mds_mutations.append("Exact duplicate: validate_input in service_a.py and service_b.py")

    _write(
        src / "handler_v1.py",
        "def fetch_user_data(user_id: int, db_session) -> dict:\n"
        '    """Fetch user data from database."""\n'
        '    query = f"SELECT * FROM users WHERE id = {user_id}"\n'
        "    result = db_session.execute(query)\n"
        "    rows = result.fetchall()\n"
        "    if not rows:\n"
        '        return {"error": "not found", "user_id": user_id}\n'
        "    user = rows[0]\n"
        "    return {\n"
        '        "id": user["id"],\n'
        '        "name": user["name"],\n'
        '        "email": user["email"],\n'
        '        "created_at": str(user["created_at"]),\n'
        "    }\n",
    )
    _write(
        src / "handler_v2.py",
        "def get_customer_info(customer_id: int, session) -> dict:\n"
        '    """Get customer info from database."""\n'
        '    sql = f"SELECT * FROM users WHERE id = {customer_id}"\n'
        "    res = session.execute(sql)\n"
        "    records = res.fetchall()\n"
        "    if not records:\n"
        '        return {"error": "not found", "customer_id": customer_id}\n'
        "    customer = records[0]\n"
        "    return {\n"
        '        "id": customer["id"],\n'
        '        "name": customer["name"],\n'
        '        "email": customer["email"],\n'
        '        "created_at": str(customer["created_at"]),\n'
        "    }\n",
    )
    mds_mutations.append("Near-duplicate: fetch_user_data ~ get_customer_info")

    # Additional MDS mutations: more near-duplicates with subtle variations
    _write(
        src / "report_v1.py",
        "def generate_report(data: list, title: str, format_type: str = 'html') -> str:\n"
        '    """Generate a report from data."""\n'
        "    output_lines = []\n"
        "    output_lines.append(f'<h1>{title}</h1>')\n"
        "    for item in data:\n"
        "        if format_type == 'html':\n"
        "            output_lines.append(f'<p>{item}</p>')\n"
        "        else:\n"
        "            output_lines.append(str(item))\n"
        "    return '\\n'.join(output_lines)\n",
    )
    _write(
        src / "report_v2.py",
        "def build_report(records: list, heading: str, output_format: str = 'html') -> str:\n"
        '    """Build a report from records."""\n'
        "    lines = []\n"
        "    lines.append(f'<h1>{heading}</h1>')\n"
        "    for record in records:\n"
        "        if output_format == 'html':\n"
        "            lines.append(f'<p>{record}</p>')\n"
        "        else:\n"
        "            lines.append(str(record))\n"
        "    return '\\n'.join(lines)\n",
    )
    mds_mutations.append("Near-duplicate: generate_report ~ build_report (renamed params)")

    _write(
        src / "cache_v1.py",
        "def get_cached_value(key: str, cache: dict, ttl: int = 300) -> object:\n"
        '    """Retrieve a value from cache with TTL check."""\n'
        "    import time\n"
        "    entry = cache.get(key)\n"
        "    if entry is None:\n"
        "        return None\n"
        "    timestamp, value = entry\n"
        "    if time.time() - timestamp > ttl:\n"
        "        del cache[key]\n"
        "        return None\n"
        "    return value\n",
    )
    _write(
        src / "cache_v2.py",
        "def lookup_cache(cache_key: str, store: dict, max_age: int = 300) -> object:\n"
        '    """Look up a value in the cache store."""\n'
        "    import time\n"
        "    item = store.get(cache_key)\n"
        "    if item is None:\n"
        "        return None\n"
        "    created_at, data = item\n"
        "    if time.time() - created_at > max_age:\n"
        "        del store[cache_key]\n"
        "        return None\n"
        "    return data\n",
    )
    mds_mutations.append("Near-duplicate: get_cached_value ~ lookup_cache (renamed vars)")

    _write(
        src / "serializer_a.py",
        "def serialize_user(user: dict) -> dict:\n"
        '    """Serialize user object for API response."""\n'
        "    result = {}\n"
        '    result["id"] = user.get("id")\n'
        '    result["name"] = user.get("name", "")\n'
        '    result["email"] = user.get("email", "")\n'
        '    result["active"] = user.get("is_active", True)\n'
        '    result["created"] = str(user.get("created_at", ""))\n'
        "    return result\n",
    )
    _write(
        src / "serializer_b.py",
        "def format_user_response(user_data: dict) -> dict:\n"
        '    """Format user data for API response."""\n'
        "    output = {}\n"
        '    output["id"] = user_data.get("id")\n'
        '    output["name"] = user_data.get("name", "")\n'
        '    output["email"] = user_data.get("email", "")\n'
        '    output["active"] = user_data.get("is_active", True)\n'
        '    output["created"] = str(user_data.get("created_at", ""))\n'
        "    return output\n",
    )
    mds_mutations.append("Near-duplicate: serialize_user ~ format_user_response")

    _write(
        src / "retry_a.py",
        "import time\n\n"
        "def retry_operation(func, max_retries: int = 3, delay: float = 1.0):\n"
        '    """Retry a function with exponential backoff."""\n'
        "    last_error = None\n"
        "    for attempt in range(max_retries):\n"
        "        try:\n"
        "            return func()\n"
        "        except Exception as e:\n"
        "            last_error = e\n"
        "            time.sleep(delay * (2 ** attempt))\n"
        "    raise last_error\n",
    )
    _write(
        src / "retry_b.py",
        "import time\n\n"
        "def with_retries(callable_fn, attempts: int = 3, wait: float = 1.0):\n"
        '    """Call a function with retry logic."""\n'
        "    last_exc = None\n"
        "    for try_num in range(attempts):\n"
        "        try:\n"
        "            return callable_fn()\n"
        "        except Exception as exc:\n"
        "            last_exc = exc\n"
        "            time.sleep(wait * (2 ** try_num))\n"
        "    raise last_exc\n",
    )
    mds_mutations.append("Near-duplicate: retry_operation ~ with_retries")

    mutations["mutant_duplicate"] = mds_mutations

    # =========================================================
    # PFS: Pattern Fragmentation - inconsistent error handling
    # =========================================================
    pfs_mutations = []

    _write(
        handlers / "auth.py",
        "import logging\n"
        "logger = logging.getLogger(__name__)\n\n"
        "def login(username: str, password: str) -> dict:\n"
        "    try:\n"
        "        if not username or not password:\n"
        '            raise ValueError("Missing credentials")\n'
        '        return {"token": "abc123", "user": username}\n'
        "    except ValueError as e:\n"
        '        logger.error(f"Login failed: {e}")\n'
        "        raise\n"
        "    except Exception as e:\n"
        '        logger.exception("Unexpected error in login")\n'
        '        raise RuntimeError("Internal error") from e\n',
    )
    _write(
        handlers / "orders.py",
        "class OrderError(Exception):\n"
        "    pass\n\n"
        "def create_order(items: list) -> dict:\n"
        "    if not items:\n"
        '        raise OrderError("No items provided")\n'
        "    try:\n"
        '        total = sum(item["price"] for item in items)\n'
        "    except (KeyError, TypeError):\n"
        '        raise OrderError("Invalid item format")\n'
        '    return {"order_id": 1, "total": total}\n',
    )
    _write(
        handlers / "payments.py",
        "from typing import Optional\n\n"
        "def process_payment(amount: float) -> dict:\n"
        '    result = {"success": False, "error": None}\n'
        "    if amount <= 0:\n"
        '        result["error"] = "Invalid amount"\n'
        "        return result\n"
        "    if amount > 10000:\n"
        '        result["error"] = "Amount exceeds limit"\n'
        "        return result\n"
        '    result["success"] = True\n'
        '    result["transaction_id"] = "txn_123"\n'
        "    return result\n",
    )
    _write(
        handlers / "notifications.py",
        "def send_notification(user_id: int, message: str) -> bool:\n"
        '    assert user_id > 0, "user_id must be positive"\n'
        '    assert message, "message must not be empty"\n'
        "    if len(message) > 1000:\n"
        "        return False\n"
        "    return True\n",
    )
    pfs_mutations.append("error_handling: 4 variants in handlers/")
    pfs_mutations.append("return_pattern: 3 variants in models/")

    # Additional PFS mutations: more pattern categories
    _write(
        handlers / "validation_a.py",
        "def validate_age(data: dict) -> bool:\n"
        "    try:\n"
        '        age = int(data["age"])\n'
        "        if age < 0 or age > 150:\n"
        '            raise ValueError("Invalid age")\n'
        "        return True\n"
        "    except (ValueError, KeyError) as e:\n"
        '        raise ValidationError(str(e)) from e\n',
    )
    _write(
        handlers / "validation_b.py",
        "def validate_name(data: dict) -> dict:\n"
        '    errors = []\n'
        '    if "name" not in data:\n'
        '        errors.append("name is required")\n'
        '    elif len(data["name"]) < 2:\n'
        '        errors.append("name too short")\n'
        '    return {"valid": len(errors) == 0, "errors": errors}\n',
    )
    _write(
        handlers / "validation_c.py",
        "import logging\n"
        "logger = logging.getLogger(__name__)\n\n"
        "def validate_email(data: dict) -> bool:\n"
        "    try:\n"
        '        email = data["email"]\n'
        '        if "@" not in email:\n'
        "            return False\n"
        "        return True\n"
        "    except KeyError:\n"
        '        logger.warning("email field missing")\n'
        "        return False\n",
    )
    pfs_mutations.append("error_handling: 3 validation variants in handlers/")

    # More PFS: logging pattern fragmentation in services
    services = src / "services"
    services.mkdir(parents=True, exist_ok=True)
    _write(services / "__init__.py", "")
    _write(
        services / "email_service.py",
        "import logging\n"
        "logger = logging.getLogger(__name__)\n\n"
        "def send_email(to: str, subject: str, body: str) -> bool:\n"
        "    try:\n"
        '        logger.info(f"Sending email to {to}")\n'
        "        return True\n"
        "    except Exception as e:\n"
        '        logger.exception(f"Email send failed: {e}")\n'
        "        raise\n",
    )
    _write(
        services / "sms_service.py",
        "def send_sms(phone: str, message: str) -> bool:\n"
        "    try:\n"
        '        print(f"Sending SMS to {phone}")\n'
        "        return True\n"
        "    except Exception as e:\n"
        '        print(f"SMS failed: {e}")\n'
        "        return False\n",
    )
    _write(
        services / "push_service.py",
        "import sys\n\n"
        "def send_push(device_id: str, payload: dict) -> bool:\n"
        "    try:\n"
        "        return True\n"
        "    except Exception:\n"
        '        sys.stderr.write("Push notification failed\\n")\n'
        "        return False\n",
    )
    pfs_mutations.append("error_handling: 3 notification service variants in services/")

    # PFS: data access pattern fragmentation
    _write(
        models / "product.py",
        "def get_product(product_id: int):\n"
        '    """Returns product or None."""\n'
        "    if product_id <= 0:\n"
        "        return None\n"
        '    return {"id": product_id, "name": "Widget"}\n',
    )
    _write(
        models / "order.py",
        "def get_order(order_id: int) -> dict:\n"
        '    """Returns order or raises."""\n'
        "    if order_id <= 0:\n"
        '        raise ValueError("Invalid order_id")\n'
        '    return {"id": order_id, "items": []}\n\n'
        "def get_order_result(order_id: int) -> tuple:\n"
        '    """Returns (order, error) tuple."""\n'
        "    if order_id <= 0:\n"
        '        return None, "Invalid order_id"\n'
        '    return {"id": order_id, "items": []}, None\n',
    )
    pfs_mutations.append("return_pattern: 3 data access variants in models/")

    mutations["pattern_fragmentation"] = pfs_mutations

    # =========================================================
    # EDS: Explainability Deficit - complex undocumented functions
    # =========================================================
    eds_mutations = []

    # Original models/user.py (also used by PFS)
    _write(
        models / "user.py",
        "def get_user(user_id: int):\n"
        '    """Returns user dict or None."""\n'
        "    if user_id <= 0:\n"
        "        return None\n"
        '    return {"id": user_id, "name": "Alice"}\n\n'
        "def get_user_or_raise(user_id: int) -> dict:\n"
        '    """Returns user dict or raises."""\n'
        "    if user_id <= 0:\n"
        '        raise ValueError("Invalid user_id")\n'
        '    return {"id": user_id, "name": "Alice"}\n\n'
        "def get_user_result(user_id: int) -> tuple:\n"
        '    """Returns (user, error) tuple."""\n'
        "    if user_id <= 0:\n"
        '        return None, "Invalid user_id"\n'
        '    return {"id": user_id, "name": "Alice"}, None\n',
    )

    complex_code = (
        "def calculate_pricing(items, user, discounts, tax_rules, shipping, region):\n"
        "    total = 0\n"
        "    for item in items:\n"
        '        price = item["price"]\n'
        '        qty = item.get("quantity", 1)\n'
        '        if user.get("premium"):\n'
        '            if item.get("category") == "electronics":\n'
        "                price *= 0.9\n"
        '            elif item.get("category") == "books":\n'
        "                price *= 0.85\n"
        "            else:\n"
        "                price *= 0.95\n"
        "        for discount in discounts:\n"
        '            if discount["type"] == "percentage":\n'
        '                if discount.get("category") is None '
        'or discount["category"] == item.get("category"):\n'
        '                    price *= (1 - discount["value"] / 100)\n'
        '            elif discount["type"] == "fixed":\n'
        '                price -= discount["value"]\n'
        '            elif discount["type"] == "bogo":\n'
        "                if qty >= 2:\n"
        "                    qty = qty - qty // 2\n"
        "        subtotal = price * qty\n"
        "        for rule in tax_rules:\n"
        '            if rule["region"] == region:\n'
        '                if rule.get("category") is None '
        'or rule["category"] == item.get("category"):\n'
        '                    subtotal *= (1 + rule["rate"])\n'
        "                    break\n"
        "        total += subtotal\n"
        "    if shipping:\n"
        '        if total > shipping.get("free_threshold", float("inf")):\n'
        "            pass\n"
        '        elif region in shipping.get("premium_regions", []):\n'
        '            total += shipping["premium_rate"]\n'
        "        else:\n"
        '            total += shipping["standard_rate"]\n'
        "    return round(total, 2)\n"
        "\n\n"
        "def transform_dataset(records, schema, mappings, filters, aggregations):\n"
        "    result = []\n"
        "    for record in records:\n"
        "        transformed = {}\n"
        "        for field, spec in schema.items():\n"
        "            source = mappings.get(field, field)\n"
        "            value = record.get(source)\n"
        '            if spec.get("type") == "int":\n'
        "                try:\n"
        '                    value = int(value) if value is not None else spec.get("default", 0)\n'
        "                except (ValueError, TypeError):\n"
        '                    value = spec.get("default", 0)\n'
        '            elif spec.get("type") == "float":\n'
        "                try:\n"
        '                    value = float(value) if value is not None '
        'else spec.get("default", 0.0)\n'
        "                except (ValueError, TypeError):\n"
        '                    value = spec.get("default", 0.0)\n'
        '            elif spec.get("type") == "str":\n'
        '                value = str(value) if value is not None else spec.get("default", "")\n'
        '                if spec.get("max_length"):\n'
        '                    value = value[:spec["max_length"]]\n'
        '            elif spec.get("type") == "bool":\n'
        '                value = bool(value) if value is not None else spec.get("default", False)\n'
        "            transformed[field] = value\n"
        "        skip = False\n"
        "        for f in filters:\n"
        '            fval = transformed.get(f["field"])\n'
        '            if f["op"] == "eq" and fval != f["value"]:\n'
        "                skip = True\n"
        '            elif f["op"] == "gt" and (fval is None or fval <= f["value"]):\n'
        "                skip = True\n"
        '            elif f["op"] == "lt" and (fval is None or fval >= f["value"]):\n'
        "                skip = True\n"
        '            elif f["op"] == "in" and fval not in f["value"]:\n'
        "                skip = True\n"
        "        if not skip:\n"
        "            result.append(transformed)\n"
        "    if aggregations:\n"
        "        agg_result = {}\n"
        "        for agg in aggregations:\n"
        '            field = agg["field"]\n'
        "            values = [r.get(field, 0) for r in result if r.get(field) is not None]\n"
        '            if agg["func"] == "sum":\n'
        '                agg_result[f"{field}_sum"] = sum(values)\n'
        '            elif agg["func"] == "avg":\n'
        '                agg_result[f"{field}_avg"] = sum(values) / len(values) if values else 0\n'
        '            elif agg["func"] == "count":\n'
        '                agg_result[f"{field}_count"] = len(values)\n'
        '            elif agg["func"] == "max":\n'
        '                agg_result[f"{field}_max"] = max(values) if values else None\n'
        '            elif agg["func"] == "min":\n'
        '                agg_result[f"{field}_min"] = min(values) if values else None\n'
        "        return agg_result\n"
        "    return result\n"
    )
    _write(src / "complex_logic.py", complex_code)
    eds_mutations.append("Unexplained complexity: calculate_pricing (CC>=12, no docstring)")
    eds_mutations.append("Unexplained complexity: transform_dataset (CC>=15, no docstring)")

    # Additional EDS mutations: more complex undocumented functions
    _write(
        src / "scheduler.py",
        "def schedule_tasks(tasks, workers, priorities, constraints, deadlines):\n"
        "    assigned = {w: [] for w in workers}\n"
        "    for task in sorted(tasks, key=lambda t: priorities.get(t['id'], 0), reverse=True):\n"
        "        best_worker = None\n"
        "        best_load = float('inf')\n"
        "        for worker in workers:\n"
        "            if worker in constraints.get(task['id'], {}).get('excluded', []):\n"
        "                continue\n"
        "            load = sum(t.get('weight', 1) for t in assigned[worker])\n"
        "            if load < best_load:\n"
        "                best_load = load\n"
        "                best_worker = worker\n"
        "        if best_worker is not None:\n"
        "            deadline = deadlines.get(task['id'])\n"
        "            if deadline and len(assigned[best_worker]) > 5:\n"
        "                assigned[best_worker].insert(0, task)\n"
        "            else:\n"
        "                assigned[best_worker].append(task)\n"
        "    return assigned\n",
    )
    eds_mutations.append("Unexplained complexity: schedule_tasks (CC>=10, no docstring)")

    _write(
        src / "reconciler.py",
        "def reconcile_accounts(local_records, remote_records, rules, tolerances):\n"
        "    mismatches = []\n"
        "    matched = set()\n"
        "    for local in local_records:\n"
        "        for remote in remote_records:\n"
        "            if remote['id'] in matched:\n"
        "                continue\n"
        "            if local.get('ref') == remote.get('ref'):\n"
        "                diff = abs(local.get('amount', 0) - remote.get('amount', 0))\n"
        "                tolerance = tolerances.get(local.get('type'), 0.01)\n"
        "                if diff > tolerance:\n"
        "                    if rules.get('strict'):\n"
        "                        mismatches.append({'local': local, "
        "'remote': remote, 'diff': diff})\n"
        "                    elif diff > tolerance * 10:\n"
        "                        mismatches.append({'local': local, "
        "'remote': remote, 'diff': diff})\n"
        "                matched.add(remote['id'])\n"
        "                break\n"
        "    unmatched_local = [r for r in local_records if r.get('ref') "
        "not in {rm.get('ref') for rm in remote_records}]\n"
        "    unmatched_remote = [r for r in remote_records if r['id'] not in matched]\n"
        "    return {'mismatches': mismatches, 'unmatched_local': "
        "unmatched_local, 'unmatched_remote': unmatched_remote}\n",
    )
    eds_mutations.append("Unexplained complexity: reconcile_accounts (CC>=10, no docstring)")

    _write(
        src / "migration.py",
        "def migrate_schema(tables, column_defs, constraints, indexes, dry_run=False):\n"
        "    operations = []\n"
        "    for table_name, columns in tables.items():\n"
        "        for col_name, col_spec in columns.items():\n"
        "            new_spec = column_defs.get(table_name, {}).get(col_name)\n"
        "            if new_spec is None:\n"
        "                operations.append(('drop_column', table_name, col_name))\n"
        "            elif new_spec != col_spec:\n"
        "                if new_spec.get('type') != col_spec.get('type'):\n"
        "                    operations.append(('alter_column', table_name, col_name, new_spec))\n"
        "                elif new_spec.get('nullable') != col_spec.get('nullable'):\n"
        "                    operations.append(('alter_null', table_name, col_name, new_spec))\n"
        "        for col_name, new_spec in column_defs.get(table_name, {}).items():\n"
        "            if col_name not in columns:\n"
        "                operations.append(('add_column', table_name, col_name, new_spec))\n"
        "    for table_name, idx_list in indexes.items():\n"
        "        for idx in idx_list:\n"
        "            if idx.get('unique'):\n"
        "                operations.append(('create_unique_index', table_name, idx))\n"
        "            else:\n"
        "                operations.append(('create_index', table_name, idx))\n"
        "    if dry_run:\n"
        "        return operations\n"
        "    return [('execute', op) for op in operations]\n",
    )
    eds_mutations.append("Unexplained complexity: migrate_schema (CC>=12, no docstring)")

    _write(
        src / "event_router.py",
        "def route_events(events, handlers, middleware, fallback_handler):\n"
        "    results = []\n"
        "    for event in events:\n"
        "        handled = False\n"
        "        for mw in middleware:\n"
        "            event = mw(event)\n"
        "            if event is None:\n"
        "                handled = True\n"
        "                break\n"
        "        if handled:\n"
        "            continue\n"
        "        for pattern, handler in handlers.items():\n"
        "            if event.get('type') == pattern or pattern == '*':\n"
        "                try:\n"
        "                    result = handler(event)\n"
        "                    results.append(result)\n"
        "                    handled = True\n"
        "                except Exception as e:\n"
        "                    results.append({'error': str(e), 'event': event})\n"
        "                    handled = True\n"
        "                break\n"
        "        if not handled and fallback_handler:\n"
        "            results.append(fallback_handler(event))\n"
        "    return results\n",
    )
    eds_mutations.append("Unexplained complexity: route_events (CC>=10, no docstring)")

    _write(
        src / "permission_checker.py",
        "def check_permissions(user, resource, action, policies, overrides):\n"
        "    if user.get('role') == 'admin':\n"
        "        return True\n"
        "    override = overrides.get(user.get('id'), {}).get(resource)\n"
        "    if override is not None:\n"
        "        return override\n"
        "    for policy in policies:\n"
        "        if policy.get('resource') != resource:\n"
        "            continue\n"
        "        if action not in policy.get('actions', []):\n"
        "            continue\n"
        "        if policy.get('role') and policy['role'] != user.get('role'):\n"
        "            continue\n"
        "        if policy.get('condition') == 'owner':\n"
        "            if user.get('id') != resource.get('owner_id'):\n"
        "                continue\n"
        "        elif policy.get('condition') == 'department':\n"
        "            if user.get('dept') != resource.get('dept'):\n"
        "                continue\n"
        "        return policy.get('allow', True)\n"
        "    return False\n",
    )
    eds_mutations.append("Unexplained complexity: check_permissions (CC>=10, no docstring)")

    mutations["explainability_deficit"] = eds_mutations

    # =========================================================
    # AVS: Architecture Violations - cross-layer imports
    # =========================================================
    avs_mutations = []

    _write(
        models / "enriched.py",
        "from src.myapp.handlers.auth import login\n"
        "from src.myapp.handlers.orders import create_order\n\n"
        "def enrich_user_model(user_id: int) -> dict:\n"
        '    token = login("admin", "secret")\n'
        '    order = create_order([{"price": 10}])\n'
        '    return {"user_id": user_id, "token": token, "order": order}\n',
    )
    avs_mutations.append("Upward import: models/enriched.py imports from handlers/")

    _write(
        utils / "helpers.py",
        "from src.myapp.models.enriched import enrich_user_model\n\n"
        "def quick_setup(user_id: int) -> dict:\n"
        "    return enrich_user_model(user_id)\n",
    )
    avs_mutations.append("Transitive violation: utils/ -> models/ -> handlers/")

    # Additional AVS mutations
    _write(
        models / "analytics.py",
        "from src.myapp.handlers.payments import process_payment\n\n"
        "def enrich_analytics(data: dict) -> dict:\n"
        '    result = process_payment(data.get("amount", 0))\n'
        '    data["payment_result"] = result\n'
        "    return data\n",
    )
    avs_mutations.append("Upward import: models/analytics.py imports from handlers/payments")

    _write(
        models / "report.py",
        "from src.myapp.handlers.notifications import send_notification\n\n"
        "def generate_and_notify(user_id: int, report: dict) -> bool:\n"
        '    return send_notification(user_id, str(report))\n',
    )
    avs_mutations.append("Upward import: models/report.py imports from handlers/notifications")

    # Circular dependency
    _write(
        handlers / "shared.py",
        "from src.myapp.handlers.auth import login\n\n"
        "def get_auth_token(user: str) -> dict:\n"
        '    return login(user, "default")\n',
    )
    _write(
        src / "services" / "user_ops.py",
        "from src.myapp.handlers.shared import get_auth_token\n"
        "from src.myapp.models.user import get_user\n\n"
        "def authenticated_user(user_id: int) -> dict:\n"
        "    user = get_user(user_id)\n"
        '    token = get_auth_token(user.get("name", ""))\n'
        "    return {**user, **token}\n",
    )
    avs_mutations.append("Cross-layer: services/ imports from handlers/ (upward)")

    # ----- AVS: Circular dependency (3-module cycle) -----
    cycle_dir = src / "cycle"
    cycle_dir.mkdir(parents=True, exist_ok=True)
    _write(cycle_dir / "__init__.py", "")
    _write(
        cycle_dir / "alpha.py",
        "from src.myapp.cycle.gamma import gamma_fn\n\n"
        "def alpha_fn():\n"
        "    return gamma_fn()\n",
    )
    _write(
        cycle_dir / "beta.py",
        "from src.myapp.cycle.alpha import alpha_fn\n\n"
        "def beta_fn():\n"
        "    return alpha_fn()\n",
    )
    _write(
        cycle_dir / "gamma.py",
        "from src.myapp.cycle.beta import beta_fn\n\n"
        "def gamma_fn():\n"
        "    return beta_fn()\n",
    )
    avs_mutations.append("Circular dependency: cycle/alpha → beta → gamma → alpha (3-cycle)")

    # ----- AVS: High blast radius (central module with many dependents) -----
    blast_dir = src / "blast"
    blast_dir.mkdir(parents=True, exist_ok=True)
    _write(blast_dir / "__init__.py", "")
    _write(
        blast_dir / "core.py",
        "def core_function(): return 42\n",
    )
    for i in range(1, 7):
        _write(
            blast_dir / f"user_{i}.py",
            f"from src.myapp.blast.core import core_function\n\n"
            f"def use_{i}(): return core_function() + {i}\n",
        )
    avs_mutations.append(
        "High blast radius: blast/core.py (6 dependents)"
    )

    # ----- AVS: Zone of Pain (concrete, stable, many dependents) -----
    pain_dir = src / "pain"
    pain_dir.mkdir(parents=True, exist_ok=True)
    _write(pain_dir / "__init__.py", "")
    _write(
        pain_dir / "core.py",
        "# Concrete module with no abstractions\n"
        "DATA = {'version': 1}\n\n"
        "def get_data(): return DATA.copy()\n"
        "def set_data(k, v): DATA[k] = v\n",
    )
    for i in range(1, 4):
        _write(
            pain_dir / f"consumer_{i}.py",
            f"from src.myapp.pain.core import get_data\n\n"
            f"def consume_{i}(): return get_data()\n",
        )
    avs_mutations.append(
        "Zone of Pain: pain/core.py (I=0.0, D=1.0, 3 dependents, concrete)"
    )

    # ----- AVS: God module (high fan-in + fan-out) -----
    god_dir = src / "god"
    god_dir.mkdir(parents=True, exist_ok=True)
    _write(god_dir / "__init__.py", "")
    _write(god_dir / "dep_a.py", "def dep_a(): return 'a'\n")
    _write(god_dir / "dep_b.py", "def dep_b(): return 'b'\n")
    _write(god_dir / "dep_c.py", "def dep_c(): return 'c'\n")
    _write(
        god_dir / "central.py",
        "from src.myapp.god.dep_a import dep_a\n"
        "from src.myapp.god.dep_b import dep_b\n"
        "from src.myapp.god.dep_c import dep_c\n\n"
        "def orchestrate(): return dep_a() + dep_b() + dep_c()\n",
    )
    for i in range(1, 4):
        _write(
            god_dir / f"client_{i}.py",
            f"from src.myapp.god.central import orchestrate\n\n"
            f"def client_{i}(): return orchestrate()\n",
        )
    avs_mutations.append(
        "God module: god/central.py (Ca=3, Ce=3, total=6, br=3)"
    )

    # ----- AVS: Unstable dependency (stable → volatile) -----
    udep_dir = src / "udep"
    udep_dir.mkdir(parents=True, exist_ok=True)
    _write(udep_dir / "__init__.py", "")
    # Volatile target: many outgoing deps, few incoming → high I
    _write(udep_dir / "ext_1.py", "EXT_1 = 1\n")
    _write(udep_dir / "ext_2.py", "EXT_2 = 2\n")
    _write(udep_dir / "ext_3.py", "EXT_3 = 3\n")
    _write(
        udep_dir / "volatile_target.py",
        "from src.myapp.udep.ext_1 import EXT_1\n"
        "from src.myapp.udep.ext_2 import EXT_2\n"
        "from src.myapp.udep.ext_3 import EXT_3\n\n"
        "def volatile_fn(): return EXT_1 + EXT_2 + EXT_3\n",
    )
    # Stable source: many incoming, few outgoing → low I
    _write(
        udep_dir / "stable_src.py",
        "from src.myapp.udep.volatile_target import volatile_fn\n\n"
        "def stable_fn(): return volatile_fn()\n",
    )
    _write(
        udep_dir / "user_1.py",
        "from src.myapp.udep.stable_src import stable_fn\n\n"
        "def use_1(): return stable_fn()\n",
    )
    _write(
        udep_dir / "user_2.py",
        "from src.myapp.udep.stable_src import stable_fn\n\n"
        "def use_2(): return stable_fn()\n",
    )
    avs_mutations.append(
        "Unstable dependency: udep/stable_src (I=0.33) → volatile_target (I=0.75)"
    )

    mutations["architecture_violation"] = avs_mutations

    # =========================================================
    # SMS: System Misalignment - unusual dependency structure
    # =========================================================
    sms_mutations = []

    _write(
        src / "outlier_module.py",
        "import ast\nimport dis\nimport ctypes\nimport struct\n"
        "import mmap\nimport multiprocessing\n"
        "import xml.etree.ElementTree as ET\n\n"
        "def low_level_optimization(code: str) -> bytes:\n"
        "    tree = ast.parse(code)\n"
        '    compiled = compile(tree, "<string>", "exec")\n'
        "    bytecode = dis.Bytecode(compiled)\n"
        '    raw = struct.pack("I", len(list(bytecode)))\n'
        "    return raw\n",
    )
    sms_mutations.append("Novel deps: outlier_module.py uses ctypes/struct/mmap in web app")

    _write(
        src / "ml_predictor.py",
        "import tensorflow as tf\nimport pandas as pd\nimport scipy\n"
        "import numpy as np\n\n"
        "def predict_churn(user_data: dict) -> float:\n"
        "    features = np.array([user_data.get('age', 0), user_data.get('tenure', 0)])\n"
        "    return float(features.mean())\n",
    )
    sms_mutations.append("Novel deps: ml_predictor.py uses tensorflow/pandas/scipy in web app")

    _write(
        src / "crypto_util.py",
        "import hmac\nimport secrets\nimport ssl\n"
        "from cryptography.fernet import Fernet\n\n"
        "def encrypt_payload(data: bytes) -> bytes:\n"
        "    key = Fernet.generate_key()\n"
        "    f = Fernet(key)\n"
        "    return f.encrypt(data)\n",
    )
    sms_mutations.append("Novel deps: crypto_util.py uses cryptography/ssl/hmac in web app")

    mutations["system_misalignment"] = sms_mutations

    # Add "normal" modules to establish baseline for SMS comparison
    for name in ["config", "database", "cache", "logging_setup"]:
        _write(
            src / f"{name}.py",
            f"import os\nimport json\nimport logging\n\n"
            f"logger = logging.getLogger(__name__)\n\n"
            f"def setup_{name}():\n"
            f"    logger.info('Setting up {name}')\n"
            f"    return {{'status': 'ok'}}\n",
        )

    # =========================================================
    # DIA: Doc-Implementation Drift - README vs code mismatch
    # =========================================================
    dia_mutations = []

    _write(
        repo_dir / "README.md",
        "# MyApp\n\n"
        "A web application with the following components:\n\n"
        "- `src/myapp/` - Main application code\n"
        "- `src/myapp/handlers/` - Request handlers\n"
        "- `src/myapp/models/` - Data models\n"
        "- `src/myapp/utils/` - Utility functions\n"
        "- `src/myapp/views/` - Template views (Jinja2)\n"
        "- `src/myapp/middleware/` - Request middleware\n"
        "- `src/myapp/plugins/` - Plugin system\n"
        "- `tests/` - Test suite\n",
    )
    dia_mutations.append("Phantom dir: README references views/ (does not exist)")
    dia_mutations.append("Phantom dir: README references middleware/ (does not exist)")
    dia_mutations.append("Phantom dir: README references plugins/ (does not exist)")

    # Additional DIA: ADR file with outdated claims
    adr_dir = repo_dir / "docs" / "adr"
    adr_dir.mkdir(parents=True, exist_ok=True)
    _write(
        adr_dir / "001-architecture.md",
        "# ADR 001: Architecture\n\n"
        "## Decision\n\n"
        "The project uses a layered architecture:\n\n"
        "- `src/myapp/controllers/` — HTTP controllers\n"
        "- `src/myapp/repositories/` — Data access layer\n"
        "- `src/myapp/domain/` — Domain entities\n",
    )
    dia_mutations.append("Phantom dir: ADR references controllers/ (does not exist)")
    dia_mutations.append("Phantom dir: ADR references repositories/ (does not exist)")
    dia_mutations.append("Phantom dir: ADR references domain/ (does not exist)")

    mutations["doc_impl_drift"] = dia_mutations

    # =========================================================
    # TVS: Temporal Volatility - requires git history
    # =========================================================
    tvs_mutations = []

    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=repo_dir, capture_output=True
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_dir, capture_output=True)

    # Use recent dates so TVS --since 365 window captures them
    from datetime import datetime, timedelta

    base_date = datetime.now() - timedelta(days=30)

    hotspot = src / "hotspot.py"
    for i in range(10):
        hotspot.write_text(
            f"# Version {i}\ndef unstable_function():\n    return {i}\n\n"
            f"def also_changes():\n    x = {i * 10}\n    return x + {i}\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "add", str(hotspot)], cwd=repo_dir, capture_output=True)
        commit_date = (base_date + timedelta(days=i)).strftime("%Y-%m-%dT12:00:00")
        env = os.environ.copy()
        env["GIT_AUTHOR_DATE"] = commit_date
        env["GIT_COMMITTER_DATE"] = commit_date
        subprocess.run(
            ["git", "commit", "-m", f"Update hotspot v{i}"],
            cwd=repo_dir,
            capture_output=True,
            env=env,
        )
    tvs_mutations.append("High volatility: hotspot.py (10 commits in 10 days)")

    # Additional TVS: another volatile file
    hotspot2 = src / "config_hotspot.py"
    for i in range(8):
        hotspot2.write_text(
            f"# Config v{i}\nSETTINGS = {{'version': {i}, 'debug': {i % 2 == 0}}}\n\n"
            f"def get_config():\n    return SETTINGS\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "add", str(hotspot2)], cwd=repo_dir, capture_output=True)
        commit_date = (base_date + timedelta(days=i)).strftime("%Y-%m-%dT14:00:00")
        env = os.environ.copy()
        env["GIT_AUTHOR_DATE"] = commit_date
        env["GIT_COMMITTER_DATE"] = commit_date
        subprocess.run(
            ["git", "commit", "-m", f"Update config v{i}"],
            cwd=repo_dir,
            capture_output=True,
            env=env,
        )
    tvs_mutations.append("High volatility: config_hotspot.py (8 commits in 8 days)")

    mutations["temporal_volatility"] = tvs_mutations

    # =========================================================
    # AVS (continued): Co-change coupling — requires git history
    # =========================================================
    # Two files changed together in 5 commits, no import edge between them.
    co_a = src / "co_file_a.py"
    co_b = src / "co_file_b.py"
    for i in range(5):
        co_a.write_text(
            f"# Revision {i}\n"
            f"def co_a_fn(): return {i}\n",
            encoding="utf-8",
        )
        co_b.write_text(
            f"# Revision {i}\n"
            f"def co_b_fn(): return {i * 10}\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "add", str(co_a), str(co_b)], cwd=repo_dir, capture_output=True)
        commit_date = (base_date + timedelta(days=12 + i)).strftime("%Y-%m-%dT16:00:00")
        env = os.environ.copy()
        env["GIT_AUTHOR_DATE"] = commit_date
        env["GIT_COMMITTER_DATE"] = commit_date
        subprocess.run(
            ["git", "commit", "-m", f"Update co-files v{i}"],
            cwd=repo_dir,
            capture_output=True,
            env=env,
        )

    mutations.setdefault("architecture_violation", []).append(
        "Co-change coupling: co_file_a.py ↔ co_file_b.py (5 co-commits, no import)"
    )

    # Test files
    _write(
        tests / "test_services.py",
        "def test_process_order():\n"
        "    from src.myapp.service_a import process_order\n"
        "    result = process_order(1, 1)\n"
        '    assert result["status"] == "processed"\n\n'
        "def test_validate_input():\n"
        "    from src.myapp.service_a import validate_input\n"
        '    assert validate_input({"name": "a", "email": "b", "age": 1})\n',
    )

    return mutations


def _run_drift(repo_dir: Path) -> dict:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "drift",
            "analyze",
            "--repo",
            str(repo_dir),
            "--format",
            "json",
            "--since",
            "365",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        print(f"drift stderr: {result.stderr[:500]}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"Failed to parse: {result.stdout[:500]}")
        return {}


def _check_detection(mutations, findings):
    findings_by_signal = {}
    for f in findings:
        sig = f.get("signal", f.get("signal_type", ""))
        findings_by_signal.setdefault(sig, []).append(f)

    results = {}
    for signal, injected in mutations.items():
        detected = findings_by_signal.get(signal, [])

        if signal == "doc_impl_drift":
            flagged = {
                f.get("metadata", {}).get("referenced_dir", "")
                for f in detected
                if "missing" in f.get("title", "").lower()
            }
            count = sum(1 for m in injected if any(d in m for d in flagged))
        elif signal == "temporal_volatility":
            hits = [
                f
                for f in detected
                if "hotspot" in str(f.get("title", "")).lower()
                or "hotspot" in str(f.get("file", "")).lower()
            ]
            count = min(len(hits), len(injected))
        elif signal == "explainability_deficit":
            targets = [
                "calculate_pricing", "transform_dataset",
                "schedule_tasks", "reconcile_accounts",
                "migrate_schema", "route_events", "check_permissions",
            ]
            count = sum(1 for n in targets if any(n in f.get("title", "") for f in detected))
        elif signal == "architecture_violation":
            # Precise per-mutation-type matching for AVS diagnostics
            avs_detail = {}
            titles_lower = [f.get("title", "").lower() for f in detected]

            # Upward layer imports (check for "upward" keyword)
            upward_count = sum(1 for t in titles_lower if "upward" in t)
            # Circular dependency
            circular_count = sum(1 for t in titles_lower if "circular" in t)
            # Blast radius
            blast_count = sum(1 for t in titles_lower if "blast radius" in t)
            # Zone of Pain
            pain_count = sum(1 for t in titles_lower if "zone of pain" in t)
            # God module
            god_count = sum(1 for t in titles_lower if "god module" in t)
            # Unstable dependency
            unstable_count = sum(1 for t in titles_lower if "unstable dependency" in t)
            # Hidden coupling (co-change)
            cochange_count = sum(1 for t in titles_lower if "hidden coupling" in t)
            # Policy violations
            policy_count = sum(1 for t in titles_lower if "policy violation" in t)

            avs_detail = {
                "upward_layer": upward_count,
                "circular_deps": circular_count,
                "blast_radius": blast_count,
                "zone_of_pain": pain_count,
                "god_module": god_count,
                "unstable_dep": unstable_count,
                "co_change": cochange_count,
                "policy": policy_count,
            }

            # Match mutations to detected categories
            # Check more specific patterns FIRST to avoid false matches
            count = 0
            for m in injected:
                ml = m.lower()
                if "circular" in ml:
                    if circular_count > 0:
                        count += 1
                        circular_count -= 1
                elif "blast radius" in ml:
                    if blast_count > 0:
                        count += 1
                        blast_count -= 1
                elif "zone of pain" in ml:
                    if pain_count > 0:
                        count += 1
                        pain_count -= 1
                elif "god module" in ml:
                    if god_count > 0:
                        count += 1
                        god_count -= 1
                elif "unstable dependency" in ml:
                    if unstable_count > 0:
                        count += 1
                        unstable_count -= 1
                elif "co-change" in ml:
                    if cochange_count > 0:
                        count += 1
                        cochange_count -= 1
                elif "upward" in ml or "cross-layer" in ml or "transitive" in ml:
                    if upward_count > 0:
                        count += 1
                        upward_count -= 1
        else:
            count = min(len(detected), len(injected))

        recall = count / len(injected) if injected else 0.0
        result_entry = {
            "injected": len(injected),
            "detected": count,
            "recall": recall,
            "finding_count": len(detected),
            "mutation_descriptions": injected,
            "finding_titles": [f.get("title", "?") for f in detected[:20]],
        }
        if signal == "architecture_violation":
            result_entry["avs_detail"] = avs_detail
        results[signal] = result_entry
    return results


def main():
    tmpdir = tempfile.mkdtemp(prefix="drift_mutation_")
    repo_dir = Path(tmpdir) / "synthetic_repo"
    repo_dir.mkdir()

    print(f"Creating synthetic repo in {repo_dir}")
    mutations = _create_synthetic_repo(repo_dir)

    total_injected = sum(len(v) for v in mutations.values())
    print(f"\nInjected {total_injected} mutations across {len(mutations)} signals:")
    for sig, muts in mutations.items():
        print(f"  {sig}: {len(muts)}")
        for m in muts:
            print(f"    - {m}")

    print("\nRunning drift analyze...")
    result = _run_drift(repo_dir)

    if not result:
        print("ERROR: drift produced no output")
        shutil.rmtree(tmpdir, ignore_errors=True)
        sys.exit(1)

    findings = result.get("findings", [])
    print(f"\ndrift found {len(findings)} findings total")

    detection = _check_detection(mutations, findings)

    print("\n" + "=" * 70)
    print("CONTROLLED MUTATION BENCHMARK RESULTS")
    print("=" * 70)

    total_det = 0
    total_mut = 0
    order = [
        "pattern_fragmentation",
        "architecture_violation",
        "mutant_duplicate",
        "temporal_volatility",
        "explainability_deficit",
        "system_misalignment",
        "doc_impl_drift",
    ]

    print(f"\n{'Signal':<25s} {'Injected':>8s} {'Detected':>8s} {'Recall':>8s}")
    print("-" * 55)
    for sig in order:
        if sig in detection:
            d = detection[sig]
            total_det += d["detected"]
            total_mut += d["injected"]
            print(f"{sig:<25s} {d['injected']:>8d} {d['detected']:>8d} {d['recall']:>7.0%}")

    overall = total_det / total_mut if total_mut else 0
    print("-" * 55)
    print(f"{'TOTAL':<25s} {total_mut:>8d} {total_det:>8d} {overall:>7.0%}")

    output_path = Path("benchmark_results") / "mutation_benchmark.json"
    output_path.parent.mkdir(exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "mutations": mutations,
                "detection": detection,
                "total_injected": total_mut,
                "total_detected": total_det,
                "overall_recall": overall,
                "drift_output": result,
            },
            f,
            indent=2,
            default=str,
        )
    print(f"\nSaved to {output_path}")

    print("\n\nDETAILED DETECTION:")
    for sig, d in detection.items():
        print(f"\n--- {sig} ---")
        print(f"  Injected ({d['injected']}):")
        for m in d["mutation_descriptions"]:
            print(f"    - {m}")
        print(f"  Findings ({d['finding_count']}):")
        for t in d["finding_titles"]:
            print(f"    - {t}")
        if "avs_detail" in d:
            print("  AVS Detection Breakdown:")
            for cat, cnt in d["avs_detail"].items():
                print(f"    {cat}: {cnt}")

    shutil.rmtree(tmpdir, ignore_errors=True)
    print(f"\nCleaned up {tmpdir}")


if __name__ == "__main__":
    main()
