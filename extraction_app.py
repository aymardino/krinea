"""
extraction_app.py — Rayyan-like AI extraction & verification tool (local).

Workflow:
- Upload one PDF or a batch (queue). The AI extracts in the background, results
  become "drafts" you review one by one.
- For each draft: side-by-side form (with source quotes + extracted text) ->
  correct -> save as verified.
- Export verified studies to a relational Excel (4 sheets matching your DB).
"""

import os
import json
import sqlite3
import datetime as dt
import base64
from pathlib import Path

import streamlit as st
import pandas as pd

import extractor

DB = Path(__file__).parent / "extractions.db"
PDF_CACHE = Path(__file__).parent / "_pdf_cache"
PDF_CACHE.mkdir(exist_ok=True)
st.set_page_config(page_title="AISESA — AI Extraction", layout="wide", page_icon="📄")


# ── Storage ──────────────────────────────────────────────────────────────────────
def init_db():
    con = sqlite3.connect(DB)
    con.execute("""CREATE TABLE IF NOT EXISTS extractions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_file TEXT, model TEXT,
        status TEXT DEFAULT 'verified',          -- 'draft' or 'verified'
        created_at TEXT, verified_at TEXT,
        data_json TEXT, quotes_json TEXT,
        text_extracted TEXT, pdf_path TEXT,
        error TEXT)""")
    # Add columns if upgrading from the older schema
    cols = [r[1] for r in con.execute("PRAGMA table_info(extractions)").fetchall()]
    for col, typ in [("status", "TEXT DEFAULT 'verified'"), ("created_at", "TEXT"),
                     ("text_extracted", "TEXT"), ("pdf_path", "TEXT"), ("error", "TEXT")]:
        if col not in cols:
            con.execute(f"ALTER TABLE extractions ADD COLUMN {col} {typ}")
    con.commit()
    con.close()


def save_draft(source_file, model, result, text, pdf_path, error=None):
    """Save an unverified extraction (or a failed one) as a draft."""
    values = {f: result[f]["value"] for f in extractor.EXPORT_FIELDS if f in result} if result else {}
    quotes = {f: result[f]["quote"] for f in extractor.EXPORT_FIELDS if f in result} if result else {}
    con = sqlite3.connect(DB)
    con.execute(
        "INSERT INTO extractions (source_file, model, status, created_at, data_json, quotes_json, "
        "text_extracted, pdf_path, error) VALUES (?,?,?,?,?,?,?,?,?)",
        (source_file, model, "draft" if not error else "failed",
         dt.datetime.now().isoformat(timespec="seconds"),
         json.dumps(values, ensure_ascii=False),
         json.dumps(quotes, ensure_ascii=False),
         text, str(pdf_path) if pdf_path else "", error))
    con.commit()
    con.close()


def update_verified(row_id, values, quotes):
    con = sqlite3.connect(DB)
    con.execute("UPDATE extractions SET status='verified', verified_at=?, data_json=?, "
                "quotes_json=? WHERE id=?",
                (dt.datetime.now().isoformat(timespec="seconds"),
                 json.dumps(values, ensure_ascii=False),
                 json.dumps(quotes, ensure_ascii=False), row_id))
    con.commit()
    con.close()


def load_drafts() -> pd.DataFrame:
    con = sqlite3.connect(DB)
    df = pd.read_sql("SELECT id, source_file, status, created_at, error FROM extractions "
                     "WHERE status IN ('draft','failed') ORDER BY id", con)
    con.close()
    return df


def load_one(row_id):
    con = sqlite3.connect(DB)
    row = con.execute("SELECT source_file, data_json, quotes_json, text_extracted, pdf_path "
                      "FROM extractions WHERE id=?", (row_id,)).fetchone()
    con.close()
    if not row:
        return None
    values = json.loads(row[1] or "{}")
    quotes = json.loads(row[2] or "{}")
    # Rehydrate the {value,quote} structure the verification UI expects
    result = {f: {"value": values.get(f, ""), "quote": quotes.get(f, "")}
              for f in extractor.SCHEMA_FIELDS + ["power_pool"]}
    return {"source_file": row[0], "result": result, "text": row[3] or "", "pdf_path": row[4] or ""}


