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


# Failures that every following record would hit as well: the run stops at the first one.
AI_FATAL = {"nokey", "key", "model", "credit", "quota"}


def _screen_one(db: Session, review: models.Review, user: models.User, rec: models.Record, stage: str,
                provider: str, model: str) -> tuple[str, str] | None:
    """None once the suggestion is saved, else (kind, message) with kind as in
    `llm.error_kind`, or "nokey". A rate limit is waited out, three times at most, before it
    counts as a failure. The message never contains the key."""
    from krinea_api.services import ai
    from krinea_core import llm
    attempt = 0
    while True:
        try:
            ai.screen_record(db, review, user, rec, stage, provider, model)
            return None
        except ai.AIUnavailable as e:
            db.rollback()
            return "nokey", str(e)
        except Exception as e:                       # noqa: BLE001  (reported to the user)
            db.rollback()
            wait = llm.retry_after(e)
            if wait is None or attempt >= 3:
                message = f"{type(e).__name__}: {e}"
                try:
                    key, _source = ai.resolve_key(db, user, provider)
                    message = message.replace(key, "[key]") if key else message
                except ai.AIUnavailable:
                    pass
                return llm.error_kind(e), message
            attempt += 1
            time.sleep(wait)


def _run_ai_screen(db: Session, job: models.Job) -> dict:
    """Suggestions for the job's records, in the order sent (the page sends the record on
    screen first). A failure that every following record would hit too (key refused, model
    not available, quota, credit) stops the run at once, as do five failures in a row; the
    result says what happened (`error_kind`, `error`) and is kept up to date as the run goes,
    so the page can show each suggestion as it comes."""
    from krinea_api.services import ai
    review = db.get(models.Review, job.review_id)
    user = db.get(models.User, job.user_id)
    p = job.payload or {}
    ids = list(p.get("record_ids") or [])
    stage = p.get("stage", "ta")
    provider, model = ai.provider_and_model(review, "screening", p.get("provider"), p.get("model"))
    out = {"stage": stage, "provider": provider, "model": model, "total": len(ids), "ok": 0, "failed": 0,
           "error_kind": "", "error": "", "errors": [], "stopped": False}
    streak = 0
    for i, rid in enumerate(ids, 1):
        rec = db.get(models.Record, rid)
        if rec and rec.review_id == job.review_id:
            failure = _screen_one(db, review, user, rec, stage, provider, model)
            if failure is None:
                out["ok"], streak = out["ok"] + 1, 0
            else:
                kind, message = failure
                out["failed"], streak = out["failed"] + 1, streak + 1
                out["error_kind"], out["error"] = kind, message[:800]
                out["errors"] = [*out["errors"], f"#{rid}: {message[:300]}"][-5:]
                out["stopped"] = kind in AI_FATAL or streak >= 5
        _progress(db, job, i, len(ids), dict(out))
        if out["stopped"]:
            break
    return out


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
