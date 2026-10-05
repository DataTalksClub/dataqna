"""The two themes, checked as numbers rather than as intentions.

Every ratio the stylesheet claims in a comment was true when it was written.
What went wrong with the dark theme was not a ratio: the hero band was 1.21:1
against the page — legible, because nothing was written on it, and invisible,
because that is what 1.21:1 looks like. WCAG cannot see that, so the checks
here cover figure/ground separation as well as text legibility, and both
themes have to pass the same ones.
"""

import re

from dataqna import render

CSS = render.asset_bytes("app.css").decode()

LIGHT = re.search(r"^:root \{(.*?)^}", CSS, re.S | re.M).group(1)
DARK = re.search(r'^:root\[data-theme="dark"\] \{(.*?)^}', CSS, re.S | re.M).group(1)


def tokens(block):
    return dict(re.findall(r"--([a-z0-9-]+):\s*([^;]+);", block))


# `:root` holds the raw ramps and the light mapping; a dark block overlays it,
# exactly as the cascade does. The ramps resolve into dakit's vendored sheet,
# so its light values join the table — and for the dark block its dark remap
# joins too, which is what `:root[data-theme="dark"]` does in the browser.
DK = render.asset_bytes("dakit-tokens.css").decode()
DK_ROOT = tokens(re.search(r"^:root \{(.*?)^}", DK, re.S | re.M).group(1))
DK_DARK = tokens(re.search(r'^:root\[data-theme="dark"\] \{(.*?)^}', DK, re.S | re.M).group(1))

ROOT = tokens(re.search(r"^:root \{(.*?)^}", CSS, re.S | re.M).group(1))


def resolve(block, name):
    """Follow a token through its var() chain to a literal value."""
    table = ROOT | DK_ROOT | (DK_DARK if block is DARK else {}) | tokens(block)
    seen = set()
    value = table[name].strip()
    while value.startswith("var(--") and value.endswith(")"):
        key = value[len("var(--"):-1].strip()
        assert key not in seen, f"cycle resolving {name}"
        seen.add(key)
        value = table[key].strip()
    # Gradients and shadows carry vars inside a longer expression.
    return re.sub(r"var\(--([a-z0-9-]+)\)", lambda m: table[m.group(1)].strip(), value)


