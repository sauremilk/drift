# Co-Change Coupling Signal (CCC)

**Signal ID:** `CCC`
**Full name:** Co-Change Coupling
**Type:** Scoring signal (contributes to drift score)
**Default weight:** `0.005`
**Scope:** git_dependent

---

## What CCC detects

CCC detects **hidden coupling** between files that repeatedly change together in commits but have no explicit import relationship. If files A and B always change in the same commit but neither imports the other, there's an implicit dependency that isn't visible in the code structure.

### Example finding

```
co_change_coupling between services/pricing.py ↔ templates/invoice.html
  Co-change frequency: 8/10 commits (80%)
  Import relationship: none
  → Score: 0.64 (MEDIUM)
```

These files have no code dependency, yet 80% of pricing changes also require invoice template changes — a hidden coupling.

---

## Why co-change coupling matters

- **Invisible dependencies** — code review can't catch coupling that isn't in imports.
- **Incomplete changes** — developers change one file but forget the coupled partner, introducing bugs.
- **AI doesn't know about co-change history** — AI assistants only see the file being edited, not its historical partners.
- **Architectural decay indicator** — co-change coupling often reveals that responsibilities should be co-located or that a shared abstraction is missing.

---

## How the score is calculated

CCC builds a co-change matrix from git history:

1. **Extract commit touchsets** — which files changed together in each commit.
2. **Build pairwise co-change counts** — how often each file pair appears in the same commit.
3. **Filter to significant pairs** — minimum frequency threshold (e.g., 3+ co-changes).
4. **Check for import relationship** — only flag pairs without explicit imports.
5. **Score by confidence** — `co_changes / total_changes` for the less-frequently-changed file.

**Severity thresholds:**

| Score range | Severity |
|-------------|----------|
| ≥ 0.7       | HIGH     |
| ≥ 0.5       | MEDIUM   |
| ≥ 0.3       | LOW      |
| < 0.3       | INFO     |

---

## How to fix CCC findings

1. **Co-locate related logic** — move the coupled code into the same module or package.
2. **Extract a shared abstraction** — if both files depend on the same concept, make it explicit.
3. **Add explicit imports** — if there's a real dependency, make it visible in code.
4. **Document the relationship** — if coupling is intentional (e.g., schema + migration), document the link.

---

## Configuration

```yaml
# drift.yaml
weights:
  co_change_coupling: 0.005   # default weight (0.0 to 1.0)
```

---

## Detection details

1. **Parse git log** — extract commit file lists.
2. **Build co-change matrix** — count pairwise co-occurrences.
3. **Filter by minimum threshold** — ignore infrequent pairs.
4. **Cross-reference with import graph** — exclude pairs with explicit imports.
5. **Score remaining pairs** by co-change confidence.

CCC **requires git history** (`git_dependent=True`). Without a git repository, CCC produces no findings.

---

## Related signals

- **AVS (Architecture Violation)** — detects static import violations. CCC detects dynamic co-change coupling.
- **TVS (Temporal Volatility)** — detects volatile individual modules. CCC detects coupled pairs.
- **ECM (Exception Contract Drift)** — also git-dependent, but focused on behavioral drift rather than structural coupling.
