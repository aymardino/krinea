"""
biblio.py — Import and export of bibliographic search results.

Reads RIS (.ris, .txt), BibTeX (.bib), PubMed/MEDLINE (.nbib, .txt), Web of
Science plain text (.txt), CSV/TSV (Scopus, Web of Science, Google Scholar,
Zotero, Mendeley exports…) and Excel (.xlsx), and normalises everything to one
flat record dict so that deduplication and screening never need to know where
a record came from.

    import biblio
    records = biblio.parse_file("scopus.ris", open("scopus.ris", "rb").read())
    records[0]["title"], records[0]["doi"], records[0]["abstract"]

Writes RIS and CSV for the records you want to export (e.g. included studies).
Only pandas is needed, and only for CSV/Excel inputs.
"""
from __future__ import annotations

import csv
import io
import re
import unicodedata

RECORD_FIELDS = ["title", "abstract", "authors", "year", "journal", "volume", "issue",
                 "pages", "doi", "url", "keywords", "pmid", "publisher", "type",
                 "language", "source_db", "raw_id"]

_DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\"'<>]+", re.I)
_YEAR_RE = re.compile(r"(?<!\d)(1[89]\d{2}|20\d{2})(?!\d)")


# ── Field helpers ────────────────────────────────────────────────────────────────
def clean_doi(value) -> str:
    """Extract a bare, lower-case DOI from any string (URL, 'doi:' prefix, free text)."""
    m = _DOI_RE.search(str(value or ""))
    if not m:
        return ""
    doi = m.group(0).rstrip(".,;:")
    # A trailing ')' only belongs to the DOI if it closes a '(' inside it
    while doi.endswith(")") and doi.count("(") < doi.count(")"):
        doi = doi[:-1]
    return doi.lower()


def clean_year(value) -> str:
    m = _YEAR_RE.search(str(value or ""))
    return m.group(1) if m else ""


def _clean_text(s) -> str:
    s = str(s or "")
    s = "".join(c for c in s if c >= " " or c in "\t\n")
    return " ".join(s.split())


def split_list(value) -> list[str]:
    """Split a '; '-joined field (authors, keywords) back into a list."""
    return [x.strip() for x in str(value or "").split(";") if x.strip()]


def _join(items) -> str:
    seen, out = set(), []
    for it in items:
        it = _clean_text(it)
        if it and it.lower() not in seen:
            seen.add(it.lower())
            out.append(it)
    return "; ".join(out)


def normalise(rec: dict) -> dict:
    """Return a record with every RECORD_FIELDS key, cleaned values, bare DOI."""
    out = {f: "" for f in RECORD_FIELDS}
    for k, v in rec.items():
        if k not in out:
            continue
        out[k] = _join(v) if isinstance(v, (list, tuple)) else _clean_text(v)
    out["doi"] = clean_doi(out["doi"]) or clean_doi(out["url"])
    out["year"] = clean_year(out["year"])
    out["pmid"] = re.sub(r"\D", "", out["pmid"])[:12]
    return out


def _first(d: dict, *tags) -> str:
    for t in tags:
        for v in d.get(t, []):
            if v.strip():
                return v.strip()
    return ""


def _all(d: dict, *tags) -> list[str]:
    return [v.strip() for t in tags for v in d.get(t, []) if v.strip()]


# ── RIS ──────────────────────────────────────────────────────────────────────────
_RIS_TAG = re.compile(r"^([A-Z][A-Z0-9])\s{1,2}-\s?(.*)$")


def parse_ris(text: str) -> list[dict]:
    records, cur, last = [], None, None
    for raw in text.lstrip("\ufeff").splitlines():
        line = raw.rstrip()
        m = _RIS_TAG.match(line)
        if m:
            tag, val = m.group(1), m.group(2).strip()
            if tag == "TY":
                if cur:
                    records.append(_ris_record(cur))
                cur, last = {"TY": [val]}, "TY"
                continue
            if tag == "ER":
                if cur is not None:
                    records.append(_ris_record(cur))
                cur, last = None, None
                continue
            if cur is None:
                cur = {}
            cur.setdefault(tag, []).append(val)
            last = tag
        elif cur is not None and last and line.strip():
            # Continuation line of a wrapped field (abstracts, long titles)
            cur[last][-1] = (cur[last][-1] + " " + line.strip()).strip()
    if cur:
        records.append(_ris_record(cur))
    return records


