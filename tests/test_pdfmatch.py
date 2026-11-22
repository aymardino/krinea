"""Matching PDFs to records (krinea_core.pdfmatch): by DOI from the metadata, the first page or
the file name, then by title, then by file name, with one clear winner or none."""
import pymupdf
import pytest

from krinea_core import biblio, pdfmatch

RECORDS = [
    {"id": 1, "title": "Microgrids in rural Kenya: a techno-economic review", "doi": "10.1016/j.energy.2021.121108",
     "authors": "Mwangi, C.; Otieno, D.", "year": "2021"},
    {"id": 2, "title": "Solar home systems and household electricity demand in Nigeria", "doi": "10.1016/j.enpol.2020.111111",
     "authors": "Okafor, A.", "year": "2020"},
    {"id": 3, "title": "Least-cost electrification planning for remote villages", "doi": "", "authors": "Diallo, B.", "year": "2019"},
    {"id": 4, "title": "Battery storage for island mini-grids", "doi": "10.3390/en13010001", "authors": "Silva, M.", "year": "2020"},
    {"id": 5, "title": "Battery storage for island mini-grids", "doi": "", "authors": "Silva, M.", "year": "2019"},  # its conference version
]


def _pdf(*pages: str, metadata: dict | None = None) -> bytes:
    doc = pymupdf.open()
    for text in pages or ("",):
        page = doc.new_page()
        if text:
            assert page.insert_textbox(pymupdf.Rect(40, 40, 560, 800), text, fontsize=10) >= 0
    if metadata:
        doc.set_metadata(metadata)
    return doc.tobytes()


def _match(data: bytes, filename: str = "paper.pdf") -> pdfmatch.Match:
    return pdfmatch.match(pdfmatch.read_clues(data, filename), RECORDS)


def test_every_doi_of_a_text_once_in_order():
    text = "doi:10.1016/j.energy.2021.121108. See (https://doi.org/10.3390/EN13010001), and 10.1016/j.energy.2021.121108."
    assert biblio.find_dois(text) == ["10.1016/j.energy.2021.121108", "10.3390/en13010001"]
    assert biblio.find_dois("") == []


def test_the_doi_of_the_first_page_wins_over_those_of_the_references():
    data = _pdf("Solar home systems and household electricity demand in Nigeria\nA. Okafor\n"
                "https://doi.org/10.1016/j.enpol.2020.111111\nAbstract. We survey households.",
                "References\n[1] Mwangi C. Microgrids in rural Kenya. https://doi.org/10.1016/j.energy.2021.121108")
    m = _match(data)
    assert (m.record_id, m.how) == (2, "doi") and m.candidates[0] == (2, 100)


def test_a_doi_in_the_metadata_or_the_file_name():
    assert _match(_pdf("Scanned page", metadata={"subject": "Energies 2020, 13, 1; doi:10.3390/en13010001"})).record_id == 4
    m = _match(_pdf(), "10.1016_j.energy.2021.121108.pdf")
    assert (m.record_id, m.how) == (1, "doi")


def test_a_title_on_the_first_page_with_words_cut_at_line_ends():
    m = _match(_pdf("Least-cost electri-\nfication planning for remote villages\nB. Diallo\nAbstract. We plan grids."))
    assert (m.record_id, m.how) == (3, "title")


def test_a_file_name_as_reference_managers_write_it():
    m = _match(_pdf(), "Okafor - 2020 - Solar home systems and household electricity.pdf")
    assert (m.record_id, m.how) == (2, "filename")


def test_no_clear_winner_no_pick():
    # Two records with the same title: both are offered first, none is picked.
    m = _match(_pdf("Battery storage for island mini-grids\nM. Silva\nAbstract. We size batteries."))
    assert m.record_id is None and m.how == "" and {k for k, _ in m.candidates[:2]} == {4, 5}
    # The DOIs of two records on one first page, and no title to tell them apart.
    m = _match(_pdf("Comment on https://doi.org/10.1016/j.energy.2021.121108 and https://doi.org/10.1016/j.enpol.2020.111111"))
    assert m.record_id is None and {k for k, _ in m.candidates[:2]} == {1, 2}
    # Nothing to go by: a page number and a scanner's file name.
    m = _match(_pdf("12"), "scan001.pdf")
    assert m.record_id is None and len(m.candidates) == pdfmatch.N_CANDIDATES


def test_an_unreadable_pdf():
    with pytest.raises(ValueError):
        pdfmatch.read_clues(b"%PDF-1.4 broken", "x.pdf")
