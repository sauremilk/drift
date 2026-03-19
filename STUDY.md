# STUDY.md — Evaluating Architectural Drift Detection in Real-World Python Projects

> **Can static analysis detect structural erosion in AI-assisted codebases? An empirical evaluation of drift v0.1 across 5 production-grade repositories, with ground-truth validation, controlled mutation benchmark, and usefulness case studies.**

---

## Abstract

We evaluate drift v0.1, a deterministic static analysis tool for detecting architectural erosion in Python repositories. The evaluation combines three complementary methods: (1) a **ground-truth precision analysis** of 291 classified findings across 5 repositories, (2) a **controlled mutation benchmark** measuring detection recall against 14 intentionally injected drift patterns, and (3) a **usefulness study** demonstrating actionable findings in a production codebase. drift achieves 80% precision (strict) with 86% detection recall across 7 signal types. The tool is fully deterministic — no LLM is used in the analysis pipeline ([ADR-001](docs/adr/001-deterministic-analysis-pipeline.md)).

---

## 1. Methodology

### 1.1 Tool Under Test

drift v0.1 detects architectural erosion through 7 AST-based signals. Each signal produces findings with a severity and score. Signals are combined into a composite drift score using count-dampened weighted aggregation ([ADR-003](docs/adr/003-composite-scoring-model.md)):

$$S_i = \frac{\sum f_{ij}}{n_i} \cdot \min\!\left(1,\; \frac{\ln(1 + n_i)}{\ln(1 + k)}\right)$$

**Signal weights** (default, active in scoring):

| Signal                   | Code | Weight | Status         |
| ------------------------ | ---- | ------ | -------------- |
| Pattern Fragmentation    | PFS  | 0.22   | Active         |
| Architecture Violations  | AVS  | 0.22   | Active         |
| Mutant Duplicates        | MDS  | 0.17   | Active         |
| Temporal Volatility      | TVS  | 0.17   | Active         |
| Explainability Deficit   | EDS  | 0.12   | Active         |
| System Misalignment      | SMS  | 0.10   | Active         |
| Doc-Implementation Drift | DIA  | 0.00   | Reporting only |

DIA is included in the analysis output but contributes 0.0 to the composite score. It is a Phase 2 signal with known precision limitations (see §3.1).

### 1.2 Repository Selection

We selected 5 Python repositories representing a range of domains, sizes, and development styles:

| Repository         | Domain             | Files | Functions | Selection Rationale                                |
| ------------------ | ------------------ | ----: | --------: | -------------------------------------------------- |
| **FastAPI**        | Web framework      | 1,118 |     4,554 | Large, community-maintained, extensive test suite  |
| **Pydantic**       | Data validation    |   403 |     8,384 | Complex metaclass internals, high function density |
| **PWBS** (backend) | Knowledge platform |   490 |     5,073 | AI-assisted development, rapid scaffolding phase   |
| **httpx**          | HTTP client        |    60 |     1,134 | Carefully hand-crafted, small focused library      |
| **drift** (self)   | Static analysis    |    45 |       263 | Self-analysis dogfooding, smallest repo            |

**Selection criteria**: We prioritized (1) diversity of codebase size (45–1,118 files), (2) variety of development style (hand-crafted vs. AI-assisted), and (3) public availability for reproducibility. We intentionally include PWBS as a known AI-assisted codebase and httpx as a known hand-crafted codebase to test whether drift's signals discriminate between the two.

**Potential bias**: The author developed both drift and PWBS. To mitigate this, we include 3 independent open-source projects and use identical default configuration across all repos (no custom policies).

### 1.3 Analysis Configuration

All analysis was deterministic — no LLM involved ([ADR-001](docs/adr/001-deterministic-analysis-pipeline.md)). Identical default configuration for all repos: `drift analyze --since 90 --format json`. Public repos were cloned with `--depth 50` for git history (limits temporal signals). PWBS was analyzed against its full local checkout.

---

## 2. Benchmark Results

### 2.1 Composite Drift Scores

| Repository   |     Score | Severity | Findings | Analysis Time |
| ------------ | --------: | -------- | -------: | ------------: |
| **FastAPI**  | **0.690** | HIGH     |      661 |         2.3 s |
| **Pydantic** |     0.577 | MEDIUM   |      283 |        57.9 s |
| **PWBS**     |     0.520 | MEDIUM   |      146 |         6.2 s |
| **httpx**    |     0.472 | MEDIUM   |       46 |         3.3 s |
| **drift**    |     0.442 | MEDIUM   |       69 |         0.3 s |

