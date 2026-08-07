# DataQnA — Design System

Version 0.1 (2026-08-06)

## 1. Purpose

One stylesheet, `src/web/app.css`, dresses every surface: the participant room, the
presentation view, the admin console, and the pages `render.py` builds in Python.
This document is what that stylesheet means, so a change lands in the system rather
than beside it.

The reference is **Stripe** — slate neutrals, a blurple accent, hairline borders
under layered shadows, tight tracking on headings. Behaviour and information
architecture follow Slido (see [specification.md](specification.md)); the look does
not.

**Constraint that shapes everything:** there is no build step and no bundler.
`render.py` reads the CSS off disk and serves it. So the system is hand-written
custom properties, not a framework, and it costs one request.

## 2. The two layers

Raw ramps feed semantic tokens. **Components only ever touch the semantic layer.**

```text
--slate-900 ─┐
--navy-50  ──┼──►  --text  ──►  body, h1, .card …
--blurple-600 ┘    --accent
```

A component that reaches past `--text` to `--slate-900` looks correct in light mode
and breaks in dark, because a theme is nothing more than an alternative mapping of
the semantic layer. That is the one rule worth enforcing.

### Ramps

| Ramp | Range | Used for |
|---|---|---|
| `--slate-50…900` | `#f6f8fb` → `#1a1f36` | neutrals, light-theme surfaces and text |
| `--navy-950…50` | `#0d1220` → `#e9edf6` | dark-theme surfaces — desaturated navy, never pure black |
| `--blurple-100…850` | `#edeefd` → `#232a4d` | brand and accent |

### Semantic tokens

`--bg` `--surface` `--surface-2` `--field` `--border` `--text` `--muted` `--brand`
`--accent` `--accent-hover` `--accent-fill` `--accent-fill-hover` `--accent-soft`
`--accent-line` `--on-accent` `--danger` `--danger-fill` `--ok` `--warn` (each with
a `-soft` background pair) `--shadow-sm` `--shadow-md`.

`--accent` is the brand as text and stroke on a page background; `--accent-fill` is
the brand as a mass that has to carry ink. Light maps both to `--blurple-600`, so a
fill written as `var(--accent)` looks correct until dark maps them apart. Nothing
that takes `--on-accent` may paint itself with `--accent`.

## 3. Themes

**Light is the default, for everyone, whatever their device prefers.** A room link
is handed to a hall full of people who did not choose to be here, and it should
open the same way for all of them — the same way it looked on the slide it was
scanned from. `prefers-color-scheme` is not consulted anywhere. Dark is opt-in,
mapped once under `html.theme-dark`, and it is the only value ever written to
`localStorage` under `dq_theme` (`dq_present_theme` for presentation mode, which is
its own surface with its own default). Switching back to light clears the key
rather than storing "light".

**Every page carries a toggle** — a `[data-theme-toggle]` button — and the logic
behind it lives once, in `theme.js`. It used to live in `room.js` and `admin.js` as
the same thirty lines twice, which is exactly why the front page, the co-host gate
and the notices had none: adding one meant a third copy. A page opts in with the
button and a `<script src="/assets/theme.js" defer>`. `<html>` may carry
`data-theme-dark` / `data-theme-light` to say what the address bar should match;
the room sets them to its hero band, everything else defaults to the page
background.

Three things have to happen before first paint, and a deferred asset is far too
late for any of them, so each `<head>` carries them inline: `color-scheme`, so the
UA paints the right canvas *before the stylesheet exists* — without it a pinned
dark load on a cold cache flashes full-screen white; the `theme-dark` class; and
the `theme-color` meta. The static templates carry their own copy; `render.py`
injects `THEME_CANVAS` and `THEME_SCRIPT` into `_shell`.

Presentation mode pins **light**, deliberately: a projector renders white as "screen
off", and dark slides wash out in a lit room. That is a different decision rather
than a variation on this one, so it keeps its own script and its own storage key.

The dark mapping lives in exactly one place, `html.theme-dark`. It used to be
duplicated under `@media (prefers-color-scheme: dark)` as well, with a standing
instruction to keep the two identical; making light the default removed the media
query and the hazard with it. `tests/test_theme.py` fails if a second mapping
appears.

## 4. Colour and contrast

Every text-on-background pair is checked against **WCAG AA**. The tightest are
accent-on-soft at 4.84:1 (light) and 5.59:1 (dark).

Two results are load-bearing and easy to undo by accident:

- **`--blurple-500` (`#635BFF`) is 4.70:1 on white.** Stripe's signature hue passes,
  but reads thin at body size. It stays decorative as `--brand`; interactive fills
  and text use `--blurple-600` (5.57:1).
- **White on `--blurple-400` is 2.49:1** — far below AA, which is why the dark
  theme's *text* accent is that value and its *fill* is `--blurple-600`, white on it
  at 5.57:1 in both themes. The earlier answer — keep one accent and give it dark
  ink — cleared AA and produced a pale chip with black ink on a black page. Passing
  contrast was never the question the button was failing.
- **The dark hero band was 1.21:1 against the page.** No text sat on it, so every
  ratio passed and the band was still not visible. `tests/test_theme.py` checks
  figure/ground separation in L\* alongside the text ratios, for both themes, and
  that the band keeps the brand hue rather than going neutral.

