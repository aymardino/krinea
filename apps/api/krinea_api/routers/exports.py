"""PRISMA counts and diagram, and file exports. The records of a screening stage and the
extraction table can be filtered by decision, exclusion reason, imported file, label and PDF
(decision D-39), several values at once in each filter (D-41). The files of a large review are
written to disk in batches and sent from there, so that no export holds the whole review in
memory (D-56)."""
from __future__ import annotations

import csv
import io
import os
import re
import tempfile
from collections.abc import Iterable, Iterator

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response
from starlette.background import BackgroundTask
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session as DBSession

from krinea_api import models
from krinea_api.db import get_db
from krinea_api.deps import ReviewAccess, current_user
from krinea_api.services import prisma as prisma_service
from krinea_api.services import screening as scr
from krinea_core import biblio, extraction_schema, prisma as prisma_core

router = APIRouter(prefix="/reviews/{review_id}", tags=["exports"])

STATUSES = ("include", "maybe", "exclude", "conflict", "pending")
PDF_STATES = ("available", "missing", "not_retrieved")
NO_REASON = "-"                      # `reason` value for the exclusions given without a reason
EXTRACTION_STATES = ("verified", "all")
STAGE_FILES = {"ta": "title-abstract", "ft": "full-text"}
STATUS_FILES = {"include": "included", "maybe": "maybe", "exclude": "excluded", "conflict": "conflicts",
                "pending": "not-screened"}
# Columns of a screening export, the most read first. `file` is the file of the copy kept
# among duplicates, `files` every file that found the record (the kept copy's first).
SCREENING_COLUMNS = ["id", "title", "authors", "year", "journal", "doi", "ta_status", "ta_reason", "ft_status",
                     "ft_reason", "pdf", "labels", "notes", "file", "files", "abstract", "keywords", "volume",
                     "issue", "pages", "url", "pmid", "publisher", "type", "language", "source_db", "raw_id"]
RIS = "application/x-research-info-systems"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
# Characters an Excel cell refuses (control characters some database exports carry).
_ILLEGAL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
# Excel keeps at most 65,530 links per sheet, each at most 2,079 characters long.
_MAX_LINKS, _MAX_URL = 65000, 2000
# Records read from the database at a time for an export.
BATCH = 1000


def _record_dict(r: models.Record) -> dict:
    d = {f: getattr(r, f) for f in biblio.RECORD_FIELDS}
    d.update(id=r.id, is_duplicate=r.is_duplicate, labels=r.labels, notes=r.notes, pdf_status=r.pdf_status)
    return d


def _record_dicts(db: DBSession, review_id: str, ids: list[int] | None = None) -> list[dict]:
    q = select(models.Record).where(models.Record.review_id == review_id)
    if ids is not None:
        q = q.where(models.Record.id.in_(ids))
    return [_record_dict(r) for r in db.scalars(q.order_by(models.Record.id))]


def _in_batches(db: DBSession, ids: list[int]) -> Iterator[models.Record]:
    """The records of `ids` in that order, read BATCH at a time and let go after."""
    for i in range(0, len(ids), BATCH):
        chunk = ids[i:i + BATCH]
        found = {r.id: r for r in db.scalars(select(models.Record).where(models.Record.id.in_(chunk)))}
        for rid in chunk:
            if rid in found:
                yield found[rid]
        for r in found.values():
            db.expunge(r)


