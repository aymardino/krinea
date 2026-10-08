"""End-to-end smoke test of the Streamlit app with Streamlit's AppTest
(no browser, no API key): create a project, import records, deduplicate,
screen, switch language, and visit every stage without exceptions."""
import os
import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import i18n
import review_db

APP = str(Path(__file__).resolve().parents[1] / "review_app.py")

RECS = [
    {"title": "Decentralized rural electrification in Kenya: speeding up universal energy access",
     "doi": "10.1016/j.esd.2019.07.009", "year": "2019", "authors": "Moner-Girona, M.",
     "abstract": "Mini-grids and solar home systems in Kenya.", "source_db": "Scopus"},
    {"title": "Decentralized rural electrification in Kenya: speeding up universal energy access",
     "doi": "", "year": "2019", "authors": "Moner-Girona M.", "source_db": "Web of Science"},
    {"title": "Hybrid PV-diesel mini-grid in Nigeria: a techno-economic study",
     "doi": "10.1109/a", "year": "2020", "authors": "Okoye, C.", "abstract": "HOMER study.",
     "source_db": "Scopus"},
]


def _no_errors(at):
    assert not at.exception, [e.value for e in at.exception]
    assert not at.error, [e.value for e in at.error]


@pytest.fixture
def at(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("REVIEWER", raising=False)
    app = AppTest.from_file(APP, default_timeout=60)
    app.run()
    _no_errors(app)
    return app


def test_i18n_keys_complete():
    """Every t('key') used by the app exists in both languages."""
    src = Path(APP).read_text(encoding="utf-8")
    # a bare t("key") call, not .get("key") / .format("key")
    used = set(re.findall(r"(?<![A-Za-z0-9_.])t\(\s*['\"]([a-z0-9_]+)['\"]", src))
    used = {k for k in used if not k.endswith("_")}          # 'dec_' + x prefixes
    used |= {"dec_include", "dec_maybe", "dec_exclude", "dec_conflict", "dec_pending",
             "view_todo", "view_my_include", "view_my_maybe", "view_my_exclude", "view_conflicts",
             "view_all", "ex_none", "ex_draft", "ex_verified", "ex_failed"}
    assert len(used) > 100
    for lang in i18n.LANGUAGES:
        missing = sorted(k for k in used if k not in i18n.STRINGS[lang])
        assert not missing, f"{lang}: {missing}"
    assert i18n.t("import_btn", lang="fr", n=2) == "Importer 2 fichier(s)"
    assert i18n.t("nope") == "nope"


def test_full_flow(at, tmp_path):
    # No project yet: the app stops after the title
    assert at.sidebar.text_input(key="new_project_name")
    at.sidebar.text_input(key="new_project_name").input("Demo review").run()
    at.sidebar.button(key="create_project").click().run()
    _no_errors(at)
    review_db.configure(tmp_path / "review.db")
    projects = review_db.list_projects()
    assert [p["name"] for p in projects] == ["Demo review"]
    pid = projects[0]["id"]

    # Setup page renders and saves criteria
    assert at.radio(key="stage_nav").value == "setup"
    at.radio(key="stage_nav").set_value("import").run()
    _no_errors(at)

    # Records go in through the library (file_uploader cannot be driven by AppTest)
    review_db.add_records(pid, RECS, "scopus.ris", "")
    at.radio(key="stage_nav").set_value("dedup").run()
    _no_errors(at)
    at.button(key="find_duplicates").click().run()
    _no_errors(at)
    assert len(review_db.records_df(pid)) == 2
    assert len(review_db.records_df(pid, include_duplicates=True)) == 3

    # Screening needs a reviewer name
    at.radio(key="stage_nav").set_value("ta").run()
    _no_errors(at)
    assert any("name" in w.value.lower() or "nom" in w.value.lower() for w in at.warning)
    at.sidebar.text_input(key="reviewer_name").input("alice").run()
    _no_errors(at)
    ids = review_db.records_df(pid)["id"].tolist()
    at.button(key=f"inc_ta_{ids[0]}").click().run()
    _no_errors(at)
    at.button(key=f"exc_ta_{ids[1]}").click().run()
    _no_errors(at)
    dec = review_db.decisions_df(pid, "ta")
    assert sorted(dec["decision"].tolist()) == ["exclude", "include"]
    assert at.radio(key="view_ta").value == "todo"

    # Full-text stage shows the included record; mark its PDF as not retrievable
    at.radio(key="stage_nav").set_value("ft").run()
    _no_errors(at)
    at.button(key=f"nr_{ids[0]}").click().run()
    _no_errors(at)
    assert review_db.get_record(ids[0])["pdf_status"] == "not_retrieved"
    at.button(key=f"undo_nr_{ids[0]}").click().run()
    _no_errors(at)
    at.button(key=f"inc_ft_{ids[0]}").click().run()
    _no_errors(at)

    # Extraction and PRISMA pages render
    at.radio(key="stage_nav").set_value("extract").run()
    _no_errors(at)
    at.radio(key="stage_nav").set_value("prisma").run()
    _no_errors(at)
    c = review_db.prisma_counts(pid)
    assert c == {**c, "identified": 3, "duplicates": 1, "screened": 2, "ta_excluded": 1,
                 "sought": 1, "included": 1}

    # Language switch re-renders everything in French
    at.sidebar.selectbox(key="lang_select").set_value("fr").run()
    _no_errors(at)
    assert at.session_state["lang"] == "fr"
    at.radio(key="stage_nav").set_value("setup").run()
    _no_errors(at)
    assert any("Question de recherche" in w.label for w in at.text_area)
