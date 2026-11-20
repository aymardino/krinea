"""Records of a review: imports, listing with screening views, decisions, PDFs, duplicates."""
from __future__ import annotations

import io
import re
import unicodedata
import urllib.parse

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session as DBSession

from krinea_api import models, schemas
from krinea_api.config import get_settings
from krinea_api.db import get_db
from krinea_api.deps import ROLE_RANK, ReviewAccess, current_user, log_activity
from krinea_api.services import dedup as dedup_service
from krinea_api.services import imports as import_service
from krinea_api.services import jobs as job_service
from krinea_api.services import screening as scr
from krinea_api.services import storage

router = APIRouter(prefix="/reviews/{review_id}", tags=["records"])

VIEWS = ("todo", "mine_include", "mine_maybe", "mine_exclude", "include", "maybe", "exclude",
         "conflict", "pending", "all", "no_pdf", "not_retrieved")
# Orders of the record lists (`sort`): "import" is the order of the imported files.
SORTS = ("import", "title", "title_desc", "year_desc", "year", "author", "journal", "ai", "ai_exclude")


# ── Imports ──────────────────────────────────────────────────────────────────────
@router.post("/imports", status_code=201)
async def upload_imports(files: list[UploadFile] = File(...), source_db: str = Form(""),
                         access=Depends(ReviewAccess("admin")), user: models.User = Depends(current_user),
                         db: DBSession = Depends(get_db)):
    review, _ = access
    limit = get_settings().max_upload_mb * 1024 * 1024
    out = []
    for f in files:
        data = await f.read()
        if len(data) > limit:
            out.append({"filename": f.filename, "error": f"File larger than {get_settings().max_upload_mb} MB"})
            continue
        try:
            imp = import_service.import_file(db, review, user, f.filename or "export", data, source_db)
            out.append({"id": imp.id, "filename": imp.filename, "format": imp.format, "source_db": imp.source_db,
                        "n_records": imp.n_records, "n_skipped": imp.n_skipped, "created_at": imp.created_at})
        except Exception as e:                     # noqa: BLE001
            db.rollback()
            out.append({"filename": f.filename, "error": f"{type(e).__name__}: {e}"})
    return out


@router.get("/imports")
def list_imports(access=Depends(ReviewAccess("viewer")), db: DBSession = Depends(get_db)):
    review, _ = access
    rows = db.scalars(select(models.Import).where(models.Import.review_id == review.id)
                      .order_by(models.Import.created_at)).all()
    dups = dict(db.execute(select(models.Record.import_id, func.count()).where(models.Record.review_id == review.id,
                                                                             models.Record.is_duplicate.is_(True))
                           .group_by(models.Record.import_id)).all())
    return [{"id": i.id, "filename": i.filename, "format": i.format, "source_db": i.source_db,
             "n_records": i.n_records, "n_skipped": i.n_skipped, "n_duplicates": int(dups.get(i.id, 0)),
             "created_at": i.created_at} for i in rows]


@router.delete("/imports/{import_id}")
def delete_import(import_id: str, access=Depends(ReviewAccess("admin")), user: models.User = Depends(current_user),
                  db: DBSession = Depends(get_db)):
    review, _ = access
    imp = db.get(models.Import, import_id)
    if not imp or imp.review_id != review.id:
        raise HTTPException(404, "Import not found")
    n = import_service.delete_import(db, review, imp)
    crit = dict(review.criteria or {})
    sk = dict(crit.get("search_keywords") or {})
    if sk.pop(import_id, None) is not None:                # the search's own keywords go with it
        review.criteria = {**crit, "search_keywords": sk}
    settings = dict(review.settings or {})
    if import_id in (settings.get("file_priority") or []):   # and its place in the file order
        review.settings = {**settings, "file_priority": [f for f in settings["file_priority"] if f != import_id]}
    log_activity(db, review.id, user.id, "import_deleted", filename=imp.filename, n=n)
    db.commit()
    return {"deleted": n}


