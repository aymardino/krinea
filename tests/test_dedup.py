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


def test_source_priority_decides_the_keeper():
    group = [0, 1, 2, 8]
    assert dedup.source_rank(RECS[1], ["PubMed", "web of science"]) == 1
    assert dedup.source_rank(RECS[3], ["PubMed"]) == 1                 # no source: after every listed one
    # A merged record ranks by its own source (listed first), not by the ones it absorbed.
    assert dedup.source_rank({"source_db": "Scopus; PubMed"}, ["pubmed", "scopus"]) == 1
    assert dedup.source_rank({"source_db": "Scopus; PubMed", "origin_source": "PubMed"}, ["pubmed"]) == 0
    # The preferred source wins over completeness; completeness decides within a source.
    assert dedup.choose_keeper(RECS, group, ["Web of Science", "Scopus"]) == 1
    assert dedup.choose_keeper(RECS, group, ["pubmed"]) == 2
    assert dedup.choose_keeper(RECS, group, ["Embase"]) == 0             # nobody listed: most complete
    assert dedup.choose_keeper(RECS, group, []) == dedup.choose_keeper(RECS, group) == 0
    # A file (search) order comes first, then the source order, then completeness.
    recs = [dict(r, import_id=f"imp{i}") for i, r in enumerate(RECS)]
    assert dedup.choose_keeper(recs, group, ["Scopus"], ["imp2", "imp1"]) == 2
    assert dedup.choose_keeper(recs, group, ["PubMed"], ["imp9"]) == 2            # unlisted files: the source order decides
    assert dedup.file_rank(recs[1], ["imp2", "imp1"]) == 1 and dedup.file_rank(recs[0], ["imp2"]) == 1
    merged = dedup.merge_records(RECS, 2, group)
    assert merged["year"] == "2020" and merged["doi"] == "10.1016/j.esd.2019.07.009"   # kept values win, gaps filled
    assert merged["source_db"] == "PubMed; Scopus; Web of Science"                       # the kept record's source first


def test_thresholds_can_be_tightened():
    pairs = dedup.find_duplicates(RECS, auto_threshold=100, review_threshold=99)
    assert _pair(pairs, 3, 4) is None
    assert _pair(pairs, 0, 1) is not None


def test_fallback_similarity_matches_rapidfuzz_scale():
    assert dedup.similarity("abc", "abc") == 100
    assert dedup.similarity("abc", "xyz") < 50


def test_progress_is_reported_while_titles_are_compared():
    seen = []
    pairs = dedup.find_duplicates(RECS, on_progress=lambda done, total: seen.append((done, total)))
    assert pairs == dedup.find_duplicates(RECS)
    assert seen[0] == (0, len(RECS)) and seen[-1] == (len(RECS), len(RECS))
    assert [d for d, _ in seen] == sorted(d for d, _ in seen)
    many = [{"title": f"A study of rural electrification number {i} in Kenya", "year": "2020"} for i in range(1000)]
    calls = []
    dedup.find_duplicates(many, on_progress=lambda done, total: calls.append(done))
    assert len(calls) <= 102                     # about a hundred, whatever the size
