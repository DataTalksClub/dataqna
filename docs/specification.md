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
  are created, opened, and closed through the REST API. The web UI is a
  convenience, never the only path.

### Non-goals for v1

Live polls, quizzes, word clouds, and the surrounding gamification. Slido has them;
they are not what the tool is used for here. Section 15 lists them as possible
later work.

## 2. Roles

| Role | Identity | How it is established |
|------|----------|-----------------------|
| **Participant** | Anonymous | A signed participant cookie issued on first visit to a room |
| **Co-host** | Anonymous, room-scoped | A secret code from a room admin, exchanged for a room-scoped cookie |
| **Admin** | `@datatalks.club` Google account | Authorization code + PKCE against `https://auth.dtcdev.click`, then a service session cookie |
| **API client** | An API key bound to an admin | `Authorization: Bearer dq_...` |

A participant is never asked to authenticate. The cookie exists to make voting
idempotent and to let someone edit or withdraw their own question — not to identify
them. It carries no personal data.

Admins are people in the DataTalks.Club Google workspace, and that is the only way
to become one. The `dataqna` app client is Google-only like every other client in
the shared pool, so nothing about this service creates an account that could reach
a sibling service.

Guest hosts are handled without accounts at all. See section 2.1.

### 2.1 Co-hosts

A room admin generates a **co-host invite**: a name and a passcode. The name goes
in the link — `/r/<slug>/cohost/<name>` — and is not secret; the passcode is
three groups of four characters, like `Q7K2-M9XR-T8VB`, drawn from an alphabet
with no glyph you can misread or mishear. Both together let someone moderate
that one room: answer, pin, delete, edit for typos, and run presentation mode.
They need no account, no email address, and no prior relationship with the
organization.

Splitting the invite in two is what makes forwarding the link harmless: the link
says which invite you mean, the passcode is what opens it, and they travel by
different routes. The link carries its room, so a name only has to be unique
inside one session — two sessions can each have an `ivan` — and the URL says
which session it opens rather than looking like a claim on the whole site.

What a co-host code deliberately cannot do:

- reach any other room, or even learn that other rooms exist;
- change the room's settings, state, or expiry;
- add admins, or create or read co-host codes — a co-host cannot widen their own
  access or pass it on in a form that outlives their own;
- create rooms, list rooms, or mint API keys;
- delete the room.

This is the whole of the guest-access story. The earlier design gave guest hosts
Cognito password accounts in the shared pool, which meant one service's guest was
an identity in a pool five other services trust — a large mechanism, and a large
blast radius, for what is really "let this person help me run tonight's Q&A".

An invite has no expiry. It is valid exactly as long as the session it belongs
to, because that is the question a host can actually answer — "is Ivan still
helping me run this?" — where "has it been thirty days?" is one they would have
to look up. Revoking is how an invite ends, and it takes effect on the next
request rather than at the end of a session. The redeemed cookie does expire, at
thirty days, because a signed cookie has to say when it stops being valid;
redeeming the same link again is free.

The passcode is stored in the clear under the room's partition, because a host
has to be able to read it back and say it out loud a second time; it is only ever
returned through admin-authorized endpoints. The lookup pointer used at
redemption is keyed by the room and the name together, so resolving a link needs
no scan, and a wrong name and a wrong passcode fail identically — the form cannot
be used to discover which invites exist.

## 3. Rooms

A room is one Q&A session. It owns its questions, its settings, and its admin list.

### 3.1 Identity and links

Each room has two identifiers:

- `room_id` — opaque, immutable, ULID-shaped. Used in the API and in storage.
- `slug` — the public URL segment. Chosen at creation (`llm-zoomcamp-2026`) or
  generated. Unique across all rooms, lowercase, `[a-z0-9-]{3,48}`. Mutable, with
  the previous slug kept as a permanent redirect so shared links never break.

