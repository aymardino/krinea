"""Screening suggestions learned from each reviewer's own title/abstract decisions (D-54).

No AI service: krinea_core.learn trains a small text classifier on the records the reviewer
included or excluded, and scores every record of the review. The suggestions are personal:
they learn from nobody else's decisions, so blind screening hides nothing more or less. They
open at learn.MIN_DECISIONS decisions (learn.MIN_EACH of each kind) and are computed when the
reviewer asks, in the worker, as each run reads the whole review."""
from __future__ import annotations

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from krinea_api import models
from krinea_core import learn

STAGE = "ta"


def _my_decisions(db: Session, review_id: str, user_id: str) -> list:
    """The reviewer's inclusions and exclusions at title/abstract, duplicates aside."""
    return db.execute(select(models.Decision.record_id, models.Decision.decision, models.Decision.reason,
                             models.Decision.decided_at)
                      .join(models.Record, models.Record.id == models.Decision.record_id)
                      .where(models.Decision.review_id == review_id, models.Decision.stage == STAGE,
                             models.Decision.reviewer == user_id,
                             models.Decision.decision.in_(("include", "exclude")),
                             models.Record.is_duplicate.is_(False))).all()


def _ready(n_inc: int, n_exc: int) -> bool:
    return n_inc + n_exc >= learn.MIN_DECISIONS and min(n_inc, n_exc) >= learn.MIN_EACH


def status(db: Session, review_id: str, user_id: str) -> dict:
    """What the reviewer's suggestions can learn from now, and their last run: what it learned
    from, how well it ranks, and how many decisions were made or changed since."""
    mine = _my_decisions(db, review_id, user_id)
    n_inc = sum(1 for d in mine if d.decision == "include")
    n_exc = len(mine) - n_inc
    run = db.scalar(select(models.LearnedRun).where(models.LearnedRun.review_id == review_id,
                                                    models.LearnedRun.user_id == user_id))
    last = None
    if run:
        last = {"n_include": run.n_include, "n_exclude": run.n_exclude, "auc": run.auc,
                "include_terms": run.include_terms or [], "exclude_terms": run.exclude_terms or [],
                "created_at": run.created_at}
    return {"n_include": n_inc, "n_exclude": n_exc, "min_decisions": learn.MIN_DECISIONS,
            "min_each": learn.MIN_EACH, "ready": _ready(n_inc, n_exc),
            "new_since": sum(1 for d in mine if d.decided_at > run.created_at) if run else 0, "run": last}


def run(db: Session, review_id: str, user_id: str) -> dict:
    """Learns from the reviewer's decisions and scores every record of the review (duplicates
    aside), replacing their previous scores. The run is dated from its start: decisions made
    while it goes on count as new."""
    started = models.now()
    rows = db.execute(select(models.Record.id, models.Record.title, models.Record.keywords, models.Record.abstract)
                      .where(models.Record.review_id == review_id, models.Record.is_duplicate.is_(False))
                      .order_by(models.Record.id)).all()
    index = {rid: i for i, (rid, *_rest) in enumerate(rows)}
    labels: dict[int, bool] = {}
    reasons: dict[int, str] = {}
    for rid, decision, reason, _at in _my_decisions(db, review_id, user_id):
        if rid in index:
            labels[index[rid]] = decision == "include"
            if decision == "exclude" and reason:
                reasons[index[rid]] = reason
    n_inc = sum(labels.values())
    n_exc = len(labels) - n_inc
    if not _ready(n_inc, n_exc):
        raise ValueError(f"Suggestions need {learn.MIN_DECISIONS} inclusions or exclusions, at least "
                         f"{learn.MIN_EACH} of each (you have {n_inc} and {n_exc})")
    res = learn.learn([learn.record_text(t or "", k or "", a or "") for _, t, k, a in rows], labels, reasons)
    db.execute(delete(models.LearnedScore).where(models.LearnedScore.review_id == review_id,
                                                 models.LearnedScore.user_id == user_id))
    if rows:
        db.execute(insert(models.LearnedScore), [
            {"review_id": review_id, "user_id": user_id, "record_id": rid, "score": round(s, 4), "reason": r[:200]}
            for (rid, *_rest), s, r in zip(rows, res.scores, res.reasons)])
    last = db.scalar(select(models.LearnedRun).where(models.LearnedRun.review_id == review_id,
                                                     models.LearnedRun.user_id == user_id))
    if not last:
        last = models.LearnedRun(review_id=review_id, user_id=user_id)
        db.add(last)
    last.n_include, last.n_exclude, last.auc = n_inc, n_exc, res.auc
    last.include_at, last.exclude_at = res.include_at, res.exclude_at
    last.include_terms, last.exclude_terms = res.include_terms, res.exclude_terms
    last.created_at = started
    db.commit()
    return {"n_include": n_inc, "n_exclude": n_exc, "auc": res.auc, "scored": len(rows)}


def scores(db: Session, review_id: str, user_id: str, ids: list[int] | None = None) -> dict[int, dict]:
    """The reviewer's learned suggestion of each record (of `ids`, or all), read with the
    boundaries of their last run."""
    run = db.scalar(select(models.LearnedRun).where(models.LearnedRun.review_id == review_id,
                                                    models.LearnedRun.user_id == user_id))
    if not run:
        return {}
    q = select(models.LearnedScore.record_id, models.LearnedScore.score, models.LearnedScore.reason).where(
        models.LearnedScore.review_id == review_id, models.LearnedScore.user_id == user_id)
    if ids is not None:
        if not ids:
            return {}
        q = q.where(models.LearnedScore.record_id.in_(ids))
    return {rid: {"score": s, "decision": learn.suggestion(s, run.include_at, run.exclude_at), "reason": r}
            for rid, s, r in db.execute(q)}
