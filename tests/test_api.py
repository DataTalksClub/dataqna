"""Route-level tests, focused on who is allowed to do what."""

import json

import pytest

from dataqna import api, rooms, security, store
from dataqna.http import HttpError

OWNER = "alexey@datatalks.club"
GUEST = "realmistic@gmail.com"
STRANGER = "someone@example.com"


def event(method="GET", body=None, cookies=None, headers=None, query=None):
    return {
        "rawPath": "/api/v1",
        "requestContext": {"http": {"method": method, "sourceIp": "203.0.113.7"}},
        "headers": headers or {},
        "cookies": cookies or [],
        "queryStringParameters": query or {},
        "body": json.dumps(body) if body is not None else None,
    }


def call(segments, method="GET", identity=None, **kwargs):
    return api.route(event(method, **kwargs), segments, method, identity or api.Identity())


def owner():
    return api.Identity(email=OWNER, source="session")


def make_room(**overrides):
    payload = {"title": "Podcast", "state": "open"}
    payload.update(overrides)
    return rooms.create(payload, OWNER)


def test_anonymous_cannot_create_a_room(table):
    with pytest.raises(HttpError) as excinfo:
        call(["rooms"], "POST", body={"title": "Nope"})
    assert excinfo.value.status == 401


def test_owner_creates_and_lists_rooms(table):
    response = call(["rooms"], "POST", identity=owner(), body={"title": "Podcast", "state": "open"})
    assert response["statusCode"] == 201
    created = json.loads(response["body"])
    assert created["url"].endswith("/r/podcast")

    listed = json.loads(call(["rooms"], "GET", identity=owner())["body"])
    assert [room["room_id"] for room in listed["items"]] == [created["room_id"]]


def test_a_stranger_cannot_change_a_room(table):
    room = make_room()
    stranger = api.Identity(email=STRANGER, source="session")
    with pytest.raises(HttpError) as excinfo:
        call(["rooms", room["room_id"]], "PATCH", identity=stranger, body={"title": "Hijacked"})
    assert excinfo.value.status == 403


def test_there_is_no_way_to_grant_another_account_access(table):
    """Access is owner plus session codes. Nothing else, deliberately."""
    room = make_room()
    for method in ("PUT", "DELETE", "GET"):
        with pytest.raises(HttpError) as excinfo:
            call(["rooms", room["room_id"], "admins", GUEST], method, identity=owner())
        assert excinfo.value.status == 404


def test_creating_a_room_ignores_any_admins_field(table):
    response = call(["rooms"], "POST", identity=owner(),
                    body={"title": "Podcast", "admins": [GUEST]})
    room_id = json.loads(response["body"])["room_id"]
    assert not store.is_admin(room_id, GUEST)


def test_a_signed_in_stranger_sees_only_their_own_sessions(table):
    make_room()
    stranger = api.Identity(email=STRANGER, source="session")
    listed = json.loads(call(["rooms"], "GET", identity=stranger)["body"])
    assert listed["items"] == []


def test_draft_rooms_are_invisible_to_the_public(table):
    room = make_room(state="draft")
    with pytest.raises(HttpError) as excinfo:
        call(["rooms", room["room_id"], "questions"], "GET")
    assert excinfo.value.status == 404


def test_a_room_scoped_key_cannot_touch_other_rooms(table):
    mine = make_room(slug="mine")
    other = make_room(slug="other")
    scoped = api.Identity(email=OWNER, source="key", key_room_id=mine["room_id"])

    call(["rooms", mine["room_id"]], "PATCH", identity=scoped, body={"title": "ok"})
    with pytest.raises(HttpError) as excinfo:
        call(["rooms", other["room_id"]], "PATCH", identity=scoped, body={"title": "no"})
    assert excinfo.value.status == 403


def test_a_scoped_key_cannot_create_rooms(table):
    room = make_room()
    scoped = api.Identity(email=OWNER, source="key", key_room_id=room["room_id"])
    with pytest.raises(HttpError) as excinfo:
        call(["rooms"], "POST", identity=scoped, body={"title": "New"})
    assert excinfo.value.status == 403


def test_api_keys_cannot_mint_api_keys(table):
    key_identity = api.Identity(email=OWNER, source="key")
    with pytest.raises(HttpError) as excinfo:
        call(["api-keys"], "POST", identity=key_identity, body={"name": "escalation"})
    assert excinfo.value.status == 403


def test_bearer_key_is_resolved_and_scoped(table):
    key, key_hash = security.new_api_key()
    store.put_api_key(
        {
            "key_id": "k1",
            "key_hash": key_hash,
            "email": OWNER,
            "name": "script",
            "room_id": None,
            "created_at": store.now(),
            "expires_at": None,
        }
    )
    identity = api.identify(event(headers={"authorization": f"Bearer {key}"}))
    assert identity.email == OWNER
    assert identity.source == "key"


