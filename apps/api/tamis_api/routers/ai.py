"""AI suggestions, data extraction and the job endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from tamis_api import models, schemas
from tamis_api.db import get_db
from tamis_api.deps import ReviewAccess, current_user, log_activity
from tamis_api.services import ai as ai_service
from tamis_api.services import jobs as job_service
from tamis_api.services import screening as scr
from tamis_core import extraction_schema

router = APIRouter(tags=["ai"])


@router.post("/reviews/{review_id}/ai/screen", response_model=schemas.JobOut)
def ai_screen(body: schemas.AIScreenIn, access=Depends(ReviewAccess("reviewer")),
              user: models.User = Depends(current_user), db: DBSession = Depends(get_db)):
    review, _ = access
    if body.stage not in ("ta", "ft"):
        raise HTTPException(400, "stage must be ta or ft")
    c = scr.compute(db, review)
    ids = body.record_ids
    if ids is None:
        have = set(db.scalars(select(models.AISuggestion.record_id).where(models.AISuggestion.review_id == review.id,
                                                                         models.AISuggestion.stage == body.stage)))
        status = c["ta_status"] if body.stage == "ta" else c["ft_status"]
        ids = [rid for rid in scr.pool_ids(c, body.stage) if rid not in have and status.get(rid) == "pending"]
    ids = ids[: max(1, min(body.limit, 2000))]
    try:                                            # fail fast when no key is usable
        provider, _model = ai_service.provider_and_model(review, "screening", body.provider, body.model)
        ai_service.resolve_key(db, user, provider)
    except ai_service.AIUnavailable as e:
        raise HTTPException(402, str(e))
    log_activity(db, review.id, user.id, "ai_screen", n=len(ids), stage=body.stage)
    db.commit()
    return job_service.enqueue(db, "ai_screen", {"record_ids": ids, "stage": body.stage, "provider": body.provider,
                                                 "model": body.model}, review.id, user.id)


@router.get("/reviews/{review_id}/ai/suggestions")
def suggestions(stage: str = "ta", access=Depends(ReviewAccess("viewer")), db: DBSession = Depends(get_db)):
    review, _ = access
    rows = db.scalars(select(models.AISuggestion).where(models.AISuggestion.review_id == review.id,
                                                        models.AISuggestion.stage == stage)).all()
    return [{"record_id": s.record_id, "decision": s.decision, "reason": s.reason, "rationale": s.rationale,
             "confidence": s.confidence, "model": s.model, "created_at": s.created_at} for s in rows]


# ── Extraction ───────────────────────────────────────────────────────────────────
def _ex_out(ex: models.Extraction, fields: list[dict], with_text: bool = False) -> schemas.ExtractionOut:
    return schemas.ExtractionOut(record_id=ex.record_id, status=ex.status, model=ex.model, values=ex.values or {},
                                 quotes=ex.quotes or {}, ai_values=ex.ai_values or {},
                                 text_extracted=(ex.text_extracted or "") if with_text else "", error=ex.error,
                                 created_at=ex.created_at, verified_at=ex.verified_at,
                                 flags={k: list(v) for k, v in extraction_schema.check_values(
                                     fields, ex.values or {}, ex.quotes or {}).items()})


@router.post("/reviews/{review_id}/extraction/run", response_model=schemas.JobOut)
def run_extraction(body: schemas.ExtractionRunIn, access=Depends(ReviewAccess("reviewer")),
                   user: models.User = Depends(current_user), db: DBSession = Depends(get_db)):
    review, _ = access
    c = scr.compute(db, review)
    ids = body.record_ids
    if ids is None:
        have = set(db.scalars(select(models.Extraction.record_id).where(models.Extraction.review_id == review.id,
                                                                       models.Extraction.status != "failed")))
        with_pdf = set(db.scalars(select(models.Record.id).where(models.Record.review_id == review.id,
                                                                 models.Record.pdf_key != "")))
        ids = [rid for rid in c["extract_pool"] if rid in with_pdf and rid not in have]
    try:
        provider, _model = ai_service.provider_and_model(review, "extraction", body.provider, body.model)
        ai_service.resolve_key(db, user, provider)
    except ai_service.AIUnavailable as e:
        raise HTTPException(402, str(e))
    log_activity(db, review.id, user.id, "extraction_run", n=len(ids))
    db.commit()
    return job_service.enqueue(db, "extract", {"record_ids": ids, "provider": body.provider, "model": body.model},
                               review.id, user.id)


@router.get("/reviews/{review_id}/extraction", response_model=list[schemas.ExtractionOut])
def list_extractions(access=Depends(ReviewAccess("viewer")), db: DBSession = Depends(get_db)):
    review, _ = access
    fields = extraction_schema.from_json(review.extraction_schema or [])
    rows = db.scalars(select(models.Extraction).where(models.Extraction.review_id == review.id)
                      .order_by(models.Extraction.record_id)).all()
    return [_ex_out(e, fields) for e in rows]


@router.get("/reviews/{review_id}/extraction/{record_id}", response_model=schemas.ExtractionOut)
def get_extraction(record_id: int, access=Depends(ReviewAccess("viewer")), db: DBSession = Depends(get_db)):
    review, _ = access
    ex = db.scalar(select(models.Extraction).where(models.Extraction.review_id == review.id,
                                                   models.Extraction.record_id == record_id))
    if not ex:
        raise HTTPException(404, "No extraction for this record")
    return _ex_out(ex, extraction_schema.from_json(review.extraction_schema or []), with_text=True)


@router.put("/reviews/{review_id}/extraction/{record_id}", response_model=schemas.ExtractionOut)
def verify_extraction(record_id: int, body: schemas.ExtractionVerifyIn, access=Depends(ReviewAccess("reviewer")),
                      user: models.User = Depends(current_user), db: DBSession = Depends(get_db)):
    review, _ = access
    fields = extraction_schema.from_json(review.extraction_schema or [])
    ex = db.scalar(select(models.Extraction).where(models.Extraction.review_id == review.id,
                                                   models.Extraction.record_id == record_id))
    if not ex:
        rec = db.get(models.Record, record_id)
        if not rec or rec.review_id != review.id:
            raise HTTPException(404, "Record not found")
        ex = models.Extraction(review_id=review.id, record_id=record_id, model="manual")
        db.add(ex)
    names = {f["name"] for f in fields}
    ex.values = {k: ("" if v is None else str(v)) for k, v in body.values.items() if k in names}
    ex.quotes = {k: str(v or "") for k, v in body.quotes.items() if k in names} or (ex.quotes or {})
    ex.status, ex.error, ex.verified_at, ex.verified_by, ex.seconds = "verified", "", models.now(), user.id, body.seconds
    log_activity(db, review.id, user.id, "extraction_verified", record_id=record_id)
    db.commit()
    return _ex_out(ex, fields)


@router.delete("/reviews/{review_id}/extraction/{record_id}", response_model=schemas.Ok)
def delete_extraction(record_id: int, access=Depends(ReviewAccess("reviewer")), db: DBSession = Depends(get_db)):
    review, _ = access
    ex = db.scalar(select(models.Extraction).where(models.Extraction.review_id == review.id,
                                                   models.Extraction.record_id == record_id))
    if ex:
        db.delete(ex)
        db.commit()
    return schemas.Ok()


# ── Jobs ─────────────────────────────────────────────────────────────────────────
@router.get("/jobs/{job_id}", response_model=schemas.JobOut)
def get_job(job_id: str, user: models.User = Depends(current_user), db: DBSession = Depends(get_db)):
    job = db.get(models.Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job.review_id:
        m = db.scalar(select(models.Membership).where(models.Membership.review_id == job.review_id,
                                                      models.Membership.user_id == user.id))
        if not m:
            raise HTTPException(403, "Not your job")
    return job


@router.get("/reviews/{review_id}/jobs", response_model=list[schemas.JobOut])
def review_jobs(access=Depends(ReviewAccess("viewer")), db: DBSession = Depends(get_db)):
    review, _ = access
    return db.scalars(select(models.Job).where(models.Job.review_id == review.id)
                      .order_by(models.Job.created_at.desc()).limit(20)).all()
