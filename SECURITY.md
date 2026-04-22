# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 2.30.x  | :white_check_mark: |
| 2.29.x  | :white_check_mark: |
| 2.28.x  | :white_check_mark: |
| 2.27.x  | :white_check_mark: |
| 2.26.x  | :white_check_mark: |
| 2.25.x  | :white_check_mark: |
| 2.24.x  | :white_check_mark: |
| 2.23.x  | :white_check_mark: |
| 2.22.x  | :white_check_mark: |
| 2.21.x  | :white_check_mark: |
| 2.20.x  | :white_check_mark: |
| 2.19.x  | :white_check_mark: |
| 2.18.x  | :white_check_mark: |
| 2.17.x  | :white_check_mark: |
| 2.16.x  | :white_check_mark: |
| 2.15.x  | :white_check_mark: |
| 2.14.x  | :white_check_mark: |
| 2.13.x  | :white_check_mark: |
| 2.12.x  | :white_check_mark: |
| 2.11.x  | :white_check_mark: |
| 2.10.x  | :white_check_mark: |
| 2.9.x   | :white_check_mark: |
| 2.7.x   | :white_check_mark: |
| 2.6.x   | :white_check_mark: |
| 2.4.x   | :white_check_mark: |
| < 2.4   | :x:                |

Current release line: **v2.30.0**.

## Reporting a Vulnerability

If you discover a security vulnerability in drift, **please do not open a public issue.**

Instead, report it privately:

1. **Email:** Send a detailed description to the maintainer via the contact listed on the [GitHub profile](https://github.com/mick-gsk).
2. **GitHub Security Advisory:** Use the [private vulnerability reporting](https://github.com/mick-gsk/drift/security/advisories/new) feature.

Please include:

- A description of the vulnerability and its potential impact.
- Steps to reproduce or a proof-of-concept.
- The drift version affected.

You will receive an acknowledgment within **72 hours** and a resolution timeline within **7 days**.

## Scope

drift is a static analysis tool that:

- **Parses Python and TypeScript source code** using AST modules and tree-sitter.
- **Invokes `git log`** via `subprocess` to read commit history.
- **Reads file system contents** of the target repository.

### Security Boundary Controls

The following controls are implemented in runtime code and treated as part of
the security baseline:

- **Path normalization:** repository roots are resolved to absolute paths before
	file traversal.
- **Symlink policy:** symlink files are skipped during file discovery.
- **File size guardrail:** files larger than 5 MB are skipped.
- **Git subprocess hardening:** git commands are invoked with argument lists
	(no shell interpolation) and fixed command templates.
- **Git timeout guardrail:** git history parsing uses a 60 second subprocess
	timeout.
- **Safe config parsing:** configuration is loaded via `yaml.safe_load` and
	validated via strict Pydantic schemas (`extra="forbid"`).
- **Non-executing parsing:** source files are parsed via `ast.parse` or
	tree-sitter; no analyzed source is executed.

### Known Attack Surface

| Vector | Description | Mitigation |
| --- | --- | --- |
| Git history parsing | drift calls `git log` via `subprocess` on the target repo. A crafted `.git` directory could theoretically influence output. | drift passes only hardcoded `git log` format strings — no user-controlled arguments are interpolated into shell commands. |
| Arbitrary file read | drift reads all `.py` and `.ts` files in the target directory tree. | No file contents are executed. Parsing is done via Python `ast.parse()` which does not execute code. |
| CI environment | When run in CI (e.g., GitHub Actions), drift has access to the runner's environment. | drift does not read environment variables, secrets, or network resources beyond the local repository. |

### Residual Risks and Operational Guidance

Even with the controls above, drift may still consume significant resources on
very large or adversarial repositories (for example, huge numbers of small
files or expensive parser workloads).

Recommended operational posture:

1. Run drift in isolated CI runners for untrusted repositories.
2. Use report-only mode first (`fail-on: none`) before enforcing hard gates.
3. Keep clone depth and analysis scope aligned with your risk and runtime
	 budget.
4. Treat optional dependency sets as an expanded supply-chain surface and pin
	 versions in controlled environments.

### Trust Model

drift operates under the **same trust level as local shell access**:

- It reads files and Git history from the local file system only.
- It does **not** make network requests, access remote APIs, or exfiltrate data.
- It does **not** execute any analyzed source code.
- The user invoking drift must already have read access to the target repository.

Consequently, an attacker who can modify files in the target repository already
has equal or greater privileges than drift itself. Findings that require prior
write access to the repository are **not considered vulnerabilities in drift**.

### Out of Scope

The following are explicitly **not** security issues in drift:

| Category | Example | Reason |
| --- | --- | --- |
| Privileged file-system crafting | Malicious `.py` files causing misleading findings | Attacker already has write access — same trust boundary. |
| Resource exhaustion on huge repos | OOM or long runtime on 100k+ file repositories | Operational concern, not a vulnerability. Use `--max-files` and resource limits. |
| Static-analysis false positives | A signal reports a finding that is not a real problem | Signal-quality issue, not a security issue. Report via [false-positive template](https://github.com/mick-gsk/drift/issues/new?template=false_positive.yml). |
| Secret-scanning baseline entries | `.secrets.baseline` contains hashed fixture secrets | Intentional test fixtures; hashes are not reversible. |
| Git history tampering | Rewritten Git history producing different drift results | drift trusts `git log` output; history integrity is the repository owner's responsibility. |

### Security Regression Evidence

Security-relevant behavior is covered by dedicated tests, including:

- `tests/test_git_history_safety.py` (subprocess argument safety and path
	handling)
- `tests/test_file_discovery.py` (symlink skipping, exclude handling, oversize
	file handling)
- `tests/test_cache_resilience.py` (corrupted cache and concurrent access
	resilience)

## Security Scanning

This repository uses `detect-secrets` with a tracked baseline
(`.secrets.baseline`) and exclusion reference (`.detect-secrets.cfg`).

GitHub-native security workflows are enabled:

- **CodeQL** (`.github/workflows/codeql.yml`): scans Python code on pushes and
  pull requests targeting `main`, plus a weekly scheduled run.
- **Dependency Review** (`.github/workflows/dependency-review.yml`): reviews
  dependency changes on pull requests and fails on `high` severity and above.

- CI enforcement: `.github/workflows/security-hygiene.yml` runs
	blocking gates for `detect-private-key`, `detect-secrets`, and
	`actionlint` via pre-commit.
- Advisory (non-blocking) checks in the same workflow: `shellcheck` and
	`zizmor`.
- Local enforcement: run the same pre-commit hooks before pushing changes.

Local commands:

```bash
pip install pre-commit==4.2.0 detect-secrets==1.5.0
pre-commit run --all-files detect-private-key
pre-commit run --all-files detect-secrets
pre-commit run --all-files shellcheck
pre-commit run --all-files actionlint
pre-commit run --all-files zizmor
```

Baseline refresh flow (after intentional fixture/doc updates):

```bash
detect-secrets scan --all-files --baseline .secrets.baseline
detect-secrets audit .secrets.baseline
```

## Disclosure Policy

We follow [coordinated disclosure](https://en.wikipedia.org/wiki/Coordinated_vulnerability_disclosure). Vulnerabilities will be patched before public disclosure. Credit will be given to reporters unless they prefer anonymity.
