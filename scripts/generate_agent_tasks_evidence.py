#!/usr/bin/env python
"""Generate feature evidence for agent-tasks phase 1-4 feature."""

import json
from pathlib import Path

from drift.analyzer import analyze_repo
from drift.output.agent_tasks import analysis_to_agent_tasks

# Analyze the repo
analysis = analyze_repo(Path('.'))

# Get agent tasks with new fields
agent_tasks = analysis_to_agent_tasks(analysis)

# Create feature evidence
evidence = {
    "feature": "agent-tasks-phase-1-4",
    "timestamp": analysis.analyzed_at.isoformat(),
    "description": (
        "Feature: automation fitness classification, "
        "do-not-over-fix constraints, repair maturity matrix"
    ),
    "summary": {
        "total_tasks_generated": len(agent_tasks),
        "tasks_with_automation_fit_high": sum(
            1 for t in agent_tasks if t.automation_fit == "high"
        ),
        "tasks_with_automation_fit_medium": sum(
            1 for t in agent_tasks if t.automation_fit == "medium"
        ),
        "tasks_with_automation_fit_low": sum(
            1 for t in agent_tasks if t.automation_fit == "low"
        ),
        "all_tasks_have_constraints": all(len(t.constraints) > 0 for t in agent_tasks),
        "all_tasks_have_repair_maturity": all(
            t.repair_maturity in ("verified", "experimental", "indirect-only")
            for t in agent_tasks
        ),
        "verified_signal_tasks": sum(
            1 for t in agent_tasks if t.repair_maturity == "verified"
        ),
        "experimental_signal_tasks": sum(
            1 for t in agent_tasks if t.repair_maturity == "experimental"
        ),
        "indirect_only_tasks": sum(
            1 for t in agent_tasks if t.repair_maturity == "indirect-only"
        ),
    },
    "sample_tasks": []
}

# Sample first 3 tasks
for t in agent_tasks[:3]:
    evidence["sample_tasks"].append({
        "id": t.id,
        "signal_type": t.signal_type,
        "severity": t.severity.value,
        "title": t.title,
        "automation_fit": t.automation_fit,
        "review_risk": t.review_risk,
        "change_scope": t.change_scope,
        "verification_strength": t.verification_strength,
        "repair_maturity": t.repair_maturity,
        "constraints_count": len(t.constraints),
        "success_criteria_count": len(t.success_criteria),
    })

# Write to file
output_path = Path("benchmark_results/v0.7.5_agent_tasks_feature_evidence.json")
output_path.parent.mkdir(parents=True, exist_ok=True)

with open(output_path, "w") as f:
    json.dump(evidence, f, indent=2)

print(f"Evidence written to {output_path}")
print("\nSummary:")
print(f"  Total tasks: {evidence['summary']['total_tasks_generated']}")
print(f"  High automation_fit: {evidence['summary']['tasks_with_automation_fit_high']}")
print(f"  Medium automation_fit: {evidence['summary']['tasks_with_automation_fit_medium']}")
print(f"  Low automation_fit: {evidence['summary']['tasks_with_automation_fit_low']}")
print(f"  All have constraints: {evidence['summary']['all_tasks_have_constraints']}")
print(f"  All have repair_maturity: {evidence['summary']['all_tasks_have_repair_maturity']}")
