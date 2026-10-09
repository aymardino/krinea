"""
dedup.py — Duplicate detection across imported search results.

Three signals, from certain to fuzzy:
  1. same DOI                                   -> certain
  2. identical normalised title                 -> certain (unless the DOIs differ)
  3. fuzzy title similarity (rapidfuzz ratio)   -> certain above `auto_threshold`
     when the year or the first author agrees, otherwise "possible" and left
     for a human to confirm, as Rayyan does.

    pairs = dedup.find_duplicates(records)          # list of Pair
    certain = [p for p in pairs if p.certain]
    for group in dedup.cluster(certain, len(records)):
        keeper = dedup.choose_keeper(records, group)
        merged = dedup.merge_records(records, keeper, group)

Records are plain dicts with at least title / doi / year / authors / abstract.
rapidfuzz is used when installed; difflib is the (slower) fallback.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from krinea_core.biblio import RECORD_FIELDS, clean_doi, clean_year

try:
    from rapidfuzz import fuzz, process
    HAVE_RAPIDFUZZ = True
except ImportError:                       # pragma: no cover - fallback path
    import difflib
    HAVE_RAPIDFUZZ = False


@dataclass
class Pair:
    a: int
    b: int
    score: float
    reason: str
    certain: bool


# ── Normalisation ────────────────────────────────────────────────────────────────
def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", str(s or ""))
                   if not unicodedata.combining(c))


def norm_title(title) -> str:
    t = strip_accents(str(title or "")).lower()
    t = re.sub(r"<[^>]+>", " ", t)              # HTML tags some databases leave in
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return " ".join(t.split())


def first_author_key(authors) -> str:
    """Surname of the first author, normalised ('Smith, J.' / 'J Smith' / 'Smith J.')."""
    first = re.split(r";|\band\b", str(authors or ""), maxsplit=1)[0].strip()
    if not first:
        return ""
    if "," in first:
        surname = first.split(",")[0]
    else:
        parts = first.split()
        # 'Smith J.' (Scopus) vs 'John Smith': initials are short tokens ending in '.'
        if len(parts) > 1 and re.fullmatch(r"(?:[A-Z]\.?)+", parts[-1]):
            surname = parts[0]
        else:
            surname = parts[-1]
    return norm_title(surname)


def similarity(a: str, b: str) -> float:
    if HAVE_RAPIDFUZZ:
        return float(fuzz.ratio(a, b))
    return difflib.SequenceMatcher(None, a, b).ratio() * 100.0


# ── Detection ────────────────────────────────────────────────────────────────────
def find_duplicates(records, auto_threshold: float = 95.0, review_threshold: float = 85.0,
                    min_title_len: int = 20) -> list[Pair]:
    """Return one Pair per suspected duplicate pair (indices into `records`)."""
    n = len(records)
    titles = [norm_title(r.get("title")) for r in records]
    dois = [clean_doi(r.get("doi")) for r in records]
    years = [clean_year(r.get("year")) for r in records]
    authors = [first_author_key(r.get("authors")) for r in records]
    best: dict[tuple[int, int], Pair] = {}

    def add(i, j, score, reason, certain):
        key = (i, j) if i < j else (j, i)
        cur = best.get(key)
        if cur is None or score > cur.score or (score == cur.score and certain and not cur.certain):
            best[key] = Pair(key[0], key[1], round(score, 1), reason, certain)

    # 1. Same DOI
    groups: dict[str, list[int]] = {}
    for i, d in enumerate(dois):
        if d:
            groups.setdefault(d, []).append(i)
    for idxs in groups.values():
        for x in range(len(idxs)):
            for y in range(x + 1, len(idxs)):
                add(idxs[x], idxs[y], 100.0, "same DOI", True)

    # 2. Identical normalised title
    groups = {}
    for i, t in enumerate(titles):
        if len(t) >= min_title_len:
            groups.setdefault(t, []).append(i)
    for idxs in groups.values():
        for x in range(len(idxs)):
            for y in range(x + 1, len(idxs)):
                i, j = idxs[x], idxs[y]
                conflict = bool(dois[i] and dois[j] and dois[i] != dois[j])
                add(i, j, 100.0, "identical title" + (", but different DOI" if conflict else ""),
                    not conflict)

    # 3. Fuzzy title, only between records whose years are compatible
    by_year: dict[str, list[int]] = {}
    for i, y in enumerate(years):
        by_year.setdefault(y, []).append(i)

    def candidates(i):
        y = years[i]
        if y:
            buckets = {y, str(int(y) - 1), str(int(y) + 1), ""}
        else:
            buckets = set(by_year)
        for yy in buckets:
            for j in by_year.get(yy, []):
                if j > i and len(titles[j]) >= min_title_len and (i, j) not in best:
                    yield j

    for i in range(n):
        if len(titles[i]) < min_title_len:
            continue
        cand = list(candidates(i))
        if not cand:
            continue
        if HAVE_RAPIDFUZZ:
            hits = process.extract(titles[i], [titles[j] for j in cand], scorer=fuzz.ratio,
                                   score_cutoff=review_threshold, limit=None)
            hits = [(cand[idx], float(score)) for _, score, idx in hits]
        else:
            hits = [(j, similarity(titles[i], titles[j])) for j in cand]
            hits = [(j, s) for j, s in hits if s >= review_threshold]
        for j, score in hits:
            conflict = bool(dois[i] and dois[j] and dois[i] != dois[j])
            same_author = bool(authors[i] and authors[j] and authors[i] == authors[j])
            same_year = bool(years[i] and years[j] and years[i] == years[j])
            reason = f"title similarity {score:.0f}%"
            if conflict:
                reason += ", different DOI"
            elif same_author and same_year:
                reason += ", same first author and year"
            elif same_author:
                reason += ", same first author"
            elif same_year:
                reason += ", same year"
            certain = score >= auto_threshold and not conflict and (same_author or same_year)
            add(i, j, score, reason, certain)

    return sorted(best.values(), key=lambda p: (-p.score, p.a, p.b))


def cluster(pairs, n: int) -> list[list[int]]:
    """Union-find over pairs. Returns groups (size >= 2) of record indices."""
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for p in pairs:
        ra, rb = find(p.a), find(p.b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return sorted([sorted(g) for g in groups.values() if len(g) > 1], key=lambda g: g[0])


# ── Merging ──────────────────────────────────────────────────────────────────────
def completeness(rec: dict) -> int:
    score = len(str(rec.get("abstract") or ""))
    score += 50 * bool(rec.get("doi")) + 20 * bool(rec.get("keywords"))
    score += 10 * bool(rec.get("journal")) + 5 * bool(rec.get("year")) + 5 * bool(rec.get("authors"))
    score += 2 * bool(rec.get("pages")) + 2 * bool(rec.get("volume")) + bool(rec.get("url"))
    return score


def choose_keeper(records, idxs) -> int:
    """Index of the most complete record in the group (earliest import wins ties)."""
    return max(sorted(idxs), key=lambda i: (completeness(records[i]), -i))


def merge_records(records, keeper: int, idxs) -> dict:
    """Keeper's values, with its empty fields filled from the other duplicates.
    `source_db` becomes the union of all sources (useful for PRISMA per-database counts)."""
    merged = {f: records[keeper].get(f, "") for f in RECORD_FIELDS}
    sources = []
    for i in sorted(idxs):
        src = str(records[i].get("source_db") or "").strip()
        for s in src.split(";"):
            s = s.strip()
            if s and s not in sources:
                sources.append(s)
        if i == keeper:
            continue
        for f in RECORD_FIELDS:
            if not merged.get(f) and records[i].get(f):
                merged[f] = records[i][f]
    merged["source_db"] = "; ".join(sources)
    return merged
