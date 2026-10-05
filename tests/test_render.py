"""Page rendering: the details that only break in a browser."""

import re

from dataqna import render


def room(**overrides):
    base = {"room_id": "01K3", "slug": "podcast", "title": "Podcast #142",
            "description": "Ask anything", "state": "open", "settings": {}}
    base.update(overrides)
    return base


def test_room_page_carries_theme_and_icon():
    body = render.room_page(room(), config_payload={"room_id": "01K3"})["body"]
    assert 'name="theme-color"' in body
    assert 'class="theme-dark"' not in body  # light unless the visitor pins dark
    assert 'rel="icon"' in body
    assert "data:image/svg+xml" in body


def test_room_page_sets_link_preview_metadata():
    body = render.room_page(room(), config_payload={})["body"]
    assert '<meta property="og:title" content="Podcast #142">' in body


def test_titles_are_escaped_everywhere_they_appear():
    body = render.room_page(room(title='<script>alert(1)</script>'),
                            config_payload={})["body"]
    assert "<script>alert(1)</script>" not in body
    assert "&lt;script&gt;" in body


def test_assets_are_version_stamped():
    """A participant mid-session must not be left holding stale JS."""
    body = render.room_page(room(), config_payload={})["body"]
    stamped = re.findall(r'/assets/[a-z.]+\?v=([0-9a-f]{10})', body)
    assert stamped, body[:400]
    assert len(set(stamped)) == 1
    assert 'href="/assets/app.css"' not in body


def test_no_surface_ever_clamps_a_question_to_a_line_count():
    """Presentation mode clamped its cards to two lines once, and the host
    answered half a question in front of the room. A question is shown whole
    or the surface scrolls — line clamps must not come back."""
    assert "line-clamp" not in render.asset_bytes("app.css").decode()


def test_asset_responses_are_cacheable_because_they_are_versioned():
    response = render.asset_response("app.css")
    assert response["statusCode"] == 200
    assert "immutable" in response["headers"]["cache-control"]


def test_unknown_assets_and_traversal_are_refused():
    assert render.asset_response("nope.js")["statusCode"] == 404
    assert render.asset_response("../dataqna/config.py")["statusCode"] == 404


def test_fonts_travel_as_binary_not_decoded_text():
    """woff2 is bytes; the asset route used to .decode() every payload as
    utf-8 and served a 500 notice page in place of every font."""
    import base64

    response = render.asset_response("fonts/inter-var.woff2")
    assert response["statusCode"] == 200
    assert response["isBase64Encoded"] is True
    assert base64.b64decode(response["body"]) == render.asset_bytes("fonts/inter-var.woff2")
    assert response["headers"]["content-type"] == "font/woff2"


def test_admin_markup_is_the_family_account_popover():
    """Operator admin owns identity, appearance and sign-out in one Account
    control — avatar, name, chevron — not a lone theme icon or a toolbar
    sign-out link."""
    body = render.asset_bytes("admin.html").decode()
    assert 'aria-label="Account"' in body
    assert "account-button" in body
    assert 'id="account-menu"' in body
    assert "data-appearance-toggle" in body
    assert "Signed in as" in body
    assert "Sign out" in body
    assert "data-theme-toggle" not in body
    assert "toolbar-who" not in body


def test_account_chrome_names_the_operator_from_their_email():
    chrome = render.account_chrome(email="alexey.grigorev@datatalks.club")
    assert chrome["ACCOUNT_NAME"] == "Alexey Grigorev"
    assert chrome["ACCOUNT_INITIAL"] == "AG"
    assert chrome["ACCOUNT_EMAIL"] == "alexey.grigorev@datatalks.club"
    assert chrome["ACCOUNT_SIGN_OUT_HIDDEN"] == ""


def test_account_chrome_hides_sign_out_without_a_session():
    chrome = render.account_chrome()
    assert chrome["ACCOUNT_SIGN_OUT_HIDDEN"] == "hidden"
    assert chrome["ACCOUNT_INITIAL"] == "?"


