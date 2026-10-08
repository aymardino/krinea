"""
review_db.py — SQLite storage for systematic-review projects.

One file (review.db, in DATA_DIR) holds every project: imported records,
duplicate decisions, screening decisions per reviewer and stage, AI
suggestions and the author-defined data extractions.

    import review_db
    review_db.configure("/var/data/review.db")      # creates tables if needed
    pid = review_db.create_project("Solar mini-grids in Africa")
    review_db.add_records(pid, biblio.parse_file("scopus.ris", data), "scopus.ris", "Scopus")

Everything returns plain dicts or pandas DataFrames so the Streamlit app and
the tests stay simple.
"""
from __future__ import annotations

import datetime as dt
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

import pandas as pd

import biblio
import extraction_schema
import screening

DB_PATH = Path("review.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT DEFAULT '',
    criteria_json TEXT DEFAULT '{}',
    schema_json TEXT DEFAULT '',
    created_at TEXT);

CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title TEXT DEFAULT '', abstract TEXT DEFAULT '', authors TEXT DEFAULT '',
    year TEXT DEFAULT '', journal TEXT DEFAULT '', volume TEXT DEFAULT '',
    issue TEXT DEFAULT '', pages TEXT DEFAULT '', doi TEXT DEFAULT '', url TEXT DEFAULT '',
    keywords TEXT DEFAULT '', pmid TEXT DEFAULT '', publisher TEXT DEFAULT '',
    type TEXT DEFAULT '', language TEXT DEFAULT '', source_db TEXT DEFAULT '',
    raw_id TEXT DEFAULT '', source_file TEXT DEFAULT '', imported_at TEXT,
    is_duplicate INTEGER DEFAULT 0, duplicate_of INTEGER, dup_score REAL,
    dup_reason TEXT DEFAULT '',
    pdf_path TEXT DEFAULT '', pdf_status TEXT DEFAULT '', notes TEXT DEFAULT '');
CREATE INDEX IF NOT EXISTS idx_records_project ON records(project_id);

CREATE TABLE IF NOT EXISTS dedup_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    record_a INTEGER NOT NULL REFERENCES records(id) ON DELETE CASCADE,
    record_b INTEGER NOT NULL REFERENCES records(id) ON DELETE CASCADE,
    score REAL, reason TEXT DEFAULT '', status TEXT DEFAULT 'pending',
    UNIQUE(record_a, record_b));

CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id INTEGER NOT NULL REFERENCES records(id) ON DELETE CASCADE,
    stage TEXT NOT NULL, reviewer TEXT NOT NULL, decision TEXT NOT NULL,
    reason TEXT DEFAULT '', labels TEXT DEFAULT '', note TEXT DEFAULT '',
    decided_at TEXT,
    UNIQUE(record_id, stage, reviewer));

CREATE TABLE IF NOT EXISTS ai_suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id INTEGER NOT NULL REFERENCES records(id) ON DELETE CASCADE,
    stage TEXT NOT NULL, decision TEXT, reason TEXT DEFAULT '',
    rationale TEXT DEFAULT '', confidence REAL, model TEXT DEFAULT '', created_at TEXT,
    UNIQUE(record_id, stage));

CREATE TABLE IF NOT EXISTS extractions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id INTEGER NOT NULL UNIQUE REFERENCES records(id) ON DELETE CASCADE,
    model TEXT DEFAULT '', status TEXT DEFAULT 'draft',
    created_at TEXT, verified_at TEXT,
    values_json TEXT DEFAULT '{}', quotes_json TEXT DEFAULT '{}', ai_json TEXT DEFAULT '{}',
    text_extracted TEXT DEFAULT '', pdf_path TEXT DEFAULT '', error TEXT DEFAULT '',
    review_seconds REAL);
