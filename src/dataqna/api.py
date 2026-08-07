"""The REST API.

Every action in the admin UI is available here. The browser calls these same
routes with a session cookie; scripts call them with a bearer key. Participant
routes take neither and are protected by rate limits instead.
"""


from . import config, http, ids, questions, rooms, security, store
from .http import HttpError

API_PREFIX = "/api/v1"


class Identity:
    """Who is calling, and how much that is worth.

    Three ways in, and only three:

    Signed in with a DataTalks.Club Google account — an admin, of the rooms
    they own or have been granted.

    Holding a session's secret code — an admin *of that one session*: its
    questions, its settings, its lifecycle, its presentation view.

    Neither — a participant, who can ask and vote and nothing else.

    The line a code does not cross is handing on access. Adding admins, minting
    or reading co-host codes, changing the published slug, deleting the room,
    and anything touching another room all stay with the signed-in owner, so a
    session code can never grow into more than the session it was cut for.
    """

    def __init__(self, email=None, source="anonymous", key_room_id=None, cohost=None):
        self.email = email
        self.source = source
        self.key_room_id = key_room_id
        self.cohost = cohost

    @property
    def authenticated(self):
        return bool(self.email)

    def _key_allows(self, room):
        return not self.key_room_id or self.key_room_id == room["room_id"]

    def is_cohost_of(self, room):
        """Re-checked against storage, so revoking a code takes effect at once."""
        if not self.cohost or self.cohost.get("room_id") != room["room_id"]:
            return False
        return bool(store.get_cohost_invite(room["room_id"], self.cohost.get("invite_id")))

    def is_admin_of(self, room):
        if not self.authenticated or not self._key_allows(room):
            return False
        return store.is_admin(room["room_id"], self.email)

    def moderates(self, room):
        return self.is_admin_of(room) or self.is_cohost_of(room)

    def role_in(self, room):
        if self.is_admin_of(room):
            return "owner" if room.get("owner") == self.email else "admin"
        return "cohost" if self.is_cohost_of(room) else None

    def require_moderator(self, room):
        if self.moderates(room):
            return
        if self.authenticated and not self._key_allows(room):
            raise HttpError(403, "key_scope", "This API key is scoped to a different room.")
        if self.authenticated or self.cohost:
            raise HttpError(403, "forbidden", "You cannot moderate this room.")
        raise HttpError(401, "unauthenticated", "Sign in, provide an API key, or enter a co-host code.")

    def require_admin(self, room):
        if not self.authenticated:
            if self.cohost:
                raise HttpError(403, "cohost_scope", "A co-host code does not allow this. Ask the room owner.")
            raise HttpError(401, "unauthenticated", "Sign in or provide an API key.")
        if not self._key_allows(room):
            raise HttpError(403, "key_scope", "This API key is scoped to a different room.")
        if not store.is_admin(room["room_id"], self.email):
            raise HttpError(403, "forbidden", "You are not an admin of this room.")

    def require_owner(self, room):
        self.require_admin(room)
        if room.get("owner") != self.email and self.email not in config.ROOT_ADMINS:
            raise HttpError(403, "forbidden", "Only the room owner can do this.")

    def require_session(self):
        if self.source != "session":
            raise HttpError(403, "session_required", "This action requires a signed-in browser session.")


def identify(event):
    """Resolve the caller from a bearer key, then a session cookie."""
    authorization = http.header(event, "authorization")
    if authorization.lower().startswith("bearer "):
        presented = authorization[7:].strip()
        record = store.get_api_key(security.hash_api_key(presented))
        if not record:
            raise HttpError(401, "invalid_key", "Unknown or revoked API key.")
        if record.get("expires_at") and int(record["expires_at"]) <= store.now():
            raise HttpError(401, "expired_key", "This API key has expired.")
        store.touch_api_key(record["key_hash"])
        return Identity(
            email=record["email"], source="key", key_room_id=record.get("room_id") or None
        )

    email = security.session_email(http.cookie(event, config.SESSION_COOKIE))
    if email:
        return Identity(email=email, source="session")

    cohost = security.cohost_claim(http.cookie(event, config.COHOST_COOKIE))
    if cohost:
        return Identity(source="cohost", cohost=cohost)
    return Identity()


