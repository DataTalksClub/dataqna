# DataQnA

Audience Q&A for live events, podcasts, and courses. A self-hosted replacement for
Slido, running serverless on AWS.

Attendees join a room by link or QR code without signing in, ask questions, and
upvote each other's. The host answers the top-ranked ones from a projector-ready
presentation view. Every room can be created and driven through a REST API, so
recurring events are scripted rather than clicked.

**Status: specification only.** No implementation yet.

- [Specification](docs/specification.md) — product behaviour, architecture, data model
- [API reference](docs/api.md) — endpoints, payloads, authentication

## Shape of it

```text
participants ──► https://qna.dtcdev.click/r/llm-zoomcamp
                        │
                 API Gateway (HTTP API)
                        │
                 ┌──────┴──────┐
                 │  Lambda     │  public app · admin app · REST API
                 └──────┬──────┘
                        │
                   DynamoDB (single table, per-room partitions)

admins ──► Google sign-in via https://auth.dtcdev.click (@datatalks.club)
scripts ──► REST API with a bearer key
```

Rooms live anywhere from one hour (a podcast recording) to four months (a course
cohort). Short-lived rooms expire on a timer; long-lived rooms stay open until
closed.

## Related repositories

- [DataTalksClub/auth](https://github.com/DataTalksClub/auth) — shared Cognito login
- [DataTalksClub/aws-infra](https://github.com/DataTalksClub/aws-infra) — certificates, DNS, deploy roles
- [DataTalksClub/dapier](https://github.com/DataTalksClub/dapier) — the SAM/Lambda project this one is modelled on
