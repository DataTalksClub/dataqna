# DataQnA — Specification

Version 0.1 (draft, 2026-08-06)

## 1. Purpose

Replace Slido for DataTalks.Club events. The system hosts audience Q&A rooms that
participants join anonymously by link or QR code. Participants submit questions and
upvote existing ones; the host works through the ranked list from a presentation
view designed to be projected or screen-shared.

Two properties drive the design and separate this from a generic forum:

- **Joining must cost nothing.** No account, no app, no email. One tap from a QR
  code to a text box.
- **Everything is scriptable.** Rooms for a recurring podcast or a course cohort
  are created, opened, closed, and exported through the REST API. The web UI is a
  convenience, never the only path.

### Non-goals for v1

Live polls, quizzes, word clouds, and the surrounding gamification. Slido has them;
they are not what the tool is used for here. Section 15 lists them as possible
later work.

## 2. Roles

| Role | Identity | How it is established |
|------|----------|-----------------------|
| **Participant** | Anonymous | A signed participant cookie issued on first visit to a room |
| **Admin** | `@datatalks.club` Google account, or a Cognito password user created by an operator | Authorization code + PKCE against `https://auth.dtcdev.click`, then a service session cookie |
| **API client** | An API key bound to an admin | `Authorization: Bearer dq_...` |

A participant is never asked to authenticate. The cookie exists to make voting
idempotent and to let someone edit or withdraw their own question — not to identify
them. It carries no personal data.

Admins are people in the DataTalks.Club Google workspace. External co-hosts who
need moderation rights are handled by creating a Cognito password user for them in
the shared pool (`admin-create-user`, documented in `aws-infra/sandbox/auth`), not
by weakening the room's authorization model.

## 3. Rooms

A room is one Q&A session. It owns its questions, its settings, and its admin list.

### 3.1 Identity and links

Each room has three identifiers:

- `room_id` — opaque, immutable, ULID-shaped. Used in the API and in storage.
- `slug` — the public URL segment. Chosen at creation (`llm-zoomcamp-2026`) or
  generated. Unique across all rooms, lowercase, `[a-z0-9-]{3,48}`. Mutable, with
  the previous slug kept as a permanent redirect so shared links never break.
- `code` — a six-character human-typeable join code (`Q7K2M9`), for when someone
  reads the link out loud. Resolves to the same room.

The public URL is `https://qna.dtcdev.click/r/<slug>`. That single URL is what goes
on a slide, in a podcast description, or into a QR code — there is no separate
"join" step and no separate presenter link for the audience.

### 3.2 Lifecycle

```text
 draft ──open──► open ──close──► closed ──archive──► archived
                  │                │
                  └──── reopen ────┘
```

| State | Public page | New questions | Voting |
|-------|-------------|---------------|--------|
| `draft` | 404 | — | — |
| `open` | visible | yes (unless `questions_open` is off) | yes |
| `closed` | visible, read-only | no | no |
| `archived` | 410 Gone | no | no |

`draft` lets a room be created and configured ahead of time — a course cohort's
room can exist weeks before the first session — without the link being live.

**Expiry.** A room may carry `expires_at`. When it passes, the room transitions to
`closed` automatically; it is never deleted by expiry alone. This covers the
one-hour event: create with `expires_at` an hour out and forget about it. A
four-month course room simply has no `expires_at`, or one at the cohort's end.

**Retention.** Separately, `retention_days` (default 365, `null` for indefinite)
sets a DynamoDB TTL on every item in the room, measured from the close date.
Retention deletes data; expiry only stops accepting it.

### 3.3 Settings

| Setting | Default | Meaning |
|---------|---------|---------|
| `title` | required | Shown on the public page and in presentation mode |
| `description` | `null` | Short context, rendered above the question box |
| `moderation` | `off` | `off`: questions appear immediately. `on`: they sit in a review queue and are invisible to others until approved |
| `questions_open` | `true` | Accept new questions. Turn off to freeze submissions while keeping voting live |
| `voting_open` | `true` | Accept upvotes |
| `allow_names` | `true` | Offer an optional name field. When `false`, all questions are anonymous |
| `require_names` | `false` | Make the name field mandatory |
| `answered_placement` | `separate` | `separate`: answered questions move to their own tab. `bottom`: they sink below open ones. `inline`: they stay in place, marked |
| `default_sort` | `popular` | `popular` or `recent` |
| `max_question_length` | `500` | Characters |
| `expires_at` | `null` | ISO 8601, see above |
| `retention_days` | `365` | See above |

## 4. Questions

### 4.1 Submission

