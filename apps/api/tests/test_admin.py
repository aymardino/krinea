"""The operator dashboard (/admin) and the sign-up notification."""
from krinea_api.config import get_settings
from krinea_api.services.email import OUTBOX


def _register(client, email, name="", password="password123"):
    r = client.post("/auth/register", json={"email": email, "password": password, "name": name})
    if r.status_code == 409:
        r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code in (200, 201), r.text
    return r.json()


def test_overview_is_for_administrators_only(client, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "admin_emails", frozenset({"operator@example.org"}))
    monkeypatch.setattr(s, "notify_signups_to", "")
    me = _register(client, "someone@example.org", "Someone")
    assert me["is_admin"] is False
    assert client.get("/admin/overview").status_code == 403

    me = _register(client, "operator@example.org", "Owner")
    assert me["is_admin"] is True
    r = client.get("/admin/overview")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["totals"]["users"] >= 2 and data["totals"]["signups_7d"] >= 2
    assert len(data["series"]["days"]) == 30 == len(data["series"]["signups"]) == len(data["series"]["active"])
    assert sum(data["series"]["signups"]) >= 2 and data["series"]["active"][-1] >= 1
    emails = {u["email"] for u in data["recent_users"]}
    assert {"someone@example.org", "operator@example.org"} <= emails
    owner = next(u for u in data["recent_users"] if u["email"] == "operator@example.org")
    assert owner["method"] == "password" and owner["reviews"] == 0


def test_sign_up_sends_a_notice_to_the_operator(client, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "admin_emails", frozenset({"operator@example.org"}))
    monkeypatch.setattr(s, "notify_signups_to", "operator@example.org")
    before = len(OUTBOX)
    _register(client, "newcomer@example.org", "New Comer")
    notices = [m for m in OUTBOX[before:] if "New account" in m.get("subject", "")]
    assert len(notices) == 1
    assert notices[0]["to"] == "operator@example.org"
    assert "newcomer@example.org" in notices[0]["text"] and "password" in notices[0]["text"]

    # Signing in again is not a sign-up: no second notice.
    before = len(OUTBOX)
    client.post("/auth/logout")
    assert client.post("/auth/login", json={"email": "newcomer@example.org", "password": "password123"}).status_code == 200
    assert not [m for m in OUTBOX[before:] if "New account" in m.get("subject", "")]
