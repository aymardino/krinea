"""Public URLs of the deployment (links in e-mails, OAuth redirects).

The browser talks to the API through the web app's `/api` proxy (decision D-23), so the
API often does not know its public address. Explicit BASE_URL / API_URL settings win;
otherwise the proxy tells us the origin it was reached on (`X-Tamis-Origin`), which is
trusted only when the request also carries the shared secret (`X-Tamis-Proxy-Key`).
"""
from __future__ import annotations

import hmac

from fastapi import Request

from tamis_api.config import get_settings

ORIGIN_HEADER = "x-tamis-origin"
KEY_HEADER = "x-tamis-proxy-key"


def proxied_origin(request: Request | None) -> str | None:
    if request is None:
        return None
    origin = request.headers.get(ORIGIN_HEADER, "").strip().rstrip("/")
    key = request.headers.get(KEY_HEADER, "")
    if not origin.startswith(("http://", "https://")) or "/" in origin[8:] or not key:
        return None
    if not hmac.compare_digest(key.encode(), get_settings().secret_key.encode()):
        return None
    return origin


def public_base_url(request: Request | None = None) -> str:
    """Where the web app is served, for links sent to people."""
    s = get_settings()
    if s.base_url_explicit:
        return s.base_url
    return proxied_origin(request) or s.base_url


def public_api_url(request: Request | None = None) -> str:
    """Where browsers reach the API (the proxy path of the web app by default)."""
    s = get_settings()
    if s.api_url_explicit:
        return s.api_url
    origin = proxied_origin(request)
    return f"{origin}/api" if origin else s.api_url
