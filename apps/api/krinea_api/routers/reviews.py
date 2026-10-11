"""Reviews, members, invitations, settings, summaries."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DBSession

from krinea_api import models, schemas
from krinea_api.config import get_settings
from krinea_api.urls import public_base_url
from krinea_api.db import get_db
from krinea_api.deps import ROLE_RANK, ReviewAccess, current_user, log_activity
from krinea_api.security import expires_in, new_token, token_hash
from krinea_api.services import email as email_service
from krinea_api.services import screening as scr
from krinea_core import extraction_schema
from krinea_core import screening as core_screening

router = APIRouter(prefix="/reviews", tags=["reviews"])

DEFAULT_SETTINGS = {"required_reviewers": 1, "blind": True, "ai_provider": "claude",
                    "ai_model_screening": "", "ai_model_extraction": ""}


def _members(db: DBSession, review_id: str) -> list[schemas.MemberOut]:
    rows = db.execute(select(models.Membership, models.User).join(models.User, models.User.id == models.Membership.user_id)
                      .where(models.Membership.review_id == review_id).order_by(models.Membership.created_at)).all()
    return [schemas.MemberOut(user_id=u.id, email=u.email, name=u.name, role=m.role, created_at=m.created_at)
            for m, u in rows]


def review_out(db: DBSession, review: models.Review, role: str, with_counts: bool = True,
               user: models.User | None = None) -> schemas.ReviewOut:
    return schemas.ReviewOut(
        id=review.id, title=review.title, description=review.description, question=review.question,
        review_type=review.review_type, criteria=core_screening.criteria_with_defaults(review.criteria or {}),
        settings={**DEFAULT_SETTINGS, **(review.settings or {})},
        extraction_schema=extraction_schema.from_json(review.extraction_schema or []),
        is_archived=review.is_archived, created_at=review.created_at, updated_at=review.updated_at,
        my_role=role, members=_members(db, review.id),
        counts=scr.summary(db, review, user) if with_counts else {})


@router.get("", response_model=list[schemas.ReviewSummary])
def list_reviews(user: models.User = Depends(current_user), db: DBSession = Depends(get_db)):
    rows = db.execute(select(models.Review, models.Membership.role)
                      .join(models.Membership, models.Membership.review_id == models.Review.id)
                      .where(models.Membership.user_id == user.id).order_by(models.Review.updated_at.desc())).all()
    out = []
    for review, role in rows:
        n_records = db.scalar(select(func.count()).where(models.Record.review_id == review.id,
                                                          models.Record.is_duplicate.is_(False))) or 0
        n_members = db.scalar(select(func.count()).where(models.Membership.review_id == review.id)) or 1
        my_done = db.scalar(select(func.count()).where(models.Decision.review_id == review.id,
                                                        models.Decision.reviewer == user.id,
                                                        models.Decision.stage == "ta")) or 0
        out.append(schemas.ReviewSummary(id=review.id, title=review.title, review_type=review.review_type,
                                         my_role=role, is_archived=review.is_archived, updated_at=review.updated_at,
                                         n_records=int(n_records), n_members=int(n_members),
                                         progress=round(min(1.0, my_done / n_records), 3) if n_records else 0.0))
    return out


@router.post("", response_model=schemas.ReviewOut, status_code=201)
def create_review(body: schemas.ReviewCreate, user: models.User = Depends(current_user),
                  db: DBSession = Depends(get_db)):
    review = models.Review(owner_id=user.id, title=body.title.strip(), description=body.description,
                           question=body.question, review_type=body.review_type,
                           criteria=core_screening.criteria_with_defaults({}), settings=dict(DEFAULT_SETTINGS),
                           extraction_schema=[dict(f) for f in extraction_schema.DEFAULT_SCHEMA])
    db.add(review)
    db.flush()
    db.add(models.Membership(review_id=review.id, user_id=user.id, role="owner"))
    log_activity(db, review.id, user.id, "review_created", title=review.title)
    db.commit()
    return review_out(db, review, "owner", user=user)


@router.get("/templates/extraction")
def extraction_templates():
    out = {"default": extraction_schema.DEFAULT_SCHEMA}
    try:
        out["energy"] = extraction_schema.energy_template()
    except Exception:            # noqa: BLE001 — the legacy module is optional
        pass
    return out


@router.get("/{review_id}", response_model=schemas.ReviewOut)
def get_review(access=Depends(ReviewAccess("viewer")), user: models.User = Depends(current_user),
               db: DBSession = Depends(get_db)):
    review, m = access
    return review_out(db, review, m.role, user=user)


@router.patch("/{review_id}", response_model=schemas.ReviewOut)
def update_review(body: schemas.ReviewUpdate, access=Depends(ReviewAccess("admin")),
                  user: models.User = Depends(current_user), db: DBSession = Depends(get_db)):
    review, m = access
    for f in ("title", "description", "question", "review_type", "is_archived"):
        v = getattr(body, f)
        if v is not None:
            setattr(review, f, v.strip() if isinstance(v, str) and f == "title" else v)
    if body.criteria is not None:
        review.criteria = core_screening.criteria_with_defaults({**(review.criteria or {}), **body.criteria})
    if body.settings is not None:
        merged = {**DEFAULT_SETTINGS, **(review.settings or {}), **body.settings}
        merged["required_reviewers"] = max(1, min(5, int(merged.get("required_reviewers") or 1)))
        review.settings = merged
    if body.extraction_schema is not None:
        fields = [extraction_schema.normalise_field(f) for f in body.extraction_schema
                  if str(f.get("name") or f.get("label") or "").strip()]
        errors = extraction_schema.validate_schema(fields)
        if errors:
            raise HTTPException(422, "; ".join(errors))
        review.extraction_schema = fields
    log_activity(db, review.id, user.id, "review_updated")
    db.commit()
    return review_out(db, review, m.role, user=user)


@router.delete("/{review_id}", response_model=schemas.Ok)
def delete_review(access=Depends(ReviewAccess("owner")), db: DBSession = Depends(get_db)):
    review, _ = access
    db.delete(review)
    db.commit()
    return schemas.Ok()


@router.get("/{review_id}/summary")
def summary(access=Depends(ReviewAccess("viewer")), user: models.User = Depends(current_user),
            db: DBSession = Depends(get_db)):
    review, _ = access
    return scr.summary(db, review, user)


@router.get("/{review_id}/keywords")
def keywords(access=Depends(ReviewAccess("viewer")), db: DBSession = Depends(get_db)):
    review, _ = access
    return scr.keyword_counts(db, review)


@router.get("/{review_id}/activity")
def activity(access=Depends(ReviewAccess("viewer")), db: DBSession = Depends(get_db)):
    review, _ = access
    return {"items": scr.activity(db, review.id), "throughput": scr.throughput(db, review.id)}


# ── Members ──────────────────────────────────────────────────────────────────────
@router.get("/{review_id}/members", response_model=list[schemas.MemberOut])
def members(access=Depends(ReviewAccess("viewer")), db: DBSession = Depends(get_db)):
    review, _ = access
    return _members(db, review.id)


@router.patch("/{review_id}/members/{user_id}", response_model=list[schemas.MemberOut])
def set_role(user_id: str, body: schemas.RoleIn, access=Depends(ReviewAccess("admin")),
             db: DBSession = Depends(get_db)):
    review, me = access
    if body.role not in ("admin", "reviewer", "viewer"):
        raise HTTPException(400, "role must be admin, reviewer or viewer")
    m = db.scalar(select(models.Membership).where(models.Membership.review_id == review.id,
                                                  models.Membership.user_id == user_id))
    if not m:
        raise HTTPException(404, "Member not found")
    if m.role == "owner":
        raise HTTPException(400, "The owner's role cannot be changed")
    m.role = body.role
    db.commit()
    return _members(db, review.id)


@router.delete("/{review_id}/members/{user_id}", response_model=list[schemas.MemberOut])
def remove_member(user_id: str, access=Depends(ReviewAccess("viewer")), user: models.User = Depends(current_user),
                  db: DBSession = Depends(get_db)):
    review, me = access
    if user_id != user.id and ROLE_RANK[me.role] < ROLE_RANK["admin"]:
        raise HTTPException(403, "Only admins remove other members")
    m = db.scalar(select(models.Membership).where(models.Membership.review_id == review.id,
                                                  models.Membership.user_id == user_id))
    if not m:
        raise HTTPException(404, "Member not found")
    if m.role == "owner":
        raise HTTPException(400, "The owner cannot leave the review; transfer it first")
    db.delete(m)
    db.commit()
    return _members(db, review.id)


# ── Invitations ──────────────────────────────────────────────────────────────────
def _invite_out(inv: models.Invitation, token: str | None = None, base: str = "") -> schemas.InvitationOut:
    s = get_settings()
    return schemas.InvitationOut(id=inv.id, email=inv.email, role=inv.role, created_at=inv.created_at,
                                 expires_at=inv.expires_at, accepted_at=inv.accepted_at,
                                 accept_url=f"{base or s.base_url}/invite/{token}" if token and s.debug else None)


@router.post("/{review_id}/invitations", response_model=schemas.InvitationOut, status_code=201)
def invite(body: schemas.InviteIn, request: Request, access=Depends(ReviewAccess("admin")),
           user: models.User = Depends(current_user), db: DBSession = Depends(get_db)):
    review, _ = access
    email = body.email.lower().strip()
    existing = db.scalar(select(models.Membership).join(models.User).where(models.Membership.review_id == review.id,
                                                                            models.User.email == email))
    if existing:
        raise HTTPException(409, "This person is already a member")
    token = new_token()
    inv = models.Invitation(review_id=review.id, email=email, role=body.role, token_hash=token_hash(token),
                            invited_by=user.id, expires_at=expires_in(days=14))
    db.add(inv)
    log_activity(db, review.id, user.id, "invited", email=email, role=body.role)
    db.commit()
    base = public_base_url(request)
    url = f"{base}/invite/{token}"
    email_service.send_invitation(email, user.name or user.email, review.title, body.role, url, user.locale)
    return _invite_out(inv, token, base)


@router.get("/{review_id}/invitations", response_model=list[schemas.InvitationOut])
def invitations(access=Depends(ReviewAccess("admin")), db: DBSession = Depends(get_db)):
    review, _ = access
    rows = db.scalars(select(models.Invitation).where(models.Invitation.review_id == review.id,
                                                      models.Invitation.accepted_at.is_(None))
                      .order_by(models.Invitation.created_at.desc())).all()
    return [_invite_out(i) for i in rows]


@router.delete("/{review_id}/invitations/{inv_id}", response_model=schemas.Ok)
def revoke_invitation(inv_id: str, access=Depends(ReviewAccess("admin")), db: DBSession = Depends(get_db)):
    review, _ = access
    inv = db.get(models.Invitation, inv_id)
    if inv and inv.review_id == review.id:
        db.delete(inv)
        db.commit()
    return schemas.Ok()


@router.post("/invitations/accept", response_model=schemas.ReviewOut)
def accept_invitation(body: schemas.TokenIn, user: models.User = Depends(current_user),
                      db: DBSession = Depends(get_db)):
    inv = db.scalar(select(models.Invitation).where(models.Invitation.token_hash == token_hash(body.token)))
    if not inv or inv.accepted_at or inv.expires_at < models.now():
        raise HTTPException(400, "This invitation is invalid or has expired")
    review = db.get(models.Review, inv.review_id)
    m = db.scalar(select(models.Membership).where(models.Membership.review_id == review.id,
                                                  models.Membership.user_id == user.id))
    if not m:
        m = models.Membership(review_id=review.id, user_id=user.id, role=inv.role)
        db.add(m)
    inv.accepted_at = models.now()
    log_activity(db, review.id, user.id, "joined", role=inv.role)
    db.commit()
    return review_out(db, review, m.role, user=user)


@router.get("/invitations/{token}/preview")
def invitation_preview(token: str, db: DBSession = Depends(get_db)):
    inv = db.scalar(select(models.Invitation).where(models.Invitation.token_hash == token_hash(token)))
    if not inv or inv.accepted_at or inv.expires_at < models.now():
        raise HTTPException(400, "This invitation is invalid or has expired")
    review = db.get(models.Review, inv.review_id)
    inviter = db.get(models.User, inv.invited_by)
    return {"review_title": review.title, "role": inv.role, "email": inv.email,
            "inviter": (inviter.name or inviter.email) if inviter else ""}