def ensure_participant(event):
    """Return (participant_id, set_cookie_or_None)."""
    token = http.cookie(event, config.PARTICIPANT_COOKIE)
    participant = security.participant_id(token)
    if participant:
        return participant, None
    token = security.new_participant_token()
    return security.participant_id(token), http.set_cookie(
        config.PARTICIPANT_COOKIE, token, max_age=config.PARTICIPANT_TTL_SECONDS
    )


def _require_room(identifier, *, allow_archived=False):
    room = rooms.load(identifier)
    if not room:
        raise HttpError(404, "not_found", "No such room.")
    if room.get("state") == "archived" and not allow_archived:
        raise HttpError(410, "archived", "This room has been archived.")
    return room


def _readable(room, identity):
    """A draft room is invisible to anyone who is not an admin of it."""
    if room.get("state") != "draft":
        return
    if not identity.moderates(room):
        raise HttpError(404, "not_found", "No such room.")


def _limit(scope, window, cap):
    allowed, _ = store.rate_allow(scope, window, cap)
    if not allowed:
        raise HttpError(429, "rate_limited", "Too many requests. Wait a moment and try again.")


# --- routes -----------------------------------------------------------------


def route(event, segments, method, identity):
    """Dispatch a path already stripped of the /api/v1 prefix."""
    if segments == ["health"]:
        return http.json_response(200, {"status": "ok"})

    if segments and segments[0] == "api-keys":
        return _api_keys(event, segments[1:], method, identity)

    if not segments or segments[0] != "rooms":
        raise HttpError(404, "not_found", "Unknown endpoint.")

    rest = segments[1:]
    if not rest:
        if method == "POST":
            return _create_room(event, identity)
        if method == "GET":
            return _list_rooms(identity)
        raise HttpError(405, "method_not_allowed", f"{method} is not allowed here.")

    room = _require_room(rest[0], allow_archived=method == "DELETE")
    tail = rest[1:]

    if not tail:
        return _room_detail(event, room, method, identity)
    if tail == ["questions"]:
        return _questions(event, room, method, identity)
    if tail == ["questions", "bulk"] and method == "POST":
        return _bulk(event, room, identity)
    if len(tail) == 2 and tail[0] == "questions":
        return _question(event, room, tail[1], method, identity)
    if len(tail) == 3 and tail[0] == "questions" and tail[2] == "vote":
        return _vote(event, room, tail[1], method, identity)
    if tail == ["cohosts"]:
        return _cohosts(event, room, method, identity)
    if len(tail) == 2 and tail[0] == "cohosts" and method == "DELETE":
        identity.require_admin(room)
        if not store.revoke_cohost_invite(room["room_id"], tail[1]):
            raise HttpError(404, "not_found", "No such co-host code.")
        return http.json_response(200, {"revoked": True})
    raise HttpError(404, "not_found", "Unknown endpoint.")


def _create_room(event, identity):
    if not identity.authenticated:
        raise HttpError(401, "unauthenticated", "Sign in or provide an API key.")
    if identity.key_room_id:
        raise HttpError(403, "key_scope", "This API key is scoped to a single room.")
    payload = http.body(event)

    idempotency_key = str(payload.get("idempotency_key") or "").strip()
    if idempotency_key:
        existing_id = store.claim_idempotency(identity.email, idempotency_key, "pending")
        if existing_id and existing_id != "pending":
            existing = store.get_room(existing_id)
            if existing:
                return http.json_response(200, rooms.admin_view(existing))
        # "pending" means an earlier attempt claimed the key and then failed.
        # Fall through and let this attempt create the room properly.

    room = rooms.create(payload, identity.email)
    if idempotency_key:
        store.table().update_item(
            Key={"PK": f"IDEM#{identity.email}#{idempotency_key}", "SK": "META"},
            UpdateExpression="SET room_id = :r",
            ExpressionAttributeValues={":r": room["room_id"]},
        )
    return http.json_response(201, rooms.admin_view(room))


