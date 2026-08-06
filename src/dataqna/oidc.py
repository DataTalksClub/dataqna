"""Authorization code + PKCE against the shared Cognito login.

Follows the consumer contract in aws-infra/sandbox/auth: unpredictable state and
nonce, an S256 challenge, and full validation of the returned ID token before a
service session is created. The Cognito session is not reused as our session.
"""

import base64
import hashlib
import json
import os
import time
import urllib.parse
import urllib.request

import jwt

from . import config, security

_jwk_client = None


def _b64(raw):
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def configured():
    return all([config.AUTH_BASE_URL, config.AUTH_CLIENT_ID, config.AUTH_ISSUER, config.AUTH_JWKS_URL])


def begin(next_path="/admin"):
    """Return (authorize_url, state_token) for the login redirect."""
    verifier = _b64(os.urandom(48))
    challenge = _b64(hashlib.sha256(verifier.encode()).digest())
    state = _b64(os.urandom(24))
    nonce = _b64(os.urandom(24))

    query = urllib.parse.urlencode(
        {
            "client_id": config.AUTH_CLIENT_ID,
            "response_type": "code",
            "scope": "openid email profile",
            "redirect_uri": config.AUTH_CALLBACK_URL,
            "state": state,
            "nonce": nonce,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    token = security.sign(
        {
            "kind": "oidc",
            "state": state,
            "nonce": nonce,
            "verifier": verifier,
            "next": next_path if next_path.startswith("/") else "/admin",
            "exp": int(time.time()) + config.OIDC_TTL_SECONDS,
        }
    )
    return f"{config.AUTH_BASE_URL}/oauth2/authorize?{query}", token


def _exchange(code, verifier):
    payload = urllib.parse.urlencode(
        {
            "grant_type": "authorization_code",
            "client_id": config.AUTH_CLIENT_ID,
            "code": code,
            "redirect_uri": config.AUTH_CALLBACK_URL,
            "code_verifier": verifier,
        }
    ).encode()
    request = urllib.request.Request(
        f"{config.AUTH_BASE_URL}/oauth2/token",
        data=payload,
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(request, timeout=10) as handle:
        return json.loads(handle.read().decode())


def _claims(id_token):
    global _jwk_client
    if _jwk_client is None:
        _jwk_client = jwt.PyJWKClient(config.AUTH_JWKS_URL)
    key = _jwk_client.get_signing_key_from_jwt(id_token)
    return jwt.decode(
        id_token,
        key.key,
        algorithms=["RS256"],
        audience=config.AUTH_CLIENT_ID,
        issuer=config.AUTH_ISSUER,
        options={"require": ["exp", "iat", "iss", "aud", "sub"]},
    )


def complete(pending, code, state):
    """Validate the callback and return the signed-in email, or None."""
    if not pending or not code:
        return None, None
    if not security.constant_time_equals(state, pending.get("state", "")):
        return None, None
    try:
        tokens = _exchange(code, pending["verifier"])
        claims = _claims(tokens["id_token"])
    except Exception:
        return None, None
    if not security.constant_time_equals(str(claims.get("nonce", "")), pending.get("nonce", "")):
        return None, None
    email = claims.get("email")
    if not isinstance(email, str) or claims.get("email_verified") is not True:
        return None, None
    return email.lower(), pending.get("next", "/admin")


def logout_url():
    query = urllib.parse.urlencode(
        {"client_id": config.AUTH_CLIENT_ID, "logout_uri": f"{config.SITE_URL}/"}
    )
    return f"{config.AUTH_BASE_URL}/logout?{query}"