def _clean_keywords(value) -> list[str]:
    out: list[str] = []
    for s in value if isinstance(value, list) else []:
        s = str(s).strip()[:100]
        if s and s.lower() not in {o.lower() for o in out}:
            out.append(s)
    return out[:100]


@router.put("/imports/{import_id}/keywords")
def set_search_keywords(import_id: str, body: schemas.SearchKeywordsIn, access=Depends(ReviewAccess("admin")),
                        user: models.User = Depends(current_user), db: DBSession = Depends(get_db)):
    """Highlight keywords of one search (imported file), added to the review's own keywords
    on the records that search found."""
    review, _ = access
    imp = db.get(models.Import, import_id)
    if not imp or imp.review_id != review.id:
        raise HTTPException(404, "Import not found")
    crit = dict(review.criteria or {})
    sk = dict(crit.get("search_keywords") or {})
    entry = {"include": _clean_keywords(body.include), "exclude": _clean_keywords(body.exclude)}
    if entry["include"] or entry["exclude"]:
        sk[import_id] = entry
    else:
        sk.pop(import_id, None)
    review.criteria = {**crit, "search_keywords": sk}
    log_activity(db, review.id, user.id, "search_keywords", filename=imp.filename)
    db.commit()
    return entry


# ── Listing ──────────────────────────────────────────────────────────────────────
_blind = scr.is_blind


def _decision_dict(d: models.Decision, names: dict[str, str]) -> dict:
    return {"reviewer": d.reviewer, "name": names.get(d.reviewer, "consensus" if d.reviewer == "consensus" else ""),
            "decision": d.decision, "reason": d.reason, "note": d.note, "decided_at": d.decided_at.isoformat()}


def record_out(rec: models.Record, computed: dict, user_id: str, blind: bool, names: dict[str, str],
               ai: dict | None, stage: str = "ta", merged_from: list[str] | None = None) -> schemas.RecordOut:
    decs = computed["decisions"]
    ta = computed["ta_status"].get(rec.id, "pending")
    ft = computed["ft_status"].get(rec.id, "pending")
    mine = decs[stage].get(rec.id, {}).get(user_id)
    others = [d for r, d in decs[stage].get(rec.id, {}).items() if r != user_id]
    visible = [] if blind else [_decision_dict(d, names) for d in others]
    if mine:
        visible = [_decision_dict(mine, names)] + visible
    return schemas.RecordOut(
        id=rec.id, title=rec.title, abstract=rec.abstract, authors=rec.authors, year=rec.year,
        journal=rec.journal, volume=rec.volume, issue=rec.issue, pages=rec.pages, doi=rec.doi, url=rec.url,
        keywords=rec.keywords, pmid=rec.pmid, type=rec.type, language=rec.language, source_db=rec.source_db,
        import_id=rec.import_id, is_duplicate=rec.is_duplicate, duplicate_of=rec.duplicate_of,
        dup_score=rec.dup_score, dup_reason=rec.dup_reason, pdf_status=rec.pdf_status,
        has_pdf=bool(rec.pdf_key), labels=rec.labels, notes=rec.notes, ta_status=ta, ft_status=ft,
        my_decision=_decision_dict(mine, names) if mine else None, decisions=visible, ai=ai,
        found_in=list(dict.fromkeys([i for i in [rec.import_id, *(merged_from or [])] if i])))


def _merged_from(db: DBSession, review: models.Review, ids: list[int]) -> dict[int, list[str]]:
    """Imports of the duplicates merged into each record: a record counts for every search
    that found it, unless the review keeps duplicates by file order, where it belongs to its
    own file only (D-42)."""
    out: dict[int, list[str]] = {}
    if not ids or scr.by_kept_file(review):
        return out
    for keeper, imp in db.execute(select(models.Record.duplicate_of, models.Record.import_id)
                                  .where(models.Record.review_id == review.id, models.Record.is_duplicate.is_(True),
                                         models.Record.duplicate_of.in_(ids), models.Record.import_id.is_not(None))):
        out.setdefault(keeper, []).append(imp)
    return out


_labels_of = scr.labels_of


