"""End-to-end review: create, invite, import, dedup, screen (two reviewers,
conflict, consensus), full text, extraction, PRISMA, exports, AI job."""
import io

from tamis_api.services import email as email_service
from tamis_core import llm
from tests.conftest import register

RIS = """TY  - JOUR
AU  - Moner-Girona, M.
TI  - Techno-economic assessment of solar PV mini-grids for rural electrification in Kenya
JO  - Energy for Sustainable Development
PY  - 2019
DO  - 10.1016/j.esd.2019.07.009
AB  - Mini-grids and solar home systems in Kenya, HOMER modelling, LCOE results.
KW  - Kenya
ER  - 

TY  - JOUR
AU  - Moner-Girona M.
TI  - Techno-economic assessment of solar PV mini-grids for rural electrification in Kenya
JO  - Energy Sustain Dev
PY  - 2019
ER  - 

TY  - JOUR
AU  - Okoye, C.
TI  - Optimal sizing of a hybrid PV-diesel-battery mini-grid for a village in Nigeria
PY  - 2020
DO  - 10.1016/j.renene.2020.01.001
AB  - Hybrid mini-grid techno-economic optimisation, LCOE 0.31 USD/kWh.
ER  - 

TY  - JOUR
AU  - Smith, J.
TI  - Grid extension policy in Europe: a historical review
PY  - 2018
DO  - 10.1016/j.enpol.2018.02.002
AB  - A review of grid extension in Europe. No quantitative modelling.
ER  - 

TY  - JOUR
AU  - Mwakitalima, I.
TI  - Levelised cost of electricity of solar mini-grids in Tanzania: evidence from 30 sites
PY  - 2021
DO  - 10.1016/j.energy.2021.03.003
AB  - LCOE data from 30 mini-grids in Tanzania.
ER  - 

TY  - JOUR
AU  - Mwakitalima, I.
TI  - Levelized cost of electricity of solar mini grids in Tanzania: evidence from thirty sites
PY  - 2021
ER  - 
"""


def _setup(client, client2):
    alice = register(client, "owner@example.org", "Alice")
    bob = register(client2, "reviewer@example.org", "Bob")
    r = client.post("/reviews", json={"title": "Solar mini-grids", "question": "Cost-effectiveness of mini-grids?"})
    assert r.status_code == 201, r.text
    review = r.json()
    rid = review["id"]
    assert review["my_role"] == "owner" and review["settings"]["required_reviewers"] == 1
    # Bob is not a member yet
    assert client2.get(f"/reviews/{rid}").status_code == 403
    # Invite Bob
    r = client.post(f"/reviews/{rid}/invitations", json={"email": "reviewer@example.org", "role": "reviewer"})
    assert r.status_code == 201, r.text
    token = r.json()["accept_url"].rsplit("/", 1)[1]
    assert "reviewer@example.org" == email_service.OUTBOX[-1]["to"]
    assert client2.get(f"/reviews/invitations/{token}/preview").json()["review_title"] == "Solar mini-grids"
    r = client2.post("/reviews/invitations/accept", json={"token": token})
    assert r.status_code == 200 and r.json()["my_role"] == "reviewer"
    assert len(client.get(f"/reviews/{rid}/members").json()) == 2
    return alice, bob, rid


