"""Operator dashboard: counts, thirty-day series and the latest accounts and reviews.
Administrators only: the signed-in address must be listed in ADMIN_EMAILS."""
from __future__ import annotations

import datetime as dt
from collections import Counter, defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DBSession

from krinea_api import models
from krinea_api.db import get_db
from krinea_api.deps import admin_user
from krinea_api.routers.stats import audience

router = APIRouter(prefix="/admin", tags=["admin"])
DAYS = 30
LIMIT = 25


def _count(db: DBSession, model, *where) -> int:
    return int(db.scalar(select(func.count()).select_from(model).where(*where)) or 0)


def _active_since(db: DBSession, since: dt.datetime) -> int:
    """Distinct accounts that signed in or recorded a decision since `since`."""
    users = set(db.scalars(select(models.Session.user_id).where(models.Session.created_at >= since)))
    users |= {u for u in db.scalars(select(models.Decision.user_id).where(models.Decision.decided_at >= since)) if u}
    return len(users)


@router.get("/overview")
def overview(db: DBSession = Depends(get_db), _admin: models.User = Depends(admin_user)) -> dict:
    now = models.now()
    today = now.date()
    days = [today - dt.timedelta(days=DAYS - 1 - i) for i in range(DAYS)]
    start = dt.datetime.combine(days[0], dt.time.min)
    week, month = now - dt.timedelta(days=7), now - dt.timedelta(days=30)

    signups: Counter[dt.date] = Counter()
    decisions: Counter[dt.date] = Counter()
    active: dict[dt.date, set[str]] = defaultdict(set)
    for (created,) in db.execute(select(models.User.created_at).where(models.User.created_at >= start)):
        signups[created.date()] += 1
    for created, uid in db.execute(select(models.Session.created_at, models.Session.user_id)
                                   .where(models.Session.created_at >= start)):
        active[created.date()].add(uid)
    for decided, uid in db.execute(select(models.Decision.decided_at, models.Decision.user_id)
                                   .where(models.Decision.decided_at >= start)):
        decisions[decided.date()] += 1
        if uid:
            active[decided.date()].add(uid)

    ai_calls, ai_tokens = db.execute(select(
        func.count(models.AIUsage.id),
        func.coalesce(func.sum(models.AIUsage.input_tokens + models.AIUsage.output_tokens), 0))).one()
    totals = {
        "users": _count(db, models.User),
        "verified": _count(db, models.User, models.User.email_verified_at.is_not(None)),
        "google": _count(db, models.OAuthAccount, models.OAuthAccount.provider == "google"),
        "signups_7d": _count(db, models.User, models.User.created_at >= week),
        "signups_30d": _count(db, models.User, models.User.created_at >= month),
        "active_7d": _active_since(db, week),
        "active_30d": _active_since(db, month),
        "reviews": _count(db, models.Review),
        "imports": _count(db, models.Import),
        "records": _count(db, models.Record),
        "decisions": _count(db, models.Decision),
        "extractions": _count(db, models.Extraction),
        "extractions_verified": _count(db, models.Extraction, models.Extraction.status == "verified"),
        "ai_calls": int(ai_calls or 0),
        "ai_tokens": int(ai_tokens or 0),
    }
    series = {
        "days": [d.isoformat() for d in days],
        "signups": [signups.get(d, 0) for d in days],
        "active": [len(active.get(d, ())) for d in days],
        "decisions": [decisions.get(d, 0) for d in days],
    }

    google_ids = set(db.scalars(select(models.OAuthAccount.user_id).where(models.OAuthAccount.provider == "google")))
    reviews_per_user = dict(db.execute(select(models.Membership.user_id, func.count())
                                       .group_by(models.Membership.user_id)).all())
    recent_users = [{
        "id": u.id, "email": u.email, "name": u.name, "plan": u.plan, "is_active": u.is_active,
        "created_at": u.created_at, "last_login_at": u.last_login_at,
        "email_verified": u.email_verified_at is not None,
        "method": "google" if u.id in google_ids else ("password" if u.password_hash else "email_link"),
        "reviews": int(reviews_per_user.get(u.id, 0)),
    } for u in db.scalars(select(models.User).order_by(models.User.created_at.desc()).limit(LIMIT))]

    records_per_review = dict(db.execute(select(models.Record.review_id, func.count())
                                         .group_by(models.Record.review_id)).all())
    decisions_per_review = dict(db.execute(select(models.Decision.review_id, func.count())
                                           .group_by(models.Decision.review_id)).all())
    members_per_review = dict(db.execute(select(models.Membership.review_id, func.count())
                                         .group_by(models.Membership.review_id)).all())
    recent_reviews = []
    for r, owner_email in db.execute(select(models.Review, models.User.email)
                                     .join(models.User, models.User.id == models.Review.owner_id)
                                     .order_by(models.Review.updated_at.desc()).limit(LIMIT)):
        recent_reviews.append({
            "id": r.id, "title": r.title, "owner_email": owner_email, "is_archived": r.is_archived,
            "created_at": r.created_at, "updated_at": r.updated_at,
            "records": int(records_per_review.get(r.id, 0)),
            "decisions": int(decisions_per_review.get(r.id, 0)),
            "members": int(members_per_review.get(r.id, 0)),
        })

    return {"generated_at": now, "totals": totals, "series": series, "audience": audience(db, days),
            "recent_users": recent_users, "recent_reviews": recent_reviews}
