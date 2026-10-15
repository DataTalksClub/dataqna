"""Dakit's own checkers, run where the app lives, so CI fails on drift.

All four tools are vendored from dakit into src/web/dakit/ by `make dakit`
(dakit's sync.mjs), so each rule here is whatever dakit's is:

- the vendored files still match dakit.lock.json byte for byte, so a hand
  edit to the kit is caught and the kit only changes by re-syncing;
- no colored edge accents: borders are neutral 1px, status is a tinted fill
  plus text, selection is the soft accent fill;
- no raw color literals in app styles: a raw value has no dark-theme remap,
  so colors go through the semantic --dk-* roles;
- spacing on the 4px grid and type on the --dk-text-* scale. The baseline
  (tests/scale-baseline.json) is empty and may only shrink, so any new
  violation fails;
- the pages the server renders carry no style="" attributes, and their own
  <style> blocks pass the same three checkers, so Python templates cannot
  slip values past them.
"""

import pathlib
import shutil
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
KIT = ROOT / "src" / "web" / "dakit"
WEB = ROOT / "src" / "web"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def _run(*args):
    r = subprocess.run(["node", *map(str, args)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_vendored_kit_matches_its_lock():
    _run(KIT / "sync.mjs", "--check", "--dest", KIT)


def test_no_accent_borders():
    _run(KIT / "check-borders.mjs", WEB)


def test_no_raw_colors():
    _run(KIT / "check-colors.mjs", WEB)


def test_spacing_and_type_stay_on_the_scales():
    _run(KIT / "check-scale.mjs", "--baseline", ROOT / "tests" / "scale-baseline.json", WEB)


def _rendered_pages():
    """Every page the server renders, as HTML, with representative data."""
    from dataqna import render

    room = {"room_id": "R1", "slug": "podcast", "title": "Podcast", "state": "open",
            "description": "Ask anything.", "settings": {"listed": True}}
    rooms = [dict(room, q_total=3)]
    return {
        "admin": render.page("admin.html", render.account_chrome(email="host@datatalks.club")),
        "room": render.room_page(room, config_payload={})["body"],
        "present": render.present_page(room, config_payload={})["body"],
        "directory": render.directory_page(rooms, rooms, signed_in="host@datatalks.club")["body"],
        "directory-empty": render.directory_page([], [])["body"],
        "cohost": render.cohost_page(room, name="ivan")["body"],
        "cohost-error": render.cohost_page(room, error="Wrong passcode.", name="ivan")["body"],
        "notice": render.notice("Gone", "Nothing here.")["body"],
    }


def test_rendered_pages_carry_no_inline_styles():
    """Python-rendered markup is outside the CSS files the checkers scan, so
    a style="" attribute there would put spacing, type or color past every
    rule above. Pages carry classes; app.css carries the values."""
    for name, body in _rendered_pages().items():
        assert 'style="' not in body and "style='" not in body, name


def test_rendered_pages_pass_the_checkers(tmp_path):
    """The rendered pages' own <style> blocks go through the same three
    checkers as the stylesheets, so a template cannot bypass them."""
    for name, body in _rendered_pages().items():
        (tmp_path / f"{name}.html").write_text(body)
    _run(KIT / "check-borders.mjs", tmp_path)
    _run(KIT / "check-colors.mjs", tmp_path)
    _run(KIT / "check-scale.mjs", tmp_path)
