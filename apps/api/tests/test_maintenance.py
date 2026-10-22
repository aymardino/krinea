"""The worker's housekeeping: old sign-in tokens and expired sessions are purged."""
import datetime as dt

from sqlalchemy import select

from krinea_api import models
from krinea_api.db import session_factory
from krinea_api.security import new_token, token_hash
from krinea_api.services import maintenance


def _token(db, email: str, created: dt.datetime, expires: dt.datetime) -> str:
    t = models.LoginToken(email=email, token_hash=token_hash(new_token()), created_at=created, expires_at=expires)
    db.add(t)
    db.flush()
    return t.id


def _session(db, user_id: str, expires: dt.datetime) -> str:
    s = models.Session(user_id=user_id, token_hash=token_hash(new_token()), expires_at=expires)
    db.add(s)
    db.flush()
    return s.id


def test_purge_expired():
    now = models.now()
    hour, day = dt.timedelta(hours=1), dt.timedelta(days=1)
    db = session_factory()()
    try:
        user = models.User(email="purge@example.org")
        db.add(user)
        db.flush()
        old_used = _token(db, "purge@example.org", now - 2 * day, now - 2 * day + hour)
        old_still_valid = _token(db, "purge@example.org", now - 2 * day, now + hour)   # long-lived link
        recent_expired = _token(db, "purge@example.org", now - 2 * hour, now - hour)
        fresh = _token(db, "purge@example.org", now, now + hour)
        expired = _session(db, user.id, now - hour)
        live = _session(db, user.id, now + day)
        db.commit()

        counts = maintenance.purge_expired(db, now=now)
        assert counts["login_tokens"] >= 1 and counts["sessions"] >= 1
        tokens = set(db.scalars(select(models.LoginToken.id)).all())
        sessions = set(db.scalars(select(models.Session.id)).all())
        assert old_used not in tokens
        assert {old_still_valid, recent_expired, fresh} <= tokens
        assert expired not in sessions and live in sessions
        assert maintenance.purge_expired(db, now=now) == {"login_tokens": 0, "sessions": 0, "page_views": 0}
    finally:
        db.close()


def test_purge_runs_at_most_hourly(monkeypatch):
    runs = []
    monkeypatch.setattr(maintenance, "purge_expired", lambda db: runs.append(1) or {"login_tokens": 0, "sessions": 0})
    clock = iter([100.0, 200.0, 100.0 + 3599, 100.0 + 3600, 100.0 + 3700]).__next__
    last = maintenance.purge_if_due(None, clock)         # first call: runs
    assert last == 100.0 and len(runs) == 1
    last = maintenance.purge_if_due(last, clock)         # 100 s later: skipped
    last = maintenance.purge_if_due(last, clock)         # 3599 s later: skipped
    assert last == 100.0 and len(runs) == 1
    last = maintenance.purge_if_due(last, clock)         # an hour later: runs
    assert last == 3700.0 and len(runs) == 2
    last = maintenance.purge_if_due(last, clock)
    assert len(runs) == 2


def test_purge_failure_does_not_stop_the_worker(monkeypatch):
    def boom(db):
        raise RuntimeError("database away")

    monkeypatch.setattr(maintenance, "purge_expired", boom)
    assert maintenance.purge_if_due(None, lambda: 5.0) == 5.0