def _list_rooms(identity):
    if not identity.authenticated:
        raise HttpError(401, "unauthenticated", "Sign in or provide an API key.")
    found = store.rooms_for_user(identity.email)
    if identity.key_room_id:
        found = [room for room in found if room["room_id"] == identity.key_room_id]
    found.sort(key=lambda room: int(room.get("updated_at") or 0), reverse=True)
    return http.json_response(200, {"items": [rooms.admin_view(room) for room in found]})


def _room_detail(event, room, method, identity):
    if method == "GET":
        _readable(room, identity)
        role = identity.role_in(room)
        if role:
            return http.json_response(200, dict(rooms.admin_view(room), role=role))
        return http.json_response(200, rooms.public_view(room))
    if method == "PATCH":
        identity.require_moderator(room)
        payload = http.body(event)
        # The slug is the link the owner published; a session code must not be
        # able to break it out from under them.
        if "slug" in payload and not identity.is_admin_of(room):
            raise HttpError(403, "cohost_scope", "Only a room admin can change the link.")
        updated = rooms.apply_updates(room, payload)
        return http.json_response(200, rooms.admin_view(updated))
    if method == "DELETE":
        identity.require_owner(room)
        if str(http.query(event).get("purge", "")).lower() in ("1", "true", "yes"):
            store.delete_room(room)
            return http.json_response(200, {"deleted": True, "purged": True})
        rooms.transition(room, "archived")
        return http.json_response(200, {"deleted": True, "purged": False})
    raise HttpError(405, "method_not_allowed", f"{method} is not allowed here.")


def _questions(event, room, method, identity):
    is_admin = identity.moderates(room)
    _readable(room, identity)

    if method == "GET":
        query = http.query(event)
        sort = query.get("sort")
        if sort and sort not in ("popular", "recent"):
            raise HttpError(400, "invalid_request", "sort must be popular or recent")
        statuses = [s for s in (query.get("status") or "").split(",") if s]
        if statuses and not is_admin:
            statuses = [s for s in statuses if s in questions.PUBLIC_STATUSES]
        participant = security.participant_id(http.cookie(event, config.PARTICIPANT_COOKIE))

        items, counts, tag = questions.collect(
            room, participant=participant, is_admin=is_admin, sort=sort, statuses=statuses or None
        )
        if http.header(event, "if-none-match") == tag:
            return http.response(304, "", headers={"etag": tag, "cache-control": "no-store"})
        return http.json_response(
            200,
            {"items": items, "counts": counts, "etag": tag, "state": room.get("state")},
            headers={"etag": tag},
        )

    if method == "POST":
        participant, cookie = ensure_participant(event)
        ip = http.source_ip(event)
        _limit(f"q:{room['room_id']}:{participant}", 10, 1)
        _limit(f"qh:{room['room_id']}:{participant}", 3600, 20)
        if ip:
            _limit(f"ip:{ip}", 3600, 300)
        question = questions.submit(room, http.body(event), participant)
        return http.json_response(
            201,
            questions.serialize(question, participant=participant, voted=True),
            cookies=[cookie] if cookie else None,
        )

    raise HttpError(405, "method_not_allowed", f"{method} is not allowed here.")