def test_full_flow(client, client2, pdf_bytes, monkeypatch):
    alice, bob, rid = _setup(client, client2)

    # Settings: double screening, blind, keywords
    r = client.patch(f"/reviews/{rid}", json={
        "settings": {"required_reviewers": 2, "blind": True},
        "criteria": {"inclusion": "Solar mini-grid in Africa", "highlight_include": ["mini-grid*", "solar", "LCOE"],
                     "highlight_exclude": ["Europe", "review"]}})
    assert r.status_code == 200 and r.json()["settings"]["required_reviewers"] == 2
    assert client2.patch(f"/reviews/{rid}", json={"title": "x"}).status_code == 403     # reviewer cannot

    # Import
    r = client.post(f"/reviews/{rid}/imports", files={"files": ("scopus.ris", RIS.encode(), "text/plain")},
                    data={"source_db": "Scopus"})
    assert r.status_code == 201, r.text
    imp = r.json()[0]
    assert imp["n_records"] == 6 and imp["format"] == "ris"
    assert client.get(f"/reviews/{rid}/imports").json()[0]["n_records"] == 6
    kw = client.get(f"/reviews/{rid}/keywords").json()
    assert {k["keyword"]: k["n"] for k in kw["include"]}["solar"] >= 4

    # Dedup (inline job)
    r = client.post(f"/reviews/{rid}/dedup/run", json={"auto_threshold": 95, "review_threshold": 85})
    assert r.status_code == 200 and r.json()["status"] == "done", r.text
    assert r.json()["result"]["removed"] == 1 and r.json()["result"]["possible"] == 1
    dups = client.get(f"/reviews/{rid}/dedup/duplicates").json()
    assert len(dups) == 1 and dups[0]["kept_title"].startswith("Techno-economic")
    cands = client.get(f"/reviews/{rid}/dedup/candidates").json()
    assert len(cands) == 1 and cands[0]["a"]["title"].startswith("Levelised")
    assert client.post(f"/reviews/{rid}/dedup/candidates/{cands[0]['id']}/merge").json()["status"] == "merged"
    assert client.get(f"/reviews/{rid}/dedup/candidates").json() == []
    summary = client.get(f"/reviews/{rid}/summary").json()
    assert summary == {**summary, "records": 6, "duplicates": 2, "unique": 4}
    assert summary["stages"]["ta"]["pool"] == 4 and summary["stages"]["ta"]["pending"] == 4

    # Screening: views and decisions
    page = client.get(f"/reviews/{rid}/records", params={"stage": "ta", "view": "todo"}).json()
    assert page["total"] == 4 and all(i["ta_status"] == "pending" for i in page["items"])
    ids = [i["id"] for i in page["items"]]
    kenya, nigeria, europe, tanzania = ids
    r = client.post(f"/reviews/{rid}/records/{kenya}/decision", json={"stage": "ta", "decision": "include", "seconds": 12})
    assert r.status_code == 200 and r.json()["my_decision"]["decision"] == "include"
    assert r.json()["ta_status"] == "pending"                       # Bob has not decided yet
    client2.post(f"/reviews/{rid}/records/{kenya}/decision", json={"stage": "ta", "decision": "include"})
    client.post(f"/reviews/{rid}/records/{europe}/decision", json={"stage": "ta", "decision": "exclude", "reason": "Wrong population / setting"})
    client2.post(f"/reviews/{rid}/records/{europe}/decision", json={"stage": "ta", "decision": "exclude", "reason": "Wrong population / setting"})
    client.post(f"/reviews/{rid}/records/{nigeria}/decision", json={"stage": "ta", "decision": "include"})
    client2.post(f"/reviews/{rid}/records/{nigeria}/decision", json={"stage": "ta", "decision": "exclude", "reason": "Wrong outcome"})
    # Blind mode: Bob sees only his decision, Alice (owner) sees both
    rec_bob = client2.get(f"/reviews/{rid}/records/{nigeria}").json()
    assert rec_bob["ta_status"] == "conflict" and len(rec_bob["decisions"]) == 1
    rec_alice = client.get(f"/reviews/{rid}/records/{nigeria}").json()
    assert len(rec_alice["decisions"]) == 2
    assert client2.post(f"/reviews/{rid}/records/{nigeria}/decision",
                        json={"stage": "ta", "decision": "include", "as_consensus": True}).status_code == 403
    r = client.post(f"/reviews/{rid}/records/{nigeria}/decision", json={"stage": "ta", "decision": "include", "as_consensus": True})
    assert r.json()["ta_status"] == "include"
    conflicts = client.get(f"/reviews/{rid}/records", params={"view": "conflict"}).json()
    assert conflicts["total"] == 0
    todo_bob = client2.get(f"/reviews/{rid}/records", params={"view": "todo"}).json()
    assert [i["id"] for i in todo_bob["items"]] == [tanzania]
    search = client.get(f"/reviews/{rid}/records", params={"view": "all", "search": "Tanzania"}).json()
    assert search["total"] == 1
    # Bulk decision + labels
    r = client2.post(f"/reviews/{rid}/records/decisions/bulk", json={"record_ids": [tanzania], "stage": "ta", "decision": "maybe"})
    assert r.json()["updated"] == 1
    client.patch(f"/reviews/{rid}/records/{tanzania}", json={"labels": "needs full text; Tanzania"})
    assert {l["label"] for l in client.get(f"/reviews/{rid}/labels").json()} == {"needs full text", "Tanzania"}
    s = client.get(f"/reviews/{rid}/summary").json()["stages"]["ta"]
    assert s["include"] == 2 and s["exclude"] == 1 and s["pending"] == 1 and s["my_done"] == 3
    assert {r["name"]: r["done"] for r in s["reviewers"]} == {"Alice": 3, "Bob": 4}

    # Full text: Kenya and Nigeria are in the pool
    ft = client.get(f"/reviews/{rid}/records", params={"stage": "ft", "view": "all"}).json()
    assert sorted(i["id"] for i in ft["items"]) == sorted([kenya, nigeria])
    r = client.post(f"/reviews/{rid}/records/{kenya}/pdf", files={"file": ("paper.pdf", pdf_bytes, "application/pdf")})
    assert r.status_code == 200 and r.json()["has_pdf"] and r.json()["pdf_status"] == "available"
    assert client.get(f"/reviews/{rid}/records/{kenya}/pdf").headers["content-type"] == "application/pdf"
    assert "mini-grids" in client.get(f"/reviews/{rid}/records/{kenya}/text").json()["text"]
    assert client.post(f"/reviews/{rid}/records/{nigeria}/pdf", files={"file": ("x.pdf", b"not a pdf", "application/pdf")}).status_code == 400
    assert client.post(f"/reviews/{rid}/records/{nigeria}/pdf/not-retrieved").json()["pdf_status"] == "not_retrieved"
    for c in (client, client2):
        c.post(f"/reviews/{rid}/records/{kenya}/decision", json={"stage": "ft", "decision": "include"})
    prisma = client.get(f"/reviews/{rid}/prisma").json()
    assert prisma == {**prisma, "identified": 6, "duplicates_removed": 2, "screened": 4, "ta_excluded": 1,
                      "sought": 2, "not_retrieved": 1, "assessed": 1, "included": 1}
    svg = client.get(f"/reviews/{rid}/prisma.svg", params={"variant": "new_v2", "lang": "fr"})
    assert svg.status_code == 200 and svg.text.startswith("<svg") and "Doublons" in svg.text

    # Extraction without AI: manual verification, then exports
    r = client.put(f"/reviews/{rid}/extraction/{kenya}", json={"values": {"authors": "Moner-Girona et al.", "year": "2019", "country": "Kenya"}})
    assert r.status_code == 200 and r.json()["status"] == "verified"
    assert r.json()["flags"]["key_result"][0] == "error"          # required field still empty
    assert len(client.get(f"/reviews/{rid}/extraction").json()) == 1
    assert client.get(f"/reviews/{rid}/extraction/{kenya}").json()["values"]["country"] == "Kenya"
    for path, needle in (("export/included.ris", "TY  - JOUR"), ("export/included.csv", "Moner-Girona"),
                         ("export/records.csv", "ta_status"), ("export/decisions.csv", "consensus"),
                         ("export/extractions.csv", "Kenya"), ("export/prisma.csv", "included")):
        r = client.get(f"/reviews/{rid}/{path}")
        assert r.status_code == 200 and needle in r.text, path
    assert client.get(f"/reviews/{rid}/export/extractions.xlsx").status_code == 200

    # AI: no key -> 402; with a key, a stubbed provider, inline job, metering
    assert client2.post(f"/reviews/{rid}/ai/screen", json={"stage": "ta"}).status_code == 402
    client2.put("/auth/keys/claude", json={"key": "sk-ant-test-key-1234567890"})
    monkeypatch.setattr(llm, "call_json", lambda prompt, provider, key, model=None, **kw: (
        {"decision": "exclude", "reason": "Wrong outcome", "rationale": "No cost data.", "confidence": 0.8},
        llm.Usage(120, 30)))
    r = client2.post(f"/reviews/{rid}/ai/screen", json={"stage": "ta"})
    assert r.status_code == 200 and r.json()["status"] == "done", r.text
    assert r.json()["result"]["ok"] == 1                            # only Tanzania is still pending
    sugg = client2.get(f"/reviews/{rid}/ai/suggestions").json()
    assert sugg[0]["record_id"] == tanzania and sugg[0]["decision"] == "exclude"
    rec = client2.get(f"/reviews/{rid}/records/{tanzania}").json()
    assert rec["ai"]["confidence"] == 0.8
    assert client2.get("/auth/usage").json()["own_key_tokens"] == 150
    # Extraction job on Kenya (has a PDF)
    monkeypatch.setattr(llm, "call_json", lambda prompt, provider, key, model=None, **kw: (
        {"authors": {"value": "Moner-Girona et al.", "quote": "M Moner-Girona"},
         "key_result": {"value": "Mini-grids are least cost.", "quote": "mini-grids are least cost"}}, llm.Usage(5000, 400)))
    r = client2.post(f"/reviews/{rid}/extraction/run", json={"record_ids": [kenya]})
    assert r.json()["status"] == "done" and r.json()["result"]["ok"] == 1
    ex = client2.get(f"/reviews/{rid}/extraction/{kenya}").json()
    assert ex["status"] == "draft" and ex["values"]["key_result"] == "Mini-grids are least cost."
    assert "mini-grids" in ex["text_extracted"]
    jobs = client.get(f"/reviews/{rid}/jobs").json()
    assert [j["kind"] for j in jobs][:3] == ["extract", "ai_screen", "dedup"]
    activity = client.get(f"/reviews/{rid}/activity").json()
    assert {a["kind"] for a in activity["items"]} >= {"import", "dedup", "review_created", "invited", "joined"}

    # Reviews list, member management, delete import, delete review
    lst = client2.get("/reviews").json()
    assert lst[0]["n_members"] == 2 and lst[0]["my_role"] == "reviewer" and lst[0]["n_records"] == 4
    assert client.patch(f"/reviews/{rid}/members/{bob['id']}", json={"role": "admin"}).status_code == 200
    assert client2.patch(f"/reviews/{rid}", json={"title": "Solar mini-grids in Africa"}).status_code == 200
    assert client.delete(f"/reviews/{rid}/imports/{imp['id']}").json()["deleted"] == 6
    assert client.get(f"/reviews/{rid}/summary").json()["records"] == 0
    assert client2.delete(f"/reviews/{rid}").status_code == 403
    assert client.delete(f"/reviews/{rid}").status_code == 200
    assert client.get(f"/reviews/{rid}").status_code == 404
