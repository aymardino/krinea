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
