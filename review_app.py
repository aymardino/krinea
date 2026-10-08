"""
review_app.py — Systematic review workbench (Streamlit).

One app for the whole review, Rayyan-style:
    1 Setup        project, screening criteria, author-defined extraction form
    2 Import       RIS / BibTeX / PubMed / Web of Science / CSV / Excel search exports
    3 Duplicates   automatic merge (DOI, title) + manual check of near-matches
    4 Title & abstract screening, per reviewer, blind, with conflicts and AI hints
    5 Full-text screening, with PDF upload or open-access fetch by DOI
    6 Extraction   AI fills your form from each PDF, you verify side by side
    7 PRISMA 2020 counts, flow diagram and exports

    streamlit run review_app.py
    DATA_DIR=/var/data streamlit run review_app.py      # persistent storage (Docker)
"""
from __future__ import annotations

import datetime as dt
import html
import inspect
import io
import json
import os
import re
from pathlib import Path

import pandas as pd
import streamlit as st

import biblio
import dedup
import extraction_schema
import review_db
import screening
from i18n import LANGUAGES, t

DATA_DIR = Path(os.environ.get("DATA_DIR", str(Path(__file__).parent)))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "review.db"
PDF_DIR = DATA_DIR / "_review_pdfs"
PDF_DIR.mkdir(exist_ok=True)
review_db.configure(DB_PATH)

st.set_page_config(page_title="Systematic review workbench", layout="wide", page_icon="🔎",
                   initial_sidebar_state="expanded")

# Streamlit renamed use_container_width -> width="stretch" in 2025; support both.
_WIDE = ({"width": "stretch"} if "width" in inspect.signature(st.button).parameters
         else {"use_container_width": True})

PROVIDERS = ["claude", "gemini", "deepseek"]
SCREEN_MODELS = {"claude": "claude-haiku-5-5", "gemini": "gemini-2.5-flash",
                 "deepseek": "deepseek-v4-flash"}
EXTRACT_MODELS = {"claude": "claude-sonnet-5", "gemini": "gemini-2.5-flash",
                  "deepseek": "deepseek-v4-flash"}
KEY_ENV = {"claude": "ANTHROPIC_API_KEY", "gemini": "GEMINI_API_KEY", "deepseek": "DEEPSEEK_API_KEY"}

st.html("""
<style>
  :root { --brand: #0E7490; --brand-dark: #155E75; --brand-soft: rgba(14,116,144,0.08);
          --ink: #1F2937; --muted: #6B7280; --line: #E5E7EB; }
  h1, h2, h3, h4 { letter-spacing: -0.01em; }
  div[data-testid="stVerticalBlock"] { gap: 0.6rem; }
  div[data-testid="stAppDeployButton"], div[data-testid="stDecoration"], #MainMenu,
  footer { display: none; }
  div[data-testid="stMainBlockContainer"] { padding-top: 2.4rem; max-width: 1400px; }

  /* Header band */
  .hero { display:flex; align-items:baseline; justify-content:space-between; gap: 16px;
          padding: 14px 20px; margin: 0 0 6px 0; border-radius: 12px;
          background: linear-gradient(100deg, var(--brand) 0%, var(--brand-dark) 100%); color: #fff; }
  .hero .title { font-size: 1.45rem; font-weight: 650; letter-spacing: -0.01em; }
  .hero .project { font-size: 0.95rem; opacity: 0.9; }
  .hero .sub { font-size: 0.8rem; opacity: 0.75; }

  /* Stage navigation and view switches: pills instead of radio circles */
  div[data-testid="stRadio"] > div[role="radiogroup"] { gap: 6px; flex-wrap: wrap; }
  div[data-testid="stRadio"] > div[role="radiogroup"] > label {
      border: 1px solid var(--line); border-radius: 999px; padding: 5px 14px; margin: 0;
      background: #fff; color: var(--ink); font-size: 0.86rem; cursor: pointer; }
  div[data-testid="stRadio"] > div[role="radiogroup"] > label:hover { background: var(--brand-soft); }
  div[data-testid="stRadio"] > div[role="radiogroup"] > label:has(input:checked) {
      background: var(--brand); border-color: var(--brand); color: #fff; }
  div[data-testid="stRadio"] > div[role="radiogroup"] > label:has(input:checked) p { color: #fff; }
  div[data-testid="stRadio"] > div[role="radiogroup"] > label > div:first-child { display: none; }

  /* Cards and notes */
  div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 12px; }
  .meta { font-size: 0.85rem; color: var(--muted); margin-bottom: 0.4rem; }
  .meta a { color: var(--brand); }
  .abstract { font-size: 0.97rem; line-height: 1.6; padding: 14px 18px; border-radius: 10px;
              background: var(--brand-soft); border-left: 3px solid var(--brand); }
  .ai-box { font-size: 0.85rem; padding: 9px 12px; border-radius: 8px;
            background: rgba(79,70,229,0.08); color: #3730A3; margin-top: 8px; }
  .fieldnote { font-size:0.76rem; margin:-6px 0 9px 0; padding:5px 10px; border-radius:6px;
               background: rgba(180,83,9,0.12); color:#92400E; font-weight:500; }
  .note-quote { font-size:0.76rem; margin:-6px 0 9px 0; padding:5px 10px; color: var(--muted);
                font-style:italic; }
  .status-box { padding:9px 13px; border-radius:8px; margin-bottom:10px; font-size:0.85rem;
                background: rgba(180,83,9,0.12); color:#92400E; font-weight:500; }
  .status-ok { padding:9px 13px; border-radius:8px; margin-bottom:10px; font-size:0.85rem;
               background: rgba(5,150,105,0.12); color:#065F46; font-weight:500; }
  section[data-testid="stSidebar"] { background: var(--brand-soft); }
</style>
""")


# ── Small helpers ────────────────────────────────────────────────────────────────
def _esc(s) -> str:
    return html.escape(str(s or ""))


