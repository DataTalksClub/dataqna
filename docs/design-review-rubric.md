# DataQnA — Design Review Rubric

A scoring instrument, not an essay. It exists so that a screenshot can be scored
by anyone and land on the same number. Derived from
[design-system.md](design-system.md); where the two disagree, the design system
wins and this file is wrong.

## How to score

Score **each surface separately**: room view, presentation list, spotlight,
admin console. Each surface is scored **in light and dark, at 390×844 (phone)
and 1920×1080**, against every criterion below. A criterion's score for a
surface is the *worst* of its four renders — a page that is right in light and
broken in dark is broken.

Scores are 10 (meets the stated standard exactly), 8 (one concrete, nameable
deviation), 6 (the failure mode described below), or lower (multiple failure
modes at once). There is no 9: if you cannot name the deviation, it is a 10; if
you can, it is at most an 8.

## Criteria

### 1. Spacing rhythm

Every margin, padding, and gap sits on the 4px scale (`--space-1…10`). Page
gutters are constant down one edge — content blocks share a left edge within
1px. Vertical intervals repeat from a small set (e.g. 8/12/16/24), and the gap
*between* sections is visibly larger than the gap *inside* them.

- **10:** measured paddings and gaps are all scale values; section breaks are
  ≥1.5× the intra-section rhythm; nothing touches a viewport edge closer than
  16px on phone.
- **6:** ad-hoc values (10px, 18px, 22px) mixed with scale values, or a card
  whose internal gap equals the gap between cards, so grouping is illegible.

### 2. Readability

Body text ≥16px on phone. Line length 45–90 characters for body copy. Leading
per the scale (`1.2` headings, `1.35` snug UI text, `1.55` running text). Every
text/background pair ≥4.5:1 (AA), measured numerically, in both themes —
including text over gradients, measured against the *lightest* stop it can sit
on.

- **10:** all pairs measured ≥4.5:1; no body text under 16px on phone; no line
  of running text over ~90ch.
- **6:** any pair under 4.5:1, any body text at 12–13px doing real work, or
  full-width paragraphs at 1920px with 200-character lines.

### 3. Typographic hierarchy

The type scale does work: a reader can tell title / primary content / metadata
apart at a glance without reading. On each surface the *primary* content (the
question text) is the visually dominant text. Weight and size both step; no two
adjacent levels differ by weight alone at the same size unless separated by
color.

- **10:** three or more clearly distinct levels per surface; question text
  outweighs its metadata in size *and* weight or color; labels use the
  label treatment (xs, 600, tracked caps) consistently.
- **6:** metadata at the same optical weight as content, or a page where
  everything is 14–16px regular and hierarchy is carried by position alone.

### 4. Alignment and optical balance

Elements align to shared edges. Rows that read as one unit are vertically
centered to each other. Nothing is optically off-grid: icon baselines sit with
their labels, numbers in score pills are centered, cards in a list share
identical widths.

- **10:** left edges of stacked blocks align within 1px; controls in a row
  share a centerline; no orphaned element floating in asymmetric whitespace.
- **6:** mixed alignment (some blocks centered, some left) without intent, or
  controls that sit visibly off the row centerline.

### 5. Density and economy

The layout earns its space at both extremes. Phone room view: composer plus at
least two full question cards visible on one 844px screen without scrolling —
several cards per swipe after that. Presentation at 1080p: a card is one fixed
size regardless of how many questions exist; one question looks like the top
card of eight, never inflated to fill the frame; six cards fit without
scrolling.

- **10:** the fixed-size rule holds at 1, 3, and 12 questions; phone shows ≥2
  cards below the composer; no dead band of unused space taller than one card.
- **6:** element size varies with item count, or a phone screen that fits only
  one card, or a projector frame more than a third empty with content available
  to show.

### 6. Touch targets and control affordance

Every interactive element has a ≥44×44px hit area on touch layouts. Every
action is a visible, labeled (or accessibly named) control — nothing reachable
only by keyboard, hover, or knowledge. Primary action per surface is visually
primary (filled); secondary actions are quieter but discoverable.

- **10:** all targets ≥44px measured; icon-only buttons carry `aria-label`;
  destructive actions gated by an armed state; undo reachable within one tap of
  the action it reverses.
- **6:** any control under 40px on touch, any action with no visible control,
  or two adjacent controls whose hit areas overlap visual boundaries.

### 7. State clarity

