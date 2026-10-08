import json
import extraction_schema as es


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


def test_energy_template_matches_extractor():
    import extractor
    fields = es.energy_template()
    assert len(fields) == len(extractor.FIELDS)
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