def _names(db: DBSession, review_id: str) -> dict[str, str]:
    rows = db.execute(select(models.User.id, models.User.name, models.User.email)
                      .join(models.Membership, models.Membership.user_id == models.User.id)
                      .where(models.Membership.review_id == review_id)).all()
    return {uid: (name or email) for uid, name, email in rows}


def _ai_map(db: DBSession, review_id: str, stage: str, ids: list[int]) -> dict[int, dict]:
    if not ids:
        return {}
    rows = db.scalars(select(models.AISuggestion).where(models.AISuggestion.review_id == review_id,
                                                        models.AISuggestion.stage == stage,
                                                        models.AISuggestion.record_id.in_(ids))).all()
    return {s.record_id: {"decision": s.decision, "reason": s.reason, "rationale": s.rationale,
                          "confidence": s.confidence, "model": s.model} for s in rows}


def _alpha(text: str | None) -> str:
    """Text as one alphabetises it: accents and case ignored, leading quotes or brackets skipped
    ("“Électricité”" files under e)."""
    text = "".join(ch for ch in unicodedata.normalize("NFKD", text or "") if not unicodedata.combining(ch))
    return re.sub(r"^\W+", "", text.casefold())


def _year(rec: models.Record) -> int | None:
    m = re.match(r"\s*(\d{4})", rec.year or "")
    return int(m.group(1)) if m else None


def _ai_rank(db: DBSession, review_id: str, stage: str, exclude_first: bool = False) -> dict[int, tuple[int, float]]:
    """Records by how likely the AI finds their inclusion: include (most confident first),
    maybe, then exclude (least confident first); or the other way round, exclude first."""
    order = {"exclude": 0, "maybe": 1, "include": 2} if exclude_first else {"include": 0, "maybe": 1, "exclude": 2}
    out: dict[int, tuple[int, float]] = {}
    for rid, decision, confidence in db.execute(
            select(models.AISuggestion.record_id, models.AISuggestion.decision, models.AISuggestion.confidence)
            .where(models.AISuggestion.review_id == review_id, models.AISuggestion.stage == stage)):
        rank = order.get(decision, 1)
        out[rid] = (rank, (confidence or 0.0) if rank == 2 else -(confidence or 0.0))
    return out


def _sorted(db: DBSession, review_id: str, stage: str, rows: list[models.Record], sort: str) -> list[models.Record]:
    """`rows`, given in import order, in the order asked for. Records without the value sorted
    on (no year, no author...) or without an AI suggestion come last, and equal values keep the
    import order, in both directions (Python's sort is stable, reversed too)."""
    if sort == "import":
        return rows
    if sort in ("ai", "ai_exclude"):
        ranks = _ai_rank(db, review_id, stage, exclude_first=sort == "ai_exclude")
        return sorted(rows, key=lambda r: ranks.get(r.id, (3, 0.0)))
    if sort in ("year", "year_desc"):
        keyed = [(_year(r), r) for r in rows]
    elif sort == "author":
        keyed = [(_alpha((r.authors or "").split(";")[0]), r) for r in rows]
    else:
        keyed = [(_alpha(r.journal if sort == "journal" else r.title), r) for r in rows]
    known = sorted((kr for kr in keyed if kr[0] not in (None, "")), key=lambda kr: kr[0],
                   reverse=sort in ("title_desc", "year_desc"))
    return [r for _, r in known] + [r for k, r in keyed if k in (None, "")]


