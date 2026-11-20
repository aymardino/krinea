"""Screening status, summaries and keyword counts for a review."""
from __future__ import annotations

import datetime as dt
import re
from collections import defaultdict

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from krinea_api import models
from krinea_api.deps import ROLE_RANK
from krinea_core import screening as core

STAGES = ("ta", "ft")


def is_blind(review: models.Review, role: str) -> bool:
    """Whether a member with this role sees only their own decisions: every role below admin,
    in a blind review."""
    return bool((review.settings or {}).get("blind", True)) and ROLE_RANK[role] < ROLE_RANK["admin"]


def labels_of(text: str) -> set[str]:
    """The labels of a record, lower-cased ("SQ1; costs" gives {"sq1", "costs"})."""
    return {x.strip().lower() for x in re.split(r"[;,]", text or "") if x.strip()}


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


def found_in_import(review_id: str, import_id: str):
    """Records found by a search (an imported file): its own records, and the records its
    duplicates were merged into."""
    merged_into = (select(models.Record.duplicate_of)
                   .where(models.Record.review_id == review_id, models.Record.import_id == import_id,
                          models.Record.is_duplicate.is_(True), models.Record.duplicate_of.is_not(None)))
    return or_(models.Record.import_id == import_id, models.Record.id.in_(merged_into))


def by_kept_file(review: models.Review) -> bool:
    """Whether each record belongs to one file only, that of the copy kept among duplicates:
    when the review keeps duplicates by file order (one file per search, each with its own
    criteria; D-42)."""
    return (review.settings or {}).get("keeper_rule") == "file"


def in_file(review: models.Review, import_id: str):
    """The records that count for an imported file: those kept from it when the review keeps
    duplicates by file order, else every record the file found, merged duplicates included."""
    if by_kept_file(review):
        return models.Record.import_id == import_id
    return found_in_import(review.id, import_id)


def search_keywords(review: models.Review) -> dict[str, dict[str, list[str]]]:
    """Highlight keywords that belong to one search (imported file), by import id."""
    raw = (review.criteria or {}).get("search_keywords") or {}
    return {str(k): {"include": list(v.get("include") or []), "exclude": list(v.get("exclude") or [])}
            for k, v in raw.items() if isinstance(v, dict)}


def keyword_filter(kws: list[str], mode: str = "all"):
    """A test on a record: does its title, abstract or keywords mention all of `kws` (or at
    least one, with mode "any")? Keywords match as they are counted: whole words, * as a
    wildcard, so a keyword shown with 90 records filters those 90."""
    rxs = [_kw_regex(k) for k in core.parse_keywords(kws)]
    test = any if mode == "any" else all

    def match(rec: models.Record) -> bool:
        text = f"{rec.title or ''}\n{rec.abstract or ''}\n{rec.keywords or ''}"
        return test(rx.search(text) for rx in rxs)
    return match


def _counts(texts: list[str], kws: list[str]) -> list[dict]:
    out = []
    for kw in kws:
        rx = _kw_regex(kw)
        out.append({"keyword": kw, "n": sum(1 for t in texts if rx.search(t))})
    return out


def keyword_counts(db: Session, review: models.Review, import_id: str = "") -> dict:
    """How many unique records mention each highlight keyword (title + abstract + keywords).
    With `import_id`, the keywords of that search are also counted, over its own records."""
    crit = core.criteria_with_defaults(review.criteria or {})
    inc = core.parse_keywords(crit["highlight_include"])
    exc = core.parse_keywords(crit["highlight_exclude"])
    own = search_keywords(review).get(import_id, {}) if import_id else {}
    s_inc, s_exc = core.parse_keywords(own.get("include") or []), core.parse_keywords(own.get("exclude") or [])
    out: dict = {"include": [], "exclude": []}
    base = select(models.Record.title, models.Record.abstract, models.Record.keywords).where(
        models.Record.review_id == review.id, models.Record.is_duplicate.is_(False))
    if inc or exc:
        texts = [f"{t}\n{a}\n{k}" for t, a, k in db.execute(base).all()]
        out = {"include": _counts(texts, inc), "exclude": _counts(texts, exc)}
    if import_id:
        texts = [f"{t}\n{a}\n{k}" for t, a, k in db.execute(base.where(in_file(review, import_id))).all()] \
            if (s_inc or s_exc) else []
        out["search"] = {"include": _counts(texts, s_inc), "exclude": _counts(texts, s_exc)}
    return out


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
