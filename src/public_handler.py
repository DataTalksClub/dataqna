"""Public Lambda: room pages, QR codes, static assets, and the REST API.

This function takes the participant traffic and is the only one reachable
without credentials, so it holds no OIDC client and never exchanges tokens.
"""

import logging

from dataqna import api, config, http, qr, questions, render, rooms, security, store
from dataqna.http import HttpError

logging.getLogger().setLevel(logging.INFO)

ASSETS = {"app.css", "room.js", "admin.js", "present.js"}


def _room_config(room, participant):
    return {
        "room_id": room["room_id"],
        "slug": room.get("slug"),
        "code": room.get("code"),
        "state": room.get("state"),
        "url": f"{config.SITE_URL}/r/{room.get('slug')}",
        "settings": rooms.public_view(room)["settings"],
        "can_ask": rooms.accepting_questions(room),
        "can_vote": rooms.accepting_votes(room),
        "banner": _banner(room),
    }


def _banner(room):
    if room.get("state") == "closed":
        return "This room is closed. You can still read the questions."
    settings = room.get("settings", {})
    if not settings.get("questions_open", True):
        return "New questions are paused. Voting is still open."
    return None


def _serve_room(event, identifier):
    room = rooms.load(identifier)
    if not room or room.get("state") == "draft":
        return render.notice("Room not found", "This link does not point at an active Q&A.", status=404)
    if room.get("state") == "archived":
        return render.notice("Room archived", "This Q&A has been archived.", status=410)

    token = http.cookie(event, config.PARTICIPANT_COOKIE)
    cookies = None
    if not security.participant_id(token):
        token = security.new_participant_token()
        cookies = [
            http.set_cookie(config.PARTICIPANT_COOKIE, token, max_age=config.PARTICIPANT_TTL_SECONDS)
        ]
    participant = security.participant_id(token)

    # Canonicalize a join code or a superseded slug onto the current slug.
    if identifier != room.get("slug"):
        return http.redirect(f"/r/{room['slug']}", cookies=cookies)

    return render.room_page(room, config_payload=_room_config(room, participant), cookies=cookies)


def _serve_qr(identifier, extension, query):
    room = rooms.load(identifier)
    if not room or room.get("state") in ("draft", "archived"):
        return http.response(404, "Not found")
    url = f"{config.SITE_URL}/r/{room['slug']}"
    if extension == "svg":
        return http.response(
            200,
            qr.svg(url),
            content_type="image/svg+xml",
            headers={"cache-control": "public, max-age=3600"},
        )
    import base64

    try:
        size = max(64, min(2048, int(query.get("size", 512))))
    except (TypeError, ValueError):
        size = 512
    payload = qr.png(url, size=size)
    return {
        "statusCode": 200,
        "headers": {"content-type": "image/png", "cache-control": "public, max-age=3600"},
        "body": base64.b64encode(payload).decode(),
        "isBase64Encoded": True,
    }


def _serve_live():
    open_rooms = rooms.live_room()
    if not open_rooms:
        return render.notice(
            "Nothing live right now",
            "There is no open Q&A at the moment. Check back when the session starts.",
            link=("Check again", "/live"),
        )
    if len(open_rooms) == 1:
        return http.redirect(f"/r/{open_rooms[0]['slug']}")

    import html as _html

    items = "".join(
        f'<div class="card room-card"><a class="stretched" href="/r/{_html.escape(room["slug"])}">'
        f'<strong>{_html.escape(room.get("title") or "Q&A")}</strong></a></div>'
        for room in open_rooms
    )
    inner = (
        f'{render.BRAND}'
        '<h1 style="font-size:1.5rem;letter-spacing:-.01em">Live right now</h1>'
        f"{items}"
    )
    return render._shell("Live Q&A", inner)


def lambda_handler(event, _context):
    path = http.path(event)
    method = http.method(event)

    try:
        if path == "/health":
            return http.json_response(200, {"status": "ok"})

        if path.startswith("/assets/"):
            name = path[len("/assets/"):]
            if name not in ASSETS:
                return http.response(404, "Not found")
            return render.asset_response(name)

        if path.startswith("/api/v1"):
            segments = [part for part in path[len("/api/v1"):].split("/") if part]
            identity = api.identify(event)
            return api.route(event, segments, method, identity)

        if path in ("/", "/live"):
            return _serve_live()

        if path.startswith("/r/"):
            rest = path[len("/r/"):].strip("/")
            if rest.endswith("/qr.svg") or rest.endswith("/qr.png"):
                identifier, _, filename = rest.rpartition("/")
                return _serve_qr(identifier, filename.split(".")[-1], http.query(event))
            if "/" in rest:
                return http.response(404, "Not found")
            return _serve_room(event, rest)

        return render.notice("Not found", "Nothing lives at this address.", status=404)

    except HttpError as exc:
        if path.startswith("/api/"):
            return http.error_response(exc)
        return render.notice("Something went wrong", exc.message, status=exc.status)
    except Exception:
        logging.exception("unhandled error path=%s method=%s", path, method)
        if path.startswith("/api/"):
            return http.json_response(
                500, {"error": {"code": "internal_error", "message": "Unexpected error."}}
            )
        return render.notice("Something went wrong", "Please try again.", status=500)
