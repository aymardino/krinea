"""Duplicate detection for a review, on top of krinea_core.dedup."""
from __future__ import annotations

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from krinea_api import models
from krinea_core import biblio, dedup as core

FIELDS = biblio.RECORD_FIELDS


def _record_dicts(db: Session, review_id: str) -> list[dict]:
    cols = [getattr(models.Record, f) for f in FIELDS]
    rows = db.execute(select(models.Record.id, *cols).where(models.Record.review_id == review_id)
                      .order_by(models.Record.id)).all()
    return [dict(zip(["id"] + FIELDS, r)) for r in rows]


def reset(db: Session, review_id: str) -> None:
    db.execute(update(models.Record).where(models.Record.review_id == review_id)
               .values(is_duplicate=False, duplicate_of=None, dup_score=None, dup_reason=""))
    db.execute(delete(models.DedupCandidate).where(models.DedupCandidate.review_id == review_id,
                                                   models.DedupCandidate.status != "ignored"))


def mark(db: Session, keeper_id: int, dup_ids: list[int], score: float, reason: str,
         merged: dict | None = None) -> None:
    for d in dup_ids:
        if d == keeper_id:
            continue
        db.execute(update(models.Record).where(models.Record.id == d)
                   .values(is_duplicate=True, duplicate_of=keeper_id, dup_score=score, dup_reason=reason[:200]))
        db.execute(update(models.Record).where(models.Record.duplicate_of == d).values(duplicate_of=keeper_id))
    if merged:
        db.execute(update(models.Record).where(models.Record.id == keeper_id)
                   .values({f: merged[f] for f in FIELDS if f in merged}))


def run(db: Session, review: models.Review, auto_threshold: float = 95.0,
        review_threshold: float = 85.0, user_id: str | None = None) -> dict:
    reset(db, review.id)
    db.flush()
    records = _record_dicts(db, review.id)
    ids = [r["id"] for r in records]
    pairs = core.find_duplicates(records, auto_threshold, review_threshold)
    certain = [p for p in pairs if p.certain]
    info = {(p.a, p.b): p for p in certain}
    groups = core.cluster(certain, len(records))
    removed = 0
    for g in groups:
        keeper = core.choose_keeper(records, g)
        for i in g:
            if i == keeper:
                continue
            pr = info.get((min(i, keeper), max(i, keeper)))
            mark(db, ids[keeper], [ids[i]], pr.score if pr else 100.0, pr.reason if pr else "duplicate group")
            removed += 1
        mark(db, ids[keeper], [], 100.0, "", core.merge_records(records, keeper, g))
    possible = [p for p in pairs if not p.certain]
    ignored = {(c.record_a, c.record_b) for c in db.scalars(
        select(models.DedupCandidate).where(models.DedupCandidate.review_id == review.id,
                                            models.DedupCandidate.status == "ignored"))}
    n_possible = 0
    for p in possible:
        a, b = sorted((ids[p.a], ids[p.b]))
        if (a, b) in ignored:
            continue
        db.add(models.DedupCandidate(review_id=review.id, record_a=a, record_b=b, score=p.score, reason=p.reason[:200]))
        n_possible += 1
    db.add(models.ActivityLog(review_id=review.id, user_id=user_id, kind="dedup",
                              detail={"removed": removed, "groups": len(groups), "possible": n_possible}))
    db.commit()
    return {"records": len(records), "removed": removed, "groups": len(groups), "possible": n_possible}


def merge_candidate(db: Session, cand: models.DedupCandidate) -> None:
    ra, rb = db.get(models.Record, cand.record_a), db.get(models.Record, cand.record_b)
    if not ra or not rb:
        cand.status = "ignored"
        db.commit()
        return
    both = [{f: getattr(r, f) for f in FIELDS} | {"id": r.id} for r in (ra, rb)]
    keeper = core.choose_keeper(both, [0, 1])
    merged = core.merge_records(both, keeper, [0, 1])
    mark(db, both[keeper]["id"], [both[1 - keeper]["id"]], cand.score, cand.reason, merged)
    cand.status = "merged"
    db.commit()


def ignore_candidate(db: Session, cand: models.DedupCandidate) -> None:
    cand.status = "ignored"
    db.commit()


def restore(db: Session, record: models.Record) -> None:
    record.is_duplicate, record.duplicate_of, record.dup_score, record.dup_reason = False, None, None, ""
    db.commit()
