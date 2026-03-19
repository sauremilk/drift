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
from pathlib import Path


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
    mutations["pattern_fragmentation"] = pfs_mutations

    # =========================================================
    # EDS: Explainability Deficit - complex undocumented functions
    # =========================================================
    eds_mutations = []

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
        '                if discount.get("category") is None or discount["category"] == item.get("category"):\n'
        '                    price *= (1 - discount["value"] / 100)\n'
        '            elif discount["type"] == "fixed":\n'
        '                price -= discount["value"]\n'
        '            elif discount["type"] == "bogo":\n'
        "                if qty >= 2:\n"
        "                    qty = qty - qty // 2\n"
        "        subtotal = price * qty\n"
        "        for rule in tax_rules:\n"
        '            if rule["region"] == region:\n'
        '                if rule.get("category") is None or rule["category"] == item.get("category"):\n'
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
        '                    value = float(value) if value is not None else spec.get("default", 0.0)\n'
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
    mutations["temporal_volatility"] = tvs_mutations

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
            targets = ["calculate_pricing", "transform_dataset"]
            count = sum(1 for n in targets if any(n in f.get("title", "") for f in detected))
        else:
            count = min(len(detected), len(injected))

        recall = count / len(injected) if injected else 0.0
        results[signal] = {
            "injected": len(injected),
            "detected": count,
            "recall": recall,
            "finding_count": len(detected),
            "mutation_descriptions": injected,
            "finding_titles": [f.get("title", "?") for f in detected[:10]],
        }
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

    shutil.rmtree(tmpdir, ignore_errors=True)
    print(f"\nCleaned up {tmpdir}")


if __name__ == "__main__":
    main()
