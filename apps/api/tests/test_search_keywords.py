"""Keywords of one search (imported file), the files a record was found in, and labels."""
from tests.conftest import register
from tests.test_dedup_choice import PUBMED, SCOPUS, _import, _records


def test_search_keywords_and_found_in(client, client2):
    register(client, "kw-owner@example.org", "Owner")
    register(client2, "kw-reviewer@example.org", "Reviewer")
    rid = client.post("/reviews", json={"title": "Sub-questions"}).json()["id"]
    file_a = _import(client, rid, "scopus.ris", SCOPUS, "Scopus")
    file_b = _import(client, rid, "pubmed.ris", PUBMED, "PubMed")
    client.post(f"/reviews/{rid}/dedup/run", json={"auto_threshold": 95, "review_threshold": 85})

    # The Nigerian study was found by both searches: the kept record says so.
    found = {r["year"]: r["found_in"] for r in _records(client, rid) if r["year"] == "2020"}
    assert sorted(found["2020"]) == sorted([file_a, file_b])

    # Only administrators set a search's keywords; they are cleaned and stored per import.
    r = client.put(f"/reviews/{rid}/imports/{file_b}/keywords",
                   json={"include": [" LCOE ", "lcoe", "mini-grid*", ""], "exclude": ["nuclear"]})
    assert r.status_code == 200 and r.json() == {"include": ["LCOE", "mini-grid*"], "exclude": ["nuclear"]}
    review = client.get(f"/reviews/{rid}").json()
    assert review["criteria"]["search_keywords"] == {file_b: {"include": ["LCOE", "mini-grid*"], "exclude": ["nuclear"]}}
    assert client.put(f"/reviews/{rid}/imports/not-an-import/keywords", json={"include": ["x"]}).status_code == 404
    token = client.post(f"/reviews/{rid}/invitations", json={"email": "kw-reviewer@example.org", "role": "reviewer"}).json()
    client2.post("/reviews/invitations/accept", json={"token": token["accept_url"].rsplit("/", 1)[-1]})
    assert client2.put(f"/reviews/{rid}/imports/{file_b}/keywords", json={"include": ["x"]}).status_code == 403

    # Counts: the review's keywords over the whole review, the search's over its own records.
    client.patch(f"/reviews/{rid}", json={"criteria": {"highlight_include": ["Tanzania"]}})
    kw = client.get(f"/reviews/{rid}/keywords?import_id={file_b}").json()
    assert kw["include"] == [{"keyword": "Tanzania", "n": 2}]
    assert {k["keyword"]: k["n"] for k in kw["search"]["include"]} == {"LCOE": 1, "mini-grid*": 1}
    assert "search" not in client.get(f"/reviews/{rid}/keywords").json()

    # Clearing both lists removes the entry; deleting an import removes its keywords.
    client.put(f"/reviews/{rid}/imports/{file_a}/keywords", json={"include": ["Tanzania"]})
    client.put(f"/reviews/{rid}/imports/{file_b}/keywords", json={"include": [], "exclude": []})
    assert list(client.get(f"/reviews/{rid}").json()["criteria"]["search_keywords"]) == [file_a]
    assert client.delete(f"/reviews/{rid}/imports/{file_a}").status_code == 200
    assert client.get(f"/reviews/{rid}").json()["criteria"]["search_keywords"] == {}


def test_label_filter_is_exact(client):
    register(client, "kw-labels@example.org", "Labels")
    rid = client.post("/reviews", json={"title": "Labels"}).json()["id"]
    _import(client, rid, "scopus.ris", SCOPUS, "Scopus")
    a, b = [r["id"] for r in _records(client, rid)]
    client.patch(f"/reviews/{rid}/records/{a}", json={"labels": "SQ1, costs"})
    client.patch(f"/reviews/{rid}/records/{b}", json={"labels": "SQ10"})
    assert [r["id"] for r in _records(client, rid, label="SQ1")] == [a]
    assert [r["id"] for r in _records(client, rid, label="sq10")] == [b]
    assert {x["label"] for x in client.get(f"/reviews/{rid}/labels").json()} == {"SQ1", "costs", "SQ10"}