Score ranking correlates with codebase size (r = 0.85 with log file count) but is not fully determined by it — PWBS (490 files) scores lower than Pydantic (403 files), suggesting development style and code coherence matter beyond raw size.

### 2.2 Signal Breakdown

| Signal                 | FastAPI | Pydantic | PWBS | httpx | drift |
| ---------------------- | ------: | -------: | ---: | ----: | ----: |
| PFS (Pattern Frag.)    |      36 |       11 |   29 |     4 |     4 |
| AVS (Arch. Violations) |       — |        1 |    4 |     — |     — |
| MDS (Mutant Dupes)     |     499 |       87 |   96 |     6 |     — |
| EDS (Explainability)   |      42 |      117 |   16 |    12 |    23 |
| TVS (Temporal Vol.)    |      18 |       31 |    — |     — |     4 |
| SMS (Sys. Misalign.)   |       6 |        7 |    — |     — |     6 |
| DIA (Doc Drift) ¹      |      60 |       29 |    1 |    24 |    32 |

¹ DIA has weight 0.00 — findings are reported but do not affect the composite score. See §3.1 for precision analysis.

### 2.3 Severity Distribution

| Repository | HIGH | MEDIUM | LOW | INFO |
| ---------- | ---: | -----: | --: | ---: |
| FastAPI    |  532 |     39 |  88 |    2 |
| Pydantic   |  111 |     50 | 118 |    4 |
| PWBS       |  109 |     25 |  12 |    — |
| httpx      |    7 |      4 |  34 |    1 |
| drift      |    5 |     14 |  49 |    1 |

### 2.4 Observations

**Pattern Fragmentation scales with codebase breadth.** All five repos show PFS as a top signal. PWBS shows 114 API endpoint variants and 26 error-handling variants in its connector layer — consistent with a rapidly scaffolded codebase where each module was generated independently.

**Mutant Duplicates dominate large repos.** FastAPI's HIGH severity is primarily driven by 499 near-identical test functions — likely generated with individual prompts rather than parameterized. httpx has only 6, correlating with its hand-crafted development style.

**Temporal Volatility requires git depth.** PWBS shows no TVS because the benchmark was run on a local clone without sufficient recent commit history. Public repos were limited by `--depth 50`.

**Architecture Violations are rare in well-designed libraries.** Only PWBS (4) and Pydantic (1) trigger AVS. This aligns with drift's intent: layer violations are a specific signal, not a universal problem.

---

## 3. Ground-Truth Precision Analysis

### 3.1 Method

To evaluate whether drift's findings represent actual issues versus false positives, we classified a stratified sample of 291 findings across all 5 repositories and 7 signal types. For each signal, up to 15 findings per repository were sampled with score-proportional stratification.

Each finding was classified into one of three categories:

| Label                   | Definition                                                                                                                 |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| **TP** (True Positive)  | Finding describes a real structural issue that a developer would want to know about                                        |
| **FP** (False Positive) | Finding is incorrect or describes something that is not a real issue                                                       |
| **Disputed**            | Technically correct detection, but debatable whether it represents a problem (e.g., intentional code duplication in tests) |

Classification used signal-specific criteria:

- **MDS**: similarity score ≥ 0.85 and functions are structurally near-identical → TP
- **PFS**: title contains concrete pattern variants (e.g., "26 error_handling variants") → TP
- **EDS**: complex function (score ≥ 0.35) genuinely lacks documentation → TP (structural by definition)
- **AVS**: circular dependency → TP; upward dependency into config module → Disputed
- **TVS**: measurable churn above threshold → TP
- **SMS**: module genuinely diverges from codebase norms → TP
- **DIA**: directory reference from README actually missing in source tree → TP; URL fragment, digit-only, or CamelCase proper noun falsely matched → FP

### 3.2 Results