def _ris_record(d: dict) -> dict:
    pages = _first(d, "SP")
    ep = _first(d, "EP")
    if ep and pages and "-" not in pages:
        pages = f"{pages}-{ep}"
    doi = clean_doi(_first(d, "DO", "DI"))
    if not doi:
        for t in ("UR", "L1", "L2", "L3", "LK", "M3", "N1", "ID", "AN"):
            doi = clean_doi(" ".join(d.get(t, [])))
            if doi:
                break
    return normalise({
        "title": _first(d, "TI", "T1", "CT", "BT"),
        "abstract": _first(d, "AB", "N2"),
        "authors": _all(d, "AU", "A1"),
        "year": _first(d, "PY", "Y1", "DA", "Y2"),
        "journal": _first(d, "JO", "JF", "T2", "JA", "J2"),
        "volume": _first(d, "VL"), "issue": _first(d, "IS"), "pages": pages,
        "doi": doi, "url": _first(d, "UR", "L1", "L2"),
        "keywords": _all(d, "KW"), "pmid": _first(d, "PM"),
        "publisher": _first(d, "PB"), "type": _first(d, "TY"),
        "language": _first(d, "LA"), "source_db": _first(d, "DB", "DP"),
        "raw_id": _first(d, "ID", "AN"),
    })


# ── PubMed / MEDLINE (.nbib) ─────────────────────────────────────────────────────
_NBIB_TAG = re.compile(r"^([A-Z]{2,4})\s*- (.*)$")


def parse_nbib(text: str) -> list[dict]:
    records, cur, last = [], None, None
    for raw in text.lstrip("\ufeff").splitlines():
        line = raw.rstrip()
        if not line.strip():
            if cur:
                records.append(_nbib_record(cur))
            cur, last = None, None
            continue
        m = _NBIB_TAG.match(line)
        if m and not line.startswith(" "):
            tag, val = m.group(1), m.group(2).strip()
            if cur is None:
                cur = {}
            cur.setdefault(tag, []).append(val)
            last = tag
        elif cur is not None and last:
            cur[last][-1] = (cur[last][-1] + " " + line.strip()).strip()
    if cur:
        records.append(_nbib_record(cur))
    return records


def _nbib_record(d: dict) -> dict:
    doi = ""
    for v in d.get("LID", []) + d.get("AID", []):
        if "[doi]" in v.lower():
            doi = clean_doi(v)
            break
    pmid = _first(d, "PMID")
    return normalise({
        "title": _first(d, "TI"), "abstract": _first(d, "AB"),
        "authors": _all(d, "FAU") or _all(d, "AU"),
        "year": _first(d, "DP"), "journal": _first(d, "JT", "TA"),
        "volume": _first(d, "VI"), "issue": _first(d, "IP"), "pages": _first(d, "PG"),
        "doi": doi, "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
        "keywords": _all(d, "MH", "OT"), "pmid": pmid,
        "type": _first(d, "PT"), "language": _first(d, "LA"),
        "source_db": "PubMed", "raw_id": pmid,
    })


# ── Web of Science plain text (FN/VR/PT … ER/EF) ─────────────────────────────────
_WOS_TAG = re.compile(r"^([A-Z][A-Z0-9]) (.*)$")


def parse_wos(text: str) -> list[dict]:
    records, cur, last = [], None, None
    for raw in text.lstrip("\ufeff").splitlines():
        line = raw.rstrip()
        if line.startswith("   ") and cur is not None and last:
            cur[last].append(line.strip())   # continuation = extra author / wrapped text
            continue
        m = _WOS_TAG.match(line)
        if not m:
            if line.strip() in ("ER", "EF") and cur:
                records.append(_wos_record(cur))
                cur, last = None, None
            continue
        tag, val = m.group(1), m.group(2).strip()
        if tag in ("FN", "VR"):
            continue
        if tag == "PT":
            if cur:
                records.append(_wos_record(cur))
            cur, last = {"PT": [val]}, "PT"
            continue
        if cur is None:
            cur = {}
        cur.setdefault(tag, []).append(val)
        last = tag
    if cur:
        records.append(_wos_record(cur))
    return records


