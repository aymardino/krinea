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


def test_choice_values_are_written_as_the_options_are():
    fields = [es.normalise_field({"name": "problem", "kind": "multi", "options": "Capacity expansion | Neural network | Other"}),
              es.normalise_field({"name": "family", "kind": "enum", "options": "Long_term planning | Modélisation", "required": True}),
              es.normalise_field({"name": "guarantee", "kind": "enum", "options": "Always feasible | Not reported"}),
              es.normalise_field({"name": "deep", "kind": "yesno"})]
    raw = {"problem": {"value": ["capacity expansion", "Neural-Network", "capacity expansion", "GAN"], "quote": "q"},
           "family": {"value": "long term planning", "quote": "q"}, "guarantee": {"value": "not applicable", "quote": "q"},
           "deep": {"value": "True", "quote": "q"}}
    values, _ = es.clean_result(fields, raw)
    assert values == {"problem": "Capacity expansion, Neural network, GAN", "family": "Long_term planning",
                      "guarantee": "not applicable", "deep": "yes"}
    assert es.canonical(fields, {"family": "MODELISATION"})["family"] == "Modélisation"
    flags = es.check_values(fields, values, {n: "q" for n in values})
    assert flags == {"problem": ("error", "Not allowed: GAN"),
                     "guarantee": ("error", "'not applicable' is not one of: Always feasible, Not reported")}
    assert "copied exactly as written" in es.build_prompt(fields, "TEXT") and "lowercase" not in es.build_prompt(fields, "TEXT")


def test_a_doi_field_and_the_answer_budget():
    doi = es.normalise_field({"name": "link", "kind": "DOI"})
    assert doi["kind"] == "doi" and "link" not in es.build_prompt([doi], "TEXT")
    assert es.answer_tokens([doi]) == 8192                          # never under the former limit
    fifty = [es.normalise_field({"name": f"f{i}"}) for i in range(51)]
    assert es.answer_tokens(fifty) == 1024 + 200 * 51 and es.answer_tokens(fifty * 3) == 16384


def test_a_form_reads_from_a_french_spreadsheet():
    warnings = []
    text = ("Clé;Libellé;Type;Options;Consigne pour l'IA;Obligatoire;Requêtes\n"
            "main_strand;Main strand;choix;modelling | data;Point of the chain;oui;requete 1.ris\n"
            'secondary;Secondary strands;liste;;Other than main_strand;non;"requete 1.ris; requete 3.ris"\n'
            "odd;Odd one;bizarre;;;;\n"
            ";;;;;;\n")
    fields = es.from_csv(text, warnings)
    assert [f["name"] for f in fields] == ["main_strand", "secondary", "odd"]
    assert (fields[0]["kind"], fields[0]["options"], fields[0]["required"]) == ("enum", ["modelling", "data"], True)
    assert fields[0]["hint"] == "Point of the chain" and fields[0]["searches"] == ["requete 1.ris"]
    assert fields[1]["kind"] == "list" and fields[1]["searches"] == ["requete 1.ris", "requete 3.ris"]
    assert fields[2]["kind"] == "text" and warnings == ["Field 'odd': kind 'bizarre' is unknown, read as text"]
    back = es.from_csv(es.to_csv(fields, {}))                 # written with a searches column, read again
    assert [(f["name"], f.get("searches")) for f in back] == [(f["name"], f.get("searches")) for f in fields]


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
