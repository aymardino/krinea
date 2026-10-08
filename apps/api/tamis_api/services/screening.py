"""Screening status, summaries and keyword counts for a review."""
from __future__ import annotations

import datetime as dt
import re
from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tamis_api import models
from tamis_core import screening as core

STAGES = ("ta", "ft")


def required_reviewers(review: models.Review) -> int:
    try:
        return max(1, int((review.settings or {}).get("required_reviewers", 1)))
    except (TypeError, ValueError):
        return 1


def decisions_by_record(db: Session, review_id: str) -> dict[str, dict[int, dict[str, models.Decision]]]:
    """{stage: {record_id: {reviewer: Decision}}} for the whole review."""
    out: dict[str, dict[int, dict[str, models.Decision]]] = {s: defaultdict(dict) for s in STAGES}
    for d in db.scalars(select(models.Decision).where(models.Decision.review_id == review_id)):
        out[d.stage][d.record_id][d.reviewer] = d
    return out


def status_of(decs: dict[str, models.Decision], required: int) -> str:
    return core.consensus({k: v.decision for k, v in decs.items()}, required)


def unique_ids(db: Session, review_id: str) -> list[int]:
    return list(db.scalars(select(models.Record.id).where(models.Record.review_id == review_id,
                                                           models.Record.is_duplicate.is_(False))
                           .order_by(models.Record.id)))


def compute(db: Session, review: models.Review) -> dict:
    """Everything the screening views need, computed once:
    pools, statuses per stage, decisions, per-record reasons."""
    required = required_reviewers(review)
    decs = decisions_by_record(db, review.id)
    ids = unique_ids(db, review.id)
    ta_status = {rid: status_of(decs["ta"].get(rid, {}), required) for rid in ids}
    ft_pool = [rid for rid in ids if ta_status[rid] == "include"]
    ft_status = {rid: status_of(decs["ft"].get(rid, {}), required) for rid in ft_pool}
    extract_pool = [rid for rid in ft_pool if ft_status[rid] == "include"]
    return {"required": required, "decisions": decs, "unique_ids": ids, "ta_status": ta_status,
            "ft_pool": ft_pool, "ft_status": ft_status, "extract_pool": extract_pool}


def pool_ids(computed: dict, stage: str) -> list[int]:
    return {"ta": computed["unique_ids"], "ft": computed["ft_pool"], "extract": computed["extract_pool"]}[stage]


def first_reason(decs: dict[str, models.Decision]) -> str:
    if "consensus" in decs and decs["consensus"].reason:
        return decs["consensus"].reason
    for d in decs.values():
        if d.decision == "exclude" and d.reason:
            return d.reason
    return ""


