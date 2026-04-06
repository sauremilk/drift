# Repository Governance

## Project ownership

Drift is maintained by **Mick Gottschalk** ([@mick-gsk](https://github.com/mick-gsk)).

## Decision authority

| Decision type | Authority |
|---------------|-----------|
| ADR approval (`accepted` / `rejected`) | Maintainer only |
| Signal heuristic or scoring weight changes | Maintainer approval required |
| Policy changes | Maintainer approval required |
| Backlog priority changes | Maintainer approval required |
| Merge to `main` | Maintainer only |
| Issue/PR triage and labeling | Maintainer (contributors may suggest) |

## Agent boundaries

AI agents (Copilot, Claude, etc.) may autonomously:

- Prepare ADR drafts (status `proposed`)
- Write and run tests
- Fix lint/typecheck errors
- Update audit artifacts per POLICY §18
- Prepare CHANGELOG entries

AI agents require maintainer approval for:

- Setting ADR status to `accepted` or `rejected`
- Changing signal heuristics or scoring weights
- Pushing commits
- Commenting on or closing issues/PRs
- Implementing new signals

## Contribution process

1. For non-trivial changes: open an issue or contribution proposal first
2. Follow [CONTRIBUTING.md](../CONTRIBUTING.md) for the full workflow
3. All PRs require `make check` to pass
4. The maintainer makes the final merge decision (human-in-the-loop gate)

## Code of Conduct

All participants must follow the [Code of Conduct](../CODE_OF_CONDUCT.md).

## Licensing

Drift is licensed under the [MIT License](../LICENSE). All contributions are made under the same license.
