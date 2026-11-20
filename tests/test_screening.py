import screening


def test_consensus():
    c = screening.consensus
    assert c({}) == "pending"
    assert c({"a": "include"}) == "include"
    assert c({"a": "include"}, required=2) == "pending"
    assert c({"a": "include", "b": "include"}, required=2) == "include"
    assert c({"a": "include", "b": "exclude"}, required=2) == "conflict"
    assert c({"a": "include", "b": "maybe"}, required=2) == "maybe"
    assert c({"a": "include", "b": "exclude", "consensus": "include"}, required=2) == "include"
    assert c({"a": "include", "b": "exclude"}, required=1) == "conflict"


def test_highlight():
    out = screening.highlight("Solar mini-grids in Kenya & Uganda", ["mini*", "Kenya"], ["Uganda"])
    assert "<mark" in out
    assert "&amp;" in out                       # escaped
    assert out.count("<mark") == 3
    assert "#CDE8D2" in out and "#F4D3D3" in out
    assert screening.highlight("plain", [], []) == "plain"
    assert screening.parse_keywords("solar, mini-grid; Africa\nsolar") == ["solar", "mini-grid", "Africa"]


def test_criteria_defaults_and_prompt():
    c = screening.criteria_with_defaults({"question": "Q?", "exclusion_reasons": [],
                                          "required_reviewers": "2"})
    assert c["required_reviewers"] == 2
    assert c["exclusion_reasons"] == screening.DEFAULT_EXCLUSION_REASONS
    rec = {"title": "T", "abstract": "A", "authors": "X", "year": "2020"}
    p = screening.build_screening_prompt(c, rec)
    assert "Q?" in p and "STUDY TEXT:" in p and "Title: T" in p and "Abstract: A" in p
    p2 = screening.build_screening_prompt(c, rec, stage="ft", full_text="BODY")
    assert "FULL TEXT:\nBODY" in p2
    assert "SEARCH-SPECIFIC" not in p


def test_a_search_brings_its_own_sub_question_and_criteria():
    rec = {"title": "T", "abstract": "A"}
    one = [{"name": "query3.ris", "question": "Do mini-grids lower tariffs?", "inclusion": "Tariff data", "exclusion": ""}]
    p = screening.build_screening_prompt({"inclusion": "Africa"}, rec, searches=one)
    head = p.split("STUDY TEXT:")[0]                       # in the cached part, before the study
    assert 'Search "query3.ris":' in head and "Sub-question: Do mini-grids lower tariffs?" in head
    assert "Inclusion criteria: Tariff data" in head and "Exclusion criteria:" not in head.split("SEARCH-SPECIFIC")[1]
    assert "together with the review's criteria" in head
    two = one + [{"name": "query5.ris", "inclusion": "Storage costs"}]
    assert "at least one of these searches" in screening.build_screening_prompt({}, rec, searches=two)
    assert "SEARCH-SPECIFIC" not in screening.build_screening_prompt({}, rec, searches=[{"name": "q", "question": " "}])


def test_parse_suggestion():
    s = screening.parse_suggestion('{"decision": "Exclude", "reason": "Language", "confidence": 1.7}')
    assert s == {"decision": "exclude", "reason": "Language", "rationale": "", "confidence": 1.0}
    assert screening.parse_suggestion("not json")["decision"] == "maybe"
    assert screening.parse_suggestion({"decision": "weird"})["decision"] == "maybe"
