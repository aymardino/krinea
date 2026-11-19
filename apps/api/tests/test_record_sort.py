"""Record lists in the order a reviewer picks: title (accents, case and leading quotes ignored),
year, first author, journal, or the AI's suggestion. Missing values come last and equal values
keep the import order; the cursor goes on from the last record of the previous page."""
import io

from krinea_api import models
from krinea_api.db import session_factory
from tests.conftest import register

RIS = """TY  - JOUR
AU  - Young, A.
TI  - Zebra mussels and grid reliability
JO  - Energy
PY  - 2019
ER  -

TY  - JOUR
AU  - Adams, B.
AU  - Moreau, C.
TI  - “Électricité” for remote villages
JO  - Applied Energy
PY  - 2023
ER  -

TY  - JOUR
TI  - battery storage for mini-grids: a review
JO  - Zeitschrift für Energiewirtschaft
ER  -

TY  - JOUR
AU  - Mwangi, C.
AU  - Otieno, D.
TI  - Microgrids in Kenya
PY  - 2021
ER  -
"""


def _review(client) -> tuple[str, list[int]]:
    register(client, "sort-owner@example.org", "Owner")
    rid = client.post("/reviews", json={"title": "Orders"}).json()["id"]
    r = client.post(f"/reviews/{rid}/imports", data={"source_db": "Scopus"},
                    files={"files": ("s.ris", io.BytesIO(RIS.encode()), "application/x-research-info-systems")})
    assert r.status_code == 201, r.text
    ids = [x["id"] for x in client.get(f"/reviews/{rid}/records?stage=ta&view=all").json()["items"]]
    assert len(ids) == 4
    return rid, ids


def _order(client, rid, sort, **params):
    query = "&".join(f"{k}={v}" for k, v in {"stage": "ta", "view": "all", "sort": sort, **params}.items())
    r = client.get(f"/reviews/{rid}/records?{query}")
    assert r.status_code == 200, r.text
    return r.json()


def test_lists_come_in_the_order_picked(client):
    rid, (zebra, electricite, battery, kenya) = _review(client)
    ids = lambda sort: [x["id"] for x in _order(client, rid, sort)["items"]]   # noqa: E731
    assert ids("import") == [zebra, electricite, battery, kenya]
    assert ids("title") == [battery, electricite, kenya, zebra]               # “É” files under e
    assert ids("title_desc") == [zebra, kenya, electricite, battery]
    assert ids("year_desc") == [electricite, kenya, zebra, battery]           # no year: last
    assert ids("year") == [zebra, kenya, electricite, battery]
    assert ids("author") == [electricite, kenya, zebra, battery]              # Adams, Mwangi, Young
    assert ids("journal") == [electricite, zebra, battery, kenya]             # no journal: last

    db = session_factory()()
    try:
        for rec_id, decision, confidence in ((zebra, "exclude", 0.9), (kenya, "exclude", 0.6),
                                             (electricite, "include", 0.7)):
            db.add(models.AISuggestion(review_id=rid, record_id=rec_id, stage="ta", decision=decision,
                                       confidence=confidence))
        db.commit()
    finally:
        db.close()
    # include first, then the exclusions the AI is least sure of, then records without a suggestion
    assert ids("ai") == [electricite, kenya, zebra, battery]
    assert client.get(f"/reviews/{rid}/records?sort=shuffle").status_code == 400


def test_the_cursor_follows_the_order(client):
    rid, (zebra, electricite, battery, kenya) = _review(client)
    first = _order(client, rid, "title", limit=2)
    assert [x["id"] for x in first["items"]] == [battery, electricite] and first["total"] == 4
    rest = _order(client, rid, "title", limit=2, cursor=first["next_cursor"])
    assert [x["id"] for x in rest["items"]] == [kenya, zebra] and rest["next_cursor"] is None