def _question(event, room, question_id, method, identity):
    question = store.get_question(room["room_id"], question_id)
    if not question or question.get("status") == "deleted":
        raise HttpError(404, "not_found", "No such question.")

    if method != "PATCH":
        raise HttpError(405, "method_not_allowed", f"{method} is not allowed here.")

    payload = http.body(event)
    is_admin = identity.moderates(room)
    participant = security.participant_id(http.cookie(event, config.PARTICIPANT_COOKIE))

    if not is_admin:
        # Authors may fix or withdraw their own question, briefly.
        if not questions.can_author_edit(question, participant):
            raise HttpError(403, "forbidden", "This question can no longer be changed.")

        if set(payload) - {"text", "status"}:
            raise HttpError(403, "forbidden", "You may only edit or withdraw your question.")
        if payload.get("status") not in (None, "deleted"):
            raise HttpError(403, "forbidden", "You may only withdraw your question.")

    updated = question
    if "text" in payload:
        text = str(payload["text"]).strip()
        limit = int(room.get("settings", {}).get("max_question_length", 500))
        if not text or len(text) > limit:
            raise HttpError(400, "invalid_request", f"text must be 1 to {limit} characters")
        updated = store.update_question(room["room_id"], question_id, {"text": text})
    if "pinned" in payload:
        if not is_admin:
            raise HttpError(403, "forbidden", "Only admins can pin questions.")
        updated = store.update_question(
            room["room_id"], question_id, {"pinned": bool(payload["pinned"])}
        )
    if "status" in payload:
        updated = questions.set_status(room, updated, payload["status"])

    return http.json_response(200, questions.serialize(updated, participant=participant, is_admin=is_admin))


def _vote(event, room, question_id, method, identity):
    question = store.get_question(room["room_id"], question_id)
    if not question or questions.status_of(question) not in questions.PUBLIC_STATUSES:
        raise HttpError(404, "not_found", "No such question.")
    if not rooms.accepting_votes(room):
        raise HttpError(409, "voting_closed", "Voting is closed for this room.")

    participant, cookie = ensure_participant(event)
    _limit(f"v:{room['room_id']}:{participant}", 3600, 120)
    cookies = [cookie] if cookie else None

    if method == "POST":
        store.add_vote(room["room_id"], question_id, participant, ttl=rooms.question_ttl(room))
        voted = True
    elif method == "DELETE":
        store.remove_vote(room["room_id"], question_id, participant)
        voted = False
    else:
        raise HttpError(405, "method_not_allowed", f"{method} is not allowed here.")

    refreshed = store.get_question(room["room_id"], question_id)
    return http.json_response(
        200, {"score": int(refreshed.get("score") or 0), "voted": voted}, cookies=cookies
    )


def _bulk(event, room, identity):
    identity.require_moderator(room)
    payload = http.body(event)
    action = payload.get("action")
    ids_ = payload.get("question_ids") or []
    if not isinstance(ids_, list) or not ids_:
        raise HttpError(400, "invalid_request", "question_ids must be a non-empty list")
    if len(ids_) > 100:
        raise HttpError(400, "invalid_request", "question_ids is limited to 100 per call")

    mapping = {
        "answer": ("status", "answered"),
        "hide": ("status", "hidden"),
        "delete": ("status", "deleted"),
        "pin": ("pinned", True),
        "unpin": ("pinned", False),
    }
    if action not in mapping:
        raise HttpError(400, "invalid_request", f"action must be one of {sorted(mapping)}")

    field, value = mapping[action]
    results = []
    for question_id in ids_:
        question = store.get_question(room["room_id"], question_id)
        if not question:
            results.append({"question_id": question_id, "ok": False, "error": "not_found"})
            continue
        try:
            if field == "status":
                questions.set_status(room, question, value)
            else:
                store.update_question(room["room_id"], question_id, {"pinned": value})
            results.append({"question_id": question_id, "ok": True})
        except HttpError as exc:
            results.append({"question_id": question_id, "ok": False, "error": exc.code})
    return http.json_response(200, {"results": results})


def _cohost_view(room, invite):
    return {
        "invite_id": invite["invite_id"],
        "name": invite["name"],
        "passcode": invite["passcode"],
        "join_url": f"{config.SITE_URL}/r/{room.get('slug')}/cohost/{invite['name']}",
        "created_at": rooms.iso(invite.get("created_at")),
    }


