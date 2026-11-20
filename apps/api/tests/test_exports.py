"""Exports of each stage (decision D-39): the records of title/abstract or full-text screening
and the extraction table, filtered by decision, exclusion reason, PDF, imported file and
label, as RIS, CSV or Excel; a blind reviewer only gets their own decisions and reasons."""
import csv
import io

from openpyxl import load_workbook

from krinea_api.routers.exports import SCREENING_COLUMNS
from tests.conftest import register

SCOPUS = """TY  - JOUR
AU  - Moner-Girona, M.
TI  - Solar mini-grids for rural electrification in Kenya
JO  - Energy for Sustainable Development
PY  - 2019
DO  - 10.1016/j.esd.2019.07.009
AB  - Mini-grids in Kenya, HOMER modelling, LCOE results.
ER  -

TY  - JOUR
AU  - Okoye, C.
TI  - Optimal sizing of a hybrid mini-grid for a village in Nigeria
PY  - 2020
DO  - 10.1016/j.renene.2020.01.001
AB  - Hybrid mini-grid optimisation, LCOE 0.31 USD/kWh.
ER  -

TY  - JOUR
AU  - Smith, J.
TI  - Grid extension policy in Europe: a historical review
PY  - 2018
DO  - 10.1016/j.enpol.2018.02.002
AB  - A review of grid extension in Europe.
ER  -

TY  - JOUR
AU  - Rojas, P.
TI  - Wind farms and local acceptance in Chile
PY  - 2022
DO  - 10.1016/j.enpol.2022.05.005
ER  -
"""

PUBMED = """TY  - JOUR
AU  - Moner-Girona M.
TI  - Solar mini-grids for rural electrification in Kenya
PY  - 2019
DO  - 10.1016/j.esd.2019.07.009
ER  -

TY  - JOUR
AU  - Mwakitalima, I.
TI  - Levelised cost of electricity of solar mini-grids in Tanzania
PY  - 2021
DO  - 10.1016/j.energy.2021.03.003
AB  - LCOE data from 30 mini-grids in Tanzania.
ER  -
"""
POPULATION, OUTCOME = "Wrong population / setting", "Wrong outcome"


def _import(client, rid, name, text, source):
    r = client.post(f"/reviews/{rid}/imports", data={"source_db": source},
                    files={"files": (name, io.BytesIO(text.encode()), "application/x-research-info-systems")})
    assert r.status_code == 201, r.text
    return r.json()[0]["id"]


def _decide(client, rid, rec, stage, decision, reason=""):
    r = client.post(f"/reviews/{rid}/records/{rec}/decision", json={"stage": stage, "decision": decision, "reason": reason})
    assert r.status_code == 200, r.text


def _rows(client, rid, **params) -> list[dict]:
    r = client.get(f"/reviews/{rid}/export/screening.csv", params=params)
    assert r.status_code == 200, r.text
    return list(csv.DictReader(io.StringIO(r.text)))


def _ids(client, rid, **params) -> set[int]:
    ids = {int(row["id"]) for row in _rows(client, rid, **params)}
    stage = params.get("stage", "ta")
    assert client.get(f"/reviews/{rid}/export/count", params={"stage": stage, **params}).json()["n"] == len(ids)
    return ids


