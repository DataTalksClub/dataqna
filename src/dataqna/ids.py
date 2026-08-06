"""Identifier generation: ULIDs, join codes, and slugs."""

import os
import re
import time

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

# Join codes are read aloud and typed on a phone, so the alphabet drops every
# pair that is ambiguous in a sans-serif font or in speech: O/0, I/1/L, U/V.
_CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTWXYZ"

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")
SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,46}[a-z0-9]$")

RESERVED_SLUGS = frozenset(
    {
        "admin", "api", "auth", "assets", "health", "live", "r", "static",
        "login", "logout", "new", "present", "qr", "favicon.ico", "robots.txt",
    }
)


def _encode(value, length):
    out = []
    for _ in range(length):
        out.append(_CROCKFORD[value & 0x1F])
        value >>= 5
    return "".join(reversed(out))


def ulid():
    """A lexicographically sortable 26-character identifier."""
    millis = int(time.time() * 1000)
    return _encode(millis, 10) + _encode(int.from_bytes(os.urandom(10), "big"), 16)


def join_code(length=6):
    alphabet = _CODE_ALPHABET
    return "".join(alphabet[b % len(alphabet)] for b in os.urandom(length))


def slugify(text, fallback_length=8):
    slug = _SLUG_STRIP.sub("-", (text or "").strip().lower()).strip("-")[:48].strip("-")
    if len(slug) < 3 or not SLUG_PATTERN.match(slug):
        suffix = join_code(fallback_length).lower()
        slug = f"{slug}-{suffix}".strip("-") if slug else f"room-{suffix}"
    return slug[:48].strip("-")


def valid_slug(slug):
    return bool(slug) and bool(SLUG_PATTERN.match(slug)) and slug not in RESERVED_SLUGS