There is deliberately no join code. Slido needs one because a participant has to
find a session among all the sessions in the world; here the link *is* the session,
and a QR code carries it. A second identifier would be one more thing to print,
read out, mistype, and keep in sync.

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
| `open` | visible | yes | yes |
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
| `listed` | `true` | Show the session on the public front page. Off makes it reachable by link only |
| `allow_names` | `true` | Offer an optional name field. When `false`, all questions are anonymous |
| `require_names` | `false` | Make the name field mandatory |
| `answered_placement` | `separate` | `separate`: answered questions move to their own tab. `bottom`: they sink below open ones. `inline`: they stay in place, marked |
| `default_sort` | `popular` | `popular` or `recent` |
| `max_question_length` | `450` | Characters. Slido caps at 300; half as long again is generous without letting a question become a speech |
| `expires_at` | `null` | ISO 8601, see above |
| `retention_days` | `365` | See above |

There is deliberately no pre-publication review queue and no pause switch for
questions or votes: an open room accepts both, a closed room accepts neither.
A question is visible to everyone the moment it is asked. Moderation happens
after the fact — `deleted` removes anything that needs removing — and closing
the room is how a session stops.

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
| `visible` | Everyone | Submission |
| `answered` | Everyone, marked | Admin |
| `deleted` | Nobody | Admin, or the author within the edit window |

Two earlier states are gone. `pending` fed a review queue; `hidden` was a
removal that did not remove — the question left the room and stayed in a tab
nobody ever went back to, so it was the same decision as deleting with a pile
of admin left over. There is one way to take a question away, it is called
delete, and it is not recoverable through the UI.

### 4.3 Ranking

`popular` sorts by score descending, then oldest first — so that among equally
upvoted questions, the one that has waited longest is answered next. `recent` sorts
by creation time descending.

Pin is singular. One question per room is pinned at a time — the pin is the host
holding one question up for the room, and two held up is just the list again — so
pinning one quietly unpins the room's other pinned question. A pinned question
that is answered or deleted takes no pin with it. A host uses this to hold the
question being discussed above the vote race.

Score is the upvote count. There are no downvotes: they turn a question queue into
a popularity contest with a losing side, and the host already has `deleted` for
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
- **Host icons** — a cog into the room's console and a screen into presentation
  mode, in the header, rendered only for whoever already moderates the room. A
  host who has been handed the audience link is one tap from either instead of
  hunting the session down again through `/admin` while the room watches. They
  sit at the weight of the theme toggle beside them: the audience outnumbers
  the host on this page, and nothing here should read louder than the question
  composer. The page is `no-store`, so it can differ per viewer; everyone else
  is not told the routes exist, and both enforce access themselves regardless.

The page is legible on a phone held in one hand in a dark room, which is the actual
usage context. It opens in light mode for everyone regardless of what their device
prefers — a room link reaches people who did not choose to be here, and it should
look the way it looked on the slide they scanned it from. The header toggle is how
anyone changes that, and the choice sticks.

**Updates.** The client polls `GET /api/v1/rooms/{id}/questions` every 4 seconds
while the tab is visible and every 30 seconds when it is hidden, sending
`If-None-Match`. Unchanged responses are `304` and cost almost nothing. Optimistic
local updates apply immediately on submit and vote, and are reconciled on the next
poll.

Presentation mode polls the same endpoint every **1 second** — see section 5.1 for
why the two rates differ.

### 5.1 Why polling, and why two rates

The audience page and the projector have opposite economics, and conflating them is
what makes real-time look expensive.

The room page is multiplied by everyone in the room. Two hundred people polling
every second is where throttling and cost begin, and an attendee seeing a vote tick
four seconds late loses nothing. Presentation mode is **one client** — the host's
screen. Making that feel live costs 3,600 mostly-`304` requests an hour for a single
viewer, which is free in every sense that matters. So the projector polls at 1s and
the audience at 4s.

That asymmetry is the whole reason no push mechanism is needed. Fan-out to the
audience is what makes WebSockets expensive; the surface that actually has to feel
immediate has exactly one connection.

**Alternatives considered.**

| Option | Why not |
|---|---|
| API Gateway WebSockets | Connection state in DynamoDB, disconnect pruning on `410`, and a fan-out of one `PostToConnection` call per client per update. Permanent complexity to save three seconds on one screen. |
| Long polling | The Lambda bills for the whole time it holds the request open, and API Gateway caps the integration at 30 seconds. |
| Server-Sent Events | Only needs one direction, which fits — votes already go by `POST`. API Gateway HTTP API cannot stream, but a Lambda Function URL with `RESPONSE_STREAM` can. The function runs for the life of the connection, so cost scales with connected attendees. |
| AppSync subscriptions | Managed fan-out with no connection table, at the price of a GraphQL layer bolted onto a REST API. |
| IoT Core over MQTT/WSS | Cheapest real pub-sub at scale, and the strangest fit. |
| Ably, Pusher, Momento | Ruled out by section 15: the page carries no third-party scripts. |