def test_each_stage_exports_with_its_filters(client):
    register(client, "exports-owner@example.org", "Owner")
    rid = client.post("/reviews", json={"title": "Exports"}).json()["id"]
    scopus = _import(client, rid, "scopus.ris", SCOPUS, "Scopus")
    pubmed = _import(client, rid, "pubmed.ris", PUBMED, "PubMed")
    assert client.post(f"/reviews/{rid}/dedup/run", json={"auto_threshold": 95, "review_threshold": 85}).status_code == 200
    recs = {r["title"].split(" in ")[-1].split(":")[0]: r["id"]
            for r in client.get(f"/reviews/{rid}/records", params={"stage": "ta", "view": "all"}).json()["items"]}
    kenya, nigeria, europe, chile, tanzania = (recs[k] for k in ("Kenya", "Nigeria", "Europe", "Chile", "Tanzania"))

    for rec in (kenya, nigeria, tanzania):
        _decide(client, rid, rec, "ta", "include")
    _decide(client, rid, europe, "ta", "exclude", POPULATION)
    _decide(client, rid, chile, "ta", "exclude")
    client.patch(f"/reviews/{rid}/records/{nigeria}", json={"labels": "SQ1; costs"})
    client.patch(f"/reviews/{rid}/records/{kenya}", json={"labels": "SQ10", "notes": "Check the tables\x07 again"})
    assert client.post(f"/reviews/{rid}/records/{nigeria}/pdf/not-retrieved").status_code == 200
    _decide(client, rid, kenya, "ft", "include")
    _decide(client, rid, nigeria, "ft", "include")
    _decide(client, rid, tanzania, "ft", "exclude", OUTCOME)
    r = client.put(f"/reviews/{rid}/extraction/{kenya}", json={"values": {"authors": "Moner-Girona et al.", "country": "Kenya"}})
    assert r.json()["status"] == "verified"

    # Title and abstract: every unique record, by decision and reason.
    assert _ids(client, rid, stage="ta") == {kenya, nigeria, europe, chile, tanzania}
    assert _ids(client, rid, stage="ta", status="include") == {kenya, nigeria, tanzania}
    assert _ids(client, rid, stage="ta", status="exclude") == {europe, chile}
    assert _ids(client, rid, stage="ta", status="exclude", reason=POPULATION) == {europe}
    assert _ids(client, rid, stage="ta", status="exclude", reason="-") == {chile}         # no reason given
    # A file keeps the records found in it, merged duplicates included; labels match exactly.
    assert _ids(client, rid, stage="ta", import_id=pubmed) == {kenya, tanzania}
    assert _ids(client, rid, stage="ta", import_id=scopus) == {kenya, nigeria, europe, chile}
    assert _ids(client, rid, stage="ta", label="sq1") == {nigeria}
    # Full text: the records kept at title and abstract, by decision and PDF.
    assert _ids(client, rid, stage="ft") == {kenya, nigeria, tanzania}
    assert _ids(client, rid, stage="ft", status="exclude", reason=OUTCOME) == {tanzania}
    assert _ids(client, rid, stage="ft", pdf="not_retrieved") == {nigeria}
    assert _ids(client, rid, stage="ft", pdf="missing") == {kenya, tanzania}
    assert _ids(client, rid, stage="ft", pdf="available") == set()
    # Several values in one filter: any of them; several filters: all of them (D-41).
    assert _ids(client, rid, stage="ta", status=["include", "exclude"]) == {kenya, nigeria, europe, chile, tanzania}
    assert _ids(client, rid, stage="ta", status="exclude", reason=[POPULATION, "-"]) == {europe, chile}
    assert _ids(client, rid, stage="ta", reason=POPULATION) == {europe}     # a reason keeps its exclusions only
    assert _ids(client, rid, stage="ta", import_id=[scopus, pubmed]) == {kenya, nigeria, europe, chile, tanzania}
    assert _ids(client, rid, stage="ta", import_id=pubmed, status=["include", "maybe"]) == {kenya, tanzania}
    assert _ids(client, rid, stage="ta", label=["sq1", "SQ10"]) == {kenya, nigeria}
    assert _ids(client, rid, stage="ft", status="include", pdf=["not_retrieved", "missing"]) == {kenya, nigeria}
    r = client.get(f"/reviews/{rid}/export/screening.csv", params={"stage": "ta", "status": ["exclude", "include"]})
    assert r.headers["content-disposition"].endswith('"title-abstract-included-excluded.csv"')

    rows = {int(r["id"]): r for r in _rows(client, rid, stage="ta")}
    assert list(rows[kenya]) == SCREENING_COLUMNS
    assert rows[kenya]["files"] == "scopus.ris; pubmed.ris" and rows[tanzania]["files"] == "pubmed.ris"
    assert (rows[europe]["ta_status"], rows[europe]["ta_reason"], rows[europe]["ft_status"]) == ("exclude", POPULATION, "")
    assert (rows[tanzania]["ft_status"], rows[tanzania]["ft_reason"]) == ("exclude", OUTCOME)
    assert rows[nigeria]["pdf"] == "not retrieved" and rows[nigeria]["labels"] == "SQ1; costs"

    r = client.get(f"/reviews/{rid}/export/screening.ris", params={"stage": "ta", "status": "include"})
    assert r.text.count("TY  - ") == 3 and r.headers["content-disposition"].endswith('"title-abstract-included.ris"')
    r = client.get(f"/reviews/{rid}/export/screening.xlsx", params={"stage": "ft"})
    sheet = load_workbook(io.BytesIO(r.content))["records"]
    assert [c.value for c in sheet[1]] == SCREENING_COLUMNS and sheet.max_row == 4
    assert "Check the tables again" in {c.value for c in sheet["M"]}      # Excel refuses control characters

    # Extraction: the verified extractions by default, or every included study with its status.
    assert client.get(f"/reviews/{rid}/export/count", params={"stage": "extract"}).json()["n"] == 1
    assert client.get(f"/reviews/{rid}/export/count", params={"stage": "extract", "status": "all"}).json()["n"] == 2
    verified = list(csv.DictReader(io.StringIO(client.get(f"/reviews/{rid}/export/extractions.csv").text)))
    assert [(int(r["record_id"]), r["country"]) for r in verified] == [(kenya, "Kenya")] and "status" not in verified[0]
    every = list(csv.DictReader(io.StringIO(client.get(f"/reviews/{rid}/export/extractions.csv", params={"status": "all"}).text)))
    assert {int(r["record_id"]): r["status"] for r in every} == {kenya: "verified", nigeria: ""}
    assert client.get(f"/reviews/{rid}/export/extractions.csv", params={"status": "all", "label": "SQ1"}).text.count("\n") == 2
    assert client.get(f"/reviews/{rid}/export/count",
                      params={"stage": "extract", "status": "all", "label": ["SQ1", "SQ10"]}).json()["n"] == 2
    book = load_workbook(io.BytesIO(client.get(f"/reviews/{rid}/export/extractions.xlsx", params={"status": "all"}).content))
    assert book.sheetnames == ["values", "quotes", "fields"] and book["values"].max_row == 3
    assert client.get(f"/reviews/{rid}/export/extractions.ris").text.count("TY  - ") == 1

    for path, params in (("screening.csv", {"stage": "extract"}), ("screening.pdf", {}), ("screening.csv", {"status": "x"}),
                         ("screening.csv", {"stage": "ft", "pdf": "x"}), ("extractions.csv", {"status": "x"}),
                         ("count", {"stage": "x"})):
        assert client.get(f"/reviews/{rid}/export/{path}", params=params).status_code == 400, (path, params)


