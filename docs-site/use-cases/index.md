# Use Cases

> Concrete scenarios where drift provides actionable insight.
> Each case follows the pattern: Problem → Solution with drift → Command → What you see.

---

## 1. Pattern Fragmentation in a Connector Layer

**Problem:** A service has 4+ API connectors. Each implements error handling
differently — bare `except`, custom exceptions, retry decorators, silent
fallbacks. Code reviews don't catch this because each file looks fine in
isolation.

**Solution:** drift's PFS signal detects that the same concern is implemented
N different ways within a directory.

```bash
drift analyze --repo . --sort-by impact --max-findings 5
```

**What you see:** A PFS finding with score 0.96:
"26 error_handling variants in connectors/" — listing every file that diverges.

**Next step:** Agree on one error-handling pattern, extract a shared base, and
refactor the outliers.

---

## 2. Architecture Boundary Violation

**Problem:** A database model file imports directly from the API layer, creating
a hidden circular dependency. Tests still pass, but test isolation is fragile
and refactoring becomes risky.

**Solution:** drift's AVS signal detects imports that cross defined or inferred
layer boundaries.

```bash
drift check --fail-on high
```

**What you see:** AVS finding — "DB import in API layer at src/api/auth.py:18".
CI blocks the merge until the import direction is fixed.

**Next step:** Move the shared type or function to a neutral module (e.g.
`shared/types.py`) and update both layers to import from there.

---

## 3. Duplicate Utility Code from AI Scaffolding

**Problem:** AI code generation created 6 identical `_run_async()` helper
functions across separate Celery task files instead of finding the existing
shared utility.

**Solution:** drift's MDS signal detects near-identical functions with AST
structural similarity ≥ 0.80.

```bash
drift analyze --repo . --format json | python -c "
import json, sys
for f in json.load(sys.stdin)['findings']:
    if f['signal'] == 'mutant_duplicates':
        print(f['title'], f['location'])
"
```

**What you see:** MDS findings listing all 6 locations with similarity scores
≥ 0.95.

**Next step:** Extract the function into a shared module
(e.g. `tasks/utils.py`) and replace all copies.

---

## 4. Complex Undocumented Functions

**Problem:** A rapidly growing codebase has accumulated several functions with
8+ parameters, deep nesting, and no docstrings. New team members spend hours
understanding them before making changes.

**Solution:** drift's EDS signal flags functions whose complexity exceeds a
threshold while lacking documentation.

```bash
drift analyze --repo . --sort-by score --max-findings 10
```

**What you see:** EDS findings with score ≥ 0.7 pointing to specific functions
and their file locations.

**Next step:** Add docstrings and type annotations to the flagged functions, or
refactor them into smaller, self-documenting units.

---

## 5. Monitoring Drift Score in CI

**Problem:** The team wants to track whether their codebase is getting more or
less coherent over time, without blocking PRs on day one.

**Solution:** Use drift in report-only mode in the GitHub Actions pipeline.

```yaml
# .github/workflows/drift.yml
name: Drift
on: [push, pull_request]
jobs:
  drift:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: mick-gsk/drift@v2
        with:
          fail-on: none
          upload-sarif: "true"
```

**What you see:** Findings appear as PR annotations in GitHub Code Scanning.
The drift score is logged in the action output for trend tracking.

**Next step:** After reviewing findings for 2–3 sprints, tighten the gate:
`fail-on: high`.

---

## 6. Running drift on a Demo Project

**Problem:** You want to see what drift output looks like before running it on
a production codebase.

**Solution:** The repository includes a demo project with intentional drift
patterns.

```bash
git clone https://github.com/mick-gsk/drift.git
cd drift/examples/demo-project
pip install -q drift-analyzer
drift analyze --repo .
```

**What you see:** Findings for pattern fragmentation (PFS), architecture
violation (AVS), and mutant duplicates (MDS) — all intentionally planted.

**Next step:** Try on your own repository: `drift analyze --repo /path/to/your/project`.

---

## Further Reading

- [Architecture Drift Detection for Python](architecture-drift-python.md)
- [Architectural Linter for AI Coding Teams](architectural-linter-ai-teams.md)
- [CI Architecture Checks with SARIF](ci-architecture-checks-sarif.md)
- [Architectural Technical Debt in AI-Assisted Codebases](technical-debt-ai-codebases.md)
