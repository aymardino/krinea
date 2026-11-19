"""Filtering the screening queue by several highlight keywords, and keyword lists pasted
from a spreadsheet or a document."""
from krinea_core import screening as core
from tests.conftest import register
from tests.test_dedup_choice import _import, _records

RIS = """TY  - JOUR
AU  - Beacher, M.
TI  - Health damage mitigation in generation expansion planning via surrogate neural networks
PY  - 2026
ER  -

TY  - JOUR
AU  - Okoye, C.
TI  - Machine learning-enabled large-scale capacity expansion planning under uncertainty
PY  - 2027
ER  -

TY  - JOUR
AU  - Mensah, K.
TI  - Capacity expansion of rural mini-grids and their electrification costs
PY  - 2022
ER  -

TY  - JOUR
AU  - Tesfaye, H.
TI  - Learning a non-linear surrogate model for multistage transmission planning
PY  - 2027
ER  -
"""


def _titles(client, rid, query):
    return sorted(r["title"].split()[0] for r in _records(client, rid, **query))


def test_queue_filtered_by_several_keywords(client):
    register(client, "kw-filter@example.org", "Owner")
    rid = client.post("/reviews", json={"title": "Keyword filter"}).json()["id"]
    _import(client, rid, "a.ris", RIS, "Scopus")

    # One keyword: whole words, as the counts in the rail count them.
    assert _titles(client, rid, {"kw": "expansion planning"}) == ["Health", "Machine"]
    assert _titles(client, rid, {"kw": "electrif*"}) == ["Capacity"]
    assert _titles(client, rid, {"kw": "plan"}) == []

    # Several: all of them by default, at least one on request.
    both = "kw=capacity expansion&kw=expansion planning"
    assert _titles(client, rid, {"kw": "capacity expansion", "kw_mode": "all"}) == ["Capacity", "Machine"]
    assert sorted(r["title"].split()[0] for r in client.get(
        f"/reviews/{rid}/records?stage=ta&view=all&{both}").json()["items"]) == ["Machine"]
    assert sorted(r["title"].split()[0] for r in client.get(
        f"/reviews/{rid}/records?stage=ta&view=all&{both}&kw_mode=any").json()["items"]) == ["Capacity", "Health", "Machine"]

    # No keyword, or only blanks: the whole queue.
    assert len(_records(client, rid)) == 4
    assert len(client.get(f"/reviews/{rid}/records?stage=ta&view=all&kw=%20").json()["items"]) == 4


def test_pasted_keyword_lists_are_split():
    assert core.parse_keywords(["capacity expansion\texpansion planning", "surrogate\r\nneural network", "Surrogate"]) \
        == ["capacity expansion", "expansion planning", "surrogate", "neural network"]
    assert core.parse_keywords("a\tb\nc, d; e") == ["a", "b", "c", "d", "e"]
