"""Question submission, ranking, and serialization."""

import hashlib

from . import config, ids, rooms, store
from .http import HttpError

STATUSES = ("visible", "answered", "deleted")
PUBLIC_STATUSES = ("visible", "answered")

EDIT_WINDOW_SECONDS = 300


def _bad(message, code="invalid_request"):
    return HttpError(400, code, message)


def submit(room, payload, participant):
    if not rooms.accepting_questions(room):
        raise HttpError(409, "questions_closed", "This room is not accepting questions.")

    settings = room.get("settings", {})
    text = str(payload.get("text", "")).strip()
    limit = config.MAX_QUESTION_LENGTH
    if not text:
        raise _bad("text is required")
    if len(text) > limit:
        raise _bad(f"text must be {limit} characters or fewer")

    name = str(payload.get("author_name") or "").strip()[: config.MAX_NAME_LENGTH]
    if name and not settings.get("allow_names", True):
        raise _bad("This room does not accept names.")
    if not name and settings.get("require_names"):
        raise _bad("This room requires a name.")

    timestamp = store.now()
    question = {
        "question_id": ids.ulid(),
        "room_id": room["room_id"],
        "text": text,
        "author_name": name or None,
        "participant": participant,
        "status": "visible",
        # Starts at zero; the author's own vote below is what makes it one, so
        # that withdrawing it decrements exactly once.
        "score": 0,
        "pinned": False,
        "created_at": timestamp,
        "answered_at": None,
    }
    ttl = rooms.question_ttl(room)
    if ttl:
        question["ttl"] = ttl
    store.put_question(question)
    # The author's own vote is implicit and recorded so it can be withdrawn.
    store.add_vote(room["room_id"], question["question_id"], participant, ttl=ttl)
    question["score"] = 1
    store.bump_counter(room["room_id"], "q_total", 1)
    return question


def can_author_edit(question, participant, now=None):
    if not participant or question.get("participant") != participant:
        return False
    if question.get("status") != "visible":
        return False
    if int(question.get("score") or 0) > 1:
        return False
    return int(question.get("created_at") or 0) + EDIT_WINDOW_SECONDS > (now or store.now())


def set_status(room, question, target):
    if target not in STATUSES:
        raise _bad(f"status must be one of {list(STATUSES)}")
    current = question.get("status")
    if current == target:
        return question

    fields = {"status": target}
    if target == "answered":
        fields["answered_at"] = store.now()
    elif current == "answered":
        fields["answered_at"] = None
    if target in ("answered", "deleted"):
        # A question that leaves the board takes no pin with it, so the
        # room's one pin is never spent on something nobody can see.
        fields["pinned"] = False

    updated = store.update_question(room["room_id"], question["question_id"], fields)
    room_id = room["room_id"]
    if target == "answered" and current != "answered":
        store.bump_counter(room_id, "q_answered", 1)
    if current == "answered" and target != "answered":
        store.bump_counter(room_id, "q_answered", -1)
    if target == "deleted" and current != "deleted":
        store.bump_counter(room_id, "q_total", -1)
    if current == "deleted" and target != "deleted":
        store.bump_counter(room_id, "q_total", 1)
    return updated


def set_pinned(room, question, pinned):
    """Pin is singular: one question per room at a time. The pin is the host
    holding one question up for the room, and two held up is just the list
    again — so pinning retires every other pin before it lands."""
    room_id = room["room_id"]
    if pinned:
        for other in store.list_questions(room_id):
            if other["question_id"] != question["question_id"] and other.get("pinned"):
                store.update_question(room_id, other["question_id"], {"pinned": False})
    return store.update_question(room_id, question["question_id"], {"pinned": bool(pinned)})


def visible_to(question, participant, is_admin):
    status = question.get("status")
    if is_admin:
        return status != "deleted"
    return status in PUBLIC_STATUSES


def rank(questions, sort):
    if sort == "recent":
        key = lambda q: (not q.get("pinned"), -int(q.get("created_at") or 0))
    else:
        key = lambda q: (
            not q.get("pinned"),
            -int(q.get("score") or 0),
            int(q.get("created_at") or 0),
        )
    return sorted(questions, key=key)


def serialize(question, *, participant=None, voted=False, is_admin=False, now=None):
    view = {
        "question_id": question["question_id"],
        "text": question.get("text"),
        "author_name": question.get("author_name"),
        "status": question.get("status"),
        "score": int(question.get("score") or 0),
        "pinned": bool(question.get("pinned")),
        "created_at": rooms.iso(question.get("created_at")),
        "answered_at": rooms.iso(question.get("answered_at")),
    }
    if participant is not None:
        own = question.get("participant") == participant
        view["own"] = own
        view["voted"] = voted
        view["editable"] = can_author_edit(question, participant, now=now)
    return view


def etag(items):
    digest = hashlib.sha256()
    for item in items:
        digest.update(
            f"{item['question_id']}:{item.get('score')}:{item.get('status')}:"
            f"{item.get('pinned')}:{item.get('text')}".encode()
        )
    return f'W/"{digest.hexdigest()[:20]}"'


def collect(room, *, participant=None, is_admin=False, sort=None, statuses=None):
    """Load, filter, rank, and serialize a room's questions in one pass."""
    raw = store.list_questions(room["room_id"])
    voted = store.votes_for_participant(room["room_id"], participant) if participant else set()
    now = store.now()

    allowed = set(statuses) if statuses else None
    visible = []
    for question in raw:
        if not visible_to(question, participant, is_admin):
            continue
        if allowed and question.get("status") not in allowed:
            continue
        visible.append(question)

    sort = sort or room.get("settings", {}).get("default_sort", "popular")
    ordered = rank(visible, sort)
    items = [
        serialize(
            question,
            participant=participant,
            voted=question["question_id"] in voted,
            is_admin=is_admin,
            now=now,
        )
        for question in ordered
    ]
    counts = {
        "visible": sum(1 for q in visible if q.get("status") == "visible"),
        "answered": sum(1 for q in visible if q.get("status") == "answered"),
    }
    return items, counts, etag(ordered)