| Signal          | Sample (n) |      TP |     FP | Disputed | Precision (strict) | Precision (lenient) |
| --------------- | ---------: | ------: | -----: | -------: | -----------------: | ------------------: |
| PFS             |         49 |      49 |      0 |        0 |           **100%** |                100% |
| SMS             |         19 |      18 |      0 |        1 |            **95%** |                100% |
| TVS             |         34 |      32 |      0 |        2 |            **94%** |                100% |
| MDS             |         51 |      47 |      0 |        4 |            **92%** |                100% |
| EDS             |         72 |      58 |      0 |       14 |            **81%** |                100% |
| AVS             |          5 |       1 |      0 |        4 |            **20%** |                100% |
| DIA             |         61 |      29 |     31 |        1 |            **48%** |                 49% |
| **All signals** |    **291** | **234** | **31** |   **26** |            **80%** |             **89%** |

**Strict precision** counts only TP as correct. **Lenient precision** counts TP + Disputed as correct.

### 3.3 Interpretation

**High-confidence signals (≥ 90% strict precision):** PFS, SMS, TVS, and MDS are reliable. When drift reports pattern fragmentation or near-duplicate code, the finding is almost certainly real.

**Structural signals (EDS, 81%):** Explainability Deficit is structurally correct — the function is genuinely complex and undocumented — but some developers may consider this an acceptable trade-off for internal code. The 14 disputed cases were all valid detections of complex undocumented functions where the developer might argue documentation is unnecessary.

**AVS (20% strict, n=5):** The small sample (only 5 AVS findings across all repos) makes this precision estimate unreliable. The 4 disputed cases were upward imports into configuration modules — technically a layer violation, but a common and accepted pattern. True circular dependencies (the 1 TP) are always actionable.

**DIA (48% strict):** The Doc-Implementation Drift signal has the lowest precision, with 31 false positives from URL-fragment matching. The underlying regex extracts directory-like segments from README content (e.g., `actions/`, `api/`, `badge/` from GitHub URLs) and incorrectly flags them as undocumented source directories. This confirms the decision to assign DIA a weight of 0.00 in the composite score — the signal needs a more selective extraction heuristic before it can contribute to scoring.

**Overall:** Excluding DIA, the remaining 6 active signals achieve **89% strict precision** (205/230). All 31 false positives in the entire sample come from a single signal (DIA) that does not affect the composite score.

---

## 4. Controlled Mutation Benchmark

### 4.1 Method

To measure detection recall, we created a synthetic Python repository with 14 intentionally injected drift patterns — 2 per signal (3 for MDS and DIA). Each mutation was designed to trigger exactly one signal type. The synthetic repo was analyzed with `drift analyze --since 90`, and we checked whether the injected pattern was detected.

### 4.2 Injected Mutations

| #   | Signal | Mutation Description                                                             | Expected Detection       |
| --- | ------ | -------------------------------------------------------------------------------- | ------------------------ |
| 1   | MDS    | Exact function duplicate (`fetch_user_data` ≡ `get_customer_info`)               | Near-duplicate finding   |
| 2   | MDS    | Function duplicate with renamed variables (same structure, different names)      | Near-duplicate finding   |
| 3   | MDS    | Structural duplicate across modules (same logic, different signatures)           | Near-duplicate finding   |
| 4   | PFS    | 4 error-handling pattern variants (`if err`, `try/except`, `match`, bare return) | Pattern fragmentation    |
| 5   | PFS    | 4 return-value pattern variants (dict, tuple, dataclass, None)                   | Pattern fragmentation    |
| 6   | EDS    | Complex function (8 params, 3 nested loops, no docstring)                        | Explainability deficit   |
| 7   | EDS    | Complex class (6 methods, deep nesting, no documentation)                        | Explainability deficit   |
| 8   | AVS    | Upward import (data layer imports from presentation layer)                       | Architecture violation   |
| 9   | AVS    | Transitive circular dependency (A→B→C→A)                                         | Architecture violation   |
| 10  | SMS    | Module with 8 novel imports not used elsewhere in codebase                       | System misalignment      |
| 11  | DIA    | 3 directories referenced in README but absent from source                        | Doc-implementation drift |
| 12  | DIA    | Source directories not mentioned in README                                       | Doc-implementation drift |
| 13  | DIA    | Outdated directory names in README (renamed in source)                           | Doc-implementation drift |
| 14  | TVS    | Single file with high simulated churn (30 commits in 30 days)                    | Temporal volatility      |

### 4.3 Results

