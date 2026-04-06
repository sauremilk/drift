---
name: svg-distribution-design
description: "Create or update beautiful, professional SVG assets for Drift's distribution phase. Use when users ask for SVG graphics, social cards, launch visuals, README/doc illustrations, distribution artwork, or polished vector assets for docs/distribution and docs-site."
argument-hint: "Describe the SVG asset, target location, and message, for example: create a launch SVG for docs/distribution that explains Drift in one visual or update a professional hero graphic for docs-site/assets."
---

# SVG Distribution Design Skill

## Purpose

Create polished, reusable SVG assets that support Drift's current distribution phase.

The bar is higher than merely matching the existing overview graphic. New SVG work should be able to surpass `docs-site/assets/readme-overview.svg` in clarity, composition, and finish when the task justifies it.

The truth bar is equally non-negotiable: the SVG must visualize only claims, metrics, workflows, or product properties that are supported by the repository, the user's prompt, or explicitly cited source material in the workspace.

The goal is not decorative output. The asset should help discovery, comprehension, or adoption:

- explain Drift faster in launch materials
- improve the professionalism of public-facing distribution assets
- support README, docs, articles, social posts, or outreach pages with crisp vector graphics

If visual polish conflicts with factual accuracy, factual accuracy wins.

## When to Use

- A user asks for a new SVG or wants an existing SVG improved
- A distribution or launch asset needs a visual explainer
- A docs or README section needs a professional diagram, social card, or header graphic
- A task mentions hero graphic, illustration, launch visual, social image, badge-like visual, vector asset, or SVG
- The work is explicitly tied to Distribution phase materials under `docs/distribution/` or public docs assets under `docs-site/assets/`

## Repo Context

Current roadmap phase is Distribution. During this phase, visual work should support demand validation and adoption rather than adding product features.

Prefer assets that strengthen these public surfaces:

1. `docs/distribution/` execution materials
2. `docs-site/assets/` public-facing graphics
3. `README.md` visuals that improve first-run understanding

Use the existing visual language in `docs-site/assets/logo.svg` and `docs-site/assets/readme-overview.svg` as the baseline unless the user explicitly requests a different campaign style.

Treat that baseline as the floor, not the ceiling. Reuse the brand cues, but improve the result through tighter layout rhythm, clearer hierarchy, better negative space, and a more memorable focal idea.

## Design Standard

Every SVG created with this skill should aim for these qualities:

- clear message in under 5 seconds
- professional composition, not generic clip-art
- strong hierarchy with one focal point
- crisp rendering at common documentation widths
- semantic accessibility via `title`, `desc`, and sensible `role`
- lightweight, maintainable markup that can live in git comfortably
- truthful content with no invented facts, numbers, labels, product states, or evidence signals
- production-safe layout with no text overflow, clipping, accidental overlap, or broken alignment

In addition, higher-end public assets should target:

- a stronger editorial feel than a generic product diagram
- one visually memorable move, such as a bold contrast, a striking central motif, or a more cinematic layout
- cleaner balance and spacing than the default three-card explainer pattern
- text economy, where labels support the graphic instead of carrying the whole idea

If the result feels interchangeable with a typical SaaS illustration, it is not finished.

If the result looks impressive but overstates what Drift can prove, it is not acceptable.

## Quality Bar

Use this internal bar before finalizing a public-facing SVG:

### Must-Have

- One dominant idea is obvious immediately.
- The composition still reads when scaled down.
- The color system feels intentional rather than randomly pleasant.
- Typography hierarchy is clear without relying on excessive text.
- The asset looks native to Drift's documentation surfaces.
- Every factual statement and implied claim is grounded in source material available in the workspace or directly provided by the user.
- No text, badge, chip, caption, or connector extends beyond its intended visual bounds.
- Primary headline and bottom support zone both fit inside a deliberate safe area with visible breathing room.
- Background ornaments never reduce contrast behind the headline or other high-priority copy.
- Supporting proof points are clearly intentional, not so pale or low-contrast that they read like accidental leftovers.

### Better-Than-Baseline Signals

- More disciplined spacing and alignment than `readme-overview.svg`
- More distinctive silhouette or scene structure than three equal cards in a row
- Fewer filler labels and more communication through form, grouping, and motion cues
- More polished transitions between elements, especially arrows, connectors, and grouped components
- A more refined balance between warmth, technical clarity, and visual confidence

When the asset is central to README, launch, or article distribution, do not stop at competent. Push toward memorable.

### README Hero-Specific Checks

If the asset is intended for README, docs-site hero placement, or article-header preview, all of the following must be true:

