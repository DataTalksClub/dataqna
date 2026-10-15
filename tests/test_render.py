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
    stamped = re.findall(r'/assets/[a-z./]+\?v=([0-9a-f]{10})', body)
    assert stamped, body[:400]
    assert len(set(stamped)) == 1
    # Every asset reference, including the vendored kit under /assets/dakit/,
    # carries the stamp: the route caches for a day as immutable.
    assert not re.search(r'(?:href|src)="/assets/[^"?]+"', body)


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

    response = render.asset_response("dakit/fonts/inter-var.woff2")
    assert response["statusCode"] == 200
    assert response["isBase64Encoded"] is True
    assert base64.b64decode(response["body"]) == render.asset_bytes("dakit/fonts/inter-var.woff2")
    assert response["headers"]["content-type"] == "font/woff2"


def _between(body, start, end):
    return body.split(start, 1)[1].split(end, 1)[0]


def test_admin_wears_the_dakit_topbar_shell():
    """Two destinations, so dakit's topbar shell (docs/shell.md §4.2): the
    wordmark, Live Q&A and Sessions in one bar, the avatar-only account
    trigger at its end. No sidebar, no rail, no drawer, no bell, and none of
    the app's own shell script or classes left over."""
    body = render.asset_bytes("admin.html").decode()
    assert 'class="dk-shell dk-shell--topbar console"' in body
    assert 'class="dk-skip-link" href="#main-content"' in body
    bar = _between(body, '<header class="dk-shell__bar">', "</header>")
    assert '<span class="dk-brand__name">DataQnA</span>' in bar
    nav = _between(bar, '<nav class="dk-shell__nav" aria-label="Primary">', "</nav>")
    assert re.findall(r'class="dk-nav-item" href="([^"]+)"', nav) == ["/live", "/admin"]
    assert nav.count('aria-current="page"') == 1
    end = _between(bar, '<div class="dk-shell__end">', "</div>")
    assert "dk-account-trigger--compact" in end
    assert 'data-dk-popover-trigger="dk-account-menu"' in end
    assert 'aria-controls="dk-account-menu"' in end
    assert '<main class="dk-main" id="main-content"' in body
    assert "/assets/dakit/shell.js" in body
    for gone in ("dk-sidebar", "dk-notif", "app-shell", "app-sidebar", "sidebar-", "account-button",
                 "data-sidebar", "data-account-menu", "brand-mark"):
        assert gone not in body, gone


def test_admin_account_menu_is_the_dakit_disclosure():
    """Identity, the one theme control, the build, sign out — in that order,
    with no destinations, header bar or close button (docs/shell.md §6)."""
    body = render.page("admin.html", render.account_chrome(email="host@datatalks.club"))
    menu = _between(body, 'id="dk-account-menu" data-dk-popover hidden>', '<div id="dk-live"')
    order = [menu.index(marker) for marker in (
        'class="dk-menu__identity"', 'role="switch"', 'class="dk-menu__meta"', "Sign out")]
    assert order == sorted(order)
    assert "host@datatalks.club" in menu
    assert 'class="dk-menu__item" type="button" role="switch" aria-checked="false" data-appearance-toggle' in menu
    assert '<span class="dk-switch" aria-hidden="true"></span>' in menu
    assert 'class="dk-menu__item dk-menu__item--danger" href="/auth/logout"' in menu
    assert f"build {render.version()}" in menu
    # Only sign out leaves the menu; nothing else in it is a destination.
    assert re.findall(r'href="([^"]+)"', menu) == ["/auth/logout"]
    assert "Signed in as" not in menu and "aria-label=\"Close" not in menu
    assert "data-theme-toggle" not in body


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
    assert "dk-account-trigger" in response["body"]
    assert "data-theme-toggle" not in response["body"]


def test_dialog_helper_is_loaded_on_every_page():
    """Native <dialog class="dk-dialog"> dismisses on backdrop click only
    when the vendored helper has registered once on the document."""
    import public_handler

    assert "dakit/dialogs.js" in public_handler.ASSETS
    assert render.asset_response("dakit/dialogs.js")["statusCode"] == 200
    bodies = [render.asset_bytes(name).decode() for name in ("room.html", "admin.html", "present.html")]
    bodies.append(render.notice("Gone", "Nothing here.")["body"])
    for body in bodies:
        assert "/assets/dakit/dialogs.js" in body


def test_tabs_helper_is_loaded_where_a_segmented_control_lives():
    """Arrow keys and the roving tabindex of a .dk-tabs radiogroup come from
    the vendored dakit helper, so the asset route serves it and every page
    that carries a segmented control loads it."""
    import public_handler

    assert "dakit/tabs.js" in public_handler.ASSETS
    assert render.asset_response("dakit/tabs.js")["statusCode"] == 200
    for name in ("room.html", "admin.html"):
        assert "/assets/dakit/tabs.js" in render.asset_bytes(name).decode()


def test_dakit_bundle_ships_ahead_of_the_app_sheet():
    """app.css resolves its colors through the vendored dakit bundle (tokens,
    then the dk.base and dk.components cascade layers), so the bundle is
    linked ahead of the app sheet on every page that links one and in the
    server-rendered shell. The asset route has to serve both."""
    import public_handler

    order = ("dakit/dakit.css", "app.css")
    for name in order:
        assert name in public_handler.ASSETS
        assert render.asset_response(name)["statusCode"] == 200
    bodies = [render.asset_bytes(name).decode() for name in ("room.html", "admin.html", "present.html")]
    bodies.append(render.notice("Gone", "Nothing here.")["body"])
    for body in bodies:
        positions = [body.index(f"/assets/{name}") for name in order]
        assert positions == sorted(positions), "dakit bundle is out of cascade order"


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


