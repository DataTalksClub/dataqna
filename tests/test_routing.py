"""Routing: a page the app renders must be reachable through API Gateway.

Handler tests call `lambda_handler` directly, so they pass whether or not the
gateway would ever hand the request over. The co-host passcode gate shipped
that way once — the page rendered, the form posted, and API Gateway answered
`{"message": "Not Found"}` because `/r/{proxy+}` was declared GET-only.
"""

import pathlib
import re

from dataqna import render

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "template.yaml"

# The intrinsic tags (!Ref) make the template unloadable by a plain YAML
# parser, and the routes are one-line flow mappings, so read them as text.
ROUTE = re.compile(r"Path:\s*'?([^,']+)'?\s*,\s*Method:\s*(\w+)")

FORM = re.compile(r'<form[^>]*method="POST"[^>]*action="([^"]+)"', re.IGNORECASE)


def routes():
    return [(path, method) for path, method in ROUTE.findall(TEMPLATE.read_text())]


def matches(route, path):
    """API Gateway greedy proxy matching: `/r/{proxy+}` covers `/r/anything/at/all`."""
    if route.endswith("/{proxy+}"):
        return path.startswith(route[: -len("{proxy+}")])
    return route == path


def accepts_post(path):
    return any(
        method in ("POST", "ANY") and matches(route, path) for route, method in routes()
    )


def test_the_template_declares_routes_at_all():
    """A regex that silently stops matching would make every check below vacuous."""
    assert len(routes()) >= 8


def test_every_rendered_form_posts_to_a_declared_route():
    room = {"room_id": "01K3", "slug": "tonight", "title": "Tonight", "state": "open"}
    pages = [render.cohost_page(room, name="ivan")]

    actions = [action for page in pages for action in FORM.findall(page["body"])]
    assert actions, "no POST forms found — the extraction broke, not the routing"
    for action in actions:
        assert accepts_post(action), f"nothing in template.yaml accepts POST {action}"


def test_room_pages_accept_post():
    """The co-host gate lives under /r/, so that route cannot be GET-only."""
    assert accepts_post("/r/tonight/cohost/ivan")
