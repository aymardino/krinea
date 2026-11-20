"""Choosing which duplicate to keep, the source order of a review, the file filter (a record
belongs to its kept file only under the file order), and AI runs that only ever touch the
review's own records."""
import csv
import io

from krinea_api import models
from krinea_api.db import session_factory
from krinea_api.services import jobs
from krinea_core import llm
from tests.conftest import register

SCOPUS = """TY  - JOUR
AU  - Mwakitalima, I.
TI  - Levelised cost of electricity of solar mini-grids in Tanzania: evidence from 30 sites
JO  - Energy
PY  - 2021
DO  - 10.1016/j.energy.2021.03.003
AB  - LCOE data from 30 mini-grids in Tanzania, with capital and operating costs per site.
ER  -

TY  - JOUR
AU  - Okoye, C.
TI  - Optimal sizing of a hybrid PV-diesel-battery mini-grid for a village in Nigeria
JO  - Renewable Energy
PY  - 2020
DO  - 10.1016/j.renene.2020.01.001
AB  - Hybrid mini-grid techno-economic optimisation, LCOE 0.31 USD/kWh, sized for 450 households.
KW  - Nigeria
ER  -
"""

PUBMED = """TY  - JOUR
AU  - Mwakitalima, I.
TI  - Levelized cost of electricity of solar mini grids in Tanzania: evidence from thirty sites
PY  - 2021
ER  -

TY  - JOUR
AU  - Okoye, C.
TI  - Optimal sizing of a hybrid PV-diesel-battery mini-grid for a village in Nigeria
PY  - 2020
DO  - 10.1016/j.renene.2020.01.001
ER  -
"""


def _import(client, rid, name, text, source):
    r = client.post(f"/reviews/{rid}/imports", data={"source_db": source},
                    files={"files": (name, io.BytesIO(text.encode()), "application/x-research-info-systems")})
    assert r.status_code == 201, r.text
    return r.json()[0]["id"]


def _records(client, rid, **params):
    q = "&".join(f"{k}={v}" for k, v in {"stage": "ta", "view": "all", **params}.items())
    return client.get(f"/reviews/{rid}/records?{q}").json()["items"]


def test_source_order_and_explicit_choice(client):
    register(client, "dedup-owner@example.org", "Owner")
    rid = client.post("/reviews", json={"title": "Mini-grid costs"}).json()["id"]
    file_a = _import(client, rid, "scopus.ris", SCOPUS, "Scopus")
    file_b = _import(client, rid, "pubmed.ris", PUBMED, "PubMed")
    recs = {(r["source_db"], r["year"]): r["id"] for r in _records(client, rid)}
    x_a, y_a, x_b, y_b = recs[("Scopus", "2021")], recs[("Scopus", "2020")], recs[("PubMed", "2021")], recs[("PubMed", "2020")]

    assert client.get(f"/reviews/{rid}/sources").json() == [{"source": "PubMed", "n": 2}, {"source": "Scopus", "n": 2}]

    # Without an order, the most complete record is kept.
    assert client.post(f"/reviews/{rid}/dedup/run", json={"auto_threshold": 95, "review_threshold": 85}).status_code == 200
    dups = client.get(f"/reviews/{rid}/dedup/duplicates").json()
    assert [(d["id"], d["kept_id"]) for d in dups] == [(y_b, y_a)]
    cands = client.get(f"/reviews/{rid}/dedup/candidates").json()
    assert len(cands) == 1 and cands[0]["suggested_keep"] == x_a

    # The review's source order wins over completeness, for the suggestion and for automatic merges.
    r = client.patch(f"/reviews/{rid}", json={"settings": {"source_priority": ["PubMed", " Scopus ", "pubmed", ""]}})
    assert r.json()["settings"]["source_priority"] == ["PubMed", "Scopus"]
    assert r.json()["settings"]["keeper_rule"] == "database"
    assert client.get(f"/reviews/{rid}/dedup/candidates").json()[0]["suggested_keep"] == x_b
    client.post(f"/reviews/{rid}/dedup/run", json={"auto_threshold": 95, "review_threshold": 85})
    assert [(d["id"], d["kept_id"]) for d in client.get(f"/reviews/{rid}/dedup/duplicates").json()] == [(y_a, y_b)]

    # The person can still keep the other record of a pair; anything else is refused.
    cand = client.get(f"/reviews/{rid}/dedup/candidates").json()[0]
    assert client.post(f"/reviews/{rid}/dedup/candidates/{cand['id']}/merge?keep={y_a}").status_code == 400
    assert client.post(f"/reviews/{rid}/dedup/candidates/{cand['id']}/merge?keep={x_a}").json()["status"] == "merged"
    kept = client.get(f"/reviews/{rid}/records/{x_a}").json()
    assert kept["doi"] == "10.1016/j.energy.2021.03.003" and kept["source_db"] == "Scopus; PubMed"
    assert client.get(f"/reviews/{rid}/records/{x_b}").json()["duplicate_of"] == x_a

    # Filtering by file keeps the records found in that file, even when merged into another file's record.
    assert {r["id"] for r in _records(client, rid, import_id=file_a)} == {x_a, y_b}
    assert {r["id"] for r in _records(client, rid, import_id=file_b)} == {x_a, y_b}
    assert len(_records(client, rid)) == 2


