import pytest

from dataqna import questions, rooms, store
from dataqna.http import HttpError

OWNER = "alexey@datatalks.club"


def make_room(table, **overrides):
    payload = {"title": "Podcast #142", "state": "open"}
    payload.update(overrides)
    return rooms.create(payload, OWNER)


def test_create_allocates_slug_and_owner_grant(table):
    """The slug is the room's whole identity — there is no separate join code."""
    room = make_room(table)
    assert room["slug"] == "podcast-142"
    assert "code" not in room
    assert store.is_admin(room["room_id"], OWNER)
    assert rooms.load("podcast-142")["room_id"] == room["room_id"]
    assert rooms.load(room["room_id"])["room_id"] == room["room_id"]


def test_duplicate_explicit_slug_is_rejected(table):
    make_room(table, slug="taken-slug")
    with pytest.raises(HttpError) as excinfo:
        make_room(table, slug="taken-slug")
    assert excinfo.value.status == 409


def test_generated_slug_falls_back_when_taken(table):
    first = make_room(table)
    second = make_room(table)
    assert first["slug"] != second["slug"]


def test_reserved_slugs_are_refused(table):
    with pytest.raises(HttpError):
        make_room(table, slug="admin")


def test_renaming_keeps_the_old_link_working(table):
    room = make_room(table)
    rooms.apply_updates(room, {"slug": "podcast-142-live"})
    assert rooms.load("podcast-142")["room_id"] == room["room_id"]
    assert rooms.load("podcast-142-live")["room_id"] == room["room_id"]


def test_expiry_closes_the_room_on_next_read(table):
    room = make_room(table, expires_at=store.now() - 1)
    assert rooms.load(room["room_id"])["state"] == "closed"


def test_expiry_in_the_future_leaves_the_room_open(table):
    room = make_room(table, expires_at=store.now() + 3600)
    assert rooms.load(room["room_id"])["state"] == "open"


def test_invalid_transition_is_rejected(table):
    room = make_room(table)
    with pytest.raises(HttpError):
        rooms.transition(room, "draft")


def test_an_archived_room_can_be_reopened(table):
    """An archive is a filing, not a shredding: the accident it exists to
    undo is sometimes the archive itself."""
    room = make_room(table)
    rooms.transition(room, "closed")
    rooms.transition(rooms.load(room["room_id"]), "archived")
    reopened = rooms.transition(rooms.load(room["room_id"]), "open")
    assert reopened["state"] == "open"


def test_reopening_clears_the_retention_timer(table):
    """Retention counts from the close date, and only while the room stays
    closed: a room brought back to life must not carry the death date an
    earlier closing set."""
    room = make_room(table)
    closed = rooms.transition(room, "closed")
    assert "ttl" in closed
    reopened = rooms.transition(rooms.load(room["room_id"]), "open")
    assert "ttl" not in reopened


def test_live_lists_only_open_unexpired_rooms(table):
    open_room = make_room(table, slug="open-one")
    make_room(table, slug="draft-one", state="draft")
    expired = make_room(table, slug="expired-one", expires_at=store.now() - 1)
    rooms.load(expired["room_id"])

    live = [room["slug"] for room in rooms.live_room()]
    assert "open-one" in live
    assert "draft-one" not in live
    assert "expired-one" not in live
    assert open_room["slug"] in live


def test_settings_are_validated(table):
    room = make_room(table)
    with pytest.raises(HttpError):
        rooms.apply_updates(room, {"settings": {"answered_placement": "sometimes"}})
    with pytest.raises(HttpError):
        rooms.apply_updates(room, {"settings": {"unknown_key": True}})


def test_removed_settings_are_rejected_as_unknown(table):
    """moderation, questions_open, and voting_open left the product, and
    max_question_length was promoted from a setting to a product constant; a
    script still sending them should hear about it rather than silently
    no-op."""
    room = make_room(table)
    for key, value in (
        ("moderation", "on"),
        ("questions_open", False),
        ("voting_open", False),
        ("max_question_length", 450),
    ):
        with pytest.raises(HttpError):
            rooms.apply_updates(room, {"settings": {key: value}})


def test_index_keys_are_strings(table):
    """The GSI declares string keys; DynamoDB rejects a number, moto does not."""
    room = make_room(table)
    stored = table.get_item(Key={"PK": f"ROOM#{room['room_id']}", "SK": "META"})["Item"]
    assert isinstance(stored["GSI1PK"], str)
    assert isinstance(stored["GSI1SK"], str)

    rooms.transition(room, "closed")
    after = table.get_item(Key={"PK": f"ROOM#{room['room_id']}", "SK": "META"})["Item"]
    assert isinstance(after["GSI1SK"], str)


def test_failed_creation_does_not_strand_the_slug(table, monkeypatch):
    monkeypatch.setattr(store, "put_room", lambda room: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(RuntimeError):
        make_room(table, slug="retryable")
    monkeypatch.undo()
    assert make_room(table, slug="retryable")["slug"] == "retryable"


def test_closing_sets_a_retention_ttl(table):
    room = make_room(table, retention_days=30)
    closed = rooms.transition(room, "closed")
    assert closed["ttl"] > store.now()