def _file(content: str | bytes, filename: str, media: str) -> Response:
    return Response(content, media_type=media, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


def _temp(suffix: str) -> str:
    fd, path = tempfile.mkstemp(prefix="krinea-export-", suffix=suffix)
    os.close(fd)
    return path


def _send(path: str, filename: str, media: str) -> FileResponse:
    """A file written to disk, sent, then deleted."""
    return FileResponse(path, media_type=media, filename=filename, background=BackgroundTask(os.unlink, path))


def _csv_file(columns: list[str], rows: Iterable[list]) -> str:
    path = _temp(".csv")
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(columns)
        w.writerows(rows)
    return path


def _ris_file(records: Iterable[dict]) -> str:
    """The RIS of `records`, as biblio.to_ris writes them all at once."""
    path = _temp(".ris")
    with open(path, "w", encoding="utf-8", newline="") as f:
        n = 0
        for r in records:
            f.write(("\n\n" if n else "") + biblio.to_ris([r])[:-1])
            n += 1
        if n:
            f.write("\n")
    return path


def _xlsx_file(sheets: dict[str, tuple[list[str], Iterable[list]]]) -> str:
    """An Excel workbook with one sheet per {name: (columns, rows)}, written as the rows come
    (openpyxl's write-only mode). DOIs and web addresses are links you can click: a `doi` cell
    keeps its bare DOI and links to https://doi.org/, a cell holding one address links to it."""
    from openpyxl import Workbook
    from openpyxl.cell import WriteOnlyCell
    from openpyxl.styles import Font
    path = _temp(".xlsx")
    wb = Workbook(write_only=True)
    for name, (columns, rows) in sheets.items():
        ws = wb.create_sheet(name)
        head = []
        for col in columns:
            cell = WriteOnlyCell(ws, value=col)
            cell.font = Font(bold=True)
            head.append(cell)
        ws.append(head)
        doi_col = columns.index("doi") if "doi" in columns else -1
        links = 0
        for row in rows:
            out = []
            for j, v in enumerate(row):
                if isinstance(v, str) and v:
                    v = _ILLEGAL.sub("", v)
                    url = biblio.doi_url(v) if j == doi_col else v if v.startswith(("https://", "http://")) else ""
                    if url and links < _MAX_LINKS and len(url) <= _MAX_URL and not any(c.isspace() for c in url):
                        cell = WriteOnlyCell(ws, value=v)
                        cell.hyperlink, cell.style = url, "Hyperlink"
                        links += 1
                        v = cell
                out.append(v)
            ws.append(out)
    wb.save(path)
    return path


# ── Selection ────────────────────────────────────────────────────────────────────
def _reason(decs: dict[str, models.Decision], user_id: str, blind: bool) -> str:
    """The exclusion reason of a record at one stage: the consensus one, else the first given.
    In a blind review, a reviewer only sees their own, as on screen."""
    if blind:
        mine = decs.get(user_id)
        return mine.reason if mine and mine.decision == "exclude" else ""
    return scr.first_reason(decs)


def _found_in(db: DBSession, review_id: str) -> dict[int, list[str]]:
    """The names of the imported files each record was found in: its own first, then those of
    the duplicates merged into it."""
    names = dict(db.execute(select(models.Import.id, models.Import.filename)
                            .where(models.Import.review_id == review_id)).all())
    rows = db.execute(select(models.Record.id, models.Record.import_id, models.Record.is_duplicate,
                             models.Record.duplicate_of)
                      .where(models.Record.review_id == review_id).order_by(models.Record.id)).all()
    out: dict[int, list[str]] = {}
    for rid, imp, dup, keeper in sorted(rows, key=lambda row: bool(row[2])):      # kept copies first
        target = keeper if dup and keeper is not None else rid
        name = names.get(imp or "")
        if name and name not in out.setdefault(target, []):
            out[target].append(name)
    return out


def _values(raw: list[str] | str | None) -> list[str]:
    """The values given for a filter that may be repeated (?status=a&status=b), blanks left out."""
    raw = [raw] if isinstance(raw, str) else (raw or [])
    return list(dict.fromkeys(v.strip() for v in raw if v and v.strip()))


def _select(db: DBSession, review: models.Review, role: str, user_id: str, stage: str, status=(), reason=(),
            import_id=(), label=(), pdf=()):
    """The ids of the records of a stage that pass the filters, in import order, with the
    screening state of the review and whether the member sees it blind. Stages: "ta" (every unique record),
    "ft" (those kept at title and abstract), "extract" (those included at full text). Each
    filter takes one value or several: a record passes when it matches any of them, and every
    filter given. A reason filter keeps the records excluded for one of the reasons given
    (NO_REASON: excluded without one)."""
    if stage not in ("ta", "ft", "extract"):
        raise HTTPException(400, "stage must be ta, ft or extract")
    status, reasons, files, labels, pdfs = (_values(v) for v in (status, reason, import_id, label, pdf))
    if set(status) - set(STATUSES):
        raise HTTPException(400, f"status must be among {', '.join(STATUSES)}")
    if set(pdfs) - set(PDF_STATES):
        raise HTTPException(400, f"pdf must be among {', '.join(PDF_STATES)}")
    c = scr.compute(db, review)
    blind = scr.is_blind(review, role)
    st = "ta" if stage == "ta" else "ft"
    statuses, decs = c[f"{st}_status"], c["decisions"][st]
    ids = set(scr.pool_ids(c, stage))
    if status:
        ids = {i for i in ids if statuses.get(i, "pending") in status}
    if reasons:
        def excluded_for(i: int) -> bool:
            given = _reason(decs.get(i, {}), user_id, blind)
            return given in reasons if given else (NO_REASON in reasons and statuses.get(i) == "exclude")
        ids = {i for i in ids if excluded_for(i)}
    q = (select(models.Record.id, models.Record.labels)
         .where(models.Record.review_id == review.id, models.Record.is_duplicate.is_(False)))
    if files:                                  # what counts for a file: scr.in_file (D-29, D-42)
        q = q.where(or_(*(scr.in_file(review, f) for f in files)))
    if pdfs:
        has = {"available": models.Record.pdf_key != "",
               "not_retrieved": models.Record.pdf_status == "not_retrieved",
               "missing": and_(models.Record.pdf_key == "", models.Record.pdf_status != "not_retrieved")}
        q = q.where(or_(*(has[p] for p in pdfs)))
    rows = [(rid, labs) for rid, labs in db.execute(q.order_by(models.Record.id)) if rid in ids]
    if labels:                                 # exact labels: "SQ1" must not match "SQ10"
        wanted = {lab.lower() for lab in labels}
        rows = [(rid, labs) for rid, labs in rows if scr.labels_of(labs) & wanted]
    return [rid for rid, _ in rows], c, blind


def _screening_rows(db: DBSession, review: models.Review, ids: list[int], c: dict, user_id: str,
                    blind: bool) -> Iterator[dict]:
    found = _found_in(db, review.id)
    names = dict(db.execute(select(models.Import.id, models.Import.filename)
                            .where(models.Import.review_id == review.id)).all())
    for r in _in_batches(db, ids):
        d = {f: getattr(r, f) for f in biblio.RECORD_FIELDS}
        d.update(id=r.id, file=names.get(r.import_id or "", ""), files="; ".join(found.get(r.id, [])),
                 ta_status=c["ta_status"].get(r.id, ""), ta_reason=_reason(c["decisions"]["ta"].get(r.id, {}), user_id, blind),
                 ft_status=c["ft_status"].get(r.id, ""), ft_reason=_reason(c["decisions"]["ft"].get(r.id, {}), user_id, blind),
                 pdf="available" if r.pdf_key else ("not retrieved" if r.pdf_status == "not_retrieved" else ""),
                 labels=r.labels, notes=r.notes)
        yield d


def _extraction_pairs(db: DBSession, review: models.Review, role: str, user_id: str, status: str,
                      import_id=(), label=()) -> list[tuple[models.Record, models.Extraction | None]]:
    """The studies included at full text that pass the filters, with their extraction: only
    the verified ones, or all of them (with or without an extraction)."""
    if status not in EXTRACTION_STATES:
        raise HTTPException(400, "status must be verified or all")
    ids, _c, _blind = _select(db, review, role, user_id, "extract", import_id=import_id, label=label)
    rows = list(_in_batches(db, ids))
    exs = {e.record_id: e for e in db.scalars(select(models.Extraction).where(models.Extraction.review_id == review.id))}
    pairs = [(r, exs.get(r.id)) for r in rows]
    if status == "verified":
        pairs = [(r, e) for r, e in pairs if e and e.status == "verified"]
    return pairs


# ── Endpoints ────────────────────────────────────────────────────────────────────
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


@router.get("/export/count")
def export_count(stage: str = "ta", status: list[str] = Query(default=[]), reason: list[str] = Query(default=[]),
                 import_id: list[str] = Query(default=[]), label: list[str] = Query(default=[]),
                 pdf: list[str] = Query(default=[]), access=Depends(ReviewAccess("viewer")),
                 user: models.User = Depends(current_user), db: DBSession = Depends(get_db)):
    """How many records the export with these filters holds; for stage "extract", `status` is
    the extraction status (verified or all)."""
    review, m = access
    if stage == "extract":
        extraction = (_values(status) or ["verified"])[0]
        return {"n": len(_extraction_pairs(db, review, m.role, user.id, extraction, import_id, label))}
    ids, _c, _blind = _select(db, review, m.role, user.id, stage, status, reason, import_id, label, pdf)
    return {"n": len(ids)}


@router.get("/export/screening.{fmt}")
def export_screening(fmt: str, stage: str = "ta", status: list[str] = Query(default=[]),
                     reason: list[str] = Query(default=[]), import_id: list[str] = Query(default=[]),
                     label: list[str] = Query(default=[]), pdf: list[str] = Query(default=[]),
                     access=Depends(ReviewAccess("viewer")), user: models.User = Depends(current_user),
                     db: DBSession = Depends(get_db)):
    """The records of a screening stage, filtered, as RIS, CSV or Excel, with their status and
    exclusion reason at each stage."""
    review, m = access
    if fmt not in ("ris", "csv", "xlsx"):
        raise HTTPException(400, "fmt must be ris, csv or xlsx")
    if stage not in STAGE_FILES:
        raise HTTPException(400, "stage must be ta or ft")
    ids, c, blind = _select(db, review, m.role, user.id, stage, status, reason, import_id, label, pdf)
    recs = _screening_rows(db, review, ids, c, user.id, blind)
    picked = [s for s in STATUSES if s in _values(status)]
    name = "-".join([STAGE_FILES[stage], *(STATUS_FILES[s] for s in picked)])
    if fmt == "ris":
        return _send(_ris_file(recs), f"{name}.ris", RIS)
    table = ([r.get(col, "") for col in SCREENING_COLUMNS] for r in recs)
    if fmt == "csv":
        return _send(_csv_file(SCREENING_COLUMNS, table), f"{name}.csv", "text/csv")
    return _send(_xlsx_file({"records": (SCREENING_COLUMNS, table)}), f"{name}.xlsx", XLSX)


@router.get("/export/included.{fmt}")
def export_included(fmt: str, access=Depends(ReviewAccess("viewer")), db: DBSession = Depends(get_db)):
    review, _ = access
    c = scr.compute(db, review)
    recs = _record_dicts(db, review.id, c["extract_pool"])
    if fmt == "ris":
        return _file(biblio.to_ris(recs), "included.ris", RIS)
    if fmt == "csv":
        return _file(biblio.to_csv(recs, extra_fields=["id", "labels", "notes"]), "included.csv", "text/csv")
    raise HTTPException(400, "fmt must be ris or csv")


@router.get("/export/records.csv")
def export_records(access=Depends(ReviewAccess("viewer")), db: DBSession = Depends(get_db)):
    review, _ = access
    c = scr.compute(db, review)
    ids = list(db.scalars(select(models.Record.id).where(models.Record.review_id == review.id).order_by(models.Record.id)))
    extra = ["id", "is_duplicate", "ta_status", "ft_status", "labels", "notes", "pdf_status"]
    columns = list(biblio.RECORD_FIELDS) + [f for f in extra if f not in biblio.RECORD_FIELDS]

    def rows() -> Iterator[list]:
        for r in _in_batches(db, ids):
            d = _record_dict(r)
            d["ta_status"], d["ft_status"] = c["ta_status"].get(r.id, ""), c["ft_status"].get(r.id, "")
            yield [d.get(f, "") for f in columns]
    return _send(_csv_file(columns, rows()), "records.csv", "text/csv")


@router.get("/export/decisions.csv")
def export_decisions(access=Depends(ReviewAccess("viewer")), user: models.User = Depends(current_user),
                     db: DBSession = Depends(get_db)):
    review, m = access
    names = dict(db.execute(select(models.User.id, models.User.email).join(
        models.Membership, models.Membership.user_id == models.User.id).where(models.Membership.review_id == review.id)).all())
    q = select(models.Decision).where(models.Decision.review_id == review.id)
    if scr.is_blind(review, m.role):              # a blind reviewer gets their own decisions only
        q = q.where(models.Decision.reviewer == user.id)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["record_id", "stage", "reviewer", "decision", "reason", "note", "seconds", "decided_at"])
    for d in db.scalars(q.order_by(models.Decision.record_id, models.Decision.stage, models.Decision.reviewer)):
        w.writerow([d.record_id, d.stage, names.get(d.reviewer, d.reviewer), d.decision, d.reason, d.note,
                    d.seconds or "", d.decided_at.isoformat()])
    return _file(buf.getvalue(), "decisions.csv", "text/csv")


