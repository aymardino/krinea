import dedup

RECS = [
    {"title": "Decentralized rural electrification in Kenya: Speeding up universal energy access",
     "doi": "10.1016/j.esd.2019.07.009", "year": "2019", "authors": "Moner-Girona, M.; Bódis, K.",
     "abstract": "A long abstract " * 20, "keywords": "Kenya", "source_db": "Scopus"},
    {"title": "DECENTRALIZED RURAL ELECTRIFICATION IN KENYA - SPEEDING UP UNIVERSAL ENERGY ACCESS",
     "doi": "", "year": "2019", "authors": "Moner-Girona M.", "abstract": "", "source_db": "Web of Science"},
    {"title": "Decentralised rural electrification in Kenya: speeding up universal energy access",
     "doi": "", "year": "2020", "authors": "Moner-Girona, Magda", "abstract": "", "source_db": "PubMed"},
    {"title": "Techno-economic assessment of a hybrid PV-diesel mini-grid in Nigeria",
     "doi": "10.1109/a", "year": "2020", "authors": "Okoye, C."},
    {"title": "Techno-economic assessment of a hybrid PV-diesel mini-grid in Niger",
     "doi": "10.1109/b", "year": "2020", "authors": "Okoye, C."},
    {"title": "Short", "doi": "", "year": "", "authors": ""},
    {"title": "Short", "doi": "", "year": "", "authors": ""},
    {"title": "Completely different study about hydropower in Ethiopia",
     "doi": "", "year": "2015", "authors": "Abebe, T."},
    {"title": "Same DOI, totally different title written by the database",
     "doi": "https://doi.org/10.1016/J.ESD.2019.07.009", "year": "", "authors": ""},
]


def _pair(pairs, a, b):
    return next((p for p in pairs if (p.a, p.b) == (min(a, b), max(a, b))), None)


def test_normalisation():
    assert dedup.norm_title("Decentralised <i>Rural</i> Électrification: Kenya!") == \
        "decentralised rural electrification kenya"
    assert dedup.first_author_key("Moner-Girona, M.; Bódis, K.") == "moner girona"
    assert dedup.first_author_key("Okoye C.") == "okoye"
    assert dedup.first_author_key("John Smith and Jane Doe") == "smith"
    assert dedup.first_author_key("") == ""


def test_find_duplicates_signals():
    pairs = dedup.find_duplicates(RECS)
    p01 = _pair(pairs, 0, 1)
    assert p01 and p01.certain and p01.score == 100 and "identical title" in p01.reason
    p02 = _pair(pairs, 0, 2)
    assert p02 and p02.certain and p02.score >= 95 and "same first author" in p02.reason
    p34 = _pair(pairs, 3, 4)
    assert p34 and not p34.certain and "different DOI" in p34.reason
    p08 = _pair(pairs, 0, 8)
    assert p08 and p08.certain and p08.reason == "same DOI"
    assert _pair(pairs, 5, 6) is None          # too short to be trusted
    assert all(7 not in (p.a, p.b) for p in pairs)


def test_cluster_keeper_merge():
    pairs = dedup.find_duplicates(RECS)
    certain = [p for p in pairs if p.certain]
    groups = dedup.cluster(certain, len(RECS))
    assert groups == [[0, 1, 2, 8]]
    keeper = dedup.choose_keeper(RECS, groups[0])
    assert keeper == 0
    merged = dedup.merge_records(RECS, keeper, groups[0])
    assert merged["doi"] == "10.1016/j.esd.2019.07.009"
    assert merged["source_db"] == "Scopus; Web of Science; PubMed"
    assert merged["abstract"] == RECS[0]["abstract"]


def test_thresholds_can_be_tightened():
    pairs = dedup.find_duplicates(RECS, auto_threshold=100, review_threshold=99)
    assert _pair(pairs, 3, 4) is None
    assert _pair(pairs, 0, 1) is not None


def test_fallback_similarity_matches_rapidfuzz_scale():
    assert dedup.similarity("abc", "abc") == 100
    assert dedup.similarity("abc", "xyz") < 50
