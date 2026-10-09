"""Importing search exports into a review."""
from __future__ import annotations

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from krinea_api import models
from krinea_core import biblio

RECORD_FIELDS = biblio.RECORD_FIELDS


def import_file(db: Session, review: models.Review, user: models.User | None, filename: str,
                data: bytes, source_db: str = "") -> models.Import:
    records = biblio.parse_file(filename, data)
    fmt = records[0]["_format"] if records else biblio.detect_format(filename, biblio.decode_bytes(data[:5000]))
    imp = models.Import(review_id=review.id, filename=filename[:300], format=fmt, source_db=source_db[:120],
                        created_by=user.id if user else None)
    db.add(imp)
    db.flush()
    rows, skipped = [], 0
    for r in records:
        rec = biblio.normalise(r)
        if not rec["title"] and not rec["doi"]:
            skipped += 1
            continue
        if source_db and source_db.lower() not in rec["source_db"].lower():
            rec["source_db"] = source_db
        rows.append({**{f: rec[f] for f in RECORD_FIELDS}, "review_id": review.id, "import_id": imp.id})
    if rows:
        db.execute(models.Record.__table__.insert(), rows)
    imp.n_records, imp.n_skipped = len(rows), skipped
    db.add(models.ActivityLog(review_id=review.id, user_id=user.id if user else None, kind="import",
                              detail={"filename": filename, "n": len(rows), "format": fmt}))
    db.commit()
    db.refresh(imp)
    return imp


def delete_import(db: Session, review: models.Review, imp: models.Import) -> int:
    n = db.execute(delete(models.Record).where(models.Record.import_id == imp.id,
                                                models.Record.review_id == review.id)).rowcount
    # Duplicates whose keeper vanished become visible again
    keeper_ids = select(models.Record.id).where(models.Record.review_id == review.id)
    db.execute(update(models.Record).where(models.Record.review_id == review.id,
                                           models.Record.duplicate_of.is_not(None),
                                           models.Record.duplicate_of.not_in(keeper_ids))
               .values(is_duplicate=False, duplicate_of=None, dup_score=None, dup_reason=""))
    db.delete(imp)
    db.commit()
    return n