def test_question_filters_are_dakit_segmented_radiogroups():
    """The room's Popular/Recent/Answered and the console's All/Unanswered/
    Answered each narrow one list to a single choice: dakit's segmented
    control as a radiogroup, with exactly one segment in the tab order. The
    app sheet never draws a .dk-tab itself."""
    import re

    for name, group in (("room.html", "question-view"), ("admin.html", "question-filter")):
        body = render.asset_bytes(name).decode()
        track = re.search(r'<div class="dk-tabs" role="radiogroup" id="%s" aria-label="[^"]+">(.*?)</div>' % group, body, re.S)
        assert track, name
        segments = re.findall(r'<button [^>]*>', track.group(1))
        assert segments and all('class="dk-tab" role="radio"' in s for s in segments)
        assert sum('aria-checked="true" tabindex="0"' in s for s in segments) == 1
        assert all('aria-checked="false" tabindex="-1"' in s for s in segments if 'aria-checked="true"' not in s)
        assert 'class="tabs"' not in body
    css = render.asset_bytes("app.css").decode()
    assert not re.search(r"\.dk-tab\b[^,{]*\{", css)
    assert ".tabs" not in css


def _element_paths(body):
    """Each element with an id or a button, with the classes and ids of every
    ancestor, so a test can say where an action sits on the page."""
    from html.parser import HTMLParser

    void = {"meta", "link", "input", "br", "img", "hr", "path", "circle", "rect", "source"}

    class Walker(HTMLParser):
        def __init__(self):
            super().__init__()
            self.stack, self.found = [], []

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            node = {"tag": tag, "id": attrs.get("id"), "class": attrs.get("class") or "", "attrs": attrs, "text": ""}
            if tag == "button" or node["id"]:
                self.found.append((node, list(self.stack)))
            if tag not in void:
                self.stack.append(node)

        def handle_endtag(self, tag):
            if tag in void or all(node["tag"] != tag for node in self.stack):
                return
            while self.stack:
                if self.stack.pop()["tag"] == tag:
                    break

        def handle_data(self, data):
            for node in self.stack:
                node["text"] += data

    walker = Walker()
    walker.feed(body)
    return walker.found


def test_new_session_rides_on_the_session_list_not_the_page_header():
    """dakit "Action placement": the create sits right after the title of the
    collection it creates into, as dakit's collection header, and the page
    header holds only the title and description. It is the page's one create,
    so it carries the c shortcut, and the form it opens is a dialog."""
    body = render.asset_bytes("admin.html").decode()
    found = _element_paths(body)
    by_id = {node["id"]: (node, path) for node, path in found if node["id"]}

    button, path = by_id["new-session"]
    assert "dk-collection-create" in button["class"] and "dk-button--sm" in button["class"]
    assert "New session" in button["text"]
    assert button["attrs"].get("aria-keyshortcuts") == "c"
    assert "data-dk-create" in button["attrs"]
    assert "dk-collection-header__lead" in path[-1]["class"]
    assert "dk-collection-header" in path[-2]["class"].split()
    assert not any("page-head" in node["class"] for node in path)
    # Title first, then the create, in the lead.
    lead = re.search(r'<div class="dk-collection-header__lead">(.*?)</div>', body, re.S).group(1)
    assert lead.index('id="sessions-title"') < lead.index('id="new-session"')

    # The sessions page header carries no actions at all.
    list_head = re.search(r'<div id="view-list" hidden>\s*<header class="dk-page-header">(.*?)</header>', body, re.S).group(1)
    assert "<button" not in list_head and "<a " not in list_head and "__actions" not in list_head

    # The old inline "New session" panel is gone; its form lives in the dialog.
    _, create_path = by_id["create"]
    assert any(node["id"] == "new-session-dialog" for node in create_path)
    assert '<div class="panel-header"><h2>New session</h2></div>' not in body
    assert sum("data-dk-create" in node["attrs"] for node, _ in found) == 1


def test_an_empty_session_list_repeats_the_create():
    """The empty state offers the create again as a secondary, and the header
    button stays put."""
    script = render.asset_bytes("admin.js").decode()
    assert "Create the first session" in script
    assert "dk-empty__actions" in script and "dk-button--secondary" in script
    assert "Create one above" not in script
    # The directory's New session link opens the same dialog on arrival.
    assert '"#new-session"' in script


def test_the_session_page_keeps_only_its_own_actions_in_its_header():
    """A record's detail page may keep that record's own actions in its
    header: Presentation mode and Copy link act on this session. No create,
    refresh or export sits there."""
    body = render.asset_bytes("admin.html").decode()
    actions = re.search(r'<div class="dk-page-header__actions">(.*?)</div>', body, re.S).group(1)
    assert re.findall(r'id="([^"]+)"', actions) == ["present", "copy-link"]
    assert not re.search(r"\b(New|Create|Add|Refresh|Export)\b", actions)


def test_collection_helper_is_loaded_where_a_collection_create_lives():
    """The c shortcut comes from dakit's collection.js, vendored as
    dakit/collection.js: served from the asset route and loaded by the console,
    the one page with a collection create."""
    import public_handler

    assert "dakit/collection.js" in public_handler.ASSETS
    assert render.asset_response("dakit/collection.js")["statusCode"] == 200
    assert "/assets/dakit/collection.js" in render.asset_bytes("admin.html").decode()
    assert "dakitCollection.installShortcut" in render.asset_bytes("admin.js").decode()