def load_verified() -> pd.DataFrame:
    con = sqlite3.connect(DB)
    rows = con.execute("SELECT id, source_file, verified_at, data_json FROM extractions "
                       "WHERE status='verified' ORDER BY id").fetchall()
    con.close()
    records = []
    for _id, src, ts, dj in rows:
        rec = {"_id": _id, "source_file": src, "verified_at": ts}
        rec.update(json.loads(dj or "{}"))
        records.append(rec)
    return pd.DataFrame(records)


def counts():
    con = sqlite3.connect(DB)
    c = {r[0]: r[1] for r in con.execute("SELECT COALESCE(status,'verified'), COUNT(*) "
                                          "FROM extractions GROUP BY status").fetchall()}
    con.close()
    return c


def delete_extraction(row_id):
    con = sqlite3.connect(DB)
    pdf = con.execute("SELECT pdf_path FROM extractions WHERE id=?", (row_id,)).fetchone()
    if pdf and pdf[0] and Path(pdf[0]).exists():
        try: Path(pdf[0]).unlink()
        except OSError: pass
    con.execute("DELETE FROM extractions WHERE id=?", (row_id,))
    con.commit(); con.close()


def reset_all():
    con = sqlite3.connect(DB)
    con.execute("DELETE FROM extractions")
    con.execute("DELETE FROM sqlite_sequence WHERE name='extractions'")
    con.commit(); con.close()
    for p in PDF_CACHE.glob("*.pdf"):
        try: p.unlink()
        except OSError: pass


def _move_to_next_draft_after(current_id):
    """After saving or deleting the current draft, set current_draft_id to the
    next remaining draft (or previous if we were at the end). The selectbox
    in the Review tab uses a dynamic key that includes current_draft_id, so
    changing this value alone is enough — Streamlit will recreate the widget."""
    df = load_drafts()
    remaining_ids = [int(x) for x in df["id"].tolist() if int(x) != current_id]
    if not remaining_ids:
        st.session_state.pop("current_draft_id", None)
        return
    all_ids_before = [int(x) for x in df["id"].tolist()]
    try:
        was_idx = all_ids_before.index(current_id)
    except ValueError:
        was_idx = 0
    next_idx = min(was_idx, len(remaining_ids) - 1)
    st.session_state.current_draft_id = remaining_ids[next_idx]


def build_relational_excel(df: pd.DataFrame, out_path, start_id=1):
    """Split the flat extractions into your relational sheets.
    Renumbers studies sequentially from `start_id` to fill any gaps created
    by deleted drafts. The internal SQLite IDs are unchanged."""
    import re as _re
    def split(v): return [x.strip() for x in _re.split(r"[,;]", str(v)) if x.strip()]

    # Build a mapping: internal_id -> exported_id (sequential from start_id)
    df_sorted = df.sort_values("_id").reset_index(drop=True)
    id_map = {int(row["_id"]): start_id + i for i, row in df_sorted.iterrows()}

    studies, tools, ctries, pools = [], [], [], []
    for _, r in df_sorted.iterrows():
        old_sid = int(r["_id"])
        new_sid = id_map[old_sid]
        # Studies sheet: no source_file, renumbered study_id
        srow = {"study_id": new_sid}
        for f in extractor.EXPORT_FIELDS:
            if f not in ("tools_used", "tool_categories"):
                srow[f] = r.get(f, "")
        studies.append(srow)
        # Link tables use the new IDs too
        for i, t in enumerate(split(r.get("tools_used", ""))):
            cats = split(r.get("tool_categories", ""))
            tools.append({"study_id": new_sid, "tool_name": t,
                          "tool_category": cats[i] if i < len(cats) else ""})
        for iso in split(r.get("countries", "")):
            ctries.append({"study_id": new_sid, "iso_code": iso})
        for p in split(r.get("power_pool", "")):
            pools.append({"study_id": new_sid, "pool_code": p})

    with pd.ExcelWriter(out_path, engine="openpyxl") as xl:
        pd.DataFrame(studies).to_excel(xl, sheet_name="studies", index=False)
        pd.DataFrame(tools).to_excel(xl, sheet_name="study_tools", index=False)
        pd.DataFrame(ctries).to_excel(xl, sheet_name="study_countries", index=False)
        pd.DataFrame(pools).to_excel(xl, sheet_name="study_pools", index=False)


