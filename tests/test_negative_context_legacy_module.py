from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from drift.models import Finding, NegativeContextScope, Severity, SignalType


@pytest.fixture(scope="module")
def legacy_nc_module():
    repo_root = Path(__file__).resolve().parents[1]
    mod_path = repo_root / "src" / "drift" / "negative_context.py"
    spec = importlib.util.spec_from_file_location("drift.negative_context_legacy", mod_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _finding(
    signal: SignalType, *, file_path: str = "src/x.py", metadata: dict | None = None
) -> Finding:
    return Finding(
        signal_type=signal,
        severity=Severity.HIGH,
        score=0.7,
        title="t",
        description="d",
        file_path=Path(file_path),
        start_line=10,
        end_line=20,
        related_files=[Path("src/y.py")],
        symbol="sym",
        fix="do this",
        metadata=metadata or {},
    )


def test_legacy_helpers_and_policy(legacy_nc_module) -> None:
    assert legacy_nc_module._sanitize("a\n\rb") == "a b"
    covered = legacy_nc_module._policy_covered_signal_types()
    assert isinstance(covered, set)
    uncovered = legacy_nc_module._policy_uncovered_signal_types()
    assert uncovered <= {"phantom_reference", "type_safety_bypass"}

    nid = legacy_nc_module._neg_id(
        "pattern_fragmentation", _finding(SignalType.PATTERN_FRAGMENTATION)
    )
    assert nid.startswith("neg-")

    affected = legacy_nc_module._affected(_finding(SignalType.PATTERN_FRAGMENTATION))
    assert "src/x.py" in affected
    assert "src/y.py" in affected


@pytest.mark.parametrize(
    "signal",
    [
        SignalType.TEST_POLARITY_DEFICIT,
        SignalType.DOC_IMPL_DRIFT,
        SignalType.MISSING_AUTHORIZATION,
        SignalType.EXPLAINABILITY_DEFICIT,
        SignalType.BROAD_EXCEPTION_MONOCULTURE,
        SignalType.EXCEPTION_CONTRACT_DRIFT,
        SignalType.ARCHITECTURE_VIOLATION,
        SignalType.CO_CHANGE_COUPLING,
        SignalType.HARDCODED_SECRET,
        SignalType.PATTERN_FRAGMENTATION,
        SignalType.MUTANT_DUPLICATE,
        SignalType.INSECURE_DEFAULT,
        SignalType.NAMING_CONTRACT_VIOLATION,
        SignalType.GUARD_CLAUSE_DEFICIT,
        SignalType.DEAD_CODE_ACCUMULATION,
        SignalType.CIRCULAR_IMPORT,
        SignalType.FAN_OUT_EXPLOSION,
        SignalType.TEMPORAL_VOLATILITY,
        SignalType.SYSTEM_MISALIGNMENT,
        SignalType.TS_ARCHITECTURE,
        SignalType.BYPASS_ACCUMULATION,
        SignalType.COGNITIVE_COMPLEXITY,
        SignalType.COHESION_DEFICIT,
    ],
)
def test_legacy_generators_return_negative_context(signal: SignalType, legacy_nc_module) -> None:
    finding = _finding(
        signal,
        metadata={
            "function_name": "fn",
            "auth_mechanisms_in_module": ["Depends(get_current_user)"],
            "framework": "fastapi",
            "endpoint": "/api/x",
            "boundary": "module",
            "raw_snippet": "except Exception: pass",
            "exception_type": "Exception",
            "current_layer": "api",
            "forbidden_import": "db.repo",
            "detected_forbidden_imports": ["db.repo"],
            "cluster_size": 3,
            "n_duplicated_functions": 2,
            "setting_name": "DEBUG",
            "violation_type": "snake_case mismatch",
            "cycle": ["a", "b"],
            "import_count": 12,
            "module": "src/x.py",
            "change_frequency_30d": 5,
            "recent_commits": 3,
            "expected_contract": "service",
            "actual_behavior": "controller",
            "source": "ui",
            "target": "infra",
            "rule": "ui->infra forbidden",
            "complexity": 42,
        },
    )

    out = legacy_nc_module.findings_to_negative_context([finding])
    assert out
    item = out[0]
    assert item.anti_pattern_id
    assert item.description
    assert item.forbidden_pattern
    assert item.canonical_alternative


def test_legacy_scope_filter_target_and_fallback(legacy_nc_module) -> None:
    specific = _finding(SignalType.PATTERN_FRAGMENTATION)
    many_related = _finding(
        SignalType.PATTERN_FRAGMENTATION,
        metadata={},
    )
    many_related.related_files = [Path("a.py"), Path("b.py"), Path("c.py")]

    items = legacy_nc_module.findings_to_negative_context([specific, many_related], scope="file")
    assert all(i.scope == NegativeContextScope.FILE for i in items)

    target = legacy_nc_module.findings_to_negative_context([specific], target_file="src/x.py")
    assert len(target) == 1

    # Unknown signal should use fallback with metadata policy marker.
    unknown = Finding(
        signal_type="non_existing_signal",
        severity=Severity.LOW,
        score=0.2,
        title="fallback",
        description="fallback-desc",
        file_path=Path("src/fallback.py"),
        start_line=1,
        end_line=2,
        related_files=[],
        fix="fix",
        metadata={},
    )
    fallback_items = legacy_nc_module.findings_to_negative_context([unknown], max_items=5)
    assert fallback_items
    assert fallback_items[0].metadata.get("fallback_policy") in {
        "explicit_fallback_only",
        "implicit_missing_policy",
    }

    payload = legacy_nc_module.negative_context_to_dict(fallback_items[0])
    assert payload["anti_pattern_id"]
    assert payload["description"] == "fallback-desc"
