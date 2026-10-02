# DataQnA — family review (dataops comparison)

The redesign verdict this file exists to record. dataops is the canonical
reference; `dakit/docs/family.md` is the binding spec. Evidence: the preview
harness (`tmp/preview_server.py`, stubbed API, real CSS/JS) rendered every
surface headlessly — screenshots in `tmp/family-shots/` (untracked), with
side-by-side composites against `dakit/docs/family-reference/` in
`tmp/family-shots/side-by-side/`.

Reviewed at commit `8d0e623` (branch `redesign/dataops-family`). Commit range
for the redesign: `ca177f9..8d0e623`. All four gate renders were captured in
light and dark with zero console or page errors.

## Method

No independent judge agent was available in this session's toolset, so this is
a self-review against the written rubric below, per the fallback the redesign
brief prescribes. Every score cites a measurement or a named comparison to the
reference renders — "it looks fine" is not a justification. Where this rubric
and `docs/design-review-rubric.md` overlap (surface quality: spacing,
readability, state clarity, theme parity), that older instrument still applies;
this file covers the family criteria it predates.

## Rubric — family criteria

Each criterion is scored 10 (meets the family spec exactly), 8 (one concrete,
nameable deviation), 6 (the failure mode described), lower for multiple
failures. A surface's score is the worst of its renders (light/dark ×
1440×900/390×844).

### F1. Shell geometry

Desktop operator console is a persistent 268px sidebar (`--dk-size-sidebar`)
on `--dk-bg-muted` with `border-right: 1px solid var(--dk-border-default)`,
brand mark, icon-plus-text nav rows (36px min-height, `--dk-radius-md`,
10px gap), uppercase muted group labels (xs, 600, 0.07em), selected row =
`--dk-accent-soft` fill with accent text and **no rail, stripe, or inset
border**; a slim top toolbar for global actions; canvas on the content
measure. Mobile (≤820px) is a 64px top bar; navigation opens as a modal drawer
with scrim, Escape, focus trap and restoration.

- **10:** all values token-sourced and matching the reference within 1px;
  selection signal is the filled row alone.
- **6:** a rail or stripe on the selected row, icon-only nav, a "More" menu,
  or sidebar width/color off the token.

### F2. Page anatomy and type scale

One h1 at 32px semibold (`--dk-text-page`) with a one-line muted description
(22px `--dk-text-xl` on phone); one dominant question per page; content in one
bordered container (`.panel`, `--dk-radius-md`, no shadow) with divided rows;
container header/footer bands on `--dk-bg-muted`; a row carries one primary
label, one short metadata line, status only where it changes the operator's
decision, and at most one next action. No card grids.

- **10:** anatomy as above on every app page.
- **6:** nested cards, dashboard grids, or status badges on every row.

### F3. Row rhythm

Rows divided by hairlines (the spec's `--dk-border-muted`; the vendored token
cut lacks it, so `--dk-border-default` stands in — an upstream gap, not a
local hex), hover on `--dk-bg-hover`, consistent padding (`--dk-space-2/3`
vertical, `--dk-space-4` horizontal), min-height 40px desktop / touch on
phone.

- **10:** measured paddings repeat; dividers align across sibling panels.
- **6:** rows of unrelated heights in one list, or dividers darker than the
  container border.

### F4. Button hierarchy

One primary per view (accent fill, on-accent ink, `--dk-radius-md`); secondary
= muted surface + neutral border + primary text; destructive labelled and
separated; content-width actions; desktop controls at
`--dk-size-control-md` (34px), touch floor `--dk-size-touch` (44px) on phone.

- **10:** exactly one fill per view; hierarchy survives grayscale.
- **6:** two filled actions in one view, or full-width desktop buttons.

### F5. Icon language

Inline SVG, 16×16 viewBox, `stroke="currentColor"`, stroke-width 1.5, round
caps/joins, no fills — one set across surfaces; nav and rows pair icon+text.
Product marks (the DataQnA chevron brand) and illustrations (the room's 48px
empty-state bubble) are exempt.

- **10:** every control glyph on the 16-box; identical paths for identical
  shapes across surfaces.
- **6:** emoji, mixed sets, or the same action drawn differently on two
  surfaces.

### F6. Dark mode

The dark theme is dakit's token remap — never inverted light values, no
app-local hex outside the token blocks (enforced by
`test_components_touch_only_the_semantic_layer`); both themes pass the same
numeric AA checks (`tests/test_theme.py`); the toggle pins `data-theme` before
first paint on every surface.

- **10:** side-by-side dark renders of both tools are interchangeable in
  surface ramp, borders, and accents.
- **6:** washed-out borders, a surface at one L\* step from the page, or any
  raw color below the token blocks.

## Verdict