def run_extraction(pdf_path, api_key, model, upgrade_synth, provider="gemini"):
    """Run extraction and save as draft. Returns (success, error_msg)."""
    source = Path(pdf_path).name
    cached_pdf = PDF_CACHE / f"{dt.datetime.now().strftime('%Y%m%d%H%M%S%f')}_{source}"
    try:
        # Copy PDF to cache so we can show it later in the review screen
        cached_pdf.write_bytes(Path(pdf_path).read_bytes())
        text = extractor.extract_text(pdf_path)
        if len(text) < 500:
            raise ValueError("Extracted text too short — PDF may be scanned (needs OCR).")
        result = extractor.extract_pdf(pdf_path, api_key, model,
                                        upgrade_synthesis=upgrade_synth,
                                        provider=provider)
        save_draft(source, model, result, text, cached_pdf)
        return True, None
    except Exception as e:
        save_draft(source, model, None, "", cached_pdf, error=f"{type(e).__name__}: {e}")
        return False, f"{type(e).__name__}: {e}"

# ── Duplicate detection against the master Excel ──────────────────────────────
MASTER_XLSX = Path(__file__).parent / "Models_Africa_v2.xlsm"


@st.cache_data(ttl=300)
def load_master_index(_mtime: float):
    """Load a lightweight index (title + DOI) from the master Excel's
    'studies' sheet. Cached for 5 minutes and keyed on the file's mtime, so
    edits to the Excel are picked up without restarting the app."""
    if not MASTER_XLSX.exists():
        return pd.DataFrame(columns=["study_id", "full_title", "link_doi"])
    try:
        df = pd.read_excel(MASTER_XLSX, sheet_name="studies.csv", dtype=str)
    except Exception:
        return pd.DataFrame(columns=["study_id", "full_title", "link_doi"])
    cols = {c.lower().strip(): c for c in df.columns}
    title_col = cols.get("full_title") or cols.get("title")
    doi_col = cols.get("link_doi") or cols.get("doi")
    id_col = cols.get("study_id")
    out = pd.DataFrame({
        "study_id": df[id_col] if id_col else range(1, len(df) + 1),
        "full_title": df[title_col].fillna("") if title_col else "",
        "link_doi": df[doi_col].fillna("") if doi_col else "",
    })
    return out[out["full_title"].str.strip() != ""]


def check_duplicate(new_title, new_doi, master_df, threshold=85):
    """Return (match_type, matched_row, score) or (None, None, 0) if no match.
    match_type is 'doi' (certain) or 'title' (fuzzy, score is similarity %)."""
    if not len(master_df):
        return None, None, 0

    new_doi = (new_doi or "").strip().lower()
    if new_doi:
        hit = master_df[master_df["link_doi"].str.strip().str.lower() == new_doi]
        if len(hit):
            return "doi", hit.iloc[0], 100

    new_title = (new_title or "").strip()
    if not new_title:
        return None, None, 0
    from rapidfuzz import process, fuzz
    result = process.extractOne(
        new_title, master_df["full_title"].tolist(), scorer=fuzz.token_sort_ratio)
    if result and result[1] >= threshold:
        matched_row = master_df.iloc[result[2]]
        return "title", matched_row, round(result[1])
    return None, None, 0

init_db()
C = counts()

