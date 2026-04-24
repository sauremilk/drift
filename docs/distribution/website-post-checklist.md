# Drift Website Post PRD

Status: active
Version: 2.0
Last updated: 2026-04-07
Owner: maintainer
Related artifact: derived operational checklist and review record are defined in this document

## 1. Document Purpose

This document is the product requirements document for Drift's external website-post workflow.
It defines the problem, the intended operating model, the user and stakeholder needs, the success criteria, and the concrete product requirements for preparing, reviewing, approving, and publishing website posts about Drift.

This PRD exists so that distribution work is:

- repeatable
- evidence-backed
- auditable
- channel-aware
- robust against contradictory public claims

This document is not a marketing brief.
It is the product definition for the publication workflow itself.

## 2. Problem Statement

Drift is in a distribution phase where credibility matters more than volume.
The publishing problem is not merely writing persuasive copy. The real problem is avoiding posts that create avoidable trust damage through:

- contradictory version references
- contradictory signal counts
- benchmark overstatement
- misuse of self-scan as external proof
- confusing adoption and reach metrics
- poor landing-page fit
- submissions to channels that Drift does not yet qualify for

Without a formal publishing system, authors can still produce text that looks strong while being weakly grounded. That failure mode is expensive because external posts persist longer than internal discussion and are easy for skeptical readers to compare against the repository.

## 3. Product Goal

The product goal is to define a publishing workflow that reliably blocks low-credibility external posts and allows only those posts that are evidence-backed, internally consistent, and appropriate for the target channel.

## 4. Goals

The workflow must:

- prevent publication of externally visible contradictions
- force one-claim, one-metric, one-CTA discipline
- make evidence collection part of the work, not an optional afterthought
- make review decisions reproducible by a second reviewer
- define clear ownership when a draft fails review
- enforce revalidation before stale approvals turn into stale posts

## 5. Non-Goals

This workflow does not attempt to:

- automate website publishing
- generate marketing copy automatically
- define social-media strategy
- replace product strategy or roadmap decisions
- prove product quality on its own
- optimize for maximum posting velocity

## 6. Users and Stakeholders

### 6.1 Primary Users

- Author: prepares the post package, gathers evidence, drafts copy
- Reviewer: performs adversarial verification against this PRD
- Approver: grants final GO or NO-GO decision

### 6.2 Stakeholders

- maintainer
- contributors affected by public claims
- potential adopters who evaluate Drift through external websites
- future reviewers who must understand why a post was approved

### 6.3 User Needs

Author needs:

- a clear definition of what inputs are required before drafting
- a clear definition of what counts as acceptable evidence
- a deterministic way to know whether a claim is allowed

Reviewer needs:

- unambiguous gate criteria
- a way to fail drafts without oral context
- a durable record of evidence and rationale

Approver needs:

- a concise, auditable decision artifact
- confidence that the review is current and not stale

## 7. Operating Principles

- Credibility over reach
- Precision over hype
- Public consistency over local convenience
- Specific evidence over generic confidence
- Reproducibility over oral context

If a decision is ambiguous, the stricter interpretation wins.

## 8. Scope

This PRD applies to all externally visible website publications about Drift, including:

- curated tool directories
- listing sites
- product showcases
- launch platforms
- comparison sites
- partner or community websites
- long-form guest posts on external domains

This PRD does not cover:

- short social posts
- GitHub issue comments
- GitHub PR comments
- private outreach emails
- internal planning notes

If one post is mirrored across multiple websites, each website is a separate review target.

## 9. Definitions

- Low-reach post: expected reach below 500 unique referrals in 30 days, not homepage-featured by the target website, and not placed on a major launch or aggregator platform.
- High-visibility target: any target outside the low-reach definition.
- Adoption metric: evidence of real usage or integration by confirmed users, teams, or repositories under a defined counting rule.
- Reach metric: attention metric such as stars, downloads, clones, views, impressions, or page visits.
- Confidence level: the explicit strength attached to a claim source. Allowed values are high, medium, and low.
- Immediate answer: answerable within 15 minutes using the prepared evidence packet only, without new external research.
- Known gate: a documented channel requirement, threshold, or maintainer rule recorded either on the target website or in Drift distribution documentation.