- the headline is fully readable without edge clipping on the right, left, top, or bottom
- the subtitle remains comfortably readable in a typical GitHub README view, not just in a zoomed local preview
- footer claims or proof chips carry enough contrast and visual weight to read as deliberate support, not faded residue
- the canvas includes enough outer margin that the composition feels framed rather than tightly cropped
- the top message does not overpower the lower proof layer to the point that the justification disappears
- terminal sublabels, side-card labels, and key supporting copy are not treated as microtext
- the transform path from problem to Drift output to repair step is immediately legible without guessing
- the before/after contrast is explicit enough that a first-time viewer can identify what changed
- the background stays subordinate to the explanatory content and does not blur away structural precision
- the center card is dominant but does not make the left and right cards feel incidental

## Workflow

### Step 1: Define the Communication Job

Before drawing, identify exactly what the SVG must do:

- explain a concept
- support a launch post or article
- visualize workflow or value proposition
- provide a polished header or card asset

If the message is vague, reduce it to one sentence first. The SVG should communicate one main idea, not a whole spec.

Then identify what evidence supports that message:

- repo copy already present in README, docs-site, or docs/distribution
- benchmark or trust pages already committed in the repo
- user-provided wording or data

If the claim source is unclear, narrow the claim before designing.

### Step 1a: Establish the Truth Boundary

Before adding any label, metric, badge, chart, or visual metaphor, decide which of these it is:

- directly supported fact
- faithful abstraction of a documented workflow
- clearly non-factual decorative support element

Only the third category may be invented, and it must not read like evidence, telemetry, product capability, or adoption proof.

### Step 2: Pick the Right Asset Type

Use the smallest fitting format:

- Hero graphic: for README, docs landing areas, or article headers
- Explainer diagram: for workflow, before/after, problem/solution visuals
- Social card style visual: for distribution posts and announcement assets
- Supporting illustration: for docs/distribution collateral where text already carries most detail

Do not default every request to a large diagram.

Also avoid defaulting to the same layout pattern as the existing overview unless it is genuinely the best fit.

### Step 3: Reuse Repo Visual Language

Unless explicitly overridden, inherit from the existing Drift style:

- soft warm-to-cool background gradients
- deep blue headline text
- teal and blue directional accents
- rounded cards and restrained shadows
- clean sans-serif typography with pragmatic system fallbacks

Match tone before inventing a new brand system.

However, avoid simply cloning the existing asset structure. The new work should feel related, not repetitive.

### Step 3a: Choose a Strong Composition

Prefer layouts with a clear visual decision instead of evenly distributing boxes across the canvas.

Good options include:

- one dominant hero element with smaller supporting annotations
- an asymmetric left-to-right narrative with deliberate tension
- a before/after split with one dramatic point of resolution
- a zoomed-in technical scene with layered depth instead of flat panels

Weak default to avoid:

- three same-sized cards with similar internal density and equal visual weight unless the story truly requires strict comparison
- one extremely heavy central mass with two underdeveloped side panels that read as decoration instead of argument

### Step 4: Build for SVG Strengths

Prefer native SVG primitives over raster-like hacks:

- `rect`, `path`, `line`, `circle`, `text`, `defs`, gradients, and restrained filters
- consistent `viewBox`
- scalable spacing grid
- reusable classes in a small internal `style` block when it improves maintainability

Avoid overcomplicated masks, excessive filters, huge embedded path dumps, or fragile editor-export noise when hand-authored SVG is sufficient.

Prefer elegance through proportion, spacing, layering, and color discipline over sheer element count.

Design for real string length, not ideal placeholder length. If a label, subtitle, metric, or caption is long, solve it through wrapping, shortening, resizing the container, or changing the layout instead of letting the text spill outside the intended area.

Treat the headline and the lower support band as protected zones. Do not route ornaments, glows, arcs, or decorative connectors through those zones unless readability improves rather than worsens.

### Step 5: Keep It Distribution-Ready

The output should be ready to drop into public assets:

- readable on desktop and narrow doc widths
- clear alt semantics via `title` and `desc`
- no dependency on external fonts, scripts, or linked assets
- filenames and placement aligned with the target distribution surface
- wording and visual cues that remain defensible if quoted out of context
- text blocks, chips, and panels that remain stable at realistic content lengths

### Step 6: Verify Before Finishing

Check that the SVG:

- opens cleanly
- has a sensible `viewBox`
- contains no broken references
- stays legible at likely embed widths
- still looks intentional when rendered without exotic font availability
- feels like a designed artifact, not just a wireframe with color
- would not be visually overshadowed by the existing `readme-overview.svg` if shown side by side
- does not contain invented metrics, unsupported badges, fabricated UI states, or fictional evidence cues
- would remain accurate if a reader interpreted every visible label as a product or evidence claim
- has no text overflow, clipping, cropped descenders, panel collisions, or labels floating outside their container
- has no accidental collisions between text, chips, connectors, icons, and cards
- keeps safe internal padding so long labels do not nearly touch card edges
- keeps the headline fully visible with explicit right-side slack, not just mathematically fitting text length
- keeps footer or proof-strip content dark enough and large enough to read at README embed scale
- keeps decorative background shapes away from the most important copy areas
- keeps the relative visual weight of left, center, and right regions intentional and explainable