def _wos_record(d: dict) -> dict:
    pages = _first(d, "BP")
    ep = _first(d, "EP")
    if pages and ep:
        pages = f"{pages}-{ep}"
    return normalise({
        "title": " ".join(d.get("TI", [])), "abstract": " ".join(d.get("AB", [])),
        "authors": _all(d, "AF") or _all(d, "AU"),
        "year": _first(d, "PY"), "journal": " ".join(d.get("SO", [])),
        "volume": _first(d, "VL"), "issue": _first(d, "IS"), "pages": pages,
        "doi": _first(d, "DI"), "keywords": _all(d, "DE", "ID"),
        "pmid": _first(d, "PM"), "publisher": _first(d, "PU"),
        "type": _first(d, "DT", "PT"), "language": _first(d, "LA"),
        "source_db": "Web of Science", "raw_id": _first(d, "UT"),
    })


# ── BibTeX ───────────────────────────────────────────────────────────────────────
_LATEX_SPECIALS = {"ss": "ß", "ae": "æ", "AE": "Æ", "oe": "œ", "OE": "Œ", "aa": "å",
                   "AA": "Å", "o": "ø", "O": "Ø", "l": "ł", "L": "Ł", "i": "ı"}
_LATEX_ACCENTS = {"'": "\u0301", "`": "\u0300", "^": "\u0302", '"': "\u0308", "~": "\u0303",
                  "=": "\u0304", ".": "\u0307", "u": "\u0306", "v": "\u030c", "H": "\u030b",
                  "c": "\u0327", "k": "\u0328", "r": "\u030a"}


def delatex(s: str) -> str:
    """Turn LaTeX-escaped text ({\\'e}, \\&, {Title}) into plain unicode."""
    s = str(s or "")

    def special(m):
        return _LATEX_SPECIALS[m.group(1)]

    def accent(m):
        base = m.group(2) or m.group(3)
        return unicodedata.normalize("NFC", base + _LATEX_ACCENTS[m.group(1)])

    s = re.sub(r"\\(ss|ae|AE|oe|OE|aa|AA|o|O|l|L|i)(?![A-Za-z])", special, s)
    s = re.sub(r"\\([`'^\"~=.])\s*(?:\{([A-Za-z\u0131])\}|([A-Za-z\u0131]))", accent, s)
    s = re.sub(r"\\([uvHckr])(?:\{([A-Za-z\u0131])\}|\s+([A-Za-z\u0131]))", accent, s)
    s = re.sub(r"\\([&%$_#{}])", r"\1", s)
    s = re.sub(r"\\[A-Za-z]+\s*", "", s)       # \textit, \emph, \url … keep their argument
    s = s.replace("---", "—").replace("--", "–").replace("~", " ")
    s = s.replace("{", "").replace("}", "")
    return " ".join(s.split())


def parse_bibtex(text: str) -> list[dict]:
    text = text.lstrip("\ufeff")
    records, pos = [], 0
    while True:
        at = text.find("@", pos)
        if at < 0:
            break
        m = re.match(r"@\s*([A-Za-z]+)\s*([{(])", text[at:])
        if not m:
            pos = at + 1
            continue
        etype, opener = m.group(1).lower(), m.group(2)
        closer = "}" if opener == "{" else ")"
        i = at + m.end()
        depth, j = 0, i
        while j < len(text):
            c = text[j]
            if c == "{":
                depth += 1
            elif c == "}" and depth > 0:
                depth -= 1
            elif c == closer and depth == 0:
                break
            j += 1
        body, pos = text[i:j], j + 1
        if etype in ("comment", "preamble", "string"):
            continue
        fields = _bib_fields(body)
        if fields is None:
            continue
        fields["_type"] = etype
        records.append(_bib_record(fields))
    return records


