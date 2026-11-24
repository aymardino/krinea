"""Which record a PDF belongs to, from what the PDF says about itself (D-55).

When many PDFs are added at once, each one is matched to a record by, in order of trust:

1. its DOI, read from the document's metadata, from its first page or from its file name.
   The rest of the document is never searched for DOIs: its reference list holds those of
   other papers, often other records of the same review;
2. its title: a record's title found at the top of its first two pages (a cover page may
   come first), or equal to the title in the document's metadata;
3. its file name, as reference managers write it ("Mwangi et al. - 2021 - Microgrids in
   Kenya.pdf"), the first author and the year set aside.

A match needs one clear winner. When two records fit as well (a conference paper and its
journal version, two DOIs of the review on one first page), none is picked and both are
offered first: the reviewer chooses.
"""
from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass

from rapidfuzz import fuzz

from krinea_core.biblio import clean_doi, find_dois

TITLE_MIN = 20        # characters: shorter titles ("Editorial") are too common to tell a paper by
TITLE_SCORE = 90      # how closely a title must be found (rapidfuzz partial ratio, 0 to 100)
MARGIN = 5            # how far the best title must lead the next one
HEAD_CHARS = 6000     # the top of the first two pages, where the title is
N_CANDIDATES = 5      # records offered to choose from


def norm(text: str | None) -> str:
    """Words without accents, case or punctuation; a word cut at a line end joined back."""
    text = re.sub(r"-\s*\n\s*", "", text or "")
    text = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)).lower()
    return " ".join(re.findall(r"[a-z0-9]+", text))


def _alnum(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


@dataclass
class Clues:
    """What a PDF says about itself."""
    meta_dois: list[str]        # DOIs of the document's metadata
    page_dois: list[str]        # DOIs of its first page
    meta_title: str             # the title in its metadata (often a file name, or empty)
    head: str                   # the top of its first two pages, normalised
    filename: str


def read_clues(data: bytes, filename: str = "") -> Clues:
    """The clues of a PDF; ValueError when it cannot be read."""
    import pymupdf

    from krinea_core.pdftext import reading
    with reading():
        try:
            doc = pymupdf.open(stream=data, filetype="pdf")
        except Exception as e:  # noqa: BLE001  (any parsing failure means the same to the reviewer)
            raise ValueError("This PDF cannot be read") from e
        try:
            meta = {k: str(v) for k, v in (doc.metadata or {}).items() if v}
            try:
                xmp = doc.get_xml_metadata() or ""
            except Exception:  # noqa: BLE001  (metadata is a bonus)
                xmp = ""
            pages = [doc[i].get_text() for i in range(min(2, doc.page_count))]
        finally:
            doc.close()
    meta_dois = find_dois(" ".join(meta.get(k, "") for k in ("subject", "keywords", "title")) + "\n" + xmp)
    return Clues(meta_dois, find_dois(pages[0]) if pages else [], meta.get("title", ""),
                 norm("\n".join(pages))[:HEAD_CHARS], filename or "")


def _title_score(title: str, head: str, meta_title: str) -> int:
    if len(title) < TITLE_MIN:
        return 0
    # A head shorter than the title (a scanned page with a few stray characters) would
    # "contain" any title it shares a word with.
    score = fuzz.partial_ratio(title, head) if len(head) >= len(title) else 0.0
    if meta_title:
        score = max(score, fuzz.ratio(title, meta_title))
    return round(score)


def _name_score(title: str, stem: str, record: dict) -> int:
    if len(title) < TITLE_MIN or not stem:
        return 0
    first = (record.get("authors") or "").split(";")[0]
    surname = first.split(",")[0] if "," in first else (first.split()[-1] if first.split() else "")
    aside = set(norm(surname).split()) | set(re.findall(r"\d{4}", record.get("year") or "")) | {"et", "al"}
    rest = " ".join(w for w in stem.split() if w not in aside)
    if len(rest) < TITLE_MIN:
        return 0
    return round(fuzz.partial_ratio(rest, title) if len(rest) <= len(title) else fuzz.ratio(rest, title))


def _winner(scores: dict[int, int]) -> int | None:
    """The record whose score reaches TITLE_SCORE and leads the next one by MARGIN."""
    best = sorted(scores.items(), key=lambda kv: -kv[1])
    if best and best[0][1] >= TITLE_SCORE and (len(best) == 1 or best[1][1] <= best[0][1] - MARGIN):
        return best[0][0]
    return None


@dataclass
class Match:
    record_id: int | None       # the record picked, or None
    how: str                    # "doi", "title", "filename", or "" when none is picked
    candidates: list[tuple[int, int]]   # (record id, score 0 to 100), the record picked first


def match(clues: Clues, records: list[dict]) -> Match:
    """The record of `records` (dicts with id, title, doi, authors and year) the PDF belongs to."""
    by_doi: dict[str, list[int]] = {}
    for r in records:
        d = clean_doi(r.get("doi"))
        if d:
            by_doi.setdefault(d, []).append(r["id"])
    unique = {d: ids[0] for d, ids in by_doi.items() if len(ids) == 1}
    stem = norm(os.path.splitext(os.path.basename(clues.filename))[0])
    meta_title = norm(clues.meta_title)
    title_s: dict[int, int] = {}
    name_s: dict[int, int] = {}
    for r in records:
        t = norm(r.get("title"))
        title_s[r["id"]] = _title_score(t, clues.head, meta_title)
        name_s[r["id"]] = _name_score(t, stem, r)

    meta_hit = next((unique[d] for d in clues.meta_dois if d in unique), None)
    page_hits = list(dict.fromkeys(unique[d] for d in clues.page_dois if d in unique))
    name_alnum = stem.replace(" ", "")
    name_hits = list(dict.fromkeys(rid for d, rid in unique.items() if len(_alnum(d)) >= 10 and _alnum(d) in name_alnum))

    rid, how = None, ""
    if meta_hit is not None:
        rid, how = meta_hit, "doi"
    elif len(page_hits) == 1:
        rid, how = page_hits[0], "doi"
    elif page_hits:                 # DOIs of several records on the first page: the title tells
        rid = _winner({k: title_s[k] for k in page_hits})
        how = "title" if rid is not None else ""
    elif len(name_hits) == 1:
        rid, how = name_hits[0], "doi"
    elif not name_hits:
        rid = _winner(title_s)
        how = "title" if rid is not None else ""
        if rid is None:
            rid = _winner(name_s)
            how = "filename" if rid is not None else ""

    doi_hits = set(page_hits) | set(name_hits) | ({meta_hit} if meta_hit is not None else set())
    score = {r["id"]: 100 if r["id"] in doi_hits else max(title_s[r["id"]], name_s[r["id"]]) for r in records}
    order = sorted(score, key=lambda k: (k != rid, -score[k]))
    return Match(rid, how, [(k, score[k]) for k in order[:N_CANDIDATES]])
