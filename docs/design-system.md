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
`--accent` `--accent-hover` `--accent-soft` `--accent-line` `--on-accent`
`--danger` `--ok` `--warn` (each with a `-soft` background pair) `--shadow-sm`
`--shadow-md`.

## 3. Themes

Light and dark are both first-class. `prefers-color-scheme` chooses by default, and
a page can pin one with `html.theme-light` / `html.theme-dark`.

Presentation mode pins **light**, deliberately: a projector renders white as "screen
off", and dark slides wash out in a lit room. `d` overrides it and the choice
persists in `localStorage`.

The dark mapping is duplicated — once under `@media (prefers-color-scheme: dark)`
and once under `html.theme-dark`. **Keep the two blocks identical.** CSS has no way
to express "this media query or this class" for a custom-property block without
repeating it.

## 4. Colour and contrast

Every text-on-background pair is checked against **WCAG AA**. The tightest are
accent-on-soft at 4.84:1 (light) and 5.59:1 (dark).

Two results are load-bearing and easy to undo by accident:

- **`--blurple-500` (`#635BFF`) is 4.70:1 on white.** Stripe's signature hue passes,
  but reads thin at body size. It stays decorative as `--brand`; interactive fills
  and text use `--blurple-600` (5.57:1).
- **White on the dark-theme accent is 2.49:1** — far below AA. Dark ink on it is
  7.5:1. This is why `--on-accent` exists instead of a hard-coded `#fff`, and why
  `tests/test_render.py` asserts on it. Do not delete that test; it protects a bug
  that shipped once already.

QR modules stay ink-on-white in every theme, including dark presentation mode. An
inverted QR scans unreliably on a lot of phones.

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
  the target.
- **`.vote`** is the one thing a participant taps in a dark room, one-handed. It is
  oversized on purpose.
- **`.btn.arm`** is the "are you sure" state of a destructive two-tap, not a
  separate button.
- **`[hidden] { display: none !important; }`** is required, not defensive. Author
  styles on `button` beat the UA stylesheet, so without it every hidden button
  renders. Also covered by a test.
- **`render.py` emits markup too** — `_shell`, `directory_page`, `cohost_page`,
  `notice`. Renaming a class means editing Python, not just CSS.

## 8. Presentation mode

The layout rules are in [specification.md](specification.md) §7. What belongs here:

- The ranked list uses **equal grid rows**, so the top N always fit the frame
  whether there are three questions or eight. At six or more, `.dense` trades size
  for rows — smaller type and a two-line clamp.
- Type is sized for a projector at 1920×1080 read across a lit room, not for a
  laptop at arm's length.

## 9. Changing it

1. Add or adjust a **semantic token** before adding a component rule. Most "this
   needs a new colour" turns out to be an existing token used correctly.
2. Check contrast in **both** themes, not just the one you have open.
3. If you touch the dark mapping, touch **both** copies (§3).
4. `make test` — two tests guard fixes that already regressed once (§4, §7).
