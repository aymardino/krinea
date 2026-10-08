import biblio

RIS = """﻿TY  - JOUR
AU  - Moner-Girona, M.
AU  - Bódis, K.
TI  - Decentralized rural electrification in Kenya: Speeding up universal energy access
JO  - Energy for Sustainable Development
PY  - 2019///
VL  - 52
SP  - 128
EP  - 146
DO  - https://doi.org/10.1016/J.ESD.2019.07.009
AB  - This paper assesses the cost of
  electrification options in Kenya.
KW  - Kenya
KW  - Mini-grids
DB  - Scopus
ER  - 

TY  - CONF
T1  - Techno-economic assessment of a hybrid PV-diesel mini-grid in Nigeria
A1  - Okoye, C.
Y1  - 2020/06/01
UR  - https://doi.org/10.1109/ICEPT.2020.123456
N2  - Abstract text here.
ER  - 
"""

BIB = r"""
@comment{this is ignored}
@article{moner2019,
  title = {Decentralized rural {Electrification} in {Kenya}: Speeding up universal energy access},
  author = {Moner-Girona, Magda and B{\'o}dis, K{\'a}roly and Sz{\H{o}}ke, A.},
  journal = {Energy for Sustainable Development},
  year = 2019,
  volume = {52},
  pages = {128--146},
  doi = {10.1016/j.esd.2019.07.009},
  abstract = "This paper assesses {cost} \& access.",
  keywords = {Kenya, Mini-grids}
}
@inproceedings(okoye2020, title={Hybrid PV-diesel mini-grid in Nigeria}, author={Okoye, Chukwuma}, booktitle={Proc. ICEPT}, year={2020})
"""

NBIB = """PMID- 31234567
OWN - NLM
DP  - 2019 Jul 15
TI  - Decentralized rural electrification in Kenya: speeding up universal
      energy access.
AB  - This paper assesses the cost of electrification options.
FAU - Moner-Girona, Magda
AU  - Moner-Girona M
FAU - Bodis, Karoly
AU  - Bodis K
JT  - Energy for sustainable development
VI  - 52
PG  - 128-46
LID - 10.1016/j.esd.2019.07.009 [doi]
MH  - Kenya
OT  - Mini-grids

PMID- 31234568
DP  - 2020
TI  - Second record.
AID - 10.1000/xyz123 [doi]
"""

WOS = """FN Clarivate Analytics Web of Science
VR 1.0
PT J
AU Moner-Girona, M
   Bodis, K
AF Moner-Girona, Magda
   Bodis, Karoly
TI Decentralized rural electrification in Kenya: Speeding up universal
   energy access
SO ENERGY FOR SUSTAINABLE DEVELOPMENT
DE Kenya; Mini-grids
AB This paper assesses the cost.
PY 2019
VL 52
BP 128
EP 146
DI 10.1016/j.esd.2019.07.009
UT WOS:000123456700001
ER

EF
"""

CSV = ("Authors,Author full names,Title,Year,Source title,Volume,Page start,Page end,DOI,"
       "Abstract,Author Keywords,Document Type,EID\n"
       '"Moner-Girona M.; Bódis K.","Moner-Girona, Magda (1); Bódis, Károly (2)",'
       '"Decentralized rural electrification in Kenya",2019,Energy for Sustainable Development,'
       '52,128,146,10.1016/j.esd.2019.07.009,"This paper assesses the cost.",'
       '"Kenya; Mini-grids",Article,2-s2.0-85070\n')

TSV = ("PT\tAU\tTI\tSO\tDE\tAB\tPY\tDI\n"
       "J\tSmith, J; Doe, A\tA tab separated record\tSome Journal\tsolar; wind\t"
       "An abstract.\t2021\t10.5555/tsv.1\n")


def test_clean_doi():
    assert biblio.clean_doi("https://doi.org/10.1016/J.ESD.2019.07.009.") == "10.1016/j.esd.2019.07.009"
    assert biblio.clean_doi("doi: 10.1016/S0140-6736(20)30183-5)") == "10.1016/s0140-6736(20)30183-5"
    assert biblio.clean_doi("no doi here") == ""
    assert biblio.clean_year("2019///") == "2019"
    assert biblio.clean_year("Jul 15 2019") == "2019"
    assert biblio.clean_year("vol 52") == ""


def test_parse_ris():
    recs = biblio.parse_ris(RIS)
    assert len(recs) == 2
    r = recs[0]
    assert r["title"].startswith("Decentralized rural electrification in Kenya")
    assert r["doi"] == "10.1016/j.esd.2019.07.009"
    assert r["year"] == "2019"
    assert r["pages"] == "128-146"
    assert r["authors"] == "Moner-Girona, M.; Bódis, K."
    assert r["keywords"] == "Kenya; Mini-grids"
    assert r["abstract"] == "This paper assesses the cost of electrification options in Kenya."
    assert r["source_db"] == "Scopus"
    r2 = recs[1]
    assert r2["doi"] == "10.1109/icept.2020.123456"   # pulled out of the URL
    assert r2["year"] == "2020"
    assert r2["type"] == "CONF"
    assert r2["authors"] == "Okoye, C."


