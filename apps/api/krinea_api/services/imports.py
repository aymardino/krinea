"""Importing search exports into a review."""
from __future__ import annotations

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from krinea_api import models
from krinea_api.services import storage
from krinea_core import biblio

RECORD_FIELDS = biblio.RECORD_FIELDS
# Records written to the database at a time.
BATCH = 1000


def import_file(db: Session, review: models.Review, user: models.User | None, filename: str,
                data, source_db: str = "") -> models.Import:
    """Imports an export, given as its bytes or as a binary file open on it. The records are
    read as the file streams and written BATCH at a time, all in one transaction: an export of
    20,000 records with their cited references never sits whole in memory (D-56)."""
    imp = models.Import(review_id=review.id, filename=filename[:300], format="", source_db=source_db[:120],
                        created_by=user.id if user else None)
    db.add(imp)
    db.flush()
    n, skipped, fmt, batch = 0, 0, "", []
    for r in biblio.iter_file(filename, data):
        fmt = fmt or r.get("_format", "")
        rec = biblio.normalise(r)
        if not rec["title"] and not rec["doi"]:
            skipped += 1
            continue
        if source_db and source_db.lower() not in rec["source_db"].lower():
            rec["source_db"] = source_db
        batch.append({**{f: rec[f] for f in RECORD_FIELDS}, "review_id": review.id, "import_id": imp.id})
        if len(batch) == BATCH:
            db.execute(models.Record.__table__.insert(), batch)
            n, batch = n + len(batch), []
    if batch:
        db.execute(models.Record.__table__.insert(), batch)
        n += len(batch)
    if not fmt:
        if not isinstance(data, (bytes, bytearray)):
            data.seek(0)
        fmt = biblio.file_format(filename, data)
    imp.format = fmt
    imp.n_records, imp.n_skipped = n, skipped
    db.add(models.ActivityLog(review_id=review.id, user_id=user.id if user else None, kind="import",
                              detail={"filename": filename, "n": n, "format": fmt}))
    db.commit()
    db.refresh(imp)
    return imp


def delete_import(db: Session, review: models.Review, imp: models.Import) -> int:
    """Deletes the import, its records and their stored PDFs."""
    pdf_keys = db.scalars(select(models.Record.pdf_key).where(models.Record.import_id == imp.id,
                                                              models.Record.review_id == review.id,
                                                              models.Record.pdf_key != "")).all()
    from krinea_api.services import dedup as dedup_service
    # Records of other files that absorbed this file's duplicates are recomputed without them.
    absorbed_by = set(db.scalars(select(models.Record.duplicate_of).where(
        models.Record.import_id == imp.id, models.Record.review_id == review.id,
        models.Record.duplicate_of.is_not(None))))
    n = db.execute(delete(models.Record).where(models.Record.import_id == imp.id,
                                                models.Record.review_id == review.id)).rowcount
    # Duplicates whose keeper vanished become visible again
    keeper_ids = select(models.Record.id).where(models.Record.review_id == review.id)
    orphans = set(db.scalars(select(models.Record.id).where(models.Record.review_id == review.id,
                                                            models.Record.duplicate_of.is_not(None),
                                                            models.Record.duplicate_of.not_in(keeper_ids))))
    db.execute(update(models.Record).where(models.Record.id.in_(orphans))
               .values(is_duplicate=False, duplicate_of=None, dup_score=None, dup_reason=""))
    db.flush()
    for rid in absorbed_by | orphans:
        rec = db.get(models.Record, rid)
        if rec is not None:
            dedup_service.rebuild(db, rec)
    db.delete(imp)
    db.commit()
    storage.delete_pdfs(pdf_keys)
    return n
