# DataQnA — Design System

Version 0.2 (2026-10-02) — adopted dakit; version 0.1 (2026-08-06) was the
pre-dakit local system.

## 1. Purpose

One stylesheet, `src/web/app.css`, dresses every surface: the participant room, the
presentation view, the admin console, and the pages `render.py` builds in Python.
This document is what that stylesheet means, so a change lands in the system rather
than beside it.

The system itself is **dakit** (`~/git/dakit`), the design system shared with
dapier, dataops and relay — its `docs/principles.md` is the philosophy and its
`docs/adoption.md` maps each tool onto it. DataQnA is a *remap* adoption: the
accent changed hue (blurple → dakit blue), the dark surfaces went from navy to
dakit's neutral dark, and the type, spacing and radius scales are dakit's. What
remains local is product, not style: the room hero band, the QR plate, toasts,
and one deliberate accent divergence (§4).

**Constraint that shapes everything:** there is no build step and no bundler.
`render.py` reads the CSS off disk and serves it. So dakit ships vendored —
`src/web/dakit-tokens.css` plus the self-hosted fonts, refreshed by
`scripts/sync_dakit.sh` from a sibling dakit checkout after running its build —
and it costs two requests.

## 2. The layers

Dakit has the layers and owns the direction of dependency: primitives (raw
ramps, this repo never touches them) → semantic roles (`--dk-*`, both themes,
contrast-checked at dakit's build) → components. This app adds a third, local
row to the semantic layer and components touch only that:

```text
dakit semantic (--dk-bg-page, --dk-accent-deep, --dk-danger-text …)
        │
DataQnA roles (--accent-fill, --hero-bg, --qr-paper, --toast-text …)
        │
body, .card, .vote, .hero …
```

`tests/test_theme.py` enforces the two rules that make this safe: no component
rule names a color (hex or rgb) below the token blocks, and every `var()` in
the sheet resolves to a definition. `var()` fails silent — a token renamed
without its readers is how a button loses its fill and nothing errors.

The app's roles in `app.css`: `--accent-fill` / `--accent-fill-hover` /
`--on-accent` / `--on-danger`, the `--hero-*` band, the `--qr-*` pair, the
`--toast-*` pill, plus motion (`--ease-out`, `--duration-*`), the snug leading
and tracking roles, and one spacing step (`--space-9`, 48px, under the hero).
Everything else a component needs is a `--dk-*` token.

## 3. Themes

**Light is the default, for everyone, whatever their device prefers.** A room link
is handed to a hall full of people who did not choose to be here, and it should
open the same way for all of them — the same way it looked on the slide it was
scanned from. `prefers-color-scheme` is not consulted anywhere; this is a
deliberate turn from dakit's README boot script, whose fallback is the OS
preference — right for a console you open yourself, wrong for a page an audience
is handed. Dark is opt-in, pinned with dakit's `data-theme="dark"` attribute on
`<html>` (the attribute is the whole contract — no classes), and `dq_theme` is
the only value ever written to `localStorage` (`dq_present_theme` for
presentation mode, which is its own surface with its own default). Switching
back to light writes `"light"` rather than clearing the key, and every reader
treats anything but `"dark"` as light.

**Every page carries a toggle** — a `[data-theme-toggle]` button — and the logic
behind it lives once, in `theme.js`. It used to live in `room.js` and `admin.js` as
the same thirty lines twice, which is exactly why the front page, the co-host gate
and the notices had none: adding one meant a third copy. A page opts in with the
button and a `<script src="/assets/theme.js" defer>`.

Three things have to happen before first paint, and a deferred asset is far too
late for any of them, so each `<head>` carries them inline: `color-scheme`, so the
UA paints the right canvas *before the stylesheet exists* — without it a pinned
dark load on a cold cache flashes full-screen white; the `data-theme` attribute;
and the `theme-color` meta. The static templates carry their own copy; `render.py`
injects `THEME_CANVAS` and `THEME_SCRIPT` into `_shell`.

Presentation mode pins **light**, deliberately: a projector renders white as "screen
off", and dark slides wash out in a lit room. That is a different decision rather
than a variation on this one, so it keeps its own script and its own storage key.

The app's dark mapping lives in exactly one place, the `:root[data-theme="dark"]`
block of `app.css` — and it is small, because dakit remaps every `--dk-*` role in
the same block of the vendored sheet. Only the app's own roles need a word there:
the accent fill's dark value, the hero's muted tone and hairline, the toast's
inverted pair, the QR plate. `tests/test_theme.py` fails if a second mapping
appears in the app sheet.

## 4. Colour and contrast

Dakit owns the palette: one blue accent, neutral surfaces, status hues that report
state and do nothing else. Every `--dk-*` pair dakit's consumers can co-occur is
measured at dakit's build; the app's own pairs are measured in
`tests/test_theme.py`, both themes, hero band and QR plate included. The tightest:
accent-on-soft 6.03:1 (light) and 5.45:1 over a card (dark, dakit's translucent
soft composited); hero-muted on the band's lightest stop 7.94:1 (light) / 5.37:1
(dark).

Filled controls follow dakit's own pairing in both themes — the accent under
its `--dk-text-on-accent` ink, `accent-hover` on hover — the same buttons
dataops ships. In dark that is the bright accent (#58a6ff) with near-black ink
at 7.49:1; since the pairing is defined and measured at dakit's build, it is
verified there rather than re-asserted here. The solid danger button also
follows dakit: dakit has no deep red that could hold white ink in dark — its
dark danger (#f85149) is built to be a text color, and white on it is 3.35:1 —
so the fill is `--dk-danger-text` and the ink is the same `--dk-text-on-accent`:
white in light (5.35:1 on #cf222e) and near-black in dark (5.64:1 on #f85149).
The hover is dakit's `--dk-danger-hover`, no filter.

The dark hero band keeps the brand. It is the same gradient in both themes —
`accent-deep → accent-deeper` — darkened by the role remap, 20.5 L* off the dark
page at the stop that shows. A navy panel once cleared every text check on it
and was still invisible at 1.21:1 against the page; the L* floor in
`test_theme.py` exists because of that.

The QR is one pair of tokens, `--qr-ink` / `--qr-paper`, and the theme decides
what paper is. In light the page itself is paper: no plate, the code is drawn in
the page's ink like any other mark, and stays a normal dark-on-light code that
everything decodes. A dark page is not paper, so there the code brings its own —
`--qr-paper` maps to `--hero-bg`, and white modules sit on the brand gradient.
`qr.py` emits `currentColor` on a transparent ground for exactly this.

Three dark treatments were tried and rejected before this one: dark-on-white,
which projects a glaring white slab at a darkened room; dark ink on a dimmed
grey plate, which reads as a slab that matches nothing on the page; and bare
white modules on the surface, which have high contrast and no object to be —
an unframed spray with no quiet zone and no relationship to the cards around
it. The hero band is the one plate that answers all three at once: it gives
the code edges, a radius, and a colour the page already speaks — it is how
this product paints the thing it wants everyone to look at, and the join code
*is* that thing. The container's padding is quiet zone on top of segno's four
modules, and it keeps the modules off the plate's rounded corners.

That keeps the dark code **reversed**, which is worth being precise about,
because decoders differ and the first version of this decision got it wrong by
testing one of them:

| Decoder | Normal | Reversed |
|---------|--------|----------|
| OpenCV `QRCodeDetector` | decodes | **fails** |
| WeChat (CNN-based; WeChat and many scanner apps) | decodes | decodes |

The reversal is in the QR spec, and the decoders people actually point at a screen
— phone camera apps, Lens, WeChat — handle it. OpenCV's built-in detector is an
older, weaker algorithm and does not. So this is a real but narrow risk, carried
deliberately, and mitigated by giving the code everything else it wants: pure
white ink at 11.2:1 on the gradient's lightest stop, and generous quiet zone.
Rendered screenshots of all three placements were decoded rather than assumed:
the WeChat decoder reads the dark code at every size down to the full-screen
overlay scaled to 12%, and the light code decodes with both decoders.
`tests/test_theme.py` holds the contrast floor on every gradient stop and fails
if the plate stops being the hero's.

If a reversed code ever does prove to be a problem in the field, `--qr-ink` and
`--qr-paper` are the two values to change and nothing else moves.

## 5. Type, space, shape, motion

Type, space, radius and the fonts are dakit's; consult its `docs/tokens.md` for
the scales. What this app adds to the record:

| Scale | Values |
|---|---|
| Type | dakit's steps; the body stays **16px** (`--dk-text-lg`) and so do fields |
| Leading | dakit tight 1.2 (headings) · app snug 1.35 · dakit normal 1.5 (body) |
| Tracking | `-.02em` headings · `-.01em` controls · `.08em` labels — app roles |
| Space | dakit's 4px grid (`--dk-space-1…8`) + one app step, `--space-9` 48px |
| Radius | dakit's: controls and cards both at the 10px step, pills for tags/badges |
| Motion | `--duration-1/2/3` 120/180/260ms, one `--ease-out` curve — app roles |

The 16px body is the one break with dakit's type scale, and it is load-bearing:
this text is read on phones one-handed, and iOS Safari zooms any focused field
set below 16px, which would turn every ask into a viewport jolt. Dakit's ops
tools run a 14px body on desktop consoles; this app's readers hold it at arm's
length.

The fonts are dakit's faces, self-hosted next to the sheet (SIL OFL,
`fonts/LICENSE.md`): Inter for prose, IBM Plex Mono for passcodes and IDs —
data reads as data. v0.1 used the system stack on the reasoning that a webfont
was an external request the CSP forbade; self-hosted same-origin fonts are not
that, and one shared voice across the internal tools is worth two cached
`woff2` files. `font-display: swap`, so text never waits on them.

All motion sits behind `prefers-reduced-motion: no-preference`. Note the
deliberate scope: dakit's own base sheet kills *every* animation under
`prefers-reduced-motion`, which would still the composer's in-flight ring —
feedback, not decoration — so this app vendors tokens only and keeps its own
base, which is dakit's sanctioned integration for apps with their own
component styles.

## 6. Elevation

A **hairline border does the outlining**, so shadows stay layered and low-opacity
rather than doing both jobs at once: dakit's `--dk-shadow-card` for resting cards,
`--dk-shadow-overlay` for raised surfaces. Never both a heavy shadow and a strong
border. The dark theme gets dakit's dark shadows; a dark page is too dark for a
small shadow to add anything, and elevation there comes from the surface being
lighter.

## 7. Components

Sections in `app.css`, in file order: base, layout, type, buttons, forms, cards and
banners, tabs, question list, empty state and toast, presentation mode.

Notes that are not obvious from the code:

- **Touch targets are 44px minimum** (dakit's `--dk-size-touch`, applied as a
  floor rather than a control height — dakit's 34px control is a desktop
  measure). `.btn.small` trims padding and type, never the target. `.icon-btn`
  is the square icon-only variant and always carries an `aria-label`. The admin
  queue's per-question actions use it deliberately, with presentation mode's
  glyphs: moderation happens a dozen times a session, so it must not outweigh
  the question text — the console's one filled control is Presentation mode.
  Only the armed "Really delete?" state speaks in words.
- **`.vote`** is the one thing a participant taps in a dark room, one-handed: a
  pill on the card's foot line — chevron and count side by side — 44px tall,
  secondary to the question text but primary to the thumb. The question card
  follows Slido's anatomy: text leads, author and time sit under it.
- **The room hero** (`.hero`) is the participant page's header band. It uses the
  `--hero-*` tokens; the floors are in `test_theme.py`, so do not lighten the
  gradient without re-measuring.
- **Pinned is a badge on the room, a tint on the projector.** The room shows a
  `Pinned` tag; presentation mode tints the card. The pin is exclusive, so the
  one tinted card reads as the question the host is holding up — no outline, no
  inset left edge, which would say it with noise instead.
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

1. **Color, type, space or radius?** Change it in dakit first (`tokens/*.json`,
   both themes, contrast pair, `node build.mjs`), commit there, then
   `scripts/sync_dakit.sh` and adapt. A token dakit doesn't have is a token to
   propose, not a hex to inline — the layer-rule test will refuse the inline.
2. Add or adjust an **app role** in `app.css`'s token blocks before adding a
   component rule. Most "this needs a new colour" turns out to be an existing
   token used correctly.
3. Check contrast in **both** themes, not just the one you have open —
   `tests/test_theme.py` is where the numbers live; add the new pair to it.
4. `make test` — two tests guard fixes that already regressed once (§4, §7),
   and two more guard the layer rule and the token graph (§2).
