"""Duplicate detection for a review, on top of krinea_core.dedup."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete, or_, select, update
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


KEEPER_RULES = ("complete", "file", "database")


@dataclass(frozen=True)
class KeepRule:
    """How a review chooses the record to keep among duplicates: by imported file, by
    database, or (both empty) the most complete record."""
    files: tuple[str, ...] = ()
    databases: tuple[str, ...] = ()


def keeper_rule(settings: dict | None) -> str:
    """complete | file | database. A review that saved a source order before the rule existed
    keeps using it."""
    s = settings or {}
    if s.get("keeper_rule") in KEEPER_RULES:
        return s["keeper_rule"]
    return "database" if s.get("source_priority") else "complete"


def priority(review: models.Review) -> KeepRule:
    s = review.settings or {}
    rule = keeper_rule(s)
    if rule == "file":
        return KeepRule(files=tuple(str(f) for f in s.get("file_priority") or [] if str(f)))
    if rule == "database":
        return KeepRule(databases=tuple(str(x).strip() for x in s.get("source_priority") or [] if str(x).strip()))
    return KeepRule()


def _keep(records: list[dict], idxs, rule: KeepRule | None) -> int:
    rule = rule or KeepRule()
    return core.choose_keeper(records, idxs, list(rule.databases), list(rule.files))


def _as_dicts(db: Session, *recs: models.Record) -> list[dict]:
    out = []
    for r in recs:
        imp = db.get(models.Import, r.import_id) if r.import_id else None
        out.append({f: getattr(r, f) for f in FIELDS} | {"id": r.id, "import_id": r.import_id,
                                                          "origin_source": imp.source_db if imp else ""})
    return out


def suggested_keep(db: Session, ra: models.Record, rb: models.Record, rule: KeepRule) -> int:
    """Id of the record the review's rule would keep in a pair."""
    both = _as_dicts(db, ra, rb)
    return both[_keep(both, [0, 1], rule)]["id"]


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


def _own_source(db: Session, rec: models.Record) -> str:
    """The source a record was imported with: the one matching its import's label, otherwise
    the first it lists (a kept record lists its own source first)."""
    tokens = [s.strip() for s in str(rec.source_db or "").split(";") if s.strip()]
    imp = db.get(models.Import, rec.import_id) if rec.import_id else None
    label = (imp.source_db or "").strip().lower() if imp else ""
    return next((t for t in tokens if label and t.lower() == label), tokens[0] if tokens else "")


def _keep_original(db: Session, keeper_id: int) -> None:
    """Remembers a record's own values before a merge first fills its gaps."""
    if db.get(models.RecordOriginal, keeper_id) is not None:
        return
    row = db.execute(select(models.Record.review_id, *[getattr(models.Record, f) for f in FIELDS])
                     .where(models.Record.id == keeper_id)).first()
    if row:
        db.add(models.RecordOriginal(record_id=keeper_id, review_id=row[0], values=dict(zip(FIELDS, row[1:]))))
        db.flush()


def rebuild(db: Session, rec: models.Record) -> None:
    """A kept record, recomputed from its own values and the duplicates still merged into it;
    back to its own values when none is left. Records merged before originals were kept only
    get their list of sources put right."""
    orig = db.get(models.RecordOriginal, rec.id)
    dups = db.scalars(select(models.Record).where(models.Record.duplicate_of == rec.id)
                      .order_by(models.Record.id)).all()
    if orig is None:
        sources = [_own_source(db, rec)] + [s for d in dups for s in str(d.source_db or "").split(";")]
        rec.source_db = "; ".join(dict.fromkeys(s.strip() for s in sources if s.strip()))
        return
    values = dict(orig.values)
    if dups:
        group = [values] + [{f: getattr(d, f) for f in FIELDS} for d in dups]
        values = core.merge_records(group, 0, list(range(len(group))))
    else:
        db.delete(orig)
    for f in FIELDS:
        if f in values:
            setattr(rec, f, values[f])


def reset(db: Session, review_id: str) -> int:
    """Forgets every merge of the review: duplicates come back, kept records get their own
    values back, pairs to check are cleared. Pairs answered "different" stay answered.
    Returns how many records came back."""
    keepers = set(db.scalars(select(models.Record.duplicate_of).where(
        models.Record.review_id == review_id, models.Record.is_duplicate.is_(True),
        models.Record.duplicate_of.is_not(None))))
    n = db.execute(update(models.Record).where(models.Record.review_id == review_id,
                                               models.Record.is_duplicate.is_(True))
                   .values(is_duplicate=False, duplicate_of=None, dup_score=None, dup_reason="")).rowcount
    db.execute(update(models.Record).where(models.Record.review_id == review_id)
               .values(duplicate_of=None, dup_score=None, dup_reason=""))
    db.flush()
    with_original = set(db.scalars(select(models.RecordOriginal.record_id)
                                   .where(models.RecordOriginal.review_id == review_id)))
    for rid in keepers | with_original:
        rec = db.get(models.Record, rid)
        if rec is not None:
            rebuild(db, rec)
    db.execute(delete(models.DedupCandidate).where(models.DedupCandidate.review_id == review_id,
                                                   models.DedupCandidate.status != "ignored"))
    db.flush()
    return int(n or 0)