def test_with_the_file_order_a_record_belongs_to_the_file_it_was_kept_from(client):
    """One file per search, each with its own criteria (D-42): the order of the files decides
    the record kept and the one file it counts for, in lists, keywords and exports."""
    register(client, "dedup-files@example.org", "Owner")
    rid = client.post("/reviews", json={"title": "One file per search"}).json()["id"]
    file_a = _import(client, rid, "query1.ris", SCOPUS, "Scopus")
    file_b = _import(client, rid, "query3.ris", PUBMED, "PubMed")
    recs = {(r["source_db"], r["year"]): r["id"] for r in _records(client, rid)}
    x_a, y_a, x_b, y_b = recs[("Scopus", "2021")], recs[("Scopus", "2020")], recs[("PubMed", "2021")], recs[("PubMed", "2020")]
    r = client.patch(f"/reviews/{rid}", json={"settings": {"keeper_rule": "file", "file_priority": [file_b, file_a]}})
    assert r.json()["settings"]["keeper_rule"] == "file"
    client.put(f"/reviews/{rid}/imports/{file_a}/keywords", json={"include": ["Nigeria"], "exclude": []})
    assert client.post(f"/reviews/{rid}/dedup/run", json={"auto_threshold": 95, "review_threshold": 85}).status_code == 200

    # The Nigeria study, found by both searches, is kept from query 3, ranked first: it counts
    # for query 3 only, and query 1 keeps the Tanzania study it found.
    assert [(d["id"], d["kept_id"]) for d in client.get(f"/reviews/{rid}/dedup/duplicates").json()] == [(y_a, y_b)]
    assert {r["id"] for r in _records(client, rid, import_id=file_a)} == {x_a}
    assert {r["id"] for r in _records(client, rid, import_id=file_b)} == {x_b, y_b}
    assert client.get(f"/reviews/{rid}/records/{y_b}").json()["found_in"] == [file_b]
    kw = client.get(f"/reviews/{rid}/keywords", params={"import_id": file_a}).json()
    assert kw["search"]["include"] == [{"keyword": "Nigeria", "n": 0}]
    assert client.get(f"/reviews/{rid}/export/count", params={"stage": "ta", "import_id": file_a}).json()["n"] == 1
    export = client.get(f"/reviews/{rid}/export/screening.csv", params={"stage": "ta"}).text
    rows = {int(row["id"]): row for row in csv.DictReader(io.StringIO(export))}
    assert (rows[y_b]["file"], rows[y_b]["files"]) == ("query3.ris", "query3.ris; query1.ris")