def queue_records(db: DBSession, review: models.Review, user_id: str, stage: str = "ta", view: str = "all",
                  search: str = "", source: str = "", label: str = "", import_id: str = "", year_from: str = "",
                  year_to: str = "", kw: list[str] | None = None, kw_mode: str = "all",
                  sort: str = "import") -> tuple[list[models.Record], dict, str]:
    """Every record of a list as a screening page shows it (view, filters, keywords, order),
    with the screening state of the review and the stage whose decisions count. The record
    list and the AI runs that follow it (D-40) both read it from here."""
    if stage not in ("ta", "ft", "extract", "all") or view not in VIEWS:
        raise HTTPException(400, "Unknown stage or view")
    if sort not in SORTS:
        raise HTTPException(400, f"Unknown sort; use one of {', '.join(SORTS)}")
    kw = kw or []
    c = scr.compute(db, review)
    pool = (db.scalars(select(models.Record.id).where(models.Record.review_id == review.id)).all()
            if stage == "all" else scr.pool_ids(c, stage))
    st_stage = "ft" if stage in ("ft", "extract") else "ta"
    status = c["ft_status"] if st_stage == "ft" else c["ta_status"]
    decs = c["decisions"][st_stage]

    def keep(rid: int) -> bool:
        mine = decs.get(rid, {}).get(user_id)
        s = status.get(rid, "pending")
        if view == "todo":
            return mine is None
        if view.startswith("mine_"):
            return mine is not None and mine.decision == view[5:]
        if view in ("include", "maybe", "exclude", "conflict", "pending"):
            return s == view
        return True

    ids = [rid for rid in pool if keep(rid)]
    q = select(models.Record).where(models.Record.review_id == review.id)
    if stage != "all":
        q = q.where(models.Record.is_duplicate.is_(False))
    if view == "no_pdf":
        q = q.where(models.Record.pdf_key == "")
    if view == "not_retrieved":
        q = q.where(models.Record.pdf_status == "not_retrieved")
    if search.strip():
        like = f"%{search.strip()}%"
        q = q.where(or_(models.Record.title.ilike(like), models.Record.abstract.ilike(like),
                        models.Record.authors.ilike(like), models.Record.doi.ilike(like),
                        models.Record.keywords.ilike(like)))
    if source.strip():
        q = q.where(models.Record.source_db.ilike(f"%{source.strip()}%"))
    if label.strip():
        q = q.where(models.Record.labels.ilike(f"%{label.strip()}%"))
    if import_id:
        # A record found in this file may have been merged into a record from another file: the
        # kept record counts for every file it was found in, or only for its own file when the
        # review keeps duplicates by file order (D-42).
        q = q.where(scr.in_file(review, import_id))
    if year_from.strip():
        q = q.where(models.Record.year >= year_from.strip()[:4])
    if year_to.strip():
        q = q.where(models.Record.year <= year_to.strip()[:4])
    rows = db.scalars(q.order_by(models.Record.id)).all()
    idset = set(ids)
    rows = [r for r in rows if r.id in idset]
    if label.strip():                         # exact label: "SQ1" must not match "SQ10"
        rows = [r for r in rows if label.strip().lower() in _labels_of(r.labels)]
    if any(k.strip() for k in kw):            # highlight keywords picked in the screening rail
        match = scr.keyword_filter(kw, kw_mode)
        rows = [r for r in rows if match(r)]
    return _sorted(db, review.id, st_stage, rows, sort), c, st_stage


@router.get("/records", response_model=schemas.RecordPage)
def list_records(stage: str = "ta", view: str = "all", search: str = "", source: str = "", label: str = "",
                 import_id: str = "", year_from: str = "", year_to: str = "", cursor: int = 0,
                 offset: int = Query(0, ge=0), kw: list[str] = Query(default=[]), kw_mode: str = "all",
                 sort: str = "import", limit: int = Query(50, ge=1, le=500), access=Depends(ReviewAccess("viewer")),
                 user: models.User = Depends(current_user), db: DBSession = Depends(get_db)):
    """One page of a list: from `offset` (the screening page reads its list 200 records at a
    time), else after `cursor`."""
    review, m = access
    rows, c, st_stage = queue_records(db, review, user.id, stage, view, search, source, label, import_id,
                                      year_from, year_to, kw, kw_mode, sort)
    blind = _blind(review, m.role)
    total = len(rows)
    if offset:
        page = rows[offset:offset + limit]
    elif sort == "import":
        page = [r for r in rows if r.id > cursor][:limit]
    else:                                     # the cursor is the last record of the previous page
        start = next((i + 1 for i, r in enumerate(rows) if r.id == cursor), 0) if cursor else 0
        page = rows[start:start + limit]
    names = _names(db, review.id)
    ai = _ai_map(db, review.id, st_stage, [r.id for r in page])
    merged = _merged_from(db, review, [r.id for r in page])
    items = [record_out(r, c, user.id, blind, names, ai.get(r.id), st_stage, merged.get(r.id)) for r in page]
    next_cursor = page[-1].id if len(page) == limit and page[-1].id != rows[-1].id else None
    return schemas.RecordPage(items=items, total=total, next_cursor=next_cursor)


