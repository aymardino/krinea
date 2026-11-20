"""AI screening runs: a new review runs on Gemini 3.8 Flash; records go in the order the page
sends them (the one on screen first), or follow the page's whole list; a failure every record
would hit stops the run at once and says what it means; a rate limit is waited out; a long run
goes back in line between turns; the result keeps the tally the page follows, and never shows
the key."""
import io
import re

from krinea_api import models
from krinea_api.config import get_settings
from krinea_api.db import session_factory
from krinea_api.services import ai, jobs
from krinea_core import llm
from tests.conftest import register

KEY = "AQ.secret-test-key-1234567890"
RIS = "\n".join(f"TY  - JOUR\nAU  - Author {i}\nTI  - Solar mini-grid study number {i}\nPY  - 2020\nER  - \n"
                for i in range(1, 8))
ANSWER = {"decision": "include", "reason": "", "rationale": "On topic.", "confidence": 0.9}


class ProviderError(Exception):
    """Shaped like the provider SDKs' errors: an HTTP status and the provider's message."""
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code


def _review(client, email: str) -> tuple[str, list[int]]:
    register(client, email, "Owner")
    rid = client.post("/reviews", json={"title": "AI runs"}).json()["id"]
    r = client.post(f"/reviews/{rid}/imports", data={"source_db": "Scopus"},
                    files={"files": ("s.ris", io.BytesIO(RIS.encode()), "application/x-research-info-systems")})
    assert r.status_code == 201, r.text
    assert client.patch(f"/reviews/{rid}", json={"settings": {"ai_provider": "gemini"}}).status_code == 200
    assert client.put("/auth/keys/gemini", json={"key": KEY}).status_code == 200
    ids = [x["id"] for x in client.get(f"/reviews/{rid}/records?stage=ta&view=todo").json()["items"]]
    assert len(ids) == 7
    return rid, ids


def _run(client, rid: str, ids: list[int]) -> dict:
    job = client.post(f"/reviews/{rid}/ai/screen", json={"stage": "ta", "record_ids": ids, "limit": len(ids)}).json()
    assert job["status"] == "done", job
    return job


def test_a_new_review_runs_on_gemini_3_8_flash(client):
    register(client, "ai-default@example.org", "Owner")
    s = client.post("/reviews", json={"title": "Defaults"}).json()["settings"]
    assert (s["ai_provider"], s["ai_model_screening"], s["ai_model_extraction"]) == ("gemini", "", "")
    for review in (models.Review(settings=s), models.Review(settings={})):     # stored, or none at all
        for purpose in ("screening", "extraction"):
            assert ai.provider_and_model(review, purpose, None, None) == ("gemini", "gemini-3.8-flash")


def test_the_run_follows_the_order_sent_and_names_the_model(client, monkeypatch):
    rid, ids = _review(client, "ai-order@example.org")
    seen = []

    def answer(prompt, provider, key, model=None, **kw):
        seen.append((prompt, provider, key, model))
        return ANSWER, llm.Usage(10, 5)

    monkeypatch.setattr(llm, "call_json", answer)
    job = _run(client, rid, [ids[2], ids[0]])                  # the record on screen first
    res = job["result"]
    assert (res["ok"], res["failed"], res["total"], res["stopped"], res["error_kind"]) == (2, 0, 2, False, "")
    assert (res["stage"], res["provider"], res["model"]) == ("ta", "gemini", "gemini-3.8-flash")
    assert ["number 3" in prompt for prompt, *_ in seen] == [True, False]
    assert {(p, k, m) for _, p, k, m in seen} == {("gemini", KEY, "gemini-3.8-flash")}
    assert job["user_id"]
    items = client.get(f"/reviews/{rid}/records?stage=ta&view=todo").json()["items"]
    assert [bool(x["ai"]) for x in items] == [True, False, True, False, False, False, False]