"""

RECORD_COLUMNS = biblio.RECORD_FIELDS + ["source_file", "imported_at", "is_duplicate",
                                         "duplicate_of", "dup_score", "dup_reason",
                                         "pdf_path", "pdf_status", "notes"]


def configure(path) -> None:
    """Point the module at a database file (created if missing)."""
    global DB_PATH
    DB_PATH = Path(path)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    init_db()


def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


@contextmanager
def _tx():
    """Write transaction: commit on success, rollback on error, always close."""
    con = _conn()
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


@contextmanager
def _ro():
    """Read-only connection that is always closed."""
    con = _conn()
    try:
        yield con
    finally:
        con.close()


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def init_db() -> None:
    with _tx() as con:
        con.executescript(SCHEMA)


def _query(sql, params=()) -> pd.DataFrame:
    with _ro() as con:
        return pd.read_sql_query(sql, con, params=params)


# ── Projects ─────────────────────────────────────────────────────────────────────
def create_project(name: str, description: str = "", criteria: dict | None = None,
                   schema=None) -> int:
    crit = screening.criteria_with_defaults(criteria)
    schema_json = extraction_schema.to_json(schema if schema is not None
                                            else extraction_schema.DEFAULT_SCHEMA)
    with _tx() as con:
        cur = con.execute("INSERT INTO projects (name, description, criteria_json, schema_json, "
                          "created_at) VALUES (?,?,?,?,?)",
                          (name.strip(), description, json.dumps(crit, ensure_ascii=False),
                           schema_json, _now()))
        pid = cur.lastrowid
    return pid


def list_projects() -> list[dict]:
    with _ro() as con:
        rows = con.execute("SELECT id, name, description, created_at FROM projects "
                           "ORDER BY name").fetchall()
    return [dict(r) for r in rows]


def get_project(pid: int) -> dict | None:
    with _ro() as con:
        row = con.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    if not row:
        return None
    p = dict(row)
    try:
        p["criteria"] = screening.criteria_with_defaults(json.loads(p.get("criteria_json") or "{}"))
    except json.JSONDecodeError:
        p["criteria"] = screening.criteria_with_defaults({})
    try:
        p["schema"] = extraction_schema.from_json(p.get("schema_json") or "")
    except (json.JSONDecodeError, TypeError):
        p["schema"] = [dict(f) for f in extraction_schema.DEFAULT_SCHEMA]
    return p


def update_project(pid: int, name: str | None = None, description: str | None = None,
                   criteria: dict | None = None, schema=None) -> None:
    sets, params = [], []
    if name is not None:
        sets.append("name=?"); params.append(name.strip())
    if description is not None:
        sets.append("description=?"); params.append(description)
    if criteria is not None:
        sets.append("criteria_json=?")
        params.append(json.dumps(screening.criteria_with_defaults(criteria), ensure_ascii=False))
    if schema is not None:
        sets.append("schema_json=?")
        params.append(schema if isinstance(schema, str) else extraction_schema.to_json(schema))
    if not sets:
        return
    params.append(pid)
    with _tx() as con:
        con.execute(f"UPDATE projects SET {', '.join(sets)} WHERE id=?", params)


def delete_project(pid: int) -> None:
    with _tx() as con:
        con.execute("DELETE FROM projects WHERE id=?", (pid,))


# ── Records ──────────────────────────────────────────────────────────────────────
def add_records(pid: int, records, source_file: str = "", source_db: str = "") -> tuple[int, int]:
    """Insert parsed records. Returns (added, skipped) — a record without title
    and without DOI is skipped."""
    now = _now()
    rows, skipped = [], 0
    for r in records:
        rec = biblio.normalise(r)
        if not rec["title"] and not rec["doi"]:
            skipped += 1
            continue
        if source_db and not rec["source_db"]:
            rec["source_db"] = source_db
        elif source_db and source_db.lower() not in rec["source_db"].lower():
            rec["source_db"] = source_db
        rows.append([pid] + [rec[f] for f in biblio.RECORD_FIELDS] + [source_file, now])
    if rows:
        cols = ["project_id"] + biblio.RECORD_FIELDS + ["source_file", "imported_at"]
        with _tx() as con:
            con.executemany(f"INSERT INTO records ({', '.join(cols)}) VALUES "
                            f"({', '.join('?' * len(cols))})", rows)
    return len(rows), skipped


def records_df(pid: int, include_duplicates: bool = False) -> pd.DataFrame:
    sql = "SELECT id, " + ", ".join(RECORD_COLUMNS) + " FROM records WHERE project_id=?"
    if not include_duplicates:
        sql += " AND is_duplicate=0"
    return _query(sql + " ORDER BY id", (pid,))


def get_record(rid: int) -> dict | None:
    with _ro() as con:
        row = con.execute("SELECT * FROM records WHERE id=?", (rid,)).fetchone()
    return dict(row) if row else None


def update_record(rid: int, **fields) -> None:
    allowed = {k: v for k, v in fields.items() if k in RECORD_COLUMNS}
    if not allowed:
        return
    with _tx() as con:
        con.execute(f"UPDATE records SET {', '.join(f'{k}=?' for k in allowed)} WHERE id=?",
                    list(allowed.values()) + [rid])


def delete_record(rid: int) -> None:
    with _tx() as con:
        con.execute("DELETE FROM records WHERE id=?", (rid,))


def import_batches(pid: int) -> pd.DataFrame:
    return _query("SELECT source_file, MIN(source_db) AS source_db, COUNT(*) AS records, "
                  "SUM(is_duplicate) AS duplicates, MIN(imported_at) AS imported_at "
                  "FROM records WHERE project_id=? GROUP BY source_file ORDER BY imported_at",
                  (pid,))


def delete_batch(pid: int, source_file: str) -> int:
    with _tx() as con:
        cur = con.execute("DELETE FROM records WHERE project_id=? AND source_file=?",
                          (pid, source_file))
        # Records that were merged into a now-deleted keeper become visible again
        con.execute("UPDATE records SET is_duplicate=0, duplicate_of=NULL, dup_score=NULL, "
                    "dup_reason='' WHERE project_id=? AND duplicate_of IS NOT NULL AND "
                    "duplicate_of NOT IN (SELECT id FROM records WHERE project_id=?)", (pid, pid))
    return cur.rowcount


# ── Duplicates ───────────────────────────────────────────────────────────────────
def reset_duplicates(pid: int) -> None:
    with _tx() as con:
        con.execute("UPDATE records SET is_duplicate=0, duplicate_of=NULL, dup_score=NULL, "
                    "dup_reason='' WHERE project_id=?", (pid,))
        con.execute("DELETE FROM dedup_candidates WHERE project_id=? AND status!='ignored'", (pid,))


def mark_duplicates(keeper_id: int, dup_ids, score: float, reason: str,
                    merged: dict | None = None) -> None:
    with _tx() as con:
        for d in dup_ids:
            if int(d) == int(keeper_id):
                continue
            con.execute("UPDATE records SET is_duplicate=1, duplicate_of=?, dup_score=?, "
                        "dup_reason=? WHERE id=?", (keeper_id, score, reason, int(d)))
            # Anything already pointing at the duplicate now points at the keeper
            con.execute("UPDATE records SET duplicate_of=? WHERE duplicate_of=?", (keeper_id, int(d)))
        if merged:
            cols = [f for f in biblio.RECORD_FIELDS if f in merged]
            con.execute(f"UPDATE records SET {', '.join(f'{c}=?' for c in cols)} WHERE id=?",
                        [merged[c] for c in cols] + [keeper_id])


def unmark_duplicate(rid: int) -> None:
    with _tx() as con:
        con.execute("UPDATE records SET is_duplicate=0, duplicate_of=NULL, dup_score=NULL, "
                    "dup_reason='' WHERE id=?", (rid,))


def duplicates_df(pid: int) -> pd.DataFrame:
    return _query(
        "SELECT d.id, d.title, d.year, d.doi, d.source_db, d.dup_score AS score, "
        "d.dup_reason AS reason, k.id AS kept_id, k.title AS kept_title, k.source_db AS kept_source "
        "FROM records d LEFT JOIN records k ON k.id = d.duplicate_of "
        "WHERE d.project_id=? AND d.is_duplicate=1 ORDER BY d.duplicate_of, d.id", (pid,))


def upsert_candidates(pid: int, pairs) -> None:
    """pairs: iterable of (record_a, record_b, score, reason). Ignored pairs stay ignored."""
    with _tx() as con:
        for a, b, score, reason in pairs:
            a, b = (int(a), int(b)) if int(a) < int(b) else (int(b), int(a))
            con.execute("INSERT INTO dedup_candidates (project_id, record_a, record_b, score, reason, "
                        "status) VALUES (?,?,?,?,?,'pending') ON CONFLICT(record_a, record_b) DO UPDATE "
                        "SET score=excluded.score, reason=excluded.reason "
                        "WHERE dedup_candidates.status='pending'", (pid, a, b, score, reason))


def candidates_df(pid: int, status: str = "pending") -> pd.DataFrame:
    return _query(
        "SELECT c.id, c.score, c.reason, c.status, "
        "a.id AS id_a, a.title AS title_a, a.authors AS authors_a, a.year AS year_a, "
        "a.journal AS journal_a, a.doi AS doi_a, a.source_db AS source_a, a.abstract AS abstract_a, "
        "b.id AS id_b, b.title AS title_b, b.authors AS authors_b, b.year AS year_b, "
        "b.journal AS journal_b, b.doi AS doi_b, b.source_db AS source_b, b.abstract AS abstract_b "
        "FROM dedup_candidates c JOIN records a ON a.id=c.record_a JOIN records b ON b.id=c.record_b "
        "WHERE c.project_id=? AND c.status=? AND a.is_duplicate=0 AND b.is_duplicate=0 "
        "ORDER BY c.score DESC, c.id", (pid, status))


def set_candidate_status(cid: int, status: str) -> None:
    with _tx() as con:
        con.execute("UPDATE dedup_candidates SET status=? WHERE id=?", (status, cid))


# ── Screening decisions ──────────────────────────────────────────────────────────
def set_decision(rid: int, stage: str, reviewer: str, decision: str, reason: str = "",
                 labels: str = "", note: str = "") -> None:
    if decision not in screening.DECISIONS:
        raise ValueError(f"decision must be one of {screening.DECISIONS}")
    with _tx() as con:
        con.execute("INSERT INTO decisions (record_id, stage, reviewer, decision, reason, labels, note, "
                    "decided_at) VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(record_id, stage, reviewer) DO "
                    "UPDATE SET decision=excluded.decision, reason=excluded.reason, "
                    "labels=excluded.labels, note=excluded.note, decided_at=excluded.decided_at",
                    (rid, stage, reviewer.strip(), decision, reason, labels, note, _now()))


def delete_decision(rid: int, stage: str, reviewer: str) -> None:
    with _tx() as con:
        con.execute("DELETE FROM decisions WHERE record_id=? AND stage=? AND reviewer=?",
                    (rid, stage, reviewer))


def decisions_df(pid: int, stage: str | None = None) -> pd.DataFrame:
    sql = ("SELECT d.record_id, d.stage, d.reviewer, d.decision, d.reason, d.labels, d.note, "
           "d.decided_at FROM decisions d JOIN records r ON r.id=d.record_id WHERE r.project_id=?")
    params: list = [pid]
    if stage:
        sql += " AND d.stage=?"
        params.append(stage)
    return _query(sql + " ORDER BY d.record_id, d.reviewer", tuple(params))


def reviewers(pid: int) -> list[str]:
    df = _query("SELECT DISTINCT d.reviewer FROM decisions d JOIN records r ON r.id=d.record_id "
                "WHERE r.project_id=? AND d.reviewer!='consensus' ORDER BY d.reviewer", (pid,))
    return df["reviewer"].tolist()


def stage_status(pid: int, stage: str, required: int = 1) -> pd.DataFrame:
    """One row per record of the stage's pool: record_id, status, n_decisions, summary."""
    pool = stage_pool(pid, stage, required)
    dec = decisions_df(pid, stage)
    by_rec: dict[int, dict] = {}
    reasons: dict[int, str] = {}
    for row in dec.itertuples(index=False):
        by_rec.setdefault(int(row.record_id), {})[row.reviewer] = row.decision
        if row.decision == "exclude" and row.reason and int(row.record_id) not in reasons:
            reasons[int(row.record_id)] = row.reason
    out = []
    for rid in pool["id"].tolist():
        d = by_rec.get(int(rid), {})
        out.append({"record_id": int(rid),
                    "status": screening.consensus(d, required),
                    "n_decisions": len([k for k in d if k != "consensus"]),
                    "summary": "; ".join(f"{k}: {v}" for k, v in sorted(d.items())),
                    "reason": reasons.get(int(rid), "")})
    return pd.DataFrame(out, columns=["record_id", "status", "n_decisions", "summary", "reason"])


