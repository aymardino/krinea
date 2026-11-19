"""AI screening runs: records go in the order the page sends them (the one on screen first); a
failure every record would hit stops the run at once and says what it means; a rate limit is
waited out; the result keeps the tally the page follows, and never shows the key."""
import io

from krinea_api.services import jobs
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
    assert (res["stage"], res["provider"], res["model"]) == ("ta", "gemini", "gemini-3.5-flash-lite")
    assert ["number 3" in prompt for prompt, *_ in seen] == [True, False]
    assert {(p, k, m) for _, p, k, m in seen} == {("gemini", KEY, "gemini-3.5-flash-lite")}
    assert job["user_id"]
    items = client.get(f"/reviews/{rid}/records?stage=ta&view=todo").json()["items"]
    assert [bool(x["ai"]) for x in items] == [True, False, True, False, False, False, False]


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
