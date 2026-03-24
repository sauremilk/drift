# Drift Precision Audit: requests

- **Score:** 0.322 (low)
- **Files:** 19 | Functions: 240
- **Findings:** 28 total, 13 reviewable (MEDIUM+)
- **Duration:** 0.45s
- **Analyzed:** 2026-03-24T10:20:23.286409+00:00

## Review Instructions

For each finding, mark the **Verdict** column:
- **TP** — Real problem. You'd want this flagged in a code review.
- **FP** — Not a real problem. This would erode trust if shown to a dev.
- **?** — Unsure / context-dependent.

## Findings

| # | Signal | Sev | Score | File | Title | Verdict |
|---|--------|-----|-------|------|-------|---------|
| 1 | pattern_fragmentation | high | 0.974 | src\requests | error_handling: 39 variants in src/requests/ | |
| 2 | mutant_duplicate | high | 0.85 | src\requests\cookies.py | Near-duplicate (100%): RequestsCookieJar.iterkeys ↔ Requests | |
| 3 | mutant_duplicate | high | 0.85 | src\requests\cookies.py | Near-duplicate (100%): RequestsCookieJar.list_domains ↔ Requ | |
| 4 | explainability_deficit | high | 0.8 | src\requests\utils.py | Unexplained complexity: super_len | |
| 5 | explainability_deficit | high | 0.75 | src\requests\auth.py | Unexplained complexity: HTTPDigestAuth.build_digest_header | |
| 6 | explainability_deficit | high | 0.712 | src\requests\adapters.py | Unexplained complexity: HTTPAdapter.send | |
| 7 | explainability_deficit | medium | 0.637 | src\requests\models.py | Unexplained complexity: PreparedRequest.prepare_url | |
| 8 | explainability_deficit | medium | 0.637 | src\requests\models.py | Unexplained complexity: PreparedRequest.prepare_body | |
| 9 | explainability_deficit | medium | 0.637 | src\requests\utils.py | Unexplained complexity: should_bypass_proxies | |
| 10 | explainability_deficit | medium | 0.594 | src\requests\models.py | Unexplained complexity: RequestEncodingMixin._encode_files | |
| 11 | explainability_deficit | medium | 0.562 | src\requests\sessions.py | Unexplained complexity: SessionRedirectMixin.resolve_redirec | |
| 12 | explainability_deficit | medium | 0.525 | src\requests\adapters.py | Unexplained complexity: HTTPAdapter.cert_verify | |
| 13 | explainability_deficit | medium | 0.5 | src\requests\__init__.py | Unexplained complexity: check_compatibility | |

## Detailed Findings

### #1: error_handling: 39 variants in src/requests/
**Signal:** pattern_fragmentation | **Severity:** high | **Score:** 0.974 | **Impact:** 0.941
**File:** src\requests

> 39 error_handling variants in src/requests/ (5/50 use canonical pattern).
  - __init__.py:95 (_check_cryptography)
  - models.py:225 (RequestHooksMixin.deregister_hook)
  - utils.py:714 (is_valid_cidr)

**Fix:** Konsolidiere auf das dominante Pattern (5×). 45 Abweichung(en) in: __init__.py, _internal_utils.py, adapters.py, auth.py, compat.py und 40 weitere.

**Related:** src\requests\__init__.py, src\requests\models.py, src\requests\utils.py, src\requests\_internal_utils.py, src\requests\adapters.py

**Verdict:** TP / FP / ?
**Note:**

---

### #2: Near-duplicate (100%): RequestsCookieJar.iterkeys ↔ RequestsCookieJar.itervalues
**Signal:** mutant_duplicate | **Severity:** high | **Score:** 0.85 | **Impact:** 0.216
**File:** src\requests\cookies.py (line 225)

> src\requests\cookies.py:225 and src\requests\cookies.py:242 are 100% similar. Small differences may indicate copy-paste divergence.

**Fix:** Extrahiere RequestsCookieJar.iterkeys() in src/requests/shared.py. Similarity: 100%. Aufwand: S.

**Related:** src\requests\cookies.py

**Verdict:** TP / FP / ?
**Note:**

---

### #3: Near-duplicate (100%): RequestsCookieJar.list_domains ↔ RequestsCookieJar.list_paths
**Signal:** mutant_duplicate | **Severity:** high | **Score:** 0.85 | **Impact:** 0.216
**File:** src\requests\cookies.py (line 277)

> src\requests\cookies.py:277 and src\requests\cookies.py:285 are 100% similar. Small differences may indicate copy-paste divergence.

**Fix:** Extrahiere RequestsCookieJar.list_domains() in src/requests/shared.py. Similarity: 100%. Aufwand: S.

**Related:** src\requests\cookies.py

**Verdict:** TP / FP / ?
**Note:**

---

### #4: Unexplained complexity: super_len
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.8 | **Impact:** 0.096
**File:** src\requests\utils.py (line 134)

> Complexity: 16, LOC: 69. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion super_len (Complexity 16): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #5: Unexplained complexity: HTTPDigestAuth.build_digest_header
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.75 | **Impact:** 0.09
**File:** src\requests\auth.py (line 126)

> Complexity: 23, LOC: 109. No corresponding test found. No return type annotation.

**Fix:** Funktion HTTPDigestAuth.build_digest_header (Complexity 23): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #6: Unexplained complexity: HTTPAdapter.send
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.712 | **Impact:** 0.085
**File:** src\requests\adapters.py (line 592)

> Complexity: 19, LOC: 107. No corresponding test found. No return type annotation.

**Fix:** Funktion HTTPAdapter.send (Complexity 19): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #7: Unexplained complexity: PreparedRequest.prepare_url
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.637 | **Impact:** 0.076
**File:** src\requests\models.py (line 411)

> Complexity: 17, LOC: 73. No corresponding test found. No return type annotation.

**Fix:** Funktion PreparedRequest.prepare_url (Complexity 17): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #8: Unexplained complexity: PreparedRequest.prepare_body
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.637 | **Impact:** 0.076
**File:** src\requests\models.py (line 496)

> Complexity: 17, LOC: 77. No corresponding test found. No return type annotation.

**Fix:** Funktion PreparedRequest.prepare_body (Complexity 17): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #9: Unexplained complexity: should_bypass_proxies
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.637 | **Impact:** 0.076
**File:** src\requests\utils.py (line 753)

> Complexity: 17, LOC: 59. No corresponding test found. No return type annotation.

**Fix:** Funktion should_bypass_proxies (Complexity 17): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #10: Unexplained complexity: RequestEncodingMixin._encode_files
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.594 | **Impact:** 0.071
**File:** src\requests\models.py (line 139)

> Complexity: 19, LOC: 67. No corresponding test found. No return type annotation.

**Fix:** Funktion RequestEncodingMixin._encode_files (Complexity 19): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #11: Unexplained complexity: SessionRedirectMixin.resolve_redirects
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.562 | **Impact:** 0.067
**File:** src\requests\sessions.py (line 160)

> Complexity: 15, LOC: 122. No corresponding test found. No return type annotation.

**Fix:** Funktion SessionRedirectMixin.resolve_redirects (Complexity 15): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #12: Unexplained complexity: HTTPAdapter.cert_verify
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.525 | **Impact:** 0.063
**File:** src\requests\adapters.py (line 282)

> Complexity: 14, LOC: 55. No corresponding test found. No return type annotation.

**Fix:** Funktion HTTPAdapter.cert_verify (Complexity 14): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #13: Unexplained complexity: check_compatibility
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** src\requests\__init__.py (line 58)

> Complexity: 10, LOC: 33. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion check_compatibility (Complexity 10): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---