def test_a_run_follows_the_whole_list_from_the_record_on_screen(client, monkeypatch):
    rid, ids = _review(client, "ai-queue@example.org")
    number = {rec: i for i, rec in enumerate(ids, 1)}                # "study number N", in import order
    seen = []

    def answer(prompt, provider, key, model=None, **kw):
        seen.append(int(re.search(r"study number (\d+)", prompt).group(1)))
        return ANSWER, llm.Usage(10, 5)

    monkeypatch.setattr(llm, "call_json", answer)
    assert client.post(f"/reviews/{rid}/records/{ids[3]}/decision", json={"stage": "ta", "decision": "exclude"}).status_code == 200
    # Title Z to A puts 7 first; the run starts at 5, goes down the list, round to the top, and
    # skips 4, which the reviewer decided.
    body = {"stage": "ta", "queue": {"view": "all", "sort": "title_desc"}, "start_id": ids[4], "limit": 3}
    preview = client.post(f"/reviews/{rid}/ai/screen/preview", json=body).json()
    assert preview == {"available": 6, "next": 3, "no_pdf": 0}
    job = client.post(f"/reviews/{rid}/ai/screen", json=body).json()
    assert job["status"] == "done" and job["result"]["ok"] == 3
    assert seen == [5, 3, 2]
    # Records with a suggestion are left out of the next run, unless they are to be redone.
    assert client.post(f"/reviews/{rid}/ai/screen/preview", json=body).json() == {"available": 3, "next": 3, "no_pdf": 0}
    assert client.post(f"/reviews/{rid}/ai/screen/preview", json={**body, "redo": True}).json() == {"available": 6, "next": 3, "no_pdf": 0}
    seen.clear()
    client.post(f"/reviews/{rid}/ai/screen", json={**body, "limit": 20000})
    assert seen == [1, 7, 6]
    seen.clear()
    client.post(f"/reviews/{rid}/ai/screen", json={**body, "redo": True, "start_id": ids[0], "limit": 2})
    assert seen == [1, 7]
    seen.clear()
    client.post(f"/reviews/{rid}/ai/screen", json={**body, "redo": True, "start_id": ids[6], "limit": 1})
    assert seen == [7]                                         # one record: the one on screen
    assert client.post(f"/reviews/{rid}/ai/screen/preview", json=body).json() == {"available": 0, "next": 0, "no_pdf": 0}
    # The list's filters apply: a search keeps only the records it finds.
    narrow = {**body, "redo": True, "queue": {"view": "all", "search": "number 2"}}
    assert client.post(f"/reviews/{rid}/ai/screen/preview", json=narrow).json() == {"available": 1, "next": 1, "no_pdf": 0}
    assert client.post(f"/reviews/{rid}/ai/screen/preview", json={**body, "queue": {"view": "bogus"}}).status_code == 400
    assert number[ids[4]] == 5


def test_screening_prompts_carry_the_research_question(client, monkeypatch):
    rid, ids = _review(client, "ai-question@example.org")
    assert client.patch(f"/reviews/{rid}", json={"question": "Do solar mini-grids lower electricity costs?"}).status_code == 200
    prompts = []

    def answer(prompt, provider, key, model=None, **kw):
        prompts.append(prompt)
        return ANSWER, llm.Usage(10, 5)

    monkeypatch.setattr(llm, "call_json", answer)
    _run(client, rid, ids[:1])
    assert "Research question: Do solar mini-grids lower electricity costs?" in prompts[0]


def test_full_text_runs_take_the_records_with_a_readable_pdf(client, monkeypatch, pdf_bytes):
    import pymupdf
    rid, ids = _review(client, "ai-fulltext@example.org")
    for rec in ids[:3]:                                        # kept at title and abstract
        assert client.post(f"/reviews/{rid}/records/{rec}/decision", json={"stage": "ta", "decision": "include"}).status_code == 200
    blank = pymupdf.open()
    blank.new_page()                                           # a scan: a page with no text layer
    for rec, name, data in ((ids[0], "paper.pdf", pdf_bytes), (ids[1], "scan.pdf", blank.tobytes())):
        assert client.post(f"/reviews/{rid}/records/{rec}/pdf", files={"file": (name, data, "application/pdf")}).status_code == 200
    prompts = []

    def answer(prompt, provider, key, model=None, **kw):
        prompts.append(prompt)
        return ANSWER, llm.Usage(10, 5)

    monkeypatch.setattr(llm, "call_json", answer)
    # The record without a PDF is left out; the scan is taken but left aside, the AI not asked.
    body = {"stage": "ft", "queue": {"view": "todo"}, "limit": 10}
    assert client.post(f"/reviews/{rid}/ai/screen/preview", json=body).json() == {"available": 2, "next": 2, "no_pdf": 1}
    res = client.post(f"/reviews/{rid}/ai/screen", json=body).json()["result"]
    assert (res["ok"], res["skipped"], res["failed"], res["total"], res["stopped"]) == (1, 1, 0, 2, False)
    assert len(prompts) == 1 and "FULL TEXT:" in prompts[0] and "HOMER" in prompts[0]


