from tamis_api.services import email as email_service
from tests.conftest import register


def test_register_login_me(client):
    u = register(client, "alice@example.org", "Alice")
    assert u["email"] == "alice@example.org" and u["plan"] == "free"
    assert client.get("/auth/me").json()["name"] == "Alice"
    assert client.post("/auth/register", json={"email": "alice@example.org", "password": "password123"}).status_code == 409
    assert client.post("/auth/login", json={"email": "alice@example.org", "password": "wrong-password"}).status_code == 401
    r = client.patch("/auth/me", json={"name": "Alice R.", "locale": "fr"})
    assert r.json()["name"] == "Alice R." and r.json()["locale"] == "fr"
    client.post("/auth/logout")
    assert client.get("/auth/me").status_code == 401


def test_magic_link(client):
    r = client.post("/auth/magic-link", json={"email": "magic@example.org", "locale": "fr"})
    assert r.status_code == 200
    link = r.json()["dev_link"]
    assert email_service.OUTBOX[-1]["to"] == "magic@example.org" and link in email_service.OUTBOX[-1]["text"]
    token = link.split("token=")[1]
    r = client.post("/auth/magic-link/verify", json={"token": token})
    assert r.status_code == 200 and r.json()["email_verified"] is True
    assert client.get("/auth/me").json()["email"] == "magic@example.org"
    assert client.post("/auth/magic-link/verify", json={"token": token}).status_code == 400   # single use


def test_provider_keys_and_usage(client):
    register(client, "keys@example.org")
    assert client.get("/auth/keys").json() == []
    r = client.put("/auth/keys/claude", json={"key": "sk-ant-1234567890abcdef"})
    assert r.status_code == 200 and r.json()["masked"] == "sk-a…cdef"
    assert client.put("/auth/keys/nope", json={"key": "sk-ant-1234567890abcdef"}).status_code == 400
    assert [k["provider"] for k in client.get("/auth/keys").json()] == ["claude"]
    usage = client.get("/auth/usage").json()
    assert usage["included_budget"] == 0 and usage["included_used"] == 0
    assert client.delete("/auth/keys/claude").status_code == 200
    assert client.get("/auth/keys").json() == []


def test_unauthenticated_is_rejected(client):
    assert client.get("/reviews").status_code == 401
    assert client.get("/health").json()["ok"] is True


def test_google_sign_in(client, monkeypatch):
    from urllib.parse import parse_qs, urlparse

    from tamis_api.config import get_settings
    from tamis_api.services import oauth

    s = get_settings()
    assert client.get("/auth/providers").json() == {"google": False}
    assert client.get("/auth/google/start").status_code == 404
    monkeypatch.setattr(s, "google_client_id", "cid.apps.googleusercontent.com")
    monkeypatch.setattr(s, "google_client_secret", "secret")
    assert client.get("/auth/providers").json() == {"google": True}

    r = client.get("/auth/google/start", params={"next": "/app/reviews/x", "locale": "fr"}, follow_redirects=False)
    assert r.status_code == 302
    url = urlparse(r.headers["location"])
    q = parse_qs(url.query)
    assert url.netloc == "accounts.google.com" and q["client_id"] == ["cid.apps.googleusercontent.com"]
    assert q["redirect_uri"] == ["http://localhost:8000/auth/google/callback"] and "openid" in q["scope"][0]
    state = q["state"][0]
    assert oauth.STATE_COOKIE in r.cookies

    # Wrong state -> back to sign-in with an error
    r = client.get("/auth/google/callback", params={"code": "abc", "state": "nope"}, follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"].endswith("/fr/sign-in?error=google")

    # A failed attempt clears the pending state: start again, then stub Google's side
    r = client.get("/auth/google/start", params={"next": "/app/reviews/x", "locale": "fr"}, follow_redirects=False)
    state = parse_qs(urlparse(r.headers["location"]).query)["state"][0]
    monkeypatch.setattr(oauth, "exchange_code", lambda code: {"id_token": "signed"})
    monkeypatch.setattr(oauth, "verify_id_token", lambda tok, nonce=None: {
        "sub": "g-123", "email": "Grace@Example.org", "email_verified": True, "name": "Grace Hopper"})
    r = client.get("/auth/google/callback", params={"code": "abc", "state": state}, follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == "http://web.test/fr/app/reviews/x"
    me = client.get("/auth/me").json()
    assert me["email"] == "grace@example.org" and me["name"] == "Grace Hopper" and me["email_verified"]
    assert me["locale"] == "fr"

    # Same Google subject again -> same account; unsafe next -> /app
    client.post("/auth/logout")
    r = client.get("/auth/google/start", params={"next": "//evil.example"}, follow_redirects=False)
    state = parse_qs(urlparse(r.headers["location"]).query)["state"][0]
    r = client.get("/auth/google/callback", params={"code": "abc", "state": state}, follow_redirects=False)
    assert r.headers["location"] == "http://web.test/app"
    assert client.get("/auth/me").json()["id"] == me["id"]