# ── Sidebar ──────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Configuration")
    provider = st.selectbox("Provider", ["claude", "gemini", "deepseek"],
                            help="Claude = recommended for reliable extraction. " "Gemini = alternative. DeepSeek = backup")
    # Show the right key field per provider
    if provider == "gemini":
        api_key = st.text_input("Gemini API key", type="password",
                                value=os.environ.get("GEMINI_API_KEY", ""))
        model = st.selectbox("Model", ["gemini-2.5-flash", "gemini-2.5-pro"],
                             help="Flash = cheap. Pro = better on interpretive fields.")
        flash_model = "gemini-2.5-flash"
    elif provider == "claude":
        api_key = st.text_input("Anthropic API key", type="password",
                                value=os.environ.get("ANTHROPIC_API_KEY", ""),
                                help="Get one from https://console.anthropic.com")
        model = st.selectbox("Model", ["claude-sonnet-5", "claude-opus-5"],
                            help="Sonnet 5 = best cost/quality ratio for extraction. "
                                "Opus 5 = higher quality on interpretive fields, ~5x more expensive.")
        flash_model = "claude-sonnet-5"
    else:
        api_key = st.text_input("DeepSeek API key", type="password",
                                value=os.environ.get("DEEPSEEK_API_KEY", ""),
                                help="Get one from https://platform.deepseek.com")
        model = st.selectbox("Model", ["deepseek-v4-flash", "deepseek-v4-pro"],
                             help="Flash = cheap (~$0.003/article). Pro = better synthesis.")
        flash_model = "deepseek-v4-flash"
    upgrade_synth = st.checkbox("Upgrade synthesis with Pro",
                                value=(model == flash_model),
                                help="Re-runs study_objective and key_result on Pro for "
                                     "better synthesis. ~$0.01/study.")
    unpaywall_email = st.text_input("Email for Unpaywall (DOI lookup)",
                                    value=os.environ.get("UNPAYWALL_EMAIL", ""),
                                    help="Required by Unpaywall to fetch open-access PDFs by DOI. "
                                         "Any real email works.")

    st.divider()
    st.markdown("### Today's session")
    # Count studies verified today
    _today = dt.date.today().isoformat()
    con_t = sqlite3.connect(DB)
    verified_today = con_t.execute(
        "SELECT COUNT(*) FROM extractions WHERE status='verified' "
        "AND verified_at LIKE ?", (f"{_today}%",)
    ).fetchone()[0]
    con_t.close()

    daily_goal = st.number_input("Today's goal", min_value=1, max_value=200,
                                  value=15, step=5,
                                  help="Set a realistic daily target. Small blocks "
                                       "of 15-20 studies work better than 100+ marathons.")
    progress = min(verified_today / daily_goal, 1.0)
    st.progress(progress, text=f"{verified_today} / {daily_goal} today")
    if verified_today >= daily_goal:
        st.success("🎉 Daily goal reached — take a real break!")
    elif verified_today > 0 and verified_today % 5 == 0:
        st.info(f"☕ {verified_today} done — good time for a short break")

    st.divider()
    st.markdown("### Progress")
    cc1, cc2, cc3 = st.columns(3)
    cc1.metric("Drafts", C.get("draft", 0))
    cc2.metric("Verified", C.get("verified", 0))
    cc3.metric("Failed", C.get("failed", 0))
    st.divider()
    export_start = st.number_input(
        "Start numbering exported studies at",
        min_value=1, value=1, step=1,
        help="Set this to the next available ID in your master Excel inventory. "
            "For example, if your inventory ends at study_id 65, set this to 66. "
            "The internal IDs in the extraction tool are not affected."
    )
    if st.button("⬇ Export to Excel (relational)", use_container_width=True):
        df = load_verified()
        if len(df):
            out = Path(__file__).parent / "extracted_studies.xlsx"
            build_relational_excel(df, out, start_id=int(export_start))
            with open(out, "rb") as f:
                st.download_button("Download extracted_studies.xlsx", f,
                                file_name="extracted_studies.xlsx",
                                use_container_width=True)
        else:
            st.info("No verified studies yet.")
    st.divider()
    st.markdown("##### Danger zone")
    confirm = st.checkbox("Confirm wipe everything")
    if st.button("⚠ Reset (delete ALL)", disabled=not confirm, use_container_width=True):
        reset_all(); st.success("All cleared."); st.rerun()