**The upgrade path, if 1s stops being enough.** Server-Sent Events on a Lambda
Function URL, **for the presenter only** — one connection, one streaming function,
no connection registry, no fan-out, and the audience keeps polling. Push arrives
where it is needed without any of the bookkeeping that made it unattractive.

## 6. The admin experience

`https://qna.dtcdev.click/admin`, behind Google sign-in.

- **Room list** — rooms where the signed-in user is owner or admin, grouped by
  state, with question and unanswered counts. "New room" opens a form covering the
  settings in section 3.3.
- **Room detail** — leads with the queue: the same question list as the public
  page plus per-question controls (mark answered, pin, delete, edit for
  typos), inside the first screenful on a phone. The header carries the two
  mid-session controls — presentation mode and copy link. Everything done once
  before an event — the share panel (public URL, QR downloads), settings, and
  people — sits in collapsed setup panels below the list.
- **People** — co-host invites: a link plus a passcode, created and revoked by
  the room admins.

Room admins can do everything to a room except delete it or change its owner; those
belong to the owner. Ownership can be transferred to another admin.

## 7. Presentation mode

`https://qna.dtcdev.click/admin/rooms/<room_id>/present` — admin only, and returns
403 to anyone else. This is the screen that gets projected, so it is a distinct
view rather than a fullscreen toggle on the admin page: no controls that could be
mis-clicked on a shared screen, no other rooms' names, no moderation queue.

Two states share one frame. The resting state is the **ranked list**: the top
questions as large cards, vote counts prominent, re-sorting live as votes land —
the audience votes because they can see what is winning. **Spotlight** blows a
single question up at a size readable from the back of the room, with its author
and score; the host enters it from the toolbar, which opens on whatever the room
has voted to the top, and returns to the list with Esc. A
join strip — a large QR code on the left, with the URL beside it — stays visible in
both states, so people who arrive late can join without the host interrupting
themselves. The QR is sized to be scanned from the back of a room, because it is
the entire on-ramp: if nobody can scan it, nobody asks anything. While the room has
no questions yet, the join card takes over the whole screen.

Clicking is the interaction model — every action is a visible control, nothing
is reachable only by keyboard:

- **On each card**: pin and mark answered, as always-visible icon buttons with
  accessible names. Hiding is moderation and stays in the room console, off the
  projected screen. Pinned shows as the pressed state of its own button and
  nowhere else — a second pin glyph beside the author said the same thing twice.
- **In the toolbar** (bottom of the frame): undo, spotlight (a toggle — in it
  says "All questions"), the full-screen QR overlay, the light/dark theme
  toggle (light is the projector default), and browser fullscreen. Leaving is
  the browser's back button, not a control that can be mis-clicked on a shared
  screen.
- Marking answered applies optimistically and offers **undo** both in the
  toolbar and in the confirmation cue — mis-taps are likelier with buttons than
  they were with keys.
- No spinners here, unlike the console. A pin lands pinned and an answered card
  leaves on the tap, with nothing disabled while the request is in flight: a
  stall on a projected screen is one the whole room watches the host sit
  through, over a delay none of them can do anything about. A refusal rolls the
  change back and says so in the cue.

Two conventional keys survive because they need no teaching: the arrow keys move
the selection (or walk the ranking in spotlight), and `Esc` closes the QR
overlay or leaves the spotlight. Everything else is a button.

The list refreshes on the polling loop; answered and deleted questions visibly
leave it, and rank changes animate so movement is legible. The spotlit question
never moves underneath the host — ranking applies again once they return to the
list.

## 8. The permanent link

`https://qna.dtcdev.click/live` always points at whatever room is open right now.
It redirects to the open room, lists them when several are open, and shows a
"nothing live right now" message when none are. `/` behaves identically.

