"""No colored edge accents (dakit's rule, enforced by its own checker).

Borders are neutral 1px; status is a tinted fill plus text, selection is the
soft accent fill. `src/web/dakit/check-borders.mjs` is vendored from dakit by
`make dakit` (dakit's sync.mjs), so the rule here is whatever dakit's is.
"""

import pathlib
import shutil
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_no_accent_borders():
    r = subprocess.run(
        ["node", str(ROOT / "src" / "web" / "dakit" / "check-borders.mjs"), str(ROOT / "src" / "web")],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stdout + r.stderr
