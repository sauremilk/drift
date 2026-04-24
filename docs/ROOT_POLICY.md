# Root Policy

This document defines what is allowed in the repository root and where other material belongs.

## Purpose

The repository root is not a dumping ground. It is the public control surface of Drift:

- first-entry files for users and contributors
- build, release, and automation control files
- a small set of canonical top-level content directories

If a file or directory does not improve entry clarity, release control, or public reproducibility, it does not belong in the root.

## Allowed in Root

Allowed categories:

- public entry documents such as README, CHANGELOG, CONTRIBUTING, SECURITY, POLICY
- build and packaging control such as pyproject, Makefile, mkdocs, GitHub Action metadata
- automation and governance directories such as .github, .githooks, scripts
- canonical content directories such as src, tests, docs, docs-site, benchmark_results, audit_results, examples
- explicitly designated artifact containers such as work_artifacts when local or review artifacts must stay versioned together

## Not Allowed in Root

These must not be added directly to the root:

- ad-hoc result files such as one-off JSON, TXT, or export outputs
- working notes, launch drafts, outreach drafts, or strategic documents that belong under docs or master-backlog
- generated site, build, cache, or local runtime output
- duplicate documentation copies when an existing docs or docs-site location already exists
- convenience files whose contribution to user onboarding or release control cannot be named clearly

## Placement Rules

Use these destinations by default:

| Content type | Destination |
| --- | --- |
| public product and architecture docs | `docs/` |
| published docs-site source | `docs-site/` |
| empirical benchmark and validation evidence | `benchmark_results/`, `audit_results/` |
| local or review artifacts that should not clutter root | `work_artifacts/` |
| architecture and process decisions | `docs/decisions/` |
| exploratory or internal drafts | `master-backlog/` |
| generated output | ignored local directories such as `site/`, `dist/`, caches |

## Enforcement

Root discipline is enforced by:

- `.github/repo-root-allowlist` for tracked top-level entries
- `.github/repo-guard.blocklist` for blocked sensitive or local-only content
- `scripts/check_repo_hygiene.py` in CI and local hooks

If a new root entry is truly necessary, update the allowlist in the same change and document the reason in the PR.