def stage_pool(pid: int, stage: str, required: int = 1) -> pd.DataFrame:
    """Records a stage works on: 'ta' = all unique records, 'ft' = included at
    title/abstract, 'extract' = included at full text."""
    recs = records_df(pid)
    if stage == "ta":
        return recs
    prev = "ta" if stage == "ft" else "ft"
    st = stage_status(pid, prev, required)
    keep = set(st.loc[st["status"] == "include", "record_id"].tolist())
    return recs[recs["id"].isin(keep)].reset_index(drop=True)


# ── AI suggestions ───────────────────────────────────────────────────────────────
def save_ai_suggestion(rid: int, stage: str, s: dict) -> None:
    with _tx() as con:
        con.execute("INSERT INTO ai_suggestions (record_id, stage, decision, reason, rationale, "
                    "confidence, model, created_at) VALUES (?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(record_id, stage) DO UPDATE SET decision=excluded.decision, "
                    "reason=excluded.reason, rationale=excluded.rationale, "
                    "confidence=excluded.confidence, model=excluded.model, created_at=excluded.created_at",
                    (rid, stage, s.get("decision", "maybe"), s.get("reason", ""),
                     s.get("rationale", ""), float(s.get("confidence", 0.5) or 0.5),
                     s.get("model", ""), _now()))


