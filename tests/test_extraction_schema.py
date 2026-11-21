import json

import extraction_schema as es          # the root module name (a shim for krinea_core)


def test_normalise_and_validate():
    f = es.normalise_field({"label": "Study Design!", "kind": "ENUM", "options": "rct | cohort",
                            "required": "yes"})
    assert f["name"] == "study_design" and f["kind"] == "enum"
    assert f["options"] == ["rct", "cohort"] and f["required"] is True
    bad = es.normalise_field({"name": "2nd", "kind": "unknown"})
    assert bad["name"] == "f_2nd" and bad["kind"] == "text"
    errors = es.validate_schema([f, f, es.normalise_field({"name": "x", "kind": "multi"})])
    assert any("twice" in e for e in errors) and any("two options" in e for e in errors)
    assert es.validate_schema([]) == ["The schema has no field."]


def test_fields_of_one_search_apply_to_its_studies_only():
    general = es.normalise_field({"name": "country"})
    tariffs = es.normalise_field({"name": "tariff", "searches": "imp3 | imp5 | imp3"})
    storage = es.normalise_field({"name": "storage", "searches": ["imp1"]})
    assert "searches" not in general and tariffs["searches"] == ["imp3", "imp5"]
    fields = [general, tariffs, storage]
    assert [f["name"] for f in es.fields_for(fields, ["imp5"])] == ["country", "tariff"]
    assert [f["name"] for f in es.fields_for(fields, ["imp1", "imp3"])] == ["country", "tariff", "storage"]
    assert [f["name"] for f in es.fields_for(fields, [])] == ["country"]


def test_a_search_field_is_never_asked_of_the_ai():
    query = es.normalise_field({"name": "query", "kind": "SEARCH", "required": True})
    fields = [es.normalise_field({"name": "country"}), query]
    assert query["kind"] == "search"
    prompt = es.build_prompt(fields, "TEXT")
    assert "- country:" in prompt and "query" not in prompt
    assert es.clean_result(fields, {"country": "Kenya", "query": "x"})[0] == {"country": "Kenya"}
    assert es.check_values(fields, {"country": "Kenya"}, {"country": "Kenya"}) == {}   # filled in by the app


def test_json_csv_roundtrip():
    fields = es.from_json("")
    assert fields == [es.normalise_field(f) for f in es.DEFAULT_SCHEMA]
    js = es.to_json(fields)
    assert es.from_json(js) == fields
    assert es.from_json(json.dumps({"fields": json.loads(js)})) == fields
    csv_text = es.to_csv(fields)
    back = es.from_csv(csv_text)
    assert [f["name"] for f in back] == [f["name"] for f in fields]
    assert back[3]["options"] == fields[3]["options"]


def test_energy_template_matches_data_file():
    import json
    from pathlib import Path
    rows = json.loads((Path(es.__file__).parent / "data" / "energy_template.json").read_text())
    fields = es.energy_template()
    assert len(fields) == len(rows) == 51
    by_name = {f["name"]: f for f in fields}
    assert by_name["approach"]["kind"] == "enum"
    assert by_name["informal_economy"]["options"] == ["yes", "no", "partial"]
    assert by_name["countries"]["kind"] == "list"
    assert es.validate_schema(fields) == []


def test_prompt_and_clean_result():
    fields = es.from_json("")
    prompt = es.build_prompt(fields, "THE TEXT", context="Energy access")
    assert "STUDY TEXT:\nTHE TEXT" in prompt
    assert "- study_design: choose ONE of: experimental | quasi-experimental" in prompt
    assert "Context of the review: Energy access" in prompt
    raw = {"authors": {"value": "Smith et al.", "quote": "J Smith, A Doe"},
           "study_design": {"value": "Modelling", "quote": "we model"},
           "outcomes": ["cost", "emissions"], "year": 2019}
    values, quotes = es.clean_result(fields, raw)
    assert values["authors"] == "Smith et al." and quotes["authors"] == "J Smith, A Doe"
    assert values["study_design"] == "modelling"
    assert values["outcomes"] == "cost, emissions"
    assert values["year"] == "2019" and quotes["year"] == ""
    assert values["country"] == ""


def test_check_values():
    fields = es.from_json("")
    values = {"authors": "", "year": "20x9", "study_design": "rct", "key_result": "Found X",
              "sample_size": "about 40", "funding_declared": "maybe"}
    flags = es.check_values(fields, values, {"key_result": "we found X"})
    assert flags["authors"][0] == "error"
    assert flags["year"][0] == "error"
    assert flags["study_design"][0] == "error"
    assert flags["sample_size"][0] == "warning"
    assert flags["funding_declared"][0] == "error"
    assert "key_result" not in flags
    assert "country" in flags                      # required and empty
    errors, warnings = es.summarise(flags)
    assert errors == 5 and warnings == 1
