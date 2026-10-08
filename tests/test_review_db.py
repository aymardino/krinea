import pytest

import biblio
import dedup
import review_db


@pytest.fixture
def db(tmp_path):
    review_db.configure(tmp_path / "review.db")
    return review_db


RECS = [
    {"title": "Decentralized rural electrification in Kenya: speeding up universal energy access",
     "doi": "10.1016/j.esd.2019.07.009", "year": "2019", "authors": "Moner-Girona, M.",
     "abstract": "Long abstract " * 10},
    {"title": "Decentralized rural electrification in Kenya: speeding up universal energy access",
     "doi": "", "year": "2019", "authors": "Moner-Girona M."},
    {"title": "Hybrid PV-diesel mini-grid in Nigeria: a techno-economic study",
     "doi": "10.1109/a", "year": "2020", "authors": "Okoye, C."},
    {"title": "Hydropower expansion in Ethiopia under climate uncertainty",
     "doi": "", "year": "2015", "authors": "Abebe, T."},
    {"title": "", "doi": ""},                       # skipped
]


def _seed(db):
    pid = db.create_project("Test project", "desc")
    added, skipped = db.add_records(pid, RECS[:2], "scopus.ris", "Scopus")
    assert (added, skipped) == (2, 0)
    added, skipped = db.add_records(pid, RECS[2:], "wos.txt", "Web of Science")
    assert (added, skipped) == (2, 1)
    return pid


def test_projects(db):
    pid = _seed(db)
    p = db.get_project(pid)
    assert p["name"] == "Test project"
    assert p["criteria"]["required_reviewers"] == 1
    assert p["schema"][0]["name"] == "authors"
    db.update_project(pid, criteria={"question": "Q", "required_reviewers": 2},
                      schema=[{"name": "x", "kind": "text"}])
    p = db.get_project(pid)
    assert p["criteria"]["question"] == "Q" and p["criteria"]["required_reviewers"] == 2
    assert [f["name"] for f in p["schema"]] == ["x"]
    assert [q["name"] for q in db.list_projects()] == ["Test project"]
    with pytest.raises(Exception):
        db.create_project("Test project")
    db.delete_project(pid)
    assert db.list_projects() == []
    assert len(db.records_df(pid, include_duplicates=True)) == 0     # cascade


def test_records_and_batches(db):
    pid = _seed(db)
    df = db.records_df(pid)
    assert len(df) == 4
    assert set(df["source_db"]) == {"Scopus", "Web of Science"}
    batches = db.import_batches(pid)
    assert batches["records"].tolist() == [2, 2]
    assert db.delete_batch(pid, "wos.txt") == 2
    assert len(db.records_df(pid)) == 2
    rid = int(df["id"].iloc[0])
    db.update_record(rid, notes="hello", bogus="ignored")
    assert db.get_record(rid)["notes"] == "hello"


def test_duplicates(db):
    pid = _seed(db)
    df = db.records_df(pid)
    ids = df["id"].tolist()
    records = df.to_dict("records")
    pairs = dedup.find_duplicates(records)
    certain = [p for p in pairs if p.certain]
    assert len(certain) == 1 and (certain[0].a, certain[0].b) == (0, 1)
    merged = dedup.merge_records(records, 0, [0, 1])
    db.mark_duplicates(ids[0], [ids[1]], 100, "identical title", merged)
    assert len(db.records_df(pid)) == 3
    dups = db.duplicates_df(pid)
    assert dups["kept_id"].tolist() == [ids[0]]
    assert db.get_record(ids[0])["source_db"] == "Scopus"
    db.upsert_candidates(pid, [(ids[2], ids[3], 86.0, "title similarity 86%")])
    cands = db.candidates_df(pid)
    assert len(cands) == 1 and cands["title_a"].iloc[0].startswith("Hybrid")
    db.set_candidate_status(int(cands["id"].iloc[0]), "ignored")
    assert len(db.candidates_df(pid)) == 0
    db.upsert_candidates(pid, [(ids[3], ids[2], 90.0, "again")])    # stays ignored
    assert len(db.candidates_df(pid)) == 0
    db.unmark_duplicate(ids[1])
    assert len(db.records_df(pid)) == 4
    db.reset_duplicates(pid)
    assert len(db.candidates_df(pid, "ignored")) == 1


