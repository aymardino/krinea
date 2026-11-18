"""Database-backed job queue (D-17). Long operations run in the worker process;
in development and tests they run inline so nothing else is needed."""
from __future__ import annotations

import logging
import time
import traceback

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from krinea_api import models
from krinea_api.config import get_settings
from krinea_api.db import session_factory
from krinea_api.services import maintenance

log = logging.getLogger("krinea.jobs")


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


def _side_progress(db: Session, job: models.Job, every: float = 0.5):
    """Progress of a job whose work is one transaction (duplicate detection), written through a
    separate session so that nothing of the work is committed before all of it is. At most one
    write every `every` seconds. SQLite takes one writer at a time and would make that write
    wait for the whole transaction: there the job reports no intermediate step."""
    if db.get_bind().dialect.name == "sqlite":
        return None
    job_id, last = job.id, [float("-inf")]

    def report(share: float) -> None:
        now = time.monotonic()
        if now - last[0] < every:
            return
        last[0] = now
        side = session_factory()()
        try:
            side.execute(update(models.Job).where(models.Job.id == job_id)
                         .values(progress=round(max(0.0, min(share, 0.99)), 4)))
            side.commit()
        except Exception:                            # noqa: BLE001  (a progress bar is best effort)
            side.rollback()
        finally:
            side.close()
    return report


def _run_dedup(db: Session, job: models.Job) -> dict:
    from krinea_api.services import dedup
    review = db.get(models.Review, job.review_id)
    p = job.payload or {}
    return dedup.run(db, review, float(p.get("auto_threshold", 95)), float(p.get("review_threshold", 85)),
                     user_id=job.user_id, progress=_side_progress(db, job))


def _run_ai_screen(db: Session, job: models.Job) -> dict:
    from krinea_api.services import ai
    review = db.get(models.Review, job.review_id)
    user = db.get(models.User, job.user_id)
    p = job.payload or {}
    ids = list(p.get("record_ids") or [])
    ok, errors = 0, []
    for i, rid in enumerate(ids, 1):
        rec = db.get(models.Record, rid)
        if not rec or rec.review_id != job.review_id:
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
    from krinea_api.services import ai
    review = db.get(models.Review, job.review_id)
    user = db.get(models.User, job.user_id)
    p = job.payload or {}
    ids = list(p.get("record_ids") or [])
    ok, failed = 0, 0
    for i, rid in enumerate(ids, 1):
        rec = db.get(models.Record, rid)
        if not rec or rec.review_id != job.review_id:
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


INTERRUPTED = "Interrupted: the worker restarted. Run it again."


def fail_interrupted(db: Session) -> int:
    """Jobs still marked running when no worker runs them (the worker was stopped by a deploy
    or a crash) would never end, and pages following them would wait forever: they are marked
    failed. Returns how many."""
    n = db.execute(update(models.Job).where(models.Job.status == "running")
                   .values(status="failed", error=INTERRUPTED, finished_at=models.now())).rowcount
    db.commit()
    return int(n or 0)


def worker_loop(poll_seconds: float = 2.0, sweep_after: float = 120.0) -> None:
    """`python -m krinea_api.worker` — picks queued jobs one at a time and, at most once an
    hour, purges old sign-in tokens and expired sessions. There is a single worker (D-17): once
    it has been up for `sweep_after` seconds, long enough for the instance it replaced to be
    gone, the jobs that instance left running are marked failed (once, between two jobs)."""
    log.info("worker started")
    last_purge: float | None = None
    started, swept = time.monotonic(), False
    while True:
        last_purge = maintenance.purge_if_due(last_purge)
        db: Session = session_factory()()
        try:
            if not swept and time.monotonic() - started >= sweep_after:
                swept = True
                if n := fail_interrupted(db):
                    log.warning("%d interrupted job(s) marked failed", n)
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
