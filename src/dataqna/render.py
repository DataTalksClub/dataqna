"""Static assets and server-rendered pages.

Assets ship inside the deployment package and are read once per container.
There is no build step and no bundler: the pages are small enough that the
cost of a toolchain would exceed its benefit.
"""

import html
import os

from . import config, http

WEB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")

CONTENT_TYPES = {
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".svg": "image/svg+xml",
}

_cache = {}


def asset_bytes(name):
    if name not in _cache:
        path = os.path.normpath(os.path.join(WEB_DIR, name))
        if not path.startswith(WEB_DIR) or not os.path.isfile(path):
            return None
        with open(path, "rb") as handle:
            _cache[name] = handle.read()
    return _cache[name]


def asset_response(name, *, immutable=False):
    payload = asset_bytes(name)
    if payload is None:
        return http.response(404, "Not found")
    extension = os.path.splitext(name)[1]
    return http.response(
        200,
        payload.decode("utf-8"),
        content_type=CONTENT_TYPES.get(extension, "application/octet-stream"),
        headers={"cache-control": "public, max-age=300" if not immutable else "public, max-age=86400"},
    )


def page(template, replacements):
    body = asset_bytes(template).decode("utf-8")
    for key, value in replacements.items():
        body = body.replace("{{" + key + "}}", value)
    return body


def room_page(room, *, config_payload, cookies=None):
    body = page(
        "room.html",
        {
            "TITLE": html.escape(room.get("title") or "Q&A"),
            "DESCRIPTION": html.escape(room.get("description") or ""),
            "CONFIG": http.dumps(config_payload),
        },
    )
    return http.html_response(200, body, cookies=cookies)


def present_page(room, config_payload):
    body = page(
        "present.html",
        {
            "TITLE": html.escape(room.get("title") or "Q&A"),
            "CONFIG": http.dumps(config_payload),
        },
    )
    return http.html_response(200, body)


def cohost_page(error=None, code=""):
    message = f'<div class="banner warn">{html.escape(error)}</div>' if error else ""
    body = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Co-host access</title>
<link rel="stylesheet" href="/assets/app.css"></head>
<body><div class="wrap">
<h1 style="font-size:1.4rem">Co-host access</h1>
<p class="muted">Enter the code the host gave you. It lets you moderate that one
room — approve, answer, pin, and hide questions, and run presentation mode. No
account needed.</p>
{message}
<form method="POST" action="/cohost" class="card stack">
  <input type="text" name="code" autocomplete="off" autocapitalize="characters"
         spellcheck="false" placeholder="XXXX-XXXX-XXXX" aria-label="Co-host code"
         class="mono" value="{html.escape(code)}">
  <button type="submit">Continue</button>
</form>
</div></body></html>"""
    return http.html_response(200 if not error else 403, body)


def notice(title, message, *, status=200, link=None):
    action = f'<p><a class="btn" href="{html.escape(link[1])}">{html.escape(link[0])}</a></p>' if link else ""
    body = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>{html.escape(title)}</title>
<link rel="stylesheet" href="/assets/app.css"></head>
<body><div class="wrap"><div class="empty">
<h1 style="font-size:1.4rem">{html.escape(title)}</h1>
<p>{html.escape(message)}</p>{action}
</div></div></body></html>"""
    return http.html_response(status, body)
