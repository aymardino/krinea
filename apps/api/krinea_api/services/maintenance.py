"""Housekeeping run by the worker: drop sign-in material nobody can use any more."""
from __future__ import annotations

import datetime as dt
import logging
import time
from collections.abc import Callable

from sqlalchemy import delete
from sqlalchemy.orm import Session

from krinea_api import models
from krinea_api.db import session_factory

log = logging.getLogger("krinea.maintenance")

LOGIN_TOKEN_RETENTION = dt.timedelta(days=1)     # sign-in links are kept a day, then purged
PURGE_INTERVAL_SECONDS = 3600                    # the worker purges at most once an hour
AUDIENCE_RETENTION = dt.timedelta(days=400)      # audience counts: thirteen months, as the privacy page says


def purge_expired(db: Session, now: dt.datetime | None = None) -> dict[str, int]:
    """Deletes sign-in-link tokens older than a day (never one that is still valid) and
    sessions past their expiry. Returns how many rows of each went."""
    now = now or models.now()
    tokens = db.execute(delete(models.LoginToken).where(models.LoginToken.created_at < now - LOGIN_TOKEN_RETENTION,
                                                        models.LoginToken.expires_at < now)).rowcount
    sessions = db.execute(delete(models.Session).where(models.Session.expires_at < now)).rowcount
    views = db.execute(delete(models.PageView).where(models.PageView.day < (now - AUDIENCE_RETENTION).date())).rowcount
    db.commit()
    return {"login_tokens": int(tokens or 0), "sessions": int(sessions or 0), "page_views": int(views or 0)}


def purge_if_due(last_run: float | None, clock: Callable[[], float] = time.monotonic) -> float | None:
    """Runs `purge_expired` unless it already ran less than an hour ago (by `clock`).
    Returns the time of the latest run, to pass back on the next call. Errors are logged:
    housekeeping must never stop the worker."""
    t = clock()
    if last_run is not None and t - last_run < PURGE_INTERVAL_SECONDS:
        return last_run
    db: Session = session_factory()()
    try:
        counts = purge_expired(db)
        if any(counts.values()):
            log.info("purged %(login_tokens)d sign-in token(s), %(sessions)d expired session(s) and %(page_views)d old page view(s)", counts)
    except Exception:                                # noqa: BLE001
        db.rollback()
        log.exception("purge of expired tokens and sessions failed")
    finally:
        db.close()
    return t
