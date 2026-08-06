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
    "moderation": "off",
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
  "code": "Q7K2M9",
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
  "counts": { "questions": 0, "unanswered": 0, "pending": 0 }
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
unauthenticated callers get a public subset — no admin list, no counts of pending
questions — and only for `open` or `closed` rooms.

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

### `GET /rooms/{room}/export`

`?format=json|csv|md`. Questions with state, score, author name, and timestamps.
Withdrawn questions are omitted; moderator-hidden ones appear marked. Admin only.

## Admins

### `GET /rooms/{room}/admins`

```json
{ "owner": "alexey@datatalks.club", "admins": ["co-host@datatalks.club"] }
```

### `PUT /rooms/{room}/admins/{email}`

Grants admin rights. The address must be resolvable in the shared Cognito pool —
either an `@datatalks.club` Google identity or a password user created by an
operator. Unknown addresses return `400` rather than creating a grant that can
never be used.

### `DELETE /rooms/{room}/admins/{email}`

Revokes. Takes effect on the next request; existing sessions are not trusted
between requests.

### `POST /rooms/{room}/owner`

`{ "email": "..." }` — owner only. Transfers ownership; the previous owner stays as
an admin.

## Questions

### `GET /rooms/{room}/questions`

Public for `open` and `closed` rooms. This is the endpoint the room page polls.

| Query | Default | Meaning |
|-------|---------|---------|
| `sort` | room's `default_sort` | `popular` or `recent` |
| `status` | `visible,answered` | Repeatable. `pending`, `hidden`, and `deleted` require admin |
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
  "counts": { "visible": 23, "answered": 7, "pending": 0 }
}
```

`voted`, `own`, and `editable_until` are relative to the calling participant's
`dq_p` cookie and are absent for key-authenticated callers.

### `POST /rooms/{room}/questions`

Public. Requires `questions_open` and state `open`.

```json
{ "text": "How do you decide what to cover in a course?", "author_name": "Maria" }
```

`author_name` is rejected when `allow_names` is `false` and required when
`require_names` is `true`. `201` returns the question, with `status` `pending` under
moderation. Starts at `score` 1 — the author's own.

### `PATCH /rooms/{room}/questions/{question_id}`

Admins set `status` (`visible`, `answered`, `hidden`, `deleted`), `pinned`, or
`text` — the last for fixing a typo before it goes on screen, not for changing what
someone asked.

Authors may set `text`, or `status` to `deleted`, within their edit window.

```json
{ "status": "answered" }
```

### `POST /rooms/{room}/questions/{question_id}/vote`

Public. Idempotent: voting twice leaves the score unchanged. `403` when the caller
is the author or `voting_open` is `false`.

`200`: `{ "score": 15, "voted": true }`

### `DELETE /rooms/{room}/questions/{question_id}/vote`

Withdraws the vote. `200`: `{ "score": 14, "voted": false }`

### `POST /rooms/{room}/questions/bulk`

Admin. One call for the moderation queue and end-of-session cleanup.

```json
{ "question_ids": ["01K3...", "01K4..."], "action": "approve" }
```

Actions: `approve`, `answer`, `hide`, `delete`, `pin`, `unpin`. Max 100 ids.
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

# Afterwards, keep the transcript.
curl -sS "$API/rooms/$ROOM/export?format=md" \
  -H "authorization: Bearer $KEY" -o podcast-142-questions.md
```
