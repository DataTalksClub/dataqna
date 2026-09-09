"""Runtime configuration, read once per container from the environment."""

import os


def _clean(name, default=""):
    return os.environ.get(name, default).strip()


TABLE_NAME = _clean("TABLE_NAME", "dataqna")
SITE_URL = _clean("SITE_URL", "https://qna.dtcdev.click").rstrip("/")

AUTH_BASE_URL = _clean("AUTH_BASE_URL", "https://auth.dtcdev.click").rstrip("/")
AUTH_CLIENT_ID = _clean("AUTH_CLIENT_ID")
AUTH_ISSUER = _clean("AUTH_ISSUER").rstrip("/")
AUTH_JWKS_URL = _clean("AUTH_JWKS_URL") or (
    f"{AUTH_ISSUER}/.well-known/jwks.json" if AUTH_ISSUER else ""
)
AUTH_CALLBACK_URL = _clean("AUTH_CALLBACK_URL") or f"{SITE_URL}/auth/callback"

SECRET_ARN = _clean("SESSION_SECRET_ARN")

SESSION_COOKIE = "dq_session"
OIDC_COOKIE = "dq_oidc"
PARTICIPANT_COOKIE = "dq_p"
COHOST_COOKIE = "dq_cohost"

SESSION_TTL_SECONDS = 12 * 60 * 60
# How long a redeemed invite keeps its cookie. The invite itself does not
# expire — it lasts as long as the room, and revoking is how it ends — but a
# signed cookie has to say when it stops being valid. Redeeming again is free.
COHOST_TTL_SECONDS = 30 * 24 * 60 * 60
PARTICIPANT_TTL_SECONDS = 400 * 24 * 60 * 60
OIDC_TTL_SECONDS = 600

# Bootstrap owners: admins of every room, so a freshly deployed stack is
# reachable before any grant exists. Comma-separated, and deliberately short —
# everyone else gets access one room at a time.
ROOT_ADMINS = frozenset(
    part.strip().lower()
    for part in _clean("ROOT_ADMIN", "alexey@datatalks.club").split(",")
    if part.strip()
)

# A question has to read whole on a projected card, and a wall of text asks
# the host to edit it live. The card wraps its text at 78 characters — the
# 78ch the stylesheet measures it at — so a question is held to three of
# those lines: 234 characters, and no more than three lines however they are
# broken. The limit lives at submission and edit, never in rendering, so
# every question asked before the cap keeps the text it was asked with and
# still fills its card. A product constant, not a room setting: the length
# of a good question does not vary by session.
MAX_QUESTION_LINES = 3
QUESTION_LINE_WIDTH = 78
MAX_QUESTION_LENGTH = MAX_QUESTION_LINES * QUESTION_LINE_WIDTH
MAX_NAME_LENGTH = 60

# An archived session is held this many days as an undo window and then
# deleted: a filing nobody came back for is clutter nobody wanted, and the
# alternative is a list of dead sessions that grows forever. Reopening
# cancels the clock.
ARCHIVE_DELETE_DAYS = 7
