"""Many PDFs at once (D-55): each PDF is matched to a study included at title and abstract, by
its DOI, title or file name; nothing is stored until the page sends it to the study chosen."""
import io

import pymupdf

from tests.conftest import register

RIS = """TY  - JOUR
TI  - Microgrids in rural Kenya: a techno-economic review
AU  - Mwangi, C.
PY  - 2021
DO  - 10.1016/j.energy.2021.121108
ER  -

TY  - JOUR
TI  - Solar home systems and household electricity demand in Nigeria
AU  - Okafor, A.
PY  - 2020
DO  - 10.1016/j.enpol.2020.111111
ER  -

TY  - JOUR
TI  - Hospital surgery outcomes in elderly patients of rural clinics
AU  - Smith, J.
PY  - 2018
DO  - 10.1001/jama.2018.1234
ER  -
"""


def _pdf(text: str = "") -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    if text:
        page.insert_textbox(pymupdf.Rect(40, 40, 560, 800), text, fontsize=10)
    return doc.tobytes()


def test_each_pdf_finds_its_study_among_those_included_at_title_and_abstract(client, pdf_bytes):
    register(client, "pdfmatch-owner@example.org", "Owner")
    rid = client.post("/reviews", json={"title": "Bulk PDFs"}).json()["id"]
    r = client.post(f"/reviews/{rid}/imports", data={"source_db": "Scopus"},
                    files={"files": ("s.ris", io.BytesIO(RIS.encode()), "application/x-research-info-systems")})
    assert r.status_code == 201, r.text
    recs = {x["title"][:5]: x["id"] for x in client.get(f"/reviews/{rid}/records?stage=ta&view=all").json()["items"]}
    kenya, nigeria, hospital = recs["Micro"], recs["Solar"], recs["Hospi"]
    for rec, decision in ((kenya, "include"), (nigeria, "include"), (hospital, "exclude")):
        assert client.post(f"/reviews/{rid}/records/{rec}/decision", json={"stage": "ta", "decision": decision}).status_code == 200

    def match(data: bytes, name: str = "paper.pdf"):
        return client.post(f"/reviews/{rid}/pdfs/match", files={"file": (name, data, "application/pdf")})

    r = match(_pdf("Microgrids in rural Kenya: a techno-economic review\nhttps://doi.org/10.1016/j.energy.2021.121108"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["record_id"], body["how"], body["filename"]) == (kenya, "doi", "paper.pdf")
    assert body["candidates"][0]["id"] == kenya and body["candidates"][0]["has_pdf"] is False
    assert match(_pdf(), "Okafor - 2020 - Solar home systems and household electricity.pdf").json()["record_id"] == nigeria

    # A study excluded at title and abstract needs no PDF: it is never offered.
    r = match(_pdf("Hospital surgery outcomes in elderly patients of rural clinics\nhttps://doi.org/10.1001/jama.2018.1234"))
    assert r.json()["record_id"] is None and hospital not in [c["id"] for c in r.json()["candidates"]]

    # Nothing is stored by the match; the PDF then goes to the study chosen, which says it has one.
    assert client.get(f"/reviews/{rid}/records/{kenya}?stage=ft").json()["has_pdf"] is False
    assert client.post(f"/reviews/{rid}/records/{kenya}/pdf", files={"file": ("paper.pdf", pdf_bytes, "application/pdf")}).status_code == 200
    again = match(_pdf("Microgrids in rural Kenya: a techno-economic review\nhttps://doi.org/10.1016/j.energy.2021.121108"))
    assert again.json()["candidates"][0]["has_pdf"] is True

    assert match(b"not a pdf", "notes.txt").status_code == 400