def test_revoked_key_is_rejected(table):
    key, key_hash = security.new_api_key()
    store.put_api_key(
        {"key_id": "k1", "key_hash": key_hash, "email": OWNER, "name": "x",
         "room_id": None, "created_at": store.now(), "expires_at": None}
    )
    store.delete_api_key(key_hash)
    with pytest.raises(HttpError) as excinfo:
        api.identify(event(headers={"authorization": f"Bearer {key}"}))
    assert excinfo.value.status == 401


def test_expired_key_is_rejected(table):
    key, key_hash = security.new_api_key()
    store.put_api_key(
        {"key_id": "k1", "key_hash": key_hash, "email": OWNER, "name": "x",
         "room_id": None, "created_at": store.now() - 10, "expires_at": store.now() - 1}
    )
    with pytest.raises(HttpError) as excinfo:
        api.identify(event(headers={"authorization": f"Bearer {key}"}))
    assert excinfo.value.status == 401


def test_participants_post_and_vote_without_credentials(table):
    room = make_room()
    created = call(["rooms", room["room_id"], "questions"], "POST", body={"text": "Why serverless?"})
    assert created["statusCode"] == 201
    question_id = json.loads(created["body"])["question_id"]

    listed = json.loads(call(["rooms", room["room_id"], "questions"], "GET")["body"])
    assert [item["text"] for item in listed["items"]] == ["Why serverless?"]

    voted = call(["rooms", room["room_id"], "questions", question_id, "vote"], "POST")
    assert json.loads(voted["body"])["voted"] is True


def test_a_participant_cannot_moderate(table):
    room = make_room()
    created = call(["rooms", room["room_id"], "questions"], "POST", body={"text": "Q"})
    question_id = json.loads(created["body"])["question_id"]
    with pytest.raises(HttpError) as excinfo:
        call(["rooms", room["room_id"], "questions", question_id], "PATCH", body={"status": "answered"})
    assert excinfo.value.status == 403


def _ask(room, text, participant):
    cookies = [f"dq_p={security.new_participant_token()}"] if participant else None
    created = call(
        ["rooms", room["room_id"], "questions"], "POST", body={"text": text}, cookies=cookies
    )
    return json.loads(created["body"])["question_id"]


def test_pinning_a_question_unpins_the_rooms_other_one(table):
    """The route enforces the one pin a room holds, so every client — this
    UI, a script, a future one — inherits it without knowing about it."""
    room = make_room()
    first = _ask(room, "first question", "a")
    second = _ask(room, "second question", "b")
    call(["rooms", room["room_id"], "questions", first], "PATCH", identity=owner(), body={"pinned": True})
    call(["rooms", room["room_id"], "questions", second], "PATCH", identity=owner(), body={"pinned": True})

    listed = json.loads(call(["rooms", room["room_id"], "questions"], "GET")["body"])
    assert [item["text"] for item in listed["items"]] == ["second question", "first question"]
    assert [item["pinned"] for item in listed["items"]] == [True, False]


def test_marking_a_pinned_question_answered_unpins_it(table):
    room = make_room()
    question_id = _ask(room, "the pinned one", "a")
    call(["rooms", room["room_id"], "questions", question_id], "PATCH", identity=owner(), body={"pinned": True})
    call(["rooms", room["room_id"], "questions", question_id], "PATCH", identity=owner(), body={"status": "answered"})

    stored = store.get_question(room["room_id"], question_id)
    assert not stored["pinned"]


def test_idempotent_creation_returns_the_same_room(table):
    first = call(["rooms"], "POST", identity=owner(),
                 body={"title": "Podcast #142", "idempotency_key": "podcast-142"})
    second = call(["rooms"], "POST", identity=owner(),
                  body={"title": "Podcast #142", "idempotency_key": "podcast-142"})
    assert second["statusCode"] == 200
    assert json.loads(first["body"])["room_id"] == json.loads(second["body"])["room_id"]


def test_root_admin_can_reach_any_room(table):
    room = make_room()
    root = api.Identity(email="root@datatalks.club", source="session")
    assert call(["rooms", room["room_id"]], "PATCH", identity=root, body={"title": "ok"})


def test_an_archived_session_reads_for_its_hosts_and_reopens(table):
    """Archive is reversible for the people who filed it and terminal for
    everyone else: the hosts get the console and the reopen, the audience
    keeps its 410."""
    room = make_room()
    call(["rooms", room["room_id"]], "PATCH", identity=owner(), body={"state": "archived"})

    with pytest.raises(HttpError) as excinfo:
        call(["rooms", room["room_id"]])
    assert excinfo.value.status == 410
    with pytest.raises(HttpError) as excinfo:
        call(["rooms", room["room_id"], "questions"])
    assert excinfo.value.status == 410

    listed = call(["rooms", room["room_id"]], "GET", identity=owner())
    assert json.loads(listed["body"])["state"] == "archived"
    assert call(["rooms", room["room_id"], "questions"], "GET", identity=owner())

    with pytest.raises(HttpError) as excinfo:
        call(["rooms", room["room_id"]], "PATCH", identity=owner(), body={"title": "Sneaked"})
    assert excinfo.value.status == 409

    reopened = call(["rooms", room["room_id"]], "PATCH", identity=owner(), body={"state": "open"})
    assert json.loads(reopened["body"])["state"] == "open"