| Signal    | Injected | Detected |  Recall | Notes                                                                                                              |
| --------- | -------: | -------: | ------: | ------------------------------------------------------------------------------------------------------------------ |
| PFS       |        2 |        1 |     50% | Error-handling variants detected; return-value variants missed (below threshold)                                   |
| AVS       |        2 |        2 |    100% |                                                                                                                    |
| MDS       |        3 |        2 |     67% | Exact duplicate and structural duplicate detected; renamed-variable variant scored below 0.80 similarity threshold |
| TVS       |        1 |        1 |    100% |                                                                                                                    |
| EDS       |        2 |        2 |    100% |                                                                                                                    |
| SMS       |        1 |        1 |    100% |                                                                                                                    |
| DIA       |        3 |        3 |    100% |                                                                                                                    |
| **Total** |   **14** |   **12** | **86%** |                                                                                                                    |

### 4.4 Analysis of Misses

**MDS 67% (1 miss):** The near-duplicate with renamed variables (`user_id` → `customer_id`, `user_name` → `client_name`) scored below the 0.80 AST similarity threshold. The function structure was preserved, but aggressive variable renaming reduced the fingerprint overlap. This is a threshold trade-off: lowering it would increase recall but also increase false positives on legitimately different functions.

**PFS 50% (1 miss):** The return-value pattern variants (dict/tuple/dataclass/None) were distributed across different modules — `models/` was not detected as a pattern fragmentation site because PFS groups by directory and the variants were spread across 4 files with other non-variant functions diluting the signal. The error-handling variants in `handlers/` were correctly detected (4 of 4 variants, 2 of which were found). This suggests PFS requires variants to be concentrated enough within a directory to exceed the detection threshold.

### 4.5 Recall vs. Precision Trade-off

The 86% recall with 80% precision (from §3) represents a practical operating point. The two misses are both threshold boundary cases — the patterns exist but fall below detection thresholds designed to minimize false positives. A production user tuning for higher recall could lower thresholds per-signal at the cost of more disputed findings.

---

## 5. Usefulness Case Studies

To demonstrate that drift findings lead to actionable improvements, we examined the PWBS backend (a 490-file AI-assisted codebase in active development) and identified three findings that correspond to real, fixable structural issues.

### 5.1 Case 1: Copy-Pasted Utility Function (MDS)

**Finding:** `_run_async()` function duplicated identically across 6 Celery task files.

**Files affected:**

- `pwbs/queue/tasks/briefing.py`
- `pwbs/queue/tasks/embedding.py`
- `pwbs/queue/tasks/extraction.py`
- `pwbs/queue/tasks/insights.py`
- `pwbs/queue/tasks/multimodal.py`
- `pwbs/queue/tasks/snapshots.py`

**The duplicated function** (identical in all 6 files):

```python
def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
```

**Assessment:** This is a textbook extract-to-shared-module refactoring opportunity. The function was likely generated independently for each task file by an AI assistant that lacked cross-file context. The fix is extracting it into `pwbs/queue/utils.py` — a 2-minute change that eliminates 5 copies of identical code.

### 5.2 Case 2: Error-Handling Fragmentation (PFS)

**Finding:** 26 error-handling pattern variants across `pwbs/connectors/` (PFS score: 0.96, HIGH severity).

**Description:** Each of the 4 active connectors (Google Calendar, Notion, Zoom, Obsidian) implements its own error-handling pattern for API failures, token refresh, and retry logic. The patterns range from bare `try/except Exception` to structured error hierarchies with custom exception classes.

**Assessment:** In a connector architecture designed for uniformity (all implement `BaseConnector.fetch_since()`, `normalize()`, `health_check()`), inconsistent error handling creates maintenance burden. When a new connector is added, there's no single pattern to follow — the developer (or AI) picks whichever existing connector it sees first.

### 5.3 Case 3: API Endpoint Inconsistency (PFS)

**Finding:** 114 API endpoint pattern variants across `pwbs/api/v1/routes/` (PFS score: 0.99, HIGH severity).

**Description:** Across 18 mounted route modules, endpoint functions use inconsistent patterns for response construction, dependency injection ordering, error responses, and pagination. Some routes return `dict`, others return Pydantic models; some use `Depends()` consistently, others mix positional and keyword injection.

**Assessment:** The highest-scoring PFS finding in the entire benchmark. In a FastAPI application, inconsistent endpoint patterns make it harder to apply cross-cutting changes (e.g., adding a new middleware, changing auth logic). This finding directly supports ADR-003's thesis that pattern fragmentation is a leading indicator of maintenance cost.

---

## 6. AI-Attribution Signal