def test_screening_flow_and_prisma(db):
    pid = _seed(db)
    ids = db.records_df(pid)["id"].tolist()
    db.mark_duplicates(ids[0], [ids[1]], 100, "identical title")
    # Two reviewers required
    st = db.stage_status(pid, "ta", required=2)
    assert set(st["status"]) == {"pending"} and len(st) == 3
    db.set_decision(ids[0], "ta", "alice", "include")
    db.set_decision(ids[0], "ta", "bob", "include")
    db.set_decision(ids[2], "ta", "alice", "include")
    db.set_decision(ids[2], "ta", "bob", "exclude", reason="Wrong outcome")
    db.set_decision(ids[3], "ta", "alice", "exclude", reason="Wrong population")
    db.set_decision(ids[3], "ta", "bob", "exclude", reason="Wrong population")
    st = db.stage_status(pid, "ta", required=2).set_index("record_id")
    assert st.loc[ids[0], "status"] == "include"
    assert st.loc[ids[2], "status"] == "conflict"
    assert st.loc[ids[3], "status"] == "exclude"
    assert st.loc[ids[3], "reason"] == "Wrong population"
    assert db.reviewers(pid) == ["alice", "bob"]
    db.set_decision(ids[2], "ta", "consensus", "include")
    assert db.stage_status(pid, "ta", 2).set_index("record_id").loc[ids[2], "status"] == "include"
    pool = db.stage_pool(pid, "ft", 2)
    assert pool["id"].tolist() == [ids[0], ids[2]]
    # Full text: one PDF not retrieved, the other included
    db.set_pdf(ids[2], "", "not_retrieved")
    db.set_pdf(ids[0], "/tmp/x.pdf", "available")
    db.set_decision(ids[0], "ft", "alice", "include")
    db.set_decision(ids[0], "ft", "bob", "include")
    c = db.prisma_counts(pid, required=2)
    assert c["identified"] == 4 and c["duplicates"] == 1 and c["screened"] == 3
    assert c["by_source"] == {"Scopus": 2, "Web of Science": 2}
    assert c["ta_excluded"] == 1 and c["ta_pending"] == 0 and c["sought"] == 2
    assert c["not_retrieved"] == 1 and c["assessed"] == 1
    assert c["ft_excluded"] == 0 and c["included"] == 1 and c["ft_pending"] == 0
    assert db.stage_pool(pid, "extract", 2)["id"].tolist() == [ids[0]]
    # AI suggestions
    db.save_ai_suggestion(ids[3], "ta", {"decision": "exclude", "reason": "Wrong population",
                                         "rationale": "r", "confidence": 0.9, "model": "m"})
    s = db.ai_suggestions(pid, "ta")
    assert s[ids[3]]["decision"] == "exclude" and s[ids[3]]["confidence"] == 0.9
    db.delete_decision(ids[0], "ft", "bob")
    assert db.stage_status(pid, "ft", 2).set_index("record_id").loc[ids[0], "status"] == "pending"


def test_extractions(db):
    pid = _seed(db)
    rid = db.records_df(pid)["id"].tolist()[0]
    db.save_extraction(rid, "model-x", {"authors": "Smith et al."}, {"authors": "quote"},
                       "full text", "/tmp/a.pdf")
    e = db.get_extraction(rid)
    assert e["status"] == "draft" and e["values"] == {"authors": "Smith et al."}
    assert e["ai"] == {"authors": "Smith et al."}
    db.verify_extraction(rid, {"authors": "Smith & Doe"}, {"authors": "quote"}, 12.5)
    v = db.verified_extractions(pid)
    assert len(v) == 1 and v[0]["values"]["authors"] == "Smith & Doe"
    assert v[0]["record_id"] == rid
    df = db.extractions_df(pid)
    assert df["status"].tolist() == ["verified"]
    db.save_extraction(rid, "model-x", None, None, "", "", error="boom")
    assert db.get_extraction(rid)["status"] == "failed"
    c = db.summary_counts(pid)
    assert c["extracted_verified"] == 0 and c["extracted_draft"] == 0
    db.delete_extraction(rid)
    assert db.get_extraction(rid) is None