def _one(db: DBSession, review: models.Review, record_id: int) -> models.Record:
    rec = db.get(models.Record, record_id)
    if not rec or rec.review_id != review.id:
        raise HTTPException(404, "Record not found")
    return rec


@router.get("/records/{record_id}", response_model=schemas.RecordOut)
def get_record(record_id: int, stage: str = "ta", access=Depends(ReviewAccess("viewer")),
               user: models.User = Depends(current_user), db: DBSession = Depends(get_db)):
    review, m = access
    rec = _one(db, review, record_id)
    c = scr.compute(db, review)
    st = "ft" if stage == "ft" else "ta"
    return record_out(rec, c, user.id, _blind(review, m.role), _names(db, review.id),
                      _ai_map(db, review.id, st, [rec.id]).get(rec.id), st, _merged_from(db, review, [rec.id]).get(rec.id))


@router.patch("/records/{record_id}", response_model=schemas.RecordOut)
def update_record(record_id: int, body: schemas.RecordUpdate, access=Depends(ReviewAccess("reviewer")),
                  user: models.User = Depends(current_user), db: DBSession = Depends(get_db)):
    review, m = access
    rec = _one(db, review, record_id)
    for f in ("labels", "notes", "title", "abstract", "year", "doi"):
        v = getattr(body, f)
        if v is not None:
            setattr(rec, f, v.strip() if f != "abstract" else v)
    db.commit()
    c = scr.compute(db, review)
    return record_out(rec, c, user.id, _blind(review, m.role), _names(db, review.id), None)


@router.post("/records/delete")
def delete_records(record_ids: list[int], access=Depends(ReviewAccess("admin")), db: DBSession = Depends(get_db)):
    review, _ = access
    pdf_keys = db.scalars(select(models.Record.pdf_key).where(models.Record.review_id == review.id,
                                                              models.Record.id.in_(record_ids),
                                                              models.Record.pdf_key != "")).all()
    n = db.execute(delete(models.Record).where(models.Record.review_id == review.id,
                                                models.Record.id.in_(record_ids))).rowcount
    db.commit()
    storage.delete_pdfs(pdf_keys)
    return {"deleted": n}


@router.get("/labels")
def labels(access=Depends(ReviewAccess("viewer")), db: DBSession = Depends(get_db)):
    review, _ = access
    counts: dict[str, int] = {}
    for (lab,) in db.execute(select(models.Record.labels).where(models.Record.review_id == review.id,
                                                                 models.Record.labels != "")).all():
        for l in re.split(r"[;,]", lab):
            l = l.strip()
            if l:
                counts[l] = counts.get(l, 0) + 1
    return [{"label": k, "n": v} for k, v in sorted(counts.items(), key=lambda kv: -kv[1])]


# ── Decisions ────────────────────────────────────────────────────────────────────
def _set_decision(db: DBSession, review: models.Review, user: models.User, rec: models.Record,
                  stage: str, decision: str, reason: str, note: str, seconds: float | None,
                  reviewer: str) -> None:
    d = db.scalar(select(models.Decision).where(models.Decision.record_id == rec.id, models.Decision.stage == stage,
                                                models.Decision.reviewer == reviewer))
    if not d:
        d = models.Decision(review_id=review.id, record_id=rec.id, stage=stage, reviewer=reviewer,
                            user_id=user.id, decision=decision)
        db.add(d)
    d.decision, d.reason, d.note = decision, (reason if decision == "exclude" else "")[:200], note
    d.seconds, d.decided_at, d.user_id = seconds, models.now(), user.id