## 10. Functional Requirements

### FR-1 Work Order Creation

Every website-post work item must begin with a complete work order.

The work order must include:

1. target website
2. target URL or submission entry point
3. audience description
4. post objective
5. funnel stage
6. primary claim
7. primary metric
8. primary CTA
9. landing page URL
10. author
11. reviewer
12. due date

Acceptance criteria:

- no review starts without all required fields
- missing fields produce automatic work-item incompleteness

### FR-2 Evidence Packet

Each post must have a complete evidence packet before approval.

The evidence packet must include explicit sources for:

- version
- signal count
- benchmark or trust claim
- adoption metric
- reach metric
- channel rules

Acceptance criteria:

- every strong claim in the draft maps to an evidence source
- unsupported claims are removed before review can pass

### FR-3 Source-of-Truth Precedence

When artifacts disagree, reviewers must resolve them using this order.

For product version:

1. pyproject version
2. released changelog section
3. README and docs pages
4. roadmap and secondary planning documents

For signal counts and scoring status:

1. runtime-configured weights in src/drift/config.py
2. canonical technical study pages
3. docs-site summary pages
4. secondary strategy notes

For benchmark and trust claims:

1. docs/STUDY.md
2. docs-site/trust-evidence.md
3. docs-site/benchmarking.md
4. derivative summaries

For adoption and traction metrics:

1. current metrics snapshot used by the team
2. validated-adopter summary with explicit counting rule
3. strategy memos and derivative summaries

Acceptance criteria:

- a version claim is blocked if pyproject and released changelog disagree
- a signal-count claim is blocked if config, study, and docs-site disagree
- a trust claim cannot be stronger than the highest-ranked supporting source

### FR-4 Metric Discipline

Each post must use:

- exactly one adoption metric
- exactly one primary reach metric
- exactly one primary CTA

Adoption and reach must not be merged into one proof claim.

Acceptance criteria:

- mixed metric blocks fail review
- multiple primary CTAs fail review

### FR-5 Review Record

Each work item must generate a durable review record before publication.

The review record must include:

- target website
- audience
- objective
- primary claim
- primary metric
- primary CTA
- landing page
- author
- reviewer
- reviewer timestamp
- approver
- approver timestamp
- publication window expires
- decision
- rationale
- evidence sources
- gate results with rationale

Acceptance criteria:

- no publication without review record
- no gate may be marked pass or fail without written rationale

### FR-6 Gate System

The workflow must implement the 15 blocking gates defined in Section 14.

Acceptance criteria:

- all gates must pass before approval
- any failed gate produces NO-GO until corrected

### FR-7 Failure Ownership

When a gate fails:

- Author fixes draft, evidence, or landing-page issues
- Reviewer documents the failure reason
- Approver decides whether the item returns for revision or is canceled

Acceptance criteria:

- no failed review may close without recorded disposition

### FR-8 Publication Validity Window

An approval must expire after 7 calendar days.

After expiry, the following gates must be rerun before publication:

- version consistency
- signal-count consistency
- benchmark framing
- channel viability
- release-state alignment

Acceptance criteria:

- stale approvals cannot be used for publication
- failing revalidation automatically reverts status to NO-GO

### FR-9 Channel Viability Evidence

Channel viability decisions must be based on documented requirements only.

Allowed sources:

- the target website's published rules
- the target repository's contribution or submission guidance
- a maintained Drift distribution note under docs/distribution

Undocumented assumptions must not be used as hard gates.

Acceptance criteria:

- inferred channel rules fail validation until documented

### FR-10 Two-Click Verification

Major claims must lead readers to the most specific validating page.

Acceptance criteria:

- the main claim can be verified within two clicks from the post
- generic landing-page routing fails review if a more specific evidence page exists

## 11. Non-Functional Requirements

The workflow must be:

- auditable
- reproducible
- low-ambiguity
- current-state aware
- usable without oral context

Operational thresholds:

- reviewers must be able to answer red-team questions within 15 minutes from the evidence packet
- another reviewer should be able to reproduce the decision from the artifact set alone

## 12. Success Metrics

The workflow is successful if it produces these outcomes:

