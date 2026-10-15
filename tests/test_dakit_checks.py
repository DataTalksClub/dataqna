"""Dakit's own checkers, run where the app lives, so CI fails on drift.

All four tools are vendored from dakit into src/web/dakit/ by `make dakit`
(dakit's sync.mjs), so each rule here is whatever dakit's is:

- the vendored files still match dakit.lock.json byte for byte, so a hand
  edit to the kit is caught and the kit only changes by re-syncing;
- no colored edge accents: borders are neutral 1px, status is a tinted fill
  plus text, selection is the soft accent fill;
- no raw color literals in app styles: a raw value has no dark-theme remap,
  so colors go through the semantic --dk-* roles;
- spacing on the 4px grid and type on the --dk-text-* scale. Existing debt
  is listed in tests/scale-baseline.json, which may only shrink: a new
  violation fails, and so does an entry that no longer occurs.
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