def test_each_search_brings_its_own_criteria_to_the_ai(client, monkeypatch):
    """One search per sub-question (D-47): the AI screens a record with the criteria of the
    search it belongs to, never with those of another."""
    register(client, "search-criteria@example.org", "Owner")
    rid = client.post("/reviews", json={"title": "Sub-questions"}).json()["id"]
    file_a = _import(client, rid, "query1.ris", SCOPUS, "Scopus")
    file_b = _import(client, rid, "query3.ris", PUBMED, "PubMed")
    y_b = {(r["source_db"], r["year"]): r["id"] for r in _records(client, rid)}[("PubMed", "2020")]
    client.patch(f"/reviews/{rid}", json={"settings": {"keeper_rule": "file", "file_priority": [file_b, file_a]}})
    assert client.post(f"/reviews/{rid}/dedup/run", json={"auto_threshold": 95, "review_threshold": 85}).status_code == 200
    r = client.put(f"/reviews/{rid}/imports/{file_b}/criteria",
                   json={"question": " Do hybrid mini-grids cut costs? ", "inclusion": "Cost data", "exclusion": ""})
    assert r.json() == {"question": "Do hybrid mini-grids cut costs?", "inclusion": "Cost data", "exclusion": ""}
    client.put(f"/reviews/{rid}/imports/{file_a}/criteria", json={"question": "Tanzania only?"})
    assert set(client.get(f"/reviews/{rid}").json()["criteria"]["search_criteria"]) == {file_a, file_b}

    client.put("/auth/keys/gemini", json={"key": "AQ.test-key-1234567890"})
    prompts = []

    def answer(prompt, provider, key, model=None, **kw):
        prompts.append(prompt)
        return {"decision": "include", "reason": "", "rationale": "", "confidence": 0.9}, llm.Usage(1, 1)

    monkeypatch.setattr(llm, "call_json", answer)
    # The Nigeria study, found by both searches, belongs to query 3 (ranked first).
    job = client.post(f"/reviews/{rid}/ai/screen", json={"stage": "ta", "record_ids": [y_b], "limit": 1}).json()
    assert job["result"]["ok"] == 1
    assert 'Search "query3.ris"' in prompts[0] and "Sub-question: Do hybrid mini-grids cut costs?" in prompts[0]
    assert "Tanzania only?" not in prompts[0]

    # Emptied, a search's criteria go; deleting a file takes its criteria with it.
    client.put(f"/reviews/{rid}/imports/{file_b}/criteria", json={})
    assert client.delete(f"/reviews/{rid}/imports/{file_a}").status_code == 200
    assert client.get(f"/reviews/{rid}").json()["criteria"]["search_criteria"] == {}


def test_extraction_fields_of_one_search_apply_to_its_studies_only(client, monkeypatch, pdf_bytes):
    """General fields plus fields of one search (D-48): a study is extracted and checked with the
    general fields and those of the search it belongs to."""
    register(client, "search-fields@example.org", "Owner")
    rid = client.post("/reviews", json={"title": "Fields per search"}).json()["id"]
    file_a = _import(client, rid, "query1.ris", SCOPUS, "Scopus")
    file_b = _import(client, rid, "query3.ris", PUBMED, "PubMed")
    y_b = {(r["source_db"], r["year"]): r["id"] for r in _records(client, rid)}[("PubMed", "2020")]
    client.patch(f"/reviews/{rid}", json={"settings": {"keeper_rule": "file", "file_priority": [file_b, file_a]}})
    client.post(f"/reviews/{rid}/dedup/run", json={"auto_threshold": 95, "review_threshold": 85})
    schema = [{"name": "country", "kind": "text"},
              {"name": "tariff", "kind": "text", "required": True, "searches": [file_b]},
              {"name": "storage", "kind": "text", "required": True, "searches": [file_a]}]
    r = client.patch(f"/reviews/{rid}", json={"extraction_schema": schema})
    assert [f.get("searches") for f in r.json()["extraction_schema"]] == [None, [file_b], [file_a]]
    for stage in ("ta", "ft"):
        client.post(f"/reviews/{rid}/records/{y_b}/decision", json={"stage": stage, "decision": "include"})
    assert client.post(f"/reviews/{rid}/records/{y_b}/pdf", files={"file": ("p.pdf", pdf_bytes, "application/pdf")}).status_code == 200

    client.put("/auth/keys/gemini", json={"key": "AQ.test-key-1234567890"})
    prompts = []

    def answer(prompt, provider, key, model=None, **kw):
        prompts.append(prompt)
        return {"country": {"value": "Nigeria", "quote": "Nigeria"}}, llm.Usage(1, 1)

    monkeypatch.setattr(llm, "call_json", answer)
    assert client.post(f"/reviews/{rid}/extraction/run", json={"record_ids": [y_b]}).json()["result"]["ok"] == 1
    assert "- country:" in prompts[0] and "- tariff:" in prompts[0] and "- storage:" not in prompts[0]
    flags = client.put(f"/reviews/{rid}/extraction/{y_b}", json={"values": {"country": "Nigeria"}}).json()["flags"]
    assert "tariff" in flags and "storage" not in flags          # required, but for query 1 only