A participant types the question, optionally a name, and submits. The question is
stored with the participant id derived from the cookie. No email, no IP retained
beyond the rate-limiting window (section 11).

Constraints: 1 to `max_question_length` characters after trimming; plain text only,
rendered escaped. A participant may edit or delete their own question for five
minutes after posting, or until it receives its first upvote — whichever comes
first.

### 4.2 States

| State | Visible to participants | Set by |
|-------|------------------------|--------|
| `pending` | Author only | Submission when `moderation` is `on` |
| `visible` | Everyone | Submission, or admin approval |
| `answered` | Everyone, marked | Admin |
| `hidden` | Nobody | Admin |
| `deleted` | Nobody | Admin, or the author within the edit window |

`hidden` and `deleted` differ in intent: `hidden` is moderation (the record stays,
and shows in exports as removed), `deleted` is withdrawal (the row is dropped from
exports). Neither is recoverable through the UI.

### 4.3 Ranking

`popular` sorts by score descending, then oldest first — so that among equally
upvoted questions, the one that has waited longest is answered next. `recent` sorts
by creation time descending.

Pinned questions are held at the top of both orderings, in pin order. A host uses
this to keep a seed question or a topic marker visible.

Score is the upvote count. There are no downvotes: they turn a question queue into
a popularity contest with a losing side, and the host already has `hidden` for
anything that needs removing.

### 4.4 Voting

One vote per participant per question, recorded as its own row so it can be
withdrawn. A participant cannot vote for their own question — the author's implicit
vote is already counted at submission, so every question starts at 1.

## 5. The public page

`GET /r/<slug>` returns a single server-rendered page. Everything below the header
updates by polling; there is no navigation away from it.

- **Header** — room title, description, question count, and a state banner when the
  room is closed.
- **Ask box** — always at the top, focused on load on desktop. Optional name field
  remembered in `localStorage` across rooms.
- **Tabs** — Popular / Recent, and Answered when `answered_placement` is
  `separate`. The user's own questions are marked with a subtle badge and are the
  only place edit and withdraw controls appear.
- **Question list** — text, author name or "Anonymous", relative timestamp, upvote
  button with count. The participant's own votes are shown as pressed.

The page is legible on a phone held in one hand in a dark room, which is the actual
usage context. Dark mode follows the system preference.

**Updates.** The client polls `GET /api/v1/rooms/{id}/questions` every 4 seconds
while the tab is visible and every 30 seconds when it is hidden, sending
`If-None-Match`. Unchanged responses are `304` and cost almost nothing. Optimistic
local updates apply immediately on submit and vote, and are reconciled on the next
poll.

WebSockets are deliberately not used in v1. API Gateway WebSocket APIs need
connection state, a disconnect path, and a fan-out mechanism, in exchange for
latency improvements measured in seconds on a screen a host reads aloud from.

## 6. The admin experience

`https://qna.dtcdev.click/admin`, behind Google sign-in.

- **Room list** — rooms where the signed-in user is owner or admin, grouped by
  state, with question and unanswered counts. "New room" opens a form covering the
  settings in section 3.3.
- **Room detail** — the same question list as the public page, plus per-question
  controls (mark answered, pin, hide, delete, edit for typos), the moderation queue
  when `moderation` is on, a bulk action bar, and room settings.
- **Share panel** — the public URL, the join code, a QR code with copy and download
  (SVG and PNG), and the "open presentation mode" button.
- **People** — the admin list, add and remove by email address.
- **Export** — JSON, CSV, or Markdown, covering questions, states, scores, and
  timestamps.

Room admins can do everything to a room except delete it or change its owner; those
belong to the owner. Ownership can be transferred to another admin.

## 7. Presentation mode

`https://qna.dtcdev.click/admin/rooms/<room_id>/present` — admin only, and returns
403 to anyone else. This is the screen that gets projected, so it is a distinct
view rather than a fullscreen toggle on the admin page: no controls that could be
mis-clicked on a shared screen, no other rooms' names, no moderation queue.

Layout: the current question fills most of the screen at a size readable from the
back of a room, with its author and score. A compact list of what is coming next
runs down one side. A corner holds the QR code and the short join code, so people
who arrive late can still join without the host interrupting themselves.

Keyboard only:

| Key | Action |
|-----|--------|
| `→` / `space` | Next question |
| `←` | Previous question |
| `Enter` | Mark current answered and advance |
| `p` | Pin current |
| `h` | Hide current |
| `q` | Toggle the QR overlay to full screen |
| `f` | Browser fullscreen |
| `Esc` | Back to room detail |

