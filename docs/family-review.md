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
   currently substitutes `--dk-border-default`. — **Resolved upstream
   2026-10-02**: dakit `15ca9e6` fixed the spec's row-hairline role to
   `--dk-border-default`, which is what this app already ships; the
   substitution is now the spec, not a gap.
2. The canonical icon sprite family.md promises in `showcase.html` — the
   showcase carries no SVG set today, so each app redraws the shared shapes
   (dataqna's now live in `admin.js`/`present.js`/`room.js`/`theme.js`). —
   **Partially resolved upstream 2026-10-02**: dakit `15ca9e6` added the
   canonical icon set to the showcase; per-app redraws stay byte-identical
   to it, so nothing to change here.
3. If the family wants the room's 16px body officially, widen the sanctioned
   exception from "dataqna room" to "dataqna participant surfaces", or ship a
   `--dk-text-body-phone` role so it stops reading as an app-local override.
   — still open (dakit's spec still names "dataqna room" only).

## Round 2 — the reconciliation audit (2026-10-02, `00d346c`..`2700f8a`)

Re-audited against dakit at `1be906a` (the spec, base layer, component
classes and family-reference captures all moved during the first round).
Findings and what changed:

- **Vendored layers already current.** Re-running `scripts/sync_dakit.sh`
  against dakit `1be906a` is a byte-for-byte no-op: tokens, base and
  component sheets in `src/web/` match dakit's build output, and the
  cascade-order test still pins tokens → base → components → app on every
  rendered page and the asset route.
- **The focus recipe was the one real drift.** The pre-redesign sheet still
  drew the keyboard indicator its own way: a 2px outline in the plain
  accent, and text-control halos in `--dk-accent-soft` — a wash so pale on
  the page background that the halo read as nothing (measured:
  `rgb(237,245,255)` on white). Fixed in `00d346c` to the family recipe:
  `:focus-visible` is 3px translucent `--dk-focus-ring` (measured after:
  `rgba(49,95,143,0.6) solid 3px`), text controls trade the outline for an
  accent border plus a focus-ring halo on `:focus`, and the ask composer's
  focus-within halo follows the same role. Before/after crops:
  `tmp/audit-shots/composites/cmp-focus-{light,dark}-before-vs-after.png`.
  Note for dakit: its own base layer still ships `outline: 2px` at
  `:focus-visible` while the spec and dataops say 3px — the app carries the
  spec values locally until the base layer catches up.
- **Links now take the family link role** (`04cf277`): `--dk-text-link`
  instead of the bare accent — the same rendered value today, the correct
  role for theme remaps tomorrow.
- **Re-measured, all on the family scale**: sidebar 268px on
  `--dk-bg-muted` with a 1px right border; h1 32px/600; nav rows 36px at
  radius-md; group labels 11px/600/uppercase/0.07em; selected row = accent
  soft fill, no left border; panel rows 40px; primary control 34px high at
  13px text (`--dk-size-control-md`); exactly one accent fill per view
  (`Create session` on the admin list); every control glyph 16×16, stroke
  1.5, round caps, no fills.

Judge for this round: an independent dataops session (`knowledge`, reached
over aplexer — this session has no subagent-spawning tool, so cross-session
review is the independence mechanism, replacing round 1's self-review
fallback) reviewed the renders, composites and dataops reference captures
against the spec.

- **DQ-JUDGE-R1: FAIL** — six criteria, F1/F3/F6 clean, and four findings
  this app could not wave off: the console heading sat at 22px/700 instead
  of the 32px page scale; the shell's 34px control scope lost the cascade
  (a bare `:where` cannot beat the touch defaults) so console buttons and
  fields rendered at the 44px/47px touch sizes on a desktop; the directory
  carried two solid primaries and the pressed vote pill a second fill; the
  projector stacked separate bordered cards; console rows exposed three
  icon-only actions; the setup-panel chevron was a CSS border trick outside
  the SVG language; the adjacent nav rows clipped the focus ring; and the
  base layer's `h1` rule laid near-black ink over the light hero.
- **The fixes** landed in `42eccdc` (desktop control scale, with the public
  operator pages on it past 820px and the room alone keeping its sanctioned
  touch scale at every width), `1ac64f4` (console heading onto the page
  scale), and `2700f8a` (labelled row actions, inset nav focus ring, one
  bordered list on the projector, soft-accent voted pill, secondary
  directory back-link, inline-SVG disclosure chevrons, hero ink).
- **DQ-JUDGE-R2: PASS, no required fixes.** The re-review went to the
  `invoice` dataops session (DQ-JUDGE-R2B — `knowledge` had gone stale-idle
  and its delivery queue refused fresh submission) over the same aplexer
  route, against the equal-scale composites built to round 1's evidence
  caveat. All six criteria pass (F2/F5/F6 at 10, F1/F3/F4 at 8 with one
  nameable deviation each), the focus recipe passes, and its three optional
  polish items are recorded: titling the phone bar with the page (done in
  the commit above), unifying empty-state framing, and one footer-padding
  variance — the last two left open. Verdict verbatim under
  `tmp/JUDGE-round2-verdict.md`. One spec note for the next round: dakit
  `579b01b` redefined the icon geometry to dataops' rendered form (24-grid
  paths at 20px, stroke 1.8), superseding the 16/1.5 geometry this review
  scored; migrating the app's glyphs to it is underway in this tree.