def test_parse_bibtex():
    recs = biblio.parse_bibtex(BIB)
    assert len(recs) == 2
    r = recs[0]
    assert r["title"] == "Decentralized rural Electrification in Kenya: Speeding up universal energy access"
    assert r["authors"] == "Moner-Girona, Magda; Bódis, Károly; Szőke, A."
    assert r["pages"] == "128-146"
    assert r["year"] == "2019"
    assert r["abstract"] == "This paper assesses cost & access."
    assert r["keywords"] == "Kenya; Mini-grids"
    assert r["type"] == "article"
    assert r["raw_id"] == "moner2019"
    r2 = recs[1]
    assert r2["journal"] == "Proc. ICEPT"
    assert r2["type"] == "inproceedings"


def test_delatex():
    assert biblio.delatex(r"Caf\'e {\"u}ber \c{c} \v{s} \o{} \&") == "Café über ç š ø &"
    assert biblio.delatex(r"\textit{Energy} -- Africa") == "Energy – Africa"


def test_parse_nbib():
    recs = biblio.parse_nbib(NBIB)
    assert len(recs) == 2
    r = recs[0]
    assert r["pmid"] == "31234567"
    assert r["doi"] == "10.1016/j.esd.2019.07.009"
    assert r["title"] == "Decentralized rural electrification in Kenya: speeding up universal energy access."
    assert r["authors"] == "Moner-Girona, Magda; Bodis, Karoly"
    assert r["keywords"] == "Kenya; Mini-grids"
    assert r["year"] == "2019"
    assert r["source_db"] == "PubMed"
    assert r["url"] == "https://pubmed.ncbi.nlm.nih.gov/31234567/"
    assert recs[1]["doi"] == "10.1000/xyz123"


def test_parse_wos():
    recs = biblio.parse_wos(WOS)
    assert len(recs) == 1
    r = recs[0]
    assert r["authors"] == "Moner-Girona, Magda; Bodis, Karoly"
    assert r["title"] == "Decentralized rural electrification in Kenya: Speeding up universal energy access"
    assert r["pages"] == "128-146"
    assert r["doi"] == "10.1016/j.esd.2019.07.009"
    assert r["raw_id"] == "WOS:000123456700001"
    assert r["source_db"] == "Web of Science"


def test_parse_csv_and_tsv():
    recs = biblio.parse_table(CSV.encode("utf-8"), "scopus.csv")
    assert len(recs) == 1
    r = recs[0]
    assert r["authors"] == "Moner-Girona M.; Bódis K."
    assert r["pages"] == "128-146"
    assert r["doi"] == "10.1016/j.esd.2019.07.009"
    assert r["keywords"] == "Kenya; Mini-grids"
    assert r["type"] == "Article"
    assert r["raw_id"] == "2-s2.0-85070"
    recs = biblio.parse_table(TSV.encode("utf-8"), "savedrecs.txt")
    assert recs[0]["title"] == "A tab separated record"
    assert recs[0]["doi"] == "10.5555/tsv.1"
    assert recs[0]["keywords"] == "solar; wind"


def test_detect_format_and_parse_file():
    assert biblio.detect_format("x.ris") == "ris"
    assert biblio.detect_format("x.bib") == "bibtex"
    assert biblio.detect_format("x.csv") == "table"
    assert biblio.detect_format("x.txt", RIS) == "ris"
    assert biblio.detect_format("x.txt", NBIB) == "nbib"
    assert biblio.detect_format("x.txt", WOS) == "wos"
    assert biblio.detect_format("x.txt", BIB) == "bibtex"
    assert biblio.detect_format("x.txt", TSV) == "table"
    recs = biblio.parse_file("export.txt", NBIB.encode("utf-8"))
    assert recs[0]["_format"] == "nbib"
    recs = biblio.parse_file("export.ris", RIS.encode("utf-8"))
    assert len(recs) == 2


def test_export_roundtrip():
    recs = biblio.parse_ris(RIS)
    ris = biblio.to_ris(recs)
    back = biblio.parse_ris(ris)
    assert [r["title"] for r in back] == [r["title"] for r in recs]
    assert back[0]["authors"] == recs[0]["authors"]
    assert back[0]["doi"] == recs[0]["doi"]
    assert back[1]["type"] == "CONF"
    csv_text = biblio.to_csv(recs, extra_fields=["status"])
    assert csv_text.splitlines()[0].endswith(",status")
    assert "Moner-Girona" in csv_text
