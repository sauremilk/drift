# Distribution Assets

Operational assets for discovery and adoption work.

## Files

- `awesome-submissions.md` - ready-to-submit text blocks and PR templates for curated awesome lists
- `devto-hashnode-5-repos.md` - publication draft for dev.to and Hashnode
- `ide-discovery-mvp-spec.md` - implementation spec for lightweight IDE-based discovery

## Suggested Sequence

1. Submit awesome list pull requests.
2. Publish the 5-repo article on dev.to and Hashnode.
3. Cross-post using existing outreach templates.
4. Convert the IDE MVP spec into implementation tickets.

## KPI Focus

Primary KPI for week one: increase PyPI downloads with attributable referral traffic.

## Windows Patch Paths

When editing distribution assets on Windows with patch-based tooling:

- use one path format consistently inside the patch
- do not mix `\\` and `/` in the same path string
- prefer forward-slash reasoning for repo-relative paths
- if patch application fails, check path normalization before changing content

Treat these failures as path-resolution problems first, not SVG or Markdown content problems.

## SVG Review Failures

Reject a public SVG revision if any of these are true:

- the headline is clipped or runs too close to the canvas edge
- background ornaments sit behind high-priority copy and lower readability
- footer claims are so faint that they look accidental instead of intentional
- the composition feels tightly cropped at the top, bottom, or right edge
- supporting copy drops to a size that is marginal in normal GitHub README view
- the flow from problem to Drift output to repair step is decorative instead of obvious
- the center panel overwhelms the side panels so strongly that the sequence loses clarity
