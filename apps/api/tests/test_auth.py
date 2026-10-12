import re

from krinea_api.services import email as email_service
from tests.conftest import register


def last_link(to: str) -> str:
    """The sign-in link of the last message sent to `to` (console provider outbox)."""
    msg = next(m for m in reversed(email_service.OUTBOX) if m["to"] == to)
    return re.search(r"https?://\S+", msg["text"]).group(0)


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
    assert "dev_link" not in r.json()                  # BASE_URL is not a local address
    link = last_link("magic@example.org")
    assert link.startswith("http://web.test/auth/magic?token=")
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

    from krinea_api.config import get_settings
    from krinea_api.services import oauth

    s = get_settings()
    assert client.get("/auth/providers").json() == {"google": False, "email": True}
    assert client.get("/auth/google/start").status_code == 404
    monkeypatch.setattr(s, "google_client_id", "cid.apps.googleusercontent.com")
    monkeypatch.setattr(s, "google_client_secret", "secret")
    assert client.get("/auth/providers").json()["google"] is True

    r = client.get("/auth/google/start", params={"next": "/app/reviews/x", "locale": "fr"}, follow_redirects=False)
    assert r.status_code == 302
    url = urlparse(r.headers["location"])
    q = parse_qs(url.query)
    assert url.netloc == "accounts.google.com" and q["client_id"] == ["cid.apps.googleusercontent.com"]
    assert q["redirect_uri"] == ["http://web.test/api/auth/google/callback"] and "openid" in q["scope"][0]
    state = q["state"][0]
    assert oauth.STATE_COOKIE in r.cookies

    # Wrong state -> back to sign-in with an error
    r = client.get("/auth/google/callback", params={"code": "abc", "state": "nope"}, follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"].endswith("/fr/sign-in?error=google")

    # A failed attempt clears the pending state: start again, then stub Google's side
    r = client.get("/auth/google/start", params={"next": "/app/reviews/x", "locale": "fr"}, follow_redirects=False)
    state = parse_qs(urlparse(r.headers["location"]).query)["state"][0]
    monkeypatch.setattr(oauth, "exchange_code", lambda code, request=None: {"id_token": "signed"})
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


def test_public_urls_from_proxy(client, monkeypatch):
    from urllib.parse import parse_qs, urlparse
    """Without explicit BASE_URL, links use the origin reported by the web proxy, but only
    when the request carries the shared secret (D-23)."""
    from krinea_api.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "base_url_explicit", False)
    monkeypatch.setattr(s, "api_url_explicit", False)
    monkeypatch.setattr(s, "google_client_id", "cid")
    monkeypatch.setattr(s, "google_client_secret", "secret")
    proxied = {"X-Krinea-Origin": "https://krinea-web.onrender.com", "X-Krinea-Proxy-Key": "test-secret"}

    r = client.get("/auth/google/start", headers=proxied, follow_redirects=False)
    q = parse_qs(urlparse(r.headers["location"]).query)
    assert q["redirect_uri"] == ["https://krinea-web.onrender.com/api/auth/google/callback"]
    r = client.post("/auth/magic-link", json={"email": "p@example.org"}, headers=proxied)
    assert r.status_code == 200 and "dev_link" not in r.json()        # a public origin: never echoed
    assert last_link("p@example.org").startswith("https://krinea-web.onrender.com/auth/magic?token=")

    # Wrong or missing key, or a non-origin value: the configured BASE_URL is used instead
    for bad in ({**proxied, "X-Krinea-Proxy-Key": "nope"}, {"X-Krinea-Origin": "https://evil.example"},
                {**proxied, "X-Krinea-Origin": "https://evil.example/path"}):
        r = client.post("/auth/magic-link", json={"email": "p@example.org"}, headers=bad)
        assert r.status_code == 200 and "dev_link" not in r.json()
        assert last_link("p@example.org").startswith("http://web.test/auth/magic?token=")


def test_dev_link_only_on_a_local_base_url(client, monkeypatch):
    """The link is echoed in the response only in debug mode with a localhost BASE_URL."""
    from krinea_api.config import get_settings

    s = get_settings()
    for base in ("http://localhost:3000", "http://127.0.0.1:8000"):
        monkeypatch.setattr(s, "base_url", base)
        r = client.post("/auth/magic-link", json={"email": "dev@example.org"})
        assert r.json()["dev_link"] == last_link("dev@example.org")
        assert r.json()["dev_link"].startswith(f"{base}/auth/magic?token=")
    for base in ("http://web.test", "https://krinea.org", "http://localhost.evil.example"):
        monkeypatch.setattr(s, "base_url", base)
        r = client.post("/auth/magic-link", json={"email": "dev@example.org"})
        assert r.status_code == 200 and "dev_link" not in r.json(), base
    # Production (no debug): never, even on localhost
    monkeypatch.setattr(s, "base_url", "http://localhost:3000")
    monkeypatch.setattr(s, "debug", False)
    monkeypatch.setattr(email_service, "send_magic_link", lambda to, url, locale="en": None)
    r = client.post("/auth/magic-link", json={"email": "dev@example.org"})
    assert r.status_code == 200 and "dev_link" not in r.json()