@router.get("/export/extractions.{fmt}")
def export_extractions(fmt: str, status: str = "verified", import_id: list[str] = Query(default=[]),
                       label: list[str] = Query(default=[]), access=Depends(ReviewAccess("viewer")),
                       user: models.User = Depends(current_user), db: DBSession = Depends(get_db)):
    """The extraction table of the studies included at full text: the verified extractions (the
    default) or every study with the status of its extraction, filtered by file and label."""
    review, m = access
    if fmt not in ("csv", "xlsx", "ris"):
        raise HTTPException(400, "fmt must be csv, xlsx or ris")
    pairs = _extraction_pairs(db, review, m.role, user.id, status, import_id, label)
    name = "extractions" if status == "verified" else "extractions-all"
    if fmt == "ris":
        recs = [{f: getattr(r, f) for f in biblio.RECORD_FIELDS} for r, _ in pairs]
        return _file(biblio.to_ris(recs), f"{name}.ris", RIS)
    fields = extraction_schema.from_json(review.extraction_schema or [])
    names = [f["name"] for f in fields]
    with_status = status == "all"
    files = dict(db.execute(select(models.Import.id, models.Import.filename)
                            .where(models.Import.review_id == review.id)).all())
    meta = ["record_id", "title", "authors", "year", "journal", "doi"] + (["status"] if with_status else [])
    auto = {f["name"]: f["kind"] for f in fields if f["kind"] in extraction_schema.AUTO_KINDS}

    def filled(r: models.Record, kind: str) -> str:
        # A "search" field holds the study's search, the file of its kept copy (D-49); a "doi"
        # field the link of the DOI of its citation (D-52).
        return files.get(r.import_id or "", "") if kind == "search" else biblio.doi_url(r.doi)

    def line(r: models.Record, e: models.Extraction | None, attr: str) -> list:
        head = [r.id, r.title, r.authors, r.year, r.journal, r.doi] + ([e.status if e else ""] if with_status else [])
        cells = (getattr(e, attr) or {}) if e else {}
        if attr == "values":
            cells = extraction_schema.canonical(fields, cells)        # choices as the options are (D-53)
        # The fields Krinea fills in have no quote.
        return head + [(filled(r, auto[n]) if attr == "values" else "") if n in auto else cells.get(n, "")
                       for n in names]

    values = [line(r, e, "values") for r, e in pairs]
    if fmt == "csv":
        return _send(_csv_file(meta + names, values), f"{name}.csv", "text/csv")
    quotes = [line(r, e, "quotes") for r, e in pairs]
    # The form, one row per field; "searches" names the files a field belongs to (D-48), the
    # cells of the studies of other searches being empty.
    form = [[f["name"], f["label"], f["kind"], " | ".join(f["options"]), f["hint"], "yes" if f["required"] else "no",
             "; ".join(files.get(s, s) for s in f.get("searches", [])) or "all"] for f in fields]
    path = _xlsx_file({"values": (meta + names, values), "quotes": (meta + names, quotes),
                       "fields": (["name", "label", "kind", "options", "hint", "required", "searches"], form)})
    return _send(path, f"{name}.xlsx", XLSX)


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