def ai_suggestions(pid: int, stage: str) -> dict[int, dict]:
    df = _query("SELECT a.record_id, a.decision, a.reason, a.rationale, a.confidence, a.model "
                "FROM ai_suggestions a JOIN records r ON r.id=a.record_id "
                "WHERE r.project_id=? AND a.stage=?", (pid, stage))
    return {int(r.record_id): {"decision": r.decision, "reason": r.reason,
                               "rationale": r.rationale, "confidence": r.confidence,
                               "model": r.model} for r in df.itertuples(index=False)}


# ── Full-text PDFs ───────────────────────────────────────────────────────────────
def set_pdf(rid: int, path: str = "", status: str = "") -> None:
    """status: 'available' | 'not_retrieved' | ''"""
    update_record(rid, pdf_path=path, pdf_status=status)


# ── Data extraction ──────────────────────────────────────────────────────────────
def save_extraction(rid: int, model: str, values: dict | None, quotes: dict | None,
                    text: str, pdf_path: str, error: str | None = None) -> None:
    vals = json.dumps(values or {}, ensure_ascii=False)
    with _tx() as con:
        con.execute("INSERT INTO extractions (record_id, model, status, created_at, verified_at, "
                    "values_json, quotes_json, ai_json, text_extracted, pdf_path, error, review_seconds) "
                    "VALUES (?,?,?,?,NULL,?,?,?,?,?,?,NULL) ON CONFLICT(record_id) DO UPDATE SET "
                    "model=excluded.model, status=excluded.status, created_at=excluded.created_at, "
                    "verified_at=NULL, values_json=excluded.values_json, quotes_json=excluded.quotes_json, "
                    "ai_json=excluded.ai_json, text_extracted=excluded.text_extracted, "
                    "pdf_path=excluded.pdf_path, error=excluded.error, review_seconds=NULL",
                    (rid, model, "failed" if error else "draft", _now(), vals,
                     json.dumps(quotes or {}, ensure_ascii=False), vals, text or "",
                     pdf_path or "", error or ""))


