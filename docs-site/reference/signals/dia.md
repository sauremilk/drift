# Doc-Implementation Drift Signal (DIA)

**Signal ID:** `DIA`
**Full name:** Doc-Implementation Drift
**Type:** Scoring signal (contributes to drift score)
**Default weight:** `0.04`
**Scope:** cross_file

---

## What DIA detects

DIA detects **divergence between architectural documentation and actual code** — when READMEs, ADRs, or architecture docs describe patterns, components, or conventions that don't match the implementation. Documentation drift is a reliability threat: teams make decisions based on outdated docs.

### Before — documentation doesn't match code

```markdown
<!-- README.md -->
## Architecture
The application uses a **three-layer architecture**:
- `routes/` — HTTP handlers
- `services/` — business logic
- `repositories/` — data access
```

But the actual code has:
```
src/
├── routes/
├── services/
├── repositories/
├── controllers/     ← not in docs
└── middleware/       ← not in docs
```

DIA flags the mismatch between documented and actual structure.

---

## Why doc-implementation drift matters

- **Docs become lies** — outdated documentation is worse than no documentation because it misleads.
- **Onboarding friction** — new team members follow the documented architecture, then discover reality differs.
- **AI generation worsens drift** — LLMs may follow the documentation rather than the current code, creating correct-per-docs but wrong-per-reality implementations.
- **Decision traceability breaks** — ADRs that no longer match implementation lose their value.

---

## How the score is calculated

DIA uses Markdown AST parsing to extract claims from documentation files, then validates them against the codebase:

1. **Extract claims** — component names, directory references, import patterns mentioned in docs.
2. **Validate against code** — check whether referenced directories, modules, and patterns actually exist.
3. **Score divergence** — higher scores for more claims that cannot be validated.

Optional: When embedding-based validation is enabled, DIA also checks semantic consistency between doc descriptions and code behavior.

**Severity thresholds:**

| Score range | Severity |
|-------------|----------|
| ≥ 0.7       | HIGH     |
| ≥ 0.5       | MEDIUM   |
| ≥ 0.3       | LOW      |
| < 0.3       | INFO     |

---

## How to fix DIA findings

1. **Update the documentation** — align docs with current reality.
2. **Or update the code** — if the documentation describes the intended architecture, refactor the code to match.
3. **Add a doc-review step** — include documentation review in PRs that change structure.
4. **Automate validation** — use DIA in CI to catch drift before it reaches production.

---

## Configuration

```yaml
# drift.yaml
weights:
  doc_impl_drift: 0.04   # default weight (0.0 to 1.0)
```

---

## Detection details

1. **Scan for documentation files** — README.md, ADRs, architecture docs.
2. **Parse Markdown AST** — extract references to directories, modules, and components.
3. **Resolve references** against the actual file system.
4. **Optionally use embeddings** for semantic comparison.
5. **Report unresolvable claims** as findings.

DIA is deterministic in its Markdown-AST mode. Embedding-based validation adds a semantic layer but may vary based on model.

---

## Related signals

- **EDS (Explainability Deficit)** — checks for documentation presence. DIA checks for documentation accuracy.
- **PHR (Phantom Reference)** — detects code references that can't be resolved. DIA detects documentation references that can't be resolved.
