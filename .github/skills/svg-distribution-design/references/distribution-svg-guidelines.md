# Distribution SVG Guidelines

These notes define the default design baseline for SVG assets created during Drift's distribution phase.

## Communication First

Each asset should support one of these outcomes:

- make Drift easier to understand at a glance
- make a public-facing artifact feel more credible and polished
- improve adoption materials used in articles, docs, outreach, or README surfaces

If the SVG does not improve one of those outcomes, simplify it or do not create it.

Truthfulness is part of communication quality. A polished SVG that overclaims, invents support, or visualizes fictional evidence is a bad asset even if it looks excellent.

## Evidence and Truth Boundary

Public SVGs in this repo should only visualize:

- statements already supported by repository documentation
- metrics already published in committed repo content
- workflows already described by the product or docs
- user-provided facts that are clearly in scope for the requested asset

They should not visualize:

- invented benchmark numbers
- fictional usage or adoption signals
- fake terminal output or fake product UI just to make the asset feel more complete
- extra findings, signals, or statuses not grounded in Drift's current documented behavior
- decorative pseudo-data that can be mistaken for evidence

When an element is decorative, it should read as decorative. When an element reads like data, it must be real.

## Repo Style Baseline

Existing visuals in `docs-site/assets/readme-overview.svg` establish a usable default:

- background gradient from `#f8f5ee` to `#eef6f3`
- directional accent gradient from `#1f7a6b` to `#2d5b9f`
- primary headline text around `#14324a`
- supporting text around `#476073` to `#5b7487`
- rounded cards on white with subtle blue shadow treatment

Typography fallback pattern already used in the repo:

- `'Segoe UI', Arial, sans-serif`
- `Consolas, 'Courier New', monospace` for technical labels when needed

Do not treat these values as a rigid brand system. Treat them as the default family to keep public visuals coherent.

Important: `readme-overview.svg` is the current baseline, not the target maximum. New flagship SVGs should preserve brand fit while improving at least three of these dimensions:

- composition distinctiveness
- spacing discipline
- focal clarity
- reduction of repetitive panel structure
- premium visual finish

If a new asset merely looks like a variant of the existing overview, the design work is too conservative.

## What Better Looks Like

Compared with the current overview style, stronger SVGs should usually show:

- a more decisive focal point
- fewer equally weighted regions competing for attention
- more intentional use of empty space
- fewer helper labels doing explanatory work the forms should already convey
- cleaner connector logic and less diagrammatic clutter
- one memorable visual gesture that makes the asset recognizable in a feed or doc page

This does not mean louder or more complex. It means more selective.

It also means more honest: better visuals compress truth more elegantly; they do not compensate for thin evidence by inventing detail.

## Preferred Asset Shapes

Choose one of these structures first:

1. Three-panel story
   - problem
   - Drift intervention
   - outcome

2. Single hero with supporting chips
   - strong headline
   - compact supporting proof points
   - one visual anchor

3. Before/after comparison
   - fragmented state
   - unified state
   - minimal annotation

4. Signal-to-action explainer
   - finding source
   - Drift output
   - next action

Avoid using the same structure repeatedly across multiple public assets. Variety within the same visual family is preferable.

## Composition Heuristics

- Use one primary mass and one secondary mass before adding tertiary details.
- Let one region dominate by scale, contrast, or density.
- Align groups on a clear internal grid, but avoid making every block identical.
- Use connectors only where they improve comprehension; otherwise imply flow through placement.
- Reserve bright accent colors for meaning, not decoration.
- Keep the dominant mass strong without collapsing the flanking regions into visual afterthoughts.
- Protect headline and proof-band zones from ornamental interference.

When in doubt, remove one cluster and make the remaining story stronger.

## Layout Robustness Rules

