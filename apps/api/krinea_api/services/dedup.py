"""Duplicate detection for a review, on top of krinea_core.dedup."""
from __future__ import annotations

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from krinea_api import models
from krinea_core import biblio, dedup as core

FIELDS = biblio.RECORD_FIELDS


def _import_sources(db: Session, review_id: str) -> dict[str, str]:
    """Source label given at import time, per import (empty when none was typed)."""
    return dict(db.execute(select(models.Import.id, models.Import.source_db)
                           .where(models.Import.review_id == review_id)).all())


def _record_dicts(db: Session, review_id: str) -> list[dict]:
    cols = [getattr(models.Record, f) for f in FIELDS]
    labels = _import_sources(db, review_id)
    rows = db.execute(select(models.Record.id, models.Record.import_id, *cols)
                      .where(models.Record.review_id == review_id).order_by(models.Record.id)).all()
    return [dict(zip(["id", "import_id"] + FIELDS, r)) | {"origin_source": labels.get(r[1]) or ""} for r in rows]


def priority(review: models.Review) -> list[str]:
    """The review's source order for choosing which duplicate to keep (empty: completeness only)."""
    return [str(s).strip() for s in (review.settings or {}).get("source_priority") or [] if str(s).strip()]


def _as_dicts(db: Session, *recs: models.Record) -> list[dict]:
    out = []
    for r in recs:
        imp = db.get(models.Import, r.import_id) if r.import_id else None
        out.append({f: getattr(r, f) for f in FIELDS} | {"id": r.id, "origin_source": imp.source_db if imp else ""})
    return out


def suggested_keep(db: Session, ra: models.Record, rb: models.Record, prio: list[str]) -> int:
    """Id of the record the rule would keep in a pair (source order, then completeness)."""
    both = _as_dicts(db, ra, rb)
    return both[core.choose_keeper(both, [0, 1], prio)]["id"]


def sources(db: Session, review_id: str) -> list[dict]:
    """Sources present in the review, with how many unique records carry each."""
    counts: dict[str, int] = {}
    names: dict[str, str] = {}
    for (src,) in db.execute(select(models.Record.source_db).where(models.Record.review_id == review_id,
                                                                    models.Record.is_duplicate.is_(False))):
        for s in str(src or "").split(";"):
            s = s.strip()
            if s:
                counts[s.lower()] = counts.get(s.lower(), 0) + 1
                names.setdefault(s.lower(), s)
    return [{"source": names[k], "n": n} for k, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]


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
    prio = priority(review)
    removed = 0
    for g in groups:
        keeper = core.choose_keeper(records, g, prio)
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


def merge_candidate(db: Session, cand: models.DedupCandidate, keep_id: int | None = None,
                    prio: list[str] | None = None) -> None:
    """Merges a pair: `keep_id` (one of the two records) is kept when given, otherwise the
    review's rule chooses. The kept record's empty fields are filled from the other one."""
    ra, rb = db.get(models.Record, cand.record_a), db.get(models.Record, cand.record_b)
    if not ra or not rb:
        cand.status = "ignored"
        db.commit()
        return
    both = _as_dicts(db, ra, rb)
    keeper = ([r["id"] for r in both].index(keep_id) if keep_id in (ra.id, rb.id)
              else core.choose_keeper(both, [0, 1], prio))
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
