"""Admin Lambda: the console, presentation mode, and the Cognito login flow.

Separated from the public function so that the OIDC client and the token
exchange live behind an authenticated path only, and so a burst of participant
traffic cannot throttle the host's own access mid-event.
"""

import logging

from dataqna import config, http, oidc, render, rooms, security, store
from dataqna.http import HttpError

logging.getLogger().setLevel(logging.INFO)


def _signed_in(event):
    return security.session_email(http.cookie(event, config.SESSION_COOKIE))


def _login(event):
    if not oidc.configured():
        return render.notice("Login unavailable", "Authentication is not configured for this deployment.", status=503)
    next_path = http.query(event).get("next", "/admin")
    url, token = oidc.begin(next_path)
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
        cookies=[http.clear_cookie(config.SESSION_COOKIE)],
    )


def _present(event, room_id, email):
    room = rooms.load(room_id)
    if not room:
        return render.notice("Room not found", "This room no longer exists.", status=404)
    if not store.is_admin(room["room_id"], email):
        return render.notice("Not allowed", "Presentation mode is for room admins.", status=403)
    return render.present_page(
        room,
        {
            "room_id": room["room_id"],
            "slug": room.get("slug"),
            "code": room.get("code"),
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
                "That account cannot sign in here. Use a DataTalks.Club Google account, "
                "or the credentials you were issued.",
                status=403,
                link=("Try again", "/auth/login"),
            )

        email = _signed_in(event)
        if not email:
            import urllib.parse

            return http.redirect(f"/auth/login?next={urllib.parse.quote(path)}")

        if path.startswith("/admin/rooms/") and path.endswith("/present"):
            room_id = path[len("/admin/rooms/"):-len("/present")]
            return _present(event, room_id, email)

        if path == "/admin" or path.startswith("/admin/"):
            return http.html_response(200, render.page("admin.html", {}))

        return render.notice("Not found", "Nothing lives at this address.", status=404)

    except HttpError as exc:
        return render.notice("Something went wrong", exc.message, status=exc.status)
    except Exception:
        logging.exception("unhandled admin error path=%s", path)
        return render.notice("Something went wrong", "Please try again.", status=500)