- Give text containers real internal padding, not just barely sufficient padding for the current copy.
- Size chips, badges, and cards for realistic string lengths.
- Avoid placing critical copy flush to rounded corners or visual edges.
- Prefer reflow, wrapping, or layout change over aggressive font shrinking.
- Keep repeated elements on a measurable alignment system so drift is visible and fixable.
- Leave enough vertical room for descenders and multi-line text blocks.
- Treat the canvas edge as a hard boundary unless intentional bleed is clearly part of the design.
- Reserve a visible safe margin for headline endings, footer strips, and outer cards so the asset never feels tightly cropped.
- Keep key support text above a README-credible reading threshold; do not demote essential claims to tiny annotation text.
- Ensure lower support zones have enough contrast to function as evidence or argument, not as ambient decoration.
- If the background contains arcs, glows, or texture, place them away from high-priority reading lines.

## Anti-Patterns

- three equal cards with equal visual weight by default
- too many pills, chips, or badges acting as filler
- text-heavy panels that read like a slide deck
- arrows everywhere instead of structural grouping
- ornamental gradients without hierarchy benefit
- shadows used to compensate for weak composition
- headline running long without reserved landing space near the canvas edge
- decorative background marks sitting directly behind the headline
- pale footer chips that look ghosted out instead of intentionally supportive
- central card so visually heavy that the story no longer reads left-to-right
- before/after states too similar to communicate transformation quickly
- fictional metrics presented as if measured
- fake credibility cues such as fabricated benchmark stamps or made-up status pills
- diagrams that imply product capabilities not documented anywhere in the repo
- text hanging outside a card or beyond the canvas
- clipping used accidentally because the container is too short
- layout that only works for one exact sentence length
- tiny text used as a patch for weak layout decisions
- connectors misaligned after copy or spacing changes

## SVG Implementation Rules

- include `viewBox`
- include `role="img"`
- include `title` and `desc`
- prefer a small `style` block over repeated inline style noise
- keep IDs stable and minimal
- use groups only where they improve readability
- keep filters restrained and optional
- keep text sizes and weights intentionally tiered, not arbitrarily mixed
- prefer reusable classes for recurring labels, chips, cards, and annotation styles
- keep path geometry clean enough that future edits remain practical
- validate text anchoring, container size, and line breaks after any copy change
- prefer explicit multi-line text layout over hoping one long string fits

## Preflight Checklist

Before shipping an SVG, confirm all of the following:

- no text crosses the visual boundary of its container
- no element touches the canvas edge unintentionally
- no line of copy depends on subpixel luck to fit
- no repeated group is visibly off-grid
- no label becomes unreadable at likely embed size
- no arrow or connector becomes ambiguous after scaling
- no headline sits close enough to the right edge that a README crop or render will cut it off
- no background ornament competes with the highest-priority text
- no footer proof strip fades so much that it looks accidental or overblended
- no major card feels compositionally abandoned next to a dominant center block
- no claimed transformation relies on decorative arrows more than on explicit visual contrast

## README Hero Review

For README hero or overview assets, validate these questions explicitly:

- Is the headline fully visible with comfortable right-side space?
- Is the subtitle readable in a normal GitHub page width without zooming?
- Does the lower claim band read as argument, not haze?
- Does the canvas feel framed rather than tightly cropped at the top and bottom?
- Is the flow from fragmented state to Drift interpretation to shared path obvious on first glance?
- Is the difference between before and after visually unmistakable?
- Does the background support the scene without softening it into vagueness?
- Does the center panel lead the eye without demoting the side panels into decoration?

## Self-Review Rubric

Before considering the asset finished, score each item from 1 to 5:

- clarity at first glance
- uniqueness of composition
- visual polish
- brand fit with Drift
- readability at embed size
- maintainability of SVG markup
- factual defensibility
- layout robustness

If any public-facing distribution asset scores below 4 on clarity, uniqueness, visual polish, brand fit, factual defensibility, or layout robustness, revise it.

## Distribution-Phase Fit Check

Before finalizing, ask:

- Does this asset help someone understand Drift faster?
- Does it strengthen a distribution surface already present in the repo?
- Would this still look professional in README, docs, or a launch post preview?
- Is the SVG understandable without surrounding long-form text?
- Would every factual-looking element survive a challenge of: "Where in the repo is this supported?"
- Could the layout survive a small copy edit without breaking visually?

If the answer is mostly no, the asset is not ready.