def _channel(value):
    value = value / 255
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def luminance(color):
    color = color.strip().lstrip("#")
    red, green, blue = (int(color[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _channel(red) + 0.7152 * _channel(green) + 0.0722 * _channel(blue)


def contrast(foreground, background):
    high, low = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (high + 0.05) / (low + 0.05)


THEMES = {"light": LIGHT, "dark": DARK}


def test_components_touch_only_the_semantic_layer():
    """Dakit's layer rule, enforced where the app lives: below the token
    blocks nothing may name a color — no hex, no rgb(). A component that
    reaches past the semantic roles looks right in light and breaks in dark,
    and the numbers belong in the token blocks and the comments anyway."""
    body = re.sub(r"^:root \{.*?^\}", "", CSS, flags=re.S | re.M)
    body = re.sub(r'^:root\[data-theme="dark"\] \{.*?^\}', "", body, flags=re.S | re.M)
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.S)
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", body), "raw hex below the token blocks"
    assert not re.search(r"\brgba?\(", body), "raw rgb() below the token blocks"


def test_every_variable_reference_resolves():
    """A renamed token leaves its old users pointing at nothing, and var()
    fails silent — the property just stops being set, which is how the solid
    danger button lost its fill once already. Every reference in the app
    sheet must be defined by the app's blocks or the vendored dakit sheet."""
    defined = set(DK_ROOT) | set(DK_DARK) | set(tokens(LIGHT)) | set(tokens(DARK))
    used = set(re.findall(r"var\(--([a-z0-9-]+)\)", CSS))
    missing = used - defined
    assert not missing, f"references with no definition: {sorted(missing)}"


def test_light_is_what_a_link_opens_in():
    """Dark is opt-in, for everyone, whatever their device prefers. A room link
    goes to people who did not choose to be here; it opens the same for all of
    them, and the toggle is how anyone changes that. The app layer pins it the
    way dakit's sheet does, with data-theme on the root element."""
    assert "prefers-color-scheme: dark" not in CSS
    assert CSS.count(':root[data-theme="dark"] {') == 1, "dark is mapped in more than one place"


def test_ink_is_legible_on_every_filled_control():
    """Fills follow dakit's own pairing — the same buttons dataops ships —
    pinned by equality so the app cannot drift from the system: accent and
    its hover under --on-accent (dakit's ink flips with the theme), the
    solid danger button under --on-danger. The contrast floor is re-checked
    rather than trusted: accent.hover's pair is not in dakit's own list, and
    a missing definition fails var() silent — the danger button lost its
    fill once already."""
    for name, block in THEMES.items():
        for fill, source in (("accent-fill", "dk-accent-default"),
                             ("accent-fill-hover", "dk-accent-hover"),
                             ("on-accent", "dk-text-on-accent"),
                             ("danger-fill", "dk-danger-text"),
                             ("on-danger", "dk-text-on-accent")):
            assert resolve(block, fill) == resolve(block, source), \
                f"{name}: {fill} left dakit's pairing"
        for fill, ink in (("accent-fill", "on-accent"),
                          ("accent-fill-hover", "on-accent"),
                          ("danger-fill", "on-danger")):
            ratio = contrast(resolve(block, ink), resolve(block, fill))
            assert ratio >= 4.5, f"{name}: {ink} on {fill} is {ratio:.2f}:1"


def test_body_and_muted_text_are_legible_on_the_page():
    for name, block in THEMES.items():
        for token, floor in (("dk-text-primary", 7.0), ("dk-text-muted", 4.5)):
            ratio = contrast(resolve(block, token), resolve(block, "dk-bg-page"))
            assert ratio >= floor, f"{name}: {token} on the page is {ratio:.2f}:1"


def test_the_room_is_a_family_page():
    """The room once opened on a gradient hero band with an eyebrow kicker, a
    count chip and a stack of per-question cards — the landing-page tells the
    design contract (docs/design-contract.md) bans. The participant page wears
    the family anatomy now: a quiet bar, an ink-on-paper page head, one queue
    panel with divided rows. This test holds the door shut.

    It must be updated only by a contract change, never by a regression."""
    room = render.asset_bytes("room.html").decode()
    for marker in ('class="page-head"', "queue-panel", "panel-header", "room-bar"):
        assert marker in room, f"room.html lost the family anatomy: no {marker}"
    for tell in ("hero", "linear-gradient", "rgba(255, 255, 255, .14)"):
        assert tell not in CSS, f"the app sheet still carries the band's {tell}"


def test_every_page_with_a_toggle_loads_the_script_that_works_it():
    """Theme logic lives once, in theme.js; each surface opts in.

    Room, directory, notices and the co-host gate carry a compact
    [data-theme-toggle] icon. Admin, the operator app with a sidebar, puts
    the same pin behind the Account popover's appearance switch — the family
    recipe, and the only theme control on that chrome.
    """
    pages = {name: render.asset_bytes(name).decode()
             for name in ("room.html", "admin.html")}
    pages["directory"] = render.directory_page([], [])["body"]
    pages["notice"] = render.notice("Gone", "Nothing here.")["body"]
    pages["cohost gate"] = render.cohost_page(
        {"room_id": "1", "slug": "s", "title": "T", "state": "open"}, name="ivan"
    )["body"]

    for name, body in pages.items():
        assert "/assets/theme.js" in body, f"{name} never loads theme.js"
        if name == "admin.html":
            assert "data-appearance-toggle" in body, "admin lost the Account appearance switch"
            assert "data-theme-toggle" not in body, "admin still has a lone theme icon"
        else:
            assert "data-theme-toggle" in body, f"{name} has no theme toggle"


def test_the_toggle_script_is_actually_servable():
    assert render.asset_bytes("theme.js"), "theme.js is not on disk"
    import public_handler
    assert "theme.js" in public_handler.ASSETS, "theme.js is not served"


def test_pages_declare_a_canvas_colour_before_the_stylesheet():
    """`class="theme-dark"` means nothing until app.css lands, and on a cold
    cache that is long enough for the UA to paint a full screen of white."""
    bodies = [render.asset_bytes(name).decode() for name in ("room.html", "admin.html", "present.html")]
    bodies.append(render.notice("Gone", "Nothing here.")["body"])
    for body in bodies:
        head = body.split("/assets/app.css")[0]
        assert "color-scheme" in head, "no color-scheme before the stylesheet"


def test_the_room_address_bar_matches_the_page():
    """The meta is a hand-written copy of a token, so it drifts silently. The
    room has no band to paint it with anymore — it pins the page background,
    the same value every other surface uses."""
    room = render.asset_bytes("room.html").decode()
    page_dark = resolve(DARK, "dk-bg-page")
    page_light = resolve(LIGHT, "dk-bg-page")
    assert f'setAttribute("content", "{page_dark}")' in room
    assert f'data-theme-dark="{page_dark}"' in room
    assert f'data-theme-light="{page_light}"' in room


def test_the_light_qr_is_ink_on_the_page():
    """In light the page is already paper, so the code takes no plate and is
    drawn in the page's own ink — which keeps it a normal dark-on-light code
    that every decoder reads. The floor is well past AA because a camera is
    less forgiving than an eye."""
    assert resolve(LIGHT, "qr-paper") == "transparent", "light: QR grew a plate"
    for surface in ("dk-bg-page", "dk-bg-surface"):
        ratio = contrast(resolve(LIGHT, "qr-ink"), resolve(LIGHT, surface))
        assert ratio >= 10, f"light: QR on {surface} is only {ratio:.2f}:1"


def test_the_dark_qr_is_printed_on_the_brand_plate():
    """A dark page is not paper, so the code brings its own: the deep accent,
    solid — the one plate that is neither a white slab glaring at a dark room
    nor a grey one that matches nothing. The plate must stay pinned to the
    brand's deep step — a hand-copied hex would drift when dakit moves — and
    the ink must clear a reversed code's contrast floor on it."""
    assert resolve(DARK, "qr-paper") == resolve(DARK, "dk-accent-deep"), \
        "dark: the QR plate is not the brand's deep accent"
    paper = resolve(DARK, "qr-paper").lstrip("#")
    red, green, blue = (int(paper[i:i + 2], 16) for i in (0, 2, 4))
    assert blue > red and blue - min(red, green) >= 40, "dark: the QR plate is not the brand"
    ratio = contrast(resolve(DARK, "qr-ink"), paper)
    assert ratio >= 10, f"dark: QR ink on the plate is only {ratio:.2f}:1"
