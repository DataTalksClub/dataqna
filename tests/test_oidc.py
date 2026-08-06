"""The sign-in callback.

Domain and email verification are enforced by the shared pool's pre-sign-up
trigger, not here; this service validates the token and the session.
"""

import pytest

from dataqna import oidc, security


def pending(**overrides):
    payload = {"state": "s-value", "nonce": "n-value", "verifier": "v", "next": "/admin"}
    payload.update(overrides)
    return payload


@pytest.mark.parametrize("claims", [
    {"email": "Alexey@DataTalks.Club", "email_verified": "true", "nonce": "n-value"},
    {"email": "Alexey@DataTalks.Club", "email_verified": "false", "nonce": "n-value"},
    {"email": "Alexey@DataTalks.Club", "email_verified": None, "nonce": "n-value"},
    {"email": "Alexey@DataTalks.Club", "nonce": "n-value"},
])
def test_the_pool_trigger_owns_verification_so_any_flag_signs_in(monkeypatch, claims):
    """The pre-sign-up trigger already requires a verified @datatalks.club
    address on every Google authentication, so the claim decides nothing here."""
    monkeypatch.setattr(oidc, "_exchange", lambda code, verifier: {"id_token": "token"})
    monkeypatch.setattr(oidc, "_claims", lambda token: claims)
    email, next_path = oidc.complete(pending(), "code", "s-value")
    assert email == "alexey@datatalks.club"
    assert next_path == "/admin"


@pytest.mark.parametrize("claims", [
    {"email_verified": "true", "nonce": "n-value"},
    {"email": "", "email_verified": "true", "nonce": "n-value"},
])
def test_a_token_without_an_email_is_refused(monkeypatch, claims):
    monkeypatch.setattr(oidc, "_exchange", lambda code, verifier: {"id_token": "token"})
    monkeypatch.setattr(oidc, "_claims", lambda token: claims)
    assert oidc.complete(pending(), "code", "s-value") == (None, None)


def test_state_mismatch_is_refused(monkeypatch):
    monkeypatch.setattr(oidc, "_exchange", lambda code, verifier: {"id_token": "token"})
    monkeypatch.setattr(oidc, "_claims", lambda token: {
        "email": "a@datatalks.club", "email_verified": True, "nonce": "n-value"
    })
    assert oidc.complete(pending(), "code", "wrong-state") == (None, None)


def test_nonce_mismatch_is_refused(monkeypatch):
    monkeypatch.setattr(oidc, "_exchange", lambda code, verifier: {"id_token": "token"})
    monkeypatch.setattr(oidc, "_claims", lambda token: {
        "email": "a@datatalks.club", "email_verified": True, "nonce": "replayed"
    })
    assert oidc.complete(pending(), "code", "s-value") == (None, None)


def test_missing_pending_state_is_refused():
    assert oidc.complete(None, "code", "s-value") == (None, None)


def test_a_failed_token_exchange_is_refused(monkeypatch):
    def boom(code, verifier):
        raise RuntimeError("network")

    monkeypatch.setattr(oidc, "_exchange", boom)
    assert oidc.complete(pending(), "code", "s-value") == (None, None)


@pytest.mark.parametrize(
    "hostile",
    ["https://evil.example/steal", "//evil.example/steal", "/\\evil.example", "", None],
)
def test_next_path_cannot_leave_the_site(hostile):
    assert oidc.safe_next(hostile) == "/admin"


@pytest.mark.parametrize("path", ["/admin", "/admin/rooms/01K3/present"])
def test_same_site_next_paths_survive(path):
    assert oidc.safe_next(path) == path


def test_begin_sanitizes_the_next_path():
    _, token = oidc.begin("//evil.example/steal")
    assert security.verify(token, kind="oidc")["next"] == "/admin"
