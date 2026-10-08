"""Records of a review: imports, listing with screening views, decisions, PDFs, duplicates."""
from __future__ import annotations

import io
import re
import urllib.parse

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session as DBSession

from tamis_api import models, schemas
from tamis_api.config import get_settings
from tamis_api.db import get_db
from tamis_api.deps import ROLE_RANK, ReviewAccess, current_user, log_activity
from tamis_api.services import dedup as dedup_service
from tamis_api.services import imports as import_service
from tamis_api.services import jobs as job_service
from tamis_api.services import screening as scr
from tamis_api.services import storage

router = APIRouter(prefix="/reviews/{review_id}", tags=["records"])

VIEWS = ("todo", "mine_include", "mine_maybe", "mine_exclude", "include", "maybe", "exclude",
         "conflict", "pending", "all", "no_pdf", "not_retrieved")


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
    log_activity(db, review.id, user.id, "import_deleted", filename=imp.filename, n=n)
    db.commit()
    return {"deleted": n}


# ── Listing ──────────────────────────────────────────────────────────────────────
def _blind(review: models.Review, role: str) -> bool:
    return bool((review.settings or {}).get("blind", True)) and ROLE_RANK[role] < ROLE_RANK["admin"]


def _decision_dict(d: models.Decision, names: dict[str, str]) -> dict:
    return {"reviewer": d.reviewer, "name": names.get(d.reviewer, "consensus" if d.reviewer == "consensus" else ""),
            "decision": d.decision, "reason": d.reason, "note": d.note, "decided_at": d.decided_at.isoformat()}


def record_out(rec: models.Record, computed: dict, user_id: str, blind: bool, names: dict[str, str],
               ai: dict | None, stage: str = "ta") -> schemas.RecordOut:
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
        my_decision=_decision_dict(mine, names) if mine else None, decisions=visible, ai=ai)


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


@router.get("/records", response_model=schemas.RecordPage)
def list_records(stage: str = "ta", view: str = "all", search: str = "", source: str = "", label: str = "",
                 import_id: str = "", year_from: str = "", year_to: str = "", cursor: int = 0,
                 limit: int = Query(50, ge=1, le=500), access=Depends(ReviewAccess("viewer")),
                 user: models.User = Depends(current_user), db: DBSession = Depends(get_db)):
    review, m = access
    if stage not in ("ta", "ft", "extract", "all") or view not in VIEWS:
        raise HTTPException(400, "Unknown stage or view")
    c = scr.compute(db, review)
    pool = (db.scalars(select(models.Record.id).where(models.Record.review_id == review.id)).all()
            if stage == "all" else scr.pool_ids(c, stage))
    st_stage = "ft" if stage in ("ft", "extract") else "ta"
    status = c["ft_status"] if st_stage == "ft" else c["ta_status"]
    decs = c["decisions"][st_stage]
    blind = _blind(review, m.role)

    def keep(rid: int) -> bool:
        mine = decs.get(rid, {}).get(user.id)
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
        q = q.where(models.Record.import_id == import_id)
    if year_from.strip():
        q = q.where(models.Record.year >= year_from.strip()[:4])
    if year_to.strip():
        q = q.where(models.Record.year <= year_to.strip()[:4])
    rows = db.scalars(q.order_by(models.Record.id)).all()
    idset = set(ids)
    rows = [r for r in rows if r.id in idset]
    total = len(rows)
    page = [r for r in rows if r.id > cursor][:limit]
    names = _names(db, review.id)
    ai = _ai_map(db, review.id, st_stage, [r.id for r in page])
    items = [record_out(r, c, user.id, blind, names, ai.get(r.id), st_stage) for r in page]
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
                      _ai_map(db, review.id, st, [rec.id]).get(rec.id), st)


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
    n = db.execute(delete(models.Record).where(models.Record.review_id == review.id,
                                                models.Record.id.in_(record_ids))).rowcount
    db.commit()
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
    with httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": "Tamis/1.0 (research)"}) as c:
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
    out = []
    for cand in rows:
        a, b = db.get(models.Record, cand.record_a), db.get(models.Record, cand.record_b)
        if not a or not b or a.is_duplicate or b.is_duplicate:
            continue
        out.append(schemas.CandidateOut(id=cand.id, score=cand.score, reason=cand.reason, status=cand.status,
                                        a=record_out(a, c, user.id, True, names, None),
                                        b=record_out(b, c, user.id, True, names, None)))
    return out


@router.post("/dedup/candidates/{cand_id}/{action}")
def resolve_candidate(cand_id: int, action: str, access=Depends(ReviewAccess("reviewer")),
                      user: models.User = Depends(current_user), db: DBSession = Depends(get_db)):
    review, _ = access
    cand = db.get(models.DedupCandidate, cand_id)
    if not cand or cand.review_id != review.id:
        raise HTTPException(404, "Candidate not found")
    if action == "merge":
        dedup_service.merge_candidate(db, cand)
    elif action == "ignore":
        dedup_service.ignore_candidate(db, cand)
    else:
        raise HTTPException(400, "action must be merge or ignore")
    return {"ok": True, "status": cand.status}


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


@router.post("/records/{record_id}/restore")
def restore(record_id: int, access=Depends(ReviewAccess("reviewer")), db: DBSession = Depends(get_db)):
    review, _ = access
    rec = _one(db, review, record_id)
    dedup_service.restore(db, rec)
    return {"ok": True}
