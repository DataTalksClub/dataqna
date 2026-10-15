"""A stub server for the browser tests: the real pages and assets, a fake API.

Pages render through dataqna.render, the code prod serves, and every asset
comes off disk, so the browser runs the real markup, CSS and scripts. Only
the API is stubbed, with one open session and a few questions, so nothing
needs AWS. Run it as `python tests/browser/server.py <port>`.
"""

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from dataqna import qr, render  # noqa: E402

WEB = ROOT / "src" / "web"

ROOM = {
    "room_id": "R1", "slug": "podcast", "title": "Podcast #142 — live recording",
    "state": "open", "url": "https://qna.test/r/podcast", "owner": "host@datatalks.club",
    "role": "owner", "counts": {"questions": 3, "answered": 1}, "expires_at": None,
    "settings": {"listed": True},
}

QUESTIONS = [
    {"question_id": f"q{i}", "text": text, "author_name": "Guest", "created_at": "2026-10-02T12:00:00Z",
     "score": score, "voted": False, "own": False, "pinned": False, "status": status, "editable": False}
    for i, (text, score, status) in enumerate([
        ("What is the one tool you would keep?", 9, "visible"),
        ("How do you keep the archive searchable?", 4, "visible"),
        ("Already answered on air.", 12, "answered"),
    ])
]

TYPES = {".css": "text/css", ".js": "text/javascript", ".woff2": "font/woff2", ".svg": "image/svg+xml"}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, status, body, ctype="text/html; charset=utf-8"):
        payload = body if isinstance(body, bytes) else body.encode()
        self.send_response(status)
        self.send_header("content-type", ctype)
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _json(self, payload):
        self._send(200, json.dumps(payload), "application/json")

    def do_GET(self):
        path = urlparse(self.path).path
        if path.startswith("/assets/"):
            file = (WEB / path[len("/assets/"):]).resolve()
            if not file.is_relative_to(WEB) or not file.is_file():
                return self._send(404, "not found", "text/plain")
            return self._send(200, file.read_bytes(), TYPES.get(file.suffix, "application/octet-stream"))
        if path.endswith("/qr.svg"):
            return self._send(200, qr.svg(ROOM["url"]), "image/svg+xml")
        if path.startswith("/api/v1/"):
            rest = path[len("/api/v1"):]
            if rest == "/rooms":
                return self._json({"items": [ROOM]})
            if rest == "/rooms/R1":
                return self._json(ROOM)
            if rest.startswith("/rooms/R1/questions"):
                return self._json({"items": QUESTIONS, "etag": "stub", "state": "open"})
            return self._json({"items": []})
        if path == "/admin" or path.startswith("/admin/rooms/"):
            return self._send(200, render.page("admin.html", render.account_chrome(email="host@datatalks.club")))
        return self._send(404, "not found", "text/plain")


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), Handler)
    print("ready", flush=True)
    server.serve_forever()
