"""Room creation, validation, and lifecycle."""

import time

from . import config, ids, store
from .http import HttpError

STATES = ("draft", "open", "closed", "archived")

TRANSITIONS = {
    "draft": {"open", "archived"},
    "open": {"closed", "archived"},
    "closed": {"open", "archived"},
    "archived": set(),
}

DEFAULT_SETTINGS = {
    # Whether the session appears on the public front page. Off makes a room
    # reachable by link only — it changes nothing about who may read it.
    "listed": True,
    "allow_names": True,
    "require_names": False,
    "answered_placement": "separate",
    "default_sort": "popular",
    # Slido caps questions at 300. Half as long again is generous without
    # letting a question become a speech the host has to read out.
    "max_question_length": 450,
}

_ENUMS = {
    "answered_placement": {"separate", "bottom", "inline"},
    "default_sort": {"popular", "recent"},
}


def _bad(message, code="invalid_request"):
    return HttpError(400, code, message)


def clean_settings(raw, base=None):
    # Rebuilt from the known keys, so settings removed from the product
    # (moderation, questions_open, voting_open) fall out of stored rooms on
    # their next write instead of lingering forever.
    base = base or {}
    settings = {key: base.get(key, value) for key, value in DEFAULT_SETTINGS.items()}
    for key, value in (raw or {}).items():
        if key not in DEFAULT_SETTINGS:
            raise _bad(f"Unknown setting: {key}")
        if key in _ENUMS:
            if value not in _ENUMS[key]:
                raise _bad(f"{key} must be one of {sorted(_ENUMS[key])}")
        elif key == "max_question_length":
            value = int(value)
            if not 1 <= value <= config.MAX_QUESTION_LENGTH_LIMIT:
                raise _bad(f"max_question_length must be between 1 and {config.MAX_QUESTION_LENGTH_LIMIT}")
        else:
            if not isinstance(value, bool):
                raise _bad(f"{key} must be true or false")
        settings[key] = value
    return settings


def parse_timestamp(value, field):
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    try:
        from datetime import datetime

        text = str(value).replace("Z", "+00:00")
        return int(datetime.fromisoformat(text).timestamp())
    except ValueError:
        raise _bad(f"{field} must be an RFC 3339 timestamp")