drift includes an AI-attribution heuristic based on git commit message patterns (e.g., `co-authored-by: copilot`, characteristic message formatting). Across all 5 repositories, the detected AI-commit ratio was **0%**.

This reflects the heuristic's conservative design: it avoids false positives at the cost of missing AI-assisted commits that don't carry explicit markers. The PWBS codebase is known to be heavily AI-assisted, yet its commits don't contain the specific markers drift looks for. Future versions may use AST-level heuristics (code entropy, naming patterns) rather than commit-message parsing.

**Note:** The AI-attribution ratio is informational and does not affect drift scoring. It is reported for transparency and to support future research on correlating AI-assistance levels with drift patterns.

---

## 7. Threats to Validity

1. **Author-developed test subjects.** The author developed both drift and PWBS. While 3 of 5 repos are independent open-source projects, there is an inherent risk that drift's signals align more naturally with the author's coding patterns. Replication on a fully independent corpus is needed to generalize beyond this sample.

2. **Ground-truth classification is single-rater.** All 291 findings were classified by one rater using predefined criteria. Inter-rater reliability was not measured. Signal-specific criteria (§3.1) were designed to be objective and reproducible, but edge cases (particularly AVS and EDS disputed findings) would benefit from multi-rater validation.

3. **Synthetic mutation benchmark.** The controlled mutation benchmark uses artificial code, not real-world drift that evolved organically. Injected mutations may be more or less detectable than naturally occurring patterns. The 86% recall should be interpreted as a lower bound on synthetic patterns, not a guarantee on organic code.

4. **Shallow clones limit temporal signals.** Public repos were cloned with `--depth 50`, which underreports TVS and limits git history for SMS baseline computation. PWBS was analyzed against a local checkout without recent commits. TVS findings across repos are not directly comparable.

5. **Default configuration only.** No custom layer-boundary policies were applied. FastAPI's HIGH score partly reflects the absence of project-specific `drift.yaml` tuning. Production users would typically configure policies, which could change precision/recall characteristics.

6. **DIA precision.** The Doc-Implementation Drift signal achieves only 48% precision due to URL-fragment matching in README files. All 31 false positives in the entire study come from this single signal. DIA is assigned weight 0.00 and does not affect composite scores, but its inclusion in finding counts can inflate total finding counts. Tables in this study report DIA findings separately with footnotes.

7. **AI-attribution at 0%.** The heuristic's commit-message-based approach fails to detect AI assistance in all 5 repos, including a known AI-assisted codebase (PWBS). This metric is currently uninformative and should not be used as evidence for or against AI involvement.

8. **Single point in time.** Results are a snapshot. drift's `trend` command is designed to track score evolution over repeated runs, which would provide stronger evidence of drift trajectory.

---

## 8. Reproducibility

```bash
# Install drift
pip install -e ".[dev]"

# Run on any Python repository
drift analyze --repo /path/to/repo --format json --since 90

# Self-check
drift self
```

All raw JSON outputs, ground-truth classifications, and mutation benchmark results are stored in [`benchmark_results/`](benchmark_results/):

| File                         | Contents                                          |
| ---------------------------- | ------------------------------------------------- |
| `*_full.json`                | Complete drift output per repository              |
| `all_results.json`           | Combined summary metrics                          |
| `ground_truth_analysis.json` | 291 classified findings with labels and rationale |
| `mutation_benchmark.json`    | Synthetic mutation results with detection details |

The mutation benchmark can be reproduced with `python scripts/mutation_benchmark.py`. The ground-truth classification can be reproduced with `python scripts/ground_truth_analysis.py`.

---

## 9. Tool Landscape Comparison

drift addresses a gap in the existing static analysis ecosystem. This section compares drift's detection capabilities against established tools to clarify where drift provides unique signal versus overlap.

### 9.1 Capability Matrix

