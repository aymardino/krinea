"""Database-backed job queue (D-17). Long operations run in the worker process;
in development and tests they run inline so nothing else is needed."""
from __future__ import annotations

import logging
import time
import traceback

from sqlalchemy import select
from sqlalchemy.orm import Session

from tamis_api import models
from tamis_api.config import get_settings
from tamis_api.db import session_factory

log = logging.getLogger("tamis.jobs")


def enqueue(db: Session, kind: str, payload: dict, review_id: str | None = None,
            user_id: str | None = None) -> models.Job:
    job = models.Job(kind=kind, payload=payload, review_id=review_id, user_id=user_id)
    db.add(job)
    db.commit()
    db.refresh(job)
    if get_settings().inline_jobs:
        run_job(job.id)
        db.refresh(job)
    return job


def _progress(db: Session, job: models.Job, done: int, total: int, result: dict | None = None) -> None:
    job.progress = round(done / total, 4) if total else 1.0
    if result is not None:
        job.result = result
    db.commit()


def _run_dedup(db: Session, job: models.Job) -> dict:
    from tamis_api.services import dedup
    review = db.get(models.Review, job.review_id)
    p = job.payload or {}
    return dedup.run(db, review, float(p.get("auto_threshold", 95)), float(p.get("review_threshold", 85)),
                     user_id=job.user_id)


def _run_ai_screen(db: Session, job: models.Job) -> dict:
    from tamis_api.services import ai
    review = db.get(models.Review, job.review_id)
    user = db.get(models.User, job.user_id)
    p = job.payload or {}
    ids = list(p.get("record_ids") or [])
    ok, errors = 0, []
    for i, rid in enumerate(ids, 1):
        rec = db.get(models.Record, rid)
        if not rec:
            continue
        try:
            ai.screen_record(db, review, user, rec, p.get("stage", "ta"), p.get("provider"), p.get("model"))
            ok += 1
        except ai.AIUnavailable as e:
            errors.append(f"#{rid}: {e}")
            break
        except Exception as e:                       # noqa: BLE001
            errors.append(f"#{rid}: {type(e).__name__}: {e}")
        _progress(db, job, i, len(ids), {"ok": ok, "errors": errors[-20:]})
    return {"ok": ok, "errors": errors[-20:], "total": len(ids)}


def _run_extract(db: Session, job: models.Job) -> dict:
    from tamis_api.services import ai
    review = db.get(models.Review, job.review_id)
    user = db.get(models.User, job.user_id)
    p = job.payload or {}
    ids = list(p.get("record_ids") or [])
    ok, failed = 0, 0
    for i, rid in enumerate(ids, 1):
        rec = db.get(models.Record, rid)
        if not rec:
            continue
        ex = ai.extract_record(db, review, user, rec, p.get("provider"), p.get("model"))
        ok += ex.status == "draft"
        failed += ex.status == "failed"
        _progress(db, job, i, len(ids), {"ok": ok, "failed": failed})
    return {"ok": ok, "failed": failed, "total": len(ids)}


RUNNERS = {"dedup": _run_dedup, "ai_screen": _run_ai_screen, "extract": _run_extract}


def run_job(job_id: str) -> None:
    db: Session = session_factory()()
    try:
        job = db.get(models.Job, job_id)
        if not job or job.status not in ("queued", "running"):
            return
        job.status, job.started_at = "running", models.now()
        db.commit()
        try:
            result = RUNNERS[job.kind](db, job)
            job.status, job.result, job.progress = "done", result, 1.0
        except Exception as e:                       # noqa: BLE001
            db.rollback()
            job = db.get(models.Job, job_id)
            job.status, job.error = "failed", f"{type(e).__name__}: {e}"
            log.error("job %s failed\n%s", job_id, traceback.format_exc())
        job.finished_at = models.now()
        db.commit()
    finally:
        db.close()


def worker_loop(poll_seconds: float = 2.0) -> None:
    """`python -m tamis_api.worker` — picks queued jobs one at a time."""
    log.info("worker started")
    while True:
        db: Session = session_factory()()
        try:
            job = db.scalar(select(models.Job).where(models.Job.status == "queued")
                            .order_by(models.Job.created_at).limit(1))
            job_id = job.id if job else None
            if job:
                job.status = "running"          # claim before running (single worker; see D-17)
                db.commit()
        finally:
            db.close()
        if job_id:
            run_job(job_id)
        else:
            time.sleep(poll_seconds)