Pinned, answered, pending, hidden, voted, selected, busy, disabled — each state
is legible without relying on color alone (badge text, icon, position, or
weight also changes), and no two states share a treatment. An in-flight action
shows feedback within 100ms of the tap (optimistic change or busy indicator).

- **10:** every state has a text or shape signal plus its color; voted vs
  unvoted distinguishable in grayscale; a click acknowledges instantly even on
  a slow network.
- **6:** a state carried by hue alone, or an action that visibly does nothing
  until a network round trip completes.

### 8. Theme parity

Dark is designed, not derived: surfaces are the navy ramp (never pure black),
elevation still reads (border + shadow), accents remapped to the dark-safe
values, QR stays ink-on-white, and every contrast pair re-measured. Pinning a
theme overrides `prefers-color-scheme` everywhere, including the browser chrome
(`theme-color`).

- **10:** both themes pass every other criterion independently; no light-theme
  asset or hard-coded hex leaks into dark; toggle state survives reload and
  applies before first paint.
- **6:** dark theme with washed-out borders, inverted QR, white-flash on load,
  or any hard-coded color that ignores the semantic layer.

### 9. Edge cases

The layout survives the awkward inputs: zero questions, exactly one, twenty; a
500-character question; a 60-character room title; a URL that wraps. Empty
states say what will appear and how to cause it. Overflowing text truncates or
wraps deliberately — no horizontal scroll of the page body, no card blown up by
one long word.

- **10:** all listed cases rendered and checked; long words break
  (`overflow-wrap`), clamped text shows an ellipsis, empty states are written
  for their specific tab.
- **6:** any case that misaligns the layout, a one-item list styled differently
  from a many-item list, or a generic "nothing here" for every empty state.

### 10. Composition and purpose

The surface reads as designed for its job: the room view leads with asking and
voting (one-handed, at an event); presentation leads with the join affordance
and the ranked questions (readable across a room); admin leads with the queue.
The first screenful contains the surface's reason to exist. Decoration never
outranks content.

- **10:** on first paint, the primary action/content is inside the first
  screenful at both sizes; visual emphasis order matches task order; nothing
  competes with the question text for attention.
- **6:** chrome (headers, join panels, toolbars) consuming more of the frame
  than content, or the primary action below the fold on phone.

## Calibration: the rejected first pass scores 4

The design shipped at commit `990748c` (the first design-system pass, live at
the time of writing) was rated **4/10 by the user**. Scored against this
rubric it lands there, which is the check that the rubric discriminates.
Scores below are the worst across its surfaces and renders:

| Criterion | Score | Why |
|---|---|---|
| 1 Spacing | 5 | Presentation cards were grid-stretched to fill the frame, so internal padding lost all relation to content; `.dense` changed the rhythm at six items |
| 2 Readability | 3 | `body.present { overflow: hidden }` clipped the list on a phone with no way to scroll; question text 400-weight at the same size as UI chrome |
| 3 Hierarchy | 5 | Room card: question text, author, and controls at near-equal optical weight; the vote box outweighed the question |
| 4 Alignment | 4 | The one-question presentation card centered a line of text in a frame-tall box — content optically adrift in whitespace |
| 5 Density | 2 | Element size depended on item count (equal grid rows + `.dense`): one question inflated to fill 1080p, the case the user named |
| 6 Touch/affordance | 2 | Every moderation action in presentation mode was keyboard-only, advertised by a footer legend; no visible control existed |
| 7 State clarity | 4 | Admin actions gave no feedback for ~2s (two round trips before any change); pinned relied on an accent border |
| 8 Theme parity | 5 | Both themes existed and passed AA, but nothing let a user override the system preference, and presentation `theme-color` was hard-coded |
| 9 Edge cases | 3 | One question "looks bad" (user), phone presentation "doesn't fit" (user); both are listed awkward cases |
| 10 Composition | 4 | The join affordance — the product's entire on-ramp — was a badge in a corner with a join code nobody needed; a hotkey legend occupied the foot |

Average ≈ **3.7 → 4**. Anything this rubric rates 7+ on that build (nothing
above does) is a criterion that fails to discriminate and must be sharpened.
A redesign scoring 10 must therefore be unrecognisable next to it, not a
sibling of it.

## Reporting

Publish a table: criterion × surface, one score and a one-line justification
per cell, per theme/size where they differ. A surface ships when every
criterion is 10. "It looks fine" is not a justification; a measurement or a
named comparison is.
