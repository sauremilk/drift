#!/usr/bin/env bash
# scripts/setup_github_labels.sh — Create missing labels on GitHub.
#
# Usage:
#   gh auth login            # authenticate as account with write+ access
#   bash scripts/setup_github_labels.sh [OWNER/REPO]
#
# Default repo: sauremilk/drift
# Requires: gh CLI (https://cli.github.com/)

set -euo pipefail

REPO="${1:-sauremilk/drift}"

# Labels defined in .github/labels.yml that may not exist on GitHub yet.
# Format: "name|color|description"
LABELS=(
  "priority: high|b60205|Credibility, signal precision, or finding clarity"
  "priority: medium|d93f0b|FP/FN reduction or adoptability improvements"
  "priority: low|fbca04|Comfort features, cosmetic docs, or trend improvements"
  "size: small|0e8a16|Less than 50 changed lines - quick review"
  "size: medium|1d76db|50-200 changed lines"
  "size: large|5319e7|More than 200 changed lines - needs dedicated review slot"
  "needs: rebase|e99695|Merge conflicts - contributor must rebase on master"
  "needs: tests|e99695|Test coverage missing or incomplete"
  "needs: evidence|e99695|Feature evidence artifact required (see PR template)"
  "needs: changes|e99695|Reviewer requested changes"
  "false-positive|d93f0b|Drift flags something that is not a real issue"
  "false-negative|d93f0b|Drift misses something that is a real issue"
  "signal-quality|0075ca|Improves precision, recall, or explainability of a signal"
  "needs reproduction|fbca04|A minimal reproducing case is needed before work can start"
  "not-prioritized|e4e4e4|Acknowledged but not currently prioritized"
  "stale|ededed|Inactive for 90+ days - will auto-close if no further activity"
  "docs|c5def5|Documentation improvements"
  "tests|bfd4f2|Test coverage or fixture improvements"
)

echo "Setting up labels on $REPO ..."

# Get existing labels
EXISTING=$(gh api "repos/$REPO/labels" --paginate --jq '.[].name' 2>/dev/null || true)

created=0
skipped=0

for entry in "${LABELS[@]}"; do
  IFS='|' read -r name color desc <<< "$entry"

  if echo "$EXISTING" | grep -qxF "$name"; then
    echo "  SKIP (exists): $name"
    ((skipped++))
  else
    if gh label create "$name" --repo "$REPO" --color "$color" --description "$desc" 2>/dev/null; then
      echo "  CREATED: $name"
      ((created++))
    else
      echo "  FAILED: $name"
    fi
  fi
done

echo ""
echo "Done: $created created, $skipped skipped."
