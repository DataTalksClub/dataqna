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

LIGHT = re.search(r"/\* Semantic mapping: light\. \*/(.*?)\n}", CSS, re.S).group(1)
DARK = re.search(r"^html\.theme-dark \{(.*?)^}", CSS, re.S | re.M).group(1)
MEDIA_DARK = re.search(
    r"@media \(prefers-color-scheme: dark\) \{\s*html:not\(\.theme-light\) \{(.*?)\n  }",
    CSS, re.S,
).group(1)


def tokens(block):
    return dict(re.findall(r"--([a-z0-9-]+):\s*([^;]+);", block))


# `:root` holds the raw ramps and the light mapping; a dark block overlays it,
# exactly as the cascade does.
ROOT = tokens(re.search(r"^:root \{(.*?)^}", CSS, re.S | re.M).group(1))


def resolve(block, name):
    """Follow a token through its var() chain to a literal value."""
    table = ROOT | tokens(block)
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


def lightness(color):
    """CIE L*, which is where a difference the eye can see shows up as a number."""
    relative = luminance(color)
    if relative > 216 / 24389:
        return 116 * relative ** (1 / 3) - 16
    return relative * 24389 / 27


def first_stop(gradient):
    return re.search(r"(#[0-9a-fA-F]{6})", gradient).group(1)


THEMES = {"light": LIGHT, "dark": DARK}


def test_the_two_dark_blocks_stay_identical():
    """One is for the system preference and one for the pin, and every change
    has to land in both. Nothing but this catches a change made to one."""
    strip = lambda block: re.sub(r"\s+", " ", re.sub(r"/\*.*?\*/", "", block, flags=re.S)).strip()
    assert strip(DARK) == strip(MEDIA_DARK)


def test_ink_is_legible_on_every_filled_control():
    """The pair that inverted in dark: a fill light enough to read as text on
    the page is too light to carry white."""
    for name, block in THEMES.items():
        for fill in ("accent-fill", "accent-fill-hover", "danger-fill"):
            ratio = contrast(resolve(block, "on-accent"), resolve(block, fill))
            assert ratio >= 4.5, f"{name}: on-accent on {fill} is {ratio:.2f}:1"


def test_body_and_muted_text_are_legible_on_the_page():
    for name, block in THEMES.items():
        for token, floor in (("text", 7.0), ("muted", 4.5)):
            ratio = contrast(resolve(block, token), resolve(block, "bg"))
            assert ratio >= floor, f"{name}: {token} on bg is {ratio:.2f}:1"


def test_the_hero_reads_as_a_band_against_the_page():
    """It is the room page's whole composition — the composer climbs into it.

    A dark navy panel cleared every text check on it and still was not a band,
    because it was 8.8 L* off the page it sat on.
    """
    for name, block in THEMES.items():
        band = first_stop(resolve(block, "hero-bg"))
        step = abs(lightness(band) - lightness(resolve(block, "bg")))
        assert step >= 15, f"{name}: hero is only {step:.1f} L* from the page"


def test_the_hero_keeps_the_brand_in_both_themes():
    """Dark does not get a greyer product; it gets the same hue, lower."""
    for name, block in THEMES.items():
        band = first_stop(resolve(block, "hero-bg")).lstrip("#")
        red, green, blue = (int(band[i:i + 2], 16) for i in (0, 2, 4))
        assert blue > red and blue - min(red, green) >= 40, f"{name}: hero is not the brand"


def test_hero_text_is_legible_on_the_band():
    for name, block in THEMES.items():
        band = first_stop(resolve(block, "hero-bg"))
        for token, floor in (("hero-text", 4.5), ("hero-muted", 4.5)):
            ratio = contrast(resolve(block, token), band)
            assert ratio >= floor, f"{name}: {token} on the hero is {ratio:.2f}:1"


def test_every_page_with_a_toggle_loads_the_script_that_works_it():
    """The toggle is markup on four surfaces and logic in one file.

    It used to be logic in two files, which is why the front page had no
    toggle at all: adding one meant a third copy of the same thirty lines.
    """
    pages = {name: render.asset_bytes(name).decode()
             for name in ("room.html", "admin.html")}
    pages["directory"] = render.directory_page([], [])["body"]
    pages["notice"] = render.notice("Gone", "Nothing here.")["body"]
    pages["cohost gate"] = render.cohost_page(
        {"room_id": "1", "slug": "s", "title": "T", "state": "open"}, name="ivan"
    )["body"]

    for name, body in pages.items():
        assert "data-theme-toggle" in body, f"{name} has no theme toggle"
        assert "/assets/theme.js" in body, f"{name} never loads theme.js"


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


def test_the_room_address_bar_matches_the_band_it_sits_under():
    """The meta is a hand-written copy of a token, so it drifts silently."""
    room = render.asset_bytes("room.html").decode()
    band = first_stop(resolve(DARK, "hero-bg"))
    assert f'content="{band}" media="(prefers-color-scheme: dark)"' in room
    assert f'data-theme-dark="{band}"' in room


def test_the_qr_is_never_reversed_by_a_theme():
    """Being scanned is the only reason this element exists, and a reversed
    code is not universally readable — OpenCV's decoder fails on one and reads
    the same image once it is inverted back. Dark may dim the paper; it may not
    swap the two."""
    for name, block in THEMES.items():
        ink = luminance(resolve(block, "qr-ink"))
        paper = luminance(resolve(block, "qr-paper"))
        assert ink < paper, f"{name}: QR modules are lighter than the plate"
        ratio = contrast(resolve(block, "qr-ink"), resolve(block, "qr-paper"))
        assert ratio >= 7, f"{name}: QR is only {ratio:.2f}:1"