def test_ai_runs_ignore_records_of_other_reviews(client, monkeypatch):
    register(client, "dedup-scope@example.org", "Scope")
    mine = client.post("/reviews", json={"title": "Mine"}).json()["id"]
    other = client.post("/reviews", json={"title": "Other"}).json()["id"]
    _import(client, other, "other.ris", SCOPUS, "Scopus")
    foreign = [r["id"] for r in _records(client, other)]
    client.put("/auth/keys/gemini", json={"key": "AQ.test-key-1234567890"})

    def no_call(*a, **kw):
        raise AssertionError("the AI must not be called for another review's records")
    monkeypatch.setattr(llm, "call_json", no_call)
    r = client.post(f"/reviews/{mine}/ai/screen", json={"stage": "ta", "record_ids": foreign})
    assert r.status_code == 200 and r.json()["result"]["total"] == 0
    r = client.post(f"/reviews/{mine}/extraction/run", json={"record_ids": foreign})
    assert r.status_code == 200 and r.json()["result"]["total"] == 0

    # The job runner itself skips foreign records too.
    db = session_factory()()
    try:
        user = db.query(models.User).filter_by(email="dedup-scope@example.org").one()
        job = models.Job(review_id=mine, user_id=user.id, kind="extract", payload={"record_ids": foreign})
        db.add(job)
        db.commit()
        assert jobs._run_extract(db, job) == {"ok": 0, "failed": 0, "total": len(foreign)}
        assert db.query(models.Extraction).filter(models.Extraction.record_id.in_(foreign)).count() == 0
    finally:
        db.close()


CHAIN = [  # A ~ B and B ~ C are near matches; A and C are not, on their own
    "Solar mini-grids for rural electrification in Tanzania: costs and evidence from thirty sites",
    "Solar mini grids for rural electrification in Tanzania: cost evidence from 30 sites",
    "Mini grids for rural electrification in Tanzania: cost evidence from 30 sites in 2021",
]


def _ris(rows):
    out = []
    for title, doi, abstract in rows:
        out.append("TY  - JOUR\nAU  - Kariuki, W.\nTI  - " + title + "\nPY  - 2021\n"
                   + (f"DO  - {doi}\n" if doi else "") + (f"AB  - {abstract}\n" if abstract else "") + "ER  - \n")
    return "\n".join(out)


def test_three_or_more_records_of_one_study(client):
    register(client, "dedup-many@example.org", "Many")
    rid = client.post("/reviews", json={"title": "Many copies"}).json()["id"]
    # Three records share a DOI (one under a title of the database's own), a fourth is only a
    # near match of one of them, under the title of the second database.
    _import(client, rid, "a.ris", _ris([("A record whose database rewrote the title entirely, for some reason",
                                          "10.1016/j.energy.2021.03.003", "Long abstract " * 10)]), "Scopus")
    _import(client, rid, "b.ris", _ris([(CHAIN[0], "10.1016/j.energy.2021.03.003", "")]), "PubMed")
    _import(client, rid, "c.ris", _ris([(CHAIN[0], "10.1016/j.energy.2021.03.003", "")]), "Embase")
    _import(client, rid, "d.ris", _ris([(CHAIN[1], "", "")]), "Web of Science")
    ids = {r["source_db"]: r["id"] for r in _records(client, rid)}
    client.post(f"/reviews/{rid}/dedup/run", json={"auto_threshold": 95, "review_threshold": 85})
    # The three DOI matches merge into one record (the most complete), whatever their number.
    dups = client.get(f"/reviews/{rid}/dedup/duplicates").json()
    assert sorted((d["id"], d["kept_id"]) for d in dups) == [(ids["PubMed"], ids["Scopus"]), (ids["Embase"], ids["Scopus"])]
    # The near match of a merged-away record is asked about the kept record, once.
    cands = client.get(f"/reviews/{rid}/dedup/candidates").json()
    assert [(c["a"]["id"], c["b"]["id"]) for c in cands] == [(ids["Scopus"], ids["Web of Science"])]