# ── Main: tabs for batch upload / review / saved ─────────────────────────────────
st.title("AI extraction & verification")
# ── Tab 2: Review drafts ─────────────────────────────────────────────────────────
def render_verification(draft_id):
    """Render the verify-and-save UI for one draft."""
    data = load_one(draft_id)
    if not data:
        st.error("Draft not found."); return
    src = data["source_file"]
    result = data["result"]

    st.markdown(f"### Verifying: `{src}` (draft #{draft_id})")
    left, right = st.columns([3, 2])

    with right:
        st.markdown("##### Source material")
        view_tab1, view_tab2 = st.tabs(["📋 Extracted text", "📄 PDF pages"])
        with view_tab1:
            st.caption(f"~{len(data['text']):,} chars — exactly what the AI read. Ctrl/Cmd+F to search.")
            st.text_area("Extracted text", data["text"], height=620,
                         label_visibility="collapsed", key=f"txt_{draft_id}")
        with view_tab2:
            pdf_path = data["pdf_path"]
            if pdf_path and Path(pdf_path).exists():
                # Download button — opens natively in Chrome with full search/zoom/highlight
                with open(pdf_path, "rb") as f:
                    st.download_button("⬇ Open PDF in browser (full search, zoom, highlight)",
                                       f.read(), file_name=Path(pdf_path).name,
                                       mime="application/pdf", key=f"dl_{draft_id}",
                                       use_container_width=True)
                st.caption("Click above to open the PDF in a new tab — works in all browsers.")
                # Render pages as images so they're always visible inline
                try:
                    import fitz
                    doc = fitz.open(pdf_path)
                    n_pages = len(doc)
                    show_n = st.slider("Show pages", 1, min(n_pages, 10),
                                       min(3, n_pages), key=f"pg_{draft_id}",
                                       help=f"PDF has {n_pages} pages total; showing first N as images.")
                    for i in range(show_n):
                        page = doc[i]
                        # ~120 DPI: enough to read, light enough to be fast
                        pix = page.get_pixmap(matrix=fitz.Matrix(1.7, 1.7))
                        img_bytes = pix.tobytes("png")
                        st.image(img_bytes, caption=f"Page {i+1}/{n_pages}",
                                 use_container_width=True)
                    doc.close()
                except Exception as e:
                    st.warning(f"Couldn't render PDF pages: {e}. Use the download button above.")
            else:
                st.info("PDF not available (cache cleared). Use the Extracted text tab.")

    with left:
        st.markdown("##### Fields (AI values + source quotes)")
        field_spec = {n: (k, h) for n, k, h in extractor.FIELDS}

        # Render extraction_level FIRST so we know the scope for the rest.
        # Changing this dropdown re-runs the page and updates which fields show.
        el_item = result.get("extraction_level", {"value": "", "quote": ""})
        el_opts = ["", "full", "light"]
        el_idx = el_opts.index(el_item.get("value", "")) if el_item.get("value", "") in el_opts else 0
        extraction_level_value = st.selectbox(
            "extraction_level", el_opts, index=el_idx, key=f"f_{draft_id}_extraction_level",
            help="Choose first — this determines which fields you need to fill below.")
        el_quote = el_item.get("quote", "")
        if el_quote:
            st.markdown(f"<div style='font-size:0.78rem;color:#666;margin-top:-8px;"
                        f"margin-bottom:10px;'>“{el_quote}”</div>", unsafe_allow_html=True)

        # ── Duplicate check against the master Excel ────────────────────────
        _title_val = result.get("full_title", {}).get("value", "")
        _doi_val = result.get("link_doi", {}).get("value", "")
        _master = load_master_index(MASTER_XLSX.stat().st_mtime if MASTER_XLSX.exists() else 0)
        _match_type, _match_row, _score = check_duplicate(_title_val, _doi_val, _master)
        if _match_type == "doi":
            st.error(f"🚨 **Certain duplicate** — same DOI as study_id "
                     f"{_match_row['study_id']} in your master Excel: "
                     f"\"{_match_row['full_title'][:90]}\"")
        elif _match_type == "title":
            st.warning(f"⚠ **Possible duplicate ({_score}% title match)** — study_id "
                       f"{_match_row['study_id']} in your master Excel: "
                       f"\"{_match_row['full_title'][:90]}\". Check before saving.")

        # Scope: which fields to render for this level
        scope = extractor.fields_in_scope(extraction_level_value) if extraction_level_value \
                else list(extractor.EXPORT_FIELDS)
        if extraction_level_value in ("light"):
            st.caption(f"Showing {len(scope)} fields (level **{extraction_level_value}** "
                       f"hides irrelevant fields from {len(extractor.EXPORT_FIELDS)} total).")

        edited = {"extraction_level": extraction_level_value}
        for field in extractor.SCHEMA_FIELDS:
            if field == "extraction_level":
                continue  # already rendered above
            # Skip fields not in scope for this extraction level
            if field not in scope:
                # Still preserve the AI value (saved as-is) but don't show it
                edited[field] = result.get(field, {}).get("value", "")
                continue
            item = result.get(field, {"value": "", "quote": ""})
            ai_val = item.get("value", "")
            kind, hint = field_spec.get(field, ("text", ""))
            if kind == "enum":
                opts = [""] + hint
                idx = opts.index(ai_val) if ai_val in opts else 0
                edited[field] = st.selectbox(field, opts, index=idx, key=f"f_{draft_id}_{field}")
            elif kind == "yesno":
                opts = ["", "yes", "no"]
                idx = opts.index(ai_val) if ai_val in opts else 0
                edited[field] = st.selectbox(field, opts, index=idx, key=f"f_{draft_id}_{field}")
            elif kind == "ynp":
                opts = ["", "yes", "no", "partial"]
                idx = opts.index(ai_val) if ai_val in opts else 0
                edited[field] = st.selectbox(field, opts, index=idx, key=f"f_{draft_id}_{field}")
            else:
                edited[field] = st.text_input(field, value=ai_val, key=f"f_{draft_id}_{field}")
            q = item.get("quote", "")
            if q:
                st.markdown(f"<div style='font-size:0.78rem;color:#666;margin-top:-8px;"
                            f"margin-bottom:6px;'>“{q}”</div>", unsafe_allow_html=True)
        edited["power_pool"] = extractor.compute_pools(edited.get("countries", ""))
        st.info(f"**Power pool** (computed): {edited['power_pool'] or '—'}")

        bcol1, bcol2 = st.columns(2)
        if bcol1.button("✅ Save as verified", type="primary", key=f"save_{draft_id}"):
            # Save quotes only for fields actually verified (kept in scope)
            quotes = {f: result.get(f, {}).get("quote", "")
                      for f in extractor.SCHEMA_FIELDS if f in scope}
            # For fields hors-périmètre, clear the value to avoid storing unreviewed AI guesses
            for f in extractor.SCHEMA_FIELDS:
                if f not in scope and f != "extraction_level":
                    edited[f] = ""
            update_verified(draft_id, edited, quotes)
            # Move to the NEXT draft so the user keeps flowing (Rayyan-style)
            _move_to_next_draft_after(draft_id)
            st.success("Saved."); st.rerun()
        if bcol2.button("🗑 Delete this draft", key=f"del_{draft_id}"):
            _move_to_next_draft_after(draft_id)
            delete_extraction(draft_id); st.rerun()




