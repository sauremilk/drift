# awesome-static-analysis PR Draft

## Target Repository

**Primary:** https://github.com/analysis-tools-dev/static-analysis

**Fallback:** https://github.com/vintasoftware/python-linters-and-code-analysis (if primary rejects)

---

## PR Title

```
Add drift — architectural erosion detector for Python
```

## PR Description

```markdown
### Tool: drift

- **Homepage:** https://github.com/sauremilk/drift
- **Package:** https://pypi.org/project/drift-analyzer/
- **License:** MIT
- **Language analyzed:** Python (experimental TypeScript support)

### What it does

drift is a deterministic static analyzer focused on cross-file architectural
coherence in Python repositories. It detects pattern fragmentation, architecture
boundary violations, near-duplicate code (AST-structural), explainability
deficit, temporal volatility, and system misalignment.

### Why it belongs here

drift addresses a gap not covered by existing tools in this list:
- Unlike linters (pylint, flake8, ruff): drift detects cross-file architectural
  patterns, not per-file rule violations.
- Unlike security scanners (Semgrep, CodeQL): drift measures structural
  coherence, not security vulnerabilities.
- Unlike copy-paste detectors (jscpd, CPD): drift uses AST-structural
  comparison with a composite scoring model.

### Evidence

- Benchmarked on 15 real-world repositories (Django, FastAPI, Pydantic, etc.)
- 97.3% strict precision on 263 ground-truth-labeled findings
- Full study with methodology: https://github.com/sauremilk/drift/blob/master/STUDY.md
- GitHub Action + SARIF output for CI integration

### Suggested entry

Category: Python

```yaml
- name: drift
  categories: [code-quality, architecture]
  languages: [python]
  description: >
    Detect architectural erosion in Python codebases. Measures pattern
    fragmentation, architecture violations, mutant duplicates, explainability
    deficit, temporal volatility, and system misalignment. Deterministic,
    no LLM in the pipeline.
  homepage: https://github.com/sauremilk/drift
  license: MIT
```
```

---

## Fallback: awesome-python PR

**Target:** https://github.com/vinta/awesome-python

**Section:** Code Analysis

**PR Title:** `Add drift to Code Analysis section`

**Entry:**

```markdown
* [drift](https://github.com/sauremilk/drift) - Detect architectural erosion
  and cross-file coherence problems in Python codebases. Deterministic, no LLM
  in the pipeline.
```

---

## Additional Targets (lower priority)

| List | Section | Status |
|------|---------|--------|
| [awesome-python-code-quality](https://github.com/vintasoftware/python-linters-and-code-analysis) | Static Analysis | Candidate |
| [awesome-flake8-extensions](https://github.com/DmytroLitvinov/awesome-flake8-extensions) | N/A (drift is not a flake8 extension) | Skip |
