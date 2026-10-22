"""Audience counts for the public pages, without cookies.

The web app's middleware reports each full page load of a public page over the private
network (`X-Krinea-Internal: 1` plus the shared proxy key). The API keeps the page, the day,
the interface language, the referring domain and a daily fingerprint; the IP address and
the browser signature are hashed with a secret that changes every day and never stored.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import re
from collections import Counter, defaultdict
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from krinea_api import models
from krinea_api.config import get_settings
from krinea_api.db import get_db
from krinea_api.urls import KEY_HEADER

router = APIRouter(prefix="/stats", tags=["stats"])
INTERNAL_HEADER = "x-krinea-internal"
PUBLIC_PATHS = frozenset({"/", "/pricing", "/about", "/contact", "/security", "/privacy", "/terms", "/legal",
                          "/sign-in", "/sign-up"})
BOT_RE = re.compile(r"bot|crawl|spider|slurp|preview|fetch|curl|wget|python|httpx|java/|headless|lighthouse|"
                    r"monitor|uptime|scan", re.I)
TOP = 12


class ViewIn(BaseModel):
    path: str = Field(max_length=200)
    lang: str = Field(default="", max_length=8)
    referrer: str = Field(default="", max_length=2000)
    ua: str = Field(default="", max_length=600)
    ip: str = Field(default="", max_length=64)


def visitor_hash(ip: str, ua: str, day: dt.date) -> str:
    """Daily fingerprint: the same visitor counts once a day, and nobody can get the address
    or the browser back from the stored value."""
    secret = get_settings().secret_key
    return hashlib.sha256(f"{secret}|{day.isoformat()}|{ip}|{ua}".encode()).hexdigest()[:32]


def referrer_host(referrer: str, own_hosts: set[str]) -> str:
    """The domain that linked to us; empty for direct visits and for our own pages."""
    try:
        host = (urlparse(referrer.strip()).hostname or "").lower()
    except ValueError:
        return ""
    host = host[4:] if host.startswith("www.") else host
    return "" if not host or host in own_hosts else host[:120]


def _internal(request: Request) -> bool:
    key = request.headers.get(KEY_HEADER, "")
    return (request.headers.get(INTERNAL_HEADER) == "1" and bool(key)
            and hmac.compare_digest(key.encode(), get_settings().secret_key.encode()))


@router.post("/view", status_code=204)
def record_view(body: ViewIn, request: Request, db: DBSession = Depends(get_db)) -> Response:
    if not _internal(request):
        raise HTTPException(403, "Internal endpoint")
    s = get_settings()
    path = body.path.split("?", 1)[0].rstrip("/") or "/"
    if not s.audience_stats or path not in PUBLIC_PATHS or not body.ua or BOT_RE.search(body.ua):
        return Response(status_code=204)
    now = models.now()
    own = {h for h in (urlparse(s.base_url).hostname or "",) if h}
    own |= {h[4:] for h in own if h.startswith("www.")}
    db.add(models.PageView(day=now.date(), path=path, lang=body.lang[:8],
                           referrer_host=referrer_host(body.referrer, own),
                           visitor_hash=visitor_hash(body.ip, body.ua, now.date())))
    db.commit()
    return Response(status_code=204)


def audience(db: DBSession, days: list[dt.date]) -> dict:
    """What the administration page shows for the given days (oldest first): page views and
    distinct visitors per day, the busiest pages and the referring domains."""
    week_start = days[-7] if len(days) >= 7 else days[0]
    rows = db.execute(select(models.PageView.day, models.PageView.path, models.PageView.referrer_host,
                             models.PageView.visitor_hash).where(models.PageView.day >= days[0])).all()
    views: Counter[dt.date] = Counter()
    visitors: dict[dt.date, set[str]] = defaultdict(set)
    pages: Counter[str] = Counter()
    referrers: Counter[str] = Counter()
    for day, path, host, fingerprint in rows:
        views[day] += 1
        visitors[day].add(fingerprint)
        pages[path] += 1
        referrers[host] += 1
    return {
        "views_7d": sum(v for d, v in views.items() if d >= week_start),
        "views_30d": len(rows),
        "visitors_7d": sum(len(v) for d, v in visitors.items() if d >= week_start),
        "visitors_30d": sum(len(v) for v in visitors.values()),
        "series": {"views": [views.get(d, 0) for d in days], "visitors": [len(visitors.get(d, ())) for d in days]},
        "pages": [{"path": p, "views": v} for p, v in pages.most_common(TOP)],
        "referrers": [{"host": h, "views": v} for h, v in referrers.most_common(TOP)],
    }