def _cohosts(event, room, method, identity):
    """Co-host invites are created, read, and revoked by room admins only."""
    identity.require_admin(room)

    if method == "GET":
        return http.json_response(
            200,
            {"items": [_cohost_view(room, invite) for invite in store.list_cohost_invites(room["room_id"])]},
        )

    if method == "POST":
        payload = http.body(event)
        passcode = str(payload.get("passcode") or "").strip() or security.new_cohost_code()
        if len(passcode) < 6:
            raise HttpError(400, "invalid_request", "A passcode must be at least 6 characters.")

        requested = store.normalize_cohost_name(payload.get("name"))
        if requested and not ids.SLUG_PATTERN.match(requested):
            raise HttpError(
                400, "invalid_request",
                "A link name must be 3-48 characters of lowercase letters, digits, and hyphens.",
            )

        invite_id = ids.ulid()
        name = requested or security.new_cohost_name()
        if not store.claim_cohost_name(name, room["room_id"], invite_id):
            if requested:
                raise HttpError(
                    409, "name_taken", f"This session already has a link named '{name}'."
                )
            name = security.new_cohost_name()
            if not store.claim_cohost_name(name, room["room_id"], invite_id):
                raise HttpError(503, "name_exhausted", "Could not allocate a link name. Try again.")

        invite = {
            "invite_id": invite_id,
            "room_id": room["room_id"],
            "name": name,
            "passcode": passcode,
            "created_by": identity.email,
            "created_at": store.now(),
        }
        store.put_cohost_invite(invite)
        return http.json_response(201, _cohost_view(room, invite))

    raise HttpError(405, "method_not_allowed", f"{method} is not allowed here.")


def redeem_cohost(room, name, passcode, source_ip=""):
    """Validate a link name and its passcode together, within one room.

    Returns (invite, error_message). The link alone proves nothing: it names an
    invite, and the passcode is what grants access. Failures are deliberately
    indistinguishable, so this cannot be used to discover which link names
    exist.
    """
    generic = "That link and passcode do not match. Check them with the host."

    # Guessing a passcode has to be expensive, and the attempt is unauthenticated.
    if source_ip:
        allowed, _ = store.rate_allow(f"cohost:{source_ip}", 300, 10)
        if not allowed:
            return None, "Too many attempts. Wait a few minutes and try again."

    if not room or room.get("state") == "archived":
        return None, "That session is no longer available."

    invite = store.resolve_cohost_name(room["room_id"], name)
    if not invite:
        return None, generic
    if not security.constant_time_equals(
        store.normalize_cohost_code(passcode), store.normalize_cohost_code(invite["passcode"])
    ):
        return None, generic
    return invite, None


def _api_keys(event, tail, method, identity):
    if not identity.authenticated:
        raise HttpError(401, "unauthenticated", "Sign in first.")
    identity.require_session()

    if not tail:
        if method == "GET":
            return http.json_response(
                200,
                {
                    "items": [
                        {
                            "key_id": item["key_id"],
                            "name": item.get("name"),
                            "room_id": item.get("room_id"),
                            "created_at": rooms.iso(item.get("created_at")),
                            "expires_at": rooms.iso(item.get("expires_at")),
                            "last_used_at": rooms.iso(item.get("last_used_at")),
                        }
                        for item in store.list_api_keys(identity.email)
                    ]
                },
            )
        if method == "POST":
            payload = http.body(event)
            key, key_hash = security.new_api_key()
            record = {
                "key_id": ids.ulid(),
                "key_hash": key_hash,
                "email": identity.email,
                "name": str(payload.get("name") or "").strip()[:80] or "unnamed",
                "room_id": str(payload.get("room_id") or "").strip() or None,
                "created_at": store.now(),
                "expires_at": rooms.parse_timestamp(payload.get("expires_at"), "expires_at"),
            }
            store.put_api_key(record)
            return http.json_response(
                201,
                {
                    "key_id": record["key_id"],
                    "key": key,
                    "name": record["name"],
                    "room_id": record["room_id"],
                    "created_at": rooms.iso(record["created_at"]),
                    "expires_at": rooms.iso(record["expires_at"]),
                },
            )

    if len(tail) == 1 and method == "DELETE":
        for item in store.list_api_keys(identity.email):
            if item["key_id"] == tail[0]:
                store.delete_api_key(item["key_hash"])
                return http.json_response(200, {"deleted": True})
        raise HttpError(404, "not_found", "No such key.")

    raise HttpError(405, "method_not_allowed", f"{method} is not allowed here.")
