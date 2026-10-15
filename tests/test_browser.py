"""Browser tests: the console's dakit shell driven in a real Chromium.

tests/browser/*.test.mjs run under `node --test` against the stub server in
tests/browser/server.py, which renders the real pages with a fake API. They
need node and Playwright with Chromium; without them the test skips. CI
installs both into tests/browser/node_modules and sets DQ_REQUIRE_BROWSER,
so there they always run. Locally, point PLAYWRIGHT_MODULE at
an existing install (for example ~/git/dataops/node_modules/playwright).
"""

import os
import pathlib
import shutil
import socket
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
BROWSER = ROOT / "tests" / "browser"


def _playwright():
    module = os.environ.get("PLAYWRIGHT_MODULE", "playwright")
    probe = subprocess.run(
        ["node", "-e", f"require({module!r})"], cwd=BROWSER, capture_output=True, text=True
    )
    return module if probe.returncode == 0 else None


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_browser_suite():
    module = _playwright()
    if module is None:
        # CI sets DQ_REQUIRE_BROWSER so a broken install fails rather than
        # quietly skipping the suite.
        assert not os.environ.get("DQ_REQUIRE_BROWSER"), "playwright is required here"
        pytest.skip("playwright not installed; set PLAYWRIGHT_MODULE")
    port = _free_port()
    server = subprocess.Popen(
        [sys.executable, str(BROWSER / "server.py"), str(port)], stdout=subprocess.PIPE, text=True
    )
    try:
        assert server.stdout.readline().strip() == "ready"
        env = dict(os.environ, DQ_BASE=f"http://127.0.0.1:{port}", PLAYWRIGHT_MODULE=module)
        tests = sorted(str(path) for path in BROWSER.glob("*.test.mjs"))
        run = subprocess.run(["node", "--test", *tests], env=env, capture_output=True, text=True)
        assert run.returncode == 0, run.stdout + run.stderr
    finally:
        server.terminate()
        server.wait()
