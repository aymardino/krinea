"""PRISMA counts and diagram, and file exports."""
from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from krinea_api import models
from krinea_api.db import get_db
from krinea_api.deps import ReviewAccess
from krinea_api.services import prisma as prisma_service
from krinea_api.services import screening as scr
from krinea_core import biblio, extraction_schema, prisma as prisma_core

router = APIRouter(prefix="/reviews/{review_id}", tags=["exports"])


def _record_dicts(db: DBSession, review_id: str, ids: list[int] | None = None) -> list[dict]:
    q = select(models.Record).where(models.Record.review_id == review_id)
    if ids is not None:
        q = q.where(models.Record.id.in_(ids))
    out = []
    for r in db.scalars(q.order_by(models.Record.id)):
        d = {f: getattr(r, f) for f in biblio.RECORD_FIELDS}
        d.update(id=r.id, is_duplicate=r.is_duplicate, labels=r.labels, notes=r.notes, pdf_status=r.pdf_status)
        out.append(d)
    return out


def _file(content: str | bytes, filename: str, media: str) -> Response:
    return Response(content, media_type=media, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/prisma")
def prisma(access=Depends(ReviewAccess("viewer")), db: DBSession = Depends(get_db)):
    review, _ = access
    return prisma_service.counts(db, review)


@router.get("/prisma.svg")
def prisma_svg(variant: str = "new_v1", lang: str = "en", download: bool = False,
               access=Depends(ReviewAccess("viewer")), db: DBSession = Depends(get_db)):
    review, _ = access
    if variant not in prisma_core.VARIANTS:
        raise HTTPException(400, f"variant must be one of {', '.join(prisma_core.VARIANTS)}")
    svg = prisma_core.render_svg(prisma_service.counts(db, review), variant=variant, lang=lang)
    headers = {"Content-Disposition": f'{"attachment" if download else "inline"}; filename="prisma-2020.svg"'}
    return Response(svg, media_type="image/svg+xml", headers=headers)


@router.get("/export/included.{fmt}")
def export_included(fmt: str, access=Depends(ReviewAccess("viewer")), db: DBSession = Depends(get_db)):
    review, _ = access
    c = scr.compute(db, review)
    recs = _record_dicts(db, review.id, c["extract_pool"])
    if fmt == "ris":
        return _file(biblio.to_ris(recs), "included.ris", "application/x-research-info-systems")
    if fmt == "csv":
        return _file(biblio.to_csv(recs, extra_fields=["id", "labels", "notes"]), "included.csv", "text/csv")
    raise HTTPException(400, "fmt must be ris or csv")


@router.get("/export/records.csv")
def export_records(access=Depends(ReviewAccess("viewer")), db: DBSession = Depends(get_db)):
    review, _ = access
    c = scr.compute(db, review)
    recs = _record_dicts(db, review.id)
    for r in recs:
        r["ta_status"] = c["ta_status"].get(r["id"], "")
        r["ft_status"] = c["ft_status"].get(r["id"], "")
    return _file(biblio.to_csv(recs, extra_fields=["id", "is_duplicate", "ta_status", "ft_status", "labels",
                                                   "notes", "pdf_status"]), "records.csv", "text/csv")


@router.get("/export/decisions.csv")
def export_decisions(access=Depends(ReviewAccess("viewer")), db: DBSession = Depends(get_db)):
    review, _ = access
    names = dict(db.execute(select(models.User.id, models.User.email).join(
        models.Membership, models.Membership.user_id == models.User.id).where(models.Membership.review_id == review.id)).all())
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["record_id", "stage", "reviewer", "decision", "reason", "note", "seconds", "decided_at"])
    for d in db.scalars(select(models.Decision).where(models.Decision.review_id == review.id)
                        .order_by(models.Decision.record_id, models.Decision.stage, models.Decision.reviewer)):
        w.writerow([d.record_id, d.stage, names.get(d.reviewer, d.reviewer), d.decision, d.reason, d.note,
                    d.seconds or "", d.decided_at.isoformat()])
    return _file(buf.getvalue(), "decisions.csv", "text/csv")


@router.get("/export/extractions.{fmt}")
def export_extractions(fmt: str, access=Depends(ReviewAccess("viewer")), db: DBSession = Depends(get_db)):
    review, _ = access
    fields = extraction_schema.from_json(review.extraction_schema or [])
    rows = db.execute(select(models.Extraction, models.Record).join(models.Record, models.Record.id == models.Extraction.record_id)
                      .where(models.Extraction.review_id == review.id, models.Extraction.status == "verified")
                      .order_by(models.Extraction.record_id)).all()
    meta = ["record_id", "title", "authors", "year", "journal", "doi"]
    names = [f["name"] for f in fields]
    values = [[r.id, r.title, r.authors, r.year, r.journal, r.doi] + [(e.values or {}).get(n, "") for n in names]
              for e, r in rows]
    quotes = [[r.id, r.title, r.authors, r.year, r.journal, r.doi] + [(e.quotes or {}).get(n, "") for n in names]
              for e, r in rows]
    if fmt == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(meta + names)
        w.writerows(values)
        return _file(buf.getvalue(), "extractions.csv", "text/csv")
    if fmt == "xlsx":
        import pandas as pd
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as xl:
            pd.DataFrame(values, columns=meta + names).to_excel(xl, sheet_name="values", index=False)
            pd.DataFrame(quotes, columns=meta + names).to_excel(xl, sheet_name="quotes", index=False)
            pd.DataFrame(fields).to_excel(xl, sheet_name="fields", index=False)
        return _file(buf.getvalue(), "extractions.xlsx",
                     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    raise HTTPException(400, "fmt must be csv or xlsx")


@router.get("/export/prisma.csv")
def export_prisma(access=Depends(ReviewAccess("viewer")), db: DBSession = Depends(get_db)):
    review, _ = access
    c = prisma_service.counts(db, review)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["item", "n"])
    for k, v in c.items():
        if isinstance(v, dict):
            for kk, vv in v.items():
                w.writerow([f"{k}:{kk}", vv])
        else:
            w.writerow([k, v])
    return _file(buf.getvalue(), "prisma_counts.csv", "text/csv")
