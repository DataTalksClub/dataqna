# DataQnA

Audience Q&A for live events, podcasts, and courses. A self-hosted replacement for
Slido, running serverless on AWS.

Attendees join a room by link or QR code without signing in, ask questions, and
upvote each other's. The host answers the top-ranked ones from a projector-ready
presentation view. Every room can be created and driven through a REST API, so
recurring events are scripted rather than clicked.

**Live at [qna.dtcdev.click](https://qna.dtcdev.click).**

- [Specification](docs/specification.md) — product behaviour, architecture, data model
- [API reference](docs/api.md) — endpoints, payloads, authentication

## Shape of it

```text
participants ──► https://qna.dtcdev.click/r/llm-zoomcamp
                        │
                 API Gateway (HTTP API)
                        │
                 ┌──────┴──────┐
                 │  2 Lambdas  │  public + API · admin console + OIDC
                 └──────┬──────┘
                        │
                   DynamoDB (single table, one partition per room)

admins ──► Google sign-in via https://auth.dtcdev.click
scripts ──► REST API with a bearer key
```

Rooms live anywhere from one hour (a podcast recording) to four months (a course
cohort). `expires_at` closes a room on a timer without deleting anything;
`retention_days` is what eventually removes the data.

`https://qna.dtcdev.click/live` always points at whatever room is open right now —
the URL to put in a podcast description once and never update.

## Scripting an event

```bash
curl -X POST https://qna.dtcdev.click/api/v1/rooms \
  -H "authorization: Bearer $DATAQNA_KEY" \
  -H 'content-type: application/json' \
  -d '{"title":"Podcast #142","slug":"podcast-142","state":"open",
       "expires_at":"2026-08-13T21:00:00Z","idempotency_key":"podcast-142"}'
```

The response carries the public URL and a QR code URL. `idempotency_key` makes the
call safe to re-run, so a per-episode script needs no bookkeeping.

Create API keys in the admin console at `/admin`. Keys carry the permissions of the
admin who created them and can be scoped to a single room.

## Development

```bash
make install   # uv sync — runtime and dev dependencies
make test      # uv run pytest; DynamoDB mocked with moto
make validate  # sam validate --lint
make build
make deploy    # sandbox, eu-west-1
make verify    # 30 checks against the live site; needs DATAQNA_KEY
```

Dependencies live in `pyproject.toml` — runtime under `[project]`, test tooling
under the `dev` group. `uv run pytest` needs no exported environment and no
`--with` flags: `tests/conftest.py` supplies every variable the app reads.
`src/requirements.txt` is what SAM installs into the Lambda, and a test fails if
it drifts from the project's runtime list.

`make verify` creates a throwaway session, exercises the participant, co-host,
and admin paths against the deployed site, and purges it. CI runs it after every
deploy, so a deploy that returns `CREATE_COMPLETE` but serves a broken site fails
the workflow.

## Access

Admin sign-in goes through the shared DataTalks.Club Cognito pool, restricted to
verified `@datatalks.club` Google accounts.

Guest hosts get a **co-host code** instead of an account: three groups of four
characters that grant moderation and presentation rights for one room and nothing
else. No account, no email address, no identity in the shared pool. Create one from
the Co-hosts panel on any room; revoking it takes effect on the next request.

Authorization — admin grants and co-host codes alike — is re-read from DynamoDB on
every request, so removing access is immediate rather than effective at next login.

## Related repositories

- [DataTalksClub/auth](https://github.com/DataTalksClub/auth) — shared Cognito login
- [DataTalksClub/aws-infra](https://github.com/DataTalksClub/aws-infra) — certificate, deploy role, `sandbox/dataqna`
- [DataTalksClub/dapier](https://github.com/DataTalksClub/dapier) — the SAM/Lambda project this one is modelled on