def _safe_name(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", str(s or "file"))[:120]


def _doi_link(doi: str) -> str:
    return f"<a href='https://doi.org/{_esc(doi)}' target='_blank'>{_esc(doi)}</a>" if doi else ""


def _meta_line(rec: dict) -> str:
    parts = [_esc(rec.get(k)) for k in ("authors", "year", "journal") if rec.get(k)]
    if rec.get("doi"):
        parts.append(_doi_link(rec["doi"]))
    if rec.get("source_db"):
        parts.append(_esc(rec["source_db"]))
    return " · ".join(parts)


def _render_pdf(pdf_path: str, key: str) -> None:
    p = Path(pdf_path)
    if not p.exists():
        return
    st.download_button(t("open_pdf"), p.read_bytes(), file_name=p.name,
                       mime="application/pdf", key=f"dl_{key}", **_WIDE)
    try:
        import fitz
        doc = fitz.open(str(p))
        n_pages = len(doc)
        top = min(n_pages, 40)
        show_n = st.slider(t("show_pages"), 1, top, 1, key=f"pg_{key}") if top > 1 else 1
        for i in range(min(show_n, n_pages)):
            pix = doc[i].get_pixmap(matrix=fitz.Matrix(2, 2))
            st.image(pix.tobytes("png"), caption=f"{i + 1}/{n_pages}")
        doc.close()
    except Exception as e:                                     # noqa: BLE001
        st.warning(t("pdf_error", err=e))


def _pdf_text(pdf_path: str) -> str:
    try:
        import extractor
        return extractor.extract_text(pdf_path)
    except Exception:                                         # noqa: BLE001
        return ""


# ── Sidebar ──────────────────────────────────────────────────────────────────────
with st.sidebar:
    lang_codes = list(LANGUAGES)
    default_lang = os.environ.get("APP_LANG", "en")
    cur_lang = st.session_state.get("lang", default_lang if default_lang in LANGUAGES else "en")
    lang = st.selectbox(t("language", lang=cur_lang), lang_codes,
                        index=lang_codes.index(cur_lang), format_func=lambda k: LANGUAGES[k],
                        key="lang_select")
    st.session_state.lang = lang

    st.markdown(f"### {t('project')}")
    projects = review_db.list_projects()
    pid = None
    if projects:
        ids = [p["id"] for p in projects]
        names = {p["id"]: p["name"] for p in projects}
        cur = st.session_state.get("project_id")
        if cur not in ids:
            cur = ids[0]
        pid = st.selectbox(t("project"), ids, index=ids.index(cur),
                           format_func=lambda i: names[i], label_visibility="collapsed",
                           key=f"project_select_{cur}_{len(ids)}")
        if pid != cur:
            st.session_state.project_id = pid
            st.rerun()
        st.session_state.project_id = pid
    else:
        st.info(t("no_project"))
    with st.expander(t("new_project"), expanded=not projects):
        new_name = st.text_input(t("project_name"), key="new_project_name")
        if st.button(t("create_project"), key="create_project", **_WIDE) and new_name.strip():
            try:
                st.session_state.project_id = review_db.create_project(new_name.strip())
                st.rerun()
            except Exception:                                 # noqa: BLE001 (UNIQUE name)
                st.error(t("project_exists"))

    st.divider()
    st.markdown(f"### {t('reviewer')}")
    reviewer = st.text_input(t("your_name"), value=st.session_state.get("reviewer", os.environ.get("REVIEWER", "")),
                             key="reviewer_name", help=t("your_name_help")).strip()
    st.session_state.reviewer = reviewer
    blind = st.checkbox(t("blind_mode"), value=True, key="blind_mode")

    st.divider()
    st.markdown(f"### {t('ai_assistant')}")
    provider = st.selectbox(t("provider"), PROVIDERS, key="ai_provider")
    api_key = st.text_input(t("api_key", provider=provider.capitalize()), type="password",
                            value=os.environ.get(KEY_ENV[provider], ""), key=f"api_key_{provider}")
    screen_model = st.text_input(t("model"), value=SCREEN_MODELS[provider],
                                 key=f"screen_model_{provider}", help=t("model_help"))
    unpaywall_email = st.text_input(t("unpaywall_email"),
                                    value=os.environ.get("UNPAYWALL_EMAIL", ""), key="unpaywall_email")

    st.divider()
    st.markdown(f"##### {t('data')}")
    if DB_PATH.exists():
        st.download_button(t("download_db"), DB_PATH.read_bytes(), file_name="review.db",
                           mime="application/octet-stream", help=t("download_db_help"), **_WIDE)


def _hero(project_name: str = ""):
    st.html(f"<div class='hero'><div><div class='title'>🔎 {t('app_title')}</div>"
            f"<div class='sub'>{t('app_subtitle')}</div></div>"
            f"<div class='project'>{_esc(project_name)}</div></div>")


if pid is None:
    _hero()
    st.info(t("no_project"))
    st.stop()

project = review_db.get_project(pid)
criteria = project["criteria"]
required = int(criteria["required_reviewers"])
counts = review_db.summary_counts(pid, required)
_hero(project["name"])

STAGES = ["setup", "import", "dedup", "ta", "ft", "extract", "prisma"]
STAGE_LABELS = {
    "setup": t("stage_setup"),
    "import": t("stage_import", n=counts["identified"]),
    "dedup": t("stage_dedup", n=counts["duplicates"]),
    "ta": t("stage_ta", n=counts["ta_pending"]),
    "ft": t("stage_ft", n=counts["ft_pending"]),
    "extract": t("stage_extract", n=counts["included"]),
    "prisma": t("stage_prisma"),
}
if st.session_state.get("stage") not in STAGES:
    st.session_state.stage = "setup"
stage = st.radio("stage", STAGES, index=STAGES.index(st.session_state.stage),
                 format_func=lambda k: STAGE_LABELS[k], horizontal=True,
                 label_visibility="collapsed", key="stage_nav")
st.session_state.stage = stage
st.divider()


# ── 1 · Setup ────────────────────────────────────────────────────────────────────
def page_setup():
    st.markdown(f"#### {t('setup_project')}")
    c = criteria
    with st.form("project_form"):
        name = st.text_input(t("project_name"), value=project["name"])
        desc = st.text_area(t("project_description"), value=project["description"] or "", height=70)
        question = st.text_area(t("research_question"), value=c["question"], height=70)
        col1, col2 = st.columns(2)
        inclusion = col1.text_area(t("inclusion_criteria"), value=c["inclusion"], height=160,
                                   help=t("one_per_line"))
        exclusion = col2.text_area(t("exclusion_criteria"), value=c["exclusion"], height=160,
                                   help=t("one_per_line"))
        reasons = st.text_area(t("exclusion_reasons"), value="\n".join(c["exclusion_reasons"]),
                               height=160, help=t("one_per_line"))
        col3, col4 = st.columns(2)
        hi_inc = col3.text_input(t("highlight_include"), value=", ".join(c["highlight_include"]))
        hi_exc = col4.text_input(t("highlight_exclude"), value=", ".join(c["highlight_exclude"]))
        req = st.number_input(t("required_reviewers"), 1, 5, int(c["required_reviewers"]),
                              help=t("required_reviewers_help"))
        if st.form_submit_button(t("save"), type="primary"):
            review_db.update_project(pid, name=name or project["name"], description=desc, criteria={
                "question": question, "inclusion": inclusion, "exclusion": exclusion,
                "exclusion_reasons": [r.strip() for r in reasons.splitlines() if r.strip()],
                "highlight_include": screening.parse_keywords(hi_inc),
                "highlight_exclude": screening.parse_keywords(hi_exc),
                "required_reviewers": int(req)})
            st.success(t("saved"))
            st.rerun()

    st.divider()
    st.markdown(f"#### {t('extraction_fields')}")
    st.caption(t("extraction_fields_help"))
    fields = project["schema"]
    df = pd.DataFrame([{"name": f["name"], "label": f["label"], "kind": f["kind"],
                        "options": " | ".join(f["options"]), "hint": f["hint"],
                        "required": bool(f["required"])} for f in fields],
                      columns=["name", "label", "kind", "options", "hint", "required"])
    edited = st.data_editor(
        df, num_rows="dynamic", hide_index=True, key=f"schema_editor_{pid}",
        column_config={
            "name": st.column_config.TextColumn(t("col_name")),
            "label": st.column_config.TextColumn(t("col_label")),
            "kind": st.column_config.SelectboxColumn(t("col_kind"), options=extraction_schema.FIELD_KINDS,
                                                     required=True),
            "options": st.column_config.TextColumn(t("col_options")),
            "hint": st.column_config.TextColumn(t("col_hint"), width="large"),
            "required": st.column_config.CheckboxColumn(t("col_required")),
        })
    c1, c2, c3 = st.columns(3)
    if c1.button(t("save_schema"), type="primary", key="save_schema", **_WIDE):
        rows = edited.fillna("").to_dict("records")
        new_fields = [extraction_schema.normalise_field(r) for r in rows
                      if str(r.get("name") or "").strip() or str(r.get("label") or "").strip()]
        errors = extraction_schema.validate_schema(new_fields)
        if errors:
            st.error("\n\n".join(errors))
        else:
            review_db.update_project(pid, schema=new_fields)
            st.success(t("schema_saved", n=len(new_fields)))
            st.rerun()
    if c2.button(t("load_energy_template"), key="load_energy", **_WIDE):
        review_db.update_project(pid, schema=extraction_schema.energy_template())
        st.rerun()
    if c3.button(t("reset_default_schema"), key="reset_schema", **_WIDE):
        review_db.update_project(pid, schema=extraction_schema.DEFAULT_SCHEMA)
        st.rerun()
    d1, d2, d3 = st.columns(3)
    d1.download_button(t("schema_export_json"), extraction_schema.to_json(fields),
                       file_name="extraction_fields.json", mime="application/json", **_WIDE)
    d2.download_button(t("schema_export_csv"), extraction_schema.to_csv(fields),
                       file_name="extraction_fields.csv", mime="text/csv", **_WIDE)
    up = d3.file_uploader(t("schema_import"), type=["json", "csv"], key=f"schema_up_{pid}",
                          label_visibility="collapsed")
    if up is not None:
        text = up.getvalue().decode("utf-8-sig", errors="replace")
        try:
            new_fields = (extraction_schema.from_json(text) if up.name.lower().endswith(".json")
                          else extraction_schema.from_csv(text))
            errors = extraction_schema.validate_schema(new_fields)
            if errors:
                st.error("\n\n".join(errors))
            elif new_fields != fields:
                review_db.update_project(pid, schema=new_fields)
                st.success(t("schema_saved", n=len(new_fields)))
                st.rerun()
        except Exception as e:                                # noqa: BLE001
            st.error(f"{type(e).__name__}: {e}")

    st.divider()
    with st.expander(t("danger_zone")):
        ok = st.checkbox(t("confirm_delete_project"), key="confirm_delete_project")
        if st.button(t("delete_project"), disabled=not ok, key="delete_project"):
            review_db.delete_project(pid)
            st.session_state.pop("project_id", None)
            st.rerun()


# ── 2 · Import ───────────────────────────────────────────────────────────────────
def page_import():
    files = st.file_uploader(t("upload_exports"),
                             type=["ris", "bib", "txt", "nbib", "csv", "tsv", "xlsx", "xls"],
                             accept_multiple_files=True, key=f"import_files_{pid}")
    source_db = st.text_input(t("source_label"), placeholder="Scopus, Web of Science, PubMed…",
                              key="import_source")
    if files and st.button(t("import_btn", n=len(files)), type="primary", key="import_btn"):
        log = []
        for f in files:
            try:
                recs = biblio.parse_file(f.name, f.getvalue())
                n, skipped = review_db.add_records(pid, recs, f.name, source_db.strip())
                fmt = recs[0]["_format"] if recs else "?"
                log.append(("ok", t("import_ok", file=f.name, n=n, fmt=fmt, skipped=skipped)))
            except Exception as e:                            # noqa: BLE001
                log.append(("err", t("import_failed", file=f.name, err=f"{type(e).__name__}: {e}")))
        st.session_state.import_log = log
        st.rerun()
    for level, msg in st.session_state.pop("import_log", []):
        (st.success if level == "ok" else st.error)(msg)

    batches = review_db.import_batches(pid)
    if not len(batches):
        st.info(t("no_records"))
        return
    st.markdown(f"##### {t('imported_files')}")
    for row in batches.itertuples(index=False):
        c1, c2, c3, c4, c5 = st.columns([4, 2, 1, 2, 1])
        c1.write(row.source_file)
        c2.write(row.source_db or "")
        c3.write(int(row.records))
        c4.write(str(row.imported_at or "")[:16])
        if c5.button(t("delete_batch"), key=f"del_batch_{_safe_name(row.source_file)}"):
            review_db.delete_batch(pid, row.source_file)
            st.rerun()
    st.markdown(f"##### {t('preview')}")
    recs = review_db.records_df(pid, include_duplicates=True)
    st.dataframe(recs[["id", "title", "authors", "year", "journal", "doi", "source_db"]].tail(200),
                 hide_index=True)


# ── 3 · Duplicates ───────────────────────────────────────────────────────────────
def page_dedup():
    all_recs = review_db.records_df(pid, include_duplicates=True)
    if not len(all_recs):
        st.info(t("no_records"))
        return
    st.caption(t("dedup_intro"))
    c1, c2 = st.columns(2)
    auto_t = c1.slider(t("auto_threshold"), 85, 100, 95, key="dedup_auto")
    rev_t = c2.slider(t("review_threshold"), 70, 95, 85, key="dedup_review")
    if st.button(t("find_duplicates"), type="primary", key="find_duplicates"):
        review_db.reset_duplicates(pid)
        recs = review_db.records_df(pid, include_duplicates=True)
        records = recs.to_dict("records")
        ids = recs["id"].tolist()
        pairs = dedup.find_duplicates(records, float(auto_t), float(rev_t))
        certain = [p for p in pairs if p.certain]
        pair_info = {(p.a, p.b): p for p in certain}
        groups = dedup.cluster(certain, len(records))
        removed = 0
        for g in groups:
            keeper = dedup.choose_keeper(records, g)
            for i in g:
                if i == keeper:
                    continue
                pr = pair_info.get((min(i, keeper), max(i, keeper)))
                review_db.mark_duplicates(ids[keeper], [ids[i]],
                                          pr.score if pr else 100.0,
                                          pr.reason if pr else "duplicate group")
                removed += 1
            review_db.mark_duplicates(ids[keeper], [], 100.0, "",
                                      dedup.merge_records(records, keeper, g))
        possible = [(ids[p.a], ids[p.b], p.score, p.reason) for p in pairs if not p.certain]
        review_db.upsert_candidates(pid, possible)
        st.session_state.dedup_msg = t("dedup_done", removed=removed, groups=len(groups),
                                       possible=len(possible))
        st.rerun()
    if "dedup_msg" in st.session_state:
        st.success(st.session_state.pop("dedup_msg"))

    unique = all_recs[all_recs["is_duplicate"] == 0]
    cands = review_db.candidates_df(pid)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(t("m_records"), len(all_recs))
    m2.metric(t("m_duplicates"), int(len(all_recs) - len(unique)))
    m3.metric(t("m_unique"), len(unique))
    m4.metric(t("m_to_check"), len(cands))

    if len(cands):
        st.markdown(f"##### {t('possible_duplicates')}")
        for row in cands.head(25).itertuples(index=False):
            with st.container(border=True):
                st.caption(f"{row.score:.0f}% · {row.reason}")
                ca, cb = st.columns(2)
                for col, side in ((ca, "a"), (cb, "b")):
                    rec = {k: getattr(row, f"{k}_{side}") for k in
                           ("id", "title", "authors", "year", "journal", "doi", "source")}
                    rec["source_db"] = rec.pop("source")
                    col.markdown(f"**#{rec['id']} · {_esc(rec['title'])}**")
                    col.markdown(f"<div class='meta'>{_meta_line(rec)}</div>", unsafe_allow_html=True)
                b1, b2 = st.columns(2)
                if b1.button(t("same_study"), key=f"merge_{row.id}", type="primary", **_WIDE):
                    ra, rb = review_db.get_record(int(row.id_a)), review_db.get_record(int(row.id_b))
                    both = [ra, rb]
                    keeper = dedup.choose_keeper(both, [0, 1])
                    merged = dedup.merge_records(both, keeper, [0, 1])
                    review_db.mark_duplicates(both[keeper]["id"], [both[1 - keeper]["id"]],
                                              float(row.score), row.reason, merged)
                    review_db.set_candidate_status(int(row.id), "merged")
                    st.rerun()
                if b2.button(t("different_study"), key=f"ignore_{row.id}", **_WIDE):
                    review_db.set_candidate_status(int(row.id), "ignored")
                    st.rerun()

    dups = review_db.duplicates_df(pid)
    if len(dups):
        st.markdown(f"##### {t('removed_duplicates')}")
        disp = dups[["id", "title", "year", "doi", "source_db", "score", "reason", "kept_id", "kept_title"]].copy()
        disp.insert(0, t("restore"), False)
        ed = st.data_editor(disp, hide_index=True, disabled=list(disp.columns[1:]),
                            key=f"dups_editor_{pid}_{len(dups)}")
        to_restore = ed.loc[ed[t("restore")] == True, "id"].tolist()   # noqa: E712
        if to_restore and st.button(t("restore_selected", n=len(to_restore)), key="restore_dups"):
            for rid in to_restore:
                review_db.unmark_duplicate(int(rid))
            st.rerun()
    elif not len(cands):
        st.caption(t("no_dedup_yet"))


# ── 4 & 5 · Screening ───────────────────────────────────────────────────────────
def _record_card(rec: dict, ai: dict | None, status_row, mine, others: dict, stage_key: str):
    st.markdown(f"### {_esc(rec.get('title')) or t('untitled')}")
    st.markdown(f"<div class='meta'>{_meta_line(rec)}</div>", unsafe_allow_html=True)
    if rec.get("abstract"):
        st.markdown(f"<div class='abstract'>{screening.highlight(rec['abstract'], criteria['highlight_include'], criteria['highlight_exclude'])}</div>",
                    unsafe_allow_html=True)
    else:
        st.info(t("no_abstract"))
    if rec.get("keywords"):
        st.caption(f"{t('keywords')}: {rec['keywords']}")
    if ai:
        reason = f" · {_esc(ai['reason'])}" if ai.get("reason") else ""
        st.markdown(f"<div class='ai-box'>🤖 {t('ai_suggests')}: <b>{t('dec_' + ai['decision'])}</b> "
                    f"({float(ai.get('confidence') or 0):.0%}){reason} — {_esc(ai.get('rationale'))}</div>",
                    unsafe_allow_html=True)
    bits = []
    if mine is not None:
        extra = f" ({_esc(mine.reason)})" if mine.reason else ""
        bits.append(f"{t('your_decision')}: **{t('dec_' + mine.decision)}**{extra}")
    if others and not st.session_state.get("blind_mode", True):
        bits.append(f"{t('other_decisions')}: " + ", ".join(f"{_esc(k)} → {t('dec_' + v)}" for k, v in others.items()))
    if status_row is not None and status_row["status"] == "conflict":
        bits.append(f"{t('status')}: **{t('dec_conflict')}** ({_esc(status_row['summary'])})")
    if bits:
        st.caption(" · ".join(bits))


def _fulltext_material(rec: dict, email: str):
    rid = int(rec["id"])
    with st.expander(t("full_text_pdf"), expanded=True):
        pdf_path = rec.get("pdf_path") or ""
        if pdf_path and Path(pdf_path).exists():
            tab_pdf, tab_txt = st.tabs([t("pdf_pages"), t("extracted_text")])
            with tab_pdf:
                _render_pdf(pdf_path, f"ft_{rid}")
            with tab_txt:
                st.text_area(t("extracted_text"), _pdf_text(pdf_path), height=400,
                             label_visibility="collapsed", key=f"fttxt_{rid}")
            return
        if rec.get("pdf_status") == "not_retrieved":
            st.warning(t("not_retrieved_flag"))
            if st.button(t("undo"), key=f"undo_nr_{rid}"):
                review_db.set_pdf(rid, "", "")
                st.rerun()
        up = st.file_uploader(t("upload_pdf"), type=["pdf"], key=f"pdfup_{rid}")
        if up is not None:
            dest = PDF_DIR / f"{rid}_{_safe_name(up.name)}"
            dest.write_bytes(up.getbuffer())
            review_db.set_pdf(rid, str(dest), "available")
            st.rerun()
        c1, c2 = st.columns(2)
        if c1.button(t("fetch_unpaywall"), key=f"fetch_{rid}", **_WIDE):
            if not rec.get("doi"):
                st.error(t("need_doi"))
            elif not email:
                st.error(t("need_email"))
            else:
                try:
                    import extractor
                    path = extractor.fetch_pdf_by_doi(rec["doi"], email, str(PDF_DIR))
                    review_db.set_pdf(rid, path, "available")
                    st.rerun()
                except Exception as e:                        # noqa: BLE001
                    st.warning(f"{type(e).__name__}: {e}")
        if c2.button(t("mark_not_retrieved"), key=f"nr_{rid}", **_WIDE):
            review_db.set_pdf(rid, "", "not_retrieved")
            st.rerun()


def _ai_bulk(stage_key: str, queue_ids: list[int], pool: pd.DataFrame, ai: dict):
    with st.expander(t("ai_prescreen")):
        st.caption(t("ai_prescreen_help"))
        missing = [i for i in queue_ids if i not in ai]
        limit = st.number_input(t("ai_limit"), 1, 2000, 50, key=f"ai_limit_{stage_key}")
        todo = missing[:int(limit)]
        if st.button(t("ai_run", n=len(todo)), disabled=not todo, key=f"ai_run_{stage_key}"):
            if not api_key:
                st.error(t("ai_need_key"))
                return
            prog = st.progress(0.0)
            ok = err = 0
            by_id = pool.set_index("id")
            for k, rid in enumerate(todo, 1):
                rec = by_id.loc[rid].to_dict()
                rec["id"] = rid
                full_text = _pdf_text(rec["pdf_path"]) if stage_key == "ft" and rec.get("pdf_path") else ""
                try:
                    s = screening.ai_screen(rec, criteria, api_key, provider=provider,
                                            model=screen_model, stage=stage_key, full_text=full_text)
                    review_db.save_ai_suggestion(rid, stage_key, s)
                    ok += 1
                except Exception as e:                        # noqa: BLE001
                    err += 1
                    st.warning(f"#{rid}: {type(e).__name__}: {e}")
                prog.progress(k / len(todo))
            st.success(t("ai_done", ok=ok, err=err))
            st.rerun()


def page_screen(stage_key: str):
    if not reviewer:
        st.warning(t("need_reviewer"))
        return
    pool = review_db.stage_pool(pid, stage_key, required)
    if not len(pool):
        st.info(t("no_ta_pool") if stage_key == "ta" else t("no_ft_pool"))
        return
    status = review_db.stage_status(pid, stage_key, required).set_index("record_id")
    dec = review_db.decisions_df(pid, stage_key)
    mine = {int(r.record_id): r for r in dec[dec["reviewer"] == reviewer].itertuples(index=False)}
    others_all: dict[int, dict] = {}
    for r in dec[(dec["reviewer"] != reviewer) & (dec["reviewer"] != "consensus")].itertuples(index=False):
        others_all.setdefault(int(r.record_id), {})[r.reviewer] = r.decision
    ai = review_db.ai_suggestions(pid, stage_key)
    pool_ids = [int(i) for i in pool["id"].tolist()]

    views = {
        "todo": [i for i in pool_ids if i not in mine],
        "my_include": [i for i in pool_ids if i in mine and mine[i].decision == "include"],
        "my_maybe": [i for i in pool_ids if i in mine and mine[i].decision == "maybe"],
        "my_exclude": [i for i in pool_ids if i in mine and mine[i].decision == "exclude"],
        "conflicts": [i for i in pool_ids if status.loc[i, "status"] == "conflict"],
        "all": pool_ids,
    }
    c1, c2 = st.columns([3, 2])
    view = c1.radio(t("view"), list(views), horizontal=True, key=f"view_{stage_key}",
                    format_func=lambda k: f"{t('view_' + k)} ({len(views[k])})")
    search = c2.text_input(t("search"), key=f"search_{stage_key}").strip().lower()
    queue = views[view]
    if search:
        hay = pool.set_index("id")
        queue = [i for i in queue if search in
                 f"{hay.loc[i, 'title']} {hay.loc[i, 'authors']} {hay.loc[i, 'abstract']}".lower()]
    done = len([i for i in pool_ids if i in mine])
    st.progress(done / max(1, len(pool_ids)), text=t("progress", done=done, total=len(pool_ids)))
    _ai_bulk(stage_key, views["todo"], pool, ai)
    if not queue:
        st.success(t("queue_empty"))
        return

    idx_key = f"idx_{stage_key}_{view}"
    idx = min(max(int(st.session_state.get(idx_key, 0)), 0), len(queue) - 1)
    n1, n2, n3 = st.columns([1, 1, 6])
    if n1.button(t("previous"), disabled=idx == 0, key=f"prev_{stage_key}", **_WIDE):
        st.session_state[idx_key] = idx - 1
        st.rerun()
    if n2.button(t("next"), disabled=idx >= len(queue) - 1, key=f"next_{stage_key}", **_WIDE):
        st.session_state[idx_key] = idx + 1
        st.rerun()
    n3.markdown(f"<div style='padding-top:6px'><b>{idx + 1} / {len(queue)}</b></div>", unsafe_allow_html=True)

    rid = queue[idx]
    rec = pool[pool["id"] == rid].iloc[0].to_dict()
    rec["id"] = rid
    status_row = status.loc[rid]
    card = st.container(border=True)
    with card:
        _record_card(rec, ai.get(rid), status_row, mine.get(rid), others_all.get(rid, {}), stage_key)
    if stage_key == "ft":
        _fulltext_material(rec, unpaywall_email)

    def _advance():
        st.session_state[idx_key] = idx if view == "todo" else idx + 1
        st.rerun()

    reasons = [""] + list(criteria["exclusion_reasons"])
    cur_reason = mine[rid].reason if rid in mine and mine[rid].reason in reasons else \
        (ai[rid]["reason"] if rid in ai and ai[rid].get("reason") in reasons else "")
    r1, r2, r3 = st.columns([2, 2, 2])
    reason = r1.selectbox(t("exclusion_reason"), reasons, index=reasons.index(cur_reason),
                          key=f"reason_{stage_key}_{rid}")
    labels = r2.text_input(t("labels"), value=mine[rid].labels if rid in mine else "",
                           key=f"labels_{stage_key}_{rid}")
    note = r3.text_input(t("note"), value=mine[rid].note if rid in mine else "",
                         key=f"note_{stage_key}_{rid}")
    b1, b2, b3, b4 = st.columns([2, 2, 2, 2])
    if b1.button(t("include"), type="primary", key=f"inc_{stage_key}_{rid}", **_WIDE):
        review_db.set_decision(rid, stage_key, reviewer, "include", "", labels, note)
        _advance()
    if b2.button(t("maybe"), key=f"may_{stage_key}_{rid}", **_WIDE):
        review_db.set_decision(rid, stage_key, reviewer, "maybe", reason, labels, note)
        _advance()
    if b3.button(t("exclude"), key=f"exc_{stage_key}_{rid}", **_WIDE):
        review_db.set_decision(rid, stage_key, reviewer, "exclude", reason, labels, note)
        _advance()
    if rid in ai and rid not in mine:
        if b4.button(t("accept_ai"), key=f"acc_{stage_key}_{rid}", **_WIDE):
            s = ai[rid]
            review_db.set_decision(rid, stage_key, reviewer, s["decision"],
                                   s.get("reason", "") if s["decision"] == "exclude" else "", labels, note)
            _advance()
    elif rid in mine:
        if b4.button(t("clear_decision"), key=f"clr_{stage_key}_{rid}", **_WIDE):
            review_db.delete_decision(rid, stage_key, reviewer)
            st.rerun()
    if status_row["status"] == "conflict":
        st.markdown(f"**{t('resolve_conflict')}**")
        k1, k2, k3 = st.columns(3)
        for col, d in ((k1, "include"), (k2, "maybe"), (k3, "exclude")):
            if col.button(f"{t(d)} ({t('resolved_by')})", key=f"res_{d}_{stage_key}_{rid}", **_WIDE):
                review_db.set_decision(rid, stage_key, "consensus", d,
                                       reason if d == "exclude" else "", labels, note)
                st.rerun()


# ── 6 · Extraction ───────────────────────────────────────────────────────────────
def _field_widget(f: dict, value: str, key: str):
    kind, label = f["kind"], f["label"]
    if kind == "enum":
        opts = [""] + f["options"]
        return st.selectbox(label, opts, index=opts.index(value) if value in opts else 0, key=key)
    if kind == "yesno":
        opts = ["", "yes", "no"]
        return st.selectbox(label, opts, index=opts.index(value) if value in opts else 0, key=key)
    if kind == "multi":
        chosen = [x.strip() for x in re.split(r"[,;]", value) if x.strip() in f["options"]]
        return ", ".join(st.multiselect(label, f["options"], default=chosen, key=key))
    if kind in ("sentences", "list"):
        return st.text_area(label, value=value, height=80, key=key)
    return st.text_input(label, value=value, key=key)


def _verification(rid: int, fields: list[dict], ex: dict):
    rec = review_db.get_record(rid)
    values, quotes = ex["values"], ex["quotes"]
    timer_key = f"_timer_{rid}"
    if timer_key not in st.session_state:
        st.session_state[timer_key] = dt.datetime.now()
    elapsed = (dt.datetime.now() - st.session_state[timer_key]).total_seconds()
    st.markdown(f"### {_esc(rec['title'])}")
    m, s = divmod(int(elapsed), 60)
    st.markdown(f"<div class='meta'>{_meta_line(rec)} · {t('elapsed', m=m, s=s)}</div>", unsafe_allow_html=True)
    if ex["status"] == "failed":
        st.error(ex.get("error") or "failed")
    left, right = st.columns([10, 9])
    with right:
        st.markdown(f"##### {t('source_material')}")
        tab1, tab2 = st.tabs([t("pdf_pages"), t("extracted_text")])
        with tab1:
            if ex.get("pdf_path") and Path(ex["pdf_path"]).exists():
                _render_pdf(ex["pdf_path"], f"ex_{rid}")
            else:
                st.info(t("no_pdf_for"))
        with tab2:
            st.text_area(t("extracted_text"), ex.get("text_extracted") or "", height=620,
                         label_visibility="collapsed", key=f"extxt_{rid}")
    with left:
        top = st.container()
        st.markdown(f"##### {t('fields')}")
        flags = extraction_schema.check_values(fields, values, quotes)
        n_err, n_warn = extraction_schema.summarise(flags)
        if flags:
            st.markdown(f"<div class='status-box'>{t('flagged', errors=n_err, warnings=n_warn)}</div>",
                        unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='status-ok'>{t('nothing_flagged')}</div>", unsafe_allow_html=True)
        only_flagged = st.checkbox(t("only_flagged"), value=False, key=f"onlyflag_{rid}")
        edited = {}
        for f in fields:
            name = f["name"]
            if only_flagged and name not in flags:
                edited[name] = values.get(name, "")
                continue
            edited[name] = _field_widget(f, str(values.get(name, "") or ""), key=f"f_{rid}_{name}")
            if name in flags:
                st.markdown(f"<div class='fieldnote'>{_esc(flags[name][1])}</div>", unsafe_allow_html=True)
            q = quotes.get(name, "")
            if q:
                st.markdown(f"<div class='note-quote'>↳ {_esc(q[:160])}{'…' if len(q) > 160 else ''}</div>",
                            unsafe_allow_html=True)
        with top:
            a1, a2, a3 = st.columns(3)
            save = a1.button(t("save_verified"), type="primary", key=f"save_{rid}", **_WIDE)
            redo = a2.button(t("re_extract"), key=f"redo_{rid}", **_WIDE)
            drop = a3.button(t("delete_draft"), key=f"drop_{rid}", **_WIDE)
        if st.button(t("save_verified"), type="primary", key=f"save2_{rid}"):
            save = True
        if save:
            review_db.verify_extraction(rid, edited, quotes, elapsed)
            st.session_state.pop(timer_key, None)
            st.session_state.pop("verify_rid", None)
            st.rerun()
        if redo:
            _run_extractions([rid], fields)
            st.rerun()
        if drop:
            review_db.delete_extraction(rid)
            st.session_state.pop(timer_key, None)
            st.rerun()


def _run_extractions(rids: list[int], fields: list[dict]):
    model = st.session_state.get(f"extract_model_{provider}", EXTRACT_MODELS[provider])
    if not api_key:
        st.error(t("ai_need_key"))
        return 0, 0
    prog = st.progress(0.0)
    ok = err = 0
    for k, rid in enumerate(rids, 1):
        rec = review_db.get_record(rid)
        try:
            values, quotes, text = extraction_schema.extract_pdf(
                fields, rec["pdf_path"], api_key, provider, model, context=criteria["question"])
            review_db.save_extraction(rid, model, values, quotes, text, rec["pdf_path"])
            ok += 1
        except Exception as e:                                # noqa: BLE001
            review_db.save_extraction(rid, model, None, None, "", rec.get("pdf_path") or "",
                                      error=f"{type(e).__name__}: {e}")
            err += 1
        prog.progress(k / len(rids))
    st.session_state.extract_msg = t("extraction_done", ok=ok, err=err)
    return ok, err


def page_extract():
    st.caption(t("extract_intro"))
    pool = review_db.stage_pool(pid, "extract", required)
    if not len(pool):
        st.info(t("no_extract_pool"))
        return
    fields = project["schema"]
    ex = review_db.extractions_df(pid).set_index("record_id")
    st.text_input(t("extraction_model"), value=EXTRACT_MODELS[provider],
                  key=f"extract_model_{provider}", help=t("model_help"))
    rows = []
    for r in pool.itertuples(index=False):
        has_pdf = bool(r.pdf_path and Path(r.pdf_path).exists())
        status = ex.loc[r.id, "status"] if r.id in ex.index else "none"
        rows.append({"id": int(r.id), "title": r.title, "year": r.year,
                     t("col_pdf"): "✓" if has_pdf else "", t("col_status"): t("ex_" + status)})
    st.dataframe(pd.DataFrame(rows), hide_index=True)
    todo = [row["id"] for row in rows if row[t("col_pdf")] and row[t("col_status")] == t("ex_none")]
    if st.button(t("run_extraction", n=len(todo)), type="primary", disabled=not todo, key="run_extraction"):
        _run_extractions(todo, fields)
        st.rerun()
    if "extract_msg" in st.session_state:
        st.success(st.session_state.pop("extract_msg"))

    candidates = [row["id"] for row in rows if row[t("col_status")] != t("ex_none")]
    if not candidates:
        return
    st.divider()
    labels = {row["id"]: f"#{row['id']} · {row[t('col_status')]} · {row['title'][:80]}" for row in rows}
    cur = st.session_state.get("verify_rid")
    if cur not in candidates:
        cur = candidates[0]
    rid = st.selectbox(t("verify_pick"), candidates, index=candidates.index(cur),
                       format_func=lambda i: labels[i], key=f"verify_pick_{cur}_{len(candidates)}")
    if rid != cur:
        st.session_state.verify_rid = rid
        st.rerun()
    st.session_state.verify_rid = rid
    e = review_db.get_extraction(rid)
    if e:
        _verification(rid, fields, e)


# ── 7 · PRISMA & export ──────────────────────────────────────────────────────────
def _prisma_dot(c: dict) -> str:
    src = "\\n".join(f"{_esc(k)}: {v}" for k, v in c["by_source"].items())
    reasons = "\\n".join(f"{_esc(k)}: {v}" for k, v in c["ft_excluded_reasons"].items())
    return f"""digraph PRISMA {{
  rankdir=TB; node [shape=box, style="rounded,filled", fillcolor="#F0F2EE", fontname="Helvetica", fontsize=11];
  id  [label="{t('p_identified')} (n = {c['identified']})\\n{src}"];
  dup [label="{t('p_duplicates')} (n = {c['duplicates']})"];
  scr [label="{t('p_screened')} (n = {c['screened']})"];
  ex1 [label="{t('p_ta_excluded')} (n = {c['ta_excluded']})"];
  sou [label="{t('p_sought')} (n = {c['sought']})"];
  nr  [label="{t('p_not_retrieved')} (n = {c['not_retrieved']})"];
  ass [label="{t('p_assessed')} (n = {c['assessed']})"];
  ex2 [label="{t('p_ft_excluded')} (n = {c['ft_excluded']})\\n{reasons}"];
  inc [label="{t('p_included')} (n = {c['included']})", fillcolor="#CDE8D2"];
  id -> scr; id -> dup [style=dashed]; scr -> sou; scr -> ex1 [style=dashed];
  sou -> ass; sou -> nr [style=dashed]; ass -> inc; ass -> ex2 [style=dashed];
  {{rank=same; id; dup}} {{rank=same; scr; ex1}} {{rank=same; sou; nr}} {{rank=same; ass; ex2}}
}}"""


def page_prisma():
    c = review_db.prisma_counts(pid, required)
    st.markdown(f"#### {t('prisma_title')}")
    m = st.columns(5)
    m[0].metric(t("p_identified"), c["identified"])
    m[1].metric(t("p_duplicates"), c["duplicates"])
    m[2].metric(t("p_screened"), c["screened"])
    m[3].metric(t("p_assessed"), c["assessed"])
    m[4].metric(t("p_included"), c["included"])
    st.caption(t("p_pending", ta=c["ta_pending"], ft=c["ft_pending"]))
    g1, g2 = st.columns([3, 2])
    with g1:
        st.graphviz_chart(_prisma_dot(c))
    with g2:
        st.markdown(f"**{t('p_by_source')}**")
        st.table(pd.DataFrame(list(c["by_source"].items()), columns=["source", "n"]))
        if c["ft_excluded_reasons"]:
            st.markdown(f"**{t('reasons_table')}**")
            st.table(pd.DataFrame(list(c["ft_excluded_reasons"].items()), columns=["reason", "n"]))

    st.divider()
    st.markdown(f"#### {t('exports')}")
    included = review_db.stage_pool(pid, "extract", required).to_dict("records")
    ta = review_db.stage_status(pid, "ta", required).set_index("record_id")["status"]
    ft = review_db.stage_status(pid, "ft", required).set_index("record_id")["status"]
    all_recs = review_db.records_df(pid, include_duplicates=True)
    all_recs["ta_status"] = all_recs["id"].map(ta).fillna("")
    all_recs["ft_status"] = all_recs["id"].map(ft).fillna("")
    e1, e2, e3, e4 = st.columns(4)
    e1.download_button(t("exp_included_ris"), biblio.to_ris(included), file_name="included.ris",
                       mime="application/x-research-info-systems", **_WIDE)
    e2.download_button(t("exp_included_csv"), biblio.to_csv(included), file_name="included.csv",
                       mime="text/csv", **_WIDE)
    e3.download_button(t("exp_all_csv"), all_recs.to_csv(index=False), file_name="all_records.csv",
                       mime="text/csv", **_WIDE)
    e4.download_button(t("exp_decisions_csv"), review_db.decisions_df(pid).to_csv(index=False),
                       file_name="decisions.csv", mime="text/csv", **_WIDE)
    verified = review_db.verified_extractions(pid)
    fields = project["schema"]
    meta_cols = ["record_id", "title", "authors", "year", "journal", "doi"]
    wide = pd.DataFrame([{**{k: v[k] for k in meta_cols},
                          **{f["name"]: v["values"].get(f["name"], "") for f in fields}} for v in verified],
                        columns=meta_cols + [f["name"] for f in fields])
    quotes = pd.DataFrame([{**{k: v[k] for k in meta_cols},
                            **{f["name"]: v["quotes"].get(f["name"], "") for f in fields}} for v in verified],
                          columns=meta_cols + [f["name"] for f in fields])
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xl:
        wide.to_excel(xl, sheet_name="values", index=False)
        quotes.to_excel(xl, sheet_name="quotes", index=False)
        pd.DataFrame(fields).to_excel(xl, sheet_name="fields", index=False)
    f1, f2, f3, f4 = st.columns(4)
    f1.download_button(t("exp_extractions_xlsx"), buf.getvalue(), file_name="extractions.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", **_WIDE)
    f2.download_button(t("exp_extractions_csv"), wide.to_csv(index=False), file_name="extractions.csv",
                       mime="text/csv", **_WIDE)
    prisma_rows = [(k, v) for k, v in c.items() if not isinstance(v, dict)]
    prisma_rows += [(f"source:{k}", v) for k, v in c["by_source"].items()]
    prisma_rows += [(f"ft_excluded:{k}", v) for k, v in c["ft_excluded_reasons"].items()]
    f3.download_button(t("exp_prisma_csv"), pd.DataFrame(prisma_rows, columns=["item", "n"]).to_csv(index=False),
                       file_name="prisma_counts.csv", mime="text/csv", **_WIDE)
    f4.download_button(t("exp_dot"), _prisma_dot(c), file_name="prisma.dot", mime="text/plain", **_WIDE)


PAGES = {"setup": page_setup, "import": page_import, "dedup": page_dedup,
         "ta": lambda: page_screen("ta"), "ft": lambda: page_screen("ft"),
         "extract": page_extract, "prisma": page_prisma}
PAGES[stage]()