The list refreshes on the same polling loop, but the question currently on screen
never moves underneath the host — reordering applies to the upcoming list only, and
takes effect when they advance.

## 8. Host page (optional, section 16)

A permanent link that always points at whatever room is live right now:
`https://qna.dtcdev.click/@alexey` redirects to the host's currently open room, or
shows a short list when several are open, or a "nothing live right now" message.
This makes it possible to print one URL in a podcast description or a course
syllabus and never update it again.

## 9. API

Full reference in [api.md](api.md). The design rules:

- Every action available in the admin UI is available in the API. The UI calls the
  same endpoints with a session cookie instead of a bearer key.
- Keys are created in the admin UI, shown once, stored as a SHA-256 hash, and carry
  the permissions of the admin who created them. A key is scoped either to all of
  that admin's rooms or to a single room.
- `POST /api/v1/rooms` accepts an `idempotency_key`, so a script that creates a room
  per episode can be re-run safely.
- Participant endpoints (read questions, submit, vote) need no key — they are the
  public page's own API and are protected by rate limits, not credentials.

The recurring-event case in full:

```bash
curl -X POST https://qna.dtcdev.click/api/v1/rooms \
  -H "Authorization: Bearer $DATAQNA_KEY" \
  -H 'content-type: application/json' \
  -d '{
        "title": "Podcast #142 — live Q&A",
        "slug": "podcast-142",
        "state": "open",
        "expires_at": "2026-08-13T19:00:00Z",
        "admins": ["alexey@datatalks.club", "co-host@datatalks.club"],
        "idempotency_key": "podcast-142"
      }'
```

The response carries the public URL and a QR code URL, ready to drop into the
episode description.

## 10. Architecture

Modelled on `DataTalksClub/dapier`: AWS SAM, Python 3.12 Lambda, HTTP API with a
custom domain, DynamoDB on-demand, `uv` for dependencies, GitHub Actions with OIDC
for deployment.

```text
                     Route 53 · ACM
                           │
              API Gateway HTTP API (qna.dtcdev.click)
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
   PublicFunction     AdminFunction      ApiFunction
   /r/*  /api/v1/     /admin/*           /api/v1/rooms*
   rooms/*/questions  /auth/*            (bearer key)
   (participants)     (session cookie)
        │                  │                  │
        └──────────────────┼──────────────────┘
                           ▼
                DynamoDB  table: dataqna
                   GSI1 · TTL · on-demand
                           │
                    CloudWatch alarms
```

Three functions rather than one, split by trust boundary: the participant path is
unauthenticated and takes all the traffic, the admin path holds the session
signing key and the Cognito client, and the API path validates bearer keys. Each
gets only the IAM it needs, and a burst of participants cannot throttle admin
access.

Static assets (`app.css`, `app.js`) are served by the public function from the
deployment package, as in dapier. No build step, no bundler, no CDN in v1.

Region `eu-west-1`, matching the other services. The Cognito pool it authenticates
against lives in `us-east-1` and is not owned by this stack.

## 11. Data model

One DynamoDB table, `dataqna`, on-demand, TTL on `ttl`, point-in-time recovery on.

| Entity | PK | SK | GSI1PK | GSI1SK |
|--------|----|----|--------|--------|
| Room | `ROOM#<room_id>` | `META` | `STATE#<state>` | `<updated_at>` |
| Slug pointer | `SLUG#<slug>` | `META` | — | — |
| Code pointer | `CODE#<code>` | `META` | — | — |
| Question | `ROOM#<room_id>` | `Q#<question_id>` | — | — |
| Vote | `ROOM#<room_id>` | `V#<question_id>#<participant_id>` | — | — |
| Admin grant | `ROOM#<room_id>` | `ADMIN#<email>` | `USER#<email>` | `ROOM#<room_id>` |
| API key | `KEY#<sha256>` | `META` | `USER#<email>` | `KEY#<key_id>` |
| Rate counter | `RATE#<scope>` | `<window>` | — | — |
| Idempotency | `IDEM#<email>#<key>` | `META` | — | — |

Every question and vote for a room shares that room's partition, so the whole room
loads in one `Query`. Ranking happens in the Lambda — rooms hold hundreds of
questions, not millions, and sorting a few hundred items in memory is cheaper and
simpler than maintaining a sorted index. Above 2,000 questions the list paginates
and the tail is fetched on scroll.

Upvotes are an atomic `ADD` on the question item, guarded by a conditional write on
the vote row so a double-tap cannot double-count. Slug and code pointers are
separate items written with `attribute_not_exists(PK)`, which makes uniqueness a
property of the database rather than of application logic.

Admin grants are queried both directions from one item: by room for the People
panel, by user through GSI1 for the room list.