def test_magic_link_evicts_whoever_registered_the_address_first(client, client2):
    """Account pre-hijacking: an attacker registers the victim's address with a password and
    keeps a session open. When the victim proves the address with a magic link, the
    attacker's password and session stop working."""
    attacker, victim = client2, client
    register(attacker, "victim@example.org", "Mallory", password="attacker-password")
    assert attacker.get("/auth/me").json()["email_verified"] is False

    victim.post("/auth/magic-link", json={"email": "victim@example.org"})
    token = last_link("victim@example.org").split("token=")[1]
    r = victim.post("/auth/magic-link/verify", json={"token": token})
    assert r.status_code == 200 and r.json()["email_verified"] is True

    assert attacker.get("/auth/me").status_code == 401                 # old session closed
    r = attacker.post("/auth/login", json={"email": "victim@example.org", "password": "attacker-password"})
    assert r.status_code == 401                                          # password cleared
    assert victim.get("/auth/me").json()["email"] == "victim@example.org"

    # Once verified, the owner signing in on a second device leaves the first session alone
    second_device = client2
    second_device.post("/auth/magic-link", json={"email": "victim@example.org"})
    token = last_link("victim@example.org").split("token=")[1]
    assert second_device.post("/auth/magic-link/verify", json={"token": token}).status_code == 200
    assert victim.get("/auth/me").status_code == 200
    # ...and a password the verified owner sets keeps working
    assert victim.patch("/auth/me", json={"password": "victim-password"}).status_code == 200
    victim.post("/auth/magic-link", json={"email": "victim@example.org"})
    token = last_link("victim@example.org").split("token=")[1]
    assert victim.post("/auth/magic-link/verify", json={"token": token}).status_code == 200
    r = victim.post("/auth/login", json={"email": "victim@example.org", "password": "victim-password"})
    assert r.status_code == 200


def test_google_sign_in_evicts_whoever_registered_the_address_first(client, client2, monkeypatch):
    from urllib.parse import parse_qs, urlparse

    from krinea_api.config import get_settings
    from krinea_api.services import oauth

    attacker, victim = client2, client
    register(attacker, "gvictim@example.org", password="attacker-password")
    s = get_settings()
    monkeypatch.setattr(s, "google_client_id", "cid")
    monkeypatch.setattr(s, "google_client_secret", "secret")
    monkeypatch.setattr(oauth, "exchange_code", lambda code, request=None: {"id_token": "signed"})
    monkeypatch.setattr(oauth, "verify_id_token", lambda tok, nonce=None: {
        "sub": "g-victim", "email": "gvictim@example.org", "email_verified": True, "name": "Victim"})
    r = victim.get("/auth/google/start", follow_redirects=False)
    state = parse_qs(urlparse(r.headers["location"]).query)["state"][0]
    r = victim.get("/auth/google/callback", params={"code": "abc", "state": state}, follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == "http://web.test/app"
    assert victim.get("/auth/me").json()["email_verified"] is True

    assert attacker.get("/auth/me").status_code == 401
    r = attacker.post("/auth/login", json={"email": "gvictim@example.org", "password": "attacker-password"})
    assert r.status_code == 401


def test_smtp_provider(client, monkeypatch):
    """The SMTP provider logs in, sends the message, and a failure becomes a 502."""
    import smtplib
    from krinea_api.config import get_settings
    from krinea_api.services import email as email_service

    sent = []

    class FakeSMTP:
        def __init__(self, host, port, timeout=0): sent.append(("connect", host, port))
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self): sent.append(("starttls",))
        def login(self, user, pw): sent.append(("login", user))
        def send_message(self, msg): sent.append(("send", msg["To"], msg["Subject"]))

    s = get_settings()
    monkeypatch.setattr(s, "email_provider", "smtp")
    monkeypatch.setattr(s, "smtp_host", "smtp.example.org")
    monkeypatch.setattr(s, "smtp_user", "me@example.org")
    monkeypatch.setattr(s, "smtp_password", "secret")
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    assert client.post("/auth/magic-link", json={"email": "smtp@example.org"}).status_code == 200
    assert sent[0] == ("connect", "smtp.example.org", 587) and ("starttls",) in sent and ("login", "me@example.org") in sent
    assert sent[-1][0] == "send" and sent[-1][1] == "smtp@example.org"

    class BrokenSMTP(FakeSMTP):
        def login(self, user, pw): raise smtplib.SMTPAuthenticationError(535, b"bad credentials")

    monkeypatch.setattr(smtplib, "SMTP", BrokenSMTP)
    r = client.post("/auth/magic-link", json={"email": "smtp@example.org"})
    assert r.status_code == 502 and "SMTP" in r.json()["detail"]
    assert email_service.EmailError


def test_email_misconfiguration_is_visible(client, monkeypatch):
    """EMAIL_PROVIDER=resend without a key must fail loudly, not pretend to send."""
    from krinea_api.config import get_settings
    s = get_settings()
    monkeypatch.setattr(s, "email_provider", "resend")
    monkeypatch.setattr(s, "resend_api_key", "")
    assert client.get("/auth/providers").json()["email"] is False
    r = client.post("/auth/magic-link", json={"email": "p@example.org"})
    assert r.status_code == 502 and "not configured" in r.json()["detail"]