def test_chain_of_near_matches_is_asked_about_the_kept_record(client):
    register(client, "dedup-chain@example.org", "Chain")
    rid = client.post("/reviews", json={"title": "Chain"}).json()["id"]
    _import(client, rid, "chain.ris", _ris([(t, "", "") for t in CHAIN]), "Scopus")
    a, b, c = [r["id"] for r in _records(client, rid)]
    client.post(f"/reviews/{rid}/dedup/run", json={"auto_threshold": 95, "review_threshold": 85})
    pairs = {(x["a"]["id"], x["b"]["id"]): x["id"] for x in client.get(f"/reviews/{rid}/dedup/candidates").json()}
    assert set(pairs) == {(a, b), (b, c)}
    # Merging B into A turns the pending pair B-C into A-C.
    client.post(f"/reviews/{rid}/dedup/candidates/{pairs[(a, b)]}/merge?keep={a}")
    left = client.get(f"/reviews/{rid}/dedup/candidates").json()
    assert [(x["a"]["id"], x["b"]["id"]) for x in left] == [(a, c)]
    client.post(f"/reviews/{rid}/dedup/candidates/{left[0]['id']}/merge?keep={a}")
    assert client.get(f"/reviews/{rid}/dedup/candidates").json() == []
    assert sorted((d["id"], d["kept_id"]) for d in client.get(f"/reviews/{rid}/dedup/duplicates").json()) == [(b, a), (c, a)]


def test_file_order_rule(client):
    register(client, "dedup-files@example.org", "Files")
    rid = client.post("/reviews", json={"title": "Seventeen searches"}).json()["id"]
    file_a = _import(client, rid, "q1.ris", SCOPUS, "Scopus")
    file_b = _import(client, rid, "q9.ris", PUBMED, "PubMed")
    recs = {(r["source_db"], r["year"]): r["id"] for r in _records(client, rid)}
    y_a, y_b, x_b = recs[("Scopus", "2020")], recs[("PubMed", "2020")], recs[("PubMed", "2021")]

    # Query 9 first: its record is kept, even though query 1's is more complete.
    r = client.patch(f"/reviews/{rid}", json={"settings": {"keeper_rule": "file", "file_priority": [file_b, "not-an-import", file_a, file_b]}})
    assert r.json()["settings"]["file_priority"] == [file_b, file_a] and r.json()["settings"]["keeper_rule"] == "file"
    client.post(f"/reviews/{rid}/dedup/run", json={"auto_threshold": 95, "review_threshold": 85})
    assert [(d["id"], d["kept_id"]) for d in client.get(f"/reviews/{rid}/dedup/duplicates").json()] == [(y_a, y_b)]
    assert client.get(f"/reviews/{rid}/dedup/candidates").json()[0]["suggested_keep"] == x_b
    kept = client.get(f"/reviews/{rid}/records/{y_b}").json()
    assert kept["abstract"].startswith("Hybrid mini-grid") and kept["source_db"] == "PubMed; Scopus"   # gaps filled from query 1

    # Back to the most complete record; an unknown rule is ignored; a deleted file leaves the order.
    assert client.patch(f"/reviews/{rid}", json={"settings": {"keeper_rule": "fastest"}}).json()["settings"]["keeper_rule"] == "file"
    assert client.patch(f"/reviews/{rid}", json={"settings": {"keeper_rule": "complete"}}).json()["settings"]["keeper_rule"] == "complete"
    client.delete(f"/reviews/{rid}/imports/{file_a}")
    assert client.get(f"/reviews/{rid}").json()["settings"]["file_priority"] == [file_b]