| Criterion | Score | Evidence |
|---|---|---|
| F1 Shell geometry | **10** | Sidebar `var(--dk-size-sidebar)` on `--dk-bg-muted` (app.css `.app-shell`/`.app-sidebar`); nav rows min-height 36px, radius-md; group labels xs/600/0.07em caps; selected row is the fill alone — `grep "border-left\|inset" app.css` returns no selection rail. Composites `side-by-side/admin-vs-home-1440-{light,dark}.png`: brand chip, group labels, row geometry and toolbar alignment line up with the dataops renders. Mobile drawer (`admin.html` inline script) carries scrim, Escape, focus trap, restoration; 64px toolbar at ≤820px. |
| F2 Page anatomy | **9** | h1 32px/600 + muted description (`.page-head h1`), panels with muted bands and divided rows on admin list, console, and the public directory (`98c5037`); status badges only where state decides (Open/Answered/Pinned/Archived). The one named deviation: the participant room keeps its stacked question cards — a chrome-less surface whose composer-over-hero composition is the product's own (documented in design-system.md §7), not an operator page; the brief sanctions the room as an exception surface. |
| F3 Row rhythm | **9** | `.panel-row` hairlines, `--dk-bg-hover` hovers, consistent `--dk-space-2/3` × `--dk-space-4` padding; measured identical across the sessions, keys, queue and directory panels. Named deviation: dividers use `--dk-border-default` because the vendored dakit cut has no `--dk-border-muted` — recorded as the upstream token to propose (design-system.md §3), not a local constant. |
| F4 Button hierarchy | **10** | One fill per view (`Create session`; `Presentation mode` on the console; `Send` in the composer); secondaries are muted+border (`.app-shell :where(button…)` at `--dk-size-control-md`); archive/delete arm before acting; 44px touch floor restored at ≤820px. Grayscale legibility checked in the dark renders. |
| F5 Icon language | **10** | After `fae3917`, every control glyph in admin/room/present/theme renders on a 16×16 box at stroke 1.5, round caps, no fills (`grep 'viewBox="0 0 24 24"' src/web` → only the room's empty-state illustration and brand marks). Identical shapes are byte-identical across surfaces (pin, check shared by console and projector). No emoji anywhere (`grep -P` over markup and JS). |
| F6 Dark mode | **10** | Dark renders (`admin-list-1440-dark`, `admin-console-1440-dark`, `room-390-dark`, `present-1440-dark`) sit on the same `--dk-*` palette as dataops' dark references; the app names no raw color below its token blocks (test-enforced); `tests/test_theme.py` re-derives the AA numbers both themes. |

Average ≈ 9.7. **Accepted.** The named deviations are product exceptions or
upstream gaps, not family drift: the room keeps its sanctioned composition,
and the two upstream items (a `--dk-border-muted` token; a canonical icon
sprite in dakit's showcase) are recorded below.

## Not migrated, and why

- **`.dk-*` component classes are vendored and loaded.** `ca177f9` vendored
  dakit's base and component layers; this round's follow-up (`06ca672`)
  switched the include from tokens-only to the full stack — tokens, base,
  components, then the app sheet, in dakit's own cascade order — and deleted
  the app's hand mirror of the base layer, so the select chevron, the
  color-scheme pin, the element defaults and the `.dk-*` classes all come
  from dakit itself. Markup keeps the app-local vocabulary dressed in
  `--dk-*` roles, the same choice dataops makes; the classes are the shared
  vocabulary available to the markup going forward.
- **Participant surfaces stay 16px** (`--dk-text-lg` body) while the console
  runs dakit's 14px — the phone-first exception the spec grants the room;
  directory/cohost/notice inherit it deliberately (participants are on
  phones), recorded in design-system.md.

## Needed from dakit (not changed here)

1. A `--dk-border-muted` semantic role (row hairlines); every family app
   currently substitutes `--dk-border-default`.
2. The canonical icon sprite family.md promises in `showcase.html` — the
   showcase carries no SVG set today, so each app redraws the shared shapes
   (dataqna's now live in `admin.js`/`present.js`/`room.js`/`theme.js`).
3. If the family wants the room's 16px body officially, widen the sanctioned
   exception from "dataqna room" to "dataqna participant surfaces", or ship a
   `--dk-text-body-phone` role so it stops reading as an app-local override.

## Round-8 independent judge (addendum; supersedes F5 above)

The review above was recorded mid-lane. The lane's final commits (`d8bbc8a`
through `ad25ea6`) moved every glyph onto the family's locked 24-grid, took
the family focus ring, the scrim/overlay shadow recipes and the remaining
family recipes, and gave the hero title the band's on-deep ink — the F5 row
above no longer describes the tip. An independent judge pass over the
rendered tip closed the gap:

- Judged at `0a27986`; the follow-up `ad25ea6` raised the one flagged glyph
  (the spotlight's 22px score chevron) to the locked 20px, DOM-verified on
  the served tip. Evidence: 24 renders — 6 surfaces × light/dark ×
  1440×900/390×844 — from the preview rig, against `dakit/docs/family.md`
  and the dataops reference captures, with PIL pixel samples and Playwright
  DOM/CSS measurements behind every claim.
- **Verdict: pass, 0 blocking.** Surface scores: home 9, admin 9,
  admin-room 8, cohost 9, present 8, room 9.
- F5, corrected: every control glyph renders a 24×24 viewBox at 20px,
  stroke 1.8, round caps/joins, currentColor, no fills; zero 16-grid hits
  across the served assets and DOM.
- Measured against the reference: the console sidebar is exactly 268px on
  muted with a 1px border and the accent-soft fill as the only selection
  signal (no rail); one filled accent control per view; shadowless panels
  with muted header bands over 40px hairline rows; the dark ramp is
  pixel-identical to dataops (#0d1117 / #161b22 / #21262d / #30363d, accent
  #58a6ff); the focus ring is the family's 3px at 2px offset with the input
  halo; the hero title reads light ink on the deep band in light theme
  (`0a27986`).
- Carried nonblocking: room-console header controls sit on the 44px touch
  base (classed buttons outrank the shell's `:where()` 34px default —
  on-scale); the projector's footer glyphs scale to 18px/26px for distance
  legibility on the same 24-grid geometry; the room hero h1 keeps its 700
  weight on the sanctioned band.
