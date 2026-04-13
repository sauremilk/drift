# Python API (`drift.api`)

`drift.api` is the supported Python entry point for agent and automation workflows.

Use it when you want structured `dict` responses and direct Python integration,
without shelling out to the CLI.

## Stability Contract

The stable public surface is exported in `drift.api.STABLE_API` and includes:

- `brief`
- `scan`
- `diff`
- `fix_plan`
- `nudge`
- `negative_context`
- `explain`
- `validate`
- `verify`
- `shadow_verify`
- `drift_map`
- `to_json`

Backward-compatible symbols in `drift.api.LEGACY_API` remain importable for
compatibility, but new integrations should use only `STABLE_API`.

## Deprecation Policy (`drift.api`)

For symbols in `STABLE_API`:

- no silent removal in a SemVer minor release
- deprecations are announced with a warning and changelog entry first
- removal happens only in a major release after at least one minor release with a deprecation warning

## Function Reference

All functions below return JSON-serializable `dict` payloads.

### `brief`

```python
brief(
    path: str | Path = ".",
    *,
    task: str,
    scope_override: str | None = None,
    signals: list[str] | None = None,
    max_guardrails: int = 10,
    include_non_operational: bool = False,
    on_progress: ProgressCallback | None = None,
    response_profile: str | None = None,
) -> dict[str, Any]
```

```python
from drift.api import brief

result = brief(path=".", task="refactor auth module")
print(result["risk"]["level"])
```

### `scan`

```python
scan(
    path: str | Path = ".",
    *,
    target_path: str | None = None,
    since_days: int = 90,
    signals: list[str] | None = None,
    exclude_signals: list[str] | None = None,
    max_findings: int = 10,
    max_per_signal: int | None = None,
    response_detail: str = "concise",
    strategy: str = "diverse",
    include_non_operational: bool = False,
    on_progress: Callable[[str, int, int], None] | None = None,
    response_profile: str | None = None,
) -> dict[str, Any]
```

```python
from drift.api import scan

result = scan(path=".", max_findings=5)
print(result["drift_score"], result["severity"])
```

### `diff`

```python
diff(
    path: str | Path = ".",
    *,
    diff_ref: str = "HEAD~1",
    uncommitted: bool = False,
    staged_only: bool = False,
    baseline_file: str | None = None,
    target_path: str | None = None,
    max_findings: int = 10,
    response_detail: str = "concise",
    signals: list[str] | None = None,
    exclude_signals: list[str] | None = None,
    response_profile: str | None = None,
) -> dict[str, Any]
```

```python
from drift.api import diff

result = diff(path=".", uncommitted=True)
print(result["accept_change"], result["blocking_reasons"])
```

### `fix_plan`

```python
fix_plan(
    path: str | Path = ".",
    *,
    finding_id: str | None = None,
    signal: str | None = None,
    max_tasks: int = 5,
    automation_fit_min: str | None = None,
    target_path: str | None = None,
    exclude_paths: list[str] | None = None,
    include_deferred: bool = False,
    include_non_operational: bool = False,
    on_progress: ProgressCallback | None = None,
    response_profile: str | None = None,
) -> dict[str, Any]
```

```python
from drift.api import fix_plan

result = fix_plan(path=".", max_tasks=3)
print(result["tasks"][0]["id"] if result["tasks"] else "no tasks")
```

### `nudge`

```python
nudge(
    path: str | Path = ".",
    *,
    changed_files: list[str] | None = None,
    uncommitted: bool = True,
    signals: list[str] | None = None,
    exclude_signals: list[str] | None = None,
    response_profile: str | None = None,
    task_signal: str | None = None,
    task_edit_kind: str | None = None,
    task_context_class: str | None = None,
) -> dict[str, Any]
```

```python
from drift.api import nudge

result = nudge(path=".", changed_files=["src/drift/api/scan.py"])
print(result["direction"], result["safe_to_commit"])
```

### `negative_context`

```python
negative_context(
    path: str | Path = ".",
    *,
    scope: str | None = None,
    target_file: str | None = None,
    max_items: int = 10,
    since_days: int = 90,
    disable_embeddings: bool = False,
    response_profile: str | None = None,
) -> dict[str, Any]
```

```python
from drift.api import negative_context

result = negative_context(path=".", scope="module", max_items=5)
print(result["items_returned"])
```

### `explain`

```python
explain(
    topic: str,
    *,
    repo_path: str | Path | None = None,
    response_profile: str | None = None,
) -> dict[str, Any]
```

```python
from drift.api import explain

result = explain("PFS", repo_path=".")
print(result["type"], result["signal"])
```

### `validate`

```python
validate(
    path: str | Path = ".",
    *,
    config_file: str | None = None,
    baseline_file: str | None = None,
    response_profile: str | None = None,
) -> dict[str, Any]
```

```python
from drift.api import validate

result = validate(path=".")
print(result["valid"], result["git_available"])
```

### `verify`

```python
verify(
    path: str | Path = ".",
    *,
    ref: str | None = None,
    uncommitted: bool = True,
    staged_only: bool = False,
    fail_on: str = "high",
    baseline: str | None = None,
    scope_files: list[str] | None = None,
    response_profile: str | None = None,
) -> dict[str, Any]
```

```python
from drift.api import verify

result = verify(path=".", uncommitted=True, fail_on="high")
print(result["pass"], result["blocking_reasons"])
```

### `shadow_verify`

```python
shadow_verify(
    path: str | Path = ".",
    *,
    scope_files: list[str] | None = None,
    uncommitted: bool = True,
    response_profile: str | None = None,
) -> dict[str, Any]
```

```python
from drift.api import shadow_verify

result = shadow_verify(path=".", scope_files=["src/drift/api/scan.py"])
print(result["shadow_clean"], result["safe_to_merge"])
```

### `drift_map`

```python
drift_map(
    path: str | Path = ".",
    *,
    target_path: str | None = None,
    max_modules: int = 50,
) -> dict[str, Any]
```

```python
from drift.api import drift_map

result = drift_map(path=".", target_path="src/drift")
print(result["stats"])
```

### `to_json`

```python
to_json(obj: Any) -> str
```

```python
from drift.api import scan, to_json

result = scan(path=".", max_findings=3)
payload = to_json(result)
print(payload[:120])
```

## Minimal End-To-End Script (15 lines)

```python
from drift.api import brief, scan

task = "reduce coupling in API module"
briefing = brief(path=".", task=task)

print("risk:", briefing["risk"]["level"])
print("guardrails:", len(briefing.get("guardrails", [])))

scan_result = scan(
    path=".",
    max_findings=5,
    response_detail="concise",
)

print("score:", scan_result["drift_score"])
print("severity:", scan_result["severity"])
print("accept_change:", scan_result["accept_change"])
```