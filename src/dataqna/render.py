"""Static assets and server-rendered pages.

Assets ship inside the deployment package and are read once per container.
There is no build step and no bundler: the pages are small enough that the
cost of a toolchain would exceed its benefit.
"""

import hashlib
import html
import os
import re

from . import config, http

WEB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")

CONTENT_TYPES = {
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".svg": "image/svg+xml",
}

# A speech bubble with the upvote chevron inside it — the whole product in one
# glyph. Inline so it costs no request and cannot be blocked by the CSP.
FAVICON = (
    "data:image/svg+xml,"
    "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E"
    "%3Crect width='32' height='32' rx='8' fill='%23635bff'/%3E"
    "%3Cpath d='M9 20.5h10l4 4v-4h0a2 2 0 0 0 2-2v-9a2 2 0 0 0-2-2H9a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2z'"
    " fill='none' stroke='white' stroke-width='0'/%3E"
    "%3Cpath d='M10.5 18.5l5.5-6 5.5 6' fill='none' stroke='white' stroke-width='2.6'"
    " stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E"
)

THEME_META = (
    '<meta name="theme-color" content="#f6f8fb" media="(prefers-color-scheme: light)">'
    '<meta name="theme-color" content="#0d1220" media="(prefers-color-scheme: dark)">'
)

# Applies a theme the visitor pinned elsewhere (the room or admin toggle)
# before first paint, so server-rendered pages match without a flash.
THEME_SCRIPT = (
    "<script>(function(){try{"
    'var t=localStorage.getItem("dq_theme");'
    'if(t!=="light"&&t!=="dark")return;'
    'document.documentElement.classList.add("theme-"+t);'
    'var c=t==="dark"?"#0d1220":"#f6f8fb";'
    "var m=document.querySelectorAll('meta[name=\"theme-color\"]');"
    'for(var i=0;i<m.length;i++)m[i].setAttribute("content",c);'
    "}catch(e){}})();</script>"
)

BRAND = (
    '<a class="brand" href="/live">'
    '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor"'
    ' stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    '<path d="M6 14l6-7 6 7"/></svg>DataQnA</a>'
)

_cache = {}
_version = None
_ASSET_REF = re.compile(r'(href|src)="(/assets/[a-zA-Z0-9_.-]+)"')


def asset_bytes(name):
    if name not in _cache:
        path = os.path.normpath(os.path.join(WEB_DIR, name))
        if not path.startswith(WEB_DIR) or not os.path.isfile(path):
            return None
        with open(path, "rb") as handle:
            _cache[name] = handle.read()
    return _cache[name]


def version():
    """A build stamp, so a mid-session participant is not left on stale JS.

    Computed from the asset bytes at cold start; the files cannot change under
    a running container, so this is stable for the container's life.
    """
    global _version
    if _version is None:
        digest = hashlib.sha256()
        for name in sorted(("app.css", "room.js", "admin.js", "present.js", "qna.js")):
            digest.update(asset_bytes(name) or b"")
        _version = digest.hexdigest()[:10]
    return _version


def _stamp(markup):
    return _ASSET_REF.sub(lambda m: f'{m.group(1)}="{m.group(2)}?v={version()}"', markup)


def asset_response(name):
    payload = asset_bytes(name)
    if payload is None:
        return http.response(404, "Not found")
    extension = os.path.splitext(name)[1]
    # Versioned by the query string above, so a long life is safe.
    cache = "public, max-age=86400, immutable"
    return http.response(
        200,
        payload.decode("utf-8"),
        content_type=CONTENT_TYPES.get(extension, "application/octet-stream"),
        headers={"cache-control": cache},
    )


def page(template, replacements):
    body = asset_bytes(template).decode("utf-8")
    values = dict(replacements)
    values.setdefault("FAVICON", FAVICON)
    for key, value in values.items():
        body = body.replace("{{" + key + "}}", value)
    return _stamp(body)


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


