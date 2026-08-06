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


def test_a_granted_admin_can_moderate_but_not_delete(table):
    room = make_room()
    store.add_admin(room["room_id"], GUEST)
    guest = api.Identity(email=GUEST, source="session")

    updated = call(["rooms", room["room_id"]], "PATCH", identity=guest, body={"title": "Renamed"})
    assert json.loads(updated["body"])["title"] == "Renamed"

    with pytest.raises(HttpError) as excinfo:
        call(["rooms", room["room_id"]], "DELETE", identity=guest)
    assert excinfo.value.status == 403


def test_removing_an_admin_takes_effect_immediately(table):
    room = make_room()
    store.add_admin(room["room_id"], GUEST)
    guest = api.Identity(email=GUEST, source="session")
    call(["rooms", room["room_id"]], "PATCH", identity=guest, body={"title": "Fine"})

    store.remove_admin(room["room_id"], GUEST)
    with pytest.raises(HttpError):
        call(["rooms", room["room_id"]], "PATCH", identity=guest, body={"title": "Not fine"})


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


def test_idempotent_creation_returns_the_same_room(table):
    first = call(["rooms"], "POST", identity=owner(),
                 body={"title": "Podcast #142", "idempotency_key": "podcast-142"})
    second = call(["rooms"], "POST", identity=owner(),
                  body={"title": "Podcast #142", "idempotency_key": "podcast-142"})
    assert second["statusCode"] == 200
    assert json.loads(first["body"])["room_id"] == json.loads(second["body"])["room_id"]


def test_export_requires_admin(table):
    room = make_room()
    with pytest.raises(HttpError) as excinfo:
        call(["rooms", room["room_id"], "export"], "GET")
    assert excinfo.value.status == 401


def test_export_markdown_lists_questions(table):
    room = make_room()
    call(["rooms", room["room_id"], "questions"], "POST", body={"text": "Exported?"})
    response = call(["rooms", room["room_id"], "export"], "GET", identity=owner(),
                    query={"format": "md"})
    assert "Exported?" in response["body"]


def test_root_admin_can_reach_any_room(table):
    room = make_room()
    root = api.Identity(email="root@datatalks.club", source="session")
    assert call(["rooms", room["room_id"]], "PATCH", identity=root, body={"title": "ok"})
