# DataQnA — the room's design contract (adversarial redesign)

The participant room is the last surface that predates the family. The console,
the public directory, the co-host gate and the projector all speak dakit's
anatomy — ink on paper, hairline rules, one bordered container — and passed
three family-judge rounds. The room still reads as a landing page. This file is
the attack that names why, and the contract that fixes it. It is a re-skin:
class names, element IDs, and every behavior in `room.js` stay as they are.

## Phase 1 — the attack (what makes the room read "generic AI")

Verifiable claims about this codebase, not taste:

1. **Gradient as decoration.** `--hero-bg` is a two-stop 135° accent gradient
   painted as a full-bleed band over the first screenful (`app.css`, the
   `--hero-*` block and `.hero`). No family surface carries a gradient — not
   the console, not the directory, not the projector. The band is the page's
   single loudest element, and it says nothing.
2. **Eyebrow over the heading.** `.hero-kicker` is an uppercase, letterspaced,
   bold micro-label with a pulsing dot sitting above the h1 — the template
   hero pattern. No console page has an eyebrow.
3. **A chip for a fact.** The question count renders as "5 questions" in a
   translucent white pill on the band (`.live-count`). The family renders
   counts as data — mono, in a panel header hint (`render.py` `_room_panel`
   does exactly this) — never as a chip.
4. **A card stack where the family has rows.** `li.q` draws one bordered card
   per question. The room's own siblings — the admin queue (`.queue-panel`)
   and the projector list (`ol.present-list`) — are ONE bordered container
   with hairline-divided rows. The family rubric's F2 failure mode is
   literally "nested cards"; the room is the last card stack in the app.
5. **A floating composer.** `.composer` carries `--dk-shadow-overlay` and a
   negative-margin overlap dug into the band. Family containers are bordered,
   not floating; elevation is for overlays, not for the first thing on a page.
6. **The design fights its own token system.** `.hero h1` must re-override the
   base layer's heading ink because the band put white type where the theme's
   ink belongs — the band is an impostor surface the sheet has to keep
   apologizing for (the browser's address bar is painted to match it too).
7. **Uniform softness.** Pill on the chip, pill on the tabs, pill on the vote,
   pill on the toast, 14%-white chip on the band — everything rounded, nothing
   sharp; the page has no tension between chrome and content.

Not tells, and kept deliberately: the pill filter tabs (the admin queue uses
the same control), the vote pill (the product's brand glyph and the one thing
a participant taps in the dark), the 16px participant body and 44px touch
floor (the sanctioned phone-first exceptions), the dakit type/space/radius
scales, the focus recipe, light-as-default.

## Phase 2 — the contract: the room is a family page

One direction, applied without exceptions: **the room wears the same anatomy
as every other page in the family** — a quiet bar, an ink-on-paper page head,
content in bordered containers with hairline-divided rows.

Concrete values:

- **Top bar.** Sticky, `--dk-bg-page`, 1px `--dk-border-default` bottom
  hairline, 56px tall. Left: the live dot (8px accent circle, pulsing under
  `prefers-reduced-motion: no-preference`) + "Live Q&A" in
  `--dk-text-muted`, 500 weight, sentence case. Right: the staff console and
  projector links and the theme toggle as quiet chrome — transparent until
  hover, 44px touch target. The gradient band, the kicker style, and the
  translucent chip are **deleted**, not restyled.
- **Page head.** `.page-head` / `.page-desc`, the console's own classes: h1 at
  `--dk-text-page` 32px/600 (`--dk-text-xl` on phone), description in
  `--dk-text-muted`. Ink on paper. No band, no eyebrow, no chip.
- **Composer.** The same bordered container the family uses: 1px
  `--dk-border-default`, `--dk-radius-md`, `--dk-bg-surface`, **no shadow**.
  The `:focus-within` accent border + `--dk-focus-ring` halo stays — it is
  the family's input recipe. The overlap into the band is gone with the band.
- **Queue.** One `.panel` with a banded header (`--dk-bg-muted`): h2
  "Questions", the count as a mono `panel-hint`, and the filter tabs — the
  admin queue's exact anatomy. Questions are rows inside it: hairline
  `border-bottom` dividers, no per-row border or radius, `--dk-bg-hover` on
  hover. The empty state lives inside the panel.
- **Counts are data.** Mono, `panel-hint` muted, in the queue's header band.
- **QR plate (dark).** With the gradient gone the dark plate is solid
  `--dk-accent-deep` — still the brand, still not a white slab, still ≥10:1
  for the reversed code. Light stays ink-on-page.
- **Banned list** — must never reappear on any dataqna surface: gradients as
  decoration; uppercase letterspaced eyebrows above headings; chips that
  carry counts; per-item bordered cards inside a list; overlay shadows on
  resting surfaces; full-bleed brand bands behind content.
- **Untouched.** Type scale (16px participant body), 44px touch floor, the
  vote pill, the tabs control, the toast, banners, the focus recipe,
  `room.js` behavior, light-is-the-default.

## Verification

`tests/test_theme.py` re-pinned to the new pairs (the hero band checks retire
with the band; the QR plate checks pin the solid plate; the address bar pins
the page, not the band). Every surface re-rendered light/dark at 1440 and 390
and judged by an independent agent against the attack list above.
