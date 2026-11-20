"""Full-text screening and reports not retrieved (D-46): flagged not retrievable, a report
leaves the records to screen and the counts of what is left, and has a view of its own, apart
from the records whose PDF is still to find."""
import io

from tests.conftest import register

RIS = "\n".join(f"TY  - JOUR\nAU  - Author {i}\nTI  - Mini-grid tariff study number {i}\nPY  - 2021\nER  - \n"
                for i in range(1, 4))


def _ids(client, rid, view):
    return [r["id"] for r in client.get(f"/reviews/{rid}/records", params={"stage": "ft", "view": view}).json()["items"]]


def test_reports_not_retrieved_leave_the_records_to_screen(client):
    register(client, "ft-queue@example.org", "Owner")
    rid = client.post("/reviews", json={"title": "Full texts"}).json()["id"]
    r = client.post(f"/reviews/{rid}/imports", data={"source_db": "Scopus"},
                    files={"files": ("s.ris", io.BytesIO(RIS.encode()), "application/x-research-info-systems")})
    assert r.status_code == 201, r.text
    a, b, c = [x["id"] for x in client.get(f"/reviews/{rid}/records", params={"stage": "ta", "view": "all"}).json()["items"]]
    for rec in (a, b, c):
        assert client.post(f"/reviews/{rid}/records/{rec}/decision", json={"stage": "ta", "decision": "include"}).status_code == 200
    assert client.post(f"/reviews/{rid}/records/{b}/pdf/not-retrieved").json()["pdf_status"] == "not_retrieved"

    assert _ids(client, rid, "todo") == [a, c]
    assert _ids(client, rid, "not_retrieved") == [b]
    assert _ids(client, rid, "no_pdf") == [a, c]                # a PDF still to find
    assert _ids(client, rid, "all") == [a, b, c]
    ft = client.get(f"/reviews/{rid}/summary").json()["stages"]["ft"]
    assert (ft["pool"], ft["my_left"], ft["not_retrieved"]) == (2, 2, 1)
    client.post(f"/reviews/{rid}/records/{a}/decision", json={"stage": "ft", "decision": "include"})
    assert client.get(f"/reviews/{rid}/summary").json()["stages"]["ft"]["my_left"] == 1

    # Unflagged, it is to screen again; PRISMA counts it as assessed.
    client.post(f"/reviews/{rid}/records/{b}/pdf/not-retrieved")
    assert _ids(client, rid, "todo") == [b, c]
    prisma = client.get(f"/reviews/{rid}/prisma").json()
    assert (prisma["sought"], prisma["not_retrieved"], prisma["assessed"]) == (3, 0, 3)