def _bib_fields(body: str):
    comma = body.find(",")
    if comma < 0:
        return None
    fields = {"_key": body[:comma].strip()}
    s = body[comma + 1:]
    i, n = 0, len(s)
    while i < n:
        while i < n and (s[i].isspace() or s[i] == ","):
            i += 1
        if i >= n:
            break
        j = i
        while j < n and s[j] not in "=,":
            j += 1
        name = s[i:j].strip().lower()
        if j >= n or s[j] != "=":
            i = j + 1
            continue
        i = j + 1
        parts = []
        while True:
            while i < n and s[i].isspace():
                i += 1
            if i >= n:
                break
            c = s[i]
            if c == "{":
                depth, k = 1, i + 1
                while k < n and depth:
                    if s[k] == "{":
                        depth += 1
                    elif s[k] == "}":
                        depth -= 1
                    k += 1
                parts.append(s[i + 1:k - 1])
                i = k
            elif c == '"':
                k, depth = i + 1, 0
                while k < n:
                    if s[k] == "{":
                        depth += 1
                    elif s[k] == "}":
                        depth -= 1
                    elif s[k] == '"' and depth == 0 and s[k - 1] != "\\":
                        break
                    k += 1
                parts.append(s[i + 1:k])
                i = k + 1
            else:
                k = i
                while k < n and s[k] not in ",#\n":
                    k += 1
                parts.append(s[i:k].strip())
                i = k
            while i < n and s[i].isspace():
                i += 1
            if i < n and s[i] == "#":      # string concatenation
                i += 1
                continue
            break
        if name:
            fields[name] = delatex(" ".join(parts))
    return fields


def _bib_record(f: dict) -> dict:
    authors = [a for a in re.split(r"\s+and\s+", f.get("author", ""), flags=re.I) if a.strip()]
    return normalise({
        "title": f.get("title", ""), "abstract": f.get("abstract", ""),
        "authors": authors, "year": f.get("year") or f.get("date", ""),
        "journal": f.get("journal") or f.get("journaltitle") or f.get("booktitle")
                   or f.get("series", ""),
        "volume": f.get("volume", ""), "issue": f.get("number") or f.get("issue", ""),
        "pages": f.get("pages", "").replace("–", "-"),
        "doi": f.get("doi", ""), "url": f.get("url", ""),
        "keywords": re.split(r"[;,]", f.get("keywords", "")),
        "pmid": f.get("pmid") or f.get("pubmed", ""),
        "publisher": f.get("publisher", ""), "type": f.get("_type", ""),
        "language": f.get("language", ""), "source_db": f.get("database", ""),
        "raw_id": f.get("_key", ""),
    })


# ── CSV / TSV / Excel ────────────────────────────────────────────────────────────
_COLUMN_SYNONYMS = {
    "title": ["title", "article title", "document title", "ti", "primary title", "titre",
              "item title", "name"],
    "abstract": ["abstract", "ab", "description", "résumé", "resume", "abstract note"],
    "authors": ["authors", "author", "au", "af", "author full names", "creators", "auteurs",
                "author(s)", "author names"],
    "year": ["year", "publication year", "py", "date", "publication date", "année",
             "annee", "issued", "pubyear"],
    "journal": ["journal", "source title", "source", "journal/book", "publication title",
                "secondary title", "container-title", "so", "publication", "journal name",
                "periodical", "journal title", "book title"],
    "volume": ["volume", "vl", "vol"],
    "issue": ["issue", "is", "number", "no", "issue number"],
    "pages": ["pages", "page range", "pg", "page"],
    "doi": ["doi", "di", "digital object identifier", "link doi"],
    "url": ["url", "link", "links", "dl", "uri", "article url"],
    "keywords": ["keywords", "author keywords", "keyword", "index keywords", "mesh terms",
                 "de", "manual tags", "tags", "mots-clés", "keywords plus"],
    "pmid": ["pmid", "pubmed id", "pubmed_id", "pm"],
    "publisher": ["publisher", "pu"],
    "type": ["type", "document type", "item type", "dt", "publication type"],
    "language": ["language", "language of original document", "la"],
    "source_db": ["source database", "database", "source_db", "db"],
    "raw_id": ["id", "key", "eid", "ut", "accession number", "record id"],
}
_PAGE_START = ["page start", "start page", "bp", "first page", "pagestart"]
_PAGE_END = ["page end", "end page", "ep", "last page", "pageend"]