@router.post("/records/{record_id}/decision", response_model=schemas.RecordOut)
def decide(record_id: int, body: schemas.DecisionIn, access=Depends(ReviewAccess("reviewer")),
           user: models.User = Depends(current_user), db: DBSession = Depends(get_db)):
    review, m = access
    rec = _one(db, review, record_id)
    reviewer = user.id
    if body.as_consensus:
        if ROLE_RANK[m.role] < ROLE_RANK["admin"]:
            raise HTTPException(403, "Only admins resolve conflicts")
        reviewer = "consensus"
    _set_decision(db, review, user, rec, body.stage, body.decision, body.reason, body.note, body.seconds, reviewer)
    db.commit()
    c = scr.compute(db, review)
    return record_out(rec, c, user.id, _blind(review, m.role), _names(db, review.id),
                      _ai_map(db, review.id, body.stage, [rec.id]).get(rec.id), body.stage)


@router.delete("/records/{record_id}/decision", response_model=schemas.RecordOut)
def undecide(record_id: int, stage: str = "ta", consensus: bool = False, access=Depends(ReviewAccess("reviewer")),
             user: models.User = Depends(current_user), db: DBSession = Depends(get_db)):
    review, m = access
    rec = _one(db, review, record_id)
    reviewer = "consensus" if consensus and ROLE_RANK[m.role] >= ROLE_RANK["admin"] else user.id
    db.execute(delete(models.Decision).where(models.Decision.record_id == rec.id, models.Decision.stage == stage,
                                             models.Decision.reviewer == reviewer))
    db.commit()
    c = scr.compute(db, review)
    return record_out(rec, c, user.id, _blind(review, m.role), _names(db, review.id), None, stage)


@router.post("/records/decisions/bulk")
def bulk_decide(body: schemas.BulkDecisionIn, access=Depends(ReviewAccess("reviewer")),
                user: models.User = Depends(current_user), db: DBSession = Depends(get_db)):
    review, _ = access
    if body.stage not in ("ta", "ft") or body.decision not in ("include", "maybe", "exclude"):
        raise HTTPException(400, "Bad stage or decision")
    n = 0
    for rec in db.scalars(select(models.Record).where(models.Record.review_id == review.id,
                                                      models.Record.id.in_(body.record_ids))):
        _set_decision(db, review, user, rec, body.stage, body.decision, body.reason, "", None, user.id)
        n += 1
    log_activity(db, review.id, user.id, "bulk_decision", n=n, decision=body.decision, stage=body.stage)
    db.commit()
    return {"updated": n}


# ── PDFs ─────────────────────────────────────────────────────────────────────────
@router.post("/records/{record_id}/pdf", response_model=schemas.RecordOut)
async def upload_pdf(record_id: int, file: UploadFile = File(...), access=Depends(ReviewAccess("reviewer")),
                     user: models.User = Depends(current_user), db: DBSession = Depends(get_db)):
    review, m = access
    rec = _one(db, review, record_id)
    data = await file.read()
    if not data.startswith(b"%PDF"):
        raise HTTPException(400, "This file is not a PDF")
    if rec.pdf_key:
        storage.delete_pdf(rec.pdf_key)
    rec.pdf_key = storage.save_pdf(review.id, rec.id, data, file.filename or "paper.pdf")
    rec.pdf_status = "available"
    db.commit()
    return record_out(rec, scr.compute(db, review), user.id, _blind(review, m.role), _names(db, review.id), None, "ft")