def verify_extraction(rid: int, values: dict, quotes: dict, review_seconds=None) -> None:
    with _tx() as con:
        con.execute("UPDATE extractions SET status='verified', verified_at=?, values_json=?, "
                    "quotes_json=?, review_seconds=? WHERE record_id=?",
                    (_now(), json.dumps(values, ensure_ascii=False),
                     json.dumps(quotes, ensure_ascii=False), review_seconds, rid))


def delete_extraction(rid: int) -> None:
    with _tx() as con:
        con.execute("DELETE FROM extractions WHERE record_id=?", (rid,))


def get_extraction(rid: int) -> dict | None:
    with _ro() as con:
        row = con.execute("SELECT * FROM extractions WHERE record_id=?", (rid,)).fetchone()
    if not row:
        return None
    e = dict(row)
    for k in ("values_json", "quotes_json", "ai_json"):
        try:
            e[k[:-5]] = json.loads(e.get(k) or "{}")
        except json.JSONDecodeError:
            e[k[:-5]] = {}
    return e


def extractions_df(pid: int) -> pd.DataFrame:
    return _query("SELECT e.record_id, e.status, e.model, e.created_at, e.verified_at, e.error, "
                  "e.review_seconds FROM extractions e JOIN records r ON r.id=e.record_id "
                  "WHERE r.project_id=? ORDER BY e.record_id", (pid,))


