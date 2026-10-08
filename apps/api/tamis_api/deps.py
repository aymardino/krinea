"""FastAPI dependencies: database session, current user, review access."""
from __future__ import annotations

import datetime as dt

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from tamis_api import models
from tamis_api.config import get_settings
from tamis_api.db import get_db
from tamis_api.security import token_hash

ROLE_RANK = {"viewer": 0, "reviewer": 1, "admin": 2, "owner": 3}


def _token_from_request(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.cookies.get(get_settings().cookie_name)


def optional_user(request: Request, db: DBSession = Depends(get_db)) -> models.User | None:
    token = _token_from_request(request)
    if not token:
        return None
    sess = db.scalar(select(models.Session).where(models.Session.token_hash == token_hash(token)))
    if not sess or sess.expires_at < dt.datetime.now(dt.timezone.utc).replace(tzinfo=None):
        return None
    user = db.get(models.User, sess.user_id)
    if not user or not user.is_active:
        return None
    request.state.session_id = sess.id
    return user


def current_user(user: models.User | None = Depends(optional_user)) -> models.User:
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in")
    return user


class ReviewAccess:
    """Dependency factory: `Depends(ReviewAccess("reviewer"))` loads the review
    and checks the caller's role is at least the one required."""

    def __init__(self, min_role: str = "viewer"):
        self.min_role = min_role

    def __call__(self, review_id: str, user: models.User = Depends(current_user),
                 db: DBSession = Depends(get_db)) -> tuple[models.Review, models.Membership]:
        review = db.get(models.Review, review_id)
        if not review:
            raise HTTPException(404, "Review not found")
        m = db.scalar(select(models.Membership).where(models.Membership.review_id == review_id,
                                                      models.Membership.user_id == user.id))
        if not m:
            raise HTTPException(403, "You are not a member of this review")
        if ROLE_RANK[m.role] < ROLE_RANK[self.min_role]:
            raise HTTPException(403, f"This action needs the {self.min_role} role")
        return review, m


def log_activity(db: DBSession, review_id: str, user_id: str | None, kind: str, **detail) -> None:
    db.add(models.ActivityLog(review_id=review_id, user_id=user_id, kind=kind, detail=detail))
