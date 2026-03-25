# Show HN: drift — Architectural linter for Python that detects AI-induced code erosion

**URL:** https://github.com/sauremilk/drift

---

## Post Text

I built a static analyzer that measures how much AI-generated code erodes your
codebase architecture over time.

The problem: Copilot, Cursor, and ChatGPT optimize for the prompt context, not
the codebase context. Code passes CI — but error handling fragments across 4
patterns, import boundaries erode, and near-identical functions accumulate with
subtle differences.

drift runs 6 deterministic signals (pattern fragmentation, architecture
violations, mutant duplicates, explainability deficit, temporal volatility,
system misalignment) — all AST-based, no LLM in the pipeline. It produces a
composite score designed for weekly trend tracking.

Benchmarked on 15 real-world repositories including Django, FastAPI, and
Pydantic. 97.3% strict precision on 263 ground-truth-labeled findings (all
false positives from a single report-only signal excluded from scoring).

```
pip install drift-analyzer
drift analyze --repo .
```

GitHub Action, SARIF output for Code Scanning, pre-commit hook — all included.
MIT licensed.

---

## Posting Notes

- Best time: Monday–Tuesday, 9–11 AM US Eastern (= 15–17 CET)
- Submit URL: https://news.ycombinator.com/submitlink?u=https://github.com/sauremilk/drift
- First comment: Post the text above as the first comment after submission