# Navigation that survives reruns (st.tabs always resets to first tab after st.rerun)
if "main_tab" not in st.session_state:
    st.session_state.main_tab = "upload"
tab_labels = {
    "upload": f"📤 Upload & extract",
    "review": f"📝 Review drafts ({C.get('draft',0) + C.get('failed',0)})",
    "saved":  f"✅ Verified ({C.get('verified',0)})",
}
choice = st.radio("Section", list(tab_labels.values()), horizontal=True,
                  index=list(tab_labels.keys()).index(st.session_state.main_tab),
                  label_visibility="collapsed")
st.session_state.main_tab = [k for k, v in tab_labels.items() if v == choice][0]
st.divider()


# ── Tab 1: Upload (single or batch) ──────────────────────────────────────────────
if st.session_state.main_tab == "upload":
    upload_mode = st.radio("Source", ["📤 Upload PDF files", "🔗 Fetch by DOI (open access only)"],
                            horizontal=True, label_visibility="collapsed")

    if upload_mode.startswith("📤"):
        st.caption("Upload one PDF or a batch. Each PDF is extracted and saved as a **draft** "
                   "you can review in the next tab. Failures are recorded too, so you can retry.")
        uploaded = st.file_uploader("Choose one or more PDFs", type=["pdf"],
                                    accept_multiple_files=True)
        if uploaded and st.button(f"🔍 Extract {len(uploaded)} PDF{'s' if len(uploaded)>1 else ''} with AI",
                                  type="primary"):
            if not api_key:
                st.error("Please provide your API key in the sidebar.")
            else:
                progress = st.progress(0.0)
                log = st.empty()
                ok = err = 0
                for i, up in enumerate(uploaded, 1):
                    tmp = PDF_CACHE / f"_tmp_{up.name}"
                    tmp.write_bytes(up.getbuffer())
                    log.text(f"[{i}/{len(uploaded)}] {up.name}…")
                    success, errmsg = run_extraction(str(tmp), api_key, model, upgrade_synth, provider=provider)
                    tmp.unlink(missing_ok=True)
                    if success: ok += 1
                    else: err += 1
                    progress.progress(i / len(uploaded))
                log.text("")
                st.success(f"Done. {ok} draft(s) created, {err} failure(s). "
                           f"Open the 'Review drafts' tab to verify and save.")
                st.rerun()
    else:
        st.caption("Paste DOIs (one per line). Each is looked up on **Unpaywall**; if an open-access "
                   "PDF exists, it's downloaded and extracted. Articles behind paywalls won't work "
                   "(expect ~50–65% hit rate on energy journals).")
        doi_text = st.text_area("DOIs (one per line)",
                                placeholder="10.1088/1748-9326/11/8/084010\n10.1016/j.energy.2020.117471",
                                height=120)
        if doi_text and st.button(f"🔗 Fetch & extract", type="primary"):
            if not api_key:
                st.error("Please provide your API key in the sidebar.")
            elif not unpaywall_email:
                st.error("Please provide an email for Unpaywall in the sidebar.")
            else:
                dois = [d.strip() for d in doi_text.splitlines() if d.strip()]
                progress = st.progress(0.0)
                log = st.empty()
                ok = paywalled = err = 0
                for i, doi in enumerate(dois, 1):
                    log.text(f"[{i}/{len(dois)}] {doi}…")
                    try:
                        pdf_path = extractor.fetch_pdf_by_doi(doi, unpaywall_email, str(PDF_CACHE))
                        success, errmsg = run_extraction(pdf_path, api_key, model, upgrade_synth, provider=provider)
                        if success: ok += 1
                        else: err += 1
                    except FileNotFoundError:
                        paywalled += 1
                    except Exception as e:
                        save_draft(doi, model, None, "", None, error=f"{type(e).__name__}: {e}")
                        err += 1
                    progress.progress(i / len(dois))
                log.text("")
                msg = f"Done. {ok} draft(s) created."
                if paywalled: msg += f" {paywalled} DOI(s) paywalled (upload PDF manually)."
                if err: msg += f" {err} other failure(s)."
                st.success(msg)
                st.rerun()