This is the URL to print in a podcast description or a course syllabus and never
update again. A room that has expired or been closed drops out of `/live`
automatically, so nothing has to be tidied up after an event.

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
        ┌──────────────────┴──────────────────┐
        ▼                                     ▼
   PublicFunction                       AdminFunction
   /  /live  /health                    /admin/*
   /r/*  /assets/*                      /auth/*  (OIDC)
   /api/v1/*                            presentation mode
   read-write on the table              read-only on the table
        │                                     │
        └──────────────────┬──────────────────┘
                           ▼
                DynamoDB  table: dataqna
                   GSI1 · TTL · on-demand
                           │
                    CloudWatch alarms
```

Two functions, split by traffic profile rather than by the three-way split an
earlier draft of this document proposed. The participant path carries essentially
all of the load; the admin console carries almost none but must stay responsive
during an event, and it is the only place the OIDC client and the token exchange
live. Splitting the REST API off as a third function was dropped: the admin UI and
scripts call exactly the same routes, so it would have duplicated the whole
surface for no isolation that the other two do not already provide.

The honest limitation of two functions: `PublicFunction` verifies session cookies,
so it holds the same signing secret as `AdminFunction`. The boundary that does
hold is that no unauthenticated path can reach the Cognito client or exchange a
code, and that `AdminFunction` has read-only IAM on the table — every write goes
through the function whose authorization rules are exercised by the test suite.

Static assets ship inside the deployment package and are served by the public
function. No build step, no bundler, no CDN.

Region `eu-west-1`, matching the other services. The Cognito pool it authenticates
against lives in `us-east-1` and is not owned by this stack.

## 11. Data model

One DynamoDB table, `dataqna`, on-demand, TTL on `ttl`, point-in-time recovery on.

| Entity | PK | SK | GSI1PK | GSI1SK |
|--------|----|----|--------|--------|
| Room | `ROOM#<room_id>` | `META` | `STATE#<state>` | `<updated_at>` |
| Slug pointer | `SLUG#<slug>` | `META` | — | — |
| Question | `ROOM#<room_id>` | `Q#<question_id>` | — | — |
| Vote | `ROOM#<room_id>` | `V#<question_id>#<participant_id>` | — | — |
| Admin grant | `ROOM#<room_id>` | `ADMIN#<email>` | `USER#<email>` | `ROOM#<room_id>` |
| Co-host invite | `ROOM#<room_id>` | `COHOST#<invite_id>` | — | — |
| Co-host pointer | `COHOSTNAME#<room_id>#<name>` | `META` | — | — |
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

When a room is under active abuse, `deleted` removes individual questions and
closing the room stops submissions and votes outright while leaving it
readable. There is deliberately no finer switch — see section 3.3.

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
Retention is explicit per room and enforced by TTL.

## 16. Decided, and still open

Settled during the build:

- **Domain** is `qna.dtcdev.click`.
- **The permanent link** is `/live`, not a per-host `/@handle` (section 8).
- **Presentation advances manually.** Auto-advance to the top unanswered question
  is livelier but moves the screen under the host mid-sentence.
- **No review queue, no pause switches.** `moderation`, `questions_open`, and
  `voting_open` were built and then removed: three toggles nobody used in
  anger, and one of them let a host silently run a session where nobody could
  see anybody's questions. Open accepts everything; closed stops everything.
- **Co-host powers.** A session code runs the whole session — questions,
  settings, lifecycle, presentation — and only handing access on (invites,
  the published slug, deletion) stays with the signed-in owner.

Still open:

1. **Slido import.** Worth pulling the existing rooms' questions across before the
   subscription lapses, or is the archive not needed?
2. **Public room directory.** Rooms are currently unlisted and shared only by link,
   with `/live` as the one public entry point. A browsable index of open rooms is
   possible but is a different privacy posture.
3. **DataOps integration.** The API is in place and key-authenticated; what DataOps
   should actually do with it — pull questions after an event, create rooms from
   the course schedule, or both — is not specified yet.

## 17. Later, not now

Live polls and quizzes. Word clouds. Question categories or tags. Threaded replies.
Written answers stored alongside questions. Slack notification when a question
crosses a score threshold. AI-assisted duplicate detection and clustering, which is
the feature most likely to matter for a 200-person course room.
