import pytest

from dataqna import questions, rooms, store
from dataqna.http import HttpError

OWNER = "alexey@datatalks.club"


def make_room(**overrides):
    payload = {"title": "Course cohort", "state": "open"}
    payload.update(overrides)
    return rooms.create(payload, OWNER)


def test_submission_starts_at_one_with_the_authors_own_vote(table):
    room = make_room()
    question = questions.submit(room, {"text": "How do you pick topics?"}, "p1")
    assert question["score"] == 1
    assert store.votes_for_participant(room["room_id"], "p1") == {question["question_id"]}


def test_second_vote_from_the_same_participant_is_ignored(table):
    room = make_room()
    question = questions.submit(room, {"text": "Q"}, "p1")
    assert store.add_vote(room["room_id"], question["question_id"], "p2") is True
    assert store.add_vote(room["room_id"], question["question_id"], "p2") is False
    assert int(store.get_question(room["room_id"], question["question_id"])["score"]) == 2


def test_withdrawing_a_vote_decrements_once(table):
    room = make_room()
    question = questions.submit(room, {"text": "Q"}, "p1")
    store.add_vote(room["room_id"], question["question_id"], "p2")
    assert store.remove_vote(room["room_id"], question["question_id"], "p2") is True
    assert store.remove_vote(room["room_id"], question["question_id"], "p2") is False
    assert int(store.get_question(room["room_id"], question["question_id"])["score"]) == 1


def test_closed_room_refuses_questions(table):
    room = make_room()
    rooms.transition(room, "closed")
    with pytest.raises(HttpError):
        questions.submit(rooms.load(room["room_id"]), {"text": "Q"}, "p1")


def test_questions_are_capped_at_315_characters(table):
    """A product constant, not a room setting: a question has to read whole
    on a projected card, and a tighter limit asks for a better-phrased
    question rather than a wall of text the host has to edit live. Rooms
    made before the change still carry the old number in storage — dead
    weight there, not a limit."""
    room = make_room()
    settings = dict(room["settings"])
    settings["max_question_length"] = 450
    store.update_room(room["room_id"], {"settings": settings})
    stale = store.get_room(room["room_id"])

    assert questions.submit(stale, {"text": "x" * 315}, "p1")["score"] == 1
    with pytest.raises(HttpError):
        questions.submit(stale, {"text": "x" * 316}, "p2")


def test_questions_are_visible_to_everyone_the_moment_they_are_asked(table):
    room = make_room()
    question = questions.submit(room, {"text": "Q"}, "author")
    assert question["status"] == "visible"

    items, _, _ = questions.collect(room, participant="someone-else")
    assert [item["text"] for item in items] == ["Q"]


def test_popular_ranking_breaks_ties_by_age(table):
    room = make_room()
    first = questions.submit(room, {"text": "older"}, "p1")
    second = questions.submit(room, {"text": "newer"}, "p2")
    store.add_vote(room["room_id"], second["question_id"], "p3")
    store.add_vote(room["room_id"], first["question_id"], "p4")

    items, _, _ = questions.collect(room, sort="popular")
    assert [item["text"] for item in items] == ["older", "newer"]


def test_pinned_questions_lead_every_ordering(table):
    room = make_room()
    questions.submit(room, {"text": "loud"}, "p1")
    quiet = questions.submit(room, {"text": "quiet"}, "p2")
    for voter in ("a", "b", "c"):
        store.add_vote(room["room_id"], _first(room, "loud"), voter)
    store.update_question(room["room_id"], quiet["question_id"], {"pinned": True})

    for sort in ("popular", "recent"):
        items, _, _ = questions.collect(room, sort=sort)
        assert items[0]["text"] == "quiet"


def test_the_room_holds_one_pin_at_a_time(table):
    """The pin is the host holding one question up for the room; two held up
    is just the list again. Pinning the second retires the first."""
    room = make_room()
    loud = questions.submit(room, {"text": "loud"}, "p1")
    quiet = questions.submit(room, {"text": "quiet"}, "p2")
    for voter in ("a", "b", "c"):
        store.add_vote(room["room_id"], loud["question_id"], voter)
    questions.set_pinned(room, _stored(room, loud), True)
    questions.set_pinned(room, _stored(room, quiet), True)

    items, _, _ = questions.collect(room)
    assert [item["text"] for item in items] == ["quiet", "loud"]
    assert [item["pinned"] for item in items] == [True, False]


def test_marking_a_pinned_question_answered_unpins_it(table):
    """A question that leaves the board takes no pin with it, so the room's
    one pin is never spent on something nobody can see."""
    room = make_room()
    question = questions.submit(room, {"text": "Q"}, "p1")
    questions.set_pinned(room, _stored(room, question), True)

    updated = questions.set_status(room, _stored(room, question), "answered")

    assert not updated["pinned"]


def _first(room, text):
    for question in store.list_questions(room["room_id"]):
        if question["text"] == text:
            return question["question_id"]
    raise AssertionError(text)


def _stored(room, question):
    return store.get_question(room["room_id"], question["question_id"])


def test_marking_answered_updates_counters(table):
    room = make_room()
    question = questions.submit(room, {"text": "Q"}, "p1")
    questions.set_status(room, store.get_question(room["room_id"], question["question_id"]), "answered")
    refreshed = store.get_room(room["room_id"])
    assert int(refreshed["q_answered"]) == 1


def test_deleted_questions_disappear_for_participants(table):
    """Deleting is the only removal there is, so it has to be a real one —
    including for the participant who asked."""
    room = make_room()
    question = questions.submit(room, {"text": "spam"}, "p1")
    questions.set_status(room, store.get_question(room["room_id"], question["question_id"]), "deleted")
    items, _, _ = questions.collect(room, participant="p1")
    assert items == []


def test_hiding_is_not_a_status_anybody_can_reach(table):
    """It was a third way to remove a question that did not remove it. The
    console had a tab for the pile it made, which nobody ever emptied."""
    room = make_room()
    question = questions.submit(room, {"text": "spam"}, "p1")
    stored = store.get_question(room["room_id"], question["question_id"])
    with pytest.raises(HttpError):
        questions.set_status(room, stored, "hidden")
    assert "hidden" not in questions.STATUSES


def test_etag_changes_when_a_score_changes(table):
    room = make_room()
    question = questions.submit(room, {"text": "Q"}, "p1")
    _, _, before = questions.collect(room)
    store.add_vote(room["room_id"], question["question_id"], "p2")
    _, _, after = questions.collect(room)
    assert before != after


def test_author_edit_window_closes_after_a_vote(table):
    room = make_room()
    question = questions.submit(room, {"text": "Q"}, "p1")
    stored = store.get_question(room["room_id"], question["question_id"])
    assert questions.can_author_edit(stored, "p1")
    store.add_vote(room["room_id"], question["question_id"], "p2")
    assert not questions.can_author_edit(store.get_question(room["room_id"], question["question_id"]), "p1")


def test_author_cannot_edit_someone_elses_question(table):
    room = make_room()
    question = questions.submit(room, {"text": "Q"}, "p1")
    stored = store.get_question(room["room_id"], question["question_id"])
    assert not questions.can_author_edit(stored, "p2")
