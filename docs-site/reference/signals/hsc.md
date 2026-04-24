# Hardcoded Secret Signal (HSC)

**Signal ID:** `HSC`
**Full name:** Hardcoded Secret
**Type:** Scoring signal (contributes to drift score)
**Default weight:** `0.01`
**Scope:** file_local

---

## What HSC detects

HSC detects **hardcoded secrets and credentials** in source code — API keys, tokens, passwords, and connection strings embedded directly in code rather than sourced from environment variables or secret managers. Maps to **CWE-798: Use of Hard-Coded Credentials**.

### Before — hardcoded secret

```python
# config.py
API_KEY = "sk-proj-abc123def456ghi789"
DATABASE_URL = "postgresql://admin:s3cur3p4ss@db.example.com/prod"
AWS_SECRET_ACCESS_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
```

### After — externalized secrets

```python
# config.py
import os

API_KEY = os.environ["API_KEY"]
DATABASE_URL = os.environ["DATABASE_URL"]
AWS_SECRET_ACCESS_KEY = os.environ["AWS_SECRET_ACCESS_KEY"]
```

---

## Why hardcoded secrets matter

- **Credential exposure** — secrets in code end up in version control, CI logs, and code search.
- **Revocation difficulty** — once a secret is in git history, rotating it requires effort.
- **AI generates example secrets** — LLMs often include realistic-looking tokens that may accidentally be real.
- **Compliance violations** — many compliance frameworks (SOC2, PCI-DSS) prohibit hardcoded credentials.

---

## How the score is calculated

HSC uses a multi-stage detection approach:

1. **Variable name pattern matching** — names containing `SECRET`, `KEY`, `TOKEN`, `PASSWORD`, `CREDENTIAL`, `API_KEY`.
2. **Known token prefixes** — `sk-`, `ghp_`, `AKIA`, `xox-`, etc.
3. **Shannon entropy filtering** — high-entropy strings in assignments (randomized credentials vs. normal text).
4. **Value length and character class analysis** — secrets tend to be long, mixed-case, alphanumeric strings.

**Severity thresholds:**

| Score range | Severity |
|-------------|----------|
| ≥ 0.7       | HIGH     |
| ≥ 0.5       | MEDIUM   |
| ≥ 0.3       | LOW      |
| < 0.3       | INFO     |

---

## How to fix HSC findings

1. **Move to environment variables** — `os.environ["SECRET_NAME"]`.
2. **Use a secret manager** — AWS Secrets Manager, HashiCorp Vault, etc.
3. **Use `.env` files** (with `.gitignore`) for local development.
4. **Rotate exposed credentials** — any secret that was in code should be considered compromised.
5. **Remove from git history** — use `git filter-branch` or `BFG Repo-Cleaner`.

---

## Configuration

```yaml
# drift.yaml
weights:
  hardcoded_secret: 0.01   # default weight (0.0 to 1.0)
```

---

## Detection details

1. **Parse AST assignments** — extract variable names and string values.
2. **Match variable names** against secret-related patterns.
3. **Check values** against known token prefixes.
4. **Calculate Shannon entropy** for string literals.
5. **Filter** by length, character classes, and context (exclude test files, examples).

HSC is deterministic and AST-based.

---

## Related signals

- **ISD (Insecure Default)** — detects insecure configurations. HSC specifically detects credential values.
- **MAZ (Missing Authorization)** — detects missing access control. HSC detects exposed credentials.