- zero published posts with contradictory version claims
- zero published posts with contradictory signal counts
- zero published posts that overstate benchmark evidence beyond source wording
- zero published posts approved without a stored review record
- zero publications from expired approvals

Leading indicators:

- percentage of post drafts with complete evidence packet before review
- percentage of reviews completed without oral clarification
- percentage of channel decisions backed by documented rules

## 13. User Workflow

### Step 1. Create work order

Author creates the work order with all required fields.

Exit criterion:

- work order complete

### Step 2. Build evidence packet

Author collects all required sources.

Exit criterion:

- every strong claim has a named source

### Step 3. Draft post

Author writes the draft using one primary claim, one primary metric, and one primary CTA.

Exit criterion:

- draft exists
- unsupported statements removed

### Step 4. Review gates

Reviewer evaluates all blocking gates.

Exit criterion:

- every gate passes or explicit NO-GO is issued

### Step 5. Approve or reject

Approver issues final decision.

Exit criterion:

- GO with active validity window
- or NO-GO with written rationale

## 14. Gate Requirements

All gates are blocking.

### G1 Product Story

Requirement:

- the post reflects one official statement about Drift's current phase and priorities

Pass when:

- the post does not conflict with roadmap and current distribution strategy

Fail when:

- the draft implies a growth phase or product posture that conflicts with official artifacts

Required evidence:

- roadmap source
- current distribution strategy source from docs/distribution or equivalent maintained publication plan

### G2 Version Consistency

Requirement:

- version claims are identical across primary public sources

Pass when:

- all visible version references match, or the post avoids version claims entirely

Fail when:

- repo artifacts disagree and the draft still names a version

Required evidence:

- pyproject source
- changelog source

### G3 Signal-Count Consistency

Requirement:

- signal-count claims use one canonical count for configured, scoring-active, and report-only signals

Pass when:

- counts are aligned or omitted from the post

Fail when:

- the draft names a count contradicted elsewhere in public materials

Required evidence:

- config source
- study source
- docs-site source

### G4 Benchmark Framing

Requirement:

- numeric quality claims are framed with their methodological limits

Pass when:

- the draft makes clear whether a number is historical, synthetic, score-weighted, limited, or current

Fail when:

- a historical study number is presented as a current blanket quality claim

Required evidence:

- study source
- trust page source

### G5 Self-Scan Usage

Requirement:

- self-scan is not the primary proof of effectiveness

Pass when:

- self-scan is framed as dogfooding, example output, or transparency evidence

Fail when:

- self-scan is positioned as the core proof of external reliability

### G6 Adoption Metric Discipline

Requirement:

- the post uses one defined adoption metric

Pass when:

- one adoption number is chosen and its counting rule is known

Fail when:

- incompatible adopter counts are mixed in one draft

### G7 Reach Metric Discipline

Requirement:

- the post uses one primary reach metric

Pass when:

- one reach metric is primary and any secondary metric is clearly subordinate

Fail when:

- stars, views, downloads, and clones are piled up without a defined communication purpose

### G8 Positioning

Requirement:

- the draft defines what Drift is and what Drift is not

Pass when:

- Drift is positioned as a complementary coherence and architecture analyzer

Fail when:

- Drift is described as a general bug finder, security scanner, or universal replacement for other tool categories

### G9 Maturity Language

Requirement:

- maturity wording matches the current release posture

Pass when:

- the draft distinguishes stable core paths from experimental or optional surfaces

Fail when:

- the draft implies uniform maturity across the whole product surface

### G10 Channel Viability

Requirement:

- the target website is currently viable

Pass when:

- Drift satisfies the channel's documented hard requirements

Fail when:

- the channel has a documented unmet gate

### G11 CTA Discipline

Requirement:

- the draft has exactly one primary CTA

Pass when:

- the next action is singular and obvious

Fail when:

- the draft asks readers to do several equally important things at once

### G12 Landing-Page Fit

Requirement:

- every strong claim points to the most specific supporting page

Pass when:

- the reader can verify the main claim in no more than two clicks

Fail when:

- a generic page is used despite a more specific evidence page existing

### G13 Evidence Sufficiency

Requirement:

- every strong statement is backed by a source or removed