def iso(timestamp):
    if not timestamp:
        return None
    from datetime import datetime, timezone

    return datetime.fromtimestamp(int(timestamp), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _allocate_slug(requested, title):
    if requested:
        slug = str(requested).strip().lower()
        if not ids.valid_slug(slug):
            raise _bad(
                "slug must be 3-48 characters of lowercase letters, digits, and hyphens, "
                "and not a reserved word"
            )
        return slug, True
    return ids.slugify(title), False


def create(payload, owner_email):
    title = str(payload.get("title", "")).strip()
    if not title:
        raise _bad("title is required")
    if len(title) > 200:
        raise _bad("title must be 200 characters or fewer")

    state = payload.get("state", "draft")
    if state not in ("draft", "open"):
        raise _bad("state must be draft or open at creation")

    settings = clean_settings(payload.get("settings"))
    expires_at = parse_timestamp(payload.get("expires_at"), "expires_at")
    retention_days = payload.get("retention_days", 365)
    if retention_days is not None:
        retention_days = int(retention_days)
        if retention_days < 1:
            raise _bad("retention_days must be at least 1, or null for indefinite")

    slug, explicit = _allocate_slug(payload.get("slug"), title)
    room_id = ids.ulid()
    timestamp = store.now()

    if not store.claim_pointer("SLUG", slug, room_id):
        if explicit:
            raise HttpError(409, "slug_taken", f"The slug '{slug}' is already in use.")
        slug = ids.slugify(f"{title}-{ids.readable_code(4)}")
        if not store.claim_pointer("SLUG", slug, room_id):
            raise HttpError(409, "slug_taken", "Could not allocate a unique slug.")

    room = {
        "room_id": room_id,
        "slug": slug,
        "title": title,
        "description": str(payload.get("description") or "").strip()[:1000] or None,
        "state": state,
        "settings": settings,
        "owner": owner_email.lower(),
        "expires_at": expires_at,
        "retention_days": retention_days,
        "created_at": timestamp,
        "updated_at": timestamp,
        "state_changed_at": timestamp,
        "q_total": 0,
        "q_answered": 0,
    }
    try:
        store.put_room(room)
    except Exception:
        # Never strand a slug on a room that was not created — the next attempt
        # with the same slug would fail with a misleading conflict.
        store.release_pointer("SLUG", slug)
        raise

    store.add_admin(room_id, owner_email, role="owner")
    return room


def load(identifier):
    """Resolve a room and apply any lifecycle transition that has fallen due."""
    room = store.resolve_room(identifier)
    if not room:
        return None
    expires_at = room.get("expires_at")
    if room.get("state") == "open" and expires_at and int(expires_at) <= store.now():
        room = transition(room, "closed") or room
    return room


def transition(room, target):
    current = room.get("state", "draft")
    if target == current:
        return room
    if target not in TRANSITIONS.get(current, set()):
        raise HttpError(400, "invalid_transition", f"Cannot move a room from {current} to {target}.")
    timestamp = store.now()
    fields = {
        "state": target,
        "state_changed_at": timestamp,
        "updated_at": timestamp,
        "GSI1PK": f"STATE#{target}",
        "GSI1SK": store.sort_key(timestamp),
    }
    if target == "closed" and room.get("retention_days"):
        fields["ttl"] = timestamp + int(room["retention_days"]) * 86400
    return store.update_room(room["room_id"], fields)


def apply_updates(room, payload):
    fields, settings_changed = {}, None
    for key in ("title", "description"):
        if key in payload:
            value = str(payload[key] or "").strip()
            if key == "title" and not value:
                raise _bad("title cannot be empty")
            fields[key] = value or None

    if "settings" in payload:
        settings_changed = clean_settings(payload["settings"], base=room.get("settings"))
        fields["settings"] = settings_changed

    if "expires_at" in payload:
        fields["expires_at"] = parse_timestamp(payload["expires_at"], "expires_at")

    if "retention_days" in payload:
        value = payload["retention_days"]
        fields["retention_days"] = int(value) if value is not None else None

    if "slug" in payload and payload["slug"] and payload["slug"] != room.get("slug"):
        slug = str(payload["slug"]).strip().lower()
        if not ids.valid_slug(slug):
            raise _bad("slug must be 3-48 characters of lowercase letters, digits, and hyphens")
        if not store.claim_pointer("SLUG", slug, room["room_id"]):
            raise HttpError(409, "slug_taken", f"The slug '{slug}' is already in use.")
        fields["slug"] = slug
        # The old pointer is deliberately kept, so shared links keep resolving.

    if fields:
        fields["updated_at"] = store.now()
        room = store.update_room(room["room_id"], fields)

    if "state" in payload and payload["state"] != room.get("state"):
        if payload["state"] not in STATES:
            raise _bad(f"state must be one of {list(STATES)}")
        room = transition(room, payload["state"])
    return room


def public_view(room):
    return {
        "room_id": room["room_id"],
        "slug": room.get("slug"),
        "title": room.get("title"),
        "description": room.get("description"),
        "state": room.get("state"),
        "url": f"{config.SITE_URL}/r/{room.get('slug')}",
        "settings": {
            key: room.get("settings", {}).get(key, value)
            for key, value in DEFAULT_SETTINGS.items()
        },
        "expires_at": iso(room.get("expires_at")),
    }


def admin_view(room):
    view = public_view(room)
    view.update(
        {
            "owner": room.get("owner"),
            "qr_url": f"{config.SITE_URL}/r/{room.get('slug')}/qr.svg",
            "present_url": f"{config.SITE_URL}/admin/rooms/{room['room_id']}/present",
            "created_at": iso(room.get("created_at")),
            "updated_at": iso(room.get("updated_at")),
            "retention_days": int(room["retention_days"]) if room.get("retention_days") else None,
            "counts": {
                "questions": int(room.get("q_total") or 0),
                "answered": int(room.get("q_answered") or 0),
            },
        }
    )
    return view


def accepting_questions(room):
    """An open room accepts questions, full stop — closing is the only pause."""
    return room.get("state") == "open"


def accepting_votes(room):
    return room.get("state") == "open"


def question_ttl(room):
    if not room.get("retention_days"):
        return None
    base = room.get("expires_at") or (store.now() + 86400)
    return int(base) + int(room["retention_days"]) * 86400


def live_room():
    """The most recently opened room, for the permanent /live link."""
    open_rooms = store.rooms_by_state("open", limit=10)
    fresh = []
    for room in open_rooms:
        expires_at = room.get("expires_at")
        if expires_at and int(expires_at) <= time.time():
            continue
        fresh.append(room)
    return fresh