def mark(db: Session, keeper_id: int, dup_ids: list[int], score: float, reason: str,
         merged: dict | None = None) -> None:
    for d in dup_ids:
        if d == keeper_id:
            continue
        db.execute(update(models.Record).where(models.Record.id == d)
                   .values(is_duplicate=True, duplicate_of=keeper_id, dup_score=score, dup_reason=reason[:200]))
        db.execute(update(models.Record).where(models.Record.duplicate_of == d).values(duplicate_of=keeper_id))
    if merged:
        _keep_original(db, keeper_id)
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
    keeper_of: dict[int, int] = {}
    for g in groups:
        keeper = _keep(records, g, prio)
        keeper_of.update({i: keeper for i in g})
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
    # A near match of a record merged away is a near match of the record it was merged into:
    # the pair is asked about the kept record, once, with the best score found.
    best: dict[tuple[int, int], core.Pair] = {}
    for p in possible:
        a, b = keeper_of.get(p.a, p.a), keeper_of.get(p.b, p.b)
        if a == b:
            continue
        key = (min(ids[a], ids[b]), max(ids[a], ids[b]))
        if key not in best or p.score > best[key].score:
            best[key] = p
    n_possible = 0
    for (a, b), p in sorted(best.items()):
        if (a, b) in ignored:
            continue
        db.add(models.DedupCandidate(review_id=review.id, record_a=a, record_b=b, score=p.score, reason=p.reason[:200]))
        n_possible += 1
    db.add(models.ActivityLog(review_id=review.id, user_id=user_id, kind="dedup",
                              detail={"removed": removed, "groups": len(groups), "possible": n_possible}))
    db.commit()
    return {"records": len(records), "removed": removed, "groups": len(groups), "possible": n_possible}


def merge_candidate(db: Session, cand: models.DedupCandidate, keep_id: int | None = None,
                    prio: KeepRule | None = None) -> None:
    """Merges a pair: `keep_id` (one of the two records) is kept when given, otherwise the
    review's rule chooses. The kept record's empty fields are filled from the other one."""
    ra, rb = db.get(models.Record, cand.record_a), db.get(models.Record, cand.record_b)
    if not ra or not rb:
        cand.status = "ignored"
        db.commit()
        return
    both = _as_dicts(db, ra, rb)
    keeper = ([r["id"] for r in both].index(keep_id) if keep_id in (ra.id, rb.id)
              else _keep(both, [0, 1], prio))
    merged = core.merge_records(both, keeper, [0, 1])
    mark(db, both[keeper]["id"], [both[1 - keeper]["id"]], cand.score, cand.reason, merged)
    cand.status = "merged"
    _repoint(db, cand, gone=both[1 - keeper]["id"], kept=both[keeper]["id"])
    db.commit()


def _repoint(db: Session, done: models.DedupCandidate, gone: int, kept: int) -> None:
    """After `gone` is merged into `kept`, the pending pairs that involved `gone` concern
    `kept`: a third (fourth...) near match is then asked about the kept record."""
    pending = db.scalars(select(models.DedupCandidate).where(
        models.DedupCandidate.review_id == done.review_id, models.DedupCandidate.status == "pending",
        models.DedupCandidate.id != done.id,
        or_(models.DedupCandidate.record_a == gone, models.DedupCandidate.record_b == gone))).all()
    for c in pending:
        other = c.record_b if c.record_a == gone else c.record_a
        a, b = min(kept, other), max(kept, other)
        existing = None if other == kept else db.scalar(select(models.DedupCandidate).where(
            models.DedupCandidate.record_a == a, models.DedupCandidate.record_b == b))
        if other == kept or existing is not None:
            if existing is not None and existing.status == "pending" and c.score > existing.score:
                existing.score, existing.reason = c.score, c.reason
            db.delete(c)                     # already asked, or already answered (an ignored pair stays ignored)
        else:
            c.record_a, c.record_b = a, b
        db.flush()


def ignore_candidate(db: Session, cand: models.DedupCandidate) -> None:
    cand.status = "ignored"
    db.commit()


def restore(db: Session, record: models.Record) -> None:
    """Brings one duplicate back; the record it had been merged into is recomputed without it."""
    keeper_id = record.duplicate_of
    record.is_duplicate, record.duplicate_of, record.dup_score, record.dup_reason = False, None, None, ""
    db.flush()
    keeper = db.get(models.Record, keeper_id) if keeper_id else None
    if keeper is not None:
        rebuild(db, keeper)
    if db.get(models.RecordOriginal, record.id) is not None:     # it had been kept itself, earlier
        rebuild(db, record)
    db.commit()
