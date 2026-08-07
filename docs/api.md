# DataQnA — API reference

Version 0.1 (draft). Companion to the [specification](specification.md).

Base URL: `https://qna.dtcdev.click/api/v1`

## Authentication

| Caller | Header | Notes |
|--------|--------|-------|
| Script / automation | `Authorization: Bearer dq_...` | Created in the admin UI, shown once |
| Admin browser | `dq_session` cookie | Set by the Cognito login flow |
| Participant | none | The `dq_p` cookie is set automatically and identifies the voter, not a user |

Admin and API-key callers reach the same endpoints. A key never grants more than
its creating admin holds at request time; revoking the admin revokes the key.

Keys may be scoped to a single room at creation, in which case every request
outside that room returns `403`.

## Conventions

Requests and responses are JSON with `content-type: application/json`. Timestamps
are RFC 3339 UTC. Room-scoped paths accept either the `room_id` or the `slug`.

Errors:

```json
{ "error": { "code": "room_closed", "message": "This room is not accepting questions." } }
```

| Status | When |
|--------|------|
| `400` | Malformed request or failed validation |
| `401` | Missing or invalid credentials |
| `403` | Authenticated but not permitted, including presentation mode for non-admins |
| `404` | No such room or question, or a `draft` room requested publicly |
| `409` | Slug already taken, or idempotency key reused with a different body |
| `410` | Room is archived |
| `429` | Rate limited; see `Retry-After` |

Collection responses paginate with an opaque cursor:

```json
{ "items": [], "next_cursor": "eyJzayI6IlEjMDF..." , "etag": "W/\"a3f1\"" }
```

## Rooms

### `POST /rooms`

Creates a room. Requires an unscoped key.

```json
{
  "title": "Podcast #142 — live Q&A",
  "description": "Ask anything about the episode.",
  "slug": "podcast-142",
  "state": "open",
  "expires_at": "2026-08-13T19:00:00Z",
  "retention_days": 365,
  "admins": ["co-host@datatalks.club"],
  "settings": {
    "listed": true,
    "allow_names": true,
    "require_names": false,
    "answered_placement": "separate",
    "default_sort": "popular",
    "max_question_length": 500
  },
  "idempotency_key": "podcast-142"
}
```

Only `title` is required. `slug` is generated from the title when omitted; `state`
defaults to `draft`. The caller is the owner and does not need to be listed in
`admins`.

`201`:

```json
{
  "room_id": "01K3QJ7X8N2M4P6R8T0V2W4Y6A",
  "slug": "podcast-142",
  "title": "Podcast #142 — live Q&A",
  "state": "open",
  "url": "https://qna.dtcdev.click/r/podcast-142",
  "qr_url": "https://qna.dtcdev.click/r/podcast-142/qr.svg",
  "present_url": "https://qna.dtcdev.click/admin/rooms/01K3QJ7X8N2M4P6R8T0V2W4Y6A/present",
  "expires_at": "2026-08-13T19:00:00Z",
  "created_at": "2026-08-06T10:15:00Z",
  "owner": "alexey@datatalks.club",
  "admins": ["co-host@datatalks.club"],
  "settings": { "...": "..." },
  "counts": { "questions": 0, "answered": 0 }
}
```

Repeating the request with the same `idempotency_key` and an identical body returns
the same room and `200`. A different body returns `409`.

### `GET /rooms`

Rooms where the caller is owner or admin.

Query: `state` (repeatable), `q` (title substring), `limit` (default 50, max 200),
`cursor`.

### `GET /rooms/{room}`

The room as returned by create. Admin credentials return the full object;
unauthenticated callers get a public subset — no owner, no counts — and only
for `open` or `closed` rooms.

### `PATCH /rooms/{room}`

Partial update of `title`, `description`, `slug`, `state`, `expires_at`,
`retention_days`, and any key under `settings`.

```json
{ "state": "closed" }
```

Changing `slug` keeps the previous one as a permanent redirect. `state` accepts the
transitions in specification section 3.2; anything else returns `400`.

### `DELETE /rooms/{room}`

Owner only. Archives the room: the public URL returns `410`, data remains until
retention expires. `?purge=true` deletes immediately and irreversibly.

### `GET /rooms/{room}/qr.svg`, `GET /rooms/{room}/qr.png`

The public room URL as a QR code. Public, cacheable. `?size=` in pixels for PNG
(default 512, max 2048), `?margin=` in modules (default 4).

## Admins

### `GET /rooms/{room}/admins`

```json
{ "owner": "alexey@datatalks.club", "admins": ["co-host@datatalks.club"] }
```

### `PUT /rooms/{room}/admins/{email}`

Grants admin rights. The address must be a `@datatalks.club` Google identity in
the shared Cognito pool. To give someone outside the organization moderation
rights, issue a co-host code instead — see below.

### `DELETE /rooms/{room}/admins/{email}`

Revokes. Takes effect on the next request; existing sessions are not trusted
between requests.

### `POST /rooms/{room}/owner`

`{ "email": "..." }` — owner only. Transfers ownership; the previous owner stays as
an admin.

## Co-host invites

A co-host invite grants moderation and presentation rights for one room, to
someone with no account. It is a name, which goes in the link, plus a passcode,
which does not. Only room admins can create, read, or revoke them — a co-host
cannot reach any of these endpoints.

### `POST /rooms/{room}/cohosts`

```json
{ "name": "ivan", "passcode": "open-sesame-42" }
```

Both optional: an omitted `name` gets a readable two-word one, an omitted
`passcode` gets a generated one. A passcode must be at least 6 characters; a name
must be 3-48 characters of lowercase letters, digits, and hyphens, and unique
within this room — `409 name_taken` if it is already used here. `201`:

