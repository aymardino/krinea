"""Choosing which duplicate to keep, the source order of a review, the file filter, and AI
runs that only ever touch the review's own records."""
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


def test_ai_runs_ignore_records_of_other_reviews(client, monkeypatch):
    register(client, "dedup-scope@example.org", "Scope")
    mine = client.post("/reviews", json={"title": "Mine"}).json()["id"]
    other = client.post("/reviews", json={"title": "Other"}).json()["id"]
    _import(client, other, "other.ris", SCOPUS, "Scopus")
    foreign = [r["id"] for r in _records(client, other)]
    client.put("/auth/keys/claude", json={"key": "sk-ant-test-key-1234567890"})

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