def test_account_chrome_names_a_cohost_from_the_invite():
    chrome = render.account_chrome(cohost_name="ivan")
    assert chrome["ACCOUNT_NAME"] == "ivan"
    assert chrome["ACCOUNT_INITIAL"] == "I"
    assert chrome["ACCOUNT_EMAIL"] == "Co-host"
    assert chrome["ACCOUNT_SIGN_OUT_HIDDEN"] == ""


def test_admin_page_fills_account_chrome():
    body = render.page("admin.html", render.account_chrome(email="host@datatalks.club"))
    assert "Host" in body
    assert "host@datatalks.club" in body
    assert "{{ACCOUNT_NAME}}" not in body
    assert "data-appearance-toggle" in body


def test_the_admin_console_renders_the_signed_in_operator():
    import admin_handler
    from dataqna import config, security

    token = security.new_session_token("alexey@datatalks.club")
    event = {
        "rawPath": "/admin",
        "requestContext": {"http": {"method": "GET", "sourceIp": "203.0.113.7"}},
        "headers": {},
        "cookies": [f"{config.SESSION_COOKIE}={token}"],
        "queryStringParameters": {},
    }
    response = admin_handler.lambda_handler(event, None)
    assert response["statusCode"] == 200
    assert "Alexey" in response["body"]
    assert "alexey@datatalks.club" in response["body"]
    assert "account-button" in response["body"]
    assert "data-theme-toggle" not in response["body"]


def test_dakit_layers_ship_in_cascade_order():
    """app.css resolves its colors through the vendored dakit sheets, so the
    cascade needs them in dakit's own order — tokens, then the base layer
    (element defaults, select chevron, the color-scheme pin), then the .dk-*
    components — ahead of the app sheet, on every page that links one and in
    the server-rendered shell. The asset route has to serve all three."""
    import public_handler

    order = ("dakit-tokens.css", "dakit-base.css", "dakit-components.css", "app.css")
    for name in order:
        assert name in public_handler.ASSETS
        assert render.asset_response(name)["statusCode"] == 200
    bodies = [render.asset_bytes(name).decode() for name in ("room.html", "admin.html", "present.html")]
    bodies.append(render.notice("Gone", "Nothing here.")["body"])
    for body in bodies:
        positions = [body.index(f"/assets/{name}") for name in order]
        assert positions == sorted(positions), "dakit layers are out of cascade order"


def test_hidden_attribute_is_forced_over_button_display():
    """`display: inline-block` on button beats the UA `[hidden]` rule, so the
    Answered tab rendered even with the attribute set."""
    css = render.asset_bytes("app.css").decode()
    assert "[hidden] { display: none !important; }" in css


def test_filled_controls_never_paint_themselves_with_the_text_accent():
    """`--accent` is the brand as text; `--accent-fill` is it as a mass.

    They are the same value in light, so a fill written as `var(--accent)` looks
    right until dark maps them apart — and then it is a pale chip with dark ink
    on a black page. Contrast for the pair is checked in test_theme.
    """
    css = render.asset_bytes("app.css").decode()
    assert "background: var(--accent);" not in css
    assert "color: var(--on-accent);" in css


def test_notice_always_offers_a_way_out():
    body = render.notice("Room not found", "Nothing here.", status=404)["body"]
    assert 'class="btn"' in body
    assert "/live" in body


COHOST_ROOM = {"slug": "tonight-live", "title": "Tonight"}


def test_cohost_page_focuses_the_code_field():
    body = render.cohost_page(COHOST_ROOM, name="ivan")["body"]
    assert "autofocus" in body
    assert render.cohost_page(COHOST_ROOM, error="Bad code")["statusCode"] == 403


def test_cohost_error_is_shown_with_the_form():
    response = render.cohost_page(COHOST_ROOM, error="That code is not valid.")
    assert "That code is not valid." in response["body"]
    assert 'name="passcode"' in response["body"]


def test_the_gate_asks_only_for_the_passcode_and_names_the_session():
    """The link carries the room and the invite, so only the secret is missing."""
    body = render.cohost_page(COHOST_ROOM, name="ivan")["body"]
    assert 'action="/r/tonight-live/cohost/ivan"' in body
    assert 'name="name"' not in body
    assert "Tonight" in body