def test_a_pdf_lost_from_storage_is_cleared_so_it_can_be_added_again(client, pdf_bytes):
    from krinea_api.services import storage
    rid, ids = _review(client, "ai-lostpdf@example.org")
    rec = ids[0]
    assert client.post(f"/reviews/{rid}/records/{rec}/decision", json={"stage": "ta", "decision": "include"}).status_code == 200
    assert client.post(f"/reviews/{rid}/records/{rec}/pdf", files={"file": ("paper.pdf", pdf_bytes, "application/pdf")}).status_code == 200
    db = session_factory()()
    try:
        key = db.get(models.Record, rec).pdf_key
    finally:
        db.close()
    storage.delete_pdf(key)                                    # a server disk emptied by a deploy
    r = client.get(f"/reviews/{rid}/records/{rec}/pdf")
    assert r.status_code == 404 and "no longer stored" in r.json()["detail"]
    after = client.get(f"/reviews/{rid}/records/{rec}").json()
    assert (after["has_pdf"], after["pdf_status"]) == (False, "")
    body = {"stage": "ft", "queue": {"view": "todo"}, "limit": 5}
    assert client.post(f"/reviews/{rid}/ai/screen/preview", json=body).json() == {"available": 0, "next": 0, "no_pdf": 1}
    assert client.get("/health").json()["pdf_storage"] == "local"


def test_a_long_run_goes_back_in_line_between_turns(client, monkeypatch):
    rid, ids = _review(client, "ai-turns@example.org")
    monkeypatch.setattr(llm, "call_json", lambda prompt, provider, key, model=None, **kw: (ANSWER, llm.Usage(10, 5)))
    monkeypatch.setattr(jobs, "AI_CHUNK", 3)
    # Jobs run inline (tests, development): the turns follow each other at once.
    res = _run(client, rid, ids)["result"]
    assert (res["ok"], res["done"], res["total"]) == (7, 7, 7)
    # With a worker, the job goes back to the end of the queue after each turn of 3 records.
    monkeypatch.setattr(get_settings(), "inline_jobs", False)
    job = client.post(f"/reviews/{rid}/ai/screen", json={"stage": "ta", "record_ids": ids, "limit": len(ids)}).json()
    assert job["status"] == "queued"
    db = session_factory()()
    try:
        placed = []
        for done, status in ((3, "queued"), (6, "queued"), (7, "done")):
            jobs.run_job(job["id"])
            db.expire_all()
            row = db.get(models.Job, job["id"])
            assert (row.status, row.result["done"], row.result["ok"]) == (status, done, done)
            placed.append(row.created_at)
        assert placed[0] <= placed[1] and row.progress == 1.0 and row.started_at is not None
    finally:
        db.close()


def test_a_model_closed_to_the_key_stops_the_run_at_once(client, monkeypatch):
    rid, ids = _review(client, "ai-model@example.org")
    calls = []

    def refused(prompt, provider, key, model=None, **kw):
        calls.append(model)
        raise ProviderError(404, f"models/{model} is not found for API version v1beta (sent with {key})")

    monkeypatch.setattr(llm, "call_json", refused)
    res = _run(client, rid, ids)["result"]
    assert len(calls) == 1                                     # not seven times the same failure
    assert (res["ok"], res["failed"], res["stopped"], res["error_kind"]) == (0, 1, True, "model")
    assert "not found" in res["error"] and KEY not in res["error"] and "[key]" in res["error"]
    assert all(KEY not in e for e in res["errors"])


def test_rate_limits_are_waited_out_and_a_daily_quota_stops(client, monkeypatch):
    rid, ids = _review(client, "ai-quota@example.org")
    waits: list[float] = []
    monkeypatch.setattr(jobs.time, "sleep", waits.append)
    replies = [ProviderError(429, "RESOURCE_EXHAUSTED {'quotaId': 'PerMinute', 'retryDelay': '31s'}"), ANSWER,
               ProviderError(429, "RESOURCE_EXHAUSTED {'quotaId': 'GenerateRequestsPerDayPerProjectPerModel'}")]

    def limited(prompt, provider, key, model=None, **kw):
        reply = replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply, llm.Usage(10, 5)

    monkeypatch.setattr(llm, "call_json", limited)
    res = _run(client, rid, ids[:3])["result"]
    assert waits == [32.0] and replies == []
    assert (res["ok"], res["failed"], res["stopped"], res["error_kind"]) == (1, 1, True, "quota")


def test_unreadable_answers_are_skipped_until_five_in_a_row(client, monkeypatch):
    rid, ids = _review(client, "ai-output@example.org")
    replies = [llm.LLMError("gemini/x did not return valid JSON: Expecting value"), ANSWER]
    replies += [llm.LLMError("gemini/x did not return valid JSON: Expecting value")] * 5

    def flaky(prompt, provider, key, model=None, **kw):
        reply = replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply, llm.Usage(10, 5)

    monkeypatch.setattr(llm, "call_json", flaky)
    res = _run(client, rid, ids)["result"]
    assert replies == []
    assert (res["ok"], res["failed"], res["stopped"], res["error_kind"]) == (1, 6, True, "output")
    assert len(res["errors"]) == 5
