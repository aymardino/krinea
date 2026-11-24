"""Exports read as they stream (krinea_core.biblio.iter_file, D-56): the same records as the
whole file read at once, whatever the encoding or the line endings, and only the columns read
kept from a table."""
import io
import tempfile

import pytest

from krinea_core import biblio

RIS = ("TY  - JOUR\nTI  - Électrification rurale au Sénégal\nAU  - Diallo, B.\nPY  - 2019\n"
       "AB  - Mini-grids for remote\n  villages.\nCR  - " + "A cited reference; " * 200 + "\nER  - \n\n"
       "TY  - JOUR\nTI  - Solar home systems\nDO  - 10.1016/j.enpol.2020.111111\nER  - \n")
NBIB = "PMID- 1\nTI  - First paper\nAB  - About grids.\n\nPMID- 2\nTI  - Second paper\n"


def _titles(records):
    return [r["title"] for r in records]


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "cp1252", "utf-16"])
@pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"])
def test_a_ris_file_reads_the_same_streamed_or_whole(encoding, newline):
    data = RIS.replace("\n", newline).encode(encoding)
    whole = biblio.parse_ris(biblio.decode_bytes(data))
    streamed = list(biblio.iter_file("export.ris", io.BytesIO(data)))
    assert _titles(streamed) == _titles(whole) == ["Électrification rurale au Sénégal", "Solar home systems"]
    assert streamed[0]["abstract"] == "Mini-grids for remote villages."
    assert streamed[1]["doi"] == "10.1016/j.enpol.2020.111111" and streamed[0]["_format"] == "ris"
    assert biblio.parse_file("export.ris", data)[0] == streamed[0]


def test_records_of_a_pubmed_file_part_at_blank_lines_when_streamed():
    with tempfile.SpooledTemporaryFile(max_size=10) as f:        # as an upload leaves it, on disk
        f.write(NBIB.replace("\n", "\r\n").encode())
        f.seek(0)
        records = list(biblio.iter_file("pubmed.txt", f))
    assert _titles(records) == ["First paper", "Second paper"] and records[0]["_format"] == "nbib"


def test_a_table_keeps_only_the_columns_read():
    csv = "Title;Authors;References;DOI\n" + "".join(
        f'"Paper {i}";"Author {i}";"{"Cited work; " * 300}";"10.1/x{i}"\n'.replace("10.1/x", "10.1000/x") for i in range(3))
    records = list(biblio.iter_file("scopus.csv", csv.encode()))
    assert _titles(records) == ["Paper 0", "Paper 1", "Paper 2"]
    assert records[2]["doi"] == "10.1000/x2" and records[0]["_format"] == "table"
    # A table with its header only holds no record; one with no title or DOI column says what it has.
    assert list(biblio.iter_file("empty.csv", b"Title,DOI\n")) == []
    with pytest.raises(ValueError, match="Columns seen: Name of the thing"):
        list(biblio.iter_file("odd.csv", b"Name of the thing,Count\nx,1\n"))


def test_the_format_of_an_export_without_records():
    assert biblio.file_format("empty.ris", b"") == "ris"
    assert biblio.file_format("x.txt", b"PMID- 1\nTI  - One\n") == "nbib"
