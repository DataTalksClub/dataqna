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
    assert "prefers-color-scheme: dark" in body
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


def test_asset_responses_are_cacheable_because_they_are_versioned():
    response = render.asset_response("app.css")
    assert response["statusCode"] == 200
    assert "immutable" in response["headers"]["cache-control"]


def test_unknown_assets_and_traversal_are_refused():
    assert render.asset_response("nope.js")["statusCode"] == 404
    assert render.asset_response("../dataqna/config.py")["statusCode"] == 404


def test_hidden_attribute_is_forced_over_button_display():
    """`display: inline-block` on button beats the UA `[hidden]` rule, so the
    Answered tab rendered even with the attribute set."""
    css = render.asset_bytes("app.css").decode()
    assert "[hidden] { display: none !important; }" in css


def test_dark_mode_button_text_uses_the_on_accent_token():
    css = render.asset_bytes("app.css").decode()
    assert "--on-accent" in css
    # White on the dark-theme accent is 2.97:1, below AA.
    assert "color: var(--on-accent);" in css


def test_notice_always_offers_a_way_out():
    body = render.notice("Room not found", "Nothing here.", status=404)["body"]
    assert 'class="btn"' in body
    assert "/live" in body


def test_cohost_page_focuses_the_code_field():
    body = render.cohost_page()["body"]
    assert "autofocus" in body
    assert render.cohost_page(error="Bad code")["statusCode"] == 403


def test_cohost_error_is_shown_with_the_form():
    response = render.cohost_page(error="That code is not valid.")
    assert "That code is not valid." in response["body"]
    assert 'name="passcode"' in response["body"]


def test_a_known_link_name_only_asks_for_the_passcode():
    body = render.cohost_page(name="tonight")["body"]
    assert 'type="hidden" name="name" value="tonight"' in body
    assert 'name="passcode"' in body