elif st.session_state.main_tab == "review":
    drafts = load_drafts()
    if not len(drafts):
        st.info("No drafts to review. Upload PDFs in the first tab.")
    else:
        draft_options = []
        for _, d in drafts.iterrows():
            tag = "❌ " if d["status"] == "failed" else ""
            draft_options.append((int(d["id"]), f"{tag}#{d['id']} — {d['source_file']}"))
        draft_ids = [did for did, _ in draft_options]
        labels = [lbl for _, lbl in draft_options]

        # ── State: current_draft_id is the only source of truth ───────────────
        # The selectbox uses a DYNAMIC key tied to current_draft_id, so each
        # time current_draft_id changes, the widget is freshly recreated and
        # honours its `index=` parameter. This sidesteps Streamlit's rule that
        # "you can't modify session_state[key] after a widget with that key
        # is instantiated".
        stored_id = st.session_state.get("current_draft_id")
        if stored_id not in draft_ids:
            stored_id = draft_ids[0]
            st.session_state.current_draft_id = stored_id
        current_idx = draft_ids.index(stored_id)

        # Header row: prev / next / counter / picker
        c1, c2, c3, c4 = st.columns([1, 1, 1, 4])
        with c1:
            if st.button("◀ Prev", disabled=current_idx == 0,
                          use_container_width=True, key="btn_prev"):
                st.session_state.current_draft_id = draft_ids[current_idx - 1]
                st.rerun()
        with c2:
            if st.button("Next ▶", disabled=current_idx >= len(draft_ids) - 1,
                          use_container_width=True, key="btn_next"):
                st.session_state.current_draft_id = draft_ids[current_idx + 1]
                st.rerun()
        with c3:
            st.markdown(f"<div style='padding-top:6px;'><strong>"
                        f"{current_idx + 1} / {len(draft_ids)}"
                        f"</strong></div>", unsafe_allow_html=True)
        with c4:
            # DYNAMIC key: includes current_draft_id, so when the user navigates
            # via Prev/Next/Save, the selectbox is recreated with its `index=`
            # initial value (no stale state to override us).
            picker_key = f"picker_for_{stored_id}_{len(draft_ids)}"
            picked = st.selectbox("Jump to draft", range(len(labels)),
                                   format_func=lambda i: labels[i],
                                   index=current_idx,
                                   label_visibility="collapsed",
                                   key=picker_key)
            # If user changed the picker manually, sync current_draft_id
            if draft_ids[picked] != st.session_state.current_draft_id:
                st.session_state.current_draft_id = draft_ids[picked]
                st.rerun()

        st.divider()

        # Render the currently-selected draft
        current_id = st.session_state.current_draft_id
        current_row = drafts[drafts["id"] == current_id].iloc[0]
        if current_row["status"] == "failed":
            st.error(f"This draft failed during extraction:\n\n{current_row['error']}")
            if st.button("🗑 Delete this failure"):
                _move_to_next_draft_after(current_id)
                delete_extraction(current_id)
                st.rerun()
        else:
            render_verification(current_id)


# ── Tab 3: Verified studies ──────────────────────────────────────────────────────
elif st.session_state.main_tab == "saved":
    df = load_verified()
    if not len(df):
        st.info("No verified studies yet.")
    else:
        st.caption(f"{len(df)} verified studies. Use the checkboxes to delete some, "
                   "or export from the sidebar.")
        show_cols = [c for c in ["_id", "authors", "full_title", "source_file", "model_name", "year", "scale",
                                 "countries", "power_pool", "extraction_level"] if c in df.columns]
        disp = df[show_cols].copy()
        disp.insert(0, "Delete?", False)
        ed = st.data_editor(disp, use_container_width=True, hide_index=True,
                            disabled=show_cols, key="verified_editor")
        to_del = ed.loc[ed["Delete?"] == True, "_id"].tolist()
        if to_del and st.button(f"🗑 Delete {len(to_del)} selected"):
            for sid in to_del: delete_extraction(int(sid))
            st.rerun()