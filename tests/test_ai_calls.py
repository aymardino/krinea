"""AI screening and extraction called through the root module names the Streamlit app uses,
with the provider call (krinea_core.llm.call_json) and the PDF reader replaced by fakes:
no network, no API key."""
import json

import pytest

import extraction_schema as es
import i18n
import screening
from krinea_core import llm, pdftext


def _fake_call_json(answer, calls):
    def fake(prompt, provider, api_key, model=None, purpose="screening", max_tokens=8192, max_retries=1):
        calls.append({"prompt": prompt, "provider": provider, "api_key": api_key, "model": model,
                      "purpose": purpose, "max_retries": max_retries})
        if isinstance(answer, Exception):
            raise answer
        return answer, llm.Usage(input_tokens=100, output_tokens=20)
    return fake


def test_ai_screen_uses_the_provider_and_parses_its_answer(monkeypatch):
    calls = []
    answer = {"decision": "Include", "reason": "", "rationale": "Mini-grids in Kenya", "confidence": 0.8}
    monkeypatch.setattr(llm, "call_json", _fake_call_json(answer, calls))
    record = {"title": "Solar mini-grids in Kenya", "abstract": "We model costs.", "year": "2020"}
    criteria = {"question": "Does decentralised electricity improve access?"}

    out = screening.ai_screen(record, criteria, "KEY", provider="gemini", model="gemini-test")

    assert out == {"decision": "include", "reason": "", "rationale": "Mini-grids in Kenya",
                   "confidence": 0.8, "model": "gemini-test"}
    [call] = calls
    assert (call["provider"], call["api_key"], call["model"], call["purpose"]) == \
        ("gemini", "KEY", "gemini-test", "screening")
    assert "Does decentralised electricity improve access?" in call["prompt"]
    assert "Title: Solar mini-grids in Kenya" in call["prompt"]


def test_ai_screen_full_text_stage_and_unparseable_answer(monkeypatch):
    calls = []
    monkeypatch.setattr(llm, "call_json", _fake_call_json(json.JSONDecodeError("bad", "x", 0), calls))
    out = screening.ai_screen({"title": "T"}, {"question": "Q?"}, "KEY", stage="ft", full_text="BODY")
    assert out["decision"] == "maybe" and out["model"] == "claude"
    assert "FULL TEXT:\nBODY" in calls[0]["prompt"]


def test_extract_pdf_reads_the_pdf_and_cleans_the_answer(monkeypatch, tmp_path):
    text = "We model solar mini-grids in Kenya with HOMER. " * 20
    seen_paths = []
    monkeypatch.setattr(pdftext, "extract_text", lambda path, *a, **k: seen_paths.append(path) or text)
    calls = []
    answer = {"authors": {"value": "Smith et al.", "quote": "J Smith, A Doe"},
              "study_design": {"value": "Modelling", "quote": "We model"},
              "outcomes": ["cost", "emissions"], "year": 2019}
    monkeypatch.setattr(llm, "call_json", _fake_call_json(answer, calls))
    fields = es.from_json("")
    pdf = str(tmp_path / "paper.pdf")

    values, quotes, out_text = es.extract_pdf(fields, pdf, "KEY", "claude", "model-x", context="Energy access")

    assert seen_paths == [pdf] and out_text == text
    assert values["authors"] == "Smith et al." and quotes["authors"] == "J Smith, A Doe"
    assert values["study_design"] == "modelling"
    assert values["outcomes"] == "cost, emissions" and values["year"] == "2019"
    [call] = calls
    assert (call["provider"], call["model"], call["purpose"]) == ("claude", "model-x", "extraction")
    assert "STUDY TEXT:\n" + text in call["prompt"]
    assert "Context of the review: Energy access" in call["prompt"]


def test_extract_pdf_refuses_text_too_short_to_be_a_paper(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(pdftext, "extract_text", lambda path, *a, **k: "scanned page")
    monkeypatch.setattr(llm, "call_json", _fake_call_json({}, calls))
    with pytest.raises(ValueError, match="too short"):
        es.extract_pdf(es.from_json(""), str(tmp_path / "scan.pdf"), "KEY", "claude", "model-x")
    assert calls == []                              # no tokens spent on an unreadable PDF


def test_pdftext_reads_a_real_pdf(tmp_path):
    import pymupdf
    path = tmp_path / "paper.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Solar mini-grids in Kenya")
    doc.save(str(path))
    doc.close()
    assert "Solar mini-grids in Kenya" in pdftext.extract_text(str(path))


def test_pdftext_keeps_head_and_tail_of_long_papers(monkeypatch):
    class Page:
        def __init__(self, text):
            self.text = text

        def get_text(self):
            return self.text

    class Doc(list):
        def close(self):
            pass

    body = "INTRO " + "x" * 2000 + " CONCLUSION"
    monkeypatch.setattr(pdftext.pymupdf, "open", lambda path: Doc([Page(body), Page("\x07")]))
    out = pdftext.extract_text("paper.pdf", max_chars=1000)
    assert out.startswith("INTRO ") and out.endswith(" CONCLUSION")
    assert "middle of paper omitted" in out and "\x07" not in out and len(out) <= 1000
    short = pdftext.extract_text("paper.pdf", max_chars=60)       # no room for a tail
    assert short.startswith("INTRO ") and "CONCLUSION" not in short


def test_energy_template_has_51_fields_and_the_ui_says_so():
    n = len(es.energy_template())
    assert n == 51
    assert f"({n} fields)" in i18n.t("load_energy_template", lang="en")
    assert f"({n} champs)" in i18n.t("load_energy_template", lang="fr")
