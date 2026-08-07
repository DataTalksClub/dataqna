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


def test_length_limit_is_enforced(table):
    room = make_room(settings={"max_question_length": 10})
    with pytest.raises(HttpError):
        questions.submit(room, {"text": "x" * 11}, "p1")


def test_questions_are_visible_to_everyone_the_moment_they_are_asked(table):
    room = make_room()
    question = questions.submit(room, {"text": "Q"}, "author")
    assert question["status"] == "visible"

    items, _, _ = questions.collect(room, participant="someone-else")
    assert [item["text"] for item in items] == ["Q"]


def test_a_legacy_pending_row_reads_as_visible(table):
    """Moderation is gone; rows stored while it existed must not stay
    invisible forever — nobody asked for them to be hidden, and no control
    is left that could release them."""
    room = make_room()
    question = questions.submit(room, {"text": "Held over"}, "author")
    store.update_question(room["room_id"], question["question_id"], {"status": "pending"})

    items, counts, _ = questions.collect(room, participant="someone-else")
    assert [item["text"] for item in items] == ["Held over"]
    assert items[0]["status"] == "visible"
    assert counts["visible"] == 1

    stored = store.get_question(room["room_id"], question["question_id"])
    assert questions.can_author_edit(stored, "author")


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


def _first(room, text):
    for question in store.list_questions(room["room_id"]):
        if question["text"] == text:
            return question["question_id"]
    raise AssertionError(text)


def test_marking_answered_updates_counters(table):
    room = make_room()
    question = questions.submit(room, {"text": "Q"}, "p1")
    questions.set_status(room, store.get_question(room["room_id"], question["question_id"]), "answered")
    refreshed = store.get_room(room["room_id"])
    assert int(refreshed["q_answered"]) == 1


def test_hidden_questions_disappear_for_participants(table):
    room = make_room()
    question = questions.submit(room, {"text": "spam"}, "p1")
    questions.set_status(room, store.get_question(room["room_id"], question["question_id"]), "hidden")
    items, _, _ = questions.collect(room, participant="p1")
    assert items == []


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