```json
{
  "invite_id": "01K3QJA...",
  "name": "ivan",
  "passcode": "Q7K2-M9XR-T8VB",
  "join_url": "https://qna.dtcdev.click/r/tonight/cohost/ivan",
  "created_at": "2026-08-06T10:15:00Z"
}
```

Send the recipient the `join_url` and the `passcode`, by different routes if it
matters: the link alone opens nothing. Passcodes are matched without regard to
case, dashes, or surrounding spaces. An invite has no expiry — it lasts as long
as the room, and revoking is how it ends.

### `GET /rooms/{room}/cohosts`

Lists the room's invites in full, passcodes included, so a host can re-share one
they have mislaid.

### `DELETE /rooms/{room}/cohosts/{invite_id}`

Revokes. Effective on the co-host's next request, not at the end of their session.

### Redeeming — `GET /r/{slug}/cohost/{name}`

Not part of the JSON API. Renders a form asking for the passcode; `POST` to the
same URL with `passcode` validates the pair, sets a room-scoped cookie, and
redirects to that room's moderation view.

A wrong name and a wrong passcode fail identically, with `403`, the form, and no
cookie — the page cannot be used to find out which invites exist.

## Questions

### `GET /rooms/{room}/questions`

Public for `open` and `closed` rooms. This is the endpoint the room page polls.

| Query | Default | Meaning |
|-------|---------|---------|
| `sort` | room's `default_sort` | `popular` or `recent` |
| `status` | `visible,answered` | Repeatable. `deleted` requires admin |
| `limit` | 100 | Max 500 |
| `cursor` | — | From `next_cursor` |

Send `If-None-Match` with the previous `etag` to get `304` when nothing changed.

```json
{
  "items": [
    {
      "question_id": "01K3QJ8A1B2C3D4E5F6G7H8J9K",
      "text": "How do you decide what to cover in a course?",
      "author_name": "Maria",
      "anonymous": false,
      "status": "visible",
      "score": 14,
      "pinned": false,
      "voted": true,
      "own": false,
      "editable_until": null,
      "created_at": "2026-08-06T18:22:11Z",
      "answered_at": null
    }
  ],
  "next_cursor": null,
  "etag": "W/\"a3f1c2\"",
  "counts": { "visible": 23, "answered": 7 }
}
```

`voted`, `own`, and `editable_until` are relative to the calling participant's
`dq_p` cookie and are absent for key-authenticated callers.

### `POST /rooms/{room}/questions`

Public. Requires state `open`.

```json
{ "text": "How do you decide what to cover in a course?", "author_name": "Maria" }
```

`author_name` is rejected when `allow_names` is `false` and required when
`require_names` is `true`. `201` returns the question, visible to everyone at
once. Starts at `score` 1 — the author's own.

### `PATCH /rooms/{room}/questions/{question_id}`

Admins set `status` (`visible`, `answered`, `deleted`), `pinned`, or
`text` — the last for fixing a typo before it goes on screen, not for changing what
someone asked.

Authors may set `text`, or `status` to `deleted`, within their edit window.

```json
{ "status": "answered" }
```

### `POST /rooms/{room}/questions/{question_id}/vote`

Public. Idempotent: voting twice leaves the score unchanged. `409` when the
room is not open.

`200`: `{ "score": 15, "voted": true }`

### `DELETE /rooms/{room}/questions/{question_id}/vote`

Withdraws the vote. `200`: `{ "score": 14, "voted": false }`

### `POST /rooms/{room}/questions/bulk`

Admin. One call for end-of-session cleanup.

```json
{ "question_ids": ["01K3...", "01K4..."], "action": "answer" }
```

Actions: `answer`, `delete`, `pin`, `unpin`. Max 100 ids.
Returns per-id results; a failure on one does not roll back the rest.

## API keys

Browser session only — keys cannot mint keys.

### `POST /api-keys`

```json
{ "name": "podcast automation", "room_id": null, "expires_at": null }
```

`201` returns `key` in full. It is not retrievable afterwards.

```json
{
  "key_id": "01K3QJ9...",
  "key": "dq_7Fk2Lm9Qx4Rt8Vb1Nz6Cw3Ey5Hj0Pd2Sa4Gf7Kl9Mn",
  "name": "podcast automation",
  "room_id": null,
  "created_at": "2026-08-06T10:15:00Z",
  "expires_at": null
}
```

### `GET /api-keys`

Metadata only: `key_id`, `name`, `room_id`, `created_at`, `expires_at`,
`last_used_at`.

### `DELETE /api-keys/{key_id}`

Immediate revocation.

## Health

### `GET /health`

Unauthenticated. `{ "status": "ok", "version": "..." }`

## Scripted event, end to end

```bash
set -euo pipefail
KEY=$DATAQNA_KEY
API=https://qna.dtcdev.click/api/v1

# Create the room ahead of the recording, still hidden.
ROOM=$(curl -sS -X POST "$API/rooms" \
  -H "authorization: Bearer $KEY" -H 'content-type: application/json' \
  -d '{"title":"Podcast #142","slug":"podcast-142","state":"draft",
       "admins":["co-host@datatalks.club"],"idempotency_key":"podcast-142"}' \
  | jq -r .room_id)

# Grab the QR code for the slide deck.
curl -sS "$API/rooms/$ROOM/qr.svg" -o podcast-142-qr.svg

# Open it when the stream starts, with a two-hour fuse.
curl -sS -X PATCH "$API/rooms/$ROOM" \
  -H "authorization: Bearer $KEY" -H 'content-type: application/json' \
  -d '{"state":"open","expires_at":"2026-08-13T21:00:00Z"}'
```