def decode_bytes(data: bytes) -> str:
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def parse_table(data: bytes, filename: str = "") -> list[dict]:
    import pandas as pd
    if filename.lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(io.BytesIO(data), dtype=str)
    else:
        text = decode_bytes(data)
        df = pd.read_csv(io.StringIO(text), sep=None, engine="python", dtype=str,
                         keep_default_na=False, on_bad_lines="skip")
    df = df.fillna("")
    cols = {str(c).strip().lower(): c for c in df.columns}
    mapping = {}
    for field, names in _COLUMN_SYNONYMS.items():
        for name in names:
            if name in cols:
                mapping[field] = cols[name]
                break
    p_start = next((cols[n] for n in _PAGE_START if n in cols), None)
    p_end = next((cols[n] for n in _PAGE_END if n in cols), None)
    if "title" not in mapping and "doi" not in mapping:
        raise ValueError("No title or DOI column found. Columns seen: "
                         + ", ".join(str(c) for c in df.columns[:15]))
    records = []
    for _, row in df.iterrows():
        rec = {f: str(row[c]) for f, c in mapping.items()}
        if not rec.get("pages") and p_start and str(row[p_start]).strip():
            rec["pages"] = str(row[p_start]).strip()
            if p_end and str(row[p_end]).strip():
                rec["pages"] += "-" + str(row[p_end]).strip()
        if rec.get("authors") and ";" not in rec["authors"] and " and " in rec["authors"]:
            rec["authors"] = "; ".join(a.strip() for a in rec["authors"].split(" and "))
        if rec.get("keywords") and ";" not in rec["keywords"]:
            rec["keywords"] = "; ".join(k.strip() for k in rec["keywords"].split(","))
        records.append(normalise(rec))
    return records


# ── Dispatcher ───────────────────────────────────────────────────────────────────
def detect_format(filename: str, text: str = "") -> str:
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext == "ris":
        return "ris"
    if ext in ("bib", "bibtex"):
        return "bibtex"
    if ext == "nbib":
        return "nbib"
    if ext in ("csv", "tsv", "xlsx", "xls"):
        return "table"
    head = text.lstrip("\ufeff")[:5000]
    if re.search(r"^PMID- ", head, re.M):
        return "nbib"
    if re.search(r"^TY\s{1,2}- ", head, re.M):
        return "ris"
    if re.search(r"^\s*@[A-Za-z]+\s*[{(]", head, re.M):
        return "bibtex"
    if head.startswith("FN ") or re.search(r"^PT [JBSPC]\s*$", head, re.M):
        return "wos"
    first = head.splitlines()[0] if head.splitlines() else ""
    if "\t" in first or "," in first:
        return "table"
    return "ris"


PARSERS = {"ris": parse_ris, "bibtex": parse_bibtex, "nbib": parse_nbib, "wos": parse_wos}


def parse_file(filename: str, data: bytes) -> list[dict]:
    """Parse any supported export. Returns a list of normalised records."""
    text = "" if filename.lower().endswith((".xlsx", ".xls")) else decode_bytes(data)
    fmt = detect_format(filename, text)
    records = parse_table(data, filename) if fmt == "table" else PARSERS[fmt](text)
    for r in records:
        r["_format"] = fmt
    return records


# ── Export ───────────────────────────────────────────────────────────────────────
_RIS_TYPES = {"article": "JOUR", "jour": "JOUR", "journal article": "JOUR", "book": "BOOK",
              "inbook": "CHAP", "incollection": "CHAP", "chap": "CHAP",
              "inproceedings": "CONF", "conference paper": "CONF", "conf": "CONF",
              "techreport": "RPRT", "report": "RPRT", "rprt": "RPRT", "phdthesis": "THES",
              "mastersthesis": "THES", "thes": "THES", "misc": "GEN"}


def to_ris(records) -> str:
    out = []
    for r in records:
        ty = _RIS_TYPES.get(str(r.get("type", "")).strip().lower(), "JOUR")
        lines = [f"TY  - {ty}"]
        for a in split_list(r.get("authors")):
            lines.append(f"AU  - {a}")
        for tag, field in (("TI", "title"), ("PY", "year"), ("JO", "journal"), ("VL", "volume"),
                           ("IS", "issue"), ("SP", "pages"), ("DO", "doi"), ("UR", "url"),
                           ("AB", "abstract"), ("PB", "publisher"), ("LA", "language"),
                           ("DB", "source_db")):
            v = str(r.get(field, "") or "").strip()
            if v:
                lines.append(f"{tag}  - {v}")
        for k in split_list(r.get("keywords")):
            lines.append(f"KW  - {k}")
        lines.append("ER  - ")
        out.append("\n".join(lines))
    return "\n\n".join(out) + ("\n" if out else "")


def to_csv(records, extra_fields=()) -> str:
    fields = list(RECORD_FIELDS) + [f for f in extra_fields if f not in RECORD_FIELDS]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    w.writeheader()
    for r in records:
        w.writerow({f: r.get(f, "") for f in fields})
    return buf.getvalue()
