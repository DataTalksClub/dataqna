"""Co-host codes: moderation for one room, no account, no wider reach."""

import json

import pytest

from dataqna import api, rooms, security, store
from dataqna.http import HttpError
from tests.test_api import call, event, owner, OWNER

GUEST = "guest@example.com"


def make_room(**overrides):
    payload = {"title": "Podcast", "state": "open"}
    payload.update(overrides)
    return rooms.create(payload, OWNER)


def invite_for(room, **overrides):
    response = call(["rooms", room["room_id"], "cohosts"], "POST", identity=owner(),
                    body=overrides or {})
    return json.loads(response["body"])


def cohost_identity(room, invite):
    return api.Identity(source="cohost",
                        cohost={"room_id": room["room_id"], "invite_id": invite["invite_id"]})


def test_admin_creates_a_readable_code(table):
    room = make_room()
    invite = invite_for(room, label="Guest host")
    assert invite["label"] == "Guest host"
    assert invite["code"].count("-") == 2
    assert invite["join_url"].endswith(invite["code"])
    # Codes must survive being read aloud: no ambiguous glyphs.
    assert not set(invite["code"]) & set("OIL01U")


def test_code_resolves_case_and_dash_insensitively(table):
    room = make_room()
    invite = invite_for(room)
    scrambled = invite["code"].replace("-", "").lower()
    assert store.resolve_cohost_code(scrambled)["invite_id"] == invite["invite_id"]
    assert store.resolve_cohost_code(f"  {invite['code']}  ")["invite_id"] == invite["invite_id"]


def test_unknown_code_resolves_to_nothing(table):
    make_room()
    assert store.resolve_cohost_code("ZZZZ-ZZZZ-ZZZZ") is None
    assert store.resolve_cohost_code("") is None


def test_cohost_can_moderate_its_room(table):
    room = make_room()
    invite = invite_for(room)
    identity = cohost_identity(room, invite)

    created = call(["rooms", room["room_id"], "questions"], "POST", body={"text": "Q"})
    question_id = json.loads(created["body"])["question_id"]

    answered = call(["rooms", room["room_id"], "questions", question_id], "PATCH",
                    identity=identity, body={"status": "answered"})
    assert json.loads(answered["body"])["status"] == "answered"


def test_cohost_cannot_reach_another_room(table):
    mine = make_room(slug="mine")
    other = make_room(slug="other")
    identity = cohost_identity(mine, invite_for(mine))

    created = call(["rooms", other["room_id"], "questions"], "POST", body={"text": "Q"})
    question_id = json.loads(created["body"])["question_id"]

    with pytest.raises(HttpError) as excinfo:
        call(["rooms", other["room_id"], "questions", question_id], "PATCH",
             identity=identity, body={"status": "answered"})
    assert excinfo.value.status == 403


def test_cohost_runs_the_session_including_its_settings(table):
    """A code is admin *of one session*: its questions, settings, and lifecycle."""
    room = make_room()
    identity = cohost_identity(room, invite_for(room))

    updated = json.loads(
        call(["rooms", room["room_id"]], "PATCH", identity=identity,
             body={"settings": {"questions_open": False}})["body"]
    )
    assert updated["settings"]["questions_open"] is False

    closed = json.loads(
        call(["rooms", room["room_id"]], "PATCH", identity=identity,
             body={"state": "closed"})["body"]
    )
    assert closed["state"] == "closed"


def test_cohost_cannot_change_the_published_link(table):
    """The slug is what the owner printed on a slide; a code must not move it."""
    room = make_room()
    identity = cohost_identity(room, invite_for(room))
    with pytest.raises(HttpError) as excinfo:
        call(["rooms", room["room_id"]], "PATCH", identity=identity, body={"slug": "hijacked"})
    assert excinfo.value.status == 403
    assert excinfo.value.code == "cohost_scope"
    assert rooms.load("hijacked") is None


def test_cohost_cannot_change_another_rooms_settings(table):
    mine = make_room(slug="mine")
    other = make_room(slug="other")
    identity = cohost_identity(mine, invite_for(mine))
    with pytest.raises(HttpError) as excinfo:
        call(["rooms", other["room_id"]], "PATCH", identity=identity, body={"state": "closed"})
    assert excinfo.value.status == 403


def test_cohost_cannot_grant_admin_or_mint_codes(table):
    room = make_room()
    identity = cohost_identity(room, invite_for(room))

    with pytest.raises(HttpError):
        call(["rooms", room["room_id"], "admins", GUEST], "PUT", identity=identity)
    with pytest.raises(HttpError):
        call(["rooms", room["room_id"], "cohosts"], "POST", identity=identity, body={})
    with pytest.raises(HttpError):
        call(["rooms", room["room_id"], "cohosts"], "GET", identity=identity)


def test_cohost_cannot_delete_the_room(table):
    room = make_room()
    identity = cohost_identity(room, invite_for(room))
    with pytest.raises(HttpError):
        call(["rooms", room["room_id"]], "DELETE", identity=identity)


def test_cohost_cannot_list_or_create_rooms(table):
    room = make_room()
    identity = cohost_identity(room, invite_for(room))
    with pytest.raises(HttpError) as excinfo:
        call(["rooms"], "GET", identity=identity)
    assert excinfo.value.status == 401
    with pytest.raises(HttpError):
        call(["rooms"], "POST", identity=identity, body={"title": "Mine now"})


def test_cohost_cannot_mint_api_keys(table):
    room = make_room()
    identity = cohost_identity(room, invite_for(room))
    with pytest.raises(HttpError):
        call(["api-keys"], "POST", identity=identity, body={"name": "escalation"})


def test_revoking_a_code_takes_effect_immediately(table):
    room = make_room()
    invite = invite_for(room)
    identity = cohost_identity(room, invite)
    assert identity.moderates(room)

    call(["rooms", room["room_id"], "cohosts", invite["invite_id"]], "DELETE", identity=owner())
    assert not identity.moderates(room)
    assert store.resolve_cohost_code(invite["code"]) is None


def test_expired_code_does_not_moderate(table):
    room = make_room()
    invite = invite_for(room, expires_at=store.now() - 1)
    assert not cohost_identity(room, invite).moderates(room)


def test_cohost_sees_the_room_but_not_the_admin_list(table):
    room = make_room()
    identity = cohost_identity(room, invite_for(room))
    view = json.loads(call(["rooms", room["room_id"]], "GET", identity=identity)["body"])
    assert view["role"] == "cohost"
    assert "admins" not in view


def test_owner_view_reports_its_own_role(table):
    room = make_room()
    view = json.loads(call(["rooms", room["room_id"]], "GET", identity=owner())["body"])
    assert view["role"] == "owner"


def test_cohost_token_is_bound_to_one_room(table):
    room = make_room()
    other = make_room(slug="elsewhere")
    invite = invite_for(room)
    token = security.new_cohost_token(room["room_id"], invite["invite_id"], 600)
    claim = security.cohost_claim(token)
    assert claim["room_id"] == room["room_id"]

    identity = api.Identity(source="cohost", cohost=claim)
    assert identity.moderates(room)
    assert not identity.moderates(other)


def test_a_forged_cohost_cookie_is_rejected(table):
    room = make_room()
    invite = invite_for(room)
    forged = security.sign({"kind": "cohost", "room": room["room_id"],
                            "invite": invite["invite_id"], "exp": 1})
    assert security.cohost_claim(forged) is None
    assert security.cohost_claim(forged[:-4] + "aaaa") is None


def test_a_session_token_cannot_be_used_as_a_cohost_token(table):
    room = make_room()
    assert security.cohost_claim(security.new_session_token(OWNER)) is None
