"""Sign in with Google (OpenID Connect, authorization-code flow).

    /auth/google/start    -> redirect to Google with a signed state cookie
    /auth/google/callback -> exchange the code, verify the ID token, sign the user in

The ID token is verified locally against Google's published keys (RS256,
audience = our client id, issuer = accounts.google.com, nonce = ours).
"""
from __future__ import annotations

import urllib.parse

import httpx
import jwt
from itsdangerous import BadSignature, URLSafeTimedSerializer

from fastapi import Request

from krinea_api.config import get_settings
from krinea_api.urls import public_api_url

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = ("https://accounts.google.com", "accounts.google.com")
STATE_COOKIE = "krinea_oauth"
STATE_MAX_AGE = 600


class OAuthError(Exception):
    pass


def enabled() -> bool:
    s = get_settings()
    return bool(s.google_client_id and s.google_client_secret)


def redirect_uri(request: Request | None = None) -> str:
    return f"{public_api_url(request)}/auth/google/callback"


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().secret_key, salt="oauth-state")


def sign_state(payload: dict) -> str:
    return _serializer().dumps(payload)


def load_state(token: str) -> dict:
    try:
        return _serializer().loads(token, max_age=STATE_MAX_AGE)
    except BadSignature as e:          # covers expiry too (SignatureExpired is a subclass)
        raise OAuthError("The sign-in attempt expired or was tampered with") from e


def authorization_url(state: str, nonce: str, request: Request | None = None) -> str:
    params = {
        "client_id": get_settings().google_client_id,
        "redirect_uri": redirect_uri(request),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
        "access_type": "online",
        "prompt": "select_account",
    }
    return GOOGLE_AUTH_URL + "?" + urllib.parse.urlencode(params)


def exchange_code(code: str, request: Request | None = None) -> dict:
    """Authorization code -> token response ({id_token, access_token, ...})."""
    s = get_settings()
    r = httpx.post(GOOGLE_TOKEN_URL, timeout=20, data={
        "code": code, "client_id": s.google_client_id, "client_secret": s.google_client_secret,
        "redirect_uri": redirect_uri(request), "grant_type": "authorization_code"})
    if r.status_code != 200:
        raise OAuthError(f"Google did not accept the code ({r.status_code})")
    return r.json()


def verify_id_token(id_token: str, nonce: str | None = None) -> dict:
    """Signature, audience, issuer, expiry and nonce checks. Returns the claims."""
    try:
        key = jwt.PyJWKClient(GOOGLE_JWKS_URL, cache_keys=True).get_signing_key_from_jwt(id_token).key
        claims = jwt.decode(id_token, key, algorithms=["RS256"], audience=get_settings().google_client_id,
                            issuer=list(GOOGLE_ISSUERS))
    except jwt.PyJWTError as e:
        raise OAuthError(f"Invalid Google token: {e}") from e
    if nonce and claims.get("nonce") != nonce:
        raise OAuthError("Nonce mismatch")
    if not claims.get("email") or not claims.get("email_verified", False):
        raise OAuthError("Google did not return a verified e-mail address")
    return claims


def safe_next(path: str | None) -> str:
    """Only relative paths inside the web app are allowed as a post-login target."""
    p = (path or "/app").strip()
    if not p.startswith("/") or p.startswith("//") or "\\" in p:
        return "/app"
    return p