def verified_extractions(pid: int) -> list[dict]:
    """Record metadata + verified values (+ quotes under 'quotes'), one dict per study."""
    df = _query("SELECT r.id AS record_id, r.title, r.authors, r.year, r.journal, r.doi, "
                "r.source_db, e.values_json, e.quotes_json, e.verified_at, e.model "
                "FROM extractions e JOIN records r ON r.id=e.record_id "
                "WHERE r.project_id=? AND e.status='verified' ORDER BY r.id", (pid,))
    out = []
    for r in df.itertuples(index=False):
        d = {"record_id": int(r.record_id), "title": r.title, "authors": r.authors,
             "year": r.year, "journal": r.journal, "doi": r.doi, "source_db": r.source_db,
             "verified_at": r.verified_at, "model": r.model}
        d["values"] = json.loads(r.values_json or "{}")
        d["quotes"] = json.loads(r.quotes_json or "{}")
        out.append(d)
    return out


# ── Counts ───────────────────────────────────────────────────────────────────────
def prisma_counts(pid: int, required: int = 1) -> dict:
    allrec = records_df(pid, include_duplicates=True)
    unique = allrec[allrec["is_duplicate"] == 0]
    by_source: dict[str, int] = {}
    for src in allrec["source_db"].tolist():
        for s in (str(src or "").split(";") or [""]):
            s = s.strip() or "(unspecified)"
            by_source[s] = by_source.get(s, 0) + 1
    ta = stage_status(pid, "ta", required)
    ta_counts = ta["status"].value_counts().to_dict() if len(ta) else {}
    sought_ids = set(ta.loc[ta["status"] == "include", "record_id"].tolist())
    sought = unique[unique["id"].isin(sought_ids)]
    not_retrieved = int((sought["pdf_status"] == "not_retrieved").sum()) if len(sought) else 0
    ft = stage_status(pid, "ft", required)
    if len(ft):
        ft = ft[~ft["record_id"].isin(
            sought.loc[sought["pdf_status"] == "not_retrieved", "id"].tolist())]
    ft_counts = ft["status"].value_counts().to_dict() if len(ft) else {}
    reasons: dict[str, int] = {}
    if len(ft):
        exc = ft[ft["status"] == "exclude"]
        for r in exc["reason"].tolist():
            r = r or "(no reason given)"
            reasons[r] = reasons.get(r, 0) + 1
    assessed = len(sought_ids) - not_retrieved
    return {
        "identified": int(len(allrec)),
        "by_source": dict(sorted(by_source.items())),
        "duplicates": int(len(allrec) - len(unique)),
        "screened": int(len(unique)),
        "ta_excluded": int(ta_counts.get("exclude", 0)),
        "ta_pending": int(len(unique) - ta_counts.get("exclude", 0) - ta_counts.get("include", 0)),
        "sought": int(len(sought_ids)),
        "not_retrieved": not_retrieved,
        "assessed": int(assessed),
        "ft_excluded": int(ft_counts.get("exclude", 0)),
        "ft_excluded_reasons": reasons,
        "ft_pending": int(assessed - ft_counts.get("exclude", 0) - ft_counts.get("include", 0)),
        "included": int(ft_counts.get("include", 0)),
    }


def summary_counts(pid: int, required: int = 1) -> dict:
    c = prisma_counts(pid, required)
    ex = extractions_df(pid)
    c["extracted_verified"] = int((ex["status"] == "verified").sum()) if len(ex) else 0
    c["extracted_draft"] = int((ex["status"] == "draft").sum()) if len(ex) else 0
    return c