def summary(db: Session, review: models.Review, user: models.User | None) -> dict:
    c = compute(db, review)
    total = db.scalar(select(func.count(models.Record.id)).where(models.Record.review_id == review.id)) or 0
    n_unique = len(c["unique_ids"])
    out = {"records": int(total), "duplicates": int(total - n_unique), "unique": n_unique,
           "required_reviewers": c["required"], "stages": {}}
    members = {m.user_id: m for m in db.scalars(select(models.Membership).where(models.Membership.review_id == review.id))}
    users = {u.id: u for u in db.scalars(select(models.User).where(models.User.id.in_(list(members))))} if members else {}
    for stage in STAGES:
        pool = pool_ids(c, stage)
        status = c["ta_status"] if stage == "ta" else c["ft_status"]
        counts = defaultdict(int)
        for rid in pool:
            counts[status[rid]] += 1
        per_reviewer = defaultdict(lambda: {"include": 0, "maybe": 0, "exclude": 0, "seconds": 0.0})
        for rid in pool:
            for reviewer, d in c["decisions"][stage].get(rid, {}).items():
                if reviewer == "consensus":
                    continue
                per_reviewer[reviewer][d.decision] += 1
                per_reviewer[reviewer]["seconds"] += float(d.seconds or 0)
        reviewers = []
        for uid, m in members.items():
            r = per_reviewer.get(uid, {"include": 0, "maybe": 0, "exclude": 0, "seconds": 0.0})
            done = r["include"] + r["maybe"] + r["exclude"]
            reviewers.append({"user_id": uid, "name": users[uid].name if uid in users else "",
                              "email": users[uid].email if uid in users else "", "role": m.role,
                              "done": done, "left": max(0, len(pool) - done), "seconds": round(r["seconds"]),
                              **{k: r[k] for k in ("include", "maybe", "exclude")}})
        mine = per_reviewer.get(user.id) if user else None
        my_done = (mine["include"] + mine["maybe"] + mine["exclude"]) if mine else 0
        out["stages"][stage] = {
            "pool": len(pool), **{k: counts.get(k, 0) for k in ("pending", "include", "maybe", "exclude", "conflict")},
            "my_done": my_done, "my_left": max(0, len(pool) - my_done),
            "my_seconds": round(mine["seconds"]) if mine else 0, "reviewers": reviewers,
        }
    ex = db.execute(select(models.Extraction.status, func.count()).where(models.Extraction.review_id == review.id)
                    .group_by(models.Extraction.status)).all()
    out["extraction"] = {"pool": len(c["extract_pool"]), **{s: int(n) for s, n in ex}}
    out["pdfs"] = {
        "available": int(db.scalar(select(func.count()).where(models.Record.review_id == review.id,
                                                               models.Record.pdf_status == "available")) or 0),
        "not_retrieved": int(db.scalar(select(func.count()).where(models.Record.review_id == review.id,
                                                                   models.Record.pdf_status == "not_retrieved")) or 0),
    }
    return out


def _kw_regex(kw: str) -> re.Pattern:
    parts = [re.escape(p) for p in kw.split("*")]
    body = r"\w*".join(parts)
    return re.compile((rf"\b{body}\b" if not kw.endswith("*") else rf"\b{body}"), re.I)


def keyword_counts(db: Session, review: models.Review) -> dict:
    """How many unique records mention each highlight keyword (title + abstract + keywords)."""
    crit = core.criteria_with_defaults(review.criteria or {})
    inc = core.parse_keywords(crit["highlight_include"])
    exc = core.parse_keywords(crit["highlight_exclude"])
    if not inc and not exc:
        return {"include": [], "exclude": []}
    rows = db.execute(select(models.Record.id, models.Record.title, models.Record.abstract, models.Record.keywords)
                      .where(models.Record.review_id == review.id, models.Record.is_duplicate.is_(False))).all()
    texts = [f"{t}\n{a}\n{k}" for _, t, a, k in rows]
    def count(kws):
        out = []
        for kw in kws:
            rx = _kw_regex(kw)
            out.append({"keyword": kw, "n": sum(1 for t in texts if rx.search(t))})
        return out
    return {"include": count(inc), "exclude": count(exc)}


def activity(db: Session, review_id: str, limit: int = 30) -> list[dict]:
    rows = db.execute(select(models.ActivityLog, models.User.name, models.User.email)
                      .join(models.User, models.User.id == models.ActivityLog.user_id, isouter=True)
                      .where(models.ActivityLog.review_id == review_id)
                      .order_by(models.ActivityLog.created_at.desc()).limit(limit)).all()
    return [{"kind": a.kind, "detail": a.detail, "at": a.created_at.isoformat(), "user": name or email or ""}
            for a, name, email in rows]


def throughput(db: Session, review_id: str, days: int = 30) -> list[dict]:
    since = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) - dt.timedelta(days=days)
    rows = db.execute(select(models.Decision.decided_at, models.Decision.reviewer, models.Decision.stage)
                      .where(models.Decision.review_id == review_id, models.Decision.decided_at >= since)).all()
    per_day: dict[str, dict] = defaultdict(lambda: defaultdict(int))
    for at, reviewer, stage in rows:
        per_day[at.date().isoformat()][f"{stage}:{reviewer}"] += 1
    return [{"day": day, **dict(v)} for day, v in sorted(per_day.items())]