def test_a_blind_reviewer_exports_only_their_own_decisions(client, client2):
    register(client, "exports-blind-owner@example.org", "Alice")
    register(client2, "exports-blind-reviewer@example.org", "Bob")
    rid = client.post("/reviews", json={"title": "Blind exports"}).json()["id"]
    client.patch(f"/reviews/{rid}", json={"settings": {"required_reviewers": 2, "blind": True}})
    token = client.post(f"/reviews/{rid}/invitations", json={"email": "exports-blind-reviewer@example.org",
                                                             "role": "reviewer"}).json()["accept_url"].rsplit("/", 1)[1]
    assert client2.post("/reviews/invitations/accept", json={"token": token}).status_code == 200
    _import(client, rid, "scopus.ris", SCOPUS, "Scopus")
    europe = next(r["id"] for r in client.get(f"/reviews/{rid}/records", params={"stage": "ta", "view": "all"}).json()["items"]
                  if "Europe" in r["title"])
    _decide(client, rid, europe, "ta", "exclude", POPULATION)
    _decide(client2, rid, europe, "ta", "exclude", OUTCOME)
    r = client.post(f"/reviews/{rid}/records/{europe}/decision",
                    json={"stage": "ta", "decision": "exclude", "reason": POPULATION, "as_consensus": True})
    assert r.status_code == 200, r.text

    # Bob sees his own reason; the owner sees the consensus one.
    mine = {int(r["id"]): r for r in _rows(client2, rid, stage="ta")}
    assert (mine[europe]["ta_status"], mine[europe]["ta_reason"]) == ("exclude", OUTCOME)
    assert _ids(client2, rid, stage="ta", status="exclude", reason=POPULATION) == set()
    assert _ids(client, rid, stage="ta", status="exclude", reason=POPULATION) == {europe}
    reviewers = {r["reviewer"] for r in csv.DictReader(io.StringIO(client2.get(f"/reviews/{rid}/export/decisions.csv").text))}
    assert reviewers == {"exports-blind-reviewer@example.org"}
    reviewers = {r["reviewer"] for r in csv.DictReader(io.StringIO(client.get(f"/reviews/{rid}/export/decisions.csv").text))}
    assert reviewers == {"exports-blind-owner@example.org", "exports-blind-reviewer@example.org", "consensus"}