### Step 6a: Run a Layout Failure Check

Before finalizing, inspect the SVG for these failure modes:

- text overflow beyond card, chip, badge, or canvas bounds
- clipping caused by too-small container height, incorrect line-height assumptions, or tight masks
- overlapping elements after text edits or copy changes
- inconsistent alignment between repeated elements
- unreadably small text used to avoid reflowing the layout
- connectors or arrows that no longer point cleanly to the intended target
- visually unbalanced empty space caused by late content changes
- headline clipped by canvas edge or forced into a line that only fits in the source editor
- footer claims washed out so far that they no longer read as part of the message
- decorative arcs, glows, or gradients sitting directly behind the headline or subtitle
- lower section feeling cropped, faded, or visually unfinished because the composition runs too close to the canvas edge
- central card visually swallowing the side cards so the story stops reading as a sequence
- before/after panels lacking enough contrast to show what actually transformed

If any of these appear, redesign the layout. Do not treat them as acceptable minor defects.

## Asset Placement Guidance

Choose placement based on usage:

- `docs-site/assets/` for public docs and README-facing visuals
- `docs/distribution/` for launch and outreach collateral when the SVG is part of that package
- keep asset names descriptive and stable, such as `distribution-hero.svg` or `five-repo-explainer.svg`

If updating an existing asset, preserve its path unless the user asked for a replacement strategy.

## Guardrails

- Do not produce decorative complexity without a communication gain.
- Do not introduce unrelated brand directions when existing Drift visuals already fit.
- Do not rely on external webfonts, JavaScript, or embedded bitmaps unless the task explicitly requires them.
- Do not create inaccessible SVGs missing `title` and `desc`.
- Do not create visually busy diagrams that collapse on narrow widths.
- Do not overwrite existing public assets unless the request clearly targets them.
- Do not stop at baseline quality when the asset is meant for README, launch, or distribution-facing surfaces.
- Do not mimic the existing overview card layout by habit.
- Do not substitute more labels for stronger visual storytelling.
- Do not invent metrics, percentages, benchmark outcomes, repo counts, user counts, or maturity claims.
- Do not fabricate CLI output, UI panels, findings, signal IDs, badges, or status labels unless they reflect actual Drift behavior already documented in the repo.
- Do not imply external adoption, validation, or integrations that the repo cannot support.
- Do not add decorative pseudo-data just to make the graphic feel richer.
- Do not turn uncertainty into certainty through visual emphasis.
- Do not allow text to overflow, clip, collide, or hang outside the intended component boundary.
- Do not shrink text to a barely readable size just to force it into a box.
- Do not leave alignment drift between repeated chips, cards, panels, or connector anchors.
- Do not assume short English placeholder strings; design for realistic content length.

## Factual Content Rules

- Prefer wording already present in `README.md`, `docs-site/`, `docs/distribution/`, and `docs-site/trust-evidence.md` when a public claim is needed.
- If a metric appears in the SVG, it should come from an existing committed source and be current enough for that surface.
- If a workflow is abstracted, preserve the real causal order and avoid adding non-existent intermediate steps.
- If something is only illustrative, keep it obviously illustrative rather than evidence-shaped.
- When in doubt, simplify the claim instead of embellishing it.

## Common Failure Modes To Prevent

- text overflow below or beyond a card or panel
- clipped text baselines or descenders
- labels centered mathematically but looking optically off
- chips or badges with insufficient horizontal padding for real content
- panel copy that is too dense for the selected card height
- connectors crossing text or stopping short of the intended node
- uneven spacing that makes repeated groups look accidental instead of designed
- cards that rely on one exact string length and break after copy edits

## Response Pattern

When using this skill, work in this order:

1. State the communication goal of the SVG in one sentence.
2. State which repo or user-provided facts the SVG is allowed to visualize.
3. Decide what will make this asset visually stronger than a generic explainer.
4. Choose the smallest suitable asset type and the strongest composition.
5. Reuse the repo's visual language unless a different direction is requested.
6. Create or update the SVG at the correct target path.
7. Verify accessibility, sizing, readability, factual defensibility, layout robustness, and side-by-side quality against the current baseline.
8. Report the exact file path and what the graphic is meant to communicate.

## References

- [Distribution SVG guidelines](./references/distribution-svg-guidelines.md)