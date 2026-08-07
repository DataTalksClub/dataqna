"""Admin Lambda: the console, presentation mode, and the Cognito login flow.

Separated from the public function so that the OIDC client and the token
exchange live behind an authenticated path only, and so a burst of participant
traffic cannot throttle the host's own access mid-event.
"""

import logging
import urllib.parse

from dataqna import config, http, oidc, render, rooms, security, store
from dataqna.http import HttpError

logging.getLogger().setLevel(logging.INFO)


def _signed_in(event):
    return security.session_email(http.cookie(event, config.SESSION_COOKIE))


def _cohost_of(event, room_id):
    """The room this browser holds a valid, unrevoked co-host code for."""
    claim = security.cohost_claim(http.cookie(event, config.COHOST_COOKIE))
    if not claim or claim.get("room_id") != room_id:
        return False
    return bool(store.get_cohost_invite(room_id, claim.get("invite_id")))


def _login(event):
    if not oidc.configured():
        return render.notice(
            "Sign-in unavailable", "Authentication is not configured for this deployment.", status=503
        )
    url, token = oidc.begin(http.query(event).get("next", "/admin"))
    return http.redirect(
        url,
        cookies=[
            http.set_cookie(config.OIDC_COOKIE, token, max_age=config.OIDC_TTL_SECONDS, path_="/auth")
        ],
    )


def _callback(event):
    clear = http.clear_cookie(config.OIDC_COOKIE, path_="/auth")
    pending = security.verify(http.cookie(event, config.OIDC_COOKIE), kind="oidc")
    query = http.query(event)
    email, next_path = oidc.complete(pending, query.get("code", ""), query.get("state", ""))
    if not email:
        return http.redirect("/auth/error", status=303, cookies=[clear])
    return http.redirect(
        next_path or "/admin",
        cookies=[
            clear,
            http.set_cookie(
                config.SESSION_COOKIE, security.new_session_token(email), max_age=config.SESSION_TTL_SECONDS
            ),
        ],
    )


def _logout():
    return http.redirect(
        oidc.logout_url() if oidc.configured() else "/",
        cookies=[
            http.clear_cookie(config.SESSION_COOKIE),
            http.clear_cookie(config.COHOST_COOKIE),
        ],
    )


def _present(event, room_id, email):
    room = rooms.load(room_id)
    if not room:
        return render.notice("Room not found", "This room no longer exists.", status=404)
    if not (store.is_admin(room["room_id"], email) if email else _cohost_of(event, room["room_id"])):
        return render.notice(
            "Not allowed", "Presentation mode is for room admins and co-hosts.", status=403
        )
    return render.present_page(
        room,
        {
            "room_id": room["room_id"],
            "slug": room.get("slug"),
            "url": f"{config.SITE_URL}/r/{room.get('slug')}",
            "title": room.get("title"),
        },
    )


def lambda_handler(event, _context):
    path = http.path(event)

    try:
        if path == "/auth/login":
            return _login(event)
        if path == "/auth/callback":
            return _callback(event)
        if path == "/auth/logout":
            return _logout()
        if path == "/auth/error":
            return render.notice(
                "Sign-in failed",
                "Sign in with a DataTalks.Club Google account. If you were given a "
                "co-host link and passcode for one session, use those instead.",
                status=403,
                link=("Try again", "/auth/login"),
            )

        email = _signed_in(event)
        room_id = None
        if path.startswith("/admin/rooms/"):
            room_id = path[len("/admin/rooms/"):].split("/")[0]

        # A co-host has no session, but does hold a code for exactly one room.
        if not email and not (room_id and _cohost_of(event, room_id)):
            return http.redirect(f"/auth/login?next={urllib.parse.quote(path)}")

        if path.startswith("/admin/rooms/") and path.endswith("/present"):
            return _present(event, room_id, email)

        if path == "/admin" or path.startswith("/admin/"):
            return http.html_response(200, render.page("admin.html", {}))

        return render.notice("Not found", "Nothing lives at this address.", status=404)

    except HttpError as exc:
        return render.notice("Something went wrong", exc.message, status=exc.status)
    except Exception:
        logging.exception("unhandled admin error path=%s", path)
        return render.notice("Something went wrong", "Please try again.", status=500)