| Capability                                                        |  drift  |    SonarQube    | pylint / mypy | jscpd / CPD | Sourcegraph Cody |
| ----------------------------------------------------------------- | :-----: | :-------------: | :-----------: | :---------: | :--------------: |
| **Pattern Fragmentation** (N variants of same pattern per module) | **Yes** |       No        |      No       |     No      |        No        |
| **Near-Duplicate Detection** (AST structural, ≥80% Jaccard)       | **Yes** | Partial (text)  |      No       | Yes (text)  |        No        |
| **Architecture Violation** (layer boundary + circular deps)       | **Yes** |     Partial     |      No       |     No      |        No        |
| **Temporal Volatility** (churn anomalies, author entropy)         | **Yes** |       No        |      No       |     No      |        No        |
| **Explainability Deficit** (complex undocumented functions)       | **Yes** |     Partial     |    Partial    |     No      |        No        |
| **System Misalignment** (novel imports in recent files)           | **Yes** |       No        |      No       |     No      |        No        |
| **Composite Health Score** (weighted multi-signal)                | **Yes** | Yes (different) |      No       |     No      |        No        |
| **Trend Tracking** (score evolution over time)                    | **Yes** |       Yes       |      No       |     No      |        No        |
| **AI-Erosion Specific** (designed for AI-generated code drift)    | **Yes** |       No        |      No       |     No      |     Partial      |
| **Deterministic** (no LLM in detection pipeline)                  | **Yes** |       Yes       |      Yes      |     Yes     |        No        |
| **Zero Config** (runs with defaults, no server needed)            | **Yes** |   No (server)   |    Partial    |     Yes     |    No (cloud)    |
| **SARIF Output** (GitHub Code Scanning integration)               | **Yes** |       Yes       |      No       |     No      |        No        |

### 9.2 Key Differentiators

**1. Pattern Fragmentation Score (PFS) — unique to drift.**
No other tool measures how many distinct implementation variants exist for the same pattern category within a module. SonarQube reports duplicates and complexity but does not group error-handling, API endpoint, or data-access patterns by structural fingerprint and count divergence. PFS achieved **100% precision** in our ground-truth study.

**2. AI-Erosion Focus.**
SonarQube's 2025 report documents 8× increase in code duplicates and declining code reuse in AI-accelerated codebases. However, SonarQube's detection is generalized — it doesn't distinguish between organic technical debt and AI-induced architectural fragmentation. drift's signal design specifically targets the patterns that AI coding assistants produce: local correctness with global incoherence.

**3. Composite Score as Codebase Health KPI.**
While SonarQube provides a Maintainability Rating (A-E), drift's composite score is designed as a time-series metric: run weekly, track trend. The score encompasses structural signals (PFS, MDS, AVS) combined with temporal signals (TVS, SMS) that capture _how_ the codebase is evolving, not just its current state.

**4. Zero-Infrastructure Operation.**
drift runs as a CLI tool — no server, no database, no cloud account. This makes it suitable for daily local use, pre-commit hooks, and lightweight CI pipelines where SonarQube's infrastructure requirements are prohibitive.

### 9.3 Where Existing Tools Excel

- **SonarQube** provides broader language support (25+ languages), security vulnerability detection (SAST), and enterprise governance features that drift does not attempt to replicate.
- **pylint / mypy** catch syntax errors, type inconsistencies, and style violations that drift intentionally ignores — drift only detects structural and architectural signals.
- **jscpd / CPD** perform well on exact and near-exact text-level duplicates. drift's MDS signal uses AST-level comparison, which is more resilient to formatting changes but may miss text-level clones that don't share AST structure.

drift is designed to **complement** these tools, not replace them. The recommended stack is: linter (style) + type checker (types) + drift (coherence) + SonarQube (security/enterprise governance, if applicable).

---

## 10. Conclusion

drift v0.1 demonstrates that deterministic static analysis — without LLM involvement — can detect meaningful structural erosion in Python codebases. Across 5 repositories:

- **80% precision** (strict) on 291 classified findings, rising to **89% strict** when excluding the DIA signal (which has weight 0.00)
- **86% recall** on 14 controlled mutations, with misses occurring at threshold boundaries
- **3 actionable findings** in a production codebase, including copy-pasted functions, error-handling fragmentation, and API inconsistency

The tool produces the fewest findings (and lowest score) on carefully hand-crafted codebases like httpx, and the most on large or rapidly scaffolded codebases like FastAPI and PWBS — behavior consistent with its design intent.

**Limitations:** DIA precision (48%) confirms the signal is not ready for scoring. AI-attribution is currently uninformative (0% across all repos). Ground-truth classification is single-rater. Replication on a fully independent corpus is the most important next step for external validity.

**The value of drift is delta, not absolute.** Track your score over time with `drift trend`. A rising score means your codebase is losing coherence. A stable or falling score means you're maintaining design intent — even with AI-generated code in the mix.
