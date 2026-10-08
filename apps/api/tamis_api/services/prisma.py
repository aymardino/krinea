"""PRISMA 2020 counts for a review."""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from tamis_api import models
from tamis_api.services import screening as scr


def counts(db: Session, review: models.Review) -> dict:
    c = scr.compute(db, review)
    rows = db.execute(select(models.Record.id, models.Record.source_db, models.Record.pdf_status,
                             models.Record.is_duplicate).where(models.Record.review_id == review.id)).all()
    by_source: dict[str, int] = defaultdict(int)
    for _, src, _, _ in rows:
        for s in str(src or "").split(";"):
            by_source[s.strip() or "(unspecified)"] += 1
    pdf_status = {rid: ps for rid, _, ps, _ in rows}
    ta, ft = c["ta_status"], c["ft_status"]
    sought = c["ft_pool"]
    not_retrieved = [rid for rid in sought if pdf_status.get(rid) == "not_retrieved"]
    assessed = [rid for rid in sought if rid not in set(not_retrieved)]
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
    ta_excluded = sum(1 for rid in c["unique_ids"] if ta[rid] == "exclude")
    ta_included = len(sought)
    return {
        "identified": len(rows),
        "by_source": dict(sorted(by_source.items())),
        "duplicates_removed": sum(1 for r in rows if r[3]),
        "automation_excluded": 0,
        "other_removed": 0,
        "screened": len(c["unique_ids"]),
        "ta_excluded": ta_excluded,
        "ta_pending": len(c["unique_ids"]) - ta_excluded - ta_included,
        "sought": len(sought),
        "not_retrieved": len(not_retrieved),
        "assessed": len(assessed),
        "ft_excluded": ft_excluded,
        "ft_excluded_reasons": dict(sorted(reasons.items(), key=lambda kv: -kv[1])),
        "ft_pending": len(assessed) - ft_excluded - ft_included,
        "included": ft_included,
        "reports_included": ft_included,
    }