@router.get("/records/{record_id}/pdf")
def get_pdf(record_id: int, access=Depends(ReviewAccess("viewer")), db: DBSession = Depends(get_db)):
    review, _ = access
    rec = _one(db, review, record_id)
    data = storage.read_pdf(rec.pdf_key)
    if not data:
        raise HTTPException(404, "No PDF for this record")
    return Response(data, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="record-{rec.id}.pdf"'})


@router.get("/records/{record_id}/text")
def get_text(record_id: int, access=Depends(ReviewAccess("viewer")), db: DBSession = Depends(get_db)):
    review, _ = access
    rec = _one(db, review, record_id)
    data = storage.read_pdf(rec.pdf_key)
    if not data:
        raise HTTPException(404, "No PDF for this record")
    return {"text": storage.pdf_text(data)}


@router.delete("/records/{record_id}/pdf", response_model=schemas.RecordOut)
def delete_pdf(record_id: int, access=Depends(ReviewAccess("reviewer")), user: models.User = Depends(current_user),
               db: DBSession = Depends(get_db)):
    review, m = access
    rec = _one(db, review, record_id)
    storage.delete_pdf(rec.pdf_key)
    rec.pdf_key, rec.pdf_status = "", ""
    db.commit()
    return record_out(rec, scr.compute(db, review), user.id, _blind(review, m.role), _names(db, review.id), None, "ft")


@router.post("/records/{record_id}/pdf/not-retrieved", response_model=schemas.RecordOut)
def toggle_not_retrieved(record_id: int, access=Depends(ReviewAccess("reviewer")),
                         user: models.User = Depends(current_user), db: DBSession = Depends(get_db)):
    review, m = access
    rec = _one(db, review, record_id)
    rec.pdf_status = "" if rec.pdf_status == "not_retrieved" else "not_retrieved"
    db.commit()
    return record_out(rec, scr.compute(db, review), user.id, _blind(review, m.role), _names(db, review.id), None, "ft")


def fetch_open_access(doi: str, email: str) -> bytes:
    """Unpaywall lookup, then download of the best open-access PDF."""
    doi = doi.strip().lower().replace("https://doi.org/", "").replace("doi.org/", "")
    if "/" not in doi:
        raise ValueError("This record has no valid DOI")
    api = f"https://api.unpaywall.org/v2/{urllib.parse.quote(doi, safe='/')}?email={email}"
    with httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": "Krinea/1.0 (research)"}) as c:
        r = c.get(api)
        r.raise_for_status()
        data = r.json()
        if not data.get("is_oa"):
            raise FileNotFoundError("No open-access copy listed by Unpaywall")
        best = data.get("best_oa_location") or {}
        url = best.get("url_for_pdf") or best.get("url")
        if not url:
            raise FileNotFoundError("Open access, but no PDF link")
        pdf = c.get(url, headers={"Accept": "application/pdf,*/*"})
        pdf.raise_for_status()
        if not pdf.content.startswith(b"%PDF"):
            raise FileNotFoundError("The open-access link did not return a PDF")
        return pdf.content


@router.post("/records/{record_id}/pdf/fetch", response_model=schemas.RecordOut)
def fetch_pdf(record_id: int, access=Depends(ReviewAccess("reviewer")), user: models.User = Depends(current_user),
              db: DBSession = Depends(get_db)):
    review, m = access
    rec = _one(db, review, record_id)
    email = get_settings().unpaywall_email or user.email
    try:
        data = fetch_open_access(rec.doi, email)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except Exception as e:                 # noqa: BLE001
        raise HTTPException(502, f"Could not fetch the PDF: {type(e).__name__}: {e}")
    rec.pdf_key = storage.save_pdf(review.id, rec.id, data, f"{rec.doi.replace('/', '_')}.pdf")
    rec.pdf_status = "available"
    db.commit()
    return record_out(rec, scr.compute(db, review), user.id, _blind(review, m.role), _names(db, review.id), None, "ft")


# ── Duplicates ───────────────────────────────────────────────────────────────────
@router.post("/dedup/run", response_model=schemas.JobOut)
def run_dedup(body: schemas.DedupRunIn, access=Depends(ReviewAccess("admin")),
              user: models.User = Depends(current_user), db: DBSession = Depends(get_db)):
    review, _ = access
    # The thresholds of the last run stay with the review: the page shows them next time.
    review.settings = {**(review.settings or {}), "dedup_auto_threshold": body.auto_threshold,
                       "dedup_review_threshold": body.review_threshold}
    job = job_service.enqueue(db, "dedup", {"auto_threshold": body.auto_threshold,
                                            "review_threshold": body.review_threshold}, review.id, user.id)
    return job


@router.get("/dedup/candidates", response_model=list[schemas.CandidateOut])
def candidates(status: str = "pending", limit: int = Query(50, ge=1, le=500), access=Depends(ReviewAccess("viewer")),
               user: models.User = Depends(current_user), db: DBSession = Depends(get_db)):
    review, m = access
    rows = db.scalars(select(models.DedupCandidate).where(models.DedupCandidate.review_id == review.id,
                                                          models.DedupCandidate.status == status)
                      .order_by(models.DedupCandidate.score.desc(), models.DedupCandidate.id).limit(limit)).all()
    c = scr.compute(db, review)
    names = _names(db, review.id)
    prio = dedup_service.priority(review)
    out = []
    for cand in rows:
        a, b = db.get(models.Record, cand.record_a), db.get(models.Record, cand.record_b)
        if not a or not b or a.is_duplicate or b.is_duplicate:
            continue
        out.append(schemas.CandidateOut(id=cand.id, score=cand.score, reason=cand.reason, status=cand.status,
                                        a=record_out(a, c, user.id, True, names, None),
                                        b=record_out(b, c, user.id, True, names, None),
                                        suggested_keep=dedup_service.suggested_keep(db, a, b, prio)))
    return out


@router.post("/dedup/candidates/{cand_id}/{action}")
def resolve_candidate(cand_id: int, action: str, keep: int | None = None, access=Depends(ReviewAccess("reviewer")),
                      user: models.User = Depends(current_user), db: DBSession = Depends(get_db)):
    """`merge` keeps the record given in `keep` (one of the pair), or lets the review's rule
    choose; `ignore` keeps both records."""
    review, _ = access
    cand = db.get(models.DedupCandidate, cand_id)
    if not cand or cand.review_id != review.id:
        raise HTTPException(404, "Candidate not found")
    if keep is not None and keep not in (cand.record_a, cand.record_b):
        raise HTTPException(400, "keep must be one of the two records of the pair")
    if action == "merge":
        dedup_service.merge_candidate(db, cand, keep, dedup_service.priority(review))
    elif action == "ignore":
        dedup_service.ignore_candidate(db, cand)
    else:
        raise HTTPException(400, "action must be merge or ignore")
    return {"ok": True, "status": cand.status}


@router.get("/sources")
def list_sources(access=Depends(ReviewAccess("viewer")), db: DBSession = Depends(get_db)):
    """Databases the review's records come from, for the source order in the settings."""
    review, _ = access
    return dedup_service.sources(db, review.id)


@router.get("/dedup/duplicates")
def duplicates(limit: int = Query(200, ge=1, le=2000), access=Depends(ReviewAccess("viewer")),
               db: DBSession = Depends(get_db)):
    review, _ = access
    d = models.Record
    rows = db.execute(select(d.id, d.title, d.year, d.doi, d.source_db, d.dup_score, d.dup_reason, d.duplicate_of)
                      .where(d.review_id == review.id, d.is_duplicate.is_(True)).order_by(d.duplicate_of, d.id)
                      .limit(limit)).all()
    keepers = {}
    ids = [r[7] for r in rows if r[7]]
    if ids:
        keepers = dict(db.execute(select(d.id, d.title).where(d.id.in_(ids))).all())
    return [{"id": r[0], "title": r[1], "year": r[2], "doi": r[3], "source_db": r[4], "score": r[5],
             "reason": r[6], "kept_id": r[7], "kept_title": keepers.get(r[7], "")} for r in rows]


@router.post("/dedup/restore-all")
def restore_all(access=Depends(ReviewAccess("admin")), user: models.User = Depends(current_user),
                db: DBSession = Depends(get_db)):
    """Undoes every merge of the review: removed duplicates come back and kept records get
    their own values back. Pairs answered "different" stay answered."""
    review, _ = access
    n = dedup_service.reset(db, review.id)
    log_activity(db, review.id, user.id, "dedup_restored", n=n)
    db.commit()
    return {"restored": n}


@router.post("/records/{record_id}/restore")
def restore(record_id: int, access=Depends(ReviewAccess("reviewer")), db: DBSession = Depends(get_db)):
    review, _ = access
    rec = _one(db, review, record_id)
    dedup_service.restore(db, rec)
    return {"ok": True}
