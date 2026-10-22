"""Cookie-free audience counts of the public pages."""
from krinea_api.config import get_settings

INTERNAL = {"x-krinea-internal": "1", "x-krinea-proxy-key": "test-secret"}
BROWSER = "Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0"


def _view(client, **over):
    body = {"path": "/pricing", "lang": "fr", "referrer": "https://www.google.com/", "ua": BROWSER, "ip": "203.0.113.9"}
    body.update(over)
    return client.post("/stats/view", json=body, headers=INTERNAL)


def test_views_need_the_internal_headers(client):
    assert client.post("/stats/view", json={"path": "/", "ua": BROWSER}).status_code == 403
    bad = {"x-krinea-internal": "1", "x-krinea-proxy-key": "wrong"}
    assert client.post("/stats/view", json={"path": "/", "ua": BROWSER}, headers=bad).status_code == 403


def test_views_are_counted_without_personal_data(client, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "admin_emails", frozenset({"operator@example.org"}))
    monkeypatch.setattr(s, "notify_signups_to", "")
    assert _view(client).status_code == 204
    assert _view(client, path="/pricing?utm=x", ip="203.0.113.10").status_code == 204    # a second visitor
    assert _view(client, referrer="http://web.test/en").status_code == 204               # from our own site: direct
    assert _view(client, ua="Mozilla/5.0 (compatible; Googlebot/2.1)").status_code == 204  # crawlers are ignored
    assert _view(client, path="/app/reviews").status_code == 204                         # not a public page
    assert _view(client, ua="").status_code == 204                                       # no browser signature

    r = client.post("/auth/register", json={"email": "operator@example.org", "password": "password123", "name": "Op"})
    if r.status_code == 409:
        assert client.post("/auth/login", json={"email": "operator@example.org", "password": "password123"}).status_code == 200
    a = client.get("/admin/overview").json()["audience"]
    assert a["views_30d"] == 3 and a["views_7d"] == 3
    assert a["visitors_30d"] == 2 and a["visitors_7d"] == 2
    assert a["series"]["views"][-1] == 3 and a["series"]["visitors"][-1] == 2 and len(a["series"]["views"]) == 30
    assert a["pages"] == [{"path": "/pricing", "views": 3}]
    assert {row["host"]: row["views"] for row in a["referrers"]} == {"google.com": 2, "": 1}


def test_counting_can_be_switched_off(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "audience_stats", False)
    assert _view(client, path="/about", ip="203.0.113.11").status_code == 204
    monkeypatch.setattr(get_settings(), "audience_stats", True)
    monkeypatch.setattr(get_settings(), "admin_emails", frozenset({"operator@example.org"}))
    client.post("/auth/login", json={"email": "operator@example.org", "password": "password123"})
    a = client.get("/admin/overview").json()["audience"]
    assert all(p["path"] != "/about" for p in a["pages"])