def _shell(title, inner, *, status=200):
    body = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="robots" content="noindex">
<title>{html.escape(title)}</title>
{THEME_META}
{THEME_SCRIPT}
<link rel="icon" href="{FAVICON}">
<link rel="stylesheet" href="/assets/app.css"></head>
<body><div class="wrap">{inner}</div></body></html>"""
    return http.html_response(status, _stamp(body))


def cohost_page(room, error=None, name=""):
    """The passcode gate.

    The link names an invite within one session; it does not open it. This page
    is what turns a forwarded link into nothing much.
    """
    message = f'<div class="banner warn">{html.escape(error)}</div>' if error else ""
    action = f"/r/{html.escape(room.get('slug') or '')}/cohost/{html.escape(name)}"
    inner = f"""{BRAND}
<h1 style="font-size:1.5rem;letter-spacing:-.01em">Co-host access</h1>
<p class="muted">Enter the passcode the host gave you. It lets you run
{html.escape(room.get("title") or "this session")} — its questions, settings,
and presentation mode. No account needed.</p>
<form method="POST" action="{action}" class="card stack">
  {message}
  <input type="text" name="passcode" autocomplete="off" autocapitalize="characters"
         autofocus spellcheck="false" maxlength="40" placeholder="XXXX-XXXX-XXXX"
         aria-label="Passcode" class="mono">
  <button type="submit">Continue</button>
</form>"""
    return _shell("Co-host access", inner, status=200 if not error else 403)


def _room_card(room, *, note):
    title = html.escape(room.get("title") or "Q&A")
    slug = html.escape(room.get("slug") or "")
    return (
        f'<div class="card room-card">'
        f'<a class="stretched room-link" href="/r/{slug}">{title}</a>'
        f'<div class="muted room-note">{html.escape(note)}</div>'
        f"</div>"
    )


def _counts_note(room):
    total = int(room.get("q_total") or 0)
    return f"{total} question{'' if total == 1 else 's'}"


def directory_page(live, recent, *, signed_in=None):
    """The front page: what is on now, and what was on recently."""
    parts = [
        '<div class="row" style="margin-bottom:22px">',
        f'<span class="grow">{BRAND}</span>',
    ]
    if signed_in:
        parts.append('<a class="btn small" href="/admin">Your sessions</a>')
    else:
        parts.append('<a class="btn ghost small" href="/auth/login">Sign in</a>')
    parts.append("</div>")

    if signed_in:
        parts.append(
            '<div class="card stack">'
            f'<strong>Signed in as {html.escape(signed_in)}</strong>'
            '<p class="muted" style="margin:0">Create a session, share its QR code, '
            'and run presentation mode from the console.</p>'
            '<div class="row wrapping">'
            '<a class="btn" href="/admin">New session</a>'
            '<a class="btn ghost" href="/auth/logout">Sign out</a>'
            "</div></div>"
        )

    if live:
        parts.append('<div class="group-heading">Live now</div>')
        parts.extend(
            _room_card(room, note=f"{_counts_note(room)} · open") for room in live
        )

    if recent:
        parts.append('<div class="group-heading">Recently finished</div>')
        parts.extend(
            _room_card(room, note=f"{_counts_note(room)} · closed") for room in recent
        )

    if not live and not recent:
        parts.append(
            '<div class="empty">'
            '<h2>Nothing running right now</h2>'
            "<p>Sessions appear here while they are live, and for a week after "
            "they finish.</p></div>"
        )

    return _shell("Q&A sessions", "".join(parts))


def notice(title, message, *, status=200, link=None):
    target, label = (link[1], link[0]) if link else ("/live", "See what's live")
    inner = f"""{BRAND}
<div class="empty">
<h2 style="font-size:1.3rem">{html.escape(title)}</h2>
<p>{html.escape(message)}</p>
<p style="margin-top:18px"><a class="btn" href="{html.escape(target)}">{html.escape(label)}</a></p>
</div>"""
    return _shell(title, inner, status=status)
