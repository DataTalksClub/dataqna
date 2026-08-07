"""The front page: what is on now, and what was on recently."""

import json

import public_handler
from dataqna import config, render, rooms, security, store
from tests.test_api import event, OWNER


def home(cookies=None):
    request = event("GET", cookies=cookies or [])
    request["rawPath"] = "/"
    return public_handler.lambda_handler(request, None)


def make_room(**overrides):
    payload = {"title": "Podcast", "state": "open"}
    payload.update(overrides)
    return rooms.create(payload, OWNER)


def test_the_front_page_lists_live_sessions_instead_of_jumping_to_one(table):
    make_room(title="Tonight recording", slug="tonight")
    response = home()
    assert response["statusCode"] == 200
    assert "Tonight recording" in response["body"]
    assert "Live now" in response["body"]


def test_a_single_open_session_no_longer_hijacks_the_front_page(table):
    make_room(slug="only-one")
    assert home()["statusCode"] == 200


def test_live_still_jumps_straight_to_the_open_session(table):
    """The permanent link for podcast notes keeps its redirect behaviour."""
    make_room(slug="only-one")
    request = event("GET")
    request["rawPath"] = "/live"
    response = public_handler.lambda_handler(request, None)
    assert response["statusCode"] == 302
    assert response["headers"]["location"].endswith("/r/only-one")


def test_recently_closed_sessions_appear_for_a_week(table):
    room = make_room(title="Last week session", slug="past")
    rooms.transition(room, "closed")
    assert "Last week session" in home()["body"]


def test_older_closed_sessions_drop_off(table):
    room = make_room(title="Ancient history", slug="ancient")
    closed = rooms.transition(room, "closed")
    store.update_room(
        closed["room_id"],
        {"GSI1SK": store.sort_key(store.now() - 30 * 86400)},
    )
    assert "Ancient history" not in home()["body"]


def test_draft_sessions_are_never_listed(table):
    make_room(title="Not ready", slug="draft-one", state="draft")
    assert "Not ready" not in home()["body"]


def test_unlisted_sessions_stay_off_the_front_page(table):
    make_room(title="Private one", slug="private", settings={"listed": False})
    body = home()["body"]
    assert "Private one" not in body
    # Unlisted means unadvertised, not unreachable.
    assert rooms.load("private")["state"] == "open"


def test_the_empty_front_page_explains_itself(table):
    body = home()["body"]
    assert "Nothing running right now" in body


def test_signed_out_visitors_are_offered_sign_in(table):
    body = home()["body"]
    assert "/auth/login" in body
    assert "New session" not in body


def test_signed_in_admins_get_a_way_to_create_one(table):
    cookie = f"{config.SESSION_COOKIE}={security.new_session_token(OWNER)}"
    body = home(cookies=[cookie])["body"]
    assert "New session" in body
    assert OWNER in body
    assert "/auth/login" not in body


def test_the_directory_is_still_shown_to_signed_in_admins(table):
    make_room(title="Tonight recording", slug="tonight")
    cookie = f"{config.SESSION_COOKIE}={security.new_session_token(OWNER)}"
    assert "Tonight recording" in home(cookies=[cookie])["body"]


def test_listed_defaults_to_true_and_is_validated(table):
    room = make_room(slug="defaults")
    assert room["settings"]["listed"] is True
    import pytest

    from dataqna.http import HttpError

    with pytest.raises(HttpError):
        rooms.apply_updates(room, {"settings": {"listed": "yes"}})


def room_page(slug, cookies=None):
    request = event("GET", cookies=cookies or [])
    request["rawPath"] = f"/r/{slug}"
    return public_handler.lambda_handler(request, None)


def test_a_host_on_the_audience_page_gets_both_ways_back(table):
    """Handed the link they gave the room, a host can still reach their own
    screens: the console when a question needs attention, presentation mode
    when the projector goes up.

    Otherwise the only route is finding the session again through /admin, which
    is a search the audience watches them do.
    """
    room = make_room(slug="tonight")
    cookie = f"{config.SESSION_COOKIE}={security.new_session_token(OWNER)}"
    config_blob = json.loads(
        room_page("tonight", cookies=[cookie])["body"].split('type="application/json">')[1].split("</script>")[0]
    )
    assert config_blob["host_links"] == {
        "console": f"/admin/rooms/{room['room_id']}",
        "present": f"/admin/rooms/{room['room_id']}/present",
    }


def test_the_audience_is_not_told_where_the_host_screens_are(table):
    make_room(slug="tonight")
    body = room_page("tonight")["body"]
    assert "/present" not in body
    assert "/admin/rooms" not in body
