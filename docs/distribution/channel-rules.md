# Channel Rules — Documented Requirements

Last verified: 2026-04-07

This file documents the submission rules and hard gates for each target channel.
Only documented requirements from official channel sources are recorded here.
Inferred or assumed rules are not included.

---

## dev.to

- **Type:** Self-publishing platform (no editorial gate)
- **Submission URL:** https://dev.to/new
- **Hard requirements:** None (account creation only)
- **Community guidelines:** https://dev.to/terms — no spam, no deceptive content, disclose affiliation with promoted tools
- **Tag limit:** 4 tags per post
- **Canonical URL:** Supported (set in post metadata)
- **Formatting:** Markdown with Liquid tags; code blocks and images supported
- **Disclosure requirement:** Author affiliation with drift must be visible (e.g., "I built drift")

## Hashnode

- **Type:** Self-publishing platform (no editorial gate)
- **Submission URL:** https://hashnode.com/draft (requires blog setup)
- **Hard requirements:** None (account + blog creation only)
- **Community guidelines:** https://hashnode.com/legal/terms — no spam, no misleading content
- **Canonical URL:** Supported (set original URL to dev.to version if cross-posting)
- **Formatting:** Markdown; code blocks, tables, and images supported
- **Disclosure requirement:** Same as dev.to — author affiliation must be visible

---

## Channels with documented hard gates (currently blocked)

### awesome-python

- **Repository:** https://github.com/vinta/awesome-python
- **Source:** CONTRIBUTING.md and PR review history
- **Hard requirements:**
  - Minimum 100 GitHub stars
  - Minimum 3 months since repository creation
- **Current status (2026-04-07):** Blocked — drift has <100 stars, repo created 2026-03-18
- **Earliest eligible:** ~2026-06-18

### awesome-static-analysis

- **Repository:** https://github.com/analysis-tools-dev/static-analysis
- **Source:** CONTRIBUTING.md
- **Hard requirements:**
  - Minimum 20 GitHub stars
  - Minimum 3 months since repository creation
  - More than 1 contributor
- **Current status (2026-04-07):** Blocked — drift has <20 stars, repo age <3 months, 1 contributor
- **Earliest eligible:** ~2026-06-18