Pass when:

- every high-signal statement has evidence in the packet

Fail when:

- any material statement is unsupported, weakly supported, or only implied

### G14 Release-State Alignment

Requirement:

- unreleased capabilities are not marketed as available facts

Pass when:

- the draft references only released or clearly labeled planned capabilities

Fail when:

- ambiguous or unreleased items are presented as already available

### G15 Red-Team Check

Requirement:

- reviewer challenges the draft with three questions:

1. Is the number defensible?
2. Is the version defensible?
3. Is the framing defensible?

Pass when:

- all three answers are immediate and sourced

Fail when:

- any answer requires improvisation, unsupported extrapolation, or more than 15 minutes from the evidence packet

## 15. Stop Conditions

Publication stops immediately if any of the following is true:

- two public pages state different signal counts
- primary version references disagree
- a numeric quality claim is stronger than the available evidence supports
- the target channel has a documented unmet gate
- the draft uses more than one primary metric
- the draft uses more than one primary CTA
- a feature claim depends on unreleased state
- the evidence packet is incomplete

## 16. Approval Logic

A website post is publishable only if all of the following are true:

1. one clear user benefit is stated
2. one defensible metric is stated
3. limits are stated at the correct confidence level
4. one specific landing page is chosen
5. all gates pass
6. a review record exists
7. an approver issues GO
8. the approval is still within the 7-day publication window

If any one of these conditions is false, publication is forbidden.

## 17. Derived Operational Artifacts

### 17.1 Work Order Template

```md
# Website Post Work Order

- Target website:
- Submission URL:
- Audience:
- Objective:
- Funnel stage:
- Primary claim:
- Primary metric:
- Primary CTA:
- Landing page:
- Author:
- Reviewer:
- Due date:

## Draft

## Evidence Sources
- Version:
- Signals:
- Benchmark:
- Adoption:
- Reach:
- Channel rules:

## Decision
- Status: draft / in review / GO / NO-GO
- Notes:
```

### 17.2 Review Record Template

```md
## Website Post Review Record

- Target website:
- Audience:
- Objective:
- Primary claim:
- Primary metric:
- Primary CTA:
- Landing page:
- Author:
- Reviewer:
- Reviewer timestamp:
- Approver:
- Approver timestamp:
- Publication window expires:
- Decision: GO / NO-GO
- Rationale:

### Evidence
- Version source:
- Signal-count source:
- Benchmark source:
- Adoption source:
- Reach source:

### Gate Results
- G1 Product story: PASS / FAIL - rationale:
- G2 Version consistency: PASS / FAIL - rationale:
- G3 Signal-count consistency: PASS / FAIL - rationale:
- G4 Benchmark framing: PASS / FAIL - rationale:
- G5 Self-scan usage: PASS / FAIL - rationale:
- G6 Adoption metric discipline: PASS / FAIL - rationale:
- G7 Reach metric discipline: PASS / FAIL - rationale:
- G8 Positioning: PASS / FAIL - rationale:
- G9 Maturity language: PASS / FAIL - rationale:
- G10 Channel viability: PASS / FAIL - rationale:
- G11 CTA discipline: PASS / FAIL - rationale:
- G12 Landing-page fit: PASS / FAIL - rationale:
- G13 Evidence sufficiency: PASS / FAIL - rationale:
- G14 Release-state alignment: PASS / FAIL - rationale:
- G15 Red-team check: PASS / FAIL - rationale:
```

## 18. Reviewer Heuristics

Reviewers should apply these practical rules:

- If a claim mixes adoption and reach, fail metric discipline.
- If a number sounds stronger than the source wording, fail benchmark framing.
- If the landing page requires more than two clicks to verify the main claim, fail landing-page fit.
- If the author cannot point to the source-of-truth file immediately, fail evidence sufficiency or red-team check.
- If the channel rule is inferred but not documented, fail channel viability.

## 19. Acceptance Standard

This PRD is satisfied only when the publishing decision is reproducible by another reviewer without oral context.

That means:

- the evidence packet is complete
- the review record is complete
- the GO or NO-GO rationale is written down
- the publication window is explicit
- a second reviewer could reach the same decision from the same artifact set
