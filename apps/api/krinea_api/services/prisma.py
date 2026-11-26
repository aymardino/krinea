"""PRISMA 2020 counts for a review."""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from krinea_api import models
from krinea_api.services import dedup
from krinea_api.services import screening as scr


def counts(db: Session, review: models.Review, import_ids: list[str] | None = None) -> dict:
    """The PRISMA 2020 counts of the review. With imported files given, those of their searches
    alone (D-57): the records they imported are identified, the unique records that count for
    them (`scr.in_file`) are screened, and the difference is the duplicates removed."""
    c = scr.compute(db, review)
    files = [f for f in (import_ids or []) if f]
    # Each record counts once, for the source it was imported with: a kept record also lists
    # the sources of the duplicates merged into it, which count through their own records.
    q = (select(models.Record.source_db, models.Import.source_db)
         .outerjoin(models.Import, models.Import.id == models.Record.import_id)
         .where(models.Record.review_id == review.id))
    unique = c["unique_ids"]
    if files:
        q = q.where(models.Record.import_id.in_(files))
        counted = set(db.scalars(select(models.Record.id).where(
            models.Record.review_id == review.id, models.Record.is_duplicate.is_(False), scr.in_files(review, files))))
        unique = [rid for rid in unique if rid in counted]
    sources = db.execute(q).all()
    by_source: dict[str, int] = defaultdict(int)
    for src, label in sources:
        by_source[dedup.own_source(src, label) or "(unspecified)"] += 1
    kept = set(unique)
    not_retrieved_ids = set(db.scalars(select(models.Record.id).where(
        models.Record.review_id == review.id, models.Record.pdf_status == "not_retrieved")))
    ta, ft = c["ta_status"], c["ft_status"]
    sought = [rid for rid in c["ft_pool"] if rid in kept]
    not_retrieved = [rid for rid in sought if rid in not_retrieved_ids]
    assessed = [rid for rid in sought if rid not in not_retrieved_ids]
    reasons: dict[str, int] = defaultdict(int)
    ft_excluded = 0
    ft_included = 0
    for rid in assessed:
        st = ft.get(rid, "pending")
        if st == "exclude":
            ft_excluded += 1
            reasons[scr.first_reason(c["decisions"]["ft"].get(rid, {})) or "(no reason given)"] += 1
        elif st == "include":
            ft_included += 1
    ta_excluded = sum(1 for rid in unique if ta[rid] == "exclude")
    ta_included = len(sought)
    return {
        "identified": len(sources),
        "by_source": dict(sorted(by_source.items())),
        "duplicates_removed": len(sources) - len(unique),
        "automation_excluded": 0,
        "other_removed": 0,
        "screened": len(unique),
        "ta_excluded": ta_excluded,
        "ta_pending": len(unique) - ta_excluded - ta_included,
        "sought": len(sought),
        "not_retrieved": len(not_retrieved),
        "assessed": len(assessed),
        "ft_excluded": ft_excluded,
        "ft_excluded_reasons": dict(sorted(reasons.items(), key=lambda kv: -kv[1])),
        "ft_pending": len(assessed) - ft_excluded - ft_included,
        "included": ft_included,
        "reports_included": ft_included,
    }