Rate counters and idempotency records carry short TTLs and are the only rows that
disappear on their own during a room's life.

## 12. Authentication and authorization

**Admins.** Authorization code + S256 PKCE against `https://auth.dtcdev.click`,
following the consumer contract in `aws-infra/sandbox/auth`: unpredictable `state`
and `nonce`, `openid email profile`, ID token validated for issuer, audience,
signature, expiry, and nonce, then an independent service session. The
implementation mirrors `dapier/src/admin.py`.

The session is an HMAC-signed token in a `dq_session` cookie — `HttpOnly`, `Secure`,
`SameSite=Lax`, 12-hour TTL — carrying the email and issue time and nothing else.
The signing secret is generated by the stack into Secrets Manager. Authorization is
re-read from DynamoDB on every request, so removing an admin takes effect
immediately rather than at next login.

This service needs its own Cognito app client with callback
`https://qna.dtcdev.click/auth/callback`, added to the shared pool in `aws-infra`.

**Participants.** On first request to a room page, the server sets `dq_p`, an
HMAC-signed random 128-bit id — `HttpOnly`, `Secure`, `SameSite=Lax`, lifetime
matching the room's retention. A participant who clears cookies becomes a new
participant and may vote again; this is accepted. Blocking it would require
fingerprinting or accounts, and the stakes are the ordering of a question list.

**API keys.** 32 bytes of randomness, presented as `dq_<base62>`, stored as
SHA-256. Shown once at creation. Each key records `last_used_at` and can be revoked
individually. Keys never grant more than the admin who created them holds at the
time of the request.

## 13. Abuse prevention

The public endpoints are open by design, so limits do the work credentials
otherwise would.

| Limit | Scope |
|-------|-------|
| 1 question per 10 seconds, 20 per hour | participant, per room |
| 120 votes per hour | participant, per room |
| 300 questions per hour | IP address, across rooms |
| 2,000 requests per 5 minutes | IP address |

Enforced with conditional counter items in DynamoDB, keyed by a truncated window,
with a TTL a little longer than the window. Exceeding a limit returns `429` with
`Retry-After`.

Two switches exist for when a room is under active abuse: `moderation: on` routes
everything through the review queue, and `questions_open: false` stops submissions
outright while leaving the room readable.

IP addresses are used for rate limiting only, hashed with a per-deployment salt,
and never stored on a question.

## 14. Operations

**Deployment.** `sam build && sam deploy --config-env sandbox`, driven by GitHub
Actions on `main` after tests pass, authenticating to AWS with OIDC. No long-lived
AWS credentials in the repository. `aws-infra` owns the ACM certificate, the
Route 53 record, the CloudFormation service role, the GitHub OIDC role, and the
Cognito app client; this repository owns application code and its own stack
resources.

**Monitoring.** CloudWatch alarms on function errors, p99 latency over 2 seconds on
the participant read path, DynamoDB throttles, and 5xx rate at the API. Structured
JSON logs with a request id and, where relevant, room id — never question text.

**Cost.** A 200-person, one-hour event with active polling is on the order of a few
hundred thousand HTTP API requests and a comparable number of DynamoDB reads, most
of which are `304` responses. Single-digit dollars per event on demand pricing, and
effectively nothing between events.

**Backups.** Point-in-time recovery on the table, 35 days.

## 15. Privacy

Rooms hold what participants type and a name if they choose to give one. No
accounts, no email addresses, no tracking, no third-party scripts, no analytics.
Retention is explicit per room and enforced by TTL. Exports let a host keep what
they need after the room's data is gone.

## 16. Open questions

1. **Domain.** `qna.dtcdev.click` is the sandbox pattern. Podcast listeners and
   course participants will see this URL — is a public-facing domain wanted
   instead, and if so which?
2. **Host page (section 8).** Confirm whether the permanent `/@handle` link is
   wanted for v1 or deferred.
3. **Slido import.** Is there value in importing existing Slido rooms' questions
   before the subscription lapses, or is the archive not needed?
4. **Question ordering during presentation.** Currently the host advances manually.
   An alternative is auto-advance to the highest-scoring unanswered question,
   which is livelier but can move under the host mid-sentence.
5. **Public room directory.** Should there be a page listing currently open rooms,
   or do rooms stay unlisted and shared only by link?

## 17. Later, not now

Live polls and quizzes. Word clouds. Question categories or tags. Threaded replies.
Written answers stored alongside questions. Slack notification when a question
crosses a score threshold. AI-assisted duplicate detection and clustering, which is
the feature most likely to matter for a 200-person course room.