The QR has no plate. It is drawn in the page's ink on the page's background —
`--qr-ink` / `--qr-paper`, the latter `transparent` in both themes — so in dark it
is a white code on the dark surface rather than a card laid on top of the design.
`qr.py` emits `currentColor` for exactly this.

That makes the dark code **reversed**, which is worth being precise about, because
decoders differ and the first version of this decision got it wrong by testing
one of them:

| Decoder | Normal | Reversed |
|---------|--------|----------|
| OpenCV `QRCodeDetector` | decodes | **fails** |
| WeChat (CNN-based; WeChat and many scanner apps) | decodes | decodes |

The reversal is in the QR spec, and the decoders people actually point at a screen
— phone camera apps, Lens, WeChat — handle it. OpenCV's built-in detector is an
older, weaker algorithm and does not. So this is a real but narrow risk, carried
deliberately, and mitigated by giving the code everything else it wants: pure
white ink rather than the softened body colour, and padding on the container as a
quiet zone on top of segno's own four modules. `tests/test_theme.py` holds the
contrast floor.

If a reversed code ever does prove to be a problem in the field, `--qr-ink` and
`--qr-paper` are the two values to change and nothing else moves.

## 5. Type, space, shape, motion

| Scale | Values |
|---|---|
| Type | `--text-xs .75rem` · `sm .875` · `base 1` · `lg 1.125` · `xl 1.375` · `2xl 1.75` |
| Leading | `--leading-tight 1.2` (headings) · `snug 1.35` · `body 1.55` |
| Tracking | `--tracking-tight -.02em` (headings) · `snug -.01em` · `wide .08em` (labels) |
| Space | `--space-1…10`, a 4px base: 4 8 12 16 20 24 32 40 48 64 |
| Radius | `--radius-sm 6px` · `md 8px` · `lg 12px` · `full` — pills are for tags and badges only |
| Motion | `--duration-1 120ms` · `2 180ms` · `3 260ms`, one `--ease-out` curve |

The font is the system stack. No webfont: an external request would cost more than
it buys, and the CSP forbids it anyway.

All motion sits behind `prefers-reduced-motion: no-preference`.

## 6. Elevation

Stripe's move, and the one that makes the difference: a **hairline border does the
outlining**, so shadows stay layered and low-opacity rather than doing both jobs at
once. `--shadow-sm` for resting cards, `--shadow-md` for raised surfaces. Never
both a heavy shadow and a strong border.

## 7. Components

Sections in `app.css`, in file order: base, layout, type, buttons, forms, cards and
banners, tabs, question list, empty state and toast, presentation mode.

Notes that are not obvious from the code:

- **Touch targets are 44px minimum.** `.btn.small` trims padding and type, never
  the target. `.icon-btn` is the square icon-only variant and always carries an
  `aria-label`. The admin queue's per-question actions use it deliberately, with
  presentation mode's glyphs: moderation happens a dozen times a session, so it
  must not outweigh the question text — the console's one filled control is
  Presentation mode. Only the armed "Really delete?" state speaks in words.
- **`.vote`** is the one thing a participant taps in a dark room, one-handed: a
  pill on the card's foot line — chevron and count side by side — 44px tall,
  secondary to the question text but primary to the thumb. The question card
  follows Slido's anatomy: text leads, author and time sit under it.
- **The room hero** (`.hero`) is the participant page's header band. It uses the
  `--hero-*` tokens; hero-muted is 4.81:1 on the gradient's lightest stop, so do
  not lighten the gradient without re-measuring.
- **Pinned is a badge, not a border.** No accent outline, no inset left edge —
  the room shows a `Pinned` tag, presentation mode a pin glyph sized against the
  vote count.
- **`.btn.arm`** is the "are you sure" state of a destructive two-tap, not a
  separate button.
- **Setup panels** (`details.card`) hold the admin console's done-once tasks —
  share, settings, people — as collapsed 48px summary rows below the queue, so
  the queue owns the first screenful. The chevron is drawn in CSS and flips
  when open; open/closed is a shape change, never color alone.
- **`[hidden] { display: none !important; }`** is required, not defensive. Author
  styles on `button` beat the UA stylesheet, so without it every hidden button
  renders. Also covered by a test.
- **`render.py` emits markup too** — `_shell`, `directory_page`, `cohost_page`,
  `notice`. Renaming a class means editing Python, not just CSS.

## 8. Presentation mode

The layout rules are in [specification.md](specification.md) §7. What belongs here:

- **A card is one fixed size.** Type and padding never scale with the number of
  questions: one question renders exactly like the top card of eight, the list
  just gets shorter. Past six rows the list truncates with a "+N more" line (and
  scrolls where there is touch).
- The **join panel leads on the left** — QR first, sized viewport-relative to be
  scannable from the back of a room, URL under it, session title at the foot.
- Every action is a **visible control**: per-question icon buttons on the card,
  view-level buttons in the bottom toolbar. Only arrows and Esc remain as keys.
- Type is sized for a projector at 1920×1080 read across a lit room, with an
  added phone breakpoint (≤820px) where the shell becomes a column and the list
  scrolls — the host runs sessions from a phone too.

## 9. Changing it

1. Add or adjust a **semantic token** before adding a component rule. Most "this
   needs a new colour" turns out to be an existing token used correctly.
2. Check contrast in **both** themes, not just the one you have open.
3. If you touch the dark mapping, touch **both** copies (§3).
4. `make test` — two tests guard fixes that already regressed once (§4, §7).