def test_restore_all_gives_records_back_as_imported(client):
    register(client, "dedup-restore@example.org", "Restore")
    rid = client.post("/reviews", json={"title": "Undo"}).json()["id"]
    file_a = _import(client, rid, "scopus.ris", SCOPUS, "Scopus")
    _import(client, rid, "pubmed.ris", PUBMED, "PubMed")
    recs = {(r["source_db"], r["year"]): r for r in _records(client, rid)}
    y_a, y_b = recs[("Scopus", "2020")]["id"], recs[("PubMed", "2020")]["id"]
    x_a, x_b = recs[("Scopus", "2021")]["id"], recs[("PubMed", "2021")]["id"]
    before_b = client.get(f"/reviews/{rid}/records/{y_b}").json()

    # Query 9 (PubMed) first: the poorer PubMed record is kept and filled from the Scopus one.
    client.patch(f"/reviews/{rid}", json={"settings": {"keeper_rule": "file", "file_priority": [recs[("PubMed", "2020")]["import_id"], file_a]}})
    client.post(f"/reviews/{rid}/dedup/run", json={"auto_threshold": 95, "review_threshold": 85})
    kept = client.get(f"/reviews/{rid}/records/{y_b}").json()
    assert kept["abstract"] and kept["journal"] == "Renewable Energy" and kept["source_db"] == "PubMed; Scopus"
    cand = client.get(f"/reviews/{rid}/dedup/candidates").json()[0]
    client.post(f"/reviews/{rid}/dedup/candidates/{cand['id']}/ignore")       # "different, keep both"

    # Restoring one duplicate recomputes its keeper; restoring everything undoes every merge.
    assert client.post(f"/reviews/{rid}/records/{y_a}/restore").json() == {"ok": True}
    back = client.get(f"/reviews/{rid}/records/{y_b}").json()
    assert (back["abstract"], back["journal"], back["source_db"]) == (before_b["abstract"], before_b["journal"], "PubMed")
    client.post(f"/reviews/{rid}/dedup/run", json={"auto_threshold": 95, "review_threshold": 85})
    assert client.get(f"/reviews/{rid}/records/{y_a}").json()["duplicate_of"] == y_b
    assert client.post(f"/reviews/{rid}/dedup/restore-all").json() == {"restored": 1}
    assert client.get(f"/reviews/{rid}/dedup/duplicates").json() == []
    back = client.get(f"/reviews/{rid}/records/{y_b}").json()
    assert (back["abstract"], back["journal"], back["source_db"]) == (before_b["abstract"], before_b["journal"], "PubMed")
    assert len(_records(client, rid)) == 4
    # The pair answered "different" stays answered on the next detection.
    client.post(f"/reviews/{rid}/dedup/run", json={"auto_threshold": 95, "review_threshold": 85})
    assert client.get(f"/reviews/{rid}/dedup/candidates").json() == []
    assert {x_a, x_b} <= {r["id"] for r in _records(client, rid)}


def test_merges_made_before_originals_were_kept(client):
    from krinea_api import models
    from krinea_api.db import session_factory
    register(client, "dedup-legacy@example.org", "Legacy")
    rid = client.post("/reviews", json={"title": "Legacy"}).json()["id"]
    file_a = _import(client, rid, "scopus.ris", SCOPUS, "Scopus")
    _import(client, rid, "pubmed.ris", PUBMED, "PubMed")
    client.post(f"/reviews/{rid}/dedup/run", json={"auto_threshold": 95, "review_threshold": 85})
    y_a = next(r["id"] for r in _records(client, rid) if r["year"] == "2020")
    assert client.get(f"/reviews/{rid}/records/{y_a}").json()["source_db"] == "Scopus; PubMed"
    db = session_factory()()
    try:                                      # as if the merge had been made by an earlier version
        db.query(models.RecordOriginal).filter_by(review_id=rid).delete()
        db.commit()
    finally:
        db.close()
    client.post(f"/reviews/{rid}/dedup/restore-all")
    assert client.get(f"/reviews/{rid}/records/{y_a}").json()["source_db"] == "Scopus"   # the source list is put right
    # Deleting a file recomputes the records that had absorbed its duplicates.
    client.post(f"/reviews/{rid}/dedup/run", json={"auto_threshold": 95, "review_threshold": 85})
    pubmed = next(i["id"] for i in client.get(f"/reviews/{rid}/imports").json() if i["source_db"] == "PubMed")
    client.delete(f"/reviews/{rid}/imports/{pubmed}")
    assert client.get(f"/reviews/{rid}/records/{y_a}").json()["source_db"] == "Scopus"
    assert file_a
